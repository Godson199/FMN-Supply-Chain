import { useEffect, useState } from "react";
import "./App.css";

const API_BASE = import.meta.env.VITE_API_BASE_URL || "http://localhost:8000";

const RISK_COLORS = {
  STOCKOUT_RISK: "#c44e52",
  OVERSTOCK: "#4c72b0",
  HEALTHY: "#55a868",
};

function RiskBadge({ flag }) {
  return (
    <span className="risk-badge" style={{ backgroundColor: RISK_COLORS[flag] || "#999" }}>
      {flag.replace("_", " ")}
    </span>
  );
}

function SkuDetail({ skuId, onClose }) {
  const [explanation, setExplanation] = useState(null);
  const [payload, setPayload] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  useEffect(() => {
    setLoading(true);
    setError(null);
    fetch(`${API_BASE}/api/sku/${skuId}/explain`)
      .then((res) => {
        if (!res.ok) throw new Error(`Request failed (${res.status})`);
        return res.json();
      })
      .then((data) => {
        setExplanation(data.explanation);
        setPayload(data.payload);
      })
      .catch((err) => setError(err.message))
      .finally(() => setLoading(false));
  }, [skuId]);

  return (
    <div className="detail-panel">
      <div className="detail-header">
        <h3>{skuId}</h3>
        <button onClick={onClose}>Close</button>
      </div>
      {loading && <p>Generating explanation...</p>}
      {error && (
        <p className="error">
          Couldn't load explanation ({error}). Backend may not have ANTHROPIC_API_KEY configured.
        </p>
      )}
      {explanation && <p className="explanation">{explanation}</p>}
      {payload && (
        <table className="payload-table">
          <tbody>
            {Object.entries(payload).map(([key, value]) => (
              <tr key={key}>
                <td className="key">{key}</td>
                <td>{String(value)}</td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
    </div>
  );
}

function AskBox() {
  const [question, setQuestion] = useState("");
  const [answer, setAnswer] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);

  const handleAsk = async (e) => {
    e.preventDefault();
    if (!question.trim()) return;
    setLoading(true);
    setError(null);
    setAnswer(null);
    try {
      const res = await fetch(`${API_BASE}/api/ask`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ question }),
      });
      if (!res.ok) throw new Error(`Request failed (${res.status})`);
      const data = await res.json();
      setAnswer(data.answer);
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="ask-box">
      <h3>Ask a question</h3>
      <form onSubmit={handleAsk}>
        <input
          type="text"
          placeholder="e.g. Which SKUs need urgent attention this week?"
          value={question}
          onChange={(e) => setQuestion(e.target.value)}
        />
        <button type="submit" disabled={loading}>
          {loading ? "Thinking..." : "Ask"}
        </button>
      </form>
      {error && (
        <p className="error">
          Couldn't get an answer ({error}). Backend may not have ANTHROPIC_API_KEY configured.
        </p>
      )}
      {answer && <p className="answer">{answer}</p>}
    </div>
  );
}

function App() {
  const [rows, setRows] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [selectedSku, setSelectedSku] = useState(null);

  useEffect(() => {
    fetch(`${API_BASE}/api/risk-flags`)
      .then((res) => {
        if (!res.ok) throw new Error(`Request failed (${res.status})`);
        return res.json();
      })
      .then((data) => setRows(data.sort((a, b) => (a.cover_ratio ?? 0) - (b.cover_ratio ?? 0))))
      .catch((err) => setError(err.message))
      .finally(() => setLoading(false));
  }, []);

  return (
    <div className="app">
      <header>
        <h1>Supply Chain Stock Risk</h1>
        <p className="subtitle">Next-day demand forecast &amp; risk flags, all SKUs</p>
      </header>

      {loading && <p>Loading risk data...</p>}
      {error && (
        <p className="error">
          Couldn't reach the API ({error}). Check that VITE_API_BASE_URL points to your Render backend.
        </p>
      )}

      {!loading && !error && (
        <table className="risk-table">
          <thead>
            <tr>
              <th>SKU</th>
              <th>Category</th>
              <th>Stock</th>
              <th>Lead time</th>
              <th>Predicted demand</th>
              <th>Cover ratio</th>
              <th>Risk</th>
              <th></th>
            </tr>
          </thead>
          <tbody>
            {rows.map((row) => (
              <tr key={row.sku_id}>
                <td>{row.sku_id}</td>
                <td>{row.category}</td>
                <td>{row.closing_stock}</td>
                <td>{row.lead_time_days}d</td>
                <td>{row.predicted_next_day_demand?.toFixed(1)}/day</td>
                <td>{row.cover_ratio}</td>
                <td><RiskBadge flag={row.risk_flag} /></td>
                <td>
                  <button onClick={() => setSelectedSku(row.sku_id)}>Explain</button>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      )}

      {selectedSku && <SkuDetail skuId={selectedSku} onClose={() => setSelectedSku(null)} />}

      <AskBox />
    </div>
  );
}

export default App;
