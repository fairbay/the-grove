#!/usr/bin/env python3
"""
Multi-pass adversarial review orchestrator.

Runs structured, multi-pass adversarial reviews against a project's
codebase and data using Gemini's context caching for cost efficiency.

The workflow:
  1. Assemble a review package (schema, data, metadata)
  2. Create an explicit context cache (large static data uploaded once)
  3. Run multiple review passes (each targets a different concern)
  4. Aggregate and deduplicate findings across passes
  5. Clean up the cache

Each pass after the first gets a 90% token discount on the cached context,
making multi-pass reviews very cost-effective.

Usage (from Claude):
  import sys
  sys.path.insert(0, '/mnt/skills/user/delegate-adversarial/scripts')
  from project_review import multi_pass_review, REVIEW_PASSES

  findings, summary = multi_pass_review(
      package='<assembled review package>',
      repo_urls=['https://github.com/fairbay/medicaid-benefits-navigator'],
      passes=['schema', 'data_quality', 'methodology'],
  )
"""
import json
import sys
from textwrap import dedent

sys.path.insert(0, '/mnt/skills/user/delegate-adversarial/scripts')
from gemini import (  # noqa: E402
    GeminiError,
    create_cache,
    call_cached,
    call_with_urls,
    delete_cache,
    MODEL_PRO,
)
from review_package import generate_constraints  # noqa: E402


# -- Review pass definitions -----------------------------------------------

REVIEW_PASSES = {
    'schema': {
        'name': 'Schema & Architecture',
        'system': dedent("""\
            You are a senior database architect and independent reviewer
            from a different engineering team. Your job is to find flaws,
            gaps, and risks in the database schema design and system
            architecture. Do not praise what works. Do not suggest style
            improvements. Focus exclusively on issues that could cause
            data integrity problems, poor performance, or block future
            development."""),
        'constraint_type': 'schema',
    },
    'data_quality': {
        'name': 'Data Quality & Completeness',
        'system': dedent("""\
            You are a senior data quality auditor reviewing a dataset
            collected and structured by another team. Your job is to find
            data quality issues: missing fields, inconsistencies,
            misclassifications, duplicates, and gaps in coverage. Do not
            assess the schema design (that's a separate review). Focus
            on whether the actual data faithfully and completely represents
            the source information."""),
        'constraint_type': 'data_quality',
    },
    'architecture': {
        'name': 'System Architecture',
        'system': dedent("""\
            You are a senior systems architect reviewing an application's
            technical architecture. Your job is to find design flaws,
            scalability risks, security gaps, and maintainability issues.
            Do not review data quality or schema design (separate reviews).
            Focus on the overall system: API design, data flow, error
            handling, deployment, and operational readiness."""),
        'constraint_type': 'architecture',
    },
    'methodology': {
        'name': 'Data Collection Methodology',
        'system': dedent("""\
            You are a research methodology auditor. Your job is to evaluate
            how data was collected, whether the approach introduces
            systematic biases or gaps, and whether the results are
            reproducible. Do not review the database schema or code quality
            (separate reviews). Focus on the data gathering process itself:
            source reliability, extraction accuracy, coverage completeness,
            and temporal validity."""),
        'constraint_type': 'methodology',
    },
    'full': {
        'name': 'Comprehensive Review',
        'system': dedent("""\
            You are a senior independent reviewer conducting a comprehensive
            audit of a project's database design, data quality, architecture,
            and methodology. Your job is to find flaws, gaps, and risks
            across all dimensions. Prioritize cross-cutting issues where a
            flaw in one area causes problems in another. Do not praise what
            works. Return only issues found."""),
        'constraint_type': 'full',
    },
}


# -- Review prompt builder -------------------------------------------------

def _build_review_prompt(
    pass_config: dict,
    repo_urls: list[str] = None,
    scope: str = '',
    custom_rules: list[str] = None,
) -> str:
    """Build the user prompt for a specific review pass."""
    constraints = generate_constraints(
        review_type=pass_config['constraint_type'],
        scope=scope,
        custom_rules=custom_rules,
    )

    url_section = ''
    if repo_urls:
        url_list = '\n'.join(f'- {u}' for u in repo_urls)
        url_section = dedent(f"""\

        REPOSITORY URLs (Gemini will fetch these for code context):
        {url_list}

        Analyze the code in these repositories alongside the data provided
        in the cached context.
        """)

    return f"""{constraints}{url_section}
Review the project materials provided in context. Return your findings
in the specified output format. Be thorough but precise — every finding
must have specific evidence."""


# -- Core orchestrator -----------------------------------------------------

def multi_pass_review(
    package: str,
    repo_urls: list[str] = None,
    passes: list[str] = None,
    scope: str = '',
    custom_rules: list[str] = None,
    model: str = MODEL_PRO,
    cache_ttl: int = 1800,
    max_tokens_per_pass: int = 16384,
) -> tuple[list[dict], dict]:
    """
    Run a multi-pass adversarial review with context caching.

    Creates a context cache with the review package, then runs each
    requested review pass against it. Passes 2+ get 90% token discount.

    Args:
        package: Assembled review package text (from assemble_package).
        repo_urls: Public GitHub/doc URLs for Gemini to fetch via URL Context.
        passes: List of pass keys from REVIEW_PASSES. Default: all passes.
        scope: Human description of what's in scope.
        custom_rules: Extra rules applied to every pass.
        model: Gemini model to use.
        cache_ttl: Cache lifetime in seconds (default 30 min).
        max_tokens_per_pass: Max output tokens per review pass.

    Returns:
        (all_findings, summary) where:
        - all_findings: list of finding dicts with pass_name, severity, etc.
        - summary: dict with pass results, token usage, cost estimate.
    """
    if passes is None:
        passes = ['schema', 'data_quality', 'methodology']

    # Validate pass names
    for p in passes:
        if p not in REVIEW_PASSES:
            raise GeminiError(
                f"Unknown review pass '{p}'. "
                f"Available: {', '.join(REVIEW_PASSES.keys())}"
            )

    all_findings = []
    pass_results = []
    total_usage = {
        'prompt_tokens': 0, 'output_tokens': 0,
        'thinking_tokens': 0, 'cached_tokens': 0,
    }

    # Create the context cache with the review package
    cache_name = None
    try:
        print(f"Creating context cache ({len(package):,} chars)...")
        cache_name = create_cache(
            content=package,
            system='',
            display_name='project-review',
            model=model,
            ttl_seconds=cache_ttl,
        )
        print(f"Cache created: {cache_name}")

        # Run each review pass
        for i, pass_key in enumerate(passes):
            config = REVIEW_PASSES[pass_key]
            print(f"\nPass {i+1}/{len(passes)}: {config['name']}...")

            prompt = _build_review_prompt(
                config,
                repo_urls=repo_urls,
                scope=scope,
                custom_rules=custom_rules,
            )

            # First pass: include URL Context for repo access
            # Subsequent passes: cache-only (URLs already analyzed)
            use_urls = repo_urls if i == 0 else None

            output, usage = call_cached(
                cache_name=cache_name,
                user=f"{config['system']}\n\n{prompt}",
                model=model,
                max_tokens=max_tokens_per_pass,
                urls=use_urls,
            )

            # Parse findings from output
            findings = _parse_findings(output, config['name'])
            all_findings.extend(findings)

            # Accumulate usage
            for k in total_usage:
                total_usage[k] += usage.get(k, 0)

            pass_result = {
                'pass': pass_key,
                'name': config['name'],
                'findings_count': len(findings),
                'severity_counts': _count_severities(findings),
                'usage': usage,
                'raw_output': output,
            }
            pass_results.append(pass_result)

            crit = pass_result['severity_counts'].get('CRITICAL', 0)
            high = pass_result['severity_counts'].get('HIGH', 0)
            med = pass_result['severity_counts'].get('MEDIUM', 0)
            print(
                f"  Found {len(findings)} issues: "
                f"{crit} critical, {high} high, {med} medium"
            )
            print(
                f"  Tokens: {usage.get('prompt_tokens', 0)} in / "
                f"{usage.get('output_tokens', 0)} out "
                f"({usage.get('cached_tokens', 0)} cached)"
            )

    finally:
        # Always clean up the cache
        if cache_name:
            print(f"\nCleaning up cache...")
            delete_cache(cache_name)

    # Build summary
    summary = {
        'passes': pass_results,
        'total_findings': len(all_findings),
        'total_severity_counts': _count_severities(all_findings),
        'total_usage': total_usage,
        'cost_estimate': _estimate_cost(total_usage, model),
    }

    return all_findings, summary


# -- Single-pass review (no caching, for smaller projects) -----------------

def single_pass_review(
    package: str,
    repo_urls: list[str] = None,
    review_type: str = 'full',
    scope: str = '',
    model: str = MODEL_PRO,
    max_tokens: int = 16384,
) -> tuple[list[dict], dict]:
    """
    Run a single adversarial review pass without caching.

    For smaller reviews where caching overhead isn't justified.
    Uses URL Context if repo_urls are provided.
    """
    config = REVIEW_PASSES.get(review_type, REVIEW_PASSES['full'])
    prompt = _build_review_prompt(config, repo_urls=repo_urls, scope=scope)
    full_prompt = f"{package}\n\n{prompt}"

    if repo_urls:
        output, usage = call_with_urls(
            system=config['system'],
            user=full_prompt,
            urls=repo_urls,
            model=model,
            max_tokens=max_tokens,
        )
    else:
        from gemini import call
        output, usage = call(
            system=config['system'],
            user=full_prompt,
            model=model,
            max_tokens=max_tokens,
        )

    findings = _parse_findings(output, config['name'])
    summary = {
        'findings_count': len(findings),
        'severity_counts': _count_severities(findings),
        'usage': usage,
        'cost_estimate': _estimate_cost(usage, model),
    }

    return findings, summary


# -- Finding parser --------------------------------------------------------

def _parse_findings(output: str, pass_name: str) -> list[dict]:
    """
    Parse findings from Gemini's review output.

    Tries JSON first (if Gemini returns structured data), then falls
    back to parsing the severity-ladder text format.
    """
    # Try JSON parse first
    clean = output.strip()
    if clean.startswith('```'):
        clean = clean.split('\n', 1)[1] if '\n' in clean else clean
        clean = clean.rsplit('```', 1)[0] if '```' in clean else clean
        clean = clean.strip()

    try:
        parsed = json.loads(clean)
        if isinstance(parsed, list):
            for f in parsed:
                f['pass_name'] = pass_name
            return parsed
    except (json.JSONDecodeError, ValueError):
        pass

    # Fall back to text parsing
    findings = []
    current = {}

    for line in output.split('\n'):
        line = line.strip()
        if not line:
            if current.get('severity'):
                current['pass_name'] = pass_name
                findings.append(current)
                current = {}
            continue

        for field in ['SEVERITY', 'LOCATION', 'FINDING', 'IMPACT',
                      'EVIDENCE', 'REMEDIATION']:
            if line.upper().startswith(f'{field}:'):
                value = line.split(':', 1)[1].strip()
                current[field.lower()] = value
                break

    # Don't forget the last finding
    if current.get('severity'):
        current['pass_name'] = pass_name
        findings.append(current)

    return findings


def _count_severities(findings: list[dict]) -> dict:
    """Count findings by severity level."""
    counts = {}
    for f in findings:
        sev = f.get('severity', 'UNKNOWN').upper()
        counts[sev] = counts.get(sev, 0) + 1
    return counts


def _estimate_cost(usage: dict, model: str) -> dict:
    """
    Estimate API cost from token usage.

    Gemini 2.5 Pro pricing (as of mid-2026):
      Input: $1.25/M (≤200K), $2.50/M (>200K)
      Output: $10/M (≤200K), $15/M (>200K)
      Cached input: 90% discount → $0.125/M or $0.25/M
      Thinking: billed at output rate
    """
    input_t = usage.get('prompt_tokens', 0)
    output_t = usage.get('output_tokens', 0)
    thinking_t = usage.get('thinking_tokens', 0)
    cached_t = usage.get('cached_tokens', 0)

    # Simplified pricing (under-200K tier)
    if model.endswith('flash') or 'flash' in model:
        input_cost = (input_t - cached_t) * 0.15 / 1_000_000
        cached_cost = cached_t * 0.015 / 1_000_000
        output_cost = (output_t + thinking_t) * 0.60 / 1_000_000
    else:
        input_cost = (input_t - cached_t) * 1.25 / 1_000_000
        cached_cost = cached_t * 0.125 / 1_000_000
        output_cost = (output_t + thinking_t) * 10.0 / 1_000_000

    total = input_cost + cached_cost + output_cost
    return {
        'input_cost': round(input_cost, 4),
        'cached_cost': round(cached_cost, 4),
        'output_cost': round(output_cost, 4),
        'total': round(total, 4),
    }


# -- Report formatter (for Claude to present) ------------------------------

def format_report(findings: list[dict], summary: dict) -> str:
    """
    Format findings into a readable report for Baylee.

    Returns markdown text that Claude can present directly.
    """
    lines = []
    lines.append(f"# Adversarial Review Results")
    lines.append('')

    # Summary
    total = summary['total_findings']
    sevs = summary['total_severity_counts']
    cost = summary.get('cost_estimate', {})
    usage = summary.get('total_usage', {})

    lines.append(
        f"**{total} findings** across {len(summary.get('passes', []))} passes: "
        f"{sevs.get('CRITICAL', 0)} critical, "
        f"{sevs.get('HIGH', 0)} high, "
        f"{sevs.get('MEDIUM', 0)} medium, "
        f"{sevs.get('LOW', 0)} low, "
        f"{sevs.get('INFO', 0)} info"
    )
    if cost:
        lines.append(
            f"\nEstimated cost: ${cost.get('total', 0):.4f} "
            f"({usage.get('prompt_tokens', 0):,} prompt / "
            f"{usage.get('output_tokens', 0):,} output / "
            f"{usage.get('cached_tokens', 0):,} cached)"
        )
    lines.append('')

    # Findings by severity
    severity_order = ['CRITICAL', 'HIGH', 'MEDIUM', 'LOW', 'INFO']
    for sev in severity_order:
        sev_findings = [
            f for f in findings
            if f.get('severity', '').upper() == sev
        ]
        if not sev_findings:
            continue

        lines.append(f"## {sev} ({len(sev_findings)})")
        lines.append('')

        for f in sev_findings:
            loc = f.get('location', 'unspecified')
            finding = f.get('finding', 'No description')
            impact = f.get('impact', '')
            evidence = f.get('evidence', '')
            fix = f.get('remediation', '')
            source = f.get('pass_name', '')

            lines.append(f"### [{source}] {finding}")
            lines.append(f"**Location:** {loc}")
            if impact:
                lines.append(f"**Impact:** {impact}")
            if evidence:
                lines.append(f"**Evidence:** {evidence}")
            if fix:
                lines.append(f"**Fix:** {fix}")
            lines.append('')

    return '\n'.join(lines)
