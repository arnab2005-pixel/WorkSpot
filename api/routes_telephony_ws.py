"""
Real-time full-duplex telephony WebSocket gateway for FreeSWITCH mod_audio_fork.
Path: /ws/media/{session_id}

Handles:
- Ingress 8kHz 16-bit Mono Linear PCM audio stream
- Dual-channel async message loops (Binary audio + JSON control events)
- Concurrency worker queues (ingress -> VAD -> ASR -> FSM -> TTS -> egress)
- Sub-second barge-in detection with buffer clearing
- Complete resource teardown on hangup/disconnect
"""

import asyncio
import json
import logging

import numpy as np
from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from config.config import get_settings
from schemas.websocket_events import (
    ClearBufferEvent,
    TranscriptFinalEvent,
    WSMessageType,
)
from services.asr.whisper_worker import WhisperASRWorker
from services.audio.resampler import AudioResampler
from services.audio.vad_filter import SileroVAD, VADState
from services.orchestrator.state_machine import ConversationFSM
from services.tts.indic_tts_worker import IndicTTSWorker

logger = logging.getLogger(__name__)
settings = get_settings()

router = APIRouter(tags=["telephony"])


class TelephonyCallSession:
    """
    Manages active telephony call lifecycle, background worker tasks, and queues.
    """

    def __init__(
        self,
        session_id: str,
        websocket: WebSocket,
        fsm: ConversationFSM,
        vad: SileroVAD,
        resampler: AudioResampler,
        asr: WhisperASRWorker,
        tts: IndicTTSWorker,
    ):
        self.session_id = session_id
        self.ws = websocket
        self.fsm = fsm
        self.vad = vad
        self.resampler = resampler
        self.asr = asr
        self.tts = tts

        # Queues for decoupled non-blocking processing
        self.raw_audio_queue: asyncio.Queue[bytes] = asyncio.Queue(maxsize=200)
        self.asr_queue: asyncio.Queue[np.ndarray] = asyncio.Queue(maxsize=10)
        self.tts_text_queue: asyncio.Queue[str] = asyncio.Queue(maxsize=5)

        # State flags
        self.is_running = True
        self.is_tts_playing = False
        self.barge_in_event = asyncio.Event()

        # Background worker tasks
        self.tasks: list[asyncio.Task] = []

    async def start(self):
        """Start all async pipeline workers."""
        self.tasks = [
            asyncio.create_task(self._vad_worker(), name="vad_worker"),
            asyncio.create_task(self._asr_worker(), name="asr_worker"),
            asyncio.create_task(self._tts_worker(), name="tts_worker"),
        ]

    async def stop(self):
        """Cancel and tear down all tasks and buffers."""
        self.is_running = False
        for task in self.tasks:
            task.cancel()
        await asyncio.gather(*self.tasks, return_exceptions=True)
        self.tasks.clear()

    async def send_control_event(self, event_dict: dict):
        """Send JSON control frame to FreeSWITCH / client."""
        try:
            await self.ws.send_text(json.dumps(event_dict, ensure_ascii=False))
        except Exception as exc:  # noqa: BLE001 - logging-only failure
            logger.debug("Failed to send WS control frame: %s", exc)

    async def handle_barge_in(self):
        """Interrupt active TTS synthesis and instruct FreeSWITCH to clear playout buffer."""
        if self.is_tts_playing:
            logger.info(f"[{self.session_id}] Barge-in detected! Halting TTS playback.")
            self.is_tts_playing = False
            self.barge_in_event.set()

            # Clear pending TTS text
            while not self.tts_text_queue.empty():
                try:
                    self.tts_text_queue.get_nowait()
                except asyncio.QueueEmpty:
                    break

            # Send CLEAR_BUFFER directive to FreeSWITCH
            clear_event = ClearBufferEvent(
                session_id=self.session_id,
                reason="BARGE_IN_DETECTED",
            )
            await self.send_control_event(clear_event.model_dump(mode="json"))

    async def _vad_worker(self):
        """Worker 1: Consumes 8kHz raw PCM, resamples to 16kHz, performs VAD segmentation."""
        # 32ms window at 8kHz = 256 samples = 512 bytes
        window_bytes = self.vad.window_size * 2
        audio_accumulator = bytearray()
        voiced_frames: list[np.ndarray] = []

        try:
            while self.is_running:
                chunk = await self.raw_audio_queue.get()
                audio_accumulator.extend(chunk)

                while len(audio_accumulator) >= window_bytes:
                    raw_frame = bytes(audio_accumulator[:window_bytes])
                    del audio_accumulator[:window_bytes]

                    # Convert to float32
                    frame_float = self.resampler.pcm16_to_float32(raw_frame)
                    vad_result = self.vad.process_frame(frame_float)

                    if vad_result.is_speech:
                        # User is speaking
                        await self.handle_barge_in()
                        voiced_frames.append(frame_float)

                    elif vad_result.state == VADState.SPEECH_ENDED:
                        # End of speech detected (>400ms silence after speech)
                        if voiced_frames:
                            full_utterance_8k = np.concatenate(voiced_frames)
                            voiced_frames.clear()

                            # Resample to 16kHz for Whisper
                            utterance_16k = self.resampler.resample_array(
                                full_utterance_8k,
                                src_rate=settings.audio_sample_rate_telephony,
                                dst_rate=settings.audio_sample_rate_asr,
                            )
                            # Hand off to ASR worker
                            await self.asr_queue.put(utterance_16k)
                        self.vad.reset()

        except asyncio.CancelledError:
            pass

    async def _asr_worker(self):
        """Worker 2: Consumes 16kHz speech segments, executes faster-whisper and FSM."""
        try:
            while self.is_running:
                utterance_16k = await self.asr_queue.get()
                result = await self.asr.transcribe(utterance_16k, sample_rate=16000)

                # Send final transcript to client
                transcript_event = TranscriptFinalEvent(
                    session_id=self.session_id,
                    text=result.text or "",
                    language=result.language,
                    confidence=result.confidence,
                    duration_ms=result.duration_ms,
                    asr_latency_ms=result.latency_ms,
                    is_hallucinated=result.is_hallucinated,
                )
                await self.send_control_event(transcript_event.model_dump(mode="json"))

                if result.is_hallucinated and result.fallback_prompt_indic:
                    await self.tts_text_queue.put(result.fallback_prompt_indic)
                    continue

                if not result.text:
                    continue

                # Run LangGraph FSM step
                fsm_response = await self.fsm.step(self.session_id, result.text)
                spoken_text = fsm_response.get("spoken_response_indic")
                if spoken_text:
                    await self.tts_text_queue.put(spoken_text)

        except asyncio.CancelledError:
            pass

    async def _tts_worker(self):
        """Worker 3: Incrementally synthesizes response and streams 20ms frames to WebSocket."""
        try:
            while self.is_running:
                text = await self.tts_text_queue.get()
                self.barge_in_event.clear()
                self.is_tts_playing = True

                try:
                    async for pcm_frame in self.tts.stream_tts_frames(text):
                        if self.barge_in_event.is_set():
                            break
                        # Stream raw 20ms 8kHz PCM to FreeSWITCH
                        await self.ws.send_bytes(pcm_frame)
                finally:
                    self.is_tts_playing = False

        except asyncio.CancelledError:
            pass


# Singleton service instances
fsm_engine = ConversationFSM()
vad_engine = SileroVAD(sample_rate=settings.audio_sample_rate_telephony)
resampler_engine = AudioResampler()
asr_engine = WhisperASRWorker()
tts_engine = IndicTTSWorker()


@router.websocket("/ws/media/{session_id}")
async def telephony_media_ws(websocket: WebSocket, session_id: str):
    """
    Real-Time Full-Duplex Telephony Protocol WebSocket endpoint.
    Conforms to Section 5.2 of the Specification.
    """
    await websocket.accept()
    logger.info(f"Telephony WebSocket connection established for session {session_id}")

    session = TelephonyCallSession(
        session_id=session_id,
        websocket=websocket,
        fsm=fsm_engine,
        vad=vad_engine,
        resampler=resampler_engine,
        asr=asr_engine,
        tts=tts_engine,
    )
    await session.start()

    try:
        while True:
            message = await websocket.receive()

            if message.get("bytes"):
                # Ingress raw 8kHz PCM audio chunk
                raw_bytes = message["bytes"]
                await session.raw_audio_queue.put(raw_bytes)

            elif message.get("text"):
                # Ingress JSON control frame
                try:
                    payload = json.loads(message["text"])
                    event_type = payload.get("event")

                    if event_type == WSMessageType.START_CALL:
                        caller_id = payload.get("caller_id", "anonymous")
                        await fsm_engine.init_session(
                            session_id=session_id,
                            caller_id=caller_id,
                            call_uuid=payload.get("call_uuid"),
                        )
                        # Trigger initial greeting
                        await session.tts_text_queue.put(
                            "नमस्ते! हम पीएम-अजय योजना सहायक बोल रहे हैं। क्या हम बातचीत शुरू कर सकते हैं?"
                        )

                    elif event_type == WSMessageType.HANGUP:
                        logger.info(f"Hangup event received for session {session_id}")
                        break

                    elif event_type == WSMessageType.BARGE_IN:
                        await session.handle_barge_in()

                except (json.JSONDecodeError, KeyError) as json_err:
                    logger.warning("Error parsing WS text message: %s", json_err)

    except WebSocketDisconnect:
        logger.info("Telephony WebSocket disconnected for session %s", session_id)
    except Exception:
        logger.exception("Error in telephony WebSocket loop")
    finally:
        await session.stop()
        logger.info(f"Telephony session resources cleaned up for {session_id}")
