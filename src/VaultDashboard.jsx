import { useState, useEffect, useMemo } from "react";

const VAULT_URL = "https://script.google.com/macros/s/AKfycbwuseoPyb3kt1lajUFWgwwQJ9FZQo7tZY5Vt7U0-qZds8e_hJpAy9jP22QaKSWp-8BW/exec?format=json";

const STATUS_COLORS = {
  deployed: { bg: "#1a3a1a", text: "#6ee06e", border: "#2d5a2d" },
  shipped: { bg: "#1a3a2a", text: "#6ee0a0", border: "#2d5a4a" },
  building: { bg: "#3a3a1a", text: "#e0d86e", border: "#5a5a2d" },
  "in-dev": { bg: "#3a2a1a", text: "#e0a86e", border: "#5a4a2d" },
  scouted: { bg: "#1a2a3a", text: "#6eb8e0", border: "#2d4a5a" },
  raw: { bg: "#2a2a2a", text: "#a0a0a0", border: "#404040" },
  shelved: { bg: "#2a2a1a", text: "#c0b060", border: "#4a4a2d" },
  parked: { bg: "#2a1a2a", text: "#b88ec0", border: "#4a2d4a" },
  killed: { bg: "#3a1a1a", text: "#c07070", border: "#5a2d2d" },
};

const VERDICT_ICONS = {
  Unicorn: "\u{1F984}",
  "Public good": "\u{1F331}",
  Pass: "\u2014",
  Infrastructure: "\u{1F527}",
  "Creative project": "\u{1F3A8}",
  Blocked: "\u{1F6AB}",
  "personal-use": "\u{1F3E0}",
};

const STATUS_ORDER = ["deployed", "shipped", "building", "in-dev", "scouted", "raw", "shelved", "parked", "killed"];

const COLUMNS = [
  { key: "portfolio_visible", label: "", width: 20 },
  { key: "title", label: "Idea", sortable: true },
  { key: "status", label: "Status", sortable: true },
  { key: "impact_pct", label: "Impact", sortable: true },
  { key: "business_pct", label: "Business", sortable: true },
  { key: "sustainability_pct", label: "Sust.", sortable: true },
  { key: "verdict", label: "Verdict", sortable: true },
  { key: "date_updated", label: "Updated", sortable: true },
];

function ScoreBar({ value, color }) {
  if (value == null) return <span style={{ color: "#555", fontSize: 12 }}>--</span>;
  const w = Math.max(value, 4);
  return (
    <div style={{ display: "flex", alignItems: "center", gap: 6, minWidth: 100 }}>
      <div style={{ flex: 1, height: 6, background: "#1a1a1a", borderRadius: 3, overflow: "hidden" }}>
        <div
          style={{
            width: `${w}%`,
            height: "100%",
            background: value >= 56 ? color : "#555",
            borderRadius: 3,
            transition: "width 0.4s ease",
          }}
        />
      </div>
      <span style={{ fontSize: 12, color: value >= 56 ? color : "#777", fontVariantNumeric: "tabular-nums", minWidth: 28, textAlign: "right" }}>
        {value}%
      </span>
    </div>
  );
}

function StatusBadge({ status }) {
  const colors = STATUS_COLORS[status] || STATUS_COLORS.raw;
  return (
    <span
      style={{
        display: "inline-block",
        padding: "2px 8px",
        borderRadius: 4,
        fontSize: 11,
        fontWeight: 600,
        textTransform: "uppercase",
        letterSpacing: "0.05em",
        background: colors.bg,
        color: colors.text,
        border: `1px solid ${colors.border}`,
      }}
    >
      {status}
    </span>
  );
}

function SortIndicator({ active, direction }) {
  if (!active) return <span style={{ color: "#333", fontSize: 10, marginLeft: 3 }}>{"\u2195"}</span>;
  return <span style={{ color: "#6ee06e", fontSize: 10, marginLeft: 3 }}>{direction === "asc" ? "\u2191" : "\u2193"}</span>;
}

export default function VaultDashboard() {
  const [vault, setVault] = useState(null);
  const [error, setError] = useState(null);
  const [statusFilter, setStatusFilter] = useState("all");
  const [sortKey, setSortKey] = useState("date_updated");
  const [sortAsc, setSortAsc] = useState(false);
  const [search, setSearch] = useState("");
  const [expandedId, setExpandedId] = useState(null);

  useEffect(() => {
    fetch(VAULT_URL)
      .then((r) => {
        if (!r.ok) throw new Error(`${r.status}`);
        return r.json();
      })
      .then(setVault)
      .catch((e) => setError(e.message));
  }, []);

  const handleSort = (key) => {
    if (sortKey === key) {
      setSortAsc(!sortAsc);
    } else {
      setSortKey(key);
      // Default direction: dates and scores descending, text ascending
      setSortAsc(key === "title" || key === "status" || key === "verdict");
    }
  };

  const statuses = useMemo(() => {
    if (!vault) return [];
    const s = new Set(vault.ideas.map((i) => i.status));
    return STATUS_ORDER.filter((st) => s.has(st));
  }, [vault]);

  const filtered = useMemo(() => {
    if (!vault) return [];
    let ideas = vault.ideas;
    if (statusFilter !== "all") ideas = ideas.filter((i) => i.status === statusFilter);
    if (search.trim()) {
      const q = search.toLowerCase();
      ideas = ideas.filter(
        (i) =>
          i.title.toLowerCase().includes(q) ||
          i.one_liner.toLowerCase().includes(q) ||
          (i.tags || []).some((t) => t.toLowerCase().includes(q)) ||
          (i.verdict || "").toLowerCase().includes(q)
      );
    }
    return [...ideas].sort((a, b) => {
      let av = a[sortKey], bv = b[sortKey];
      if (sortKey === "status") {
        av = STATUS_ORDER.indexOf(a.status);
        bv = STATUS_ORDER.indexOf(b.status);
      }
      if (av == null && bv == null) return 0;
      if (av == null) return 1;
      if (bv == null) return -1;
      if (typeof av === "string") return sortAsc ? av.localeCompare(bv) : bv.localeCompare(av);
      return sortAsc ? av - bv : bv - av;
    });
  }, [vault, statusFilter, sortKey, sortAsc, search]);

  const counts = useMemo(() => {
    if (!vault) return {};
    const c = { all: vault.ideas.length };
    vault.ideas.forEach((i) => { c[i.status] = (c[i.status] || 0) + 1; });
    return c;
  }, [vault]);

  if (error) {
    return (
      <div style={{ minHeight: "100vh", background: "#0d0d0d", color: "#c07070", display: "flex", alignItems: "center", justifyContent: "center", fontFamily: "'IBM Plex Mono', monospace" }}>
        <div style={{ textAlign: "center" }}>
          <p style={{ fontSize: 18 }}>Failed to load vault</p>
          <p style={{ fontSize: 13, color: "#666", marginTop: 8 }}>{error}</p>
        </div>
      </div>
    );
  }

  if (!vault) {
    return (
      <div style={{ minHeight: "100vh", background: "#0d0d0d", color: "#6ee06e", display: "flex", alignItems: "center", justifyContent: "center", fontFamily: "'IBM Plex Mono', monospace" }}>
        <p style={{ animation: "pulse 1.5s ease-in-out infinite" }}>Loading vault...</p>
      </div>
    );
  }

  return (
    <div style={{ minHeight: "100vh", background: "#0d0d0d", color: "#d4d4c8", fontFamily: "'IBM Plex Mono', monospace" }}>
      <style>{`
        @import url('https://fonts.googleapis.com/css2?family=IBM+Plex+Mono:wght@300;400;600&display=swap');
        * { box-sizing: border-box; margin: 0; padding: 0; }
        @keyframes pulse { 0%,100% { opacity: 0.4; } 50% { opacity: 1; } }
        @keyframes fadeIn { from { opacity: 0; transform: translateY(6px); } to { opacity: 1; transform: translateY(0); } }
        ::selection { background: #2d5a2d; color: #d4d4c8; }
        ::-webkit-scrollbar { width: 6px; height: 6px; }
        ::-webkit-scrollbar-track { background: #0d0d0d; }
        ::-webkit-scrollbar-thumb { background: #333; border-radius: 3px; }
        .sort-header { cursor: pointer; user-select: none; transition: color 0.15s; }
        .sort-header:hover { color: #6ee06e !important; }
        .row-hover:hover { background: #111 !important; }
      `}</style>

      {/* Header */}
      <header style={{ borderBottom: "1px solid #1a1a1a", padding: "24px 32px 20px" }}>
        <div style={{ display: "flex", justifyContent: "space-between", alignItems: "baseline", flexWrap: "wrap", gap: 12 }}>
          <div>
            <h1 style={{ fontSize: 20, fontWeight: 300, color: "#6ee06e", letterSpacing: "0.04em" }}>
              THE VAULT
            </h1>
            <p style={{ fontSize: 11, color: "#555", marginTop: 4 }}>
              {vault.ideas.length} ideas · updated {vault.last_updated}
            </p>
          </div>
          <a
            href="/"
            style={{ fontSize: 11, color: "#555", textDecoration: "none", letterSpacing: "0.05em" }}
            onMouseOver={(e) => (e.target.style.color = "#6ee06e")}
            onMouseOut={(e) => (e.target.style.color = "#555")}
          >
            {"\u2190"} BACK TO GROVE
          </a>
        </div>
      </header>

      {/* Controls */}
      <div style={{ padding: "16px 32px", display: "flex", gap: 12, flexWrap: "wrap", alignItems: "center", borderBottom: "1px solid #111" }}>
        {/* Status filter pills */}
        <div style={{ display: "flex", gap: 4, flexWrap: "wrap" }}>
          {["all", ...statuses].map((s) => (
            <button
              key={s}
              onClick={() => setStatusFilter(s)}
              style={{
                padding: "4px 10px",
                borderRadius: 4,
                border: "1px solid",
                borderColor: statusFilter === s ? "#2d5a2d" : "#222",
                background: statusFilter === s ? "#1a3a1a" : "transparent",
                color: statusFilter === s ? "#6ee06e" : "#666",
                fontSize: 11,
                fontFamily: "inherit",
                cursor: "pointer",
                textTransform: "uppercase",
                letterSpacing: "0.03em",
              }}
            >
              {s} {counts[s] != null ? `(${counts[s]})` : ""}
            </button>
          ))}
        </div>

        <div style={{ flex: 1 }} />

        {/* Search */}
        <input
          type="text"
          placeholder="search..."
          value={search}
          onChange={(e) => setSearch(e.target.value)}
          style={{
            padding: "5px 10px",
            borderRadius: 4,
            border: "1px solid #222",
            background: "#111",
            color: "#d4d4c8",
            fontSize: 12,
            fontFamily: "inherit",
            outline: "none",
            width: 160,
          }}
        />
      </div>

      {/* Table */}
      <div style={{ overflowX: "auto", padding: "0 32px 32px" }}>
        <table style={{ width: "100%", borderCollapse: "collapse", marginTop: 8 }}>
          <thead>
            <tr style={{ borderBottom: "1px solid #1a1a1a" }}>
              {COLUMNS.map((col) => (
                <th
                  key={col.key}
                  className={col.sortable ? "sort-header" : undefined}
                  onClick={col.sortable ? () => handleSort(col.key) : undefined}
                  style={{
                    textAlign: "left",
                    padding: "8px 8px 8px 0",
                    fontSize: 10,
                    fontWeight: sortKey === col.key ? 600 : 400,
                    color: sortKey === col.key ? "#6ee06e" : "#555",
                    textTransform: "uppercase",
                    letterSpacing: "0.08em",
                    whiteSpace: "nowrap",
                    width: col.width || undefined,
                  }}
                >
                  {col.label}
                  {col.sortable && <SortIndicator active={sortKey === col.key} direction={sortAsc ? "asc" : "desc"} />}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {filtered.map((idea, idx) => {
              const isExpanded = expandedId === idea.title;
              return (
                <tr
                  key={idea.title}
                  className="row-hover"
                  onClick={() => setExpandedId(isExpanded ? null : idea.title)}
                  style={{
                    borderBottom: "1px solid #111",
                    cursor: "pointer",
                    animation: `fadeIn 0.2s ease ${idx * 0.03}s both`,
                    background: "transparent",
                  }}
                >
                  <td style={{ padding: "10px 8px 10px 0", width: 20 }}>
                    {idea.portfolio_visible && (
                      <span title="Portfolio visible" style={{ fontSize: 8, color: "#6ee06e" }}>{"\u25CF"}</span>
                    )}
                  </td>
                  <td style={{ padding: "10px 12px 10px 0" }}>
                    <div>
                      <span style={{ fontSize: 13, fontWeight: 600, color: "#d4d4c8" }}>
                        {idea.title}
                      </span>
                      {idea.deploy_url && (
                        <a
                          href={idea.deploy_url}
                          target="_blank"
                          rel="noopener"
                          onClick={(e) => e.stopPropagation()}
                          style={{ fontSize: 10, color: "#6eb8e0", marginLeft: 8, textDecoration: "none" }}
                        >
                          {"\u2197"} live
                        </a>
                      )}
                    </div>
                    {isExpanded && (
                      <div style={{ marginTop: 8, animation: "fadeIn 0.15s ease" }}>
                        <p style={{ fontSize: 12, color: "#888", lineHeight: 1.5, maxWidth: 500 }}>
                          {idea.one_liner}
                        </p>
                        {idea.key_insight && (
                          <p style={{ fontSize: 11, color: "#6e8e6e", marginTop: 6, lineHeight: 1.4, maxWidth: 500 }}>
                            {idea.key_insight}
                          </p>
                        )}
                        {idea.tags?.length > 0 && (
                          <div style={{ marginTop: 6, display: "flex", gap: 4, flexWrap: "wrap" }}>
                            {idea.tags.map((t) => (
                              <span key={t} style={{ fontSize: 10, color: "#555", padding: "1px 5px", border: "1px solid #222", borderRadius: 3 }}>
                                {t}
                              </span>
                            ))}
                          </div>
                        )}
                        {idea.platform && idea.platform !== "web" && idea.platform !== "undecided" && (
                          <p style={{ fontSize: 10, color: "#555", marginTop: 6 }}>
                            platform: {idea.platform}
                          </p>
                        )}
                        {idea.notes && (
                          <p style={{ fontSize: 11, color: "#666", marginTop: 6, lineHeight: 1.4, maxWidth: 500, fontStyle: "italic" }}>
                            {idea.notes}
                          </p>
                        )}
                      </div>
                    )}
                  </td>
                  <td style={{ padding: "10px 12px 10px 0", verticalAlign: "top" }}>
                    <StatusBadge status={idea.status} />
                  </td>
                  <td style={{ padding: "10px 8px 10px 0", verticalAlign: "top" }}>
                    <ScoreBar value={idea.impact_pct} color="#e88ec0" />
                  </td>
                  <td style={{ padding: "10px 8px 10px 0", verticalAlign: "top" }}>
                    <ScoreBar value={idea.business_pct} color="#e0a86e" />
                  </td>
                  <td style={{ padding: "10px 8px 10px 0", verticalAlign: "top" }}>
                    <ScoreBar value={idea.sustainability_pct} color="#6ee0a0" />
                  </td>
                  <td style={{ padding: "10px 8px 10px 0", fontSize: 12, verticalAlign: "top", whiteSpace: "nowrap" }}>
                    {VERDICT_ICONS[idea.verdict] || ""} {idea.verdict}
                  </td>
                  <td style={{ padding: "10px 0 10px 0", fontSize: 11, color: "#555", verticalAlign: "top", whiteSpace: "nowrap" }}>
                    {idea.date_updated}
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>

        {filtered.length === 0 && (
          <p style={{ textAlign: "center", padding: 32, color: "#555", fontSize: 13 }}>
            No ideas match this filter.
          </p>
        )}
      </div>

      {/* Summary footer */}
      <footer style={{ borderTop: "1px solid #111", padding: "16px 32px", display: "flex", gap: 24, flexWrap: "wrap" }}>
        {[
          { label: "Deployed", count: counts.deployed || 0 },
          { label: "Building", count: (counts.building || 0) + (counts["in-dev"] || 0) },
          { label: "Scouted", count: counts.scouted || 0 },
          { label: "Raw", count: counts.raw || 0 },
          { label: "Shelved", count: counts.shelved || 0 },
          { label: "Killed/Parked", count: (counts.killed || 0) + (counts.parked || 0) },
        ].map((s) => (
          <div key={s.label} style={{ fontSize: 11, color: "#555" }}>
            <span style={{ color: "#888", fontWeight: 600 }}>{s.count}</span>{" "}
            {s.label.toLowerCase()}
          </div>
        ))}
        <div style={{ flex: 1 }} />
        <div style={{ fontSize: 10, color: "#333" }}>
          vault v{vault.version}
        </div>
      </footer>
    </div>
  );
}
