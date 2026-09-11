# Supply Chain Demand & Stock Risk — Deployment Package

FMN AI Engineer Internship Assessment — Project 1

## What's in here

```
backend/          FastAPI app (deploy to Render)
  app/
    main.py            API endpoints
    pipeline/           the cleaning/EDA/feature/model scripts, for reference
                         and re-running if the underlying data changes
    data/                precomputed cleaned_data.csv, features.csv, risk_flags.csv
    model/               trained demand_model.joblib + its column order
  requirements.txt
  render.yaml
  Procfile
  .env.example

frontend/          React (Vite) app (deploy to Vercel)
  src/App.jsx           risk table, per-SKU explanation panel, Q&A box
  vercel.json
  .env.example
```

## How it works

1. `risk_flags.csv` is precomputed (cleaning → EDA-informed feature engineering
   → RandomForest demand model, backtested against a naive baseline → risk
   classification). The API serves this directly rather than recomputing it on
   every request.
2. `/api/sku/{id}/explain` and `/api/ask` call Claude live at request time,
   grounded in a small JSON payload built from the real numbers (never the raw
   dataset) — this satisfies the "not hardcoded/templated" explanation
   requirement.
3. If the underlying sales data changes, re-run the pipeline scripts in
   `backend/app/pipeline/` in this order and replace the CSVs in
   `backend/app/data/`:
   `clean_data.py` → `build_features.py` → `build_model_dataset.py` →
   `train_model.py` → `predict_and_flag.py`

## Deploy the backend to Render

1. Push the `backend/` folder to a GitHub repo (or push this whole repo and
   set Render's root directory to `backend`).
2. In Render: **New → Web Service**, connect the repo.
3. Render should auto-detect `render.yaml`. If not, set manually:
   - Build command: `pip install -r requirements.txt`
   - Start command: `uvicorn app.main:app --host 0.0.0.0 --port $PORT`
4. Add environment variable: `OPENAI_API_KEY` (or `API_KEY`) = your OpenAI-compatible key.
5. Optionally set `OPENAI_BASE_URL` and `OPENAI_CHAT_MODEL` for OpenRouter or a compatible gateway.
6. Once deployed, note the URL, e.g. `https://supply-chain-risk-api.onrender.com`
7. Test it: `curl https://YOUR-RENDER-URL/api/health` → should return `{"status":"ok"}`

## Deploy the frontend to Vercel

1. Push the `frontend/` folder to a GitHub repo (or same repo, root directory
   `frontend`).
2. In Vercel: **New Project**, import the repo, framework auto-detected as Vite.
3. Add environment variable: `VITE_API_BASE_URL` = your Render backend URL
   from above (no trailing slash).
4. Deploy.
5. Once your backend is live, go back to Render and set `ALLOWED_ORIGINS` to
   your exact Vercel URL (e.g. `https://your-app.vercel.app`) instead of `*`,
   for CORS.

## Local testing before you deploy

Backend:
```bash
cd backend
pip install -r requirements.txt
export OPENAI_API_KEY=your-key
export OPENAI_BASE_URL=https://openrouter.ai/api/v1
export OPENAI_CHAT_MODEL=openai/gpt-oss-20b:free
uvicorn app.main:app --reload
# -> http://localhost:8000/api/health
```

Frontend:
```bash
cd frontend
npm install
npm run dev
# -> http://localhost:5173, reads VITE_API_BASE_URL from .env (defaults to localhost:8000)
```

## API endpoints

| Method | Path | Description |
|---|---|---|
| GET | `/api/health` | health check |
| GET | `/api/risk-flags` | all 28 SKUs with current risk flag |
| GET | `/api/sku/{sku_id}` | one SKU's data (no LLM call) |
| GET | `/api/sku/{sku_id}/explain` | LLM explanation for one SKU |
| POST | `/api/ask` | `{"question": "..."}` → grounded Q&A |

## Known limitations (worth stating honestly in your submission)

- The 3 new SKUs (SKU-2000/2001/2002) can't be scored by the trained model —
  they don't have enough history to build its input features. They fall back
  to a category-average heuristic and are explicitly flagged
  `low (new SKU, category-average fallback)` in every API response.
- The demand model beats a naive 14-day-average baseline by ~9% MAE on a
  14-day backtest — a real but modest improvement, not a dramatic one.
- Risk thresholds (stockout: cover ratio < 1.0, overstock: > 2.0) are
  EDA-derived defaults, not tuned against real business cost data.
