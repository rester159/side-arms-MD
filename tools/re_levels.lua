-- Development-only stage probe (levels RE). Nothing here enters the cartridge.
-- Uses the game's own debug DIPs (see docs/re/levels.md):
--   DSW0 ($C803) bit7 = 0 after reset -> debug; DSW0 bit0 = 0 (+bit7) -> invincible ($2648/$2AFC/$2E41),
--   DSW0 bit1 = 0 (+bit7) -> scroll coords on text layer ($2140), DSW0 bit4 = 0 (+bit7) -> full power ($1D8E)
--   DSW1 ($C804) low nibble (inverted) -> start entry of table $15B4 (read at $1594).
-- Env: SA_STAGE (1..10), SA_FRAMES, SA_SNAP, SA_POWER (1 = full power), SA_UNSTICK (frames of halt
--      before forcing $E080=$80; 0 = never).
local m = manager.machine
local cpu = m.devices[':maincpu']
local p = cpu.spaces.program
local stage = tonumber(os.getenv('SA_STAGE') or '1')
local frames = tonumber(os.getenv('SA_FRAMES') or '6000')
local snap = tonumber(os.getenv('SA_SNAP') or '60')
local power = tonumber(os.getenv('SA_POWER') or '1')
local unstick = tonumber(os.getenv('SA_UNSTICK') or '0')
local out = assert(io.open('events.txt', 'w'))
local ports = m.ioport.ports

local function field(port, name) return assert(ports[port].fields[name], name) end
local function press(port, name, v) field(port, name):set_value(v) end

local function w16(a) return p:read_u8(a) | (p:read_u8(a + 1) << 8) end

local starx, stary = 0, 0
local tap = p:install_write_tap(0xc805, 0xc806, 'stars', function(off, data, mask)
  if off == 0xc805 then starx = starx + 1 else stary = stary + 1 end
end)

-- Crush death is not covered by the debug invincibility: B2:$8495-$84B1 (player pushed off the
-- screen edge by scrolling terrain) calls $222C. Patch that call to NOPs in the ROM region.
local rom = m.memory.regions[':maincpu']
local CRUSH = 0x8000 + 2 * 0x4000 + (0x84b1 - 0x8000)
assert(rom:read_u8(CRUSH) == 0xcd and rom:read_u8(CRUSH + 1) == 0x2c and rom:read_u8(CRUSH + 2) == 0x22)
if os.getenv('SA_NOCRUSH') ~= '0' then
  rom:write_u8(CRUSH, 0); rom:write_u8(CRUSH + 1, 0); rom:write_u8(CRUSH + 2, 0)
end
-- Sweeping up/down (SA_SWEEP=1) can pick up the alpha/beta pod; with debug invincibility on, the
-- combine sequence ($2E4E, $E014=$41/$42) then hangs the main task. Default off.
-- Player death entry $222C (enemy hit, crush, ...) patched to RET so the run never ends, and the
-- debug master switch is turned off again right after the stage select was consumed at $1594.
-- (Debug invincibility alone hangs/resets in some situations, e.g. alpha-pod combine.)
local DEATH = 0x222c
assert(rom:read_u8(DEATH) == 0x3e)
if os.getenv('SA_NODEATH') ~= '0' then rom:write_u8(DEATH, 0xc9) end
local debug_off_done = false
local sweep = tonumber(os.getenv('SA_SWEEP') or '0')

local halted = 0
local last = ''
for frame = 1, frames do
  if frame == 120 then
    -- debug on. raw DSW0: bit7=0 (debug), bit0=0 (invincible), bit1=0 (coords), bit4 (power)
    field(':DSW0', 'Service Mode').user_value = 0x00
    field(':DSW0', 'Difficulty').user_value = 0x04            -- bits0,1 = 0
    field(':DSW0', 'Bonus Life').user_value = (power == 1) and 0x20 or 0x30   -- bit4 = 0 -> power-up
    local raw = (~stage) & 0x0f                              -- ~DSW1 & $0F = stage index
    field(':DSW1', 'Coin A').user_value = raw & 0x07
    field(':DSW1', 'Coin B').user_value = 0x30 | (raw & 0x08)
  end
  if frame == 300 then press(':SYSTEM', 'Coin 1', 1) end
  if frame == 306 then press(':SYSTEM', 'Coin 1', 0) end
  if frame == 400 then press(':SYSTEM', '1 Player Start', 1) end
  if frame == 406 then press(':SYSTEM', '1 Player Start', 0) end
  if frame >= 500 then press(':P1', 'P1 Button 1', (frame // 4) % 2) end
  if frame >= 1300 and sweep == 1 then   -- sweep up/down so bosses get hit
    local ph = (frame // 90) % 4
    press(':P1', 'P1 Up', ph == 0 and 1 or 0)
    press(':P1', 'P1 Down', ph == 2 and 1 or 0)
  end
  emu.wait_next_update()
  if not debug_off_done and p:read_u8(0xe091) ~= 0 then
    field(':DSW0', 'Service Mode').user_value = 0x80
    debug_off_done = true
    out:write(string.format('D|%d|debug DIP off, script ptr=%04x\n', frame, w16(0xe090)))
  end
  if os.getenv("SA_PCLOG") and frame % 50 == 0 and frame > 4300 then local t={} for i=0,63 do t[#t+1]=string.format("%02x",p:read_u8(0xef80+i)) end out:write(string.format("PC|%d|%04x|%s|e010=%02x e014=%02x e004=%02x\n", frame, cpu.state["PC"].value, table.concat(t), p:read_u8(0xe010), p:read_u8(0xe014), p:read_u8(0xe004))) end
  local x, y = w16(0xe092), w16(0xe094)
  local mode, dy, dx, ptr = p:read_u8(0xe080), p:read_u8(0xe088), p:read_u8(0xe089), w16(0xe090)
  local s = string.format('mode=%02x dy=%02x dx=%02x ptr=%04x', mode, dy, dx, ptr)
  if s ~= last or frame % 60 == 0 then
    out:write(string.format('T|%d|x=%03x|y=%03x|%s|star=%d,%d\n', frame, x, y, s, starx, stary))
    last = s
  end
  if mode == 0x40 then halted = halted + 1 else halted = 0 end
  if unstick > 0 and halted >= unstick then
    if p:read_u8(0xe0d0) ~= 0 then
      -- BG "wheel" boss ($E0D0=$61..$63): its death handler $7511 teleports to the next section;
      -- not emulated here -> end the trace (the next section has its own debug start).
      out:write(string.format('U|%d|wheel boss %02x not killed, trace ends\n', frame, p:read_u8(0xe0d0)))
      break
    end
    out:write(string.format('U|%d|forced resume\n', frame))
    p:write_u8(0xe080, 0x80); halted = 0
  end
  if snap > 0 and frame % snap == 0 then
    m.screens[':screen']:snapshot(string.format('f%05d.png', frame))
  end
end
out:write('COMPLETE\n'); out:close(); m:exit()
