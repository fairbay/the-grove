#!/usr/bin/env python3
"""
Review package assembler for the delegate-adversarial skill.

Builds structured review packages from Supabase schema/data exports and
GitHub repo metadata. Designed to be called by Claude as part of the
multi-pass adversarial review workflow.

The output is a single text document optimized for Gemini's long context
window, following input packaging best practices from repo-scale review
practitioners:
  1. Repo tree map (orients model attention)
  2. Architecture summary (sets context)
  3. Explicit constraints (scope, severity, evidence requirements)
  4. Data sections (schema, sample data, etc.)

Usage (from Claude):
  import sys
  sys.path.insert(0, '/mnt/skills/user/delegate-adversarial/scripts')
  from review_package import assemble_package, generate_constraints

  package = assemble_package(
      tree_map='<repo tree output>',
      schema_ddl='<SQL from information_schema>',
      data_sample='<JSON data export>',
      architecture_summary='A consumer-facing web app...',
      metadata={'project': 'medicaid-benefits-navigator', 'states': 10},
  )
"""
import json
from textwrap import dedent


def generate_tree_map(file_list: list[str]) -> str:
    """
    Generate a directory tree from a flat list of file paths.

    Takes a list of paths (e.g. from GitHub API or git ls-tree) and
    produces a readable tree structure. Include this at the top of the
    review context to orient the model's attention.

    Args:
        file_list: List of relative file paths (e.g. ['src/schema.sql',
                   'src/api/routes.ts', 'README.md'])

    Returns:
        Formatted tree string.
    """
    if not file_list:
        return "(empty repository)"

    # Build tree structure
    tree = {}
    for path in sorted(file_list):
        parts = path.strip('/').split('/')
        node = tree
        for part in parts:
            node = node.setdefault(part, {})

    def _render(node, prefix='', is_last=True):
        lines = []
        items = sorted(node.items())
        for i, (name, children) in enumerate(items):
            last = (i == len(items) - 1)
            connector = '└── ' if last else '├── '
            lines.append(f"{prefix}{connector}{name}")
            if children:
                ext = '    ' if last else '│   '
                lines.extend(_render(children, prefix + ext, last))
        return lines

    return '\n'.join(_render(tree, '', True))


def format_schema(schema_ddl: str, table_count: int = 0) -> str:
    """
    Format schema DDL for review context.

    Args:
        schema_ddl: Raw SQL DDL (CREATE TABLE statements, etc.)
        table_count: Optional count for the header summary.
    """
    header = "## DATABASE SCHEMA"
    if table_count:
        header += f" ({table_count} tables)"

    return f"""{header}

```sql
{schema_ddl.strip()}
```"""


def format_data_sample(
    data: str | dict | list,
    label: str = 'DATA SAMPLE',
    max_chars: int = 500_000,
) -> str:
    """
    Format a data export for review context.

    Handles JSON strings, dicts, or lists. Truncates if over max_chars
    to stay within reasonable context limits.

    Args:
        data: JSON string, dict, or list of records.
        label: Section header label.
        max_chars: Truncation threshold. 500K chars ≈ 125K tokens.
    """
    if isinstance(data, (dict, list)):
        text = json.dumps(data, indent=2, default=str)
    else:
        text = str(data)

    truncated = ''
    if len(text) > max_chars:
        text = text[:max_chars]
        truncated = f"\n\n(TRUNCATED — showing first {max_chars:,} chars of full dataset)"

    return f"""## {label}

```json
{text}
```{truncated}"""


def generate_constraints(
    review_type: str = 'full',
    scope: str = '',
    custom_rules: list[str] = None,
) -> str:
    """
    Generate a constraints block for the review prompt.

    Adding explicit constraints reduces irrelevant findings by ~60%
    (per Verdent repo-review benchmarks). The severity ladder ensures
    consistent, actionable output.

    Args:
        review_type: 'schema', 'data_quality', 'architecture',
                     'methodology', or 'full'.
        scope: Human description of what's in scope.
        custom_rules: Additional rules specific to this review.
    """
    # Severity ladder (consistent across all review types)
    severity_ladder = dedent("""\
    SEVERITY DEFINITIONS:
    - CRITICAL: Data loss risk, security vulnerability, or fundamental
      design flaw that blocks production use.
    - HIGH: Likely to cause incorrect results, poor performance, or
      user-facing errors under realistic conditions.
    - MEDIUM: Edge case failures, missing validation, or design choices
      that will become HIGH over time.
    - LOW: Code quality, naming, documentation, or minor inconsistencies.
    - INFO: Observation only — not a defect but worth noting.
    """)

    # Evidence requirement (prevents hallucinated findings)
    evidence_rule = dedent("""\
    EVIDENCE REQUIREMENT:
    Only report findings you can support with specific evidence from the
    provided context. Do not suggest stylistic preferences, speculative
    improvements, or issues about code/data you haven't seen. Every finding
    must include a concrete location and quotation or reference.
    """)

    # Type-specific constraints
    type_constraints = {
        'schema': dedent("""\
        REVIEW FOCUS — DATABASE SCHEMA:
        - Normalization: Are entities properly separated? Redundant columns?
        - Referential integrity: FK constraints, cascading behavior, orphan risk.
        - Data types: Appropriate types for each field? Text where enum fits?
        - Temporal modeling: How are time-varying records handled?
        - Indexing: Missing indexes for likely query patterns?
        - Naming: Consistent conventions? Self-documenting column names?
        - Extensibility: Can new states/categories be added without schema changes?
        """),
        'data_quality': dedent("""\
        REVIEW FOCUS — DATA QUALITY:
        - Completeness: Missing required fields? Gaps in coverage?
        - Accuracy: Do values match expected ranges/formats? Contradictions?
        - Consistency: Same concept represented differently across records?
        - Duplication: Near-duplicate records with conflicting data?
        - Categorization: Are taxonomies applied consistently?
        - Source fidelity: Does structured data faithfully represent source material?
        """),
        'architecture': dedent("""\
        REVIEW FOCUS — SYSTEM ARCHITECTURE:
        - API design: RESTful patterns, error handling, pagination?
        - Data flow: Clear path from source → storage → consumer?
        - Separation of concerns: Business logic vs data access vs presentation?
        - Error handling: Failure modes identified and handled?
        - Scalability: Will this approach work at 10x/100x current data volume?
        - Security: Auth, input validation, data exposure risks?
        """),
        'methodology': dedent("""\
        REVIEW FOCUS — DATA COLLECTION METHODOLOGY:
        - Source reliability: Are data sources authoritative and current?
        - Extraction accuracy: Could the collection process introduce errors?
        - Coverage gaps: Systematic blind spots in data gathering?
        - Reproducibility: Could another team reproduce this data collection?
        - Temporal validity: How quickly does this data go stale?
        - Bias: Systematic over/under-representation of categories?
        """),
        'full': dedent("""\
        REVIEW FOCUS — COMPREHENSIVE:
        Evaluate schema design, data quality, architecture, and methodology.
        Prioritize findings that cross boundaries (e.g., a schema flaw that
        causes data quality issues, or a methodology gap that the architecture
        doesn't account for).
        """),
    }

    focus = type_constraints.get(review_type, type_constraints['full'])
    scope_block = f"\nSCOPE: {scope}\n" if scope else ''
    custom_block = ''
    if custom_rules:
        custom_block = "\nADDITIONAL RULES:\n" + '\n'.join(
            f"- {r}" for r in custom_rules
        ) + '\n'

    return f"""{severity_ladder}
{evidence_rule}
{focus}{scope_block}{custom_block}
OUTPUT FORMAT — one entry per finding:
SEVERITY: CRITICAL | HIGH | MEDIUM | LOW | INFO
LOCATION: [specific table/field/file/line or data record reference]
FINDING: [what's wrong — one sentence]
IMPACT: [what can go wrong if unaddressed — one sentence]
EVIDENCE: [specific reference from the provided context]
REMEDIATION: [concrete fix with specifics where possible]
"""


def assemble_package(
    tree_map: str = '',
    schema_ddl: str = '',
    data_sample: str = '',
    architecture_summary: str = '',
    methodology_notes: str = '',
    metadata: dict = None,
    additional_sections: dict = None,
) -> str:
    """
    Assemble a complete review package from components.

    Returns a single text document structured for Gemini's long context
    window. Place the largest, most stable content first (benefits
    implicit caching even without explicit cache creation).

    Args:
        tree_map: Repository directory tree (from generate_tree_map).
        schema_ddl: Database schema DDL.
        data_sample: JSON data export or sample.
        architecture_summary: 2-3 paragraph system description.
        methodology_notes: How the data was collected.
        metadata: Dict with project-level info (name, states, etc.).
        additional_sections: Dict of {header: content} for extra context.
    """
    sections = []

    # Header with metadata
    meta = metadata or {}
    project = meta.get('project', 'Unknown Project')
    sections.append(f"# REVIEW PACKAGE: {project}")
    if meta:
        meta_lines = [f"- {k}: {v}" for k, v in meta.items()]
        sections.append("## METADATA\n" + '\n'.join(meta_lines))

    # Architecture summary (sets context before details)
    if architecture_summary:
        sections.append(
            f"## ARCHITECTURE SUMMARY\n\n{architecture_summary.strip()}"
        )

    # Methodology (if provided)
    if methodology_notes:
        sections.append(
            f"## DATA COLLECTION METHODOLOGY\n\n{methodology_notes.strip()}"
        )

    # Repo tree map (orients attention)
    if tree_map:
        sections.append(f"## REPOSITORY STRUCTURE\n\n```\n{tree_map}\n```")

    # Schema DDL (large, stable — place early for implicit caching)
    if schema_ddl:
        sections.append(format_schema(schema_ddl))

    # Data sample
    if data_sample:
        sections.append(format_data_sample(data_sample))

    # Additional sections
    if additional_sections:
        for header, content in additional_sections.items():
            sections.append(f"## {header}\n\n{content}")

    return '\n\n---\n\n'.join(sections)
