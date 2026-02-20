#!/usr/bin/env python3
import json
import os
import re
from datetime import datetime, timezone

try:
    import psycopg2
except Exception as exc:  # pragma: no cover
    raise SystemExit(f"psycopg2 is required for perf db checks: {exc}")


def utc_now():
    return datetime.now(timezone.utc).isoformat()


def sanitize_query_for_explain(query: str) -> str:
    q = query.strip().rstrip(";")
    q = re.sub(r"\$\d+", "NULL", q)
    return q


def run():
    out_path = os.environ.get("PERF_DB_OUT", "reports/perf_db_checks.json")
    database_url = os.environ.get(
        "DATABASE_URL",
        "postgresql://uask_user:uask_password@localhost:5432/uask_db",
    )

    payload = {
        "generatedAt": utc_now(),
        "databaseUrlRedacted": re.sub(r":[^:@/]+@", ":***@", database_url),
        "pgStatStatementsAvailable": False,
        "topSlowQueries": [],
        "explainAnalyze": [],
        "nPlusOneHeuristics": [],
        "notes": [],
    }

    os.makedirs(os.path.dirname(out_path), exist_ok=True)

    try:
        conn = psycopg2.connect(database_url)
    except Exception as exc:
        payload["notes"].append(f"DB connect failed: {exc}")
        with open(out_path, "w", encoding="utf8") as f:
            json.dump(payload, f, indent=2)
        print(f"[perf-db] wrote {out_path}")
        return

    conn.autocommit = True
    try:
        with conn.cursor() as cur:
            try:
                cur.execute("SELECT 1 FROM pg_extension WHERE extname='pg_stat_statements';")
                payload["pgStatStatementsAvailable"] = bool(cur.fetchone())
            except Exception as exc:
                payload["notes"].append(f"Unable to check pg_stat_statements extension: {exc}")

            if not payload["pgStatStatementsAvailable"]:
                payload["notes"].append(
                    "pg_stat_statements extension is not enabled; cannot identify top slow queries from runtime stats."
                )
            else:
                try:
                    cur.execute(
                        """
                        SELECT queryid, calls, total_exec_time, mean_exec_time, rows, query
                        FROM pg_stat_statements
                        WHERE query NOT ILIKE '%pg_stat_statements%'
                        ORDER BY total_exec_time DESC
                        LIMIT 10
                        """
                    )
                    rows = cur.fetchall()
                    for r in rows:
                        payload["topSlowQueries"].append(
                            {
                                "queryid": str(r[0]),
                                "calls": int(r[1]),
                                "totalExecMs": float(r[2]),
                                "meanExecMs": float(r[3]),
                                "rows": int(r[4]),
                                "query": r[5],
                            }
                        )
                except Exception as exc:
                    payload["notes"].append(f"Unable to query pg_stat_statements: {exc}")

                for item in payload["topSlowQueries"][:5]:
                    q = item["query"]
                    if not q.lower().strip().startswith("select"):
                        payload["explainAnalyze"].append(
                            {
                                "queryid": item["queryid"],
                                "status": "skipped_non_select",
                                "query": q,
                            }
                        )
                        continue
                    stmt = sanitize_query_for_explain(q)
                    try:
                        cur.execute("SET LOCAL statement_timeout = '10s';")
                        cur.execute(f"EXPLAIN (ANALYZE, BUFFERS, FORMAT TEXT) {stmt}")
                        lines = [x[0] for x in cur.fetchall()]
                        payload["explainAnalyze"].append(
                            {
                                "queryid": item["queryid"],
                                "status": "ok",
                                "query": stmt,
                                "planLines": lines,
                            }
                        )
                    except Exception as exc:
                        payload["explainAnalyze"].append(
                            {
                                "queryid": item["queryid"],
                                "status": "failed",
                                "query": stmt,
                                "error": str(exc),
                            }
                        )

                # Heuristic N+1 detector from pg_stat_statements frequency profile.
                for item in payload["topSlowQueries"]:
                    q = item["query"].lower()
                    if item["calls"] >= 100 and item["meanExecMs"] <= 5.0 and " where " in q:
                        payload["nPlusOneHeuristics"].append(
                            {
                                "queryid": item["queryid"],
                                "calls": item["calls"],
                                "meanExecMs": item["meanExecMs"],
                                "query": item["query"],
                                "reason": "high call count with low per-call latency; review for potential N+1 patterns",
                            }
                        )
    finally:
        conn.close()

    with open(out_path, "w", encoding="utf8") as f:
        json.dump(payload, f, indent=2)
    print(f"[perf-db] wrote {out_path}")


if __name__ == "__main__":
    run()
