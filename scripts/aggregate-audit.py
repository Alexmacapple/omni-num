#!/usr/bin/env python3
"""Agrege les zone-*-r1.json en audit-results.json (skill sg-code-audit Phase 6)."""
from __future__ import annotations

import json
import re
import subprocess
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path

RESULTS_DIR = Path(".code-audit-results")

VALID_SEVERITIES = {"critical", "high", "medium", "low"}
SEVERITY_MAP = {"CRITICAL": "critical", "Critical": "critical",
                "HIGH": "high", "High": "high", "serious": "high",
                "MEDIUM": "medium", "Medium": "medium", "warning": "medium", "moderate": "medium",
                "LOW": "low", "Low": "low", "info": "low", "minor": "low", "trivial": "low", "style": "low"}

VALID_CATEGORIES = {"security", "race-condition", "silent-exception", "api-guard",
                    "resource-leak", "type-mismatch", "dead-code", "infra",
                    "ssr-hydration", "input-validation", "error-handling",
                    "performance", "accessibility", "logic-error", "other"}
CATEGORY_MAP = {"error_handling": "error-handling",
                "bare_except": "silent-exception", "except_pass": "silent-exception",
                "except-pass": "silent-exception", "swallowed-exception": "silent-exception",
                "auth": "security", "auth-bypass": "security", "xss": "security",
                "injection": "security", "secrets": "security",
                "null-check": "api-guard", "null_check": "api-guard",
                "missing-guard": "api-guard", "unused": "dead-code",
                "unused-code": "dead-code", "unreachable": "dead-code",
                "hydration": "ssr-hydration", "ssr": "ssr-hydration",
                "csr-mismatch": "ssr-hydration", "validation": "input-validation",
                "sanitization": "input-validation", "leak": "resource-leak",
                "unclosed": "resource-leak", "memory-leak": "resource-leak",
                "types": "type-mismatch", "type_mismatch": "type-mismatch",
                "schema": "type-mismatch", "docker": "infra", "ci": "infra",
                "build": "infra", "env": "infra", "perf": "performance",
                "n+1": "performance", "re-render": "performance",
                "a11y": "accessibility", "aria": "accessibility",
                "contrast": "accessibility", "race": "race-condition",
                "concurrency": "race-condition", "toctou": "race-condition",
                "off-by-one": "logic-error", "wrong-condition": "logic-error",
                "algorithm": "logic-error"}


def normalize_severity(s: str) -> str:
    s = (s or "").strip()
    if s in VALID_SEVERITIES:
        return s
    return SEVERITY_MAP.get(s, "medium")


def normalize_category(c: str) -> str:
    c = (c or "").strip().lower()
    if c in VALID_CATEGORIES:
        return c
    return CATEGORY_MAP.get(c, "other")


def dedup(bugs: list[dict]) -> list[dict]:
    groups: dict[tuple[str, str], list[dict]] = defaultdict(list)
    for b in bugs:
        title = re.sub(r"\s+", " ", (b.get("title") or "").strip().lower())
        key = (b.get("file", ""), title)
        groups[key].append(b)
    result = []
    severity_rank = {"critical": 3, "high": 2, "medium": 1, "low": 0}
    for key, items in groups.items():
        items.sort(key=lambda x: severity_rank.get(x["severity"], 0), reverse=True)
        keeper = items[0]
        if len(items) > 1:
            keeper["occurrence_count"] = len(items)
        result.append(keeper)
    return result


def derive_route(file_path: str, title: str) -> tuple[str, str] | None:
    p = file_path.strip()
    if p.startswith("omnistudio/routers/"):
        name = Path(p).stem
        mapping = {
            "assign": "/omni/steps/{id}/assign",
            "audio": "/omni/steps/{id}/audio",
            "auth_routes": "/omni/auth/*",
            "clean": "/omni/steps/{id}/clean",
            "export": "/omni/export/*",
            "generate": "/omni/steps/{id}/generate",
            "import_steps": "/omni/import",
            "sessions": "/omni/sessions/*",
            "status": "/omni/status/*",
            "voices": "/omni/voices/*",
        }
        return mapping.get(name, f"/omni/{name}"), f"Router {name}"
    if p.startswith("omnistudio/frontend/out/"):
        return "/omni/ (frontend SPA)", "Frontend DSFR"
    if p in ("omnistudio/server.py", "omnistudio/auth.py"):
        return "/omni/* (tout)", "App root"
    if p.startswith("omnistudio/graph/"):
        return "/omni/steps/* (workflow)", "Graph LangGraph"
    return None


def main() -> None:
    zone_files = sorted(RESULTS_DIR.glob("zone-*-r1.json"))
    all_bugs: list[dict] = []
    total_files_audited = 0
    norm_sev = 0
    norm_cat = 0

    for zf in zone_files:
        with zf.open() as f:
            data = json.load(f)
        total_files_audited += data.get("files_audited", 0)
        for bug in data.get("bugs", []):
            orig_sev = bug.get("severity", "")
            new_sev = normalize_severity(orig_sev)
            if new_sev != orig_sev:
                norm_sev += 1
            bug["severity"] = new_sev
            orig_cat = bug.get("category", "")
            new_cat = normalize_category(orig_cat)
            if new_cat != orig_cat:
                norm_cat += 1
            bug["category"] = new_cat
            all_bugs.append(bug)

    pre_dedup = len(all_bugs)
    all_bugs = dedup(all_bugs)
    dedup_count = pre_dedup - len(all_bugs)

    by_severity = Counter(b["severity"] for b in all_bugs)
    by_category = Counter(b["category"] for b in all_bugs)
    files_modified_set = {b["file"] for b in all_bugs if b.get("fix_applied")}

    routes_agg: dict[str, dict] = {}
    severity_rank = {"critical": 3, "high": 2, "medium": 1, "low": 0}
    for b in all_bugs:
        r = derive_route(b.get("file", ""), b.get("title", ""))
        if not r:
            continue
        route, reason = r
        existing = routes_agg.get(route)
        if existing is None or severity_rank[b["severity"]] > severity_rank[existing["severity"]]:
            routes_agg[route] = {
                "route": route,
                "reason": f"{b.get('title','')} ({b.get('file','')})",
                "severity": b["severity"],
            }
    impacted_routes = sorted(routes_agg.values(),
                             key=lambda r: severity_rank[r["severity"]], reverse=True)

    try:
        head_sha = subprocess.check_output(
            ["git", "rev-parse", "HEAD"], text=True).strip()
    except Exception:
        head_sha = ""

    result = {
        "repo": "omni-num",
        "timestamp": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "mode": "standard",
        "rounds": 1,
        "agents": len(zone_files),
        "scope_info": {"mode": "full"},
        "summary": {
            "total_bugs": len(all_bugs),
            "by_severity": {
                "critical": by_severity.get("critical", 0),
                "high": by_severity.get("high", 0),
                "medium": by_severity.get("medium", 0),
                "low": by_severity.get("low", 0),
            },
            "by_category": {cat: by_category.get(cat, 0) for cat in sorted(VALID_CATEGORIES)},
            "files_audited": total_files_audited,
            "files_modified": len(files_modified_set),
            "duration_ms": 195171,
        },
        "head_sha": head_sha,
        "impacted_routes": impacted_routes,
        "bugs": all_bugs,
    }

    out = RESULTS_DIR / "audit-results.json"
    with out.open("w") as f:
        json.dump(result, f, indent=2, ensure_ascii=False)

    print(f"Audit-results.json ecrit: {out}")
    print(f"Total bugs: {len(all_bugs)} (pre-dedup {pre_dedup}, deduped {dedup_count})")
    print(f"Normalises: severity {norm_sev}, category {norm_cat}")
    print(f"Par severite: {dict(by_severity)}")
    print(f"Top 5 categories: {by_category.most_common(5)}")
    print(f"Files audited: {total_files_audited} | modified: {len(files_modified_set)}")
    print(f"Routes impactees: {len(impacted_routes)}")


if __name__ == "__main__":
    main()
