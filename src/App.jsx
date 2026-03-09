import { useState, useMemo } from "react";

/*
  The Grove — A nature-themed portfolio of ideas.
  Each idea's maturity is depicted as a stage of plant growth.
  Receives project data as props from GroveRouter, which fetches vault.json.
*/

// ─── Nature Stage System ───
const STAGES = {
  raw:      { label: "Seed",      emoji: "🌰", color: "#8B7355", bg: "from-amber-950/20 to-stone-900/40", desc: "Buried potential" },
  scouted:  { label: "Sprout",    emoji: "🌱", color: "#6B8E23", bg: "from-lime-950/20 to-emerald-950/30", desc: "Evaluated & promising" },
  building: { label: "Sapling",   emoji: "🌿", color: "#2E8B57", bg: "from-emerald-950/20 to-green-950/30", desc: "Actively growing" },
  "in-dev": { label: "Young Tree",emoji: "🌳", color: "#228B22", bg: "from-green-950/20 to-emerald-950/30", desc: "Taking shape" },
  deployed: { label: "Flowering", emoji: "🌸", color: "#DB7093", bg: "from-pink-950/20 to-rose-950/30", desc: "In bloom" },
  shipped:  { label: "Bearing Fruit", emoji: "🍎", color: "#CD5C5C", bg: "from-red-950/20 to-orange-950/20", desc: "Mature & producing" },
  parked:   { label: "Dormant",   emoji: "🍂", color: "#B8860B", bg: "from-yellow-950/20 to-amber-950/30", desc: "Resting for now" },
  killed:   { label: "Returned to Soil", emoji: "🍃", color: "#696969", bg: "from-stone-900/30 to-zinc-900/30", desc: "Composted into wisdom" },
};

// ─── Score Ring Component ───
function ScoreRing({ value, label, size = 48 }) {
  if (value === null || value === undefined) return null;
  const radius = (size - 6) / 2;
  const circumference = 2 * Math.PI * radius;
  const offset = circumference * (1 - value / 100);
  const color = value >= 56 ? "#4ade80" : value >= 40 ? "#fbbf24" : "#f87171";

  return (
    <div className="flex flex-col items-center gap-1">
      <svg width={size} height={size} className="transform -rotate-90">
        <circle cx={size/2} cy={size/2} r={radius} fill="none" stroke="rgba(255,255,255,0.08)" strokeWidth="3" />
        <circle cx={size/2} cy={size/2} r={radius} fill="none" stroke={color} strokeWidth="3"
          strokeDasharray={circumference} strokeDashoffset={offset} strokeLinecap="round"
          style={{ transition: "stroke-dashoffset 1s ease-out" }} />
      </svg>
      <div className="absolute flex flex-col items-center justify-center" style={{ width: size, height: size }}>
        <span className="text-xs font-bold" style={{ color }}>{value}%</span>
      </div>
      <span className="text-xs text-stone-500 uppercase tracking-wider" style={{ fontSize: 9 }}>{label}</span>
    </div>
  );
}

// ─── Growth Indicator ───
function GrowthBar({ status }) {
  const stages = ["raw", "scouted", "building", "in-dev", "deployed", "shipped"];
  const activeIdx = stages.indexOf(status);
  const isSpecial = status === "parked" || status === "killed";

  if (isSpecial) return null;

  return (
    <div className="flex gap-1 items-center">
      {stages.map((s, i) => (
        <div key={s} className="flex items-center gap-1">
          <div
            className="rounded-full transition-all duration-500"
            style={{
              width: i <= activeIdx ? 8 : 5,
              height: i <= activeIdx ? 8 : 5,
              backgroundColor: i <= activeIdx ? STAGES[s].color : "rgba(255,255,255,0.1)",
              boxShadow: i === activeIdx ? `0 0 8px ${STAGES[s].color}40` : "none",
            }}
          />
          {i < stages.length - 1 && (
            <div className="h-px w-2" style={{ backgroundColor: i < activeIdx ? "rgba(255,255,255,0.15)" : "rgba(255,255,255,0.05)" }} />
          )}
        </div>
      ))}
    </div>
  );
}

// ─── Project Card ───
function ProjectCard({ project, index }) {
  const stage = STAGES[project.status] || STAGES.raw;
  const [hovered, setHovered] = useState(false);

  return (
    <div
      className={`relative rounded-2xl border border-white/5 overflow-hidden transition-all duration-500 ${hovered ? "border-white/10 scale-[1.01]" : ""}`}
      style={{
        animationDelay: `${index * 120}ms`,
        animation: "growIn 0.7s ease-out both",
      }}
      onMouseEnter={() => setHovered(true)}
      onMouseLeave={() => setHovered(false)}
    >
      {/* Gradient background based on stage */}
      <div className={`absolute inset-0 bg-gradient-to-br ${stage.bg}`} />

      {/* Texture overlay */}
      <div className="absolute inset-0 opacity-30"
        style={{
          backgroundImage: `radial-gradient(circle at 20% 80%, rgba(34,139,34,0.05) 0%, transparent 50%), radial-gradient(circle at 80% 20%, rgba(139,115,85,0.05) 0%, transparent 50%)`,
        }}
      />

      <div className="relative p-6 md:p-8">
        {/* Header row: stage + growth */}
        <div className="flex items-center justify-between mb-4">
          <div className="flex items-center gap-2">
            <span className="text-2xl">{stage.emoji}</span>
            <div>
              <span className="text-xs uppercase tracking-widest font-medium" style={{ color: stage.color }}>{stage.label}</span>
              <div className="text-xs text-stone-600 mt-0.5 italic">{stage.desc}</div>
            </div>
          </div>
          <GrowthBar status={project.status} />
        </div>

        {/* Title */}
        <h2 style={{ fontFamily: "'Cormorant Garamond', serif" }}
          className="text-2xl md:text-3xl font-bold text-stone-100 mb-2 leading-tight">
          {project.title}
        </h2>

        {/* One-liner */}
        <p className="text-stone-400 text-sm leading-relaxed mb-4">
          {project.hero_description || project.one_liner}
        </p>

        {/* Tags */}
        <div className="flex flex-wrap gap-2 mb-5">
          {project.tags.map(tag => (
            <span key={tag} className="text-xs px-2.5 py-1 rounded-full bg-white/5 text-stone-500 border border-white/5">
              {tag}
            </span>
          ))}
        </div>

        {/* Bottom row: scores + action */}
        <div className="flex items-end justify-between">
          <div className="flex gap-4">
            {project.impact_score !== null && (
              <div className="relative">
                <ScoreRing value={project.impact_score} label="Impact" />
              </div>
            )}
            {project.business_score !== null && (
              <div className="relative">
                <ScoreRing value={project.business_score} label="Business" />
              </div>
            )}
            {project.impact_score === null && (
              <div className="text-xs text-stone-600 italic py-2">Awaiting evaluation</div>
            )}
          </div>

          {project.deploy_url && (
            <a href={project.deploy_url} target="_blank" rel="noopener noreferrer"
              className="group flex items-center gap-2 px-4 py-2.5 rounded-xl text-sm font-medium transition-all duration-300"
              style={{
                backgroundColor: `${stage.color}20`,
                color: stage.color,
                border: `1px solid ${stage.color}30`,
              }}
              onMouseEnter={e => { e.currentTarget.style.backgroundColor = `${stage.color}35`; }}
              onMouseLeave={e => { e.currentTarget.style.backgroundColor = `${stage.color}20`; }}
            >
              Visit
              <span className="text-xs opacity-60 group-hover:translate-x-0.5 transition-transform">→</span>
            </a>
          )}
        </div>
      </div>
    </div>
  );
}

// ─── Main App ───
export default function TheGrove({ projects = [] }) {
  const [filter, setFilter] = useState("all");
  const [sortBy, setSortBy] = useState("status");

  const stageOrder = ["shipped", "deployed", "in-dev", "building", "scouted", "raw", "parked", "killed"];

  const filtered = useMemo(() => {
    let list = [...projects];
    if (filter === "live") list = list.filter(p => p.deploy_url);
    else if (filter === "growing") list = list.filter(p => ["building", "in-dev", "scouted"].includes(p.status));
    else if (filter === "seeds") list = list.filter(p => p.status === "raw");

    list.sort((a, b) => {
      if (sortBy === "status") return stageOrder.indexOf(a.status) - stageOrder.indexOf(b.status);
      if (sortBy === "impact") return (b.impact_score || 0) - (a.impact_score || 0);
      return 0;
    });
    return list;
  }, [projects, filter, sortBy]);

  // Count by category
  const counts = useMemo(() => ({
    all: projects.length,
    live: projects.filter(p => p.deploy_url).length,
    growing: projects.filter(p => ["building", "in-dev", "scouted"].includes(p.status)).length,
    seeds: projects.filter(p => p.status === "raw").length,
  }), [projects]);


  return (
    <div className="min-h-screen bg-gradient-to-b from-stone-950 via-stone-950 to-emerald-950/20 text-stone-200">
      

      {/* Subtle organic background textures */}
      <div className="fixed inset-0 pointer-events-none overflow-hidden">
        <div className="absolute top-0 left-0 w-full h-full opacity-20"
          style={{
            background: `
              radial-gradient(ellipse at 10% 20%, rgba(34,139,34,0.04) 0%, transparent 60%),
              radial-gradient(ellipse at 90% 80%, rgba(139,115,85,0.03) 0%, transparent 60%),
              radial-gradient(ellipse at 50% 50%, rgba(46,139,87,0.02) 0%, transparent 70%)
            `
          }}
        />
        {/* Floating particles */}
        {[...Array(6)].map((_, i) => (
          <div key={i} className="absolute rounded-full opacity-10"
            style={{
              width: 3 + i * 2,
              height: 3 + i * 2,
              backgroundColor: i % 2 === 0 ? "#228B22" : "#8B7355",
              left: `${15 + i * 15}%`,
              top: `${10 + i * 12}%`,
              animation: `drift ${8 + i * 2}s ease-in-out infinite`,
              animationDelay: `${i * 1.5}s`,
            }}
          />
        ))}
      </div>

      {/* Header */}
      <header className="relative pt-16 pb-12 md:pt-24 md:pb-16 px-6">
        <div className="max-w-3xl mx-auto text-center">
          <div className="text-4xl mb-4" style={{ animation: "sway 4s ease-in-out infinite" }}>🌿</div>
          <h1 style={{ fontFamily: "'Cormorant Garamond', serif" }}
            className="text-4xl md:text-6xl font-bold text-stone-100 mb-3 tracking-tight">
            The Grove
          </h1>
          <p className="text-stone-500 text-base md:text-lg max-w-md mx-auto leading-relaxed">
            Ideas at every stage of growth — from seeds waiting in the soil
            to trees bearing fruit.
          </p>
        </div>
      </header>

      {/* Filters */}
      <div className="relative px-6 pb-8">
        <div className="max-w-3xl mx-auto flex flex-wrap gap-2 justify-center">
          {[
            ["all", "All", counts.all],
            ["live", "In Bloom", counts.live],
            ["growing", "Growing", counts.growing],
            ["seeds", "Seeds", counts.seeds],
          ].map(([key, label, count]) => (
            <button key={key} onClick={() => setFilter(key)}
              className={`px-4 py-2 rounded-full text-xs font-medium transition-all duration-300 ${
                filter === key
                  ? "bg-emerald-900/40 text-emerald-400 border border-emerald-800/50"
                  : "bg-white/3 text-stone-500 border border-white/5 hover:border-white/10 hover:text-stone-400"
              }`}>
              {label}
              <span className="ml-1.5 opacity-50">{count}</span>
            </button>
          ))}

          <div className="w-px h-6 bg-white/5 self-center mx-1" />

          <button onClick={() => setSortBy(s => s === "status" ? "impact" : "status")}
            className="px-3 py-2 rounded-full text-xs text-stone-600 border border-white/5 hover:text-stone-400 transition-colors">
            Sort: {sortBy === "status" ? "Growth Stage" : "Impact"}
          </button>
        </div>
      </div>

      {/* Project Grid */}
      <main className="relative px-6 pb-24">
        <div className="max-w-3xl mx-auto flex flex-col gap-5">
          {filtered.map((project, i) => (
            <ProjectCard key={project.title} project={project} index={i} />
          ))}
          {filtered.length === 0 && (
            <div className="text-center py-16 text-stone-600">
              <div className="text-3xl mb-2">🌑</div>
              Nothing growing here yet.
            </div>
          )}
        </div>
      </main>

      {/* Footer */}
      <footer className="relative border-t border-white/5 py-8 px-6">
        <div className="max-w-3xl mx-auto flex items-center justify-between">
          <div className="text-xs text-stone-700">
            {projects.length} idea{projects.length !== 1 ? "s" : ""} in the grove
          </div>
          <div className="flex gap-3 text-xs text-stone-700">
            <span>🌰 Seed</span>
            <span>🌱 Sprout</span>
            <span>🌿 Sapling</span>
            <span>🌳 Tree</span>
            <span>🌸 Flower</span>
            <span>🍎 Fruit</span>
          </div>
        </div>
      </footer>
    </div>
  );
}
