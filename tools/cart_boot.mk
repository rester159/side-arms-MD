# Loaded after SGDK's makefile: retain its vectors and interrupt implementation,
# but remove the controller-port heuristic before assembling the reset entry.
$(OUT_DIR)/sega.o: tools/cart_boot.py tools/cart_boot.mk $(SRC_LIB)/boot/sega.s
	@$(MKDIR) -p $(dir $@)
	python3 tools/cart_boot.py $(SRC_LIB)/boot/sega.s $(OUT_DIR)/sega.s
	$(CC) $(AFLAGS) -c $(OUT_DIR)/sega.s -o $@
