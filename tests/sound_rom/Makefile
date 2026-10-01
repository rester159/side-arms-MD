# Standalone sound test cartridge: the real driver (../../src/sound, ../../inc/sound.h) plus the
# generated data (../../src/gen/sound_data.s from tools/build_sound.py) and a tiny jukebox main.
# Built by tools/sound_test.py; `make` here works too after `make assets` in the project root.
GDK ?= $(HOME)/mars/m68k-elf
JAVA ?= $(or $(wildcard /opt/homebrew/opt/openjdk/bin/java),java)
TOP := ../..
.PHONY: all sync clean
all: sync
	$(MAKE) -f $(GDK)/makefile.gen JAVA=$(JAVA) LIBGCC="$(shell $(GDK)/bin/m68k-elf-gcc -m68000 -print-libgcc-file-name)"
sync:
	@mkdir -p src/_sound inc
	cp $(TOP)/src/sound/* src/_sound/
	cp $(TOP)/src/gen/sound_data.s src/_sound/sound_data.s
	cp $(TOP)/inc/sound.h inc/sound.h
clean:
	rm -rf out src/_sound inc src/rom_header.c
