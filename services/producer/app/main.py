"""
AegisStream producer service.
Generates synthetic LLM traffic and publishes to aegis.raw_events.
"""
import logging
import os
import sys
import time

sys.path.insert(0, "/app")

from kafka import KafkaProducer
from kafka.errors import NoBrokersAvailable

from shared.kafka import TOPIC_RAW_EVENTS, KAFKA_BOOTSTRAP, serialize
from services.producer.app.synthetic_generator import SyntheticGenerator

logging.basicConfig(level=logging.INFO, format="%(asctime)s [PRODUCER] %(message)s")
log = logging.getLogger(__name__)

EVENTS_PER_SECOND = float(os.getenv("EVENTS_PER_SECOND", "5"))
DRIFT_ENABLED = os.getenv("DRIFT_ENABLED", "true").lower() == "true"
DRIFT_START = int(os.getenv("DRIFT_START_EVENT", "500"))
INJECTION_RATE = float(os.getenv("INJECTION_RATE", "0.04"))
HALLUCINATION_RATE = float(os.getenv("HALLUCINATION_RATE", "0.08"))


def wait_for_kafka(retries: int = 15, delay: float = 4.0) -> KafkaProducer:
    for attempt in range(retries):
        try:
            producer = KafkaProducer(
                bootstrap_servers=KAFKA_BOOTSTRAP,
                value_serializer=lambda v: serialize(v),
                acks="all",
                retries=3,
            )
            log.info("Connected to Kafka at %s", KAFKA_BOOTSTRAP)
            return producer
        except NoBrokersAvailable:
            log.warning("Kafka not ready, retrying (%d/%d)...", attempt + 1, retries)
            time.sleep(delay)
    raise RuntimeError("Could not connect to Kafka after retries.")


def run():
    producer = wait_for_kafka()
    generator = SyntheticGenerator(
        injection_rate=INJECTION_RATE,
        hallucination_rate=HALLUCINATION_RATE,
        drift_enabled=DRIFT_ENABLED,
        drift_start_event=DRIFT_START,
    )

    interval = 1.0 / max(0.1, EVENTS_PER_SECOND)
    log.info("Starting event production at %.1f events/sec", EVENTS_PER_SECOND)
    count = 0

    while True:
        t0 = time.monotonic()
        try:
            event = generator.generate()
            producer.send(TOPIC_RAW_EVENTS, value=event)
            count += 1
            if count % 100 == 0:
                log.info("Published %d events | drift=%s | counter=%d",
                         count, DRIFT_ENABLED, generator._event_counter)
        except Exception as e:
            log.error("Error producing event: %s", e)

        elapsed = time.monotonic() - t0
        sleep_time = max(0.0, interval - elapsed)
        time.sleep(sleep_time)


if __name__ == "__main__":
    run()
