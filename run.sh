#!/usr/bin/env bash
# Job Tracker launcher
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

if ! python3 -c "import flask" 2>/dev/null; then
  echo "Installing Flask..."
  pip3 install flask --break-system-packages -q
fi

python3 app.py
