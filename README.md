# FMN Supply Chain Demand Watch

## Run the FastAPI app

```powershell
.\.venv\Scripts\Activate.ps1
uvicorn app:app --reload
```

Open http://127.0.0.1:8000 for the dashboard. JSON endpoints are available at `/api/summary`, `/api/skus`, and `/health`.

## Run the notebook

```powershell
jupyter notebook supply_chain_analysis.ipynb
```

The dashboard and notebook use the same `supply_chain.py` analysis logic. A SKU is flagged for stockout risk when current stock does not cover expected demand during supplier lead time, for overstock when it has at least 45 days of cover, and as a new SKU when it has fewer than 30 days of history.