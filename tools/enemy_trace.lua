-- Development-only MAME probe for the enemy module (docs/enemies.md). Nothing here enters the cartridge.
-- Plays stage 1 with an idle, invincible player (debug DIPs as tools/re_objects.lua: Service Mode=0 +
-- Difficulty 0x04 -> invincible, difficulty 3) and logs every object every frame:
--   F|frame|scroll_x|scroll_y|player_y|player_x9|player_state|weapon,levels(5),speed (hex bytes)
--   O|frame|addr|y|x9|code|colour|flags|hp|timer|+$10|+$11|+$16|+$17    (addr = record head: $F000-$F1E0, $F600-$FA00, $FF00-$FFE0)
--   R|frame|$E008|$E003|$E00F|$E008-$E00F hex|$E027   (RNG bytes, loop frame counter, target pick counter)
--   S|frame|addr|y|x9|state|half_h|half_w/2          player 1 shots ($F2E0-$F3E0)
-- Env: SA_FRAMES, SA_STAGE (1-10), SA_FIRE (1 = autofire button 1 from frame 900), SA_START (frame of the start press)
local m = manager.machine
local p = m.devices[':maincpu'].spaces.program
local frames = tonumber(os.getenv('SA_FRAMES') or '6000')
local fire = tonumber(os.getenv('SA_FIRE') or '0')
local start = tonumber(os.getenv('SA_START') or '400')
local stage = tonumber(os.getenv('SA_STAGE') or '1')       -- debug stage select (DSW1, as tools/re_objects.lua)
local out = assert(io.open('trace.txt', 'w'))
local ports = m.ioport.ports
local function field(port, name) return assert(ports[port].fields[name], name) end
local function press(port, name, v) field(port, name):set_value(v) end
local function rd(a) return p:read_u8(a) end
local function obj(frame, a)
  local attr = rd(a + 1)
  local code = rd(a) | ((attr & 0xE0) << 3)
  local x = rd(a + 3) | ((attr & 0x10) << 4)
  out:write(string.format('O|%d|%04x|%d|%d|%d|%d|%d|%d|%d|%d|%d|%d|%d\n', frame, a, rd(a + 2), x, code, attr & 15,
    rd(a + 9), rd(a + 11), rd(a + 4), rd(a + 16), rd(a + 17), rd(a + 22), rd(a + 23)))
end
for frame = 1, frames do
  if frame == 120 then
    field(':DSW0', 'Service Mode').user_value = 0x00
    field(':DSW0', 'Difficulty').user_value = 0x04
    if stage > 1 then
      local raw = (~stage) & 0x0f
      field(':DSW1', 'Coin A').user_value = raw & 0x07
      field(':DSW1', 'Coin B').user_value = 0x30 | (raw & 0x08)
    end
  end
  if frame == start - 100 then press(':SYSTEM', 'Coin 1', 1) end
  if frame == start - 94 then press(':SYSTEM', 'Coin 1', 0) end
  if frame == start then press(':SYSTEM', '1 Player Start', 1) end
  if frame == start + 6 then press(':SYSTEM', '1 Player Start', 0) end
  if fire == 1 and frame >= 1100 then press(':P1', 'P1 Button 2', (frame // 4) % 2) end
  emu.wait_next_update()
  local sx = rd(0xe092) | (rd(0xe093) << 8)
  local sy = rd(0xe094) | (rd(0xe095) << 8)
  local pattr = rd(0xf201)
  out:write(string.format('F|%d|%d|%d|%d|%d|%d|%02x%02x%02x%02x%02x%02x%02x\n', frame, sx, sy, rd(0xf202), rd(0xf203) | ((pattr & 0x10) << 4), rd(0xf208),
    rd(0xf210), rd(0xf211), rd(0xf212), rd(0xf213), rd(0xf214), rd(0xf215), rd(0xf218)))
  out:write(string.format('R|%d|%d|%d|%d|%02x%02x%02x%02x%02x%02x%02x%02x|%d\n', frame, rd(0xe008), rd(0xe003), rd(0xe00f),
    rd(0xe008), rd(0xe009), rd(0xe00a), rd(0xe00b), rd(0xe00c), rd(0xe00d), rd(0xe00e), rd(0xe00f), rd(0xe027)))
  for a = 0xf000, 0xf1e0, 0x20 do if rd(a + 8) ~= 0 then obj(frame, a) end end
  for a = 0xf600, 0xfa00, 0x80 do if rd(a + 8) ~= 0 then obj(frame, a) end end
  for a = 0xff00, 0xffe0, 0x20 do if rd(a + 8) ~= 0 then obj(frame, a) end end
  for a = 0xf2e0, 0xf3e0, 0x20 do
    if rd(a + 8) ~= 0 then
      local at = rd(a + 1)
      out:write(string.format('S|%d|%04x|%d|%d|%d|%d|%d\n', frame, a, rd(a + 2), rd(a + 3) | ((at & 0x10) << 4), rd(a + 8), rd(a + 12), rd(a + 13)))
    end
  end
end
out:write('COMPLETE\n'); out:close(); m:exit()
