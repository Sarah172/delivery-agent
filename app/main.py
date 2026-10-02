"""The target service: deliberately tiny. The agents around it are the point."""

import logging
import os

from fastapi import FastAPI
from fastapi.responses import JSONResponse

logging.basicConfig(
    level=logging.INFO,
    format='{"time":"%(asctime)s","level":"%(levelname)s","msg":"%(message)s"}',
)
log = logging.getLogger("app")

VERSION = os.getenv("APP_VERSION", "0.1.0")

app = FastAPI(title="delivery-agents target service", version=VERSION)


@app.get("/")
def root() -> dict:
    return {"service": "delivery-agents-target", "version": VERSION}


@app.get("/health")
def health():
    # FORCE_UNHEALTHY=1 simulates a bad deployment. The Day 2 verifier agent
    # should catch this and recommend a rollback.
    if os.getenv("FORCE_UNHEALTHY") == "1":
        log.error("health check failed: dependency unavailable")
        return JSONResponse(
            status_code=503,
            content={"status": "unhealthy", "version": VERSION, "reason": "dependency unavailable"},
        )
    log.info("health check ok")
    return {"status": "ok", "version": VERSION}
