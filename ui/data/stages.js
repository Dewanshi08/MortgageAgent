/* ═══════════════════════════════════════════
   data/stages.js
   Journey stage definitions
   Edit this file to add/remove/reorder stages and topics.
   ═══════════════════════════════════════════ */

window.STAGES_DATA = [
  {
    id: 1,
    name: "Learn",
    desc: "Mortgage basics",
    color: "#2563eb",
    bg: "#eff4ff",
    topics: [
      { id: "t1", title: "Stress Test (B-20)", covered: true },
      { id: "t2", title: "Fixed vs Variable Rates", covered: true },
      { id: "t3", title: "Down Payment Rules", covered: true },
      { id: "t4", title: "CMHC Insurance", covered: false },
    ],
  },
  {
    id: 2,
    name: "Affordability",
    desc: "What can you afford?",
    color: "#0d9488",
    bg: "#ecfdf5",
    topics: [
      { id: "t5", title: "GDS / TDS Ratios", covered: true },
      { id: "t6", title: "Loan-to-Value (LTV)", covered: true },
      { id: "t7", title: "FHSA + HBP Programs", covered: false },
      { id: "t8", title: "Closing Costs", covered: false },
    ],
  },
  {
    id: 3,
    name: "Pre-Approval",
    desc: "Getting ready to apply",
    color: "#d97706",
    bg: "#fffbeb",
    topics: [
      { id: "t9", title: "What is Pre-Approval?", covered: true },
      { id: "t10", title: "Documents You'll Need", covered: false },
      { id: "t11", title: "Rate Holds Explained", covered: false },
      { id: "t12", title: "Approval Stages & Timeline", covered: false },
    ],
  },
  {
    id: 4,
    name: "Shopping",
    desc: "Evaluating properties",
    color: "#dc2626",
    bg: "#fef2f2",
    topics: [
      { id: "t13", title: "HCRA Builder Licensing", covered: false },
      { id: "t14", title: "Tarion Warranty", covered: false },
      { id: "t15", title: "Pre-Construction Risks", covered: false },
      { id: "t16", title: "Area Development Plans", covered: false },
    ],
  },
  {
    id: 5,
    name: "Agreement",
    desc: "Review before signing",
    color: "#7c3aed",
    bg: "#f5f3ff",
    topics: [
      { id: "t17", title: "Key APS Clauses", covered: false },
      { id: "t18", title: "Questions for Your Lawyer", covered: false },
      { id: "t19", title: "IRD Penalty Math", covered: false },
    ],
  },
];