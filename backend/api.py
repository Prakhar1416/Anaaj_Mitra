from contextlib import asynccontextmanager

from fastapi import FastAPI

from backend.config import (
    DATABASE_PATH,
    public_config,
)
from backend.database import initialize_database


@asynccontextmanager
async def lifespan(_: FastAPI):
    initialize_database(DATABASE_PATH)
    yield


app = FastAPI(title="Anaaj Mitra API", version="0.1.0", lifespan=lifespan)


@app.get("/health")
def health_check() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/api/config")
def get_config() -> dict[str, object]:
    return public_config()
