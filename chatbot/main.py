import os
from pathlib import Path

import uvicorn
from dotenv import load_dotenv
from fastapi import FastAPI

from sqlalchemy import text

from app.bot.router import router as bot_router
from app.core.database import engine
from app.models.chat import ChatMessage
from app.models.knowledge import KnowledgeChunk

load_dotenv(Path(__file__).resolve().parent / ".env")

os.environ.setdefault("API_PREFIX", "/api")

app = FastAPI(title="CareerForge Chatbot RAG - Minimal API")
app.include_router(bot_router)


@app.on_event("startup")
def startup():
    with engine.begin() as conn:
        try:
            conn.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))
        except Exception as exc:
            print(f"Vector extension unavailable: {exc}")

    try:
        ChatMessage.__table__.create(bind=engine)
        print("Created table: chat_messages")
    except Exception as exc:
        print(f"Unable to create table chat_messages: {exc}")

    try:
        KnowledgeChunk.__table__.create(bind=engine)
        print("Created table: knowledge_chunks")
    except Exception as exc:
        print(f"Unable to create table knowledge_chunks: {exc}")


if __name__ == "__main__":
    uvicorn.run("main:app", host="127.0.0.1", port=8002)

 