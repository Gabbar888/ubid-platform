from pydantic_settings import BaseSettings, SettingsConfigDict
from functools import lru_cache


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env", env_file_encoding="utf-8",
        extra="ignore", protected_namespaces=()
    )

    # PostgreSQL
    postgres_host: str = "localhost"
    postgres_port: int = 5432
    postgres_db: str = "ubid"
    postgres_user: str = "ubid"
    postgres_password: str = "ubid_secret"

    @property
    def database_url(self) -> str:
        return (
            f"postgresql+psycopg2://{self.postgres_user}:{self.postgres_password}"
            f"@{self.postgres_host}:{self.postgres_port}/{self.postgres_db}"
        )

    # Redis
    redis_url: str = "redis://localhost:6379/0"

    # OpenSearch
    opensearch_url: str = "http://localhost:9200"
    opensearch_index: str = "ubid-canonical-records"

    # Neo4j
    neo4j_uri: str = "bolt://localhost:7687"
    neo4j_user: str = "neo4j"
    neo4j_password: str = "ubid_neo4j_secret"

    # Kafka
    kafka_bootstrap_servers: str = "localhost:9092"
    kafka_topic_source_records: str = "ubid.source.records"
    kafka_topic_activity_events: str = "ubid.events.activity"
    kafka_topic_review_decisions: str = "ubid.review.decisions"
    kafka_topic_quarantine: str = "ubid.quarantine"
    kafka_consumer_group: str = "ubid-workers"

    # DuckDB
    duckdb_path: str = "./data/parquet/events.duckdb"

    # Model artefacts
    model_dir: str = "./data/models"

    # Linkage thresholds
    auto_link_threshold: float = 0.95
    review_threshold_low: float = 0.55

    # Activity engine
    activity_alpha: float = 1.5
    active_score_threshold: float = 1.5
    dormant_score_threshold: float = 0.4
    nascent_hold_days: int = 90

    # App
    app_env: str = "development"
    log_level: str = "INFO"


@lru_cache
def get_settings() -> Settings:
    return Settings()
