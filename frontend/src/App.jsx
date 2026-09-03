import { useEffect, useState } from "react";
import "./App.css";

const API_BASE = import.meta.env.VITE_API_BASE_URL || "http://localhost:8000";

function App() {
  const [metrics, setMetrics] = useState(null);
  const [latestRecovery, setLatestRecovery] = useState(null);
  const [loading, setLoading] = useState(true);
  const [simulating, setSimulating] = useState(false);
  const [error, setError] = useState(null);
  const [showDemoForm, setShowDemoForm] = useState(false);
  const [latestRationale, setLatestRationale] = useState("");
  const [latestPayment, setLatestPayment] = useState(null);
  const [demoForm, setDemoForm] = useState({
    payment_id: "",
    merchant_id: "",
    customer_id: "",
    amount: "",
    currency: "INR",
    payment_method: "CARD",
    simulation_outcome: "FAILED",
  });

  useEffect(() => {
    loadDashboard();
  }, []);

  async function loadDashboard() {
    setLoading(true);
    setError(null);

    try {
      const [metricsResponse, recoveryResponse] = await Promise.all([
        fetch(`${API_BASE}/metrics/recovery`),
        fetch(`${API_BASE}/recovery-events/latest`),
      ]);

      if (!metricsResponse.ok) {
        throw new Error(`Metrics request failed: ${metricsResponse.status}`);
      }

      const metricsData = await metricsResponse.json();
      setMetrics(metricsData);

      if (recoveryResponse.status === 404) {
        setLatestRecovery(null);
      } else if (!recoveryResponse.ok) {
        throw new Error(
          `Latest recovery request failed: ${recoveryResponse.status}`,
        );
      } else {
        const recoveryData = await recoveryResponse.json();
        setLatestRecovery(recoveryData);
      }
    } catch (err) {
      console.error(err);
      setError(
        "Could not load recovery data. Make sure the backend is running.",
      );
    } finally {
      setLoading(false);
    }
  }

  async function handleSimulateFailure() {
    setShowDemoForm(true);
    setError(null);
  }

  async function handleRunRecovery(e) {
    e.preventDefault();

    setSimulating(true);
    setError(null);

    try {
      const payload = {
        ...demoForm,
        amount: Number(demoForm.amount),
        payment_method: demoForm.payment_method.toUpperCase(),
        currency: demoForm.currency.toUpperCase(),
      };

      const response = await fetch(`${API_BASE}/payments`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify(payload),
      });

      if (!response.ok) {
        const errorBody = await response.text();

        throw new Error(
          `Payment simulation failed: ${response.status} ${errorBody}`,
        );
      }

      const responseData = await response.json();

      if (responseData.status === "success") {
        setLatestPayment(responseData);
        setLatestRationale("");
      } else {
        setLatestPayment(null);
        setLatestRationale(responseData?.recovery?.rationale || "");
      }
      setLatestRationale(responseData?.recovery?.rationale || "");

      setShowDemoForm(false);

      await loadDashboard();
    } catch (err) {
      console.error(err);
      setError(
        "Could not run the payment simulation. Check the backend and form values.",
      );
    } finally {
      setSimulating(false);
    }
  }

  function handleDemoFieldChange(e) {
    const { name, value } = e.target;

    setDemoForm((current) => ({
      ...current,
      [name]: value,
    }));
  }
  function formatCurrency(value, currency = "INR") {
    if (value === null || value === undefined) {
      return "—";
    }

    return new Intl.NumberFormat("en-IN", {
      style: "currency",
      currency,
      maximumFractionDigits: 2,
    }).format(Number(value));
  }

  function formatAction(action) {
    if (!action) return "—";

    return action
      .toLowerCase()
      .split("_")
      .map((word) => word.charAt(0).toUpperCase() + word.slice(1))
      .join(" ");
  }

  function formatProbability(value) {
    if (value === null || value === undefined) {
      return "—";
    }

    return `${(Number(value) * 100).toFixed(1)}%`;
  }

  const caseData = latestRecovery?.case;
  const aiDecision = latestRecovery?.ai_decision;
  const policy = latestRecovery?.policy;
  const execution = latestRecovery?.execution;
  const outcome = latestRecovery?.outcome;

  const isRecovered = caseData?.status === "RECOVERED";
  const executionSucceeded = execution?.outcome === "SUCCESS";

  return (
    <div className="app">
      <header className="header">
        <div>
          <h1>Revenue Recovery</h1>
          <p>AI-powered recovery strategy optimizer</p>
        </div>

        <div className="header-actions">
          <div className="status">
            <span className="status-dot"></span>
            Demo Environment
          </div>

          <button
            className="refresh-button"
            onClick={loadDashboard}
            disabled={loading || simulating}
          >
            {loading ? "Refreshing..." : "Refresh"}
          </button>
        </div>
      </header>

      <main>
        {error && <div className="error-banner">{error}</div>}

        {/* KPI SECTION */}
        <section className="kpi-grid">
          <div className="card kpi-card">
            <span className="label">Recovery Attempts</span>
            <strong>{metrics ? metrics.total_recovery_attempts : "—"}</strong>
            <span className="muted">Total evaluated recoveries</span>
          </div>

          <div className="card kpi-card">
            <span className="label">Success Rate</span>
            <strong>
              {metrics
                ? `${(metrics.recovery_success_rate * 100).toFixed(1)}%`
                : "—"}
            </strong>
            <span className="muted">Successful recovery attempts</span>
          </div>

          <div className="card kpi-card">
            <span className="label">Net Recovered</span>
            <strong>
              {metrics ? formatCurrency(metrics.net_recovered_value) : "—"}
            </strong>
            <span className="muted">Revenue after intervention cost</span>
          </div>
        </section>

        {/* SECONDARY METRICS */}
        <section className="secondary-metrics">
          <div className="metric-item">
            <span>Total Recovered</span>
            <strong>
              {metrics ? formatCurrency(metrics.total_recovered_value) : "—"}
            </strong>
          </div>

          <div className="metric-item">
            <span>Fee Loss</span>
            <strong>
              {metrics ? formatCurrency(metrics.total_fee_loss) : "—"}
            </strong>
          </div>

          <div className="metric-item">
            <span>Successful Recoveries</span>
            <strong>{metrics ? metrics.successful_recoveries : "—"}</strong>
          </div>

          <div className="metric-item">
            <span>LLM Probability Error</span>
            <strong>
              {metrics ? formatProbability(metrics.llm_error) : "—"}
            </strong>
          </div>

          <div className="metric-item">
            <span>Baseline Probability Error</span>
            <strong>
              {metrics ? formatProbability(metrics.baseline_error) : "—"}
            </strong>
          </div>
        </section>

        {/* DEMO CONTROLS */}
        <section className="card demo-controls">
          {!showDemoForm ? (
            <>
              <div className="demo-icon" aria-hidden="true">
                ₹
              </div>

              <div className="demo-copy">
                <h2>Demo Controls</h2>
                <p>Enter a synthetic payment and run the recovery pipeline.</p>
              </div>

              <div className="demo-action">
                <button
                  className="simulate-button"
                  onClick={handleSimulateFailure}
                >
                  Simulate Failed Payment
                </button>
              </div>
            </>
          ) : (
            <form className="demo-form" onSubmit={handleRunRecovery}>
              <div className="demo-form-header">
                <div>
                  <h2>Simulate Payment</h2>
                  <p>
                    Enter payment details to send a synthetic request to the
                    backend.
                  </p>
                </div>
              </div>

              <div className="demo-form-grid">
                <label>
                  Payment ID
                  <input
                    name="payment_id"
                    value={demoForm.payment_id}
                    onChange={handleDemoFieldChange}
                    placeholder="pay_demo_001"
                    required
                  />
                </label>

                <label>
                  Merchant ID
                  <input
                    name="merchant_id"
                    value={demoForm.merchant_id}
                    onChange={handleDemoFieldChange}
                    placeholder="merchant_001"
                    required
                  />
                </label>

                <label>
                  Customer ID
                  <input
                    name="customer_id"
                    value={demoForm.customer_id}
                    onChange={handleDemoFieldChange}
                    placeholder="customer_001"
                    required
                  />
                </label>

                <label>
                  Amount
                  <input
                    type="number"
                    name="amount"
                    value={demoForm.amount}
                    onChange={handleDemoFieldChange}
                    placeholder="5000"
                    min="1"
                    required
                  />
                </label>

                <label>
                  Currency
                  <input
                    name="currency"
                    value={demoForm.currency}
                    onChange={handleDemoFieldChange}
                    placeholder="INR"
                    required
                  />
                </label>

                <label>
                  Payment Method
                  <select
                    name="payment_method"
                    value={demoForm.payment_method}
                    onChange={handleDemoFieldChange}
                    required
                  >
                    <option value="CARD">CARD</option>
                    <option value="UPI">UPI</option>
                    <option value="NETBANKING">NETBANKING</option>
                    <option value="WALLET">WALLET</option>
                  </select>
                </label>

                <label>
                  Simulation Outcome
                  <select
                    name="simulation_outcome"
                    value={demoForm.simulation_outcome}
                    onChange={handleDemoFieldChange}
                  >
                    <option value="FAILED">FAILED</option>
                    <option value="SUCCESS">SUCCESS</option>
                  </select>
                </label>
              </div>

              <div className="demo-form-actions">
                <button
                  type="button"
                  className="cancel-button"
                  onClick={() => setShowDemoForm(false)}
                  disabled={simulating}
                >
                  Cancel
                </button>

                <button
                  type="submit"
                  className="simulate-button"
                  disabled={simulating}
                >
                  {simulating ? "Running Recovery..." : "Run Recovery"}
                </button>
              </div>
            </form>
          )}
        </section>

        {/* RECOVERY LIFECYCLE */}
        <section className="card lifecycle-card">
          <div className="section-heading">
            <div>
              <h2>Recovery Lifecycle</h2>
              <p>From payment failure to verified recovery outcome</p>
            </div>

            {caseData && (
              <span
                className={`case-status ${isRecovered ? "success" : "neutral"}`}
              >
                {caseData.status}
              </span>
            )}
          </div>

          <div className="lifecycle">
            <div className="stage stage-failed">
              <span className="stage-number">1</span>

              <span className="stage-icon" aria-hidden="true">
                !
              </span>

              <strong>Payment Failed</strong>

              <span>
                {caseData
                  ? `${formatCurrency(
                      caseData.amount,
                      caseData.currency,
                    )} at risk`
                  : "Revenue at risk identified"}
              </span>
            </div>

            <div className="arrow">→</div>

            <div className="stage stage-ai">
              <span className="stage-number">2</span>

              <span className="stage-icon" aria-hidden="true">
                ✦
              </span>

              <strong>AI Decision</strong>

              <span>
                {aiDecision
                  ? formatAction(aiDecision.action)
                  : "Gemini selects an action"}
              </span>
            </div>

            <div className="arrow">→</div>

            <div className="stage stage-policy">
              <span className="stage-number">3</span>

              <span className="stage-icon" aria-hidden="true">
                ✓
              </span>

              <strong>Policy Check</strong>

              <span>
                {policy
                  ? policy.execution_authorized
                    ? "Approved"
                    : "Not Authorized"
                  : "Guardrails validate action"}
              </span>
            </div>

            <div className="arrow">→</div>

            <div className="stage stage-execution">
              <span className="stage-number">4</span>

              <span className="stage-icon" aria-hidden="true">
                ↗
              </span>

              <strong>Execution</strong>

              <span>
                {execution ? execution.outcome : "Action executed safely"}
              </span>
            </div>

            <div className="arrow">→</div>

            <div className="stage stage-outcome">
              <span className="stage-number">5</span>

              <span className="stage-icon" aria-hidden="true">
                ✓
              </span>

              <strong>Outcome</strong>

              <span>
                {outcome ? outcome.status : "Recovery result verified"}
              </span>
            </div>
          </div>
        </section>

        {/* LATEST RECOVERY */}
        <section className="card recovery-card">
          <div className="section-heading">
            <div>
              <h2>Latest Recovery</h2>
              <p>Most recent recovery decision, execution and outcome</p>
            </div>
          </div>
          {latestPayment ? (
            <div className="successful-payment">
              <div className="successful-payment-title">Payment Successful</div>

              <div className="detail-grid">
                <div className="detail">
                  <span>Payment ID</span>
                  <strong>{latestPayment.payment_id}</strong>
                </div>

                <div className="detail">
                  <span>Amount</span>
                  <strong>
                    {formatCurrency(
                      latestPayment.amount,
                      latestPayment.currency || "INR",
                    )}
                  </strong>
                </div>

                <div className="detail">
                  <span>Payment Method</span>
                  <strong>{latestPayment.payment_method}</strong>
                </div>

                <div className="detail">
                  <span>Recovery Required</span>
                  <strong>No</strong>
                </div>
              </div>
            </div>
          ) : loading && !latestRecovery ? (
            <div className="empty-state">
              <strong>Loading recovery data...</strong>
              <span>Fetching the latest recovery case.</span>
            </div>
          ) : !latestRecovery ? (
            <div className="empty-state">
              <strong>No recovery data available</strong>
              <span>
                Click "Simulate Failed Payment" to run the first recovery.
              </span>
            </div>
          ) : (
            <>
              {/* PAYMENT FAILURE */}
              <div className="recovery-section">
                <div className="recovery-section-title">Payment Failure</div>

                <div className="detail-grid">
                  <div className="detail">
                    <span>Payment ID</span>
                    <strong>{caseData?.payment_id || "—"}</strong>
                  </div>

                  <div className="detail">
                    <span>Amount at Risk</span>
                    <strong>
                      {formatCurrency(
                        caseData?.amount,
                        caseData?.currency || "INR",
                      )}
                    </strong>
                  </div>

                  <div className="detail">
                    <span>Failure Category</span>
                    <strong>{caseData?.failure_category || "—"}</strong>
                  </div>

                  <div className="detail">
                    <span>Payment Method</span>
                    <strong>{caseData?.payment_method || "—"}</strong>
                  </div>
                </div>
              </div>

              {/* AI DECISION */}
              <div className="recovery-section">
                <div className="recovery-section-title">AI Decision</div>

                <div className="decision-row">
                  <div className="decision-main">
                    <span className="detail-label">Selected Action</span>

                    <strong className="decision-action">
                      {formatAction(aiDecision?.action)}
                    </strong>
                  </div>

                  <div className="decision-confidence">
                    <span className="detail-label">
                      Predicted Recovery Probability
                    </span>

                    <strong>
                      {formatProbability(aiDecision?.predicted_p_recovery)}
                    </strong>
                  </div>
                </div>
              </div>

              {/* GEMINI RATIONALE */}
              {latestRationale && (
                <div className="recovery-section">
                  <div className="recovery-section-title">Gemini Rationale</div>

                  <p className="rationale-text">{latestRationale}</p>
                </div>
              )}

              {/* POLICY */}
              <div className="recovery-section">
                <div className="recovery-section-title">
                  Final Policy Outcome
                </div>

                <div className="decision-row">
                  <div>
                    <span className="detail-label">
                      Execution Authorization
                    </span>

                    <strong className="policy-approved">
                      {policy?.execution_authorized
                        ? "APPROVED FOR EXECUTION"
                        : "NOT AUTHORIZED"}
                    </strong>
                  </div>

                  <div>
                    <span className="detail-label">Final Action</span>

                    <strong>{formatAction(policy?.final_action)}</strong>
                  </div>
                </div>
              </div>

              {/* EXECUTION + OUTCOME */}
              <div className="recovery-section last-section">
                <div className="recovery-section-title">
                  Execution & Outcome
                </div>

                <div className="detail-grid">
                  <div className="detail">
                    <span>Execution</span>
                    <strong>{formatAction(execution?.action)}</strong>
                  </div>

                  <div className="detail">
                    <span>Result</span>
                    <strong
                      className={executionSucceeded ? "execution-success" : ""}
                    >
                      {execution?.outcome || "—"}
                    </strong>
                  </div>

                  <div className="detail">
                    <span>Recovered Value</span>
                    <strong>
                      {formatCurrency(
                        outcome?.recovered_value,
                        caseData?.currency || "INR",
                      )}
                    </strong>
                  </div>

                  <div className="detail">
                    <span>Net Recovery</span>
                    <strong>
                      {formatCurrency(
                        outcome?.net_recovery_value,
                        caseData?.currency || "INR",
                      )}
                    </strong>
                  </div>
                </div>
              </div>
            </>
          )}
        </section>
      </main>
    </div>
  );
}

export default App;
