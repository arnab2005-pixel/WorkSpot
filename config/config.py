"""
Configuration management for PM-AJAY Voice Assistant.
All settings loaded from environment variables with sensible defaults.
"""

from functools import lru_cache
from typing import Optional, List
from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # Application
    app_name: str = "PM-AJAY Voice Assistant"
    app_version: str = "1.0.0"
    debug: bool = False
    mock_mode: bool = False
    log_level: str = "INFO"

    # Server
    host: str = "0.0.0.0"
    port: int = 8080
    workers: int = 1

    # Redis (session cache)
    redis_url: str = "redis://127.0.0.1:6379"
    redis_max_connections: int = 50
    session_ttl_seconds: int = 1800  # 30 minutes

    # MongoDB
    mongodb_url: str = "mongodb://127.0.0.1:27017"
    mongodb_database: str = "pm_ajay"
    mongodb_max_pool_size: int = 50

    # vLLM (Qwen2.5-3B-Instruct)
    vllm_base_url: str = "http://localhost:8000/v1"
    vllm_model_name: str = "qwen2.5-3b-instruct"
    vllm_timeout_seconds: float = 10.0
    vllm_max_retries: int = 2

    # Gemini API Fallback (when local vLLM is offline)
    gemini_api_key: Optional[str] = Field(default=None, validation_alias="GEMINI_API_KEY")
    gemini_model: str = "gemini-2.5-flash"
    gemini_timeout_seconds: float = 10.0

    # TTS (indic-tts FastPitch + HiFi-GAN)
    tts_base_url: str = "http://localhost:8001"
    tts_timeout_seconds: float = 8.0
    tts_sample_rate: int = 22050  # Native indic-tts output rate
    tts_language: str = "hi"

    # ASR (faster-whisper)
    whisper_base_url: str = "http://localhost:8002"
    whisper_model_size: str = "small"
    whisper_compute_type: str = "int8_float16"
    whisper_language: str = "hi"
    whisper_timeout_seconds: float = 5.0
    # Domain biasing prompt for Whisper
    whisper_prompt: str = (
        "पीएम-अजय योजना, हुनर, स्वरोज़गार, काम-धंधा, "
        "लोहार, बढ़ई, दर्जी, कसीदाकारी, राजमिस्त्री।"
    )
    # Hallucination protection thresholds
    whisper_compression_ratio_threshold: float = 2.4
    whisper_avg_logprob_threshold: float = -0.90

    # Audio processing
    audio_sample_rate_telephony: int = 8000
    audio_sample_rate_asr: int = 16000
    audio_sample_rate_tts: int = 22050
    audio_frame_duration_ms: int = 20
    audio_channels: int = 1
    audio_bit_depth: int = 16

    # VAD (Silero VAD v5)
    vad_threshold: float = 0.5
    vad_min_speech_duration_ms: int = 250
    vad_min_silence_duration_ms: int = 400
    vad_pre_speech_buffer_ms: int = 300
    vad_window_size_samples_8k: int = 256  # 32ms at 8kHz
    vad_window_size_samples_16k: int = 512  # 32ms at 16kHz

    # Resampler
    resampler_quality: str = "kaiser_best"  # or "kaiser_fast" for lower latency

    # Recommendation engine
    embedding_model: str = "BAAI/bge-m3"  # or "indian-bert"
    embedding_dim: int = 768
    vector_search_num_candidates: int = 40
    vector_search_limit: int = 10
    final_recommendation_limit: int = 2

    # Latency budgets (ms) - for monitoring
    latency_budget_vad_ms: int = 80
    latency_budget_asr_ms: int = 350
    latency_budget_llm_ms: int = 320
    latency_budget_vector_search_ms: int = 110
    latency_budget_tts_first_chunk_ms: int = 280
    latency_budget_resample_egress_ms: int = 60
    latency_budget_total_ms: int = 1200

    # FreeSWITCH / Telephony
    freeswitch_host: str = "localhost"
    freeswitch_port: int = 8021
    freeswitch_password: str = "ClueCon"
    sip_domain: str = "pm-ajay.local"

    # Supported languages/dialects
    supported_languages: List[str] = ["hi", "bhojpuri", "maithili", "magahi", "awadhi"]
    default_language: str = "hi"
    default_dialect: str = "bhojpuri_mixed"

    # DPDP Consent
    consent_audio_retention_days: int = 365
    consent_required: bool = True


@lru_cache
def get_settings() -> Settings:
    """Get cached settings instance."""
    return Settings()


# Convenience access
settings = get_settings()