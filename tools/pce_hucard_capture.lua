-- Development-only PSG observations of the user-supplied HuCard.
local m=manager.machine
local dev=m.devices[':maincpu'];local cpu=dev.spaces.program
local banks=emu.item(dev.items['0/m_mmr'])
local ram=emu.item(dev.items['0/1f0000-1f1fff'])
local frame=0
print('PSG CAPTURE START')
local limit=tonumber(os.getenv('PCE_FRAMES') or '1200')
local log=assert(io.open('psg.csv','w'));log:write('frame,time,pc,reg,value,banks\n')
local tap=cpu:install_write_tap(0x1fe800,0x1fe809,'hucard-psg',function(off,data,mask)
 log:write(string.format('%d,%.9f,%04x,%x,%02x,%s\n',frame,m.time:as_double(),dev.state['PC'].value,off-0x1fe800,data,(banks:read_block(0,8):gsub('.',function(c)return string.format('%02x',string.byte(c))end))))
end)
local requested=tonumber(os.getenv('PCE_COMMAND') or '')
local fixture_step=0
local commands=assert(io.open('commands.csv','w'));commands:write('frame,time,command,fixture\n')
local queue_tap=cpu:install_read_tap(0x1f0600,0x1f060f,'hucard-commands',function(off,data,mask)
 if dev.state['PC'].value~=0xe0de then return end
 local value=data
 if requested and frame>=60 then
  local sequence={0xf1,0xf2,requested}
  fixture_step=fixture_step+1;value=sequence[fixture_step] or 0xff
 end
 if value~=0xff then commands:write(string.format('%d,%.9f,%02x,%d\n',frame,m.time:as_double(),value,requested and frame>=60 and 1 or 0))end
 return value
end)
local tick=0
local state=assert(io.open('sound-state.bin','wb'))
local state_tap=cpu:install_read_tap(0xf9,0xf9,'hucard-sound-tick',function(off,data,mask)
 if dev.state['PC'].value~=0xe0f9 then return end
 tick=tick+1
 state:write(string.pack('<I4I4d',tick,frame,m.time:as_double())..ram:read_block(0x99,23)..ram:read_block(0xf2e,138))
end)
local ports=m.ioport.ports
for name,port in pairs(ports) do for key,field in pairs(port.fields)do print('INPUT',name,key)end end
local buttons=(ports[':ctrl:joypad2:BUTTONS'] or ports[':ctrl:joypad2_turbo:BUTTONS']).fields
emu.register_frame_done(function()
 assert(tap and queue_tap and state_tap) -- keep the address-space tap alive across Lua garbage collection
 frame=frame+1
 if frame==1 then print('FRAME',dev.state['PC'].value)end
 buttons['P1 Run']:set_value((not requested and frame>=180 and frame<190) and 1 or 0)
 if requested then cpu:write_u8(0x1f005d,0)end
 if frame%120==0 then
  local f=assert(io.open(string.format('f%06d-ram.bin',frame),'wb'));f:write(ram:read_block(0,8192));f:close()
  local b=assert(io.open(string.format('f%06d-banks.bin',frame),'wb'));b:write(banks:read_block(0,8));b:close()
 end
 if frame==limit then log:close();commands:close();state:close();local f=assert(io.open('complete.txt','w'));f:write(frame);f:close();m:exit()end
end)
