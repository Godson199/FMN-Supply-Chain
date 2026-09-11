import json
import os
import re
from pathlib import Path

from dotenv import load_dotenv
from fastapi import APIRouter, Depends
from openai import OpenAI
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.models.chat import ChatMessage
from app.models.knowledge import KnowledgeChunk

load_dotenv(Path(__file__).resolve().parents[2] / ".env")

router = APIRouter()


def get_client() -> OpenAI:
    api_key = os.getenv("API_KEY") or os.getenv("OPENAI_API_KEY")
    if not api_key:
        raise RuntimeError("Missing API key. Set API_KEY or OPENAI_API_KEY in your .env file.")

    return OpenAI(
        api_key=api_key,
        base_url=os.getenv("OPENAI_BASE_URL", "https://openrouter.ai/api/v1"),
    )


CHAT_MODEL = os.getenv("OPENAI_CHAT_MODEL", "openai/gpt-oss-20b:free")
EMBEDDING_MODEL = os.getenv("EMBEDDING_MODEL", "text-embedding-3-small")
SYSTEM_PROMPT = """You are the supply-chain assistant. Answer ONLY using the CONTEXT provided below, which comes from the product knowledge base and FAQ. If the answer isn't in the context, say you're not sure and suggest the user contact the team — do not guess or make up details."""
HISTORY_TURNS = 6
RETRIEVAL_K = 5


class ChatRequest(BaseModel):
    session_id: str
    message: str


class ChatResponse(BaseModel):
    reply: str


def embed(text: str) -> list[float] | None:
    try:
        result = get_client().embeddings.create(model=EMBEDDING_MODEL, input=text)
        return result.data[0].embedding
    except Exception:
        return None


def _parse_embedding(value: str | None) -> list[float] | None:
    if not value:
        return None
    try:
        payload = json.loads(value)
    except Exception:
        return None
    if isinstance(payload, list) and payload and all(isinstance(item, (int, float)) for item in payload):
        return [float(item) for item in payload]
    return None


def _cosine_similarity(left: list[float] | None, right: list[float] | None) -> float:
    if not left or not right or len(left) != len(right):
        return 0.0

    dot_product = sum(a * b for a, b in zip(left, right))
    left_norm = sum(a * a for a in left) ** 0.5
    right_norm = sum(b * b for b in right) ** 0.5
    if left_norm == 0 or right_norm == 0:
        return 0.0
    return dot_product / (left_norm * right_norm)


def retrieve_context(db: Session, query: str, k: int = RETRIEVAL_K) -> str:
    query_terms = set(re.findall(r"\w+", query.lower()))
    query_embedding = embed(query)

    results = db.query(KnowledgeChunk).all()
    scored_results = []
    for chunk in results:
        chunk_terms = set(re.findall(r"\w+", chunk.content.lower()))
        keyword_score = len(query_terms & chunk_terms)
        embedding_score = 0.0
        if query_embedding is not None:
            chunk_embedding = _parse_embedding(getattr(chunk, "embedding", None))
            embedding_score = _cosine_similarity(query_embedding, chunk_embedding)

        score = embedding_score if embedding_score > 0 else keyword_score
        scored_results.append((score, chunk))

    scored_results.sort(key=lambda item: item[0], reverse=True)
    top_results = [chunk for _, chunk in scored_results[:k]]

    if not top_results:
        return "(no matching context found)"

    return "\n\n".join(f"[{c.source} — {c.section}]\n{c.content}" for c in top_results)


@router.post("/api/bot/chat", response_model=ChatResponse)
def chat(payload: ChatRequest, db: Session = Depends(get_db)):
    db.add(ChatMessage(session_id=payload.session_id, role="user", content=payload.message))
    db.commit()

    context = retrieve_context(db, payload.message)

    history = (
        db.query(ChatMessage)
        .filter(ChatMessage.session_id == payload.session_id)
        .order_by(ChatMessage.created_at.desc())
        .limit(HISTORY_TURNS)
        .all()[::-1]
    )

    messages = [
        {"role": "system", "content": f"{SYSTEM_PROMPT}\n\nCONTEXT:\n{context}"},
    ] + [{"role": m.role, "content": m.content} for m in history]

    response = get_client().chat.completions.create(
        model=CHAT_MODEL,
        messages=messages,
        temperature=0.3,
        max_tokens=400,
    )
    reply = response.choices[0].message.content

    db.add(ChatMessage(session_id=payload.session_id, role="assistant", content=reply))
    db.commit()

    return ChatResponse(reply=reply)
