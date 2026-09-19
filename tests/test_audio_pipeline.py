"""
Unit tests for the audio processing pipeline:
- Polyphase resampler (8k -> 16k, 22.05k -> 8k, latency budget <= 15ms)
- Silero VAD state machine and pre-speech ring buffer
- Sentence chunker for incremental TTS
"""

import time
import pytest
import numpy as np

from services.audio.resampler import AudioResampler
from services.audio.vad_filter import SileroVAD, VADState
from services.tts.chunker import TextChunker


def test_polyphase_resampling_ratio():
    """Verify resampler produces correct sample counts."""
    resampler = AudioResampler()

    # 1 second of 8kHz audio = 8000 samples
    samples_8k = np.zeros(8000, dtype=np.float32)
    resampled_16k = resampler.resample_array(samples_8k, src_rate=8000, dst_rate=16000)
    assert len(resampled_16k) == 16000

    # 1 second of 22050Hz audio
    samples_22k = np.zeros(22050, dtype=np.float32)
    resampled_8k = resampler.resample_array(samples_22k, src_rate=22050, dst_rate=8000)
    assert len(resampled_8k) == 8000


def test_pcm_bytes_resampling_and_latency():
    """Verify PCM byte resampling and latency <= 15ms per chunk budget."""
    resampler = AudioResampler()

    # 20ms chunk at 8kHz 16-bit mono = 160 samples = 320 bytes
    chunk_8k = (b"\x00\x01" * 160)

    start = time.perf_counter()
    chunk_16k = resampler.telephony_to_asr(chunk_8k)
    elapsed_ms = (time.perf_counter() - start) * 1000.0

    # 160 samples at 8kHz -> 320 samples at 16kHz = 640 bytes
    assert len(chunk_16k) == 640
    assert elapsed_ms < 15.0, f"Resampling latency {elapsed_ms:.2f}ms exceeded 15ms budget"


def test_pcm16_float32_conversion():
    """Verify lossless roundtrip conversion between PCM16 and float32."""
    resampler = AudioResampler()

    int16_original = np.array([0, 16384, -16384, 32767, -32768], dtype=np.int16)
    raw_bytes = int16_original.tobytes()

    float_audio = resampler.pcm16_to_float32(raw_bytes)
    assert np.allclose(float_audio, [0.0, 0.5, -0.5, 32767.0 / 32768.0, -1.0], atol=1e-4)

    reconstructed_bytes = resampler.float32_to_pcm16(float_audio)
    reconstructed_int16 = np.frombuffer(reconstructed_bytes, dtype=np.int16)
    assert np.all(np.abs(int16_original - reconstructed_int16) <= 1)


def test_silero_vad_initialization():
    """Verify Silero VAD initialization with window sizes."""
    vad_8k = SileroVAD(sample_rate=8000)
    assert vad_8k.window_size == 256
    assert vad_8k.sample_rate == 8000

    vad_16k = SileroVAD(sample_rate=16000)
    assert vad_16k.window_size == 512
    assert vad_16k.sample_rate == 16000


def test_silero_vad_silence_processing():
    """Verify that pure silence does not trigger speech."""
    vad = SileroVAD(sample_rate=8000)
    vad.reset()

    silence_frame = np.zeros(256, dtype=np.float32)
    result = vad.process_frame(silence_frame)

    assert result.is_speech is False
    assert result.probability < 0.5
    assert vad.state == VADState.IDLE


def test_silero_vad_speech_transition():
    """Verify that speech energy transitions state to PRE_SPEECH and SPEECH."""
    vad = SileroVAD(sample_rate=8000, threshold=0.3)
    vad.reset()

    # Synthetic voiced frame (sine wave)
    t = np.linspace(0, 0.032, 256, endpoint=False)
    voice_frame = (0.6 * np.sin(2 * np.pi * 300 * t)).astype(np.float32)

    result = vad.process_frame(voice_frame)
    assert result.is_speech is True
    assert result.state in (VADState.PRE_SPEECH, VADState.SPEECH)


def test_text_chunker_indic():
    """Verify sentence boundary splitting on Indic danda, comma, and punctuation."""
    chunker = TextChunker(min_chunk_chars=10, max_chunk_chars=80)

    text = "नमस्ते! मैं पीएम-अजय सहायक हूँ। आपके पास सिलाई का केंद्र है, क्या आप दाखिला लेंगे?"
    chunks = chunker.split_into_chunks(text)

    assert len(chunks) >= 2
    full_recombined = " ".join(chunks)
    assert "पीएम-अजय" in full_recombined
    assert "सिलाई" in full_recombined
