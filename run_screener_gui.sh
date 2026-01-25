#!/bin/bash
# Run the Options Screener GUI
# This script handles the Qt plugin path setup automatically

cd "$(dirname "$0")"

# Activate virtual environment
source venv_qwen/bin/activate

# Clear any quarantine attributes that might block Qt plugins (macOS)
if [[ "$OSTYPE" == "darwin"* ]]; then
    xattr -r -c venv_qwen/lib/python3.12/site-packages/PyQt6/ 2>/dev/null
fi

# Run the GUI
python -m screener.ui.screener_gui
