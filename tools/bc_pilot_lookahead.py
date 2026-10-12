"""Host-side Genesis-core snapshots for controller search, never ROM game rules.

Search results must be replayed without restores before claiming natural campaign
coverage. Captures Python-side Runner display/frame state as well as the core.
"""
import ctypes as C

class PilotSnapshot:
    def __init__(self, runner):
        self.runner = runner
        lib = runner.lib
        lib.retro_serialize_size.argtypes = []
        lib.retro_serialize_size.restype = C.c_size_t
        lib.retro_serialize.argtypes = [C.c_void_p, C.c_size_t]
        lib.retro_serialize.restype = C.c_bool
        lib.retro_unserialize.argtypes = [C.c_void_p, C.c_size_t]
        lib.retro_unserialize.restype = C.c_bool
        self.size = lib.retro_serialize_size()
        assert 0 < self.size < 16 * 1024 * 1024
        self.core = C.create_string_buffer(self.size)
        assert lib.retro_serialize(self.core, self.size), 'core snapshot failed'
        self.frames, self.mask = runner.frames, runner.mask
        self.frame = runner.frame.copy()

    def restore(self, target=None):
        target = self.runner if target is None else target
        target.lib.retro_unserialize.argtypes = [C.c_void_p, C.c_size_t]
        target.lib.retro_unserialize.restype = C.c_bool
        assert target.lib.retro_unserialize(self.core, self.size), 'core restore failed'
        target.frames, target.mask = self.frames, self.mask
        target.frame = self.frame.copy()


def rapid_forecast_pads(proposed_pads, previous_held, fire_sides, tick):
    """Forecast the pilot's known 3-on/3-off rhythm; hold movement and fire side fixed.

    Call only after the first speculative update, whose exact proposed button
    edges must be preserved. This is controller planning, never game state.
    """
    assert len(proposed_pads) == 8 and len(previous_held) == len(fire_sides) == 4
    assert all(side in (0, 0x10, 0x20) for side in fire_sides)
    pads = bytearray(8)
    for i, side in enumerate(fire_sides):
        held = (proposed_pads[2*i] & ~0x30) | (side if tick % 6 < 3 else 0)
        pads[2*i] = held
        pads[2*i+1] = held & ~previous_held[i]
    return pads


def choose_move(runner, layout, proposed, previous, target, horizon=4, survival_tiebreak=False, statistics=None, player_index=0, party_pads=None, rapid_fire_sides=None):
    """Evaluate nine directions for one controller; return only its selected input.

    Forecast holds current fire unless the optional known rapid-fire sides are supplied.
    Keep the heuristic move if it survives; otherwise death outranks target
    distance among alternatives. Optional survival tie-breaking prefers the
    latest predicted death when every direction dies. Does not change
    cartridge code or CPU speed.
    """
    # Never restore a speculative branch into the authoritative instance.
    # The libretro serializer does not preserve its exact VBlank CPU phase.
    if not hasattr(runner, '_pilot_shadow'):
        import tempfile, shutil
        from pathlib import Path
        from run_rom import Runner, CORE
        runner._pilot_shadow_dir = tempfile.TemporaryDirectory(prefix='bc-pilot-core-')
        core = Path(runner._pilot_shadow_dir.name)/'prediction.dylib'
        shutil.copyfile(CORE, core)
        runner._pilot_shadow = Runner(core=core)
        assert C.addressof(runner.ram) != C.addressof(runner._pilot_shadow.ram), 'cores share RAM'
    live = runner
    assert 0 <= player_index < live.u16('dbg_bc_native_players')
    peer_inputs = bytes(8) if party_pads is None else bytes(party_pads)
    assert len(peer_inputs) == 8
    snapshot = PilotSnapshot(live)
    runner = live._pilot_shadow
    snapshot.restore(runner)
    address = (runner.symbols['player'] if player_index == 0 else
               runner.u32('peers') + (player_index - 1) * layout.o['bc_player_size'])
    def read(offset, n):
        return bytes(runner.ram[((address+offset+k)&65535)^1] for k in range(n))
    if read(layout.o['bc_state'], 1)[0] != 0x80:
        return proposed
    best = None
    old_best = None
    if statistics is not None:statistics["calls"] = statistics.get("calls",0)+1
    directions = [proposed & 15] + [d for d in (0,1,2,4,5,6,8,9,10) if d != proposed & 15]
    runner._pilot_search = True
    try:
        for direction in directions:
            snapshot.restore(runner)
            start_tick = runner.u32('dbg_bc_native_ticks')
            bits = direction | (proposed & 0x30)
            old, last_tick = previous, -1
            previous_peer_held = bytes(peer_inputs[::2])
            died = False
            for _ in range(horizon * 8 + 24):
                tick = runner.u32('dbg_bc_native_ticks')
                if tick - start_tick >= horizon:break
                if tick != last_tick:
                    pads = bytearray(peer_inputs)
                    # Peers hold their proposed inputs; only the first simulated
                    # update receives their new button edges.
                    if last_tick != -1:
                        if rapid_fire_sides is None:
                            pads[1::2] = bytes(4)
                        else:
                            pads = rapid_forecast_pads(peer_inputs, previous_peer_held,
                                                       rapid_fire_sides, tick)
                            bits = direction | (pads[2*player_index] & 0x30)
                    pads[2*player_index:2*player_index+2] = bytes([bits, bits & ~old])
                    previous_peer_held = bytes(pads[::2])
                    runner.write('pad', pads)
                    old, last_tick = bits, tick
                runner.run(1)
                if read(layout.o['bc_state'],1)[0] != 0x80:
                    died = True;break
                if runner.u16('dbg_bc_native_status') not in (0,4):break
            if direction == (proposed & 15) and not died:
                return proposed
            x,y = (int.from_bytes(read(offset,4),'big') >> 8 for offset in (0,4))
            distance = (x-target[0])**2 + (y-target[1])**2
            old_score = (died,distance)
            if old_best is None or old_score < old_best[0]:old_best = (old_score,bits)
            survival = runner.u32('dbg_bc_native_ticks')-start_tick
            score = (died,-survival if died and survival_tiebreak else 0,distance)
            if best is None or score < best[0]:best = (score,bits)
    finally:
        snapshot.restore(runner)
        runner._pilot_search = False
    if statistics is not None and best[0][0]:
        statistics["all_directions_predict_death"] = statistics.get("all_directions_predict_death",0)+1
        if best[1]!=old_best[1]:statistics["survival_changed_choice"] = statistics.get("survival_changed_choice",0)+1
    # Forecasts may end in a later rapid-fire phase; apply the selected
    # direction with the fire bits used by its first simulated update.
    return (best[1] & 15) | (proposed & 0x30)


def machine_checkpoint(runner):
    """Read-only endpoint diagnostics; no RAM normalization or ignored ranges."""
    import hashlib
    get = runner.lib.m68k_get_reg
    get.argtypes, get.restype = [C.c_uint], C.c_uint32
    registers = [get(i) for i in range(18)]
    return dict(registers=registers, sp=registers[15]&0xffffff,
                pc=registers[16],
                vram_sha256=hashlib.sha256(bytes(runner.vram)).hexdigest(),
                pixels_sha256=hashlib.sha256(runner.frame.tobytes()).hexdigest(),
                frames=runner.frames,tick=runner.u32('dbg_bc_native_ticks'))
