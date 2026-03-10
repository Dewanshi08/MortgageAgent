/* ═══════════════════════════════════════════
   components/Onboarding.js
   Personalization modal shown on first visit.
   Pastel-colored sections, pill selectors for
   purchase type and first-time buyer fields.
   ═══════════════════════════════════════════ */

const { useState: useStateOB } = React;

function Onboarding({ onDone, onSkip }) {
  const [form, setForm] = useStateOB({
    name: "",
    income: "",
    dp: "",
    loc: "GTA",
    prov: "ON",
    ftb: true,
    type: "pre-construction",
    price: "",
  });

  const [debts, setDebts] = useStateOB({
    car: false, carAmt: "",
    cc: false,  ccAmt: "",
    stu: false, stuAmt: "",
    loc2: false, locAmt: "",
  });

  const [busy, setBusy] = useStateOB(false);

  const updateForm = (key) => (e) => setForm({ ...form, [key]: e.target.value });

  const submit = async () => {
    setBusy(true);
    try {
      const body = {
        ...form,
        income: form.income ? parseFloat(form.income) : null,
        dp_amount: form.dp ? parseFloat(form.dp) : null,
        target_price: form.price ? parseFloat(form.price) : null,
        liabilities: {
          has_car_loan: debts.car,
          car_loan_monthly: debts.car && debts.carAmt ? parseFloat(debts.carAmt) : null,
          has_credit_card: debts.cc,
          credit_card_monthly: debts.cc && debts.ccAmt ? parseFloat(debts.ccAmt) : null,
          has_student_loan: debts.stu,
          student_loan_monthly: debts.stu && debts.stuAmt ? parseFloat(debts.stuAmt) : null,
          has_loc: debts.loc2,
          loc_monthly: debts.loc2 && debts.locAmt ? parseFloat(debts.locAmt) : null,
        },
      };
      const API = window.location.origin + "/api";
      const r = await fetch(API + "/context", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(body),
      });
      if (!r.ok) throw new Error(r.status);
      const data = await r.json();
      onDone(data.user_id, data.affordability_estimate);
    } catch (e) {
      console.error(e);
      onSkip();
    }
    setBusy(false);
  };

  // Reusable debt toggle row
  function DebtRow({ label, hasKey, amtKey }) {
    const on = debts[hasKey];
    return (
      <div className="debt-row">
        <div className="debt-label">{label}</div>
        <div
          className={`toggle ${on ? "on" : ""}`}
          onClick={() => {
            if (on) {
              setDebts({ ...debts, [hasKey]: false, [amtKey]: "" });
            } else {
              setDebts({ ...debts, [hasKey]: true });
            }
          }}
        >
          <div className="toggle-track" />
          <div className="toggle-thumb" />
        </div>
        <div className="debt-input">
          <input
            type="number"
            placeholder={on ? "$/month" : "--"}
            value={debts[amtKey]}
            disabled={!on}
            onChange={(e) => setDebts({ ...debts, [amtKey]: e.target.value })}
          />
        </div>
      </div>
    );
  }

  // Purchase type options
  const purchaseTypes = [
    { value: "pre-construction", label: "Pre-construction" },
    { value: "resale", label: "Resale" },
    { value: "refinance", label: "Refinance" },
  ];

  return (
    <div className="overlay">
      <div className="modal">
        {/* Header */}
        <div className="modal-header">
          <div className="modal-brand">own-ly</div>
          <div className="modal-tagline">own your dream</div>
          <h2>Let's personalize your journey</h2>
          <p className="msub">Help us tailor the numbers to your situation. You can skip this.</p>
        </div>

        {/* ── Personal Info Section ── */}
        <div className="form-section section-personal">
          <div className="section-title">About You</div>
          <div className="frow">
            <div className="ff">
              <label>Your Name</label>
              <input placeholder="e.g. Sara" value={form.name} onChange={updateForm("name")} />
            </div>
            <div className="ff">
              <label>Location</label>
              <input placeholder="GTA" value={form.loc} onChange={updateForm("loc")} />
            </div>
          </div>
        </div>

        {/* ── Financial Info Section ── */}
        <div className="form-section section-financial">
          <div className="section-title">Your Finances</div>
          <div className="frow">
            <div className="ff">
              <label>Annual Income ($)</label>
              <input type="number" placeholder="95,000" value={form.income} onChange={updateForm("income")} />
            </div>
            <div className="ff">
              <label>Down Payment ($)</label>
              <input type="number" placeholder="45,000" value={form.dp} onChange={updateForm("dp")} />
            </div>
          </div>
        </div>

        {/* ── Property Section ── */}
        <div className="form-section section-property">
          <div className="section-title">Property Details</div>
          <div className="ff">
            <label>Target Home Price ($)</label>
            <input type="number" placeholder="700,000" value={form.price} onChange={updateForm("price")} />
          </div>
          <div className="ff" style={{ marginTop: 10 }}>
            <label>Purchase Type</label>
            <div className="pill-group">
              {purchaseTypes.map((pt) => (
                <div
                  key={pt.value}
                  className={`pill ${form.type === pt.value ? "selected" : ""}`}
                  onClick={() => setForm({ ...form, type: pt.value })}
                >
                  {pt.label}
                </div>
              ))}
            </div>
          </div>
          <div className="ff" style={{ marginTop: 10 }}>
            <label>First-time Buyer?</label>
            <div className="pill-group">
              <div
                className={`pill ${form.ftb === true ? "selected" : ""}`}
                onClick={() => setForm({ ...form, ftb: true })}
              >
                Yes, first time
              </div>
              <div
                className={`pill ${form.ftb === false ? "selected" : ""}`}
                onClick={() => setForm({ ...form, ftb: false })}
              >
                No, I've owned before
              </div>
            </div>
          </div>
        </div>

        {/* ── Debts Section ── */}
        <div className="form-section section-debts">
          <div className="section-title">Existing Debts</div>
          <DebtRow label="Car Loan" hasKey="car" amtKey="carAmt" />
          <DebtRow label="Credit Card" hasKey="cc" amtKey="ccAmt" />
          <DebtRow label="Student Loan" hasKey="stu" amtKey="stuAmt" />
          <DebtRow label="Line of Credit" hasKey="loc2" amtKey="locAmt" />
        </div>

        {/* ── Actions ── */}
        <div className="modal-btns">
          <button className="btn-skip" onClick={onSkip}>Skip for now</button>
          <button className="btn-go" onClick={submit} disabled={busy}>
            {busy ? "Saving..." : "Start my journey"}
          </button>
        </div>
      </div>
    </div>
  );
}

window.Onboarding = Onboarding;