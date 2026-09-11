# CareerForge Chatbot — RAG Module

Grounded chatbot module: answers only from your Participant Handbook,
curriculum, and FAQ content (no improvising on dates, weeks, or figures).

## Files

```
app/
  core/database.py     # DB setup — merge into your existing one, don't overwrite
  models/chat.py        # conversation history table
  models/knowledge.py   # embedded knowledge chunks table (pgvector)
  bot/router.py          # the /api/bot/chat endpoint (RAG + OpenAI)
scripts/
  ingest_knowledge.py    # chunks + embeds your docs into Postgres
data/
  faq.md                 # template — replace with your real FAQ
requirements.txt
```

## Setup steps

1. **Merge files into your existing FastAPI backend repo**, replacing the
   current `app/bot/` FAQ logic. Keep your existing `app/core/database.py`
   if you already have one — just make sure it exposes `Base`,
   `SessionLocal`, and `get_db` as shown here.

2. **Install dependencies:**
   ```bash
   pip install -r requirements.txt
   ```

3. **Enable pgvector on your Render Postgres** (run once, via psql or a
   migration):
   ```sql
   CREATE EXTENSION IF NOT EXISTS vector;
   ```

4. **Create the tables** (Alembic migration, or quick-and-dirty for now):
   ```python
   from app.core.database import Base, engine
   from app.models import chat, knowledge
   Base.metadata.create_all(bind=engine)
   ```

5. **Add your real content** to `data/`:
   ```bash
   pandoc participant_handbook.docx -o data/participant_handbook.md
   pandoc curriculum.docx -o data/curriculum.md
   # edit data/faq.md directly
   ```

6. **Set environment variables** (Render dashboard):
   - `OPENAI_API_KEY`
   - `OPENAI_CHAT_MODEL` (optional, defaults to `gpt-4o-mini`)
   - `DATABASE_URL` (you already have this)

7. **Run ingestion** (locally against your Render Postgres, or as a one-off
   Render job):
   ```bash
   python scripts/ingest_knowledge.py
   ```

8. **Mount the router** in your main FastAPI app:
   ```python
   from app.bot.router import router as bot_router
   app.include_router(bot_router)
   ```

9. **Redeploy.** Your existing frontend widget doesn't need changes — it
   already POSTs `{ message, session_id }` to `/api/bot/chat` and expects
   `{ reply }` back.

## Re-ingesting after content updates

Just re-run `python scripts/ingest_knowledge.py` — it clears and re-embeds
each source (handbook/curriculum/faq) it's given, so it's safe to run
repeatedly whenever you update the docs.
