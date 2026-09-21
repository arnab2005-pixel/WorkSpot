"""
Silero VAD v5 integration for voice activity detection.

Implements real-time VAD with:
- 32ms/64ms window processing at 8kHz or 16kHz
- Pre-speech buffer retention (300ms) to prevent clipping
- Silence threshold tracking for SPEECH_ENDED detection
- ONNX runtime for CPU/GPU inference
"""

import asyncio
import logging
from collections import deque
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Optional, Deque, List
import numpy as np
import onnxruntime as ort

from config.config import get_settings

logger = logging.getLogger(__name__)
settings = get_settings()


class VADState(Enum):
    """VAD processing states."""
    IDLE = "IDLE"                    # Waiting for speech
    PRE_SPEECH = "PRE_SPEECH"        # Buffering pre-speech audio
    SPEECH = "SPEECH"                # Active speech detected
    SPEECH_ENDED = "SPEECH_ENDED"    # Silence after speech - endpoint detected
    RESET = "RESET"                  # Reset buffers for next utterance


@dataclass
class VADResult:
    """Result of VAD processing for a single audio frame."""
    state: VADState
    probability: float                    # Voice probability [0, 1]
    is_speech: bool                       # Binary speech decision
    frame: np.ndarray                     # Audio frame (may include pre-speech)
    pre_speech_buffer: Optional[np.ndarray] = None  # Buffered pre-speech audio
    speech_duration_ms: int = 0           # Accumulated speech duration
    silence_duration_ms: int = 0          # Accumulated silence duration
    metadata: dict = field(default_factory=dict)


class SileroVAD:
    """
    Silero VAD v5 wrapper with ring buffer management.
    
    Features:
    - ONNX model inference (CPU optimized)
    - Configurable thresholds and timing
    - Pre-speech ring buffer (300ms default)
    - Consecutive silence tracking for endpoint detection
    - Thread-safe async processing
    """
    
    # Silero VAD v5 expects specific window sizes
    WINDOW_SIZE_8K = 256   # 32ms at 8kHz
    WINDOW_SIZE_16K = 512  # 32ms at 16kHz
    
    def __init__(
        self,
        sample_rate: int = 8000,
        threshold: float = 0.5,
        min_speech_duration_ms: int = 250,
        min_silence_duration_ms: int = 400,
        pre_speech_buffer_ms: int = 300,
        model_path: Optional[str] = None,
        providers: Optional[List[str]] = None,
    ):
        """
        Initialize Silero VAD.
        
        Args:
            sample_rate: Audio sample rate (8000 or 16000)
            threshold: Voice probability threshold for speech detection
            min_speech_duration_ms: Minimum speech duration before endpoint detection
            min_silence_duration_ms: Silence duration to trigger SPEECH_ENDED
            pre_speech_buffer_ms: Pre-speech audio to retain (prevent clipping)
            model_path: Path to ONNX model file
            providers: ONNX Runtime providers (e.g., ['CUDAExecutionProvider', 'CPUExecutionProvider'])
        """
        if sample_rate not in (8000, 16000):
            raise ValueError("Sample rate must be 8000 or 16000")
        
        self.sample_rate = sample_rate
        self.threshold = threshold
        self.min_speech_duration_ms = min_speech_duration_ms
        self.min_silence_duration_ms = min_silence_duration_ms
        self.pre_speech_buffer_ms = pre_speech_buffer_ms
        
        # Window configuration
        self.window_size = self.WINDOW_SIZE_8K if sample_rate == 8000 else self.WINDOW_SIZE_16K
        self.window_duration_ms = (self.window_size / sample_rate) * 1000  # ~32ms
        
        # Pre-speech buffer: number of frames to retain
        self.pre_speech_frames = max(1, int(pre_speech_buffer_ms / self.window_duration_ms))
        
        # Load ONNX model
        self._load_model(model_path, providers)
        
        # State
        self.state = VADState.IDLE
        self.pre_speech_buffer: Deque[np.ndarray] = deque(maxlen=self.pre_speech_frames)
        self.speech_frames: List[np.ndarray] = []
        self.speech_duration_ms = 0
        self.silence_duration_ms = 0
        self.consecutive_speech_frames = 0
        self.consecutive_silence_frames = 0
        
        # Metrics
        self.total_frames_processed = 0
        self.total_inference_time_ms = 0.0
        
        logger.info(
            f"SileroVAD initialized: sr={sample_rate}Hz, "
            f"window={self.window_size} samples ({self.window_duration_ms:.1f}ms), "
            f"threshold={threshold}, pre_buffer={pre_speech_buffer_ms}ms"
        )
    
    def _load_model(self, model_path: Optional[str], providers: Optional[List[str]]):
        """Load Silero VAD ONNX model with fallback."""
        if providers is None:
            providers = ['CPUExecutionProvider']
        
        self.session = None
        self.state_tensor = np.zeros((2, 1, 128), dtype=np.float32)  # v5 state
        self.h = np.zeros((1, 64), dtype=np.float32)  # v4 state
        self.c = np.zeros((1, 64), dtype=np.float32)  # v4 state
        
        possible_paths = []
        if model_path:
            possible_paths.append(Path(model_path))
        possible_paths.extend([
            Path(__file__).parent.parent.parent / "models" / "silero_vad_v5.onnx",
            Path.cwd() / "models" / "silero_vad_v5.onnx",
            Path("/models/silero_vad_v5.onnx"),
        ])
        
        resolved_path = None
        for p in possible_paths:
            if p.exists():
                resolved_path = str(p)
                break
        
        if resolved_path is None:
            try:
                resolved_path = self._download_model()
            except Exception as dl_err:  # noqa: BLE001 - download failure fallback
                logger.warning("Could not download Silero VAD model: %s. Falling back to energy VAD.", dl_err)
                return

        try:
            self.session = ort.InferenceSession(resolved_path, providers=providers)
            self.input_names = [inp.name for inp in self.session.get_inputs()]
            self.output_names = [out.name for out in self.session.get_outputs()]
            logger.info("Loaded Silero VAD model from %s with inputs: %s", resolved_path, self.input_names)
        except Exception as exc:  # noqa: BLE001 - ONNX session failure fallback
            logger.warning("Failed to load Silero VAD ONNX session: %s. Falling back to energy VAD.", exc)
            self.session = None

    def _download_model(self) -> str:
        """Download Silero VAD v5 ONNX model."""
        import urllib.request
        
        model_dir = Path(__file__).parent.parent.parent / "models"
        model_dir.mkdir(exist_ok=True, parents=True)
        model_path = model_dir / "silero_vad_v5.onnx"
        
        url = "https://github.com/snakers4/silero-vad/raw/master/files/silero_vad_v5.onnx"
        logger.info(f"Downloading Silero VAD model from {url}...")
        urllib.request.urlretrieve(url, model_path)
        logger.info(f"Model downloaded to {model_path}")
        return str(model_path)

    def reset(self):
        """Reset VAD state for new utterance."""
        self.state = VADState.IDLE
        self.pre_speech_buffer.clear()
        self.speech_frames.clear()
        self.speech_duration_ms = 0
        self.silence_duration_ms = 0
        self.consecutive_speech_frames = 0
        self.consecutive_silence_frames = 0
        self.state_tensor.fill(0)
        self.h.fill(0)
        self.c.fill(0)

    def process_frame(self, frame: np.ndarray) -> VADResult:
        """
        Process a single audio frame through VAD.
        
        Args:
            frame: Audio frame as float32 numpy array [-1, 1]
                   Shape: (window_size,) for mono
            
        Returns:
            VADResult with state, probability, and audio data
        """
        if len(frame) != self.window_size:
            raise ValueError(f"Frame must be {self.window_size} samples, got {len(frame)}")
        
        if frame.dtype != np.float32:
            frame = frame.astype(np.float32)

        import time
        start = time.perf_counter()

        if self.session is not None:
            try:
                if "sr" in self.input_names and "state" in self.input_names:
                    # Silero VAD v5 layout
                    ort_inputs = {
                        self.input_names[0]: frame.reshape(1, -1),
                        "state": self.state_tensor,
                        "sr": np.array([self.sample_rate], dtype=np.int64),
                    }
                    outs = self.session.run(None, ort_inputs)
                    prob = float(outs[0][0, 0])
                    if len(outs) > 1:
                        self.state_tensor = outs[1]
                elif "h" in self.input_names and "c" in self.input_names:
                    # Silero VAD v4 layout
                    ort_inputs = {
                        self.input_names[0]: frame.reshape(1, -1),
                        "h": self.h,
                        "c": self.c,
                    }
                    outs = self.session.run(None, ort_inputs)
                    prob = float(outs[0][0, 0])
                    if len(outs) > 1:
                        self.h = outs[1]
                    if len(outs) > 2:
                        self.c = outs[2]
                else:
                    ort_inputs = {self.input_names[0]: frame.reshape(1, -1)}
                    outs = self.session.run(None, ort_inputs)
                    prob = float(outs[0].flatten()[0])
            except Exception as exc:  # noqa: BLE001 - ONNX inference fallback
                logger.debug("VAD inference error: %s, falling back to energy.", exc)
                rms = float(np.sqrt(np.mean(frame ** 2)))
                prob = min(1.0, rms * 15.0)
        else:
            # Fallback energy-based probability
            rms = float(np.sqrt(np.mean(frame ** 2)))
            prob = min(1.0, rms * 15.0)

        inference_time = (time.perf_counter() - start) * 1000
        self.total_inference_time_ms += inference_time
        self.total_frames_processed += 1

        # Determine state transition
        is_speech = prob >= self.threshold
        result = self._update_state(is_speech, prob, frame)
        return result
    
    def _update_state(
        self, 
        is_speech: bool, 
        probability: float, 
        frame: np.ndarray
    ) -> VADResult:
        """Update VAD state machine."""
        
        if self.state == VADState.IDLE:
            if is_speech:
                # Speech started - transition to PRE_SPEECH
                self.state = VADState.PRE_SPEECH
                self.consecutive_speech_frames = 1
                self.consecutive_silence_frames = 0
                self.speech_frames.append(frame.copy())
                self.speech_duration_ms += self.window_duration_ms
                
                # Include pre-speech buffer
                pre_speech = np.concatenate(list(self.pre_speech_buffer)) if self.pre_speech_buffer else None
                
                return VADResult(
                    state=VADState.PRE_SPEECH,
                    probability=probability,
                    is_speech=True,
                    frame=frame,
                    pre_speech_buffer=pre_speech,
                    speech_duration_ms=self.speech_duration_ms,
                    silence_duration_ms=0,
                )
            else:
                # Still silence - add to pre-speech buffer
                self.pre_speech_buffer.append(frame.copy())
                return VADResult(
                    state=VADState.IDLE,
                    probability=probability,
                    is_speech=False,
                    frame=frame,
                    speech_duration_ms=0,
                    silence_duration_ms=0,
                )
        
        elif self.state == VADState.PRE_SPEECH:
            if is_speech:
                self.consecutive_speech_frames += 1
                self.consecutive_silence_frames = 0
                self.speech_frames.append(frame.copy())
                self.speech_duration_ms += self.window_duration_ms
                
                # Check if minimum speech duration reached
                if self.speech_duration_ms >= self.min_speech_duration_ms:
                    self.state = VADState.SPEECH
                
                return VADResult(
                    state=self.state,
                    probability=probability,
                    is_speech=True,
                    frame=frame,
                    speech_duration_ms=self.speech_duration_ms,
                    silence_duration_ms=0,
                )
            else:
                # Silence during pre-speech - might be false start
                self.consecutive_silence_frames += 1
                if self.consecutive_silence_frames * self.window_duration_ms >= 100:  # 100ms grace
                    # False alarm - reset to IDLE
                    self.reset()
                    self.pre_speech_buffer.append(frame.copy())
                    return VADResult(
                        state=VADState.IDLE,
                        probability=probability,
                        is_speech=False,
                        frame=frame,
                    )
                else:
                    # Brief silence, keep buffering
                    self.speech_frames.append(frame.copy())
                    return VADResult(
                        state=VADState.PRE_SPEECH,
                        probability=probability,
                        is_speech=False,
                        frame=frame,
                        speech_duration_ms=self.speech_duration_ms,
                    )
        
        elif self.state == VADState.SPEECH:
            if is_speech:
                self.consecutive_speech_frames += 1
                self.consecutive_silence_frames = 0
                self.speech_frames.append(frame.copy())
                self.speech_duration_ms += self.window_duration_ms
                
                return VADResult(
                    state=VADState.SPEECH,
                    probability=probability,
                    is_speech=True,
                    frame=frame,
                    speech_duration_ms=self.speech_duration_ms,
                    silence_duration_ms=0,
                )
            else:
                # Silence during speech - start counting for endpoint
                self.consecutive_silence_frames += 1
                self.silence_duration_ms += self.window_duration_ms
                self.speech_frames.append(frame.copy())  # Include trailing silence
                
                if self.silence_duration_ms >= self.min_silence_duration_ms:
                    # Endpoint detected!
                    self.state = VADState.SPEECH_ENDED
                    
                    # Return complete utterance
                    full_audio = np.concatenate(self.speech_frames)
                    pre_speech = np.concatenate(list(self.pre_speech_buffer)) if self.pre_speech_buffer else None
                    
                    return VADResult(
                        state=VADState.SPEECH_ENDED,
                        probability=probability,
                        is_speech=False,
                        frame=full_audio,
                        pre_speech_buffer=pre_speech,
                        speech_duration_ms=self.speech_duration_ms,
                        silence_duration_ms=self.silence_duration_ms,
                        metadata={"utterance_complete": True}
                    )
                else:
                    return VADResult(
                        state=VADState.SPEECH,
                        probability=probability,
                        is_speech=False,
                        frame=frame,
                        speech_duration_ms=self.speech_duration_ms,
                        silence_duration_ms=self.silence_duration_ms,
                    )
        
        elif self.state == VADState.SPEECH_ENDED:
            # Utterance complete, reset for next
            self.reset()
            return VADResult(
                state=VADState.RESET,
                probability=probability,
                is_speech=False,
                frame=frame,
            )
        
        return VADResult(
            state=self.state,
            probability=probability,
            is_speech=is_speech,
            frame=frame,
        )
    
    def process_bytes(self, audio_bytes: bytes) -> VADResult:
        """
        Process raw PCM bytes.
        
        Args:
            audio_bytes: Raw 16-bit PCM bytes (2 bytes per sample)
            
        Returns:
            VADResult
        """
        # Convert bytes to float32 [-1, 1]
        samples = np.frombuffer(audio_bytes, dtype=np.int16)
        frame = samples.astype(np.float32) / 32768.0
        return self.process_frame(frame)
    
    async def process_stream(
        self, 
        audio_queue: asyncio.Queue,
        output_queue: asyncio.Queue
    ) -> None:
        """
        Process audio stream from queue.
        
        Args:
            audio_queue: Input queue with raw audio bytes
            output_queue: Output queue for VADResult
        """
        while True:
            try:
                chunk = await audio_queue.get()
                if chunk is None:  # Shutdown signal
                    break
                
                result = self.process_bytes(chunk)
                await output_queue.put(result)
                
            except asyncio.CancelledError:
                break
            except Exception as exc:  # noqa: BLE001 - stream error recovery
                logger.error("VAD stream processing error: %s", exc)
                await output_queue.put(VADResult(
                    state=VADState.ERROR,
                    probability=0.0,
                    is_speech=False,
                    frame=np.zeros(self.window_size, dtype=np.float32),
                    metadata={"error": str(exc)}
                ))
    
    def get_stats(self) -> dict:
        """Get VAD processing statistics."""
        avg_inference = (
            self.total_inference_time_ms / self.total_frames_processed 
            if self.total_frames_processed > 0 else 0
        )
        return {
            "total_frames": self.total_frames_processed,
            "avg_inference_ms": avg_inference,
            "current_state": self.state.value,
            "speech_duration_ms": self.speech_duration_ms,
            "silence_duration_ms": self.silence_duration_ms,
        }


# Global VAD instance for 8kHz (telephony)
_vad_8k: Optional[SileroVAD] = None
_vad_16k: Optional[SileroVAD] = None


def get_vad_8k() -> SileroVAD:
    """Get or create 8kHz VAD instance."""
    global _vad_8k
    if _vad_8k is None:
        _vad_8k = SileroVAD(
            sample_rate=8000,
            threshold=settings.vad_threshold,
            min_speech_duration_ms=settings.vad_min_speech_duration_ms,
            min_silence_duration_ms=settings.vad_min_silence_duration_ms,
            pre_speech_buffer_ms=settings.vad_pre_speech_buffer_ms,
        )
    return _vad_8k


def get_vad_16k() -> SileroVAD:
    """Get or create 16kHz VAD instance."""
    global _vad_16k
    if _vad_16k is None:
        _vad_16k = SileroVAD(
            sample_rate=16000,
            threshold=settings.vad_threshold,
            min_speech_duration_ms=settings.vad_min_speech_duration_ms,
            min_silence_duration_ms=settings.vad_min_silence_duration_ms,
            pre_speech_buffer_ms=settings.vad_pre_speech_buffer_ms,
        )
    return _vad_16k