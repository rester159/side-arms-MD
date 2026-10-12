#!/bin/sh
# Build a private snapshot of the tree so parallel workers don't race on out/.
# usage: tools/agent_build.sh NAME   -> .local/build-NAME/out/release/rom.bin
set -eu
name=${1:?name}
root=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)
dst="$root/.local/build-$name"
mkdir -p "$dst"
rsync -a --delete --exclude out --exclude .venv --exclude reports --exclude reference --exclude .local --exclude rom "$root/" "$dst/"
ln -sfn "$root/.venv" "$dst/.venv"
ln -sfn "$root/rom" "$dst/rom"
mkdir -p "$dst/.local"
ln -sfn "$root/.local/pce-reference" "$dst/.local/pce-reference"
mkdir -p "$dst/.local/pce-hucard"
ln -sfn "$root/.local/pce-hucard/SideArms - Hyper Dyne (USA).pce" "$dst/.local/pce-hucard/SideArms - Hyper Dyne (USA).pce"
cd "$dst"
rm -f out/release/rom.bin out/release/rom.out
if ! make > build.log 2>&1; then
    tail -40 build.log >&2
    echo "BUILD FAILED: $dst/build.log" >&2
    exit 1
fi
test -f out/release/rom.bin || { echo "BUILD FAILED" >&2; exit 1; }
echo "$dst/out/release/rom.bin"
