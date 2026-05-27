# Durable images — generate → store → embed

HuggingFace image-generation tools (FLUX.1 Krea, Qwen-Image, Z-Image Turbo) return a
**temporary** URL that 404s within minutes. Embedding that URL in anything persisted —
a deployed page, a saved artifact, a pushed doc, a pitch — produces a broken image the
moment the temp link expires.

**The rule:** generate freely for preview, but the instant an image will live in a
persisted artifact, page, or doc, store it first and embed the permanent `publicUrl`.
Never embed a raw HF temp URL in anything durable.

## Flow

1. **Generate** with the HF MCP image tools (chat surface). Each returns a temp image
   URL — fine for in-chat preview only:
   - FLUX.1 Krea — `gr1_flux_1_krea_dev_infer` (source slug `flux-krea-dev`)
   - Qwen-Image — `gr2_qwen_image_generate_image` (source slug `qwen-image`)
   - Z-Image Turbo — `gr3_z_image_turbo_generate` (source slug `z-image-turbo`)

2. **Store** before persisting. POST the temp URL to the image-store endpoint:

   ```
   POST https://grove-woad-phi.vercel.app/api/image-store
   Headers: x-api-key: <IMAGE_STORE_KEY>, content-type: application/json
   Body:    { "url": "<temp image url>", "name": "slug",
              "source": "flux-krea-dev", "prompt": "<the generation prompt>" }
   ```

   Returns `{ id, publicUrl, size, format, storedAt }`.

3. **Embed** the returned `publicUrl` in the artifact / page / doc.

## If the temp URL already expired

Send the image bytes instead of a URL — only one of `url` / `base64` is required:

```
Body: { "base64": "<...>", "format": "webp", "name": "slug",
        "source": "flux-krea-dev", "prompt": "<the generation prompt>" }
```

## Limits

- Max 10 MB per image.
- Formats: `webp`, `png`, `jpg`, `jpeg`, `gif`.

## Key handling

`IMAGE_STORE_KEY` lives in `fairbay/baylee-skills/secrets/image-store.env` (tier-2
committed secret — read it via the GitHub API the same way `grove.py` reads `grove.env`).
**Never hardcode the literal key value in a skill file, page, or commit.**

## Provenance

Endpoint detail: `fairbay/grove` `apps/api/README.md` + PR #1. Why it exists (HF temp
URLs are unreachable from claude.ai bash/web_fetch, so a storage intermediary was
required): `fairbay/works` `papers/slime-mold-experiment/trial-01-image-store/results.md`
("Production deployment") and `deploy/HANDOFF-to-grove.md`.
