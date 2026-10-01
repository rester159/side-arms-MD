-- Development-only original-ROM observation. Nothing here enters the cartridge.
-- Env: SA_FRAMES (total frames), SA_SNAP (snapshot every N frames, 0=off),
--      SA_INPUT (file with lines "frame field value"), SA_DUMP (dump every N frames)
local m = manager.machine
local cpu = m.devices[':maincpu']
local p = cpu.spaces.program
local frames = tonumber(os.getenv('SA_FRAMES') or '600')
local snap = tonumber(os.getenv('SA_SNAP') or '0')
local dump = tonumber(os.getenv('SA_DUMP') or '1')
local out = assert(io.open('events.txt', 'w'))

local shares = m.memory.shares
local function sh(name, n)
  local s = shares[name]; local t = {}
  for i = 0, n - 1 do t[#t + 1] = string.format('%02x', s:read_u8(i)) end
  return table.concat(t)
end
local function hex(a, n)
  local t = {}
  for i = 0, n - 1 do t[#t + 1] = string.format('%02x', p:read_u8(a + i)) end
  return table.concat(t)
end

-- register taps (write-only latches)
local reg = { ctrl = 0, gfx = 0, bank = 0, sx = 0, sy = 0, latch = {} }
local taps = {}
taps[#taps + 1] = p:install_write_tap(0xc800, 0xc80c, 'regs', function(off, data, mask)
  if off == 0xc804 then reg.ctrl = data
  elseif off == 0xc80c then reg.gfx = data
  elseif off == 0xc801 then reg.bank = data
  elseif off == 0xc805 then reg.sx = reg.sx + 1
  elseif off == 0xc806 then reg.sy = reg.sy + 1
  elseif off == 0xc800 then reg.latch[#reg.latch + 1] = string.format('%02x', data) end
end)

-- input timeline
local inputs = {}
local ipath = os.getenv('SA_INPUT')
if ipath then
  for line in io.lines(ipath) do
    local f, port, field, v = line:match('^(%d+)%s+(%S+)%s+"(.-)"%s+(%d+)')
    if f then inputs[#inputs + 1] = { tonumber(f), port, field, tonumber(v) } end
  end
end
local function apply(frame)
  for _, e in ipairs(inputs) do
    if e[1] == frame then
      local fld = m.ioport.ports[e[2]].fields[e[3]]
      assert(fld, 'no field ' .. e[2] .. ' ' .. e[3])
      fld:set_value(e[4])
    end
  end
end

for frame = 1, frames do
  apply(frame)
  emu.wait_next_update()
  if dump > 0 and frame % dump == 0 then
    out:write(string.format('F|%d|ctrl=%02x|gfx=%02x|bank=%02x|sx=%s|sy=%s|star=%d,%d|snd=%s\n', frame, reg.ctrl, reg.gfx, reg.bank,
      sh(':bg_scrollx', 2), sh(':bg_scrolly', 2), reg.sx, reg.sy, table.concat(reg.latch, ',')))
    reg.latch = {}
    out:write('S|' .. sh(':spriteram', 4096) .. '\n')
    out:write('R|' .. hex(0xe000, 4096) .. '\n')
  end
  if snap > 0 and frame % snap == 0 then
    out:write(string.format('P|%d|%s|%s\n', frame, sh(':palette', 1024), sh(':palette_ext', 1024)))
    out:write(string.format('V|%d|%s|%s\n', frame, hex(0xd000, 2048), hex(0xd800, 2048)))
    m.screens[':screen']:snapshot(string.format('f%05d.png', frame))
  end
end
out:write('COMPLETE\n'); out:close(); m:exit()
