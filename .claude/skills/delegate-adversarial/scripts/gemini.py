#!/usr/bin/env python3
"""
Gemini API helper for the delegate-adversarial skill.

Calls Google's Gemini API for cross-model review and research tasks.
The independence from the Claude model family IS the value — same-family
review shares blind spots; cross-family review doesn't.

Capabilities:
  call()            — single-pass adversarial review (no tools)
  call_with_urls()  — review with URL Context (Gemini fetches repo/docs)
  research()        — search-grounded investigation
  create_cache()    — explicit context cache for multi-pass reviews
  call_cached()     — call referencing a cached context (90% token discount)
  delete_cache()    — clean up a context cache
  upload_file()     — upload large files via Files API
  call_with_files() — call referencing uploaded files

Usage:
  import sys
  sys.path.insert(0, '/mnt/skills/user/delegate-adversarial/scripts')
  from gemini import call, call_with_urls, create_cache, call_cached

  # Basic adversarial review (backward compatible)
  output, usage = call(system='...', user='...')

  # Review with URL Context — Gemini fetches the repo itself
  output, usage = call_with_urls(
      system='You are a senior reviewer...',
      user='Review the schema design in this repo: https://github.com/fairbay/medicaid-benefits-navigator',
      urls=['https://github.com/fairbay/medicaid-benefits-navigator'],
  )

  # Multi-pass review with context caching
  cache_name = create_cache(content='<large data export>', ttl_seconds=1800)
  out1, _ = call_cached(cache_name, user='Review schema design...')
  out2, _ = call_cached(cache_name, user='Audit data quality...')
  delete_cache(cache_name)

Reads GOOGLE_AI_KEY from secrets/gemini.env in fairbay/ops.
"""
import json
import urllib.error
import urllib.request
import sys

sys.path.insert(0, '/mnt/skills/user/git-ops/scripts')
from git_push import read_file  # noqa: E402

# -- Models ----------------------------------------------------------------
MODEL_FLASH = 'gemini-2.5-flash'
MODEL_PRO = 'gemini-2.5-pro'

# -- API base --------------------------------------------------------------
API_BASE = 'https://generativelanguage.googleapis.com'


class GeminiError(RuntimeError):
    """Surfaced verbatim — message tells Baylee what to do."""


# -- Key loading -----------------------------------------------------------

def _load_api_key() -> str:
    try:
        env = read_file('fairbay/ops', 'secrets/gemini.env')
    except Exception as e:
        raise GeminiError(
            "secrets/gemini.env not found in fairbay/ops. "
            "Create the file with GOOGLE_AI_KEY=<key> from aistudio.google.com."
        ) from e

    pairs = dict(
        line.split('=', 1)
        for line in env.strip().split('\n')
        if '=' in line and not line.startswith('#')
    )
    key = pairs.get('GOOGLE_AI_KEY', '').strip()
    if not key:
        raise GeminiError(
            "GOOGLE_AI_KEY missing from secrets/gemini.env. "
            "Get a key at aistudio.google.com and update the file."
        )
    return key


# -- Low-level HTTP helpers ------------------------------------------------

def _post(model: str, payload: dict) -> dict:
    """POST to Gemini generateContent endpoint."""
    key = _load_api_key()
    url = (
        f"{API_BASE}/v1beta/"
        f"models/{model}:generateContent?key={key}"
    )
    data = json.dumps(payload).encode()
    req = urllib.request.Request(
        url,
        data=data,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=300) as resp:
            return json.loads(resp.read().decode())
    except urllib.error.HTTPError as e:
        body = e.read().decode(errors='replace')
        raise GeminiError(f"Gemini API HTTP {e.code}: {body}") from e
    except urllib.error.URLError as e:
        raise GeminiError(
            f"Gemini API unreachable: {e.reason}. "
            "Is generativelanguage.googleapis.com in the egress allowlist?"
        ) from e


def _api_request(method: str, path: str, body: dict = None,
                 timeout: int = 120) -> dict:
    """Generic REST call to Gemini API (for caching, files, etc.)."""
    key = _load_api_key()
    separator = '&' if '?' in path else '?'
    url = f"{API_BASE}{path}{separator}key={key}"
    data = json.dumps(body).encode() if body else None
    req = urllib.request.Request(
        url,
        data=data,
        headers={"Content-Type": "application/json"} if data else {},
        method=method,
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            raw = resp.read().decode()
            return json.loads(raw) if raw else {}
    except urllib.error.HTTPError as e:
        body_text = e.read().decode(errors='replace')
        raise GeminiError(f"Gemini API HTTP {e.code}: {body_text}") from e
    except urllib.error.URLError as e:
        raise GeminiError(f"Gemini API unreachable: {e.reason}") from e


# -- Response extraction ---------------------------------------------------

def _extract(result: dict) -> tuple[str, dict]:
    """Extract text + usage from a Gemini response."""
    candidate = result.get('candidates', [{}])[0]

    finish = candidate.get('finishReason', '')
    if finish == 'SAFETY':
        raise GeminiError(
            "Gemini blocked the response (safety filter). "
            "Try rephrasing the review prompt."
        )

    parts = candidate.get('content', {}).get('parts', [])
    text = ''.join(p.get('text', '') for p in parts)

    raw_usage = result.get('usageMetadata', {})
    usage = {
        'prompt_tokens': raw_usage.get('promptTokenCount', 0),
        'output_tokens': raw_usage.get('candidatesTokenCount', 0),
        'thinking_tokens': raw_usage.get('thoughtsTokenCount', 0),
        'cached_tokens': raw_usage.get('cachedContentTokenCount', 0),
    }

    # Extract grounding metadata if present
    grounding = candidate.get('groundingMetadata', {})
    if grounding.get('groundingChunks'):
        usage['grounding_chunks'] = len(grounding['groundingChunks'])
        usage['sources'] = [
            {
                'title': ch.get('web', {}).get('title', ''),
                'uri': ch.get('web', {}).get('uri', ''),
            }
            for ch in grounding['groundingChunks']
            if 'web' in ch
        ]

    # Extract URL context metadata if present
    url_meta = candidate.get('urlContextMetadata', {})
    if url_meta.get('urlMetadata'):
        usage['url_context'] = [
            {
                'url': m.get('retrievedUrl', ''),
                'status': m.get('urlRetrievalStatus', ''),
            }
            for m in url_meta['urlMetadata']
        ]

    return text, usage


# =========================================================================
# PUBLIC API — backward-compatible functions
# =========================================================================

def call(
    system: str,
    user: str,
    model: str = MODEL_PRO,
    max_tokens: int = 16384,
    temperature: float = 0,
) -> tuple[str, dict]:
    """
    Single-pass Gemini call. No tools, no search grounding.

    Use for: code review, score audits, architecture critique, artifact
    review. The system prompt sets the adversarial frame; the user message
    is the deliverable to review.
    """
    payload = {
        "systemInstruction": {"parts": [{"text": system}]},
        "contents": [{"parts": [{"text": user}]}],
        "generationConfig": {
            "maxOutputTokens": max_tokens,
            "temperature": temperature,
        },
    }
    result = _post(model, payload)
    return _extract(result)


def research(
    query: str,
    format_hint: str = '',
    model: str = MODEL_FLASH,
    max_tokens: int = 8192,
    temperature: float = 0,
) -> tuple[str, dict]:
    """
    Search-grounded Gemini call. Uses Google Search for live data.

    Use for: demand validation, competitive landscape, market signals.
    """
    prompt = query
    if format_hint:
        prompt = f"{query}\n\n{format_hint}"

    payload = {
        "contents": [{"parts": [{"text": prompt}]}],
        "tools": [{"google_search": {}}],
        "generationConfig": {
            "maxOutputTokens": max_tokens,
            "temperature": temperature,
        },
    }
    result = _post(model, payload)
    return _extract(result)


# =========================================================================
# URL CONTEXT — let Gemini fetch and analyze URLs (repos, docs, etc.)
# =========================================================================

def call_with_urls(
    system: str,
    user: str,
    urls: list[str] = None,
    model: str = MODEL_PRO,
    max_tokens: int = 16384,
    temperature: float = 0,
) -> tuple[str, dict]:
    """
    Review call with URL Context tool enabled.

    Gemini fetches the content at the provided URLs and uses it as context
    for the review. URLs must be publicly accessible. Max 20 URLs per
    request, 34MB per URL.

    Best for: GitHub repo review, documentation analysis, comparing
    multiple public sources. Include URLs both in the `urls` parameter
    AND reference them in the `user` prompt for best results.

    Example:
        output, usage = call_with_urls(
            system='You are a senior reviewer...',
            user='Review the schema in https://github.com/org/repo',
            urls=['https://github.com/org/repo'],
        )
    """
    if urls and len(urls) > 20:
        raise GeminiError(
            f"URL Context supports max 20 URLs per request, got {len(urls)}. "
            "Split into multiple calls."
        )

    payload = {
        "systemInstruction": {"parts": [{"text": system}]},
        "contents": [{"parts": [{"text": user}]}],
        "tools": [{"urlContext": {}}],
        "generationConfig": {
            "maxOutputTokens": max_tokens,
            "temperature": temperature,
        },
    }
    result = _post(model, payload)
    return _extract(result)


# =========================================================================
# CONTEXT CACHING — upload data once, query multiple times at 90% discount
# =========================================================================

def create_cache(
    content: str,
    system: str = '',
    display_name: str = 'review-package',
    model: str = MODEL_PRO,
    ttl_seconds: int = 1800,
) -> str:
    """
    Create an explicit context cache for multi-pass reviews.

    Upload the large, static context (schema, data, docs) once. Then
    call call_cached() multiple times against it — each subsequent call
    gets a 90% token discount on the cached portion.

    Min token thresholds: 4096 for Pro, 1024 for Flash.
    Cache storage costs $1/M tokens/hour — set TTL appropriately.

    Args:
        content: The large text to cache (schema DDL, data export, etc.)
        system: Optional system instruction baked into the cache.
        display_name: Human-readable label for the cache.
        model: Which model to cache for (cache is model-specific).
        ttl_seconds: How long the cache lives. Default 30 min.

    Returns:
        Cache resource name (e.g. 'cachedContents/abc123') to pass to
        call_cached().
    """
    body = {
        "model": f"models/{model}",
        "displayName": display_name,
        "contents": [
            {
                "role": "user",
                "parts": [{"text": content}],
            },
        ],
        "ttl": f"{ttl_seconds}s",
    }
    if system:
        body["systemInstruction"] = {"parts": [{"text": system}]}

    result = _api_request("POST", "/v1beta/cachedContents", body)
    cache_name = result.get('name', '')
    if not cache_name:
        raise GeminiError(
            f"Cache creation returned no name. Response: "
            f"{json.dumps(result)[:500]}"
        )
    return cache_name


def call_cached(
    cache_name: str,
    user: str,
    model: str = MODEL_PRO,
    max_tokens: int = 16384,
    temperature: float = 0,
    urls: list[str] = None,
) -> tuple[str, dict]:
    """
    Generate content using a cached context.

    The cached content provides the large static context (schema, data).
    The `user` message provides the per-pass review instructions.
    Optionally enable URL Context to let Gemini also fetch live URLs.

    Input tokens from the cache get a 90% discount on Gemini 2.5+.

    Args:
        cache_name: Resource name from create_cache().
        user: The review prompt for this specific pass.
        urls: Optional list of URLs for Gemini to fetch (e.g. repo URL).
    """
    key = _load_api_key()
    url = (
        f"{API_BASE}/v1beta/"
        f"models/{model}:generateContent?key={key}"
    )
    payload = {
        "cachedContent": cache_name,
        "contents": [
            {
                "role": "user",
                "parts": [{"text": user}],
            },
        ],
        "generationConfig": {
            "maxOutputTokens": max_tokens,
            "temperature": temperature,
        },
    }

    # Optionally add URL Context tool for live repo access
    if urls:
        payload["tools"] = [{"urlContext": {}}]

    data = json.dumps(payload).encode()
    req = urllib.request.Request(
        url,
        data=data,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=300) as resp:
            result = json.loads(resp.read().decode())
    except urllib.error.HTTPError as e:
        body_text = e.read().decode(errors='replace')
        raise GeminiError(f"Gemini API HTTP {e.code}: {body_text}") from e
    except urllib.error.URLError as e:
        raise GeminiError(f"Gemini API unreachable: {e.reason}") from e

    return _extract(result)


def delete_cache(cache_name: str) -> None:
    """Delete a context cache to stop storage charges."""
    try:
        _api_request("DELETE", f"/v1beta/{cache_name}")
    except GeminiError:
        pass  # Best-effort cleanup; cache expires via TTL anyway


# =========================================================================
# FILES API — upload large files for use in generateContent
# =========================================================================

def upload_file(
    content: str,
    display_name: str = 'review-data',
    mime_type: str = 'text/plain',
) -> str:
    """
    Upload a file via the Gemini Files API.

    Files persist for 48 hours. Per-file max 2GB, project max 20GB.
    Use for data too large for inline text (>100MB) that isn't
    URL-accessible.

    Returns:
        File URI (e.g. 'https://generativelanguage.googleapis.com/...')
        to reference in generateContent calls.
    """
    key = _load_api_key()

    # Step 1: Initiate resumable upload
    init_url = (
        f"{API_BASE}/upload/v1beta/files?key={key}"
    )
    metadata = json.dumps({"file": {"displayName": display_name}}).encode()
    content_bytes = content.encode('utf-8')

    init_req = urllib.request.Request(
        init_url,
        data=metadata,
        headers={
            "X-Goog-Upload-Protocol": "resumable",
            "X-Goog-Upload-Command": "start",
            "X-Goog-Upload-Header-Content-Length": str(len(content_bytes)),
            "X-Goog-Upload-Header-Content-Type": mime_type,
            "Content-Type": "application/json",
        },
        method="POST",
    )

    try:
        with urllib.request.urlopen(init_req, timeout=60) as resp:
            upload_url = resp.headers.get("X-Goog-Upload-URL")
            if not upload_url:
                raise GeminiError("Files API did not return an upload URL.")
    except urllib.error.HTTPError as e:
        body_text = e.read().decode(errors='replace')
        raise GeminiError(f"Files API init HTTP {e.code}: {body_text}") from e

    # Step 2: Upload the file content
    upload_req = urllib.request.Request(
        upload_url,
        data=content_bytes,
        headers={
            "Content-Length": str(len(content_bytes)),
            "X-Goog-Upload-Offset": "0",
            "X-Goog-Upload-Command": "upload, finalize",
        },
        method="POST",
    )

    try:
        with urllib.request.urlopen(upload_req, timeout=300) as resp:
            result = json.loads(resp.read().decode())
    except urllib.error.HTTPError as e:
        body_text = e.read().decode(errors='replace')
        raise GeminiError(
            f"Files API upload HTTP {e.code}: {body_text}"
        ) from e

    file_uri = result.get('file', {}).get('uri', '')
    if not file_uri:
        raise GeminiError(
            f"Files API returned no URI. Response: "
            f"{json.dumps(result)[:500]}"
        )
    return file_uri


def call_with_files(
    system: str,
    user: str,
    file_uris: list[str],
    model: str = MODEL_PRO,
    max_tokens: int = 16384,
    temperature: float = 0,
) -> tuple[str, dict]:
    """
    Generate content referencing uploaded files.

    Pass file URIs from upload_file(). Each file becomes part of the
    prompt context.
    """
    parts = [{"text": user}]
    for uri in file_uris:
        parts.append({
            "fileData": {
                "mimeType": "text/plain",
                "fileUri": uri,
            }
        })

    payload = {
        "systemInstruction": {"parts": [{"text": system}]},
        "contents": [{"parts": parts}],
        "generationConfig": {
            "maxOutputTokens": max_tokens,
            "temperature": temperature,
        },
    }
    result = _post(model, payload)
    return _extract(result)
