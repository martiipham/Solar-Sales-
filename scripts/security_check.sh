#!/usr/bin/env bash
# Solar Admin AI — Security Check Script
# Run before every deploy to catch common issues.
#
# Usage:
#   bash scripts/security_check.sh
#   # Or from project root: make security

set -euo pipefail

PASS=0
FAIL=0
WARN=0

ok()   { echo "  [OK]   $1"; ((PASS++)) || true; }
fail() { echo "  [FAIL] $1"; ((FAIL++)) || true; }
warn() { echo "  [WARN] $1"; ((WARN++)) || true; }
info() { echo "  [INFO] $1"; }

echo ""
echo "═══════════════════════════════════════════"
echo "  Solar Admin AI — Security Check"
echo "═══════════════════════════════════════════"

# ── 1. Git / secrets ────────────────────────────────────────────────────────
echo ""
echo "▶ Git / secrets"

if git ls-files --error-unmatch .env &>/dev/null 2>&1; then
    fail ".env is tracked by git — remove with: git rm --cached .env"
else
    ok ".env is not tracked by git"
fi

if grep -rE "(sk-[a-zA-Z0-9]{20,}|xoxb-[a-zA-Z0-9-]+)" \
   --include="*.py" --include="*.js" --include="*.jsx" \
   --exclude-dir=.venv --exclude-dir=node_modules --exclude-dir=.git \
   . 2>/dev/null | grep -q .; then
    fail "Possible hardcoded API key found in source files"
else
    ok "No obvious hardcoded API keys in source"
fi

# ── 2. Flask debug mode ──────────────────────────────────────────────────────
echo ""
echo "▶ Flask debug mode"

if grep -rn "debug=True" --include="*.py" \
   --exclude-dir=.venv --exclude-dir=.git . 2>/dev/null | grep -v "# " | grep -q .; then
    fail "Flask debug=True found in source — must be False in production"
else
    ok "No Flask debug=True detected"
fi

# ── 3. SQL injection — f-string queries ─────────────────────────────────────
echo ""
echo "▶ SQL injection risk (f-string queries)"

FSQL=$(grep -rn \
    -e 'f"INSERT' -e 'f"SELECT' -e 'f"UPDATE' -e 'f"DELETE' \
    -e "f'INSERT" -e "f'SELECT" -e "f'UPDATE" -e "f'DELETE" \
    --include="*.py" --exclude-dir=.venv --exclude-dir=.git . 2>/dev/null || true)

if echo "$FSQL" | grep -qv "table\|col_def\|cols\|assignments"; then
    # Filter out known-safe usages (table/column names from internal dicts)
    RISKY=$(echo "$FSQL" | grep -v "table\|col_def\|cols\|assignments" || true)
    if [ -n "$RISKY" ]; then
        warn "Possible f-string SQL query — review these lines:"
        echo "$RISKY" | head -20
    else
        ok "No risky f-string SQL queries detected"
    fi
else
    ok "No f-string SQL queries detected"
fi

# ── 4. Dependency vulnerabilities (pip-audit) ───────────────────────────────
echo ""
echo "▶ Dependency vulnerabilities (pip-audit)"

if command -v pip-audit &>/dev/null; then
    if pip-audit -r requirements.txt --no-deps -q 2>/dev/null; then
        ok "No known CVEs in requirements.txt"
    else
        fail "Vulnerable packages found — review pip-audit output above"
    fi
else
    info "pip-audit not installed — run: pip install pip-audit"
fi

# ── 5. Required environment variables ───────────────────────────────────────
echo ""
echo "▶ Required environment variables"

REQUIRED_VARS=(
    "OPENAI_API_KEY"
    "GATE_API_KEY"
    "GHL_WEBHOOK_SECRET"
    "SLACK_SIGNING_SECRET"
    "RETELL_WEBHOOK_SECRET"
    "JWT_SECRET"
)

if [ -f .env ]; then
    for var in "${REQUIRED_VARS[@]}"; do
        if grep -qE "^${var}=.+" .env 2>/dev/null; then
            ok "${var} is set"
        else
            fail "${var} is missing or empty in .env"
        fi
    done
else
    info ".env file not found — skipping env var checks"
fi

# ── 6. Debug / logging safety ────────────────────────────────────────────────
echo ""
echo "▶ Debug / logging safety"

if grep -rn -E "(print|logger\.(info|debug|warning|error))\(.*\b(password|api_key|secret|token)\b.*=.*\)" \
   --include="*.py" --exclude-dir=.venv --exclude-dir=.git . 2>/dev/null | grep -qv "# "; then
    warn "Possible secret value printed to logs — review output above"
else
    ok "No obvious secret logging detected"
fi

# ── 7. Database files not committed ──────────────────────────────────────────
echo ""
echo "▶ Database / build files"

if git ls-files --error-unmatch "*.db" &>/dev/null 2>&1; then
    fail "SQLite .db file is tracked by git — add *.db to .gitignore"
else
    ok "No .db files tracked by git"
fi

if git ls-files --error-unmatch "*.sqlite" &>/dev/null 2>&1; then
    fail "SQLite .sqlite file is tracked by git — add *.sqlite to .gitignore"
else
    ok "No .sqlite files tracked by git"
fi

# ── Summary ──────────────────────────────────────────────────────────────────
echo ""
echo "═══════════════════════════════════════════"
printf "  Results: %d passed / %d warnings / %d failed\n" "$PASS" "$WARN" "$FAIL"
echo "═══════════════════════════════════════════"
echo ""

if [ "$FAIL" -gt 0 ]; then
    exit 1
fi
