JAVA ?= $(or $(wildcard /opt/homebrew/opt/openjdk/bin/java),java)
GDK ?= $(HOME)/mars/m68k-elf
PY := .venv/bin/python
.DEFAULT_GOAL := all
.PHONY: all assets check-rom clean run
all: check-rom
	$(MAKE) assets
	$(MAKE) -f $(GDK)/makefile.gen JAVA=$(JAVA) LIBGCC="$(shell $(GDK)/bin/m68k-elf-gcc -m68000 -print-libgcc-file-name)"
	$(PY) tools/finalize_rom.py out/release/rom.bin
check-rom:
	@python3 -c "import sys;sys.path.insert(0,'tools')" && $(PY) tools/arcade_source.py
.venv/.requirements-installed: requirements.txt
	@test -x .venv/bin/python || python3 -m venv .venv
	.venv/bin/python -m pip install -q -r requirements.txt
	@touch $@
# Extraction from the hash-checked ROM set (development tools, no emulator): the inputs of the
# build_* generators. They only re-run when missing or when their extractor changed.
GEN := res/generated
EXTRACTED := $(GEN)/levels.json $(GEN)/spawns.json $(GEN)/player.json $(GEN)/sound.json
$(GEN)/levels.json: tools/extract_levels.py tools/arcade_source.py | .venv/.requirements-installed
	@mkdir -p $(GEN)
	$(PY) tools/extract_levels.py
$(GEN)/spawns.json: tools/extract_spawns.py tools/z80lite.py tools/arcade_source.py $(GEN)/levels.json | .venv/.requirements-installed
	@mkdir -p $(GEN)
	$(PY) tools/extract_spawns.py
$(GEN)/player.json: tools/extract_player.py tools/arcade_source.py | .venv/.requirements-installed
	@mkdir -p $(GEN)
	$(PY) tools/extract_player.py
$(GEN)/sound.json: tools/extract_sound.py tools/arcade_source.py | .venv/.requirements-installed
	@mkdir -p $(GEN)
	$(PY) tools/extract_sound.py
assets: .venv/.requirements-installed $(EXTRACTED)
	$(PY) tools/build_assets.py
	$(PY) tools/build_sound.py
run: all
	sh tools/launch.sh
clean:
	$(MAKE) -f $(GDK)/makefile.gen JAVA=$(JAVA) clean
	rm -rf res/generated src/gen inc/gen
