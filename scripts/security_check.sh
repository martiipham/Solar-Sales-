#!/usr/bin/env bash
# Solar Swarm — Security Check Script
# Run before every deploy to catch common issues.
#
# Usage:
#   bash scripts/security_check.sh
#   # Or from project root: make security

set -euo pipefail

PASS=0
FAIL=0

ok()   { echo "  [OK]   $1"; ((PASS++)) || true; }
fail() { echo "  [FAIL] $1"; ((FAIL++)) || true; }
info() { echo "  [INFO] $1"; }

echo ""
echo "═══════════════════════════════════════════"
echo "  Solar Swarm — Security Check"
echo "═══════════════════════════════════════════"

# ── 1. Check .env is not committed
echo ""
echo "▶ Git / secrets"
if git ls-files --error-unmatch .env &>/dev/null 2>&1; then
    fail ".env is tracked by git — remove it with: git rm --cached .env"
else
    ok ".env is not tracked by git"
fi

if grep -rE "(sk-[a-zA-Z0-9]{20,}|xoxb-[a-zA-Z0-9-]+)" --include="*.py" --include="*.js" --include="*.jsx" . \
   --exclude-dir=.venv --exclude-dir=node_modules --exclude-dir=.git -l 2>/dev/null | grep -q .; then
    fail "Possible hardcoded API key found in source files (check above paths)"
else
    ok "No obvious hardcoded API keys in source"
fi

# ── 2. pip-audit — known CVEs in dependencies
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
    info "Then re-run this script to scan for CVEs"
fi

# ── 3. Required env vars set in .env
echo ""
echo "▶ Required environment variables"
REQUIRED_VARS=(
    "OPENAI_API_KEY"
    "GATE_API_KEY"
    "GHL_WEBHOOK_SECRET"
    "SLACK_SIGNING_SECRET"
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

# ── 4. Plaintext secrets in logs / debug output
echo ""
echo "▶ Debug / logging safety"
if grep -rn -E "(print|logger\.(info|debug|warning|error))\(.*\b(password|api_key|secret|token)\b.*=.*\)" \
   --include="*.py" --exclude-dir=.venv --exclude-dir=.git . 2>/dev/null | grep -qv "# "; then
    fail "Possible secret value printed to logs — review grep output"
else
    ok "No obvious secret logging detected"
fi

# ── 5. SQLite DB not committed
echo ""
echo "▶ Database files"
if git ls-files --error-unmatch "*.db" &>/dev/null 2>&1; then
    fail "SQLite .db file is tracked by git — add *.db to .gitignore"
else
    ok "No .db files tracked by git"
fi

# ── Summary
echo ""
echo "═══════════════════════════════════════════"
echo "  Results: ${PASS} passed / ${FAIL} failed"
echo "═══════════════════════════════════════════"
echo ""

if [ "$FAIL" -gt 0 ]; then
    exit 1
fi
