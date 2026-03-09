import { useState, useEffect } from "react";
import VaultDashboard from "./VaultDashboard";

/*
 * INTEGRATION INSTRUCTIONS
 * ========================
 * 1. Push vault.json to repo root (same level as index.html)
 * 2. Push VaultDashboard.jsx to src/
 * 3. Push this file (GroveRouter.jsx) to src/
 * 4. In your existing App.jsx (the garden component):
 *    - Remove the hardcoded PROJECTS array
 *    - Add this prop: export default function App({ projects }) { ... }
 *      (or whatever your component is named)
 *    - Replace every reference to PROJECTS with the `projects` prop
 *    - That's it. The garden code stays exactly the same otherwise.
 * 5. In main.jsx, change:
 *      import App from './App'
 *    to:
 *      import GroveRouter from './GroveRouter'
 *    and change:
 *      <App />
 *    to:
 *      <GroveRouter />
 *
 * HOW IT WORKS
 * - On page load, checks window.location.pathname
 * - /vault → renders VaultDashboard (fetches vault.json itself)
 * - anything else → fetches vault.json, filters portfolio_visible,
 *   maps to the PROJECTS shape your garden expects, renders the garden
 *
 * VERSION: 1.0.0
 */

// ─── Import your existing garden component ───
// Change this import to match your actual file/export name
import Garden from "./App";

// ─── Map vault.json entries → the PROJECTS shape the garden expects ───
const STATUS_TO_STAGE = {
  raw: "seed",
  scouted: "sprout",
  building: "sapling",
  "in-dev": "sapling",
  deployed: "mature",
  shipped: "mature",
  parked: "sprout",
  killed: "seed",
};

function vaultToProjects(ideas) {
  return ideas
    .filter((i) => i.portfolio_visible)
    .map((idea) => ({
      name: idea.title,
      description: idea.one_liner,
      stage: STATUS_TO_STAGE[idea.status] || "seed",
      status: idea.status,
      impact: idea.impact_pct,
      business: idea.business_pct,
      url: idea.deploy_url || null,
      tags: idea.tags || [],
      key_insight: idea.key_insight || "",
      verdict: idea.verdict || "",
    }));
}

export default function GroveRouter() {
  const [projects, setProjects] = useState(null);
  const [error, setError] = useState(null);
  const isVault = window.location.pathname === "/vault";

  useEffect(() => {
    // VaultDashboard fetches its own data, so we only need this for the garden
    if (isVault) return;
    fetch("/vault.json")
      .then((r) => {
        if (!r.ok) throw new Error(`Failed to load vault.json: ${r.status}`);
        return r.json();
      })
      .then((vault) => setProjects(vaultToProjects(vault.ideas)))
      .catch((e) => {
        console.error("Vault fetch failed, using empty projects:", e);
        setError(e.message);
        setProjects([]);
      });
  }, [isVault]);

  if (isVault) return <VaultDashboard />;

  if (projects === null) {
    return (
      <div
        style={{
          minHeight: "100vh",
          background: "#0a1628",
          display: "flex",
          alignItems: "center",
          justifyContent: "center",
          color: "#6ee06e",
          fontFamily: "monospace",
        }}
      >
        Loading...
      </div>
    );
  }

  // Pass projects to the existing garden component
  return <Garden projects={projects} />;
}
