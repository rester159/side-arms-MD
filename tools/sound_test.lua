-- Development-only probe for the Genesis sound test cartridge (tests/sound_rom) under MAME 'genesis'.
-- Logs every YM2612 and PSG write made by the Z80 and injects commands into the driver's FIFO at
-- exact driver ticks (the test hook needs no driver code: it writes the mailbox the 68000 API uses).
-- Env: ST_SEQ   "tick:cmd,..." (hex cmd) commands pushed into the FIFO at the $27 write of that tick
--      ST_C000  arcade $C000 before its increment at tick 0 (planted so triplet/slide parity agree)
--      ST_API   "frame:cmd,..." alternatively send through the 68000 API (host_cmd/host_n in RAM)
--      ST_HOST  68000 address of host_cmd (hex), host_n = +16
--      ST_SECS, ST_WARM (frames, default 60), ST_OUT
-- Log: I|t (tick start = driver write of TICK)  W|t|part|reg|data (part 1 = $4000/1, 2 = $4002/3)  P|t|byte (PSG)
--      G|t|ms|pc0|pc1  status-read gap > 1.5 ms (poll coverage) between reads; pc0/pc1 = return address on the stack
--      Q|t|cmd  command injected   D|t|cmd  command taken by the driver   A|t|n  API batch written
local m = manager.machine
local zp = m.devices[':genesis_snd_z80'].spaces.program
local mp = m.devices[':maincpu'].spaces.program
local secs = tonumber(os.getenv('ST_SECS') or '8')
local warm = tonumber(os.getenv('ST_WARM') or '60')
local out = assert(io.open(os.getenv('ST_OUT') or 'md.log', 'w'))
local c000 = tonumber(os.getenv('ST_C000') or '-1')
local seq, api = {}, {}
for t, c in string.gmatch(os.getenv('ST_SEQ') or '', '(%d+):(%x+)') do
  t = tonumber(t); seq[t] = seq[t] or {}; table.insert(seq[t], tonumber(c, 16))
end
for f, c in string.gmatch(os.getenv('ST_API') or '', '(%d+):(%x+)') do
  f = tonumber(f); api[f] = api[f] or {}; table.insert(api[f], tonumber(c, 16))
end
local host = tonumber(os.getenv('ST_HOST') or '0', 16)
local MB_WR, MB_RING, TICK = 0x1f04, 0x1f10, 0x1400

local t0 = nil
local tick = -1
local function now() return m.time:as_double() end
local function rel() return now() - t0 end
local addr = { [1] = 0, [2] = 0 }
local taps = {}
taps[#taps + 1] = zp:install_write_tap(TICK, TICK, 'tick', function(off, data, mask)
  -- the driver increments TICK ($C000 copy) at the start of every tick, before taking a command
  if not t0 then return end
  tick = tick + 1
  out:write(string.format('I|%.6f\n', rel()))
  local q = seq[tick]
  if q then
    for _, c in ipairs(q) do
      local wr = zp:read_u8(MB_WR)
      zp:write_u8(MB_RING + wr, c)
      zp:write_u8(MB_WR, (wr + 1) & 15)
      out:write(string.format('Q|%.6f|%02x\n', rel(), c))
    end
  end
  if tick == 0 and c000 >= 0 then return (c000 + 1) & 0xff end
end)
taps[#taps + 1] = zp:install_write_tap(0x4000, 0x4003, 'ym', function(off, data, mask)
  local part = (off >= 0x4002) and 2 or 1
  if (off & 1) == 0 then addr[part] = data; return end
  if t0 then out:write(string.format('W|%.6f|%d|%02x|%02x\n', rel(), part, addr[part], data)) end
end)
taps[#taps + 1] = zp:install_write_tap(0x1f05, 0x1f05, 'fifo', function(off, data, mask)
  -- the driver advances MB_RD after taking a command: log which one
  if t0 then out:write(string.format('D|%.6f|%02x\n', rel(), zp:read_u8(MB_RING + ((data - 1) & 15)))) end
end)
-- poll coverage: the driver reads the YM status ($4000) in `poll` and before every write; a gap
-- longer than half a tick (2.009 ms) between two reads would lose a Timer A overflow.
local lastrd, maxgap, lastpc = nil, 0, 0
local zcpu = m.devices[':genesis_snd_z80']
local function caller()   -- return address of the routine doing the read (poll / ymw)
  local sp = zcpu.state['SP'].value
  return zp:read_u8(sp) | (zp:read_u8((sp + 1) & 0xffff) << 8)
end
taps[#taps + 1] = zp:install_read_tap(0x4000, 0x4000, 'stat', function(off, data, mask)
  if not t0 then return end
  local t = now()
  if lastrd then
    local g = t - lastrd
    if g > maxgap then maxgap = g end
    if g > 0.0015 then out:write(string.format('G|%.6f|%.3f|%04x|%04x\n', rel(), g * 1000, lastpc, caller())) end
  end
  lastrd = t
  lastpc = caller()
end)
taps[#taps + 1] = zp:install_write_tap(0x7f11, 0x7f11, 'psg', function(off, data, mask)
  if t0 then out:write(string.format('P|%.6f|%02x\n', rel(), data)) end
end)

for f = 1, warm do emu.wait_next_update() end
t0 = now()
out:write(string.format('# t0_abs=%.6f\n', t0))
local frame = 0
while rel() < secs do
  local q = api[frame]
  if q and host ~= 0 then
    for i, c in ipairs(q) do mp:write_u8(host + i - 1, c) end
    mp:write_u8(host + 16, #q)
    out:write(string.format('A|%.6f|%d\n', rel(), #q))
  end
  emu.wait_next_update()
  frame = frame + 1
end
out:write(string.format('# max_status_gap_ms=%.3f\n', maxgap * 1000))
out:write('COMPLETE\n'); out:close()
m:exit()
