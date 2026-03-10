import { useState, useEffect, useRef, useMemo } from "react";

/*
  The Grove — First-person walk through your idea garden.
  
  Based on hand-drawn sketch: path converges to vanishing point ~40% from top.
  Closest plants are HUGE (filling 1/3+ of screen). Farthest are tiny specks.
  Plants sit on the ground plane. Signs sit between plant and path.
  Hills on the horizon add depth.
*/

// Project data comes from vault.json via GroveRouter props.

const STAGES = {
  raw:      { label: "Seed",          color: "#8B7355", heightScale: 0.2 },
  scouted:  { label: "Sprout",        color: "#6B8E23", heightScale: 0.35 },
  building: { label: "Sapling",       color: "#2E8B57", heightScale: 0.55 },
  "in-dev": { label: "Young Tree",    color: "#228B22", heightScale: 0.75 },
  deployed: { label: "Flowering",     color: "#C06078", heightScale: 0.9 },
  shipped:  { label: "Bearing Fruit", color: "#CD5C5C", heightScale: 1.0 },
  parked:   { label: "Dormant",       color: "#B8860B", heightScale: 0.6 },
  killed:   { label: "Composted",     color: "#696969", heightScale: 0.15 },
};

// ─── SVG Plants ───
function effectiveScores(impact, business, status) {
  const minimums = {
    deployed:  { impact: 65, business: 50 },
    shipped:   { impact: 75, business: 65 },
  };
  const min = minimums[status];
  if (!min) return { impact, business };
  return {
    impact:  impact  != null ? impact  : min.impact,
    business: business != null ? business : min.business,
  };
}

function computeScoreRanges(projects) {
  const impacts = [];
  const businesses = [];
  projects.forEach(p => {
    const eff = effectiveScores(p.impact_score, p.business_score, p.status);
    if (eff.impact != null) impacts.push(eff.impact);
    if (eff.business != null) businesses.push(eff.business);
  });
  return {
    impact:  impacts.length  ? { min: Math.min(...impacts),  max: Math.max(...impacts)  } : null,
    business: businesses.length ? { min: Math.min(...businesses), max: Math.max(...businesses) } : null,
  };
}

function scoreToCount(score, maxSlots, range) {
  if (score == null || score === 0) return 0;
  if (!range || range.max === range.min) return Math.ceil(maxSlots / 2);
  const t = Math.max(0, Math.min(1, (score - range.min) / (range.max - range.min)));
  return Math.max(1, Math.round(1 + t * (maxSlots - 1)));
}

function Flowers({ positions, count, scale = 1 }) {
  if (count === 0) return null;
  const petalR = 2.4 * scale;
  const spread = 2.8 * scale;
  const centerR = 1.3 * scale;
  return positions.slice(0, count).map(([x, y], i) => (
    <g key={`f${i}`}>
      {[0, 72, 144, 216, 288].map((deg, j) => {
        const rad = deg * Math.PI / 180;
        const px = x + Math.cos(rad) * spread;
        const py = y + Math.sin(rad) * spread;
        return <ellipse key={j} cx={px} cy={py} rx={petalR} ry={petalR * 0.6}
          fill="#F4A0B8" opacity="0.85"
          transform={`rotate(${deg} ${px} ${py})`} />;
      })}
      <circle cx={x} cy={y} r={centerR} fill="#FFD700" opacity="0.9" />
    </g>
  ));
}

function Fruit({ positions, count, scale = 1 }) {
  if (count === 0) return null;
  const r = 4.5 * scale;
  const hr = 1.5 * scale;
  const stemH = 3 * scale;
  return positions.slice(0, count).map(([x, y], i) => (
    <g key={`r${i}`}>
      <line x1={x} y1={y - r} x2={x + stemH * 0.3} y2={y - r - stemH} stroke="#5C4033" strokeWidth={Math.max(0.4, 0.8 * scale)} strokeLinecap="round" />
      <circle cx={x} cy={y} r={r} fill="#CD5C5C" opacity="0.9" />
      <circle cx={x - r * 0.25} cy={y - r * 0.25} r={hr} fill="#E88080" opacity="0.5" />
    </g>
  ));
}

function SeedPlant() {
  return (
    <svg viewBox="0 0 60 30" width="100%" height="100%" preserveAspectRatio="xMidYMax meet">
      <ellipse cx="30" cy="26" rx="20" ry="5" fill="#A0926B" />
      <ellipse cx="30" cy="22" rx="5" ry="4" fill="#6B4E2E" />
      <path d="M30 18 Q32 13 30 9" stroke="#8B7355" strokeWidth="1.2" fill="none" opacity="0.6" />
      <path d="M26 12 Q24 7 27 5 Q30 3 33 5 Q36 7 34 12 Q30 10 26 12Z" fill="#5C8A1E" opacity="0.8" />
      <path d="M27 11 Q26 6 30 4 Q34 6 33 11 Q30 9 27 11Z" fill="#7BA428" opacity="0.75" />
      <path d="M28 10 Q29 6 30 5 Q31 6 32 10 Q30 8 28 10Z" fill="#90C040" opacity="0.65" />
    </svg>
  );
}

function SproutPlant({ impact, business, scoreRanges }) {
  const flowerSpots = [[32, 14], [48, 10]];
  const fruitSpots = [[40, 6]];
  return (
    <svg viewBox="0 0 80 55" width="100%" height="100%" preserveAspectRatio="xMidYMax meet">
      <path d="M40 55 Q39 37 40 18" stroke="#4A7A2E" strokeWidth="3" fill="none" strokeLinecap="round" />
      <path d="M22 26 Q18 18 22 12 Q26 6 32 4 Q36 2 40 3 Q44 2 48 4 Q54 6 58 12 Q62 18 58 26 Q54 30 48 32 Q44 34 40 35 Q36 34 32 32 Q26 30 22 26Z" fill="#3A6E1A" opacity="0.9" />
      <path d="M25 24 Q22 16 26 10 Q32 5 40 4 Q48 5 54 10 Q58 16 55 24 Q50 28 44 30 Q40 31 36 30 Q30 28 25 24Z" fill="#4A7A2E" opacity="0.85" />
      <path d="M28 22 Q26 14 30 8 Q36 4 40 5 Q44 4 50 8 Q54 14 52 22 Q48 26 42 28 Q38 28 32 26 Q28 24 28 22Z" fill="#6B8E23" opacity="0.8" />
      <path d="M32 18 Q30 12 34 8 Q38 6 42 6 Q46 8 48 12 Q48 18 44 22 Q40 24 36 22 Q32 20 32 18Z" fill="#7BA428" opacity="0.65" />
      <path d="M36 14 Q36 10 40 8 Q44 10 44 14 Q42 18 40 18 Q38 18 36 14Z" fill="#8CBC38" opacity="0.5" />
      <Flowers positions={flowerSpots} count={scoreToCount(impact, 2, scoreRanges.impact)} scale={0.25} />
      <Fruit positions={fruitSpots} count={scoreToCount(business, 1, scoreRanges.business)} scale={0.25} />
    </svg>
  );
}

function SaplingPlant({ impact, business, scoreRanges }) {
  const flowerSpots = [[32, 30], [58, 22], [46, 14]];
  const fruitSpots = [[40, 20], [65, 32]];
  return (
    <svg viewBox="0 0 100 100" width="100%" height="100%" preserveAspectRatio="xMidYMax meet">
      <path d="M50 100 Q49 75 50 38" stroke="#6B4E2E" strokeWidth="5" fill="none" strokeLinecap="round" />
      <path d="M16 54 Q10 44 14 34 Q18 24 24 18 Q30 12 38 8 Q44 5 50 6 Q56 5 62 8 Q70 12 76 18 Q82 24 84 34 Q86 44 80 54 Q76 60 68 58 Q60 56 50 58 Q40 56 32 58 Q24 60 16 54Z" fill="#1A5E1A" opacity="0.9" />
      <path d="M20 50 Q14 40 18 30 Q24 20 32 14 Q40 8 50 8 Q60 8 68 14 Q76 20 80 30 Q84 40 78 50 Q72 55 62 52 Q52 50 42 52 Q32 55 20 50Z" fill="#228B22" opacity="0.85" />
      <path d="M26 42 Q22 32 28 22 Q34 14 42 10 Q50 8 58 10 Q66 14 72 22 Q76 32 72 42 Q66 48 56 46 Q48 44 40 46 Q32 48 26 42Z" fill="#2E9B2E" opacity="0.7" />
      <path d="M34 32 Q30 24 36 16 Q44 12 50 12 Q56 12 62 16 Q68 24 64 32 Q58 38 50 36 Q42 38 34 32Z" fill="#3AAA3A" opacity="0.55" />
      <path d="M42 24 Q40 18 46 14 Q52 14 56 18 Q56 24 52 28 Q46 28 42 24Z" fill="#48B848" opacity="0.4" />
      <Flowers positions={flowerSpots} count={scoreToCount(impact, 3, scoreRanges.impact)} scale={0.25} />
      <Fruit positions={fruitSpots} count={scoreToCount(business, 2, scoreRanges.business)} scale={0.25} />
    </svg>
  );
}

function YoungTreePlant({ impact, business, scoreRanges }) {
  const flowerSpots = [[36, 50], [78, 38], [55, 22], [94, 48]];
  const fruitSpots = [[48, 34], [84, 46], [64, 18]];
  return (
    <svg viewBox="0 0 130 130" width="100%" height="100%" preserveAspectRatio="xMidYMax meet">
      <path d="M65 130 Q63 95 65 40" stroke="#6B4E2E" strokeWidth="6" fill="none" strokeLinecap="round" />
      <path d="M18 72 Q8 58 12 42 Q16 28 26 18 Q36 10 48 6 Q58 3 66 4 Q74 3 84 6 Q96 10 106 18 Q116 28 118 42 Q120 58 112 72 Q106 78 96 74 Q86 70 76 72 Q66 74 56 72 Q46 70 36 74 Q26 78 18 72Z" fill="#16581A" opacity="0.9" />
      <path d="M24 66 Q14 52 18 36 Q24 22 36 14 Q48 8 60 6 Q72 6 84 10 Q96 16 106 28 Q114 42 110 58 Q106 68 96 64 Q84 60 72 62 Q60 64 48 62 Q36 64 24 66Z" fill="#1E6B1E" opacity="0.85" />
      <path d="M30 58 Q22 44 26 30 Q34 18 46 12 Q58 8 68 8 Q80 10 92 18 Q102 28 104 44 Q104 58 96 60 Q86 56 74 56 Q62 58 50 56 Q38 58 30 58Z" fill="#228B22" opacity="0.75" />
      <path d="M38 48 Q32 36 38 24 Q46 16 56 12 Q66 10 76 14 Q86 22 90 34 Q92 46 86 50 Q76 48 66 46 Q56 48 46 48 Q40 48 38 48Z" fill="#2E9B2E" opacity="0.6" />
      <path d="M48 36 Q44 26 50 18 Q58 14 68 14 Q78 18 82 26 Q84 36 78 40 Q68 38 60 36 Q52 38 48 36Z" fill="#3AAA3A" opacity="0.45" />
      <path d="M56 28 Q54 20 62 16 Q70 16 74 22 Q76 28 70 32 Q64 30 56 28Z" fill="#48B848" opacity="0.35" />
      <Flowers positions={flowerSpots} count={scoreToCount(impact, 4, scoreRanges.impact)} />
      <Fruit positions={fruitSpots} count={scoreToCount(business, 3, scoreRanges.business)} />
    </svg>
  );
}

function FloweringPlant({ impact, business, scoreRanges }) {
  const flowerSpots = [[40, 72], [65, 28], [92, 24], [116, 52], [54, 42], [104, 68]];
  const fruitSpots = [[50, 50], [100, 58], [76, 26], [60, 68]];
  return (
    <svg viewBox="0 0 155 155" width="100%" height="100%" preserveAspectRatio="xMidYMax meet">
      <path d="M78 155 Q75 108 78 48" stroke="#6B4E2E" strokeWidth="7" fill="none" strokeLinecap="round" />
      <path d="M76 115 Q62 105 52 97" stroke="#7B5E3E" strokeWidth="3" fill="none" />
      <path d="M78 108 Q92 98 102 92" stroke="#7B5E3E" strokeWidth="2.5" fill="none" />
      <path d="M18 88 Q4 68 10 46 Q18 26 32 14 Q46 4 60 2 Q72 0 82 2 Q96 4 110 14 Q124 26 132 46 Q138 68 124 88 Q116 94 106 88 Q94 82 82 84 Q70 82 58 84 Q46 88 36 90 Q26 94 18 88Z" fill="#14521A" opacity="0.9" />
      <path d="M24 82 Q10 62 16 40 Q26 22 40 12 Q54 4 68 2 Q82 2 96 8 Q112 18 122 36 Q130 56 122 76 Q114 86 102 80 Q90 74 78 76 Q66 74 54 76 Q42 80 30 84 Q24 84 24 82Z" fill="#1E6B1E" opacity="0.85" />
      <path d="M32 72 Q20 52 26 34 Q36 18 50 10 Q64 4 78 4 Q92 6 106 16 Q118 30 122 48 Q124 66 116 72 Q104 68 92 66 Q78 68 66 66 Q52 68 40 72 Q34 72 32 72Z" fill="#228B22" opacity="0.75" />
      <path d="M42 60 Q32 42 38 26 Q50 14 66 8 Q80 6 94 14 Q108 26 112 42 Q114 58 106 62 Q94 58 82 56 Q68 58 56 58 Q46 60 42 60Z" fill="#2A9A2A" opacity="0.6" />
      <path d="M52 48 Q44 34 52 22 Q62 14 76 10 Q90 14 100 24 Q106 36 104 48 Q96 50 84 48 Q72 46 62 48 Q54 50 52 48Z" fill="#34AA34" opacity="0.45" />
      <path d="M62 38 Q58 28 66 18 Q76 14 86 18 Q94 28 92 38 Q84 40 76 38 Q68 38 62 38Z" fill="#40B840" opacity="0.35" />
      <path d="M72 30 Q70 22 78 18 Q86 22 84 30 Q80 32 72 30Z" fill="#4CC84C" opacity="0.25" />
      <Flowers positions={flowerSpots} count={scoreToCount(impact, 6, scoreRanges.impact)} />
      <Fruit positions={fruitSpots} count={scoreToCount(business, 4, scoreRanges.business)} />
    </svg>
  );
}

function FruitTreePlant({ impact, business, scoreRanges }) {
  const flowerSpots = [[38, 76], [66, 26], [108, 32], [130, 56], [52, 44], [116, 70]];
  const fruitSpots = [[46, 80], [72, 30], [100, 26], [126, 52], [56, 48], [112, 68]];
  return (
    <svg viewBox="0 0 165 165" width="100%" height="100%" preserveAspectRatio="xMidYMax meet">
      <path d="M82 165 Q79 115 82 46" stroke="#5C4033" strokeWidth="8" fill="none" strokeLinecap="round" />
      <path d="M80 123 Q64 111 52 102" stroke="#6B4E2E" strokeWidth="3.5" fill="none" />
      <path d="M82 116 Q96 106 108 98" stroke="#6B4E2E" strokeWidth="3" fill="none" />
      <path d="M14 94 Q-2 70 6 44 Q16 22 32 10 Q48 0 64 -2 Q78 -4 88 -2 Q104 0 120 10 Q136 22 146 44 Q154 70 140 94 Q130 102 118 94 Q104 86 90 88 Q76 86 62 88 Q48 92 36 96 Q24 102 14 94Z" fill="#123E14" opacity="0.9" />
      <path d="M20 88 Q4 64 12 40 Q24 18 42 8 Q58 0 72 -2 Q86 -2 100 2 Q118 10 132 28 Q142 48 142 70 Q140 88 128 86 Q114 80 100 80 Q86 78 72 80 Q58 82 44 86 Q30 90 20 88Z" fill="#1A5A1A" opacity="0.88" />
      <path d="M28 80 Q14 58 20 36 Q32 16 50 6 Q66 0 80 0 Q96 2 112 12 Q126 26 134 46 Q138 66 130 80 Q118 76 104 74 Q88 72 74 74 Q60 76 46 80 Q34 82 28 80Z" fill="#1E6B1E" opacity="0.82" />
      <path d="M36 72 Q22 52 28 32 Q40 14 56 6 Q72 0 86 2 Q102 6 116 18 Q128 34 132 52 Q134 70 124 72 Q112 68 98 66 Q82 64 68 66 Q54 70 42 72 Q38 72 36 72Z" fill="#228B22" opacity="0.72" />
      <path d="M46 62 Q34 44 40 26 Q52 12 68 6 Q84 4 100 10 Q114 22 120 40 Q122 58 114 62 Q102 58 88 56 Q74 54 62 58 Q50 62 46 62Z" fill="#2A9A2A" opacity="0.58" />
      <path d="M56 50 Q46 34 54 20 Q66 10 82 8 Q98 12 108 24 Q114 38 110 50 Q100 48 88 46 Q76 44 66 48 Q58 50 56 50Z" fill="#34AA34" opacity="0.42" />
      <path d="M66 40 Q60 28 68 18 Q80 12 92 16 Q102 26 98 38 Q90 40 80 38 Q70 38 66 40Z" fill="#40B840" opacity="0.32" />
      <path d="M76 32 Q74 22 82 16 Q92 20 90 30 Q84 34 76 32Z" fill="#4CC84C" opacity="0.22" />
      <Flowers positions={flowerSpots} count={scoreToCount(impact, 6, scoreRanges.impact)} />
      <Fruit positions={fruitSpots} count={scoreToCount(business, 6, scoreRanges.business)} />
    </svg>
  );
}

function DormantPlant() {
  return (
    <svg viewBox="0 0 110 100" width="100%" height="100%" preserveAspectRatio="xMidYMax meet">
      <path d="M55 100 Q53 70 55 30" stroke="#8B7355" strokeWidth="5" fill="none" strokeLinecap="round" />
      <path d="M54 72 Q40 61 32 53" stroke="#8B7355" strokeWidth="2.5" fill="none" />
      <path d="M55 55 Q68 45 76 39" stroke="#8B7355" strokeWidth="2" fill="none" />
      <path d="M54 43 Q44 35 38 27" stroke="#8B7355" strokeWidth="1.5" fill="none" />
      <path d="M28 54 Q24 48 28 44 Q34 46 32 52 Q30 54 28 54Z" fill="#B8960B" opacity="0.35" />
      <path d="M76 38 Q80 32 78 28 Q74 30 72 36 Q74 38 76 38Z" fill="#A88B10" opacity="0.3" />
      <path d="M36 28 Q32 22 36 20 Q40 22 38 26 Q36 28 36 28Z" fill="#B8960B" opacity="0.25" />
    </svg>
  );
}

function StumpPlant() {
  return (
    <svg viewBox="0 0 50 28" width="100%" height="100%" preserveAspectRatio="xMidYMax meet">
      <rect x="12" y="8" width="26" height="20" rx="3" fill="#696969" />
      <ellipse cx="25" cy="8" rx="14" ry="5" fill="#7A7A7A" />
      <ellipse cx="25" cy="8" rx="10" ry="3.5" fill="none" stroke="#5A5A5A" strokeWidth="0.7" />
      <ellipse cx="25" cy="8" rx="5" ry="2" fill="none" stroke="#5A5A5A" strokeWidth="0.5" />
    </svg>
  );
}

function PlantForStatus({ status, impact, business, scoreRanges }) {
  const eff = effectiveScores(impact, business, status);
  const props = { impact: eff.impact, business: eff.business, scoreRanges };
  switch (status) {
    case "raw": return <SeedPlant />;
    case "scouted": return <SproutPlant {...props} />;
    case "building": return <SaplingPlant {...props} />;
    case "in-dev": return <YoungTreePlant {...props} />;
    case "deployed": return <FloweringPlant {...props} />;
    case "shipped": return <FruitTreePlant {...props} />;
    case "parked": return <DormantPlant />;
    case "killed": return <StumpPlant />;
    default: return <SeedPlant />;
  }
}

// ─── Score Vis ───
function ScoreVis({ impact, business }) {
  if (!impact && !business) return null;
  return (
    <div style={{ display: "flex", gap: 12, padding: "4px 10px", background: "rgba(255,255,255,0.65)", borderRadius: 8, backdropFilter: "blur(4px)", border: "1px solid rgba(139,115,85,0.2)" }}>
      {impact != null && <div style={{ display: "flex", alignItems: "center", gap: 4 }}>
        <svg width="14" height="14" viewBox="0 0 14 14"><path d="M7 2 L7 12" stroke="#228B22" strokeWidth="2" strokeLinecap="round" /><path d="M7 4 Q4 6 3 8" stroke="#228B22" strokeWidth="1.5" fill="none" /><path d="M7 6 Q10 8 11 10" stroke="#228B22" strokeWidth="1.5" fill="none" /></svg>
        <span style={{ fontSize: 11, color: "#4A5E3A", fontWeight: 600 }}>{impact}%</span>
        <span style={{ fontSize: 9, color: "#7A8A6A" }}>impact</span>
      </div>}
      {business != null && <div style={{ display: "flex", alignItems: "center", gap: 4 }}>
        <svg width="14" height="14" viewBox="0 0 14 14"><circle cx="7" cy="5" r="3.5" fill="none" stroke="#6B8E23" strokeWidth="1.5" /><path d="M7 8.5 L7 12" stroke="#6B8E23" strokeWidth="1.5" strokeLinecap="round" /></svg>
        <span style={{ fontSize: 11, color: "#5A6A3A", fontWeight: 600 }}>{business}%</span>
        <span style={{ fontSize: 9, color: "#7A8A6A" }}>business</span>
      </div>}
    </div>
  );
}

// ─── Detail Modal ───
function DetailModal({ project, onClose }) {
  const stage = STAGES[project.status] || STAGES.raw;
  return (
    <div onClick={onClose} style={{ position: "fixed", inset: 0, zIndex: 50, display: "flex", alignItems: "center", justifyContent: "center", padding: "16px 12px", background: "rgba(0,0,0,0.3)", backdropFilter: "blur(6px)" }}>
      <div onClick={e => e.stopPropagation()} style={{ width: "100%", maxWidth: 400, maxHeight: "85vh", overflowY: "auto", background: "linear-gradient(180deg, #FDFCF8 0%, #F5F0E8 100%)", borderRadius: 16, border: "1px solid #D2C8B8", boxShadow: "0 20px 60px rgba(0,0,0,0.2)", overflow: "hidden" }}>
        <div style={{ display: "flex", justifyContent: "center", paddingTop: 24, paddingBottom: 8, background: "linear-gradient(180deg, #E8F0E0 0%, #FDFCF8 100%)" }}>
          <div style={{ width: 120, height: 120 }}>
            <PlantForStatus status={project.status} impact={project.impact_score} business={project.business_score} scoreRanges={{ impact: null, business: null }} />
          </div>
        </div>
        <div style={{ padding: "0 24px 24px" }}>
          <div style={{ display: "flex", justifyContent: "center", marginBottom: 12 }}>
            <span style={{ fontSize: 10, color: stage.color, textTransform: "uppercase", letterSpacing: 2, fontWeight: 700, background: `${stage.color}15`, padding: "3px 12px", borderRadius: 20, border: `1px solid ${stage.color}30` }}>{stage.label}</span>
          </div>
          <h2 style={{ fontFamily: "'Crimson Text', Georgia, serif", fontSize: 26, fontWeight: 700, color: "#2C1810", textAlign: "center", marginBottom: 8, lineHeight: 1.2 }}>{project.title}</h2>
          <p style={{ fontSize: 14, color: "#5C4A3A", lineHeight: 1.6, textAlign: "center", marginBottom: 16 }}>{project.hero_description || project.one_liner}</p>
          <div style={{ display: "flex", justifyContent: "center", marginBottom: 16 }}>
            <ScoreVis impact={project.impact_score} business={project.business_score} />
          </div>
          <div style={{ display: "flex", flexWrap: "wrap", justifyContent: "center", gap: 6, marginBottom: 20 }}>
            {(project.tags || []).map(tag => <span key={tag} style={{ fontSize: 10, padding: "2px 10px", borderRadius: 12, background: "#EDE8DF", color: "#7A6A5A", border: "1px solid #D8D0C4" }}>{tag}</span>)}
          </div>
          <div style={{ display: "flex", justifyContent: "center", gap: 12 }}>
            {project.deploy_url && <a href={project.deploy_url} target="_blank" rel="noopener noreferrer" style={{ fontSize: 13, fontWeight: 600, padding: "8px 24px", borderRadius: 10, background: stage.color, color: "white", textDecoration: "none" }}>Visit →</a>}
            <button onClick={onClose} style={{ fontSize: 13, padding: "8px 20px", borderRadius: 10, background: "transparent", color: "#8A7A6A", border: "1px solid #D2C8B8", cursor: "pointer" }}>Close</button>
          </div>
        </div>
      </div>
    </div>
  );
}

// ─── Perspective Projection ───
const VP_Y = 0.50;
const VP_X = 0.50;

function perspectiveProject(distanceAhead, side, viewW, viewH) {
  if (distanceAhead > 1.05 || distanceAhead < -0.15) {
    return { x: 0, y: 0, scale: 0, opacity: 0, visible: false, plantSize: 0 };
  }
  const d = Math.max(0.005, distanceAhead);
  const isPortrait = viewH > viewW;
  const perspScale = 1 / (d * 2.2 + 0.08);
  const dRef = 0.12;
  const yDisplacement = Math.min(1, ((1 / d) - 1) / ((1 / dRef) - 1));
  const y = (VP_Y + (1.0 - VP_Y) * yDisplacement) * viewH;
  const spreadFactor = isPortrait ? 0.28 : 0.36;
  const sideSign = side === "left" ? -1 : 1;
  const xSpread = sideSign * Math.pow(1 - d, 1.2) * viewW * spreadFactor;
  const x = VP_X * viewW + xSpread;
  const maxPlant = isPortrait ? viewH * 1.8 : viewH * 2.0;
  const plantSize = Math.max(5, Math.min(maxPlant, perspScale * (isPortrait ? 180 : 250)));
  let opacity = 1;
  if (distanceAhead > 0.88) opacity = Math.max(0, (1.05 - distanceAhead) / 0.17);
  if (distanceAhead < 0.02) opacity = Math.max(0, distanceAhead / 0.02);
  const blur = d > 0.7 ? (d - 0.7) * 5 : 0;
  return { x, y, scale: perspScale, opacity, plantSize, blur, visible: opacity > 0.01, isPortrait };
}

// ─── Main App ───
export default function TheGrove({ projects = [] }) {
  const [selected, setSelected] = useState(null);
  const scoreRanges = useMemo(() => computeScoreRanges(projects), [projects]);
  const [walkPos, setWalkPos] = useState(0);
  const [viewSize, setViewSize] = useState({ w: 800, h: 600 });
  const containerRef = useRef(null);

  const totalItems = projects.length || 0;
  const SPACING = 0.20;
  const LOOP_LEN = totalItems * SPACING;

  useEffect(() => {
    const update = () => setViewSize({ w: window.innerWidth, h: window.innerHeight });
    update();
    window.addEventListener("resize", update);
    return () => window.removeEventListener("resize", update);
  }, []);

  useEffect(() => {
    const el = containerRef.current;
    if (!el) return;
    const onWheel = (e) => { e.preventDefault(); setWalkPos(prev => prev + e.deltaY * 0.0006); };
    let lastY = 0;
    const onTouchStart = (e) => { lastY = e.touches[0].clientY; };
    const onTouchMove = (e) => { e.preventDefault(); const dy = lastY - e.touches[0].clientY; lastY = e.touches[0].clientY; setWalkPos(prev => prev + dy * 0.002); };
    el.addEventListener("wheel", onWheel, { passive: false });
    el.addEventListener("touchstart", onTouchStart, { passive: true });
    el.addEventListener("touchmove", onTouchMove, { passive: false });
    return () => { el.removeEventListener("wheel", onWheel); el.removeEventListener("touchstart", onTouchStart); el.removeEventListener("touchmove", onTouchMove); };
  }, []);

  const visiblePlants = useMemo(() => {
    if (totalItems === 0) return [];
    const result = [];
    const { w, h } = viewSize;
    for (let i = 0; i < totalItems; i++) {
      const side = i % 2 === 0 ? "left" : "right";
      const pathPos = i * SPACING;
      let dist = pathPos - walkPos;
      dist = ((dist % LOOP_LEN) + LOOP_LEN) % LOOP_LEN;
      const proj = perspectiveProject(dist, side, w, h);
      if (!proj.visible) continue;
      result.push({ project: projects[i], index: i, side, distanceAhead: dist, ...proj });
    }
    result.sort((a, b) => b.distanceAhead - a.distanceAhead);
    return result;
  }, [walkPos, viewSize, projects, totalItems, LOOP_LEN]);

  if (totalItems === 0) {
    return (
      <div style={{ width: "100vw", height: "100vh", display: "flex", alignItems: "center", justifyContent: "center", background: "#6BA34E", fontFamily: "'Outfit', sans-serif" }}>
        <div style={{ textAlign: "center", color: "#2C3E1F" }}>
          <div style={{ fontSize: 48, marginBottom: 12 }}>🌱</div>
          <div style={{ fontSize: 18, fontWeight: 600 }}>No ideas in the grove yet</div>
        </div>
      </div>
    );
  }

  return (
    <div ref={containerRef} style={{ width: "100vw", height: "100vh", overflow: "hidden", position: "relative", fontFamily: "'Outfit', sans-serif", cursor: "ns-resize", userSelect: "none", touchAction: "none", WebkitOverflowScrolling: "auto" }}>

      {/* ─── Background ─── */}
      <div style={{ position: "absolute", inset: 0, zIndex: 0 }}>
        <div style={{
          position: "absolute", inset: 0,
          background: `linear-gradient(180deg, #7EC8E3 0%, #9DD4EA 20%, #B0D6E5 38%, #A8D0E0 49.5%, #6BA34E 50.5%, #5A9340 65%, #4D8838 82%, #458030 100%)`,
        }} />
        <div style={{
          position: "absolute", top: "6%", left: "50%", transform: "translateX(-50%)",
          width: 110, height: 110, borderRadius: "50%",
          background: "radial-gradient(circle, rgba(255,252,240,0.65) 0%, rgba(255,248,220,0.15) 50%, transparent 70%)",
        }} />
        <svg style={{ position: "absolute", inset: 0, width: "100%", height: "100%" }} preserveAspectRatio="none" viewBox="0 0 1000 1000">
          {(() => {
            const vpx = 500, vpy = 500, pathHW = 6, baseHW = 300;
            return (
              <>
                <polygon points={`${vpx-pathHW},${vpy} ${vpx+pathHW},${vpy} ${vpx+baseHW},1000 ${vpx-baseHW},1000`} fill="#C8A96E" />
                <polygon points={`${vpx-pathHW*0.4},${vpy} ${vpx+pathHW*0.4},${vpy} ${vpx+baseHW*0.6},1000 ${vpx-baseHW*0.6},1000`} fill="#D8BC82" opacity="0.3" />
                {[0.03, 0.08, 0.15, 0.25, 0.38, 0.52, 0.68, 0.82, 0.93].map((t, i) => {
                  const y = vpy + (1000 - vpy) * t;
                  const hw = pathHW + (baseHW - pathHW) * t;
                  return <line key={i} x1={vpx-hw+3} y1={y} x2={vpx+hw-3} y2={y} stroke="#BFA060" strokeWidth={0.3 + t * 1} opacity={0.1 + t * 0.1} />;
                })}
                <line x1={vpx-pathHW} y1={vpy} x2={vpx-baseHW} y2={1000} stroke="#A08050" strokeWidth="1" opacity="0.2" />
                <line x1={vpx+pathHW} y1={vpy} x2={vpx+baseHW} y2={1000} stroke="#A08050" strokeWidth="1" opacity="0.2" />
              </>
            );
          })()}
        </svg>
        <svg style={{ position: "absolute", top: "3%", left: "6%", opacity: 0.28 }} width="150" height="50" viewBox="0 0 150 50">
          <ellipse cx="75" cy="28" rx="62" ry="17" fill="white" /><ellipse cx="45" cy="25" rx="38" ry="14" fill="white" /><ellipse cx="108" cy="26" rx="32" ry="12" fill="white" />
        </svg>
        <svg style={{ position: "absolute", top: "8%", right: "4%", opacity: 0.2 }} width="120" height="40" viewBox="0 0 120 40">
          <ellipse cx="60" cy="22" rx="50" ry="14" fill="white" /><ellipse cx="35" cy="20" rx="28" ry="11" fill="white" />
        </svg>
      </div>

      {/* ─── Plants Layer ─── */}
      <div style={{ position: "absolute", inset: 0, zIndex: 5, pointerEvents: "none" }}>
        {visiblePlants.map(({ project, index, side, x, y, scale, opacity, plantSize, blur, distanceAhead, isPortrait }) => {
          const stage = STAGES[project.status] || STAGES.raw;
          const isLeft = side === "left";
          const statusHeight = plantSize * stage.heightScale;
          const statusWidth = plantSize * (0.4 + stage.heightScale * 0.6);
          const nameVisible = statusHeight > 20;
          const nameFontSize = Math.max(8, Math.min(14, statusHeight * 0.08));
          const nameOpacity = Math.min(1, (statusHeight - 20) / 40);
          const isOverhead = statusHeight > (isPortrait ? viewSize.h * 0.6 : viewSize.h * 0.7);
          const isClickable = nameVisible && opacity > 0.2 && !isOverhead;

          return (
            <div key={index} style={{
              position: "absolute", left: x, top: y,
              transform: `translate(${isLeft ? "-70%" : "-30%"}, -100%)`,
              opacity, filter: blur > 0 ? `blur(${blur}px)` : undefined,
              pointerEvents: isClickable ? "auto" : "none",
              zIndex: Math.round((1 - distanceAhead) * 100),
            }}>
              <div onClick={() => isClickable && setSelected(project)} style={{ cursor: isClickable ? "pointer" : "default", width: statusWidth, height: statusHeight, position: "relative" }}>
                <PlantForStatus status={project.status} impact={project.impact_score} business={project.business_score} scoreRanges={scoreRanges} />
                {nameVisible && (
                  <div style={{
                    position: "absolute", top: "35%",
                    [isLeft ? "right" : "left"]: 0,
                    transform: `translate(${isLeft ? "60%" : "-60%"}, -50%)`,
                    opacity: nameOpacity, pointerEvents: "none", whiteSpace: "nowrap",
                  }}>
                    <div style={{ fontFamily: "'Crimson Text', Georgia, serif", fontSize: nameFontSize, fontWeight: 700, color: "#2C1810", textShadow: "0 0 8px rgba(255,255,255,0.9), 0 0 16px rgba(255,255,255,0.7), 0 1px 3px rgba(255,255,255,0.95)", lineHeight: 1.2 }}>
                      {project.title}
                    </div>
                    <div style={{ fontSize: Math.max(6, nameFontSize * 0.7), fontWeight: 600, color: stage.color, textShadow: "0 0 6px rgba(255,255,255,0.9), 0 0 12px rgba(255,255,255,0.7)", lineHeight: 1.1 }}>
                      {stage.label}
                    </div>
                  </div>
                )}
              </div>
            </div>
          );
        })}
      </div>

      {/* ─── Title ─── */}
      <div style={{ position: "absolute", top: 0, left: 0, right: 0, zIndex: 10, display: "flex", justifyContent: "center", paddingTop: 14, pointerEvents: "none" }}>
        <div style={{ background: "rgba(255,255,255,0.45)", backdropFilter: "blur(8px)", borderRadius: 14, padding: "8px 20px", border: "1px solid rgba(255,255,255,0.35)", boxShadow: "0 3px 14px rgba(0,0,0,0.04)", textAlign: "center", pointerEvents: "auto", maxWidth: "80vw" }}>
          <h1 style={{ fontFamily: "'Crimson Text', Georgia, serif", fontSize: "clamp(20px, 5vw, 28px)", fontWeight: 700, color: "#2C3E1F", margin: 0, lineHeight: 1 }}>The Grove</h1>
          <p style={{ fontSize: "clamp(8px, 2.5vw, 10px)", color: "#5A7A4A", marginTop: 2, letterSpacing: 1.2, textTransform: "uppercase" }}>Ideas at every stage of growth</p>
        </div>
      </div>

      {/* ─── Version ─── */}
      <div style={{ position: 'absolute', bottom: 4, right: 8, zIndex: 10, fontSize: 9, color: 'rgba(255,255,255,0.3)', pointerEvents: 'none' }}>v{__APP_VERSION__}</div>

      {/* ─── Scroll hint ─── */}
      <div style={{ position: "absolute", bottom: 14, left: 0, right: 0, zIndex: 10, display: "flex", justifyContent: "center", pointerEvents: "none" }}>
        <div style={{ background: "rgba(255,255,255,0.35)", backdropFilter: "blur(4px)", borderRadius: 20, padding: "5px 14px", fontSize: 11, color: "#5A7A4A" }}>
          ↕ scroll to walk the path
        </div>
      </div>

      {selected && <DetailModal project={selected} onClose={() => setSelected(null)} />}

      <style>{`
        @import url('https://fonts.googleapis.com/css2?family=Crimson+Text:wght@400;600;700&family=Outfit:wght@300;400;500;600&display=swap');
        * { box-sizing: border-box; margin: 0; padding: 0; }
        html, body, #root { height: 100%; overflow: hidden; position: fixed; width: 100%; }
        html { overscroll-behavior: none; }
        body { overscroll-behavior: none; -webkit-overflow-scrolling: auto; }
      `}</style>
    </div>
  );
}
