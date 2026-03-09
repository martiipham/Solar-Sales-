#!/bin/bash
# Solar Swarm — Quick Setup Script
# Run once after cloning: bash setup.sh

set -e

echo ""
echo "======================================================"
echo "  SOLAR SWARM — SETUP"
echo "======================================================"

# 1. Check Python
if ! command -v python3 &>/dev/null; then
    echo "ERROR: python3 is required. Install from python.org"
    exit 1
fi
PYVER=$(python3 --version 2>&1)
echo "  Python: $PYVER"

# 2. Install dependencies
echo ""
echo "  Installing dependencies..."
pip3 install -r requirements.txt -q

# 3. Create .env from example if not present
if [ ! -f .env ]; then
    cp .env.example .env
    echo ""
    echo "  Created .env from .env.example"
    echo "  ⚠️  Edit .env and add your API keys before starting!"
else
    echo "  .env already exists — skipping"
fi

# 4. Create output directories
mkdir -p proposals reports memory/knowledge
echo "  Directories ready: proposals/ reports/ memory/knowledge/"

# 5. Initialise database
echo ""
echo "  Initialising database..."
python3 -c "from memory.database import init_db; init_db()"

# 6. Run test-lead to verify everything works
echo ""
echo "  Running pipeline test..."
python3 cli.py test-lead

echo ""
echo "======================================================"
echo "  SETUP COMPLETE"
echo ""
echo "  Next steps:"
echo "  1. Edit .env and add your API keys:"
echo "     OPENAI_API_KEY=sk-..."
echo "     SLACK_WEBHOOK_URL=https://hooks.slack.com/..."
echo "     GHL_API_KEY=..."
echo "     GHL_LOCATION_ID=..."
echo ""
echo "  2. Start the swarm:"
echo "     python3 main.py"
echo ""
echo "  3. Check status:"
echo "     python3 cli.py swarm-status"
echo ""
echo "  4. Trigger first experiment cycle:"
echo "     python3 cli.py run-general"
echo "======================================================"
echo ""
