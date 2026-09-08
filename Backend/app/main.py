from __future__ import annotations

from fastapi import FastAPI

app = FastAPI(title="Supply Chain Demand Watch API", version="1.0.0")


@app.get("/")
def root() -> dict:
    return {"message": "Supply Chain Demand Watch API is running"}


@app.get("/health")
def health() -> dict:
    return {"status": "ok"}


@app.get("/api/summary")
def summary() -> dict:
    return {"total_skus": 0, "status_counts": {}}
