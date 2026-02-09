#!/usr/bin/env python3
"""
Database Inventory Report Generator

Generates a comprehensive inventory of all database tables with:
- Row counts (exact or estimated for large tables)
- Classification (essential/config/audit/operational/test/seed)
- Origin (user/system/admin/external)
- Retention guidance
- PII detection

Usage:
    python scripts/db_inventory.py [--dsn DSN] [--exact-large] [--output-dir DIR]
    
Example:
    docker compose exec uask_orchestrator python scripts/db_inventory.py
"""

import os
import sys
import json
import csv
import argparse
from datetime import datetime
from typing import Optional, Dict, List, Any
from dataclasses import dataclass, asdict

# Ensure app is importable
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy import create_engine, text
from sqlalchemy.engine import Engine


# =============================================================================
# CONFIGURATION
# =============================================================================

DEFAULT_DSN = os.environ.get(
    "DATABASE_URL",
    "postgresql://uask_user:uask_password@localhost:5432/uask_db"
)

# Tables that are definitely for testing only
TEST_TABLE_PATTERNS = ["test_", "tmp_", "fixture_", "_test", "_tmp"]

# Classification overrides (table_name -> classification)
CLASSIFICATION_OVERRIDES: Dict[str, str] = {
    # Essential production data
    "user": "ESSENTIAL_PROD",
    "session": "ESSENTIAL_PROD",
    "solve_attempt": "ESSENTIAL_PROD",
    "payment": "ESSENTIAL_PROD",
    "credit_lot": "ESSENTIAL_PROD",
    "credit_consumption": "ESSENTIAL_PROD",
    "credit_hold": "ESSENTIAL_PROD",
    "subscription": "ESSENTIAL_PROD",
    "subscription_period": "ESSENTIAL_PROD",
    "invoice": "ESSENTIAL_PROD",
    "invoice_line_item": "ESSENTIAL_PROD",
    "credit_program": "ESSENTIAL_PROD",
    "credit_program_enrollment": "ESSENTIAL_PROD",
    "whatsapp_contact": "ESSENTIAL_PROD",
    "whatsapp_message": "ESSENTIAL_PROD",
    "followup_chat_turn": "ESSENTIAL_PROD",
    "solve_session": "ESSENTIAL_PROD",
    
    # Configuration
    "system_config": "CONFIG_PROD",
    "feature_flag": "CONFIG_PROD",
    "pricing_schema": "CONFIG_PROD",
    "tier_pricing": "CONFIG_PROD",
    "topup_product": "CONFIG_PROD",
    "subscription_plan": "CONFIG_PROD",
    
    # Audit/Ledger
    "billing_ledger": "AUDIT_PROD",
    "admin_audit_log": "AUDIT_PROD",
    "financial_ledger": "AUDIT_PROD",
    "reconciliation_run": "AUDIT_PROD",
    "reconciliation_mismatch": "AUDIT_PROD",
    
    # Operational
    "request_log": "OPERATIONAL_PROD",
    "error_log": "OPERATIONAL_PROD",
    "system_error_entry": "OPERATIONAL_PROD",
    "llm_usage_ledger": "OPERATIONAL_PROD",
    "telemetry": "OPERATIONAL_PROD",
    
    # Seed/Reference data
    "school": "SEED_DATA",
    "prompt": "SEED_DATA",
    "schema_def": "SEED_DATA",
    "prompt_link": "SEED_DATA",
    "provider_pricing": "SEED_DATA",
}

# PII column patterns
PII_PATTERNS = [
    "email", "phone", "name", "address", "ssn", "dob", "birth",
    "passport", "license", "password", "secret", "token"
]

# Seed sources (table_name -> seed file path)
SEED_SOURCES: Dict[str, str] = {
    "system_config": "scripts/seed_config.py",
    "school": "scripts/seed_db.py",
    "prompt": "scripts/seed_prompt_links.py",
    "prompt_link": "scripts/seed_prompt_links.py",
    "provider_pricing": "scripts/seed_provider_pricing_gpt5_family.py",
    "tier_pricing": "scripts/seed_pricing_phase0.py",
    "subscription_plan": "scripts/seed_plans_phase3.py",
    "topup_product": "scripts/seed_topups_phase2.py",
}

# Large table threshold
LARGE_TABLE_THRESHOLD = 5_000_000


@dataclass
class TableInfo:
    schema_name: str
    table_name: str
    rows_exact: Optional[int]
    rows_estimated: int
    classification: str
    seeded: bool
    seed_source: Optional[str]
    origin: str
    retention: str
    retention_reason: str
    description: str
    notes: str
    has_pii: bool
    pii_columns: List[str]
    column_count: int
    size_bytes: int
    
    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


def get_db_connection(dsn: str) -> Engine:
    """Create database connection."""
    if dsn.startswith("postgres://"):
        dsn = dsn.replace("postgres://", "postgresql://", 1)
    return create_engine(dsn)


def get_all_tables(engine: Engine) -> List[Dict[str, Any]]:
    """Get all tables with metadata."""
    query = text("""
        SELECT 
            n.nspname as schema_name,
            c.relname as table_name,
            c.reltuples::bigint as estimated_rows,
            pg_total_relation_size(c.oid) as size_bytes,
            obj_description(c.oid) as table_comment
        FROM pg_class c
        JOIN pg_namespace n ON n.oid = c.relnamespace
        WHERE c.relkind = 'r'
          AND n.nspname NOT IN ('pg_catalog', 'information_schema', 'pg_toast')
        ORDER BY n.nspname, c.relname
    """)
    
    with engine.connect() as conn:
        result = conn.execute(query)
        return [dict(row._mapping) for row in result]


def get_table_columns(engine: Engine, schema: str, table: str) -> List[Dict[str, Any]]:
    """Get column info for a table."""
    query = text("""
        SELECT 
            column_name,
            data_type,
            is_nullable
        FROM information_schema.columns
        WHERE table_schema = :schema AND table_name = :table
        ORDER BY ordinal_position
    """)
    
    with engine.connect() as conn:
        result = conn.execute(query, {"schema": schema, "table": table})
        return [dict(row._mapping) for row in result]


def get_exact_count(engine: Engine, schema: str, table: str) -> int:
    """Get exact row count for a table."""
    query = text(f'SELECT COUNT(*) FROM "{schema}"."{table}"')
    with engine.connect() as conn:
        result = conn.execute(query)
        return result.scalar()


def detect_pii_columns(columns: List[Dict[str, Any]]) -> List[str]:
    """Detect columns that might contain PII."""
    pii_cols = []
    for col in columns:
        col_name = col["column_name"].lower()
        for pattern in PII_PATTERNS:
            if pattern in col_name:
                pii_cols.append(col["column_name"])
                break
    return pii_cols


def classify_table(table_name: str, columns: List[Dict[str, Any]]) -> str:
    """Classify a table based on name and columns."""
    name_lower = table_name.lower()
    
    # Check overrides first
    if name_lower in CLASSIFICATION_OVERRIDES:
        return CLASSIFICATION_OVERRIDES[name_lower]
    
    # Pattern-based classification
    for pattern in TEST_TABLE_PATTERNS:
        if pattern in name_lower:
            return "TEST_ONLY"
    
    # Ledger/audit patterns
    if any(x in name_lower for x in ["ledger", "audit", "log", "history"]):
        return "AUDIT_PROD"
    
    # Config patterns
    if any(x in name_lower for x in ["config", "setting", "flag", "option"]):
        return "CONFIG_PROD"
    
    # Reference/enum patterns
    if any(x in name_lower for x in ["type", "status", "category", "enum", "ref_"]):
        return "SEED_DATA"
    
    # Default to essential if user-facing
    if any(x in name_lower for x in ["user", "session", "attempt", "payment", "credit"]):
        return "ESSENTIAL_PROD"
    
    return "OPERATIONAL_PROD"


def determine_origin(classification: str, table_name: str) -> str:
    """Determine data origin."""
    name_lower = table_name.lower()
    
    if classification in ["SEED_DATA", "CONFIG_PROD"]:
        return "ADMIN_MANAGED"
    
    if any(x in name_lower for x in ["stripe", "payment", "invoice"]):
        return "EXTERNAL_PROVIDER"
    
    if classification == "AUDIT_PROD":
        return "SYSTEM_GENERATED"
    
    if any(x in name_lower for x in ["user", "session", "attempt", "message"]):
        return "USER_GENERATED"
    
    return "SYSTEM_GENERATED"


def determine_retention(classification: str, table_name: str) -> tuple[str, str]:
    """Determine retention policy."""
    if classification == "AUDIT_PROD":
        return "Keep forever", "Legal/compliance requirement for financial audit trail"
    
    if classification == "ESSENTIAL_PROD":
        if "attempt" in table_name.lower():
            return "2 years", "User solve history, can be archived after 2 years"
        return "Keep forever", "Core production data"
    
    if classification == "OPERATIONAL_PROD":
        if "log" in table_name.lower():
            return "90 days", "Operational logs, rotate to reduce storage"
        return "30 days", "Runtime metadata, safe to purge periodically"
    
    if classification == "CONFIG_PROD":
        return "Keep forever", "System configuration"
    
    if classification == "SEED_DATA":
        return "Keep forever", "Reference data"
    
    if classification == "TEST_ONLY":
        return "Not applicable", "Should not exist in production"
    
    return "Keep forever", "Default retention"


def generate_description(table_name: str, columns: List[Dict[str, Any]]) -> str:
    """Generate a description based on table name and columns."""
    descriptions = {
        "user": "User accounts with credentials and profile data",
        "session": "User work sessions containing math problems",
        "solve_attempt": "Individual problem-solving attempts with LLM interactions",
        "payment": "Stripe payment transactions (top-ups)",
        "credit_lot": "Credit balance lots with expiry tracking",
        "credit_consumption": "Credit usage per attempt",
        "credit_hold": "Temporary credit reservations during solving",
        "billing_ledger": "Immutable billing event ledger",
        "subscription": "User subscription records",
        "subscription_plan": "Available subscription plans",
        "subscription_period": "Monthly subscription periods",
        "invoice": "Generated invoices",
        "invoice_line_item": "Invoice line items",
        "credit_program": "Credit grant program definitions",
        "credit_program_enrollment": "User enrollments in credit programs",
        "system_config": "Key-value system configuration",
        "pricing_schema": "Pricing schema versions",
        "tier_pricing": "Per-tier pricing configuration",
        "topup_product": "Available credit top-up products",
        "provider_pricing": "LLM provider cost tables",
        "prompt": "LLM prompt templates",
        "prompt_link": "Prompt-to-binding mappings",
        "schema_def": "JSON schema definitions for LLM outputs",
        "school": "School/institution reference data",
        "admin_audit_log": "Admin action audit trail",
        "llm_usage_ledger": "LLM token usage tracking",
        "whatsapp_contact": "WhatsApp bot user contacts",
        "whatsapp_message": "WhatsApp chat messages",
        "system_error_entry": "System error logs",
        "solve_session": "Follow-up chat sessions",
        "followup_chat_turn": "Follow-up chat messages",
        "reconciliation_run": "Balance reconciliation job runs",
        "reconciliation_mismatch": "Detected balance mismatches",
        "financial_ledger": "Financial transaction ledger",
        "alembic_version": "Database migration version tracking",
    }
    
    name_lower = table_name.lower()
    if name_lower in descriptions:
        return descriptions[name_lower]
    
    # Generate from name
    words = table_name.replace("_", " ").title()
    return f"{words} table ({len(columns)} columns)"


def analyze_table(
    engine: Engine,
    table_raw: Dict[str, Any],
    exact_large: bool = False
) -> TableInfo:
    """Analyze a single table and return TableInfo."""
    schema = table_raw["schema_name"]
    table = table_raw["table_name"]
    estimated = max(0, table_raw["estimated_rows"] or 0)
    size_bytes = table_raw["size_bytes"] or 0
    
    # Get columns
    columns = get_table_columns(engine, schema, table)
    
    # Exact count (skip for very large tables unless forced)
    rows_exact = None
    if estimated < LARGE_TABLE_THRESHOLD or exact_large:
        try:
            rows_exact = get_exact_count(engine, schema, table)
        except Exception as e:
            print(f"Warning: Could not count {schema}.{table}: {e}")
    
    # Detect PII
    pii_cols = detect_pii_columns(columns)
    
    # Classification
    classification = classify_table(table, columns)
    
    # Origin
    origin = determine_origin(classification, table)
    
    # Retention
    retention, retention_reason = determine_retention(classification, table)
    
    # Seed info
    name_lower = table.lower()
    seeded = name_lower in SEED_SOURCES or classification == "SEED_DATA"
    seed_source = SEED_SOURCES.get(name_lower)
    
    # Description
    description = generate_description(table, columns)
    
    # Notes
    notes_parts = []
    if pii_cols:
        notes_parts.append(f"PII: {', '.join(pii_cols)}")
    if estimated > 1_000_000:
        notes_parts.append("High growth - consider partitioning")
    if rows_exact is None and estimated > LARGE_TABLE_THRESHOLD:
        notes_parts.append(f"Large table - exact count skipped (est: {estimated:,})")
    
    return TableInfo(
        schema_name=schema,
        table_name=table,
        rows_exact=rows_exact,
        rows_estimated=estimated,
        classification=classification,
        seeded=seeded,
        seed_source=seed_source,
        origin=origin,
        retention=retention,
        retention_reason=retention_reason,
        description=description,
        notes="; ".join(notes_parts) if notes_parts else "",
        has_pii=bool(pii_cols),
        pii_columns=pii_cols,
        column_count=len(columns),
        size_bytes=size_bytes,
    )


def format_size(size_bytes: int) -> str:
    """Format bytes to human readable."""
    for unit in ["B", "KB", "MB", "GB"]:
        if size_bytes < 1024:
            return f"{size_bytes:.1f} {unit}"
        size_bytes /= 1024
    return f"{size_bytes:.1f} TB"


def generate_markdown_report(
    tables: List[TableInfo],
    db_name: str,
    host: str,
    timestamp: str,
) -> str:
    """Generate markdown report."""
    lines = []
    
    # Header
    lines.append("# Database Inventory Report")
    lines.append("")
    lines.append(f"**Database:** `{db_name}`")
    lines.append(f"**Host:** `{host}`")
    lines.append(f"**Generated:** {timestamp}")
    lines.append("")
    
    # Summary
    total_tables = len(tables)
    total_rows = sum(t.rows_exact or t.rows_estimated for t in tables)
    total_size = sum(t.size_bytes for t in tables)
    
    lines.append("## Summary")
    lines.append("")
    lines.append(f"- **Total Tables:** {total_tables}")
    lines.append(f"- **Total Rows:** {total_rows:,}")
    lines.append(f"- **Total Size:** {format_size(total_size)}")
    lines.append("")
    
    # Classification breakdown
    by_class = {}
    for t in tables:
        by_class.setdefault(t.classification, []).append(t)
    
    lines.append("### By Classification")
    lines.append("")
    lines.append("| Classification | Tables | Rows |")
    lines.append("|----------------|-------:|-----:|")
    for cls in sorted(by_class.keys()):
        tbl_list = by_class[cls]
        rows = sum(t.rows_exact or t.rows_estimated for t in tbl_list)
        lines.append(f"| {cls} | {len(tbl_list)} | {rows:,} |")
    lines.append("")
    
    # Main table
    lines.append("## All Tables")
    lines.append("")
    lines.append("| Schema | Table | Rows | Classification | Seeded | Origin | Description |")
    lines.append("|--------|-------|-----:|----------------|--------|--------|-------------|")
    
    for t in sorted(tables, key=lambda x: (x.schema_name, x.table_name)):
        rows = t.rows_exact if t.rows_exact is not None else f"~{t.rows_estimated:,}"
        if isinstance(rows, int):
            rows = f"{rows:,}"
        seeded = "YES" if t.seeded else "NO"
        desc = t.description[:50] + "..." if len(t.description) > 50 else t.description
        lines.append(f"| {t.schema_name} | {t.table_name} | {rows} | {t.classification} | {seeded} | {t.origin} | {desc} |")
    
    lines.append("")
    
    # Top 20 largest
    lines.append("## Top 20 Largest Tables")
    lines.append("")
    lines.append("| Table | Rows | Size | Classification |")
    lines.append("|-------|-----:|------|----------------|")
    
    for t in sorted(tables, key=lambda x: x.rows_exact or x.rows_estimated, reverse=True)[:20]:
        rows = t.rows_exact if t.rows_exact is not None else f"~{t.rows_estimated:,}"
        if isinstance(rows, int):
            rows = f"{rows:,}"
        lines.append(f"| {t.table_name} | {rows} | {format_size(t.size_bytes)} | {t.classification} |")
    
    lines.append("")
    
    # PII tables
    pii_tables = [t for t in tables if t.has_pii]
    if pii_tables:
        lines.append("## Tables with PII")
        lines.append("")
        lines.append("| Table | PII Columns |")
        lines.append("|-------|-------------|")
        for t in pii_tables:
            lines.append(f"| {t.table_name} | {', '.join(t.pii_columns)} |")
        lines.append("")
    
    # High growth tables
    high_growth = [t for t in tables if (t.rows_exact or t.rows_estimated) > 100_000]
    if high_growth:
        lines.append("## High Growth Tables (>100k rows)")
        lines.append("")
        lines.append("| Table | Rows | Notes |")
        lines.append("|-------|-----:|-------|")
        for t in sorted(high_growth, key=lambda x: x.rows_exact or x.rows_estimated, reverse=True):
            rows = t.rows_exact if t.rows_exact is not None else f"~{t.rows_estimated:,}"
            if isinstance(rows, int):
                rows = f"{rows:,}"
            notes = "Consider partitioning" if (t.rows_exact or t.rows_estimated) > 1_000_000 else ""
            lines.append(f"| {t.table_name} | {rows} | {notes} |")
        lines.append("")
    
    # Seed sources
    seeded_tables = [t for t in tables if t.seed_source]
    if seeded_tables:
        lines.append("## Seed Sources")
        lines.append("")
        lines.append("| Table | Seed File |")
        lines.append("|-------|-----------|")
        for t in seeded_tables:
            lines.append(f"| {t.table_name} | `{t.seed_source}` |")
        lines.append("")
    
    # Sanity checks
    schemas = set(t.schema_name for t in tables)
    lines.append("## Sanity Checks")
    lines.append("")
    lines.append(f"- **Total tables found:** {total_tables}")
    lines.append(f"- **Schemas included:** {', '.join(sorted(schemas))}")
    lines.append("- **Excluded schemas:** pg_catalog, information_schema, pg_toast")
    lines.append("")
    
    return "\n".join(lines)


def generate_csv_report(tables: List[TableInfo]) -> str:
    """Generate CSV report."""
    from io import StringIO
    
    output = StringIO()
    writer = csv.writer(output)
    
    # Header
    writer.writerow([
        "schema", "table", "rows_exact", "rows_est", "classification",
        "seeded", "seed_source", "origin", "retention", "retention_reason",
        "description", "notes", "has_pii", "pii_columns", "column_count", "size_bytes"
    ])
    
    for t in sorted(tables, key=lambda x: (x.schema_name, x.table_name)):
        writer.writerow([
            t.schema_name,
            t.table_name,
            t.rows_exact if t.rows_exact is not None else "",
            t.rows_estimated,
            t.classification,
            "YES" if t.seeded else "NO",
            t.seed_source or "",
            t.origin,
            t.retention,
            t.retention_reason,
            t.description,
            t.notes,
            "YES" if t.has_pii else "NO",
            ", ".join(t.pii_columns),
            t.column_count,
            t.size_bytes,
        ])
    
    return output.getvalue()


def main():
    parser = argparse.ArgumentParser(description="Generate database inventory report")
    parser.add_argument("--dsn", default=DEFAULT_DSN, help="Database connection string")
    parser.add_argument("--exact-large", action="store_true", help="Get exact counts for large tables")
    parser.add_argument("--output-dir", default="reports", help="Output directory")
    parser.add_argument("--json", action="store_true", help="Output JSON to stdout")
    args = parser.parse_args()
    
    # Create output directory
    os.makedirs(args.output_dir, exist_ok=True)
    
    # Connect to database
    print(f"Connecting to database...")
    dsn = args.dsn
    # Mask password in output
    dsn_display = dsn.split("@")[-1] if "@" in dsn else dsn
    print(f"Host: {dsn_display}")
    
    engine = get_db_connection(dsn)
    
    # Get database name
    db_name = dsn.split("/")[-1].split("?")[0]
    host = dsn.split("@")[-1].split("/")[0] if "@" in dsn else "localhost"
    
    # Get all tables
    print("Fetching table list...")
    raw_tables = get_all_tables(engine)
    print(f"Found {len(raw_tables)} tables")
    
    # Analyze each table
    print("Analyzing tables...")
    tables: List[TableInfo] = []
    for i, raw in enumerate(raw_tables):
        print(f"  [{i+1}/{len(raw_tables)}] {raw['schema_name']}.{raw['table_name']}")
        info = analyze_table(engine, raw, args.exact_large)
        tables.append(info)
    
    # Generate timestamp
    timestamp = datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S UTC")
    
    # Output JSON if requested
    if args.json:
        output = {
            "database": db_name,
            "host": host,
            "generated_at": timestamp,
            "tables": [t.to_dict() for t in tables],
        }
        print(json.dumps(output, indent=2, default=str))
        return
    
    # Generate markdown report
    print("\nGenerating markdown report...")
    md_report = generate_markdown_report(tables, db_name, host, timestamp)
    md_path = os.path.join(args.output_dir, "db_inventory_report.md")
    with open(md_path, "w", encoding="utf-8") as f:
        f.write(md_report)
    print(f"  Written: {md_path}")
    
    # Generate CSV report
    print("Generating CSV report...")
    csv_report = generate_csv_report(tables)
    csv_path = os.path.join(args.output_dir, "db_inventory_report.csv")
    with open(csv_path, "w", encoding="utf-8", newline="") as f:
        f.write(csv_report)
    print(f"  Written: {csv_path}")
    
    # Summary
    print("\n" + "=" * 60)
    print("SUMMARY")
    print("=" * 60)
    print(f"Total tables: {len(tables)}")
    print(f"Total rows: {sum(t.rows_exact or t.rows_estimated for t in tables):,}")
    print(f"Total size: {format_size(sum(t.size_bytes for t in tables))}")
    print("\nBy classification:")
    by_class = {}
    for t in tables:
        by_class.setdefault(t.classification, 0)
        by_class[t.classification] += 1
    for cls, count in sorted(by_class.items()):
        print(f"  {cls}: {count}")
    print("\nReports written to:")
    print(f"  - {md_path}")
    print(f"  - {csv_path}")


if __name__ == "__main__":
    main()
