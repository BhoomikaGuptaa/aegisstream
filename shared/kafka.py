"""Kafka topic constants and helper utilities for AegisStream."""
import json
import os
from typing import Any, Dict

TOPIC_RAW_EVENTS = "aegis.raw_events"
TOPIC_EVALUATED_EVENTS = "aegis.evaluated_events"
TOPIC_REVIEW_EVENTS = "aegis.review_events"
TOPIC_DRIFT_ALERTS = "aegis.drift_alerts"
TOPIC_DEPLOYMENT_CHECKS = "aegis.deployment_checks"

ALL_TOPICS = [
    TOPIC_RAW_EVENTS,
    TOPIC_EVALUATED_EVENTS,
    TOPIC_REVIEW_EVENTS,
    TOPIC_DRIFT_ALERTS,
    TOPIC_DEPLOYMENT_CHECKS,
]

KAFKA_BOOTSTRAP = os.getenv("KAFKA_BOOTSTRAP_SERVERS", "redpanda:9092")


def serialize(obj: Any) -> bytes:
    """JSON-serialize a Pydantic model or dict to bytes."""
    if hasattr(obj, "model_dump"):
        data = obj.model_dump(mode="json")
    else:
        data = obj
    return json.dumps(data, default=str).encode("utf-8")


def deserialize(data: bytes) -> Dict:
    return json.loads(data.decode("utf-8"))
