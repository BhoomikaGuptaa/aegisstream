"""
AegisStream API configuration.
All settings are driven by environment variables with sensible defaults.
"""
import os
from functools import lru_cache


class Settings:
    # Database
    database_url: str = os.getenv("DATABASE_URL", "/data/aegisstream.db")

    # Kafka
    kafka_bootstrap_servers: str = os.getenv("KAFKA_BOOTSTRAP_SERVERS", "redpanda:9092")

    # Gate defaults (can be overridden per-request)
    gate_max_review_rate: float     = float(os.getenv("GATE_MAX_REVIEW_RATE", "15.0"))
    gate_max_avg_risk_score: float  = float(os.getenv("GATE_MAX_RISK_SCORE", "35.0"))
    gate_max_p95_latency_ms: float  = float(os.getenv("GATE_MAX_P95_LATENCY", "3000.0"))
    gate_max_injection_rate: float  = float(os.getenv("GATE_MAX_INJECTION_RATE", "5.0"))
    gate_max_sensitive_rate: float  = float(os.getenv("GATE_MAX_SENSITIVE_RATE", "3.0"))
    gate_max_halluc_rate: float     = float(os.getenv("GATE_MAX_HALLUC_RATE", "10.0"))
    gate_min_reliability: float     = float(os.getenv("GATE_MIN_RELIABILITY", "70.0"))

    # Service metadata
    service_name: str    = "aegisstream-api"
    service_version: str = "1.0.0"


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()
