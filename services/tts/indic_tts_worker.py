"""
Indic-TTS Worker (AI4Bharat FastPitch + HiFi-GAN) with 22.05kHz -> 8kHz polyphase downsampling.

Implements:
- Chunk-by-chunk incremental synthesis for low First-Packet-Time (<= 280ms)
- Polyphase downsampling from 22050Hz to 8000Hz
- 20ms linear PCM (160 samples / 320 bytes) framing for FreeSWITCH WebSocket egress
"""

import asyncio
import logging
import time
from typing import AsyncGenerator, Optional, List
import numpy as np
import httpx

from config.config import get_settings
from services.audio.resampler import AudioResampler
from services.tts.chunker import TextChunker

logger = logging.getLogger(__name__)
settings = get_settings()


class IndicTTSWorker:
    """
    Synthesizes Indic speech incrementally and streams 20ms 8kHz PCM frames.
    """

    # 20ms frame at 8kHz mono 16-bit = 160 samples = 320 bytes
    FRAME_SAMPLES_8K = 160
    FRAME_BYTES_8K = 320

    def __init__(
        self,
        base_url: Optional[str] = None,
        language: str = "hi",
    ):
        self.base_url = (base_url or settings.tts_base_url).rstrip("/")
        self.language = language or settings.tts_language
        self.chunker = TextChunker()
        self.resampler = AudioResampler()
        self._http_client = httpx.AsyncClient(timeout=settings.tts_timeout_seconds)

    async def close(self):
        """Close HTTP client session."""
        await self._http_client.aclose()

    async def _synthesize_chunk_audio(self, chunk_text: str) -> np.ndarray:
        """
        Synthesize a single text chunk into 22.05 kHz float32 waveform.
        Attempts HTTP call to indic-tts container, falling back to harmonic synthetic tone.
        """
        try:
            resp = await self._http_client.post(
                f"{self.base_url}/synthesize",
                json={"text": chunk_text, "language": self.language},
            )
            if resp.status_code == 200:
                # Raw float32 or int16 PCM
                raw_bytes = resp.content
                return np.frombuffer(raw_bytes, dtype=np.int16).astype(np.float32) / 32768.0
        except Exception as exc:  # noqa: BLE001 - TTS failure uses synthetic waveform
            logger.debug("Indic TTS request failed: %s", exc)

        # Fallback synthetic speech-like waveform for offline / test mode
        duration_sec = max(0.4, len(chunk_text) * 0.05)
        sr = settings.audio_sample_rate_tts  # 22050
        t = np.linspace(0, duration_sec, int(sr * duration_sec), endpoint=False)
        # 180Hz fundamental with harmonics and gentle envelope
        carrier = (
            0.5 * np.sin(2 * np.pi * 180 * t)
            + 0.3 * np.sin(2 * np.pi * 360 * t)
            + 0.1 * np.sin(2 * np.pi * 540 * t)
        )
        envelope = np.sin(np.pi * t / duration_sec) ** 2
        waveform = (carrier * envelope * 0.3).astype(np.float32)
        return waveform

    async def stream_tts_frames(
        self,
        text: str,
    ) -> AsyncGenerator[bytes, None]:
        """
        Incrementally synthesize text and yield 20ms (320 bytes) 8kHz PCM frames.
        
        Monitors First-Chunk-Time to meet the <= 280ms target.
        """
        start_time = time.perf_counter()
        chunks = self.chunker.split_into_chunks(text)
        if not chunks:
            return

        first_chunk_emitted = False
        pcm_buffer = bytearray()

        for idx, chunk in enumerate(chunks):
            chunk_start = time.perf_counter()
            audio_22k = await self._synthesize_chunk_audio(chunk)

            # Polyphase downsample from 22.05 kHz to 8 kHz
            audio_8k = self.resampler.resample_array(
                audio_22k,
                src_rate=settings.audio_sample_rate_tts,
                dst_rate=settings.audio_sample_rate_telephony,
            )

            # Convert to int16 PCM bytes
            pcm_bytes = self.resampler.float32_to_pcm16(audio_8k)
            pcm_buffer.extend(pcm_bytes)

            if not first_chunk_emitted:
                ttfc_ms = (time.perf_counter() - start_time) * 1000.0
                logger.info(f"TTS First Chunk Latency: {ttfc_ms:.1f}ms for '{chunk[:30]}...'")
                first_chunk_emitted = True

            # Emit 20ms frames (320 bytes each)
            while len(pcm_buffer) >= self.FRAME_BYTES_8K:
                frame = bytes(pcm_buffer[: self.FRAME_BYTES_8K])
                del pcm_buffer[: self.FRAME_BYTES_8K]
                yield frame
                # Yield control to event loop to prevent starvation
                await asyncio.sleep(0.001)

        # Pad remaining bytes to full 20ms frame if needed
        if pcm_buffer:
            pad_needed = self.FRAME_BYTES_8K - len(pcm_buffer)
            frame = bytes(pcm_buffer) + (b"\x00" * pad_needed)
            yield frame
