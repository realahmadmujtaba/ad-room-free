#!/usr/bin/env bash
# One-command local setup for The AD Room (free tier, no credit card).
#   ./setup.sh
# Assumes .env is filled in.

set -euo pipefail

say()  { printf "\n\033[1;36m==> %s\033[0m\n" "$1"; }
fail() { printf "\n\033[1;31mFAILED: %s\033[0m\n" "$1"; exit 1; }

[ -f .env ] || fail ".env not found. Run: cp .env.example .env  then fill it in."

set -a; . ./.env; set +a
for var in GOOGLE_API_KEY CLICKHOUSE_HOST CLICKHOUSE_PASSWORD; do
  val="${!var:-}"
  case "$val" in
    ""|paste-*|your-*|xxxxxxxx*) fail "$var is not set in .env" ;;
  esac
done

say "Creating virtualenv"
PYTHON=""
for candidate in python3 python; do
  if "$candidate" -c "" >/dev/null 2>&1; then
    PYTHON="$candidate"
    break
  fi
done
[ -n "$PYTHON" ] || fail "No working Python interpreter found (tried python3, python)."
[ -d .venv ] || "$PYTHON" -m venv .venv
# shellcheck disable=SC1091
if [ -f .venv/bin/activate ]; then
  . .venv/bin/activate
else
  . .venv/Scripts/activate
fi

say "Installing dependencies (2-3 minutes)"
python -m pip install -q --upgrade pip
python -m pip install -q -r requirements.txt

say "Testing the free Gemini API key"
python - <<'PY'
import sys
sys.path.insert(0, "src")
import config
from google import genai
try:
    c = genai.Client(api_key=config.GOOGLE_API_KEY)
    r = c.models.generate_content(model=config.MODEL_FLASH, contents="Reply with one word: ready")
    print(f"    {config.MODEL_FLASH} -> {r.text.strip()}")
except Exception as exc:
    print(f"    Gemini call failed: {exc}")
    raise SystemExit(1)
PY

say "Testing the ClickHouse connection"
python - <<'PY'
import sys
sys.path.insert(0, "src")
import ch
print("    ClickHouse version:", ch.query("SELECT version() AS v")[0]["v"])
PY

say "Building schema and seeding the demo screenplay"
python scripts/init_db.py --seed

say "Smoke test: asking the agent a real question"
python src/agent.py "Give me the overview, then the three biggest scheduling risks and why."

say "Done. Start the UI with:  streamlit run streamlit_app.py"
