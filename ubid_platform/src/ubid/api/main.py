"""UBID Platform — FastAPI application entry point."""
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from ubid.api.routers import ingest, lookup, status, review, query
from ubid.storage.postgres import create_all_tables
from ubid.blocking.opensearch_blocker import ensure_index
from ubid.storage.duckdb_warehouse import get_conn as get_duck

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s")


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Starting UBID Platform API …")
    create_all_tables()
    try:
        ensure_index()
    except Exception as e:
        logger.warning("OpenSearch index setup failed (will retry): %s", e)
    try:
        get_duck()  # initialise DuckDB schema
    except Exception as e:
        logger.warning("DuckDB init failed: %s", e)
    logger.info("UBID Platform API ready.")
    yield
    logger.info("UBID Platform API shutting down.")


app = FastAPI(
    title="UBID Platform",
    description="Unified Business Identifier and Active Business Intelligence — Karnataka C&I",
    version="0.1.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(ingest.router, prefix="/api/v1/ingest",  tags=["Ingest"])
app.include_router(lookup.router, prefix="/api/v1/lookup",  tags=["Lookup"])
app.include_router(status.router, prefix="/api/v1/ubid",    tags=["UBID Status"])
app.include_router(review.router, prefix="/api/v1/review",  tags=["Review"])
app.include_router(query.router,  prefix="/api/v1/query",   tags=["Query"])


@app.get("/health", tags=["Health"])
def health():
    return {"status": "ok"}
