#!/bin/bash
cd "$(dirname "$0")"
python3 scripts/cleanup.py --apply
echo
read -p "Press Enter to close..."
