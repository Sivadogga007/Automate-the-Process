#!/bin/sh
set -eu
cd "$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)"
if ! command -v python3 >/dev/null 2>&1; then
    echo 'Install Python 3.11 or newer, then run this launcher again.'
    exit 1
fi
python3 -c 'import sys; sys.exit(0 if sys.version_info >= (3,11) else "Python 3.11 or newer is required")'
if [ ! -x .venv/bin/python ]; then
    python3 -m venv .venv || { echo 'Could not create the environment. On Linux, install your distribution python3-venv package.'; exit 1; }
fi
exec .venv/bin/python launch.py "$@"
