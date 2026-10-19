# Loaded after SGDK's makefile: retain its vectors and interrupt implementation,
# but remove the controller-port heuristic before assembling the reset entry.
# Favor compact front-end and mode-management code over unrolled code.
$(OUT_DIR)/src/flow_menu.o: CFLAGS += -Os
$(OUT_DIR)/src/flow_menu.o: tools/cart_boot.mk
$(OUT_DIR)/src/flow_scene.o: CFLAGS += -Os
$(OUT_DIR)/src/flow_scene.o: tools/cart_boot.mk
$(OUT_DIR)/src/flow.o $(OUT_DIR)/src/flow_attract.o $(OUT_DIR)/src/flow_rush.o: CFLAGS += -Os
$(OUT_DIR)/src/flow.o $(OUT_DIR)/src/flow_attract.o $(OUT_DIR)/src/flow_rush.o: tools/cart_boot.mk
# The final Vivid pass updates this incbin after data.s has been generated.
$(OUT_DIR)/src/gen/data.o: res/generated/vivid_lut.bin

# Supply joy.o before libmd.a so its archive member is not pulled in. This
# guards the SDK's nullable Team Player callback during reset as well as play.
OBJS += $(OUT_DIR)/joy_safe.o
# Correct every SDK driver upload, including startup before main and the PCM
# logo driver, rather than waiting for the v1.4 idle hook to repair it later.
OBJS += $(OUT_DIR)/z80_safe.o
$(OUT_DIR)/cmd_: $(OUT_DIR)/z80_safe.o
$(OUT_DIR)/z80_safe.o: tools/guard_z80_upload.py $(SRC_LIB)/z80_ctrl.c
	@$(MKDIR) -p $(dir $@)
	python3 tools/guard_z80_upload.py $(SRC_LIB)/z80_ctrl.c $(OUT_DIR)/z80_safe.c
	$(CC) $(CFLAGS) -c $(OUT_DIR)/z80_safe.c -o $@

$(OUT_DIR)/cmd_: $(OUT_DIR)/joy_safe.o
$(OUT_DIR)/joy_safe.o: tools/guard_joy_callback.py $(SRC_LIB)/joy.c
	@$(MKDIR) -p $(dir $@)
	python3 tools/guard_joy_callback.py $(SRC_LIB)/joy.c $(OUT_DIR)/joy_safe.c
	$(CC) $(CFLAGS) -c $(OUT_DIR)/joy_safe.c -o $@

$(OUT_DIR)/sega.o: tools/cart_boot.py tools/cart_boot.mk $(SRC_LIB)/boot/sega.s
	@$(MKDIR) -p $(dir $@)
	python3 tools/cart_boot.py $(SRC_LIB)/boot/sega.s $(OUT_DIR)/sega.s
	$(CC) $(AFLAGS) -c $(OUT_DIR)/sega.s -o $@

# Fill existing pre-sound padding with small palettes. The R5 map remains
# after sound; grouping it with the palettes would overflow this padding.
OBJS := $(OUT_DIR)/src/gen/bc_background_palettes.o $(OUT_DIR)/src/gen/early_palettes.o $(OUT_DIR)/src/gen/wheel_cracks.o $(OUT_DIR)/src/gen/sound_data.o $(filter-out $(OUT_DIR)/src/gen/bc_background_palettes.o $(OUT_DIR)/src/gen/early_palettes.o $(OUT_DIR)/src/gen/wheel_cracks.o $(OUT_DIR)/src/gen/sound_data.o,$(OBJS))
