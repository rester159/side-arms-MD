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
	cp $(TOP)/inc/sound.h $(TOP)/inc/hucard_score.h $(TOP)/inc/hucard_fm.h $(TOP)/inc/hucard_music.h inc/
	cp $(TOP)/src/gen/hucard_data.c $(TOP)/src/gen/hucard_fm_data.c src/_sound/
	cp $(TOP)/src/gen/hucard_pitch.s src/_sound/
clean:
	rm -rf out src/_sound inc src/rom_header.c
