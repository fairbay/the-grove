import { useState, useEffect } from "react";
import VaultDashboard from "./VaultDashboard";
import Garden from "./App";
import BookPage from "./BookPage";

/*
 * GroveRouter v2.1.0
 * 
 * Routes:
 * - /vault → VaultDashboard
 * - /books/stage-directions → BookPage
 * - / (default) → The Grove walking garden
 */

function vaultToProjects(ideas) {
  return ideas
    .filter((i) => i.portfolio_visible)
    .map((idea) => ({
      title: idea.title,
      one_liner: idea.one_liner,
      hero_description: idea.hero_description || null,
      status: idea.status,
      tags: idea.tags || [],
      impact_score: idea.impact_pct != null ? idea.impact_pct : null,
      business_score: idea.business_pct != null ? idea.business_pct : null,
      deploy_url: idea.deploy_url || null,
    }));
}

export default function GroveRouter() {
  const [projects, setProjects] = useState(null);
  const [error, setError] = useState(null);
  const path = window.location.pathname;
  const isVault = path === "/vault";
  const isBook = path.startsWith("/books/");

  useEffect(() => {
    if (isVault || isBook) return;
    fetch("/vault.json")
      .then((r) => {
        if (!r.ok) throw new Error(`Failed to load vault.json: ${r.status}`);
        return r.json();
      })
      .then((vault) => setProjects(vaultToProjects(vault.ideas)))
      .catch((e) => {
        console.error("Vault fetch failed:", e);
        setError(e.message);
        setProjects([]);
      });
  }, [isVault, isBook]);

  if (isVault) return <VaultDashboard />;
  if (isBook) return <BookPage />;

  if (projects === null) {
    return (
      <div style={{
        width: "100vw", height: "100vh",
        background: "linear-gradient(180deg, #7EC8E3 0%, #6BA34E 50%)",
        display: "flex", alignItems: "center", justifyContent: "center",
        fontFamily: "'Outfit', sans-serif",
      }}>
        <div style={{
          background: "rgba(255,255,255,0.45)", backdropFilter: "blur(8px)",
          borderRadius: 14, padding: "12px 24px",
          border: "1px solid rgba(255,255,255,0.35)",
          color: "#2C3E1F", fontSize: 14,
        }}>
          Loading the grove...
        </div>
      </div>
    );
  }

  return <Garden projects={projects} />;
}
