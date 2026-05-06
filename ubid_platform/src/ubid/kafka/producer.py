"""Kafka producer — publishes source records, activity events, and review decisions."""
from __future__ import annotations
import json
import logging
from typing import Any

from confluent_kafka import Producer, KafkaException

from ubid.config import get_settings

logger = logging.getLogger(__name__)

_producer: Producer | None = None


def get_producer() -> Producer:
    global _producer
    if _producer is None:
        settings = get_settings()
        _producer = Producer({
            "bootstrap.servers": settings.kafka_bootstrap_servers,
            "acks": "all",
            "retries": 3,
            "enable.idempotence": True,
        })
    return _producer


def _delivery_report(err, msg):
    if err:
        logger.error("Kafka delivery failed: %s", err)


def publish(topic: str, key: str, value: dict[str, Any]):
    producer = get_producer()
    try:
        producer.produce(
            topic,
            key=key.encode("utf-8"),
            value=json.dumps(value, default=str).encode("utf-8"),
            callback=_delivery_report,
        )
        producer.poll(0)
    except KafkaException as e:
        logger.error("Kafka publish error on topic %s: %s", topic, e)
        raise


def flush():
    get_producer().flush(timeout=10)


# ── Typed publishers ──────────────────────────────────────────────────────────

def publish_source_record(source_system: str, record_dict: dict):
    settings = get_settings()
    publish(
        topic=settings.kafka_topic_source_records,
        key=f"{source_system}:{record_dict.get('source_record_id', '')}",
        value={"source_system": source_system, "record": record_dict},
    )


def publish_activity_event(event_dict: dict):
    settings = get_settings()
    publish(
        topic=settings.kafka_topic_activity_events,
        key=event_dict.get("event_id", ""),
        value=event_dict,
    )


def publish_review_decision(decision_dict: dict):
    settings = get_settings()
    publish(
        topic=settings.kafka_topic_review_decisions,
        key=decision_dict.get("decision_id", ""),
        value=decision_dict,
    )
