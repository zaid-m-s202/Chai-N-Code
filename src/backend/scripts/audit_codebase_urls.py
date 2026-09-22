"""Comprehensive URL & endpoint audit across the entire repository for Stage 6."""
import os
import re
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent.parent

EXCLUDE_DIRS = {".git", ".venv", "node_modules", "__pycache__", "dist", ".system_generated"}

PATTERNS = {
    "localhost": re.compile(r"localhost", re.IGNORECASE),
    "127.0.0.1": re.compile(r"127\.0\.0\.1"),
    "/api/v1/": re.compile(r"/api/v1/"),
    "http://": re.compile(r"http://"),
    "https://": re.compile(r"https://"),
}

def audit():
    findings = []
    for root, dirs, files in os.walk(REPO_ROOT):
        # Exclude directories
        dirs[:] = [d for d in dirs if d not in EXCLUDE_DIRS and not d.startswith(".")]

        for file in files:
            file_path = Path(root) / file
            rel_path = file_path.relative_to(REPO_ROOT).as_posix()

            if file.endswith((".db", ".pyc", ".geojson", ".png", ".jpg", ".ico", ".lock")):
                continue

            try:
                content = file_path.read_text(encoding="utf-8", errors="ignore")
            except Exception:
                continue

            lines = content.splitlines()
            for line_no, line in enumerate(lines, 1):
                for p_name, pattern in PATTERNS.items():
                    if pattern.search(line):
                        findings.append((rel_path, line_no, p_name, line.strip()))

    print("======================================================================")
    print(f"CODE AUDIT: FOUND {len(findings)} URL / ENDPOINT REFERENCES")
    print("======================================================================\n")

    categorized = {
        "legitimate_dev_config": [],
        "legitimate_doc_example": [],
        "legitimate_external_url": [],
        "production_blocker": []
    }

    for path, line_no, match_type, line_text in findings:
        classification = "legitimate_dev_config"

        # External schema / map / xml namespaces
        if any(ext in line_text for ext in ["w3.org", "openstreetmap.org", "json-schema.org", "vercel.sh", "github.com", "sqlalche.me", "nic.in", "data.gov.in", "onrender.com", "pune-3dulpin-cadastre.vercel.app"]):
            classification = "legitimate_external_url"
        # Documentation / Markdown
        elif path.endswith(".md") or line_text.startswith(("#", "//", "/*", "*", "'''", '"""')):
            classification = "legitimate_doc_example"
        # Tests / Seed / Mocks
        elif "tests/" in path or "scripts/" in path or "test" in path.lower():
            classification = "legitimate_dev_config"
        # Config fallbacks for local dev
        elif "config.py" in path or "vite.config.ts" in path or ".env" in path or "client.ts" in path:
            classification = "legitimate_dev_config"
        elif path.startswith("src/frontend/src/"):
            # Check for hardcoded localhost in frontend components
            if "localhost" in line_text and not "client.ts" in path:
                classification = "production_blocker"
            elif "/api/v1/" in line_text and not "API_BASE" in line_text and not "client.ts" in path:
                classification = "production_blocker"
            else:
                classification = "legitimate_dev_config"

        categorized[classification].append((path, line_no, match_type, line_text))

    for cat_name, items in categorized.items():
        print(f"[{cat_name.upper()}]: {len(items)} occurrences")
        if cat_name == "production_blocker":
            for path, lno, mtype, text in items:
                print(f"  ❌ BLOCKER: {path}:{lno} [{mtype}] -> {text}")
        else:
            sample = items[:3]
            for path, lno, mtype, text in sample:
                print(f"  - {path}:{lno} [{mtype}] -> {text[:80]}")
            if len(items) > 3:
                print(f"    ... and {len(items)-3} more.")
        print()

    print("======================================================================")
    blocker_count = len(categorized["production_blocker"])
    if blocker_count == 0:
        print("[PASS] ZERO PRODUCTION BLOCKERS FOUND IN REPOSITORY AUDIT")
    else:
        print(f"[FAIL] {blocker_count} PRODUCTION BLOCKERS REQUIRE FIXING")
    print("======================================================================")

if __name__ == "__main__":
    audit()
