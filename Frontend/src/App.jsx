import './App.css'

const kpis = [
  { label: 'Healthy SKUs', value: '72%', tone: 'green' },
  { label: 'At Risk', value: '18%', tone: 'yellow' },
  { label: 'Overstock', value: '10%', tone: 'dark' },
]

const productRows = [
  ['SKU-1042', 'Snacks', '16 days', 'Stockout risk'],
  ['SKU-1188', 'Beverages', '49 days', 'Healthy'],
  ['SKU-0911', 'Grains', '63 days', 'Overstock'],
]

function App() {
  return (
    <main className="dashboard-shell">
      <aside className="sidebar">
        <div className="brand-mark">FMN</div>
        <nav className="nav">
          <span className="nav-item active">Overview</span>
          <span className="nav-item">Inventory</span>
          <span className="nav-item">Suppliers</span>
          <span className="nav-item">Alerts</span>
        </nav>
      </aside>

      <section className="main-panel">
        <header className="topbar">
          <div>
            <p className="eyebrow">Flour Mills of Nigeria</p>
            <h1>Supply Chain Demand Watch</h1>
          </div>
          <button className="action-btn">Export report</button>
        </header>

        <div className="kpi-grid">
          {kpis.map((item) => (
            <div key={item.label} className={`kpi-card ${item.tone}`}>
              <span>{item.label}</span>
              <strong>{item.value}</strong>
            </div>
          ))}
        </div>

        <div className="content-grid">
          <div className="panel chart-panel">
            <div className="panel-header">
              <h2>Demand coverage</h2>
              <span>Last 30 days</span>
            </div>
            <div className="chart-bars" aria-label="Demand coverage chart">
              <span style={{ height: '28%' }} />
              <span style={{ height: '42%' }} />
              <span style={{ height: '54%' }} />
              <span style={{ height: '63%' }} />
              <span style={{ height: '48%' }} />
              <span style={{ height: '70%' }} />
              <span style={{ height: '82%' }} />
            </div>
          </div>

          <div className="panel list-panel">
            <div className="panel-header">
              <h2>Priority SKUs</h2>
              <span>Today</span>
            </div>
            <table>
              <thead>
                <tr>
                  <th>SKU</th>
                  <th>Category</th>
                  <th>Days</th>
                  <th>Status</th>
                </tr>
              </thead>
              <tbody>
                {productRows.map(([sku, category, days, status]) => (
                  <tr key={sku}>
                    <td>{sku}</td>
                    <td>{category}</td>
                    <td>{days}</td>
                    <td>
                      <span className={`status ${status.toLowerCase().replace(/\s+/g, '-')}`}>
                        {status}
                      </span>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      </section>
    </main>
  )
}

export default App
