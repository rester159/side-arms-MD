-- Read-only observation of each HuCard queue consumption and actual YM writes.
local m = manager.machine
local zp = m.devices[':genesis_snd_z80'].spaces.program
local mp = m.devices[':maincpu'].spaces.program
local out = assert(io.open(assert(os.getenv('HC_OUT')), 'w'))
local host = tonumber(assert(os.getenv('HC_HOST')), 16)
local song = tonumber(os.getenv('HC_SONG') or '1')
local seconds = tonumber(os.getenv('HC_SECONDS') or '12')
local armed, active = false, false
local addr = {[1]=0,[2]=0}
local taps = {}
taps[#taps+1] = zp:install_write_tap(0x1b0c,0x1b0c,'hu_frame',function(off,data,mask)
  if not armed then return end
  assert(not active, 'overlapping music frames')
  active = true
  local base = 0x1800 + 72*zp:read_u8(0x1f0a)
  out:write('F|')
  for i=0,71 do out:write(string.format('%02x',zp:read_u8(base+i))) end
  out:write('\n')
end)
taps[#taps+1] = zp:install_write_tap(0x4000,0x4003,'hu_ym',function(off,data,mask)
  local part = off >= 0x4002 and 2 or 1
  if (off & 1)==0 then addr[part]=data
  elseif active then out:write(string.format('W|%d|%02x|%02x\n',part,addr[part],data)) end
end)
taps[#taps+1] = zp:install_write_tap(0x1f0a,0x1f0a,'hu_done',function(off,data,mask)
  if active then out:write('E\n');active=false end
end)
for i=1,120 do emu.wait_next_update() end
armed=true
mp:write_u8(host,song+1)
local start=m.time:as_double()
while m.time:as_double()-start < seconds do emu.wait_next_update() end
out:write(string.format('DONE|%d\n',zp:read_u8(0x1b0a)))
out:close()
m:exit()
