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
cd "$dst"
GDK=${GDK:-$HOME/mars/m68k-elf}
JAVA=$(ls /opt/homebrew/opt/openjdk/bin/java 2>/dev/null || echo java)
.venv/bin/python tools/build_assets.py > /dev/null
rm -f out/release/rom.bin out/release/rom.out
make -f "$GDK/makefile.gen" -f tools/cart_boot.mk JAVA="$JAVA" LIBGCC="$("$GDK"/bin/m68k-elf-gcc -m68000 -print-libgcc-file-name)" 2>&1 | grep -E "error|warning: (impl|incompatible)" || true
test -f out/release/rom.bin || { echo "BUILD FAILED" >&2; exit 1; }
.venv/bin/python tools/finalize_rom.py out/release/rom.bin
echo "$dst/out/release/rom.bin"
