"""Kafka consumer worker — processes activity events and review decisions.

Runs as a standalone process (python -m ubid.kafka.consumer).
"""
from __future__ import annotations
import json
import logging
import signal
import sys
from datetime import datetime, timezone

from confluent_kafka import Consumer, KafkaError, KafkaException

from ubid.config import get_settings
from ubid.storage.postgres import create_all_tables

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s")

_running = True


def _sigterm_handler(sig, frame):
    global _running
    logger.info("Received SIGTERM — shutting down consumer.")
    _running = False


signal.signal(signal.SIGTERM, _sigterm_handler)
signal.signal(signal.SIGINT, _sigterm_handler)


def _handle_activity_event(payload: dict):
    """Join event to UBID and write to DuckDB warehouse; quarantine on miss."""
    from ubid.schema.events import ActivityEvent, EventType
    from ubid.schema.canonical import SourceSystem
    from ubid.storage import redis_cache
    from ubid.storage.duckdb_warehouse import append_event
    from ubid.activity.quarantine import quarantine

    try:
        event = ActivityEvent(**payload)
    except Exception as e:
        logger.warning("Malformed activity event: %s", e)
        return

    ubid = redis_cache.get_ubid_for_source(event.source_system, event.source_record_id)

    if not ubid:
        # Fallback to Postgres
        from ubid.storage.postgres import get_db
        from sqlalchemy import text
        with get_db() as db:
            row = db.execute(text("""
                SELECT u.ubid FROM ubid_source_links usl
                JOIN ubid_nodes u ON usl.ubid = u.ubid
                JOIN canonical_records cr ON usl.canonical_id = cr.canonical_id
                WHERE cr.source_system = :sys AND cr.source_record_id = :rid
                LIMIT 1
            """), {"sys": event.source_system, "rid": event.source_record_id}).first()
            if row:
                ubid = str(row.ubid)
                redis_cache.set_ubid_for_source(event.source_system, event.source_record_id, ubid)

    if ubid:
        append_event(
            event_id=str(event.event_id),
            source_system=event.source_system,
            source_record_id=event.source_record_id,
            event_type=event.event_type,
            event_date=event.event_date,
            ingested_at=datetime.now(timezone.utc),
            ubid=ubid,
            metadata=event.metadata,
        )
        # Invalidate cached verdict
        redis_cache.invalidate_verdict(ubid)
    else:
        quarantine(event, reason="No UBID found for source record")


def _handle_review_decision(payload: dict):
    """Apply reviewer decision: write constraint + invalidate cache."""
    from ubid.review.feedback import apply_decision
    try:
        apply_decision(payload)
    except Exception as e:
        logger.error("Error applying review decision: %s", e)


def run():
    settings = get_settings()
    create_all_tables()

    consumer = Consumer({
        "bootstrap.servers": settings.kafka_bootstrap_servers,
        "group.id": settings.kafka_consumer_group,
        "auto.offset.reset": "earliest",
        "enable.auto.commit": False,
    })

    topics = [settings.kafka_topic_activity_events, settings.kafka_topic_review_decisions]
    consumer.subscribe(topics)
    logger.info("Subscribed to topics: %s", topics)

    try:
        while _running:
            msg = consumer.poll(timeout=1.0)
            if msg is None:
                continue
            if msg.error():
                if msg.error().code() == KafkaError._PARTITION_EOF:
                    continue
                logger.error("Kafka error: %s", msg.error())
                continue

            topic = msg.topic()
            try:
                payload = json.loads(msg.value().decode("utf-8"))
            except json.JSONDecodeError as e:
                logger.warning("JSON decode error on topic %s: %s", topic, e)
                consumer.commit(msg)
                continue

            if topic == settings.kafka_topic_activity_events:
                _handle_activity_event(payload)
            elif topic == settings.kafka_topic_review_decisions:
                _handle_review_decision(payload)

            consumer.commit(msg)

    except KafkaException as e:
        logger.error("Fatal Kafka error: %s", e)
    finally:
        consumer.close()
        logger.info("Consumer closed.")


if __name__ == "__main__":
    run()
