#!/usr/bin/env bash
# Apex Harness launcher — resolves symlinks so a global install
# (e.g. ln -s ~/test/apex ~/.local/bin/apex) finds the real script dir.
set -e
SELF="$(readlink -f "${BASH_SOURCE[0]}")"
DIR="$(cd "$(dirname "$SELF")" && pwd)"
exec python3 "${DIR}/apex_harness.py" "$@"
