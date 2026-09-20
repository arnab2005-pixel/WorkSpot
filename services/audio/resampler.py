"""
Polyphase audio resampler for PM-AJAY Voice Assistant.

Implements low-latency bidirectional polyphase resampling using scipy.signal.resample_poly:
- Ingress: 8 kHz PCM (telephony) -> 16 kHz PCM (for Whisper ASR)
- Egress: 22.05 kHz PCM (indic-tts) -> 8 kHz PCM (FreeSWITCH RTP)
Ensures latency <= 15ms per chunk.
"""

import math
import time
import logging
from dataclasses import dataclass
from typing import Union, Tuple, Optional
import numpy as np
from scipy.signal import resample_poly

logger = logging.getLogger(__name__)


@dataclass
class ResampleConfig:
    """Configuration for polyphase audio resampling."""
    src_rate: int
    dst_rate: int
    dtype: np.dtype = np.float32
    normalize: bool = False


class AudioResampler:
    """
    High-performance polyphase audio resampler.
    
    Supports numpy ndarray and raw linear 16-bit PCM bytes.
    """

    def __init__(self, default_src_rate: int = 8000, default_dst_rate: int = 16000):
        self.default_src_rate = default_src_rate
        self.default_dst_rate = default_dst_rate
        self._ratio_cache: dict[Tuple[int, int], Tuple[int, int]] = {}

    def _get_factors(self, src_rate: int, dst_rate: int) -> Tuple[int, int]:
        """Compute coprime up/down resampling factors."""
        key = (src_rate, dst_rate)
        if key not in self._ratio_cache:
            gcd = math.gcd(src_rate, dst_rate)
            up = dst_rate // gcd
            down = src_rate // gcd
            self._ratio_cache[key] = (up, down)
        return self._ratio_cache[key]

    def resample_array(
        self,
        audio: np.ndarray,
        src_rate: Optional[int] = None,
        dst_rate: Optional[int] = None,
    ) -> np.ndarray:
        """
        Resample a 1D or 2D numpy audio array.
        
        Args:
            audio: Input audio array (float32 or int16)
            src_rate: Source sample rate (Hz)
            dst_rate: Destination sample rate (Hz)
            
        Returns:
            Resampled numpy array matching input dtype
        """
        src = src_rate or self.default_src_rate
        dst = dst_rate or self.default_dst_rate
        if src == dst:
            return audio

        up, down = self._get_factors(src, dst)
        orig_dtype = audio.dtype

        # resample_poly works best with float32 or float64
        if np.issubdtype(orig_dtype, np.integer):
            float_audio = audio.astype(np.float32) / 32768.0
            resampled = resample_poly(float_audio, up, down)
            # Clip and convert back to int16
            resampled = np.clip(resampled * 32768.0, -32768.0, 32767.0).astype(orig_dtype)
            return resampled
        else:
            return resample_poly(audio, up, down).astype(orig_dtype)

    def resample_pcm16_bytes(
        self,
        pcm_bytes: bytes,
        src_rate: int,
        dst_rate: int,
    ) -> bytes:
        """
        Resample raw 16-bit Mono Linear PCM bytes.
        
        Args:
            pcm_bytes: Raw PCM byte stream
            src_rate: Source sample rate
            dst_rate: Target sample rate
            
        Returns:
            Resampled PCM byte stream
        """
        if not pcm_bytes:
            return b""
        if src_rate == dst_rate:
            return pcm_bytes

        start = time.perf_counter()
        audio = np.frombuffer(pcm_bytes, dtype=np.int16)
        resampled = self.resample_array(audio, src_rate=src_rate, dst_rate=dst_rate)
        out_bytes = resampled.astype(np.int16).tobytes()
        elapsed_ms = (time.perf_counter() - start) * 1000.0

        if elapsed_ms > 15.0:
            logger.warning(
                f"Resampling from {src_rate}Hz to {dst_rate}Hz took {elapsed_ms:.2f}ms (>15ms budget)"
            )
        return out_bytes

    def telephony_to_asr(self, pcm8k_bytes: bytes) -> bytes:
        """
        Ingress conversion: 8 kHz PCM (telephony) -> 16 kHz PCM (for Whisper ASR).
        """
        return self.resample_pcm16_bytes(pcm8k_bytes, src_rate=8000, dst_rate=16000)

    def tts_to_telephony(self, pcm22k_bytes: bytes) -> bytes:
        """
        Egress conversion: 22.05 kHz PCM (indic-tts) -> 8 kHz PCM (for FreeSWITCH RTP).
        """
        return self.resample_pcm16_bytes(pcm22k_bytes, src_rate=22050, dst_rate=8000)

    def pcm16_to_float32(self, pcm_bytes: bytes) -> np.ndarray:
        """Convert raw 16-bit linear PCM bytes to float32 normalized in [-1.0, 1.0]."""
        if not pcm_bytes:
            return np.empty(0, dtype=np.float32)
        int16_arr = np.frombuffer(pcm_bytes, dtype=np.int16)
        return int16_arr.astype(np.float32) / 32768.0

    def float32_to_pcm16(self, audio_float: np.ndarray) -> bytes:
        """Convert float32 normalized audio array to 16-bit linear PCM bytes."""
        clipped = np.clip(audio_float, -1.0, 1.0)
        int16_arr = (clipped * 32767.0).astype(np.int16)
        return int16_arr.tobytes()