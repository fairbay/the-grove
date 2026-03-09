# Grove Image Integration — Chat Handoff

## What Happened This Session
Built and deployed Variant Forge (image variant generator using Gemini API), used it to generate plant images for The Grove via Imagen 4. Plant image files are saved to Google Drive root folder.

## The Grove — Current State
- **Working artifact**: `the-grove-redesign.jsx` (latest version attached to this chat's outputs)
- **Repo**: `github.com/fairbay` (needs to be pushed — may still have SVG version)
- **Live site**: bayleemiller.org (currently has old V0)

### What's working in the artifact:
- First-person perspective walk with vanishing point at 50%
- Scroll/touch to walk, infinite loop
- Plants scaled by growth stage (seed=0.2x, shipped=1.0x)
- Plants grow huge as you approach, pointer-events disable so you can click behind
- Project names as text overlays with glow
- Click plant → detail modal with scores, tags, deploy links
- Flowers (impact) and fruit (business) as SVG overlays, count driven by relative scoring
- `effectiveScores()` gives deployed+ plants with null scores default decorations
- `SCORE_RANGES` computed from actual data so decoration counts are relative (highest score = most decorations)

### Plant SVGs (to be replaced with images):
Current plants are bezier blob silhouettes — single connected canopy with layered color. They work but look generic. The generated Imagen 4 images should replace them.

### The swap architecture (designed earlier this session):
```jsx
function PlantForStatus({ status, impact, business }) {
  const eff = effectiveScores(impact, business, status);
  const src = PLANT_IMAGES[status]; // map of status → image URL
  const spots = OVERLAY_SPOTS[status]; // flower/fruit positions per stage
  
  return (
    <div style={{ position: "relative", width: "100%", height: "100%" }}>
      <img src={src} style={{ width: "100%", height: "100%", objectFit: "contain", objectPosition: "bottom" }} />
      <svg style={{ position: "absolute", inset: 0 }} viewBox={spots.viewBox}>
        <Flowers positions={spots.flowers} count={scoreToCount(eff.impact, spots.maxF, SCORE_RANGES.impact)} />
        <Fruit positions={spots.flowers} count={scoreToCount(eff.business, spots.maxR, SCORE_RANGES.business)} />
      </svg>
    </div>
  );
}
```

Key decisions:
- Images as base layer, SVG flowers/fruit overlay on top (scores are dynamic per-project)
- Images go in Vercel `/public` folder, referenced by URL
- Flowers are 5-petal blossom shapes (not circles), fruit has stem + highlight
- Non-tree plants get `scale={0.25}` on decorations, trees get full size
- `preserveAspectRatio="xMidYMax meet"` to anchor plants at ground level

## Project Data (PROJECTS array in artifact)
```
DateWeave      — deployed, null/null scores, deploy: dateweave.vercel.app
PushCraft      — deployed, null/null scores, deploy: pushcraft.vercel.app
RepairShield   — scouted, 76/59
Crisis Cascade — scouted, 81/38
Shelf Life     — scouted, null/null
```
Missing from PROJECTS (need to add from vault): StoryWeaver, The Grove itself, Variant Forge, others.

## Growth Stages → Image Mapping
```
raw       → Seed          (heightScale 0.2)
scouted   → Sprout        (heightScale 0.35)
building  → Sapling       (heightScale 0.55)
in-dev    → Young Tree    (heightScale 0.75)
deployed  → Flowering     (heightScale 0.9)
shipped   → Bearing Fruit (heightScale 1.0)
parked    → Dormant       (heightScale 0.6)
killed    → Composted     (heightScale 0.15)
```

## Generated Images
8 plant stage images generated via Variant Forge (Imagen 4), saved to Google Drive root. These need to be:
1. Downloaded from Drive
2. Checked for transparent backgrounds (Imagen doesn't guarantee alpha — may need cleanup)
3. Placed in the Grove's `/public` folder
4. Referenced in the PLANT_IMAGES map

## Still To Do (from original status list)
- ✅ Fix flowers/fruit on deployed plants with null scores
- ✅ Relative scoring for decoration counts
- ✅ Flower redesign (5-petal, distinct from fruit)
- ✅ Scale decorations smaller on non-trees
- ✅ Foliage rebuild (done as SVG, now replacing with images)
- **→ NEXT: Integrate generated images into artifact**
- Update PROJECTS from vault (add missing ideas)
- Tune plant grounding if images float
- Consider re-adding hills/distant trees
- Package for deploy to bayleemiller.org

## Deploy Infrastructure
- **The Grove repo**: needs to be created/identified on github.com/fairbay
- **PushCraft**: live at pushcraft.vercel.app (v5.2), has multi-file upload with smart path detection
- **Vercel**: connected to fairbay GitHub, auto-deploys on push
- **Variant Forge**: live at variant-forge.vercel.app (or similar), Imagen 4 working

## Files to Reference
- `the-grove-redesign.jsx` — latest Grove artifact (in this chat's outputs)
- Plant images — Google Drive root folder
- PushCraft v5.2 — for pushing to GitHub
