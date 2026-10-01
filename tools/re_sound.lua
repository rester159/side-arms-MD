-- Development-only sound probe for Side Arms (MAME 'sidearms'). Nothing here enters the cartridge.
-- Triggers ONE sound command in isolation and logs every YM2203 register write.
-- Env: SA_CMD   sound command (hex, e.g. "21")
--      SA_SECS  seconds of emulated time to record after the command (default 8)
--      SA_WARM  warm-up frames before the command (default 120)
--      SA_OUT   output log path (default cmd.log)
-- Method: a write tap on the main CPU's sound latch ($C800) overrides every value the game
-- writes (the game writes one ring entry or $FF per VBLANK, hardware.md). We force $FF during
-- warm-up, then the command for 2 frames, then $FF again. The sound driver only acts when the
-- latch value changes (a_04k $00A9: cmp with $C001), so a held value fires exactly once.
-- Log lines:
--   W|t|chip|reg|data   YM2203 register write (chip 1 = $F000/1, chip 2 = $F002/3), t = s since command.
--                       SSG regs $00-$0D are logged only when the value changes (the driver rewrites
--                       all 11 SSG regs of both chips every tick, a_04k $0BFF).
--   R|t|addr|byte       sequence-data read by the sound CPU from ROM $1429-$7FFF (stream position)
--   I|t                 Timer-A IRQ (detected as chip1 reg $27 write, done once per IRQ at $0038)
local m = manager.machine
local mainp = m.devices[':maincpu'].spaces.program
local acpu = m.devices[':audiocpu']
local ap = acpu.spaces.program
local cmd = tonumber(os.getenv('SA_CMD') or '0', 16)
local secs = tonumber(os.getenv('SA_SECS') or '8')
local warm = tonumber(os.getenv('SA_WARM') or '120')
local out = assert(io.open(os.getenv('SA_OUT') or 'cmd.log', 'w'))

local force = 0xff
local t0 = nil
local function now() return m.time:as_double() end
local function rel() return t0 and (now() - t0) or -1 end

local taps = {}
taps[#taps + 1] = mainp:install_write_tap(0xc800, 0xc800, 'latch', function(off, data, mask)
  return force
end)
local addr = { [1] = 0, [2] = 0 }
local ssg = { [1] = {}, [2] = {} }  -- last value of SSG regs $00-$0D (driver rewrites them every tick)
taps[#taps + 1] = ap:install_write_tap(0xf000, 0xf003, 'ym', function(off, data, mask)
  local chip = (off >= 0xf002) and 2 or 1
  if (off & 1) == 0 then addr[chip] = data
  else
    if t0 then
      if chip == 1 and addr[1] == 0x27 then out:write(string.format('I|%.6f\n', rel())) end
      local r = addr[chip]
      if r < 0x0e then
        if ssg[chip][r] == data then return end
        ssg[chip][r] = data
      end
      out:write(string.format('W|%.6f|%d|%02x|%02x\n', rel(), chip, r, data))
    end
  end
end)
taps[#taps + 1] = ap:install_read_tap(0x1429, 0x7fff, 'seq', function(off, data, mask)
  if t0 then out:write(string.format('R|%.6f|%04x|%02x\n', rel(), off, data)) end
end)

for f = 1, warm do emu.wait_next_update() end
out:write(string.format('# cmd=%02x warm_frames=%d t0_abs=%.6f\n', cmd, warm, now()))
force = cmd
t0 = now()
emu.wait_next_update(); emu.wait_next_update()
force = 0xff
while now() - t0 < secs do emu.wait_next_update() end
out:write(string.format('# last_cmd_seen_by_audiocpu=%02x\n', ap:read_u8(0xc001)))
out:write('COMPLETE\n'); out:close()
m:exit()
