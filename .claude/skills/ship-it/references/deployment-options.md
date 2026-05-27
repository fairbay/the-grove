# Deployment Options Reference

Load this file when the user needs help choosing a deployment platform. Skip if the target
is already known (e.g., "deploy to Vercel" — just do it).

**Note:** Verify current pricing and features via web search before recommending — this
reference may be stale.

## Web Deployment Options

| Project Type | Recommended Host | Free Tier | Why |
|---|---|---|---|
| Static site / SPA | **Cloudflare Pages** | Yes — unlimited bandwidth | Fastest CDN, zero config, generous limits |
| Static site / SPA (alt) | **Vercel** | Yes — 100GB bandwidth | Best Next.js support, great DX |
| Static site / SPA (alt) | **Netlify** | Yes — 100GB bandwidth | Easy forms, functions, identity |
| Next.js full-stack | **Vercel** | Yes (with limits) | Built for Next.js, serverless functions |
| Full-stack with DB | **Railway** | $5 trial credit | Simple, includes Postgres, Redis |
| Full-stack with DB (alt) | **Render** | Free tier with limits | Good free Postgres, web services |
| Python/Flask/FastAPI | **Railway** or **Render** | Limited free | Easy Python deployment |
| Heavy compute / custom | **Fly.io** | Free tier (3 VMs) | Docker-based, runs anything |

**Default:** Cloudflare Pages (static/SPA) or Vercel (Next.js). These cover 80% of cases at zero cost.

## Mobile Deployment Options

| Target | Path | Requirements | Cost |
|---|---|---|---|
| iOS App Store | Xcode → App Store Connect | Mac, Apple Developer Program | $99/year |
| iOS (cross-platform) | Expo → EAS Build → App Store | Apple Developer Program | $99/year + Expo plan |
| Android (Play Store) | Gradle → Play Console | Google Developer account | $25 one-time |
| Android (cross-platform) | Expo → EAS Build → Play Store | Google Developer account | $25 + Expo plan |
| Both (from React) | Expo → EAS Build → both stores | Both accounts | $124/year + Expo |
| Quick test (no store) | Expo Go / TestFlight | Minimal | Free |

**Default for mobile:** Start with Expo + React Native if the prototype was built in React.

## The PWA Middle Ground

For projects needing mobile presence without App Store submission:
- Add web app manifest + service worker to any web app
- Users "install" to home screen
- Works offline (with service worker caching)
- No app store approval process
- Free with any web hosting
- Limitations: limited hardware access, some iOS restrictions

**Recommend PWA when:** content-focused app, doesn't need native device APIs, user wants
mobile presence without App Store overhead.

## Cost Summary

| Service | Free Tier | First Paid Tier | Notes |
|---|---|---|---|
| Cloudflare Pages | Unlimited bandwidth, 500 builds/mo | $5/mo | Best free tier for static |
| Vercel | 100GB bandwidth, 100 builds/mo | $20/mo/member | Best for Next.js |
| Netlify | 100GB bandwidth, 300 build min/mo | $19/mo/member | Good forms + identity |
| Railway | $5 trial credit | ~$5-20/mo | Easiest full-stack |
| Render | 750 hrs free web service | $7/mo | Free Postgres |
| Fly.io | 3 shared VMs, 3GB storage | ~$5-15/mo | Docker-based |
| Expo EAS Build | 30 iOS + 30 Android builds/mo | $99/mo (team) | Cloud mobile builds |
| Apple Developer | — | $99/year | Required for App Store |
| Google Play | — | $25 one-time | Required for Play Store |
| Custom domain | — | ~$10-15/year | .com via Cloudflare/Namecheap |

## Static vs. Dynamic Hosting Decision

**Static hosting works if:**
- All data is baked in at build time
- No user accounts or login
- No server-side processing
- API calls go to external services (not your own backend)
- You're using client-side storage (localStorage, IndexedDB)

**You need dynamic hosting if:**
- Users create accounts and store data
- You run your own API
- You need server-side rendering for SEO
- You process uploads or files server-side
- You need background jobs or cron tasks

**The middle ground:**
- Serverless functions (Vercel, Netlify, Cloudflare Workers) — "static plus"
- Supabase or Firebase for auth + database without running a server
- These let you stay on free-tier hosting while adding dynamic features
