-- Development-only probe for docs/re/flow_player.md (player / game-flow RE).
-- Same input file format as capture.lua, plus DIP lines:  <frame> <port> "dip:<field name>" <user_value>
--   and RAM pokes:  <frame> poke <hexaddr> <hexbyte>  (test setup only, e.g. weapon levels)
-- Env: SA_FRAMES, SA_INPUT, SA_SNAP (snapshot every N frames), SA_SNAPAT (comma list of frames to snapshot)
-- Output events.txt:
--   F|frame|E001|<hex $E000-$E2FF>|<hex $F000-$FFFF sprite/object RAM>
--   T|frame|<hex text codes $D000-$D7FF>|<hex text attrs $D800-$DFFF>   (on snapshot frames)
--   W|frame|pc|addr|data   for writes to the player state byte $F208/$F408 (death/respawn transitions)
local m = manager.machine
local cpu = m.devices[':maincpu']
local p = cpu.spaces.program
local frames = tonumber(os.getenv('SA_FRAMES') or '600')
local snap = tonumber(os.getenv('SA_SNAP') or '0')
local snapat = {}
for v in string.gmatch(os.getenv('SA_SNAPAT') or '', '%d+') do snapat[tonumber(v)] = true end
local out = assert(io.open('events.txt', 'w'))
local function hex(a, n)
  local t = {}
  for i = 0, n - 1 do t[#t + 1] = string.format('%02x', p:read_u8(a + i)) end
  return table.concat(t)
end
local frame = 0
local taps = {}
taps[#taps + 1] = p:install_write_tap(0xf208, 0xf208, 'p1st', function(off, data, mask)
  out:write(string.format('W|%d|%04x|%04x|%02x\n', frame, cpu.state['PC'].value, off, data))
end)
taps[#taps + 1] = p:install_write_tap(0xf408, 0xf408, 'p2st', function(off, data, mask)
  out:write(string.format('W|%d|%04x|%04x|%02x\n', frame, cpu.state['PC'].value, off, data))
end)
local inputs = {}
local ipath = os.getenv('SA_INPUT')
if ipath then
  for line in io.lines(ipath) do
    local f, port, field, v = line:match('^(%d+)%s+(%S+)%s+"(.-)"%s+(%d+)')
    if f then inputs[#inputs + 1] = { tonumber(f), port, field, tonumber(v) } end
    local pf, pa, pv = line:match('^(%d+)%s+poke%s+(%x+)%s+(%x+)')
    if pf then inputs[#inputs + 1] = { tonumber(pf), 'poke', tonumber(pa, 16), tonumber(pv, 16) } end
  end
end
local function apply(fr)
  for _, e in ipairs(inputs) do
    if e[1] == fr and e[2] == 'poke' then
      p:write_u8(e[3], e[4])
    elseif e[1] == fr then
      local name = e[3]
      local dip = name:match('^dip:(.*)$')
      local fld = m.ioport.ports[e[2]].fields[dip or name]
      assert(fld, 'no field ' .. e[2] .. ' ' .. name)
      if dip then fld.user_value = e[4] else fld:set_value(e[4]) end
    end
  end
end
for f = 1, frames do
  frame = f
  apply(f)
  emu.wait_next_update()
  out:write(string.format('F|%d|%s|%s\n', f, hex(0xe000, 0x300), hex(0xf000, 0x1000)))
  if (snap > 0 and f % snap == 0) or snapat[f] then
    out:write(string.format('T|%d|%s|%s\n', f, hex(0xd000, 2048), hex(0xd800, 2048)))
    m.screens[':screen']:snapshot(string.format('f%05d.png', f))
  end
end
out:write('COMPLETE\n'); out:close(); m:exit()
