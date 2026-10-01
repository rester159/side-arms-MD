-- Development-only arcade probe for the sound port check (tools/sound_test.py). Nothing here enters
-- the cartridge. Like re_sound.lua, but takes a command SCHEDULE and logs what the port check needs.
-- Env: SA_SEQ  "frame:cmd,frame:cmd,..." (hex cmd; frame relative to the start, after SA_WARM frames).
--              The main CPU's latch write ($C800, once per VBLANK) is forced to cmd for that one frame,
--              $FF otherwise, i.e. exactly what the game's ring pop at $0071 produces.
--      SA_SECS seconds to record, SA_WARM warm-up frames (default 120), SA_OUT log path.
-- Log lines (t = s since the start):
--   I|t|c000      Timer-A IRQ (chip 1 reg $27 write at $0038), c000 = tick counter before its increment
--   L|t|value     the IRQ's latch read ($00AD reads $D000)
--   W|t|chip|reg|data  YM2203 write; SSG regs $00-$0D only when the value changes
local m = manager.machine
local mainp = m.devices[':maincpu'].spaces.program
local ap = m.devices[':audiocpu'].spaces.program
local secs = tonumber(os.getenv('SA_SECS') or '8')
local warm = tonumber(os.getenv('SA_WARM') or '120')
local out = assert(io.open(os.getenv('SA_OUT') or 'seq.log', 'w'))
local seq = {}
for f, c in string.gmatch(os.getenv('SA_SEQ') or '', '(%d+):(%x+)') do seq[tonumber(f)] = tonumber(c, 16) end

local force = 0xff
local t0 = nil
local function now() return m.time:as_double() end
local function rel() return now() - t0 end
local taps = {}
taps[#taps + 1] = mainp:install_write_tap(0xc800, 0xc800, 'latch', function(off, data, mask) return force end)
local addr = { [1] = 0, [2] = 0 }
local ssg = { [1] = {}, [2] = {} }
taps[#taps + 1] = ap:install_write_tap(0xf000, 0xf003, 'ym', function(off, data, mask)
  local chip = (off >= 0xf002) and 2 or 1
  if (off & 1) == 0 then addr[chip] = data; return end
  if not t0 then return end
  local r = addr[chip]
  if chip == 1 and r == 0x27 then out:write(string.format('I|%.6f|%d\n', rel(), ap:read_u8(0xc000))) end
  if r < 0x0e then
    if ssg[chip][r] == data then return end
    ssg[chip][r] = data
  end
  out:write(string.format('W|%.6f|%d|%02x|%02x\n', rel(), chip, r, data))
end)
taps[#taps + 1] = ap:install_read_tap(0xd000, 0xd000, 'latchr', function(off, data, mask)
  if t0 then out:write(string.format('L|%.6f|%02x\n', rel(), data)) end
end)

for f = 1, warm do emu.wait_next_update() end
t0 = now()
out:write(string.format('# seq=%s warm=%d secs=%g t0_abs=%.6f\n', os.getenv('SA_SEQ') or '', warm, secs, t0))
local frame = 0
while rel() < secs do
  force = seq[frame] or 0xff
  emu.wait_next_update()
  frame = frame + 1
end
out:write('COMPLETE\n'); out:close()
m:exit()
