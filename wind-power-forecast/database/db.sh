#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(cd "${SCRIPT_DIR}/.." && pwd)"
PYTHON_EXE="${PYTHON_EXE:-python}"

cd "${PROJECT_DIR}"
exec "${PYTHON_EXE}" backend/manage_db.py "$@"
