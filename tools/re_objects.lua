-- Development-only object/enemy probe (docs/re/objects.md). Nothing here enters the cartridge.
-- Uses the game's own debug DIPs (same scheme as tools/re_levels.lua):
--   DSW0 bit7=0 + bit0=0 -> invincible, bit4=0 -> full power; ~DSW1&$0F -> start entry of table $15B4.
-- Env: SA_STAGE (1..10), SA_FRAMES, SA_SNAP (png every N frames, 0=off), SA_SDUMP (sprite RAM dump every N),
--      SA_NOCRUSH (1 = NOP the terrain-crush death call B2:$84B1, default 1)
--      SA_UNSTICK (frames of scroll halt before forcing $E080=$80; 0=never), SA_MOVE (1 = weave up/down)
-- Output events.txt:
--   N|frame|addr|32 bytes hex          object record seen active (+8!=0) for the first time (spawn)
--   K|frame|addr                        object slot became inactive (+8==0)
--   C|frame|visible|maxline|r0,r1,..    visible hardware sprites, max per scanline, per-region visible counts
--   T|frame|x|y|mode|dy|dx|ptr          scroll state when it changes (or every 60 frames)
--   S|frame|4096 bytes hex              sprite RAM (every SA_SDUMP frames and at new peaks)
local m = manager.machine
local cpu = m.devices[':maincpu']
local p = cpu.spaces.program
local stage = tonumber(os.getenv('SA_STAGE') or '1')
local frames = tonumber(os.getenv('SA_FRAMES') or '6000')
local snap = tonumber(os.getenv('SA_SNAP') or '0')
local sdump = tonumber(os.getenv('SA_SDUMP') or '0')
local unstick = tonumber(os.getenv('SA_UNSTICK') or '0')
local move = tonumber(os.getenv('SA_MOVE') or '1')
local out = assert(io.open('events.txt', 'w'))
local ports = m.ioport.ports
local function field(port, name) return assert(ports[port].fields[name], name) end
local function press(port, name, v) field(port, name):set_value(v) end
local function w16(a) return p:read_u8(a) | (p:read_u8(a + 1) << 8) end
local spr = m.memory.shares[':spriteram']
local function rec(a, n)
  local t = {}
  for i = 0, n - 1 do t[#t + 1] = string.format('%02x', p:read_u8(a + i)) end
  return table.concat(t)
end
-- buffered (DMA'd) sprite RAM is what MAME draws; the share is the CPU-side RAM ($F000-$FFFF)
local regions = { { 0x000, 0x200 }, { 0x200, 0x400 }, { 0x400, 0x600 }, { 0x600, 0xB00 }, { 0xB00, 0xF00 }, { 0xF00, 0x1000 } }
-- probe-only: disable the terrain-crush death call at B2:$84B1 (call $222C -> 3x NOP) so
-- invincible runs reach the bosses. Region offset = 0x8000 + 2*0x4000 + 0x04B1.
if (tonumber(os.getenv('SA_NOCRUSH') or '1')) == 1 then
  local rg = m.memory.regions[':maincpu']
  for i = 0, 2 do rg:write_u8(0x104B1 + i, 0x00) end
end
local active = {}
local peak, halted, last = -1, 0, ''
for frame = 1, frames do
  if frame == 120 then
    field(':DSW0', 'Service Mode').user_value = 0x00
    field(':DSW0', 'Difficulty').user_value = 0x04
    field(':DSW0', 'Bonus Life').user_value = 0x20
    local raw = (~stage) & 0x0f
    field(':DSW1', 'Coin A').user_value = raw & 0x07
    field(':DSW1', 'Coin B').user_value = 0x30 | (raw & 0x08)
  end
  if frame == 300 then press(':SYSTEM', 'Coin 1', 1) end
  if frame == 306 then press(':SYSTEM', 'Coin 1', 0) end
  if frame == 400 then press(':SYSTEM', '1 Player Start', 1) end
  if frame == 406 then press(':SYSTEM', '1 Player Start', 0) end
  if frame >= 500 then
    press(':P1', 'P1 Button 1', (frame // 4) % 2)
    if move == 1 then
      local ph = (frame // 90) % 4
      press(':P1', 'P1 Up', ph == 0 and 1 or 0)
      press(':P1', 'P1 Down', ph == 2 and 1 or 0)
    end
  end
  emu.wait_next_update()
  -- spawns / kills (scan every record head: a record is an object head if +8 != 0)
  for i = 0, 127 do
    local a = 0xf000 + i * 32
    local st = p:read_u8(a + 8)
    if st ~= 0 and not active[a] then
      active[a] = true
      out:write(string.format('N|%d|%04x|%s\n', frame, a, rec(a, 32)))
    elseif st == 0 and active[a] then
      active[a] = nil
      out:write(string.format('K|%d|%04x\n', frame, a))
    end
  end
  -- sprite statistics (visible area x 64..447, y 16..239 in MAME raw coordinates)
  local lines = {}
  local vis = 0
  local rc = {}
  for r = 1, #regions do
    local c = 0
    for off = regions[r][1], regions[r][2] - 32, 32 do
      local y = spr:read_u8(off + 2)
      if y ~= 0 then
        local attr = spr:read_u8(off + 1)
        local x = spr:read_u8(off + 3) + ((attr & 0x10) << 4)
        if y + 16 > 16 and y < 240 and x + 16 > 64 and x < 448 then
          c = c + 1
          for yy = y, y + 15 do lines[yy] = (lines[yy] or 0) + 1 end
        end
      end
    end
    rc[#rc + 1] = c; vis = vis + c
  end
  local ml = 0
  for yy = 16, 239 do if (lines[yy] or 0) > ml then ml = lines[yy] end end
  out:write(string.format('C|%d|%d|%d|%s\n', frame, vis, ml, table.concat(rc, ',')))
  -- Genesis-unit estimate: a 2x2 object ($F600-$FA7F heads, player ships $F200/$F400) = one 32x32
  -- hardware sprite, the boss ($FB00) = 8 x 32x32 (4 per row), everything else one 16x16 sprite.
  -- G|frame|units|max units per line|max sprite pixels per line
  local units, ul, up = 0, {}, {}
  local function addu(y, x, w, h)
    if y + h > 16 and y < 240 and x + w > 64 and x < 448 then
      units = units + 1
      for yy = math.max(y, 16), math.min(y + h - 1, 239) do
        ul[yy] = (ul[yy] or 0) + 1; up[yy] = (up[yy] or 0) + w
      end
    end
  end
  local function sxy(off)
    local attr = spr:read_u8(off + 1)
    return spr:read_u8(off + 2), spr:read_u8(off + 3) + ((attr & 0x10) << 4)
  end
  local grouped = {}
  for _, b in ipairs({ 0x200, 0x400 }) do
    local y, x = sxy(b)
    if y ~= 0 then addu(y, x, 32, 32) end
    for o = b, b + 0x60, 0x20 do grouped[o] = true end
  end
  for b = 0x600, 0xA00, 0x80 do
    local y, x = sxy(b)
    if spr:read_u8(b + 8) ~= 0 and y ~= 0 then
      addu(y, x, 32, 32)
      for o = b, b + 0x60, 0x20 do grouped[o] = true end
    end
  end
  if spr:read_u8(0xB08) ~= 0 then
    local y, x = sxy(0xB00)
    for r = 0, 1 do for c = 0, 3 do addu(y + 32 * r, x + 32 * c, 32, 32) end end
    for o = 0xB00, 0xEE0, 0x20 do grouped[o] = true end
  end
  for off = 0, 0xFE0, 0x20 do
    if not grouped[off] then
      local y, x = sxy(off)
      if y ~= 0 then addu(y, x, 16, 16) end
    end
  end
  local mu, mp = 0, 0
  for yy = 16, 239 do
    if (ul[yy] or 0) > mu then mu = ul[yy] end
    if (up[yy] or 0) > mp then mp = up[yy] end
  end
  out:write(string.format('G|%d|%d|%d|%d\n', frame, units, mu, mp))
  if (sdump > 0 and frame % sdump == 0) or vis > peak then
    if vis > peak then peak = vis end
    out:write(string.format('S|%d|%s\n', frame, rec(0xf000, 4096)))
  end
  local x, y = w16(0xe092), w16(0xe094)
  local mode, dy, dx, ptr = p:read_u8(0xe080), p:read_u8(0xe088), p:read_u8(0xe089), w16(0xe090)
  local s = string.format('%02x|%02x|%02x|%04x', mode, dy, dx, ptr)
  if s ~= last or frame % 60 == 0 then
    out:write(string.format('T|%d|%03x|%03x|%s\n', frame, x, y, s)); last = s
  end
  if mode == 0x40 then halted = halted + 1 else halted = 0 end
  if unstick > 0 and halted >= unstick then
    out:write(string.format('U|%d|forced resume\n', frame)); p:write_u8(0xe080, 0x80); halted = 0
  end
  if snap > 0 and frame % snap == 0 then m.screens[':screen']:snapshot(string.format('f%05d.png', frame)) end
end
out:write('COMPLETE\n'); out:close(); m:exit()
