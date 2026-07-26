"""Kinesis API — momentum-selection trading system.

Step 1 skeleton: minimal FastAPI app that boots and answers /health (and proves
the DB/connection wiring). Routers, models, and engine_3 are added in later port
steps — see EXTRACTION_PLAN.md.
"""
import logging

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

logger = logging.getLogger(__name__)

app = FastAPI(
    title="Kinesis API",
    description="Momentum-selection trading system (regime-gated, risk-managed)",
    version="0.1.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/")
def root():
    return {"name": "Kinesis", "version": "0.1.0", "docs": "/docs", "health": "/health"}


@app.get("/health")
def health():
    return {"status": "ok", "service": "kinesis-backend"}
