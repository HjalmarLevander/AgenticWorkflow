#!/usr/bin/env bash
# Populates style_vault/ with the reference repos the Engineer agent's RAG
# (backend/style_vault.py) indexes for style grounding. style_vault/ itself
# is gitignored (third-party code, no reason to carry it in this repo's
# history) -- run this once after cloning, then `ingest()` picks it up.
set -euo pipefail

cd "$(dirname "${BASH_SOURCE[0]}")/.."
mkdir -p style_vault
cd style_vault

clone_shallow() {
  local url="$1" dir="$2"
  if [ -d "$dir" ]; then
    echo "skip $dir (already present)"
  else
    git clone --depth 1 "$url" "$dir"
    rm -rf "$dir/.git"
  fi
}

clone_shallow https://github.com/cosmicpython/book cosmicpython-book
clone_shallow https://github.com/cp-algorithms/cp-algorithms cp-algorithms
clone_shallow https://github.com/jrjohansson/scientific-python-lectures scientific-python-lectures
clone_shallow https://github.com/TheAlgorithms/Python thealgorithms-python

echo
echo "NOTE: style_vault/tomaugspurger/modern-1-intro.txt is a manually saved"
echo "excerpt (Tom Augspurger's 'Modern Pandas' post), not a repo clone --"
echo "add it back by hand if you want it: https://tomaugspurger.net/posts/modern-1-intro/"
echo
echo "Done. Run ingest() in backend/style_vault.py (or restart the server) to embed."
