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

Every call goes through the outside-model doorway (llm_doorway.py; MBN m1308):
the key lives in the Supabase Vault and is never read by this script. The
caching and Files API helpers are not routed through the doorway yet and raise
GeminiError; use call() / research() / call_with_urls(), or Baylee's manual
Gemini channel for a large raw-context review.
"""
import base64
import json
import os
import sys
import subprocess
import urllib.error
import urllib.request

# -- Models ----------------------------------------------------------------
# One home for the model names: llm.prices (default_for = 'review' | 'mechanical').
# These constants are the seeded values; llm_doorway.default_model() reads the live row.
MODEL_FLASH = 'gemini-3.8-flash'
MODEL_PRO = 'gemini-3.1-pro-preview'

# -- The doorway -----------------------------------------------------------
_HERE = os.path.dirname(os.path.abspath(__file__))
if _HERE not in sys.path:
    sys.path.insert(0, _HERE)
from llm_doorway import DoorwayError, call as _doorway_call, estimate as doorway_estimate, default_model  # noqa: E402,F401

PURPOSE = 'delegate-adversarial'   # set by the caller before a run, e.g. gemini.PURPOSE = 'idea-scout research'
SURFACE = os.environ.get('LLM_DOORWAY_SURFACE', 'code')
RUN_ID = None                      # set to group a multi-call run; pair with RUN_BUDGET_USD
RUN_BUDGET_USD = None
THINKING = 'low'                   # 'low' | 'medium' | 'high'; every body carries an explicit setting or the doorway refuses

API_BASE = 'https://generativelanguage.googleapis.com'  # only in the helpers that raise _NOT_THROUGH_DOORWAY

_NOT_THROUGH_DOORWAY = (
    "Not available through the doorway yet (context caching and the Files API call other endpoints). "
    "Use call() / call_with_urls() / research(), or Baylee's manual Gemini channel for a large raw-context review."
)


def thinking_config(model: str, level: str | None = None) -> dict:
    """An explicit thinking setting for the body: thinkingLevel on Gemini 3 and later, thinkingBudget on older models."""
    level = level or THINKING
    if model.startswith('gemini-3'):
        return {'thinkingLevel': level}
    budget = {'low': 1024, 'medium': 8192, 'high': 24576}.get(level, 1024)
    return {'thinkingBudget': budget}


class GeminiError(RuntimeError):
    """Surfaced verbatim — message tells Baylee what to do."""


# -- Low-level HTTP helpers ------------------------------------------------

def _post(model: str, payload: dict) -> dict:
    """POST to Gemini generateContent through the doorway; returns the provider's response body."""
    payload.setdefault('generationConfig', {})
    payload['generationConfig'].setdefault('thinkingConfig', thinking_config(model))
    try:
        res = _doorway_call('google', model, payload, purpose=PURPOSE, surface=SURFACE,
                            run_id=RUN_ID, run_budget_usd=RUN_BUDGET_USD, text_only=False)
    except DoorwayError as e:
        raise GeminiError(str(e)) from e
    status = res.get('status')
    if status == 'done' and res.get('response'):
        return res['response']
    raise GeminiError(
        f"Doorway {status}: {res.get('message') or res.get('error') or 'no response'} "
        f"(call {res.get('call_id')}). Stop and report this; a retry or a model substitution is Baylee's call."
    )


def _api_request(method: str, path: str, body: dict = None,
                 timeout: int = 120) -> dict:
    """Generic REST call to Gemini API (for caching, files, etc.)."""
    raise GeminiError(_NOT_THROUGH_DOORWAY)
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

URL_SUCCESS = 'URL_RETRIEVAL_STATUS_SUCCESS'


def _norm_url(u: str) -> str:
    """One spelling for a URL Gemini may echo differently: lowercase scheme and host,
    no fragment, no trailing slash."""
    from urllib.parse import urlsplit, urlunsplit
    p = urlsplit(u.strip())
    return urlunsplit((p.scheme.lower(), p.netloc.lower(), p.path.rstrip('/'), p.query, '')).rstrip('/')


def check_url_context(usage: dict, urls: list[str]) -> None:
    """Fail loudly unless every requested URL was fetched, and nothing else failed (4ab959be).

    Every urlContextMetadata entry for a requested URL must be
    URL_RETRIEVAL_STATUS_SUCCESS (a repeated URL with one ERROR fails); a requested URL
    absent from the metadata is "not retrieved"; any other entry that is not SUCCESS
    fails too. URLs are compared after normalization (scheme and host case, fragment,
    trailing slash).
    """
    statuses: dict[str, set] = {}
    for m in usage.get('url_context', []):
        statuses.setdefault(_norm_url(m['url']), set()).add(m['status'])
    bad = []
    for u in urls:
        got = statuses.get(_norm_url(u))
        if not got:
            bad.append(f"{u}: not retrieved")
        elif got != {URL_SUCCESS}:
            bad.append(f"{u}: {', '.join(sorted(st for st in got if st != URL_SUCCESS))}")
    wanted = {_norm_url(u) for u in urls}
    for u, got in statuses.items():
        if u not in wanted and got != {URL_SUCCESS}:
            bad.append(f"{u} (not requested): {', '.join(sorted(got - {URL_SUCCESS}))}")
    if bad:
        raise GeminiError(
            "URL context incomplete, the output is not a review: " + "; ".join(bad)
            + ". Send the content inline, or fix the URL, and make one new call."
        )


def call_with_urls(
    system: str,
    user: str,
    urls: list[str] = None,
    model: str = MODEL_PRO,
    max_tokens: int = 16384,
    temperature: float = 0,
    content_sha256: dict | None = None,
) -> tuple[str, dict]:
    """
    Review call with URL Context tool enabled, for sources that are public anyway.

    Gemini fetches the content at the provided URLs and uses it as context
    for the review. URLs must be publicly accessible. Max 20 URLs per
    request, 34MB per URL. Our own documents go inline instead (the doorway
    prices and audits only the body it sees; Google's file-input guide:
    inline for our files, URLs for data already hosted online).

    `content_sha256` maps a URL (one of `urls`) to the sha256 of the content
    the author fetched there; each hash is written into the prompt so the
    audit row (llm.calls.request) records what the author expected Gemini to
    read. Nothing compares it to what Gemini fetched. The response's
    urlContextMetadata is checked (check_url_context): any requested URL not
    retrieved with URL_RETRIEVAL_STATUS_SUCCESS raises GeminiError.

    Example:
        output, usage = call_with_urls(
            system='You are a senior reviewer...',
            user='Review the schema in https://github.com/org/repo',
            urls=['https://github.com/org/repo'],
        )
    """
    urls = list(urls or [])
    if len(urls) > 20:
        raise GeminiError(
            f"URL Context supports max 20 URLs per request, got {len(urls)}. "
            "Split into multiple calls."
        )
    if content_sha256:
        extra = [u for u in content_sha256 if _norm_url(u) not in {_norm_url(x) for x in urls}]
        if extra:
            raise GeminiError(f"content_sha256 names URLs not in urls: {extra}")
        user = user + "\n\nExpected content (sha256 of each URL's content as fetched by the author):\n" + "\n".join(
            f"- {u}: {h}" for u, h in content_sha256.items())

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
    text, usage = _extract(result)
    check_url_context(usage, urls)
    return text, usage


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
    raise GeminiError(_NOT_THROUGH_DOORWAY)
    key = None
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
    raise GeminiError(_NOT_THROUGH_DOORWAY)
    key = None

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
