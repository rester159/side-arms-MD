-- Development-only observations of the user's Side Arms Special CD.
-- No emulator or PC Engine machine code enters the Genesis cartridge.
local m = manager.machine
local cpu = m.devices[':maincpu'].spaces.program
local buttons = m.ioport.ports[':ctrl:joypad2:BUTTONS'].fields
local direction = m.ioport.ports[':ctrl:joypad2:DIRECTION'].fields
local frames = tonumber(os.getenv('PCE_FRAMES') or '6000')
local stage = tonumber(os.getenv('PCE_STAGE') or '0')
local invulnerable = os.getenv('PCE_INVULNERABLE') == '1'
local boss_fast = os.getenv('PCE_BOSS_FAST') == '1'
local fire = os.getenv('PCE_FIRE') or 'pulse'
local interval = tonumber(os.getenv('PCE_INTERVAL') or '120')
local snapshot_from = tonumber(os.getenv('PCE_SNAPSHOT_FROM') or '0')
local late_code_from = tonumber(os.getenv('PCE_LATE_CODE_FROM') or '0')
local trace_from = tonumber(os.getenv('PCE_TRACE_FROM') or '0')
local logic = trace_from>0 and assert(io.open('logic.bin','wb')) or nil
local full_state = os.getenv('PCE_FULL_STATE') == '1' and assert(io.open('state.bin','wb')) or nil
local inputs={}
local input_path=os.getenv('PCE_INPUT')
if input_path then
 for line in io.lines(input_path) do
  local f,field,value=line:match('^(%d+)%s+(.-)%s+(%S+)$')
  if f then
   local t=inputs[tonumber(f)] or {}; inputs[tonumber(f)]=t
   local addr=field:match('^poke (%x+)$')
   t[#t+1]={field=field,value=value,addr=addr}
  end
 end
end
local cpud = m.devices[':maincpu']
local ci = cpud.items
local cdram = emu.item(ci['0/:cd_ram'])
local banks = emu.item(ci['0/m_mmr'])
local ramitem = emu.item(ci['0/1f0000-1f1fff'])
local vd = m.devices[':huc6270'].items
local vc = m.devices[':huc6260'].items
local vram = emu.item(vd['0/m_vram'])
local palette = emu.item(vc['0/m_palette'])
local sat = emu.item(vd['0/m_sat'])
local regs = {}
local trace = assert(io.open('writes.csv','w'))
trace:write('frame,pc,address,value,banks\n')
local current_frame = 0
local taps = {}
local random_trace = os.getenv('PCE_RANDOM_TRACE') == '1' and assert(io.open('random.bin','wb')) or nil
local gallery_trace = os.getenv('PCE_GALLERY_TRACE') == '1' and assert(io.open('gallery-actors.bin','wb')) or nil
local gallery_birth = gallery_trace and assert(io.open('gallery-birth.bin','wb')) or nil
if gallery_trace then
 local pending=nil
 local birth_pending=nil
 for _,address in ipairs({0x947e,0x98a5,0x98dc,0x9bca,0x988a}) do
  taps[#taps+1]=cpu:install_read_tap(0x100000+address-0x4000,0x100000+address-0x4000,'gallery-'..address,function(off,data,mask)
   local pc=cpud.state['PC'].value
   if current_frame<7290 or current_frame>13130 or (pc~=address and pc~=address+1) then return end
   if address==0x9bca then
    assert(not birth_pending,'Nested gallery birth')
    birth_pending=string.pack('<I4BB',current_frame,0,0)..ramitem:read_block(0,8192)
   elseif address==0x988a then
    if birth_pending then gallery_birth:write(birth_pending..string.pack('<I4BB',current_frame,0,1)..ramitem:read_block(0,8192));birth_pending=nil end
   elseif address==0x947e then
    assert(not pending,'Nested gallery actor')
    pending=string.pack('<I4BB',current_frame,cpud.state['X'].value,0)..ramitem:read_block(0,8192)
   elseif pending then
    gallery_trace:write(pending..string.pack('<I4BB',current_frame,cpud.state['X'].value,1)..ramitem:read_block(0,8192));pending=nil
   end
  end)
 end
end
local random_pending = nil
local random_taps = {}
if random_trace then
 for _,address in ipairs({0x6d41,0x6d65}) do
  random_taps[#random_taps+1] = cpu:install_read_tap(0x100000+address-0x4000,0x100000+address-0x4000,'random-'..address,function(off,data,mask)
   local pc=cpud.state['PC'].value
   if current_frame<trace_from or (pc~=address and pc~=address+1) then return end
   local seed=cpu:read_u8(0x1f006c)+256*cpu:read_u8(0x1f006d)
   if address==0x6d41 then
    assert(not random_pending,'Nested RNG task'); random_pending={current_frame,seed}
   elseif random_pending then
    random_trace:write(string.pack('<I4I2I2',random_pending[1],random_pending[2],seed)); random_pending=nil
   end
  end)
 end
end
taps[#taps+1] = cpu:install_write_tap(0x1f0056,0x1f0056,'charge',function(off,data,mask)
 if current_frame < 2000 then return end
 trace:write(string.format('%d,%04x,%06x,%02x,%s\n',current_frame,cpud.state['PC'].value,off,data,(banks:read_block(0,8):gsub('.',function(c) return string.format('%02x',string.byte(c)) end))))
end)
taps[#taps+1] = cpu:install_write_tap(0x1f0094,0x1f009a,'movement',function(off,data,mask)
 if current_frame < 2000 then return end
 trace:write(string.format('%d,%04x,%06x,%02x,%s\n',current_frame,cpud.state['PC'].value,off,data,(banks:read_block(0,8):gsub('.',function(c) return string.format('%02x',string.byte(c)) end))))
end)
taps[#taps+1] = cpu:install_write_tap(0x1f0a48,0x1f0a65,'projectile-state',function(off,data,mask)
 if current_frame < 2000 then return end
 trace:write(string.format('%d,%04x,%06x,%02x,%s\n',current_frame,cpud.state['PC'].value,off,data,(banks:read_block(0,8):gsub('.',function(c) return string.format('%02x',string.byte(c)) end))))
end)
-- Observe the original collision scan before its first predicate and at its
-- two exits. These are instruction fetch taps in CD RAM bank $83; no writes.
local score_trace = os.getenv('PCE_SCORE_TRACE') == '1' and assert(io.open('score.bin','wb')) or nil
local player_flow = os.getenv('PCE_PLAYER_FLOW_TRACE') == '1' and assert(io.open('player-flow.bin','wb')) or nil
local play_trace = player_flow and assert(io.open('play-task.bin','wb')) or nil
if play_trace then
 local pending=nil
 for _,spec in ipairs({{0x7407,0},{0x9e6a,1},{0x637b,2}}) do
  local address,phase=table.unpack(spec)
  taps[#taps+1]=cpu:install_read_tap(0x100000+address-0x4000,0x100000+address-0x4000,'play-task-'..address,function(off,data,mask)
   local pc=cpud.state['PC'].value
   if current_frame<trace_from or (pc~=address and pc~=address+1) or cpu:read_u8(0x1f004b)~=0 then return end
   local record=string.pack('<I4BB',current_frame,0,phase)..ramitem:read_block(0,8192)
   if phase==0 then assert(not pending,'Nested play task');pending=record
   elseif pending then play_trace:write(pending..record);pending=nil end
  end)
 end
end
local player_runtime = player_flow and os.getenv('PCE_COMMON_TRACE')=='1' and assert(io.open('player-runtime.bin','wb')) or nil
local function runtime_record(kind)
 if player_runtime then
  player_runtime:write(string.pack('<I4BB',current_frame,kind,cpud.state['X'].value)..ramitem:read_block(0,8192))
 end
end
if player_flow then
 local pending=nil
 local function record(phase)
  return string.pack('<I4BB',current_frame,0,phase)..ramitem:read_block(0,8192)
 end
 for _,spec in ipairs({{0x7407,0},{0x740a,1},{0x637b,2},{0x740d,3},{0x7487,4}}) do
  local address,phase=table.unpack(spec)
  taps[#taps+1] = cpu:install_read_tap(0x100000+address-0x4000,0x100000+address-0x4000,'player-flow-'..address,function(off,data,mask)
   local pc=cpud.state['PC'].value
   if current_frame<trace_from or (pc~=address and pc~=address+1) then return end
   if phase==0 or phase==3 then
    assert(not pending,'Nested player flow'); pending=record(phase)
    if phase==0 then runtime_record(0) end
   elseif pending and (phase~=2 or pending:byte(6)==0) then
    player_flow:write(pending..record(phase));pending=nil
    if phase==2 then runtime_record(2) elseif phase==4 then runtime_record(1) end
   end
  end)
 end
end
local reset_file = player_flow and assert(io.open('player-reset.bin','wb')) or nil
if reset_file then
 local pending=nil
 for _,spec in ipairs({{0x65d6,0},{0x6623,1}}) do
  local address,phase=table.unpack(spec)
  taps[#taps+1]=cpu:install_read_tap(0x100000+address-0x4000,0x100000+address-0x4000,'player-reset-'..address,function(off,data,mask)
   local pc=cpud.state['PC'].value
   if current_frame<trace_from or (pc~=address and pc~=address+1) then return end
   local record=string.pack('<I4BB',current_frame,0,phase)..ramitem:read_block(0,8192)
   if phase==0 then pending=record
   elseif pending then reset_file:write(pending..record);reset_file:flush();pending=nil end
  end)
 end
end
local stage_trace = player_flow and assert(io.open('stage-state.bin','wb')) or nil
if stage_trace then
 local pending=nil
 for _,shift in ipairs({0,-0x217}) do
  for _,spec in ipairs({{0x6786,0},{0x67a2,1},{0x737c,2},{0x73a2,3},{0x6ed4,4},{0x6f0e,5},{0x7690,6},{0x76d3,7},{0x76d2,9}}) do
   local phase=spec[2]
   if phase>=2 or shift==0 then
    local address=spec[1]+(phase>=2 and shift or 0)
    taps[#taps+1]=cpu:install_read_tap(0x100000+address-0x4000,0x100000+address-0x4000,'stage-state-'..address,function(off,data,mask)
     local pc=cpud.state['PC'].value
     if current_frame<trace_from or (pc~=address and pc~=address+1) then return end
     if phase>=2 and cdram:read_block(0x3690+shift,8)~=string.char(0xa5,0x42,0x05,0x43,0xd0,0x06,0xa5,0x2f) then return end
     local record=string.pack('<I4BB',current_frame,0,phase)..ramitem:read_block(0,8192)
     if phase%2==0 then assert(not pending,'Nested stage state');pending=record
     elseif pending then stage_trace:write(pending..record);pending=nil end
    end)
   end
  end
 end
end
local stage_controls = player_flow and assert(io.open('stage-controls.bin','wb')) or nil
if stage_controls then
 local pending=nil
 for _,shift in ipairs({0,-0x217}) do
  for _,base in ipairs({0x76d3,0x76b8}) do
   local address=base+shift
   taps[#taps+1]=cpu:install_read_tap(0x100000+address-0x4000,0x100000+address-0x4000,'stage-control-'..address,function(off,data,mask)
    local pc=cpud.state['PC'].value
    if current_frame<trace_from or (pc~=address and pc~=address+1) then return end
    if cdram:read_block(0x3690+shift,8)~=string.char(0xa5,0x42,0x05,0x43,0xd0,0x06,0xa5,0x2f) then return end
    if base==0x76d3 then
     local pointer=cpu:read_u8(0x1f0046)+256*cpu:read_u8(0x1f0047)
     local handler=cdram:read(pointer-0x4000+1)+256*cdram:read(pointer-0x4000+2)-shift
     if handler>=0x8be9 and handler<=0x8c4b then
      pending=string.pack('<I4I2',current_frame,handler)..ramitem:read_block(0,8192)
     end
    elseif pending then
     stage_controls:write(pending..string.pack('<I4I2',current_frame,0)..ramitem:read_block(0,8192));pending=nil
    end
   end)
  end
 end
end
local stage_events = player_flow and assert(io.open('stage-events.bin','wb')) or nil
if stage_events then
 local pending=nil
 for _,shift in ipairs({0,-0x217}) do
  for _,base in ipairs({0x76d3,0x76c4}) do
   local address=base+shift
   taps[#taps+1]=cpu:install_read_tap(0x100000+address-0x4000,0x100000+address-0x4000,'stage-event-'..address,function(off,data,mask)
    local pc=cpud.state['PC'].value
    if current_frame<trace_from or (pc~=address and pc~=address+1) then return end
    if cdram:read_block(0x3690+shift,8)~=string.char(0xa5,0x42,0x05,0x43,0xd0,0x06,0xa5,0x2f) then return end
    if base==0x76d3 then
     local pointer=cpu:read_u8(0x1f0046)+256*cpu:read_u8(0x1f0047)
     local handler=cdram:read(pointer-0x4000+1)+256*cdram:read(pointer-0x4000+2)-shift
     assert(not pending,'Nested stage event')
     pending=string.pack('<I4I2',current_frame,handler)..ramitem:read_block(0,8192)
    elseif pending then
     stage_events:write(pending..string.pack('<I4I2',current_frame,0)..ramitem:read_block(0,8192));pending=nil
    end
   end)
  end
 end
end
local round_exit = player_flow and assert(io.open('round-exit.csv','w')) or nil
if round_exit then
 round_exit:write('frame,pc,round,paused,transition,stopped,lives,life_pickup\n')
 for _,canonical in ipairs({0x8daa,0x8db2,0x8dbf,0x8dc3,0x8dcc,0x8dcf,0x8dd3,0x6042,0x6053,0x605e,0x6060}) do
  local address=canonical
  if stage>0 and canonical>=0x8000 and canonical~=0x9eb1 then address=address-535 end
  taps[#taps+1]=cpu:install_read_tap(0x100000+address-0x4000,0x100000+address-0x4000,'round-exit-'..address,function(off,data,mask)
   local pc=cpud.state['PC'].value
   if current_frame<trace_from or (pc~=address and pc~=address+1) then return end
   -- Normalize logged labels to round-one addresses; tap the selected resource.
   if cpu:read_u8(0x1f004b)>stage+1 then return end
   round_exit:write(string.format('%d,%04x,%d,%d,%d,%d,%d,%d\n',current_frame,canonical,
    cpu:read_u8(0x1f004b),cpu:read_u8(0x1f004f),cpu:read_u8(0x1f0050),
    cpu:read_u8(0x1f0048),cpu:read_u8(0x1f004d),cpu:read_u8(0x1f0064)))
  end)
 end
end
local final_exit = player_flow and stage==9 and assert(io.open('final-exit.csv','w')) or nil
if final_exit then
 final_exit:write('frame,pc,paused,transition\n')
 for _,address in ipairs({0xa5ff,0xa60c,0x8ba8,0x8bb5,0x8bbc,0x6042}) do
  taps[#taps+1]=cpu:install_read_tap(0x100000+address-0x4000,0x100000+address-0x4000,'final-exit-'..address,function(off,data,mask)
   local pc=cpud.state['PC'].value
   if current_frame<trace_from or (pc~=address and pc~=address+1) or cpu:read_u8(0x1f004b)~=9 then return end
   final_exit:write(string.format('%d,%04x,%d,%d\n',current_frame,address,cpu:read_u8(0x1f004f),cpu:read_u8(0x1f0050)))
  end)
 end
end
local boss_effect_task = player_flow and assert(io.open('boss-effect-task.bin','wb')) or nil
if boss_effect_task then
 local pending=nil
 for _,canonical in ipairs({0x8de3,0x8da6}) do
  local address=canonical
  if stage>0 and canonical>=0x8000 and canonical~=0x9eb1 then address=address-535 end
  taps[#taps+1]=cpu:install_read_tap(0x100000+address-0x4000,0x100000+address-0x4000,'boss-effect-task-'..address,function(off,data,mask)
   local pc=cpud.state['PC'].value
   if current_frame<trace_from or (pc~=address and pc~=address+1) then return end
   if cpu:read_u8(0x1f004b)~=stage then return end
   if canonical==0x8de3 then
    pending=string.pack('<I4BB',current_frame,0,0)..ramitem:read_block(0,8192)
   elseif pending then
    boss_effect_task:write(pending..string.pack('<I4BB',current_frame,cpud.state['X'].value,canonical==0x8134 and 2 or 1)..ramitem:read_block(0,8192));pending=nil
   end
  end)
 end
end
local boss_effect_birth = player_flow and assert(io.open('boss-effect-birth.bin','wb')) or nil
if boss_effect_birth then
 local pending=nil
 for _,canonical in ipairs({0x8de3,0x9eb1,0x8134}) do
  local address=canonical
  if stage>0 and canonical>=0x8000 and canonical~=0x9eb1 then address=address-535 end
  taps[#taps+1]=cpu:install_read_tap(0x100000+address-0x4000,0x100000+address-0x4000,'boss-effect-birth-'..address,function(off,data,mask)
   local pc=cpud.state['PC'].value
   if current_frame<trace_from or (pc~=address and pc~=address+1) then return end
   if cpu:read_u8(0x1f004b)~=stage then return end
   if canonical==0x8de3 then
    pending=string.pack('<I4BB',current_frame,0,0)..ramitem:read_block(0,8192)
   elseif pending then
    boss_effect_birth:write(pending..string.pack('<I4BB',current_frame,cpud.state['X'].value,canonical==0x8134 and 2 or 1)..ramitem:read_block(0,8192));pending=nil
   end
  end)
 end
end
local curve_birth = player_flow and assert(io.open('curve-birth.bin','wb')) or nil
if curve_birth then
 local pending=nil
 for _,address in ipairs({0xacf3,0x9eb1,0x8134}) do
  taps[#taps+1]=cpu:install_read_tap(0x100000+address-0x4000,0x100000+address-0x4000,'curve-birth-'..address,function(off,data,mask)
   local pc=cpud.state['PC'].value
   if current_frame<trace_from or (pc~=address and pc~=address+1) then return end
   if cpu:read_u8(0x1f004b)~=0 then return end
   if address==0xacf3 then
    pending=string.pack('<I4BB',current_frame,0,0)..ramitem:read_block(0,8192)
   elseif pending then
    curve_birth:write(pending..string.pack('<I4BB',current_frame,cpud.state['X'].value,address==0x8134 and 2 or 1)..ramitem:read_block(0,8192));pending=nil
   end
  end)
 end
end
local hover_birth = player_flow and assert(io.open('hover-birth.bin','wb')) or nil
if hover_birth then
 local pending=nil
 for _,address in ipairs({0xabf1,0x9eb1,0x8134}) do
  taps[#taps+1]=cpu:install_read_tap(0x100000+address-0x4000,0x100000+address-0x4000,'hover-birth-'..address,function(off,data,mask)
   local pc=cpud.state['PC'].value
   if current_frame<trace_from or (pc~=address and pc~=address+1) then return end
   if cpu:read_u8(0x1f004b)~=0 then return end
   if address==0xabf1 then
    pending=string.pack('<I4BB',current_frame,0,0)..ramitem:read_block(0,8192)
   elseif pending then
    hover_birth:write(pending..string.pack('<I4BB',current_frame,cpud.state['X'].value,address==0x8134 and 2 or 1)..ramitem:read_block(0,8192));pending=nil
   end
  end)
 end
end
local launcher_birth = player_flow and assert(io.open('launcher-birth.bin','wb')) or nil
if launcher_birth then
 local pending=nil
 for _,address in ipairs({0xb25a,0x9eb1,0x8134}) do
  taps[#taps+1]=cpu:install_read_tap(0x100000+address-0x4000,0x100000+address-0x4000,'launcher-birth-'..address,function(off,data,mask)
   local pc=cpud.state['PC'].value
   if current_frame<trace_from or (pc~=address and pc~=address+1) then return end
   if cpu:read_u8(0x1f004b)~=0 then return end
   if address==0xb25a then
    pending=string.pack('<I4BB',current_frame,0,0)..ramitem:read_block(0,8192)
   elseif pending then
    launcher_birth:write(pending..string.pack('<I4BB',current_frame,cpud.state['X'].value,address==0x8134 and 2 or 1)..ramitem:read_block(0,8192));pending=nil
   end
  end)
 end
end
local hopper_birth = player_flow and assert(io.open('hopper-birth.bin','wb')) or nil
if hopper_birth then
 local pending=nil
 for _,address in ipairs({0xb0da,0x9eb1,0x8134}) do
  taps[#taps+1]=cpu:install_read_tap(0x100000+address-0x4000,0x100000+address-0x4000,'hopper-birth-'..address,function(off,data,mask)
   local pc=cpud.state['PC'].value
   if current_frame<trace_from or (pc~=address and pc~=address+1) then return end
   if cpu:read_u8(0x1f004b)~=0 then return end
   if address==0xb0da then
    pending=string.pack('<I4BB',current_frame,0,0)..ramitem:read_block(0,8192)
   elseif pending then
    hopper_birth:write(pending..string.pack('<I4BB',current_frame,cpud.state['X'].value,address==0x8134 and 2 or 1)..ramitem:read_block(0,8192));pending=nil
   end
  end)
 end
end
if score_trace then
 local pending={}
 local saved={}
 local cases=os.getenv('PCE_SCORE_CASES')=='1'
 local sequences={[0]=0,[1]=0}
 local function inject(kind)
  local original={}; saved[kind]=original
  local function put(address,value)
   if original[address]==nil then original[address]=cpu:read_u8(0x1f0000+address) end
   cpu:write_u8(0x1f0000+address,value)
  end
  local n=sequences[kind];sequences[kind]=n+1
  if kind==1 then
   put(0x51,n%3);put(0x93,15);put(0x91,24)
   return
  end
  local case=n%287
  local value,command,threshold,lives=49950,case,0,2
  if case>=256 and case<283 then
   local limits={50000,100000,200000,400000,800000,1200000,1600000,2000000,4000000}
   threshold=math.floor((case-256)/3);value=limits[threshold+1]+(case-256)%3-1;command=0
  elseif case==283 then value=9999999;command=1
  elseif case==284 then value=1000000;command=255
  elseif case==285 then value=50000;command=0;lives=255
  elseif case==286 then value=9999999;command=0;threshold=9 end
  local function digits(address,number)
   local text=string.format('%08d',number)
   for i=1,8 do put(address+i-1,tonumber(text:sub(i,i))) end
  end
  digits(0xc4,value);digits(0xd4,case%3==0 and value or case%3==1 and 0 or 9999999)
  for i=0,15 do put(0x82+i,255) end
  local read=(n*5)%16
  put(0x82+read,command);put(0x92,read);put(0x93,(read+1)%16)
  put(0x54,threshold);put(0x4d,lives);put(0x6c,n%256);put(0x6d,n%256)
 end
 for _,spec in ipairs({{0x6cb3,0,0x102cb3},{0x6d3b,1,0x102d3b},{0x3d7e,2,0x1f1d7e},{0x3d90,3,0x1f1d90}}) do
  local address,phase,physical=table.unpack(spec)
  taps[#taps+1] = cpu:install_read_tap(physical,physical,'score-'..address,function(off,data,mask)
   local pc=cpud.state['PC'].value
   if current_frame<trace_from or (pc~=address and pc~=address+1) then return end
   local kind=math.floor(phase/2)
   if phase%2==0 then
    assert(not pending[kind],'Nested score trace')
    if cases then inject(kind) end
    pending[kind]=string.pack('<I4BB',current_frame,cpud.state['A'].value,phase)..ramitem:read_block(0,8192)
   elseif pending[kind] then
    local record=string.pack('<I4BB',current_frame,cpud.state['A'].value,phase)..ramitem:read_block(0,8192)
    score_trace:write(pending[kind]..record); pending[kind]=nil
    if saved[kind] then
     for offset,value in pairs(saved[kind]) do cpu:write_u8(0x1f0000+offset,value) end
     saved[kind]=nil
    end
   end
  end)
 end
end
local factory_trace = os.getenv('PCE_FACTORY_TRACE') == '1' and assert(io.open('factory.bin','wb')) or nil
local factory_pending = nil
local bullet_birth = factory_trace and assert(io.open('bullet-birth.bin','wb')) or nil
local bullet_pending = nil
if factory_trace then
 local function record(phase)
  return string.pack('<I4BB',current_frame,cpud.state['X'].value,phase)..ramitem:read_block(0,8192)
 end
 for _,shift in ipairs({0,-0x217}) do
  for _,spec in ipairs({{0x8119,0,string.char(0x82,0xbd,0x08,0x2e)},
                       {0x8128,1,string.char(0xa2,0x1f,0xbd,0x08)},
                       {0x8136,2,string.char(0x60)},
                       {0x8137,3,string.char(0xc2,0xb1,0x18,0x9d)},
                       {0x81c5,4,string.char(0x60)}}) do
   local address,phase,signature=spec[1]+shift,spec[2],spec[3]
   taps[#taps+1] = cpu:install_read_tap(0x100000+address-0x4000,0x100000+address-0x4000,'factory-'..address,function(off,data,mask)
    local pc=cpud.state['PC'].value
    if current_frame<trace_from or (pc~=address and pc~=address+1) or
       cdram:read_block(address-0x4000,#signature)~=signature then return end
    if phase==0 or phase==1 or phase==3 then
     assert(not factory_pending,'Nested factory trace'); factory_pending=record(phase)
    elseif factory_pending and ((phase==2 and factory_pending:byte(6)<2) or
           (phase==4 and factory_pending:byte(6)==3)) then
     factory_trace:write(factory_pending..record(phase)); factory_pending=nil
     if phase==2 and bullet_pending and cpud.state['X'].value>=32 then
      bullet_birth:write(bullet_pending..record(2)); bullet_pending=nil
     end
    end
   end)
  end
  for _,spec in ipairs({{0x8a29,0,string.char(0x20,(0x8119+shift)%256,math.floor((0x8119+shift)/256))},
                       {0x8a5a,1,string.char(0x20,0xb1,0x9e)}}) do
   local address,phase,signature=spec[1]+shift,spec[2],spec[3]
   taps[#taps+1] = cpu:install_read_tap(0x100000+address-0x4000,0x100000+address-0x4000,'bullet-birth-'..address,function(off,data,mask)
    local pc=cpud.state['PC'].value
    if current_frame<trace_from or (pc~=address and pc~=address+1) or
       cdram:read_block(address-0x4000,#signature)~=signature then return end
    if phase==0 then
     assert(not bullet_pending,'Nested bullet birth')
     bullet_pending=string.pack('<I4BB',current_frame,cpud.state['Y'].value,0)..ramitem:read_block(0,8192)
    elseif bullet_pending then bullet_birth:write(bullet_pending..record(1)); bullet_pending=nil end
   end)
  end
 end
end
local contacts = os.getenv('PCE_CONTACT_TRACE') == '1' and assert(io.open('contacts.bin','wb')) or nil
local common_trace = os.getenv('PCE_COMMON_TRACE') == '1' and assert(io.open('common.bin','wb')) or nil
local common_pending = nil
if common_trace then
 local cases=os.getenv('PCE_COMMON_CASES')=='1'
 local saved=nil
 local sequence=0
 local function inject()
  local i=cpud.state['X'].value; saved={}
  local function put(address,value)
   if saved[address]==nil then saved[address]=cpu:read_u8(0x1f0000+address) end
   cpu:write_u8(0x1f0000+address,value)
  end
  -- Save the three slots that these fixtures may alter beyond their state.
  for base=0xa48,0xdea,30 do
   for _,slot in ipairs({0,28,29}) do saved[base+slot]=cpu:read_u8(0x1f0000+base+slot) end
  end
  for slot=0,29 do put(0xa48+slot,0) end
  local values={[0x49]=0,[0x59]=3,[0x94]=0x80,[0x95]=0,[0x96]=128,[0x98]=0,[0x99]=112,[0xaf]=0,
   [0xa5]=0,[0xae]=0,[0x5d]=0,[0x4d]=2,[0x64]=0,[0xe06]=3,[0xe07]=3,
   [0xe08+i]=0x80,[0xe28+i]=0,[0xe48+i]=128,[0xe88+i]=0,[0xea8+i]=112,
   [0xf68+i]=0,[0xf88+i]=0,[0xfa8+i]=0,[0xfc8+i]=0,
   [0x1028+i]=2,[0x1068+i]=8,[0x1088+i]=8,[0x10a8+i]=1,[0x10c8+i]=0,[0x10e8+i]=2,
   [0x1108+i]=0,[0x1128+i]=2,[0x1148+i]=0,[0x1168+i]=0,[0x1188+i]=3,
   [0xa48]=0x80,[0xa66]=0,[0xa84]=128,[0xac0]=0,[0xade]=112,[0xc46]=0,[0xc82]=1,[0xca0]=3,[0xcbe]=8,
   [0xd90]=0,[0xd18]=0x92,[0xd36]=0x3e,[0xd34]=0x9d,[0xd52]=0x22,[0xd35]=0x9d,[0xd53]=0x22}
  local variants={{},{[0x1028+i]=1},{[0x1148+i]=8,[0x1028+i]=1},
   {[0x1148+i]=8,[0x1028+i]=1,[0x10e8+i]=1},{[0x10c8+i]=1},{[0x10c8+i]=2},
   {[0x10c8+i]=255},{[0x1108+i]=1},{[0xaf]=1},{[0x94]=0x40,[0x1108+i]=2},
   {[0x94]=0},{[0xe08+i]=0x40,[0x1108+i]=2},{[0x1148+i]=1},{[0x1148+i]=2},
   {[0xa64]=0x80},{[0xa65]=0x80},{[0xa64]=0x80,[0xa65]=0x80},{[0xd90]=1},
   {[0x1128+i]=1,[0x12a8+i]=0x8a,[0x12c8+i]=0xc0,[0x1148+i]=4,[0x1108+i]=2},
   {[0xe28+i]=2,[0xe48+i]=0,[0x1148+i]=4,[0x1108+i]=2}}
  for item=1,9 do variants[#variants+1]={[0x1168+i]=item,[0x1148+i]=1} end
  for address,value in pairs(variants[sequence%#variants+1]) do values[address]=value end
  sequence=sequence+1
  for address,value in pairs(values) do put(address,value) end
 end
 local function record(phase)
  return string.pack('<I4BB',current_frame,cpud.state['X'].value,phase)..ramitem:read_block(0,8192)
 end
 for _,spec in ipairs({{0x9eb1,0},{0x9eda,1},{0xa217,2}}) do
  local address,phase=table.unpack(spec)
  taps[#taps+1] = cpu:install_read_tap(0x100000+address-0x4000,0x100000+address-0x4000,'common-'..address,function(off,data,mask)
   local pc=cpud.state['PC'].value
   if current_frame<trace_from or (pc~=address and pc~=address+1) then return end
   if phase==0 then
    assert(not common_pending,'Nested common task')
    if cases then inject() end
    common_pending=record(0)
    runtime_record(3)
   elseif common_pending then
    common_trace:write(common_pending..record(phase)); common_pending=nil
    runtime_record(phase==1 and 5 or 4)
    if saved then
     for address,value in pairs(saved) do cpu:write_u8(0x1f0000+address,value) end
     saved=nil
    end
   end
  end)
 end
end
if player_runtime then
 taps[#taps+1] = cpu:install_read_tap(0x105e2a,0x105e2a,'player-trail',function(off,data,mask)
  local pc=cpud.state['PC'].value
  if current_frame>=trace_from and (pc==0x9e2a or pc==0x9e2b) then runtime_record(6) end
 end)
end
local order = contacts and assert(io.open('weapon-order.csv','w')) or nil
local tasks = contacts and assert(io.open('weapon-tasks.bin','wb')) or nil
local function task_record(kind)
 if tasks then tasks:write(string.pack('<I4BB',current_frame,kind,cpud.state['X'].value)..ramitem:read_block(0,8192)) end
end
if order then order:write('frame,task,index\n') end
local contact_pending = false
if contacts then
 local function capture_contact(phase)
  local record=string.pack('<I4BB',current_frame,cpud.state['X'].value,phase)..ramitem:read_block(0,8192)
  if phase==0 then contact_pending=record else contacts:write(contact_pending..record) end
  task_record(phase==0 and 3 or phase==1 and 4 or 5)
 end
 taps[#taps+1] = cpu:install_read_tap(0x10601e,0x10601e,'collision-entry',function(off,data,mask)
  local pc=cpud.state['PC'].value
  if current_frame>=trace_from and (pc==0xa01e or pc==0xa01f) then
   order:write(string.format('%d,contact,%d\n',current_frame,cpud.state['X'].value))
   assert(not contact_pending,'Nested collision trace'); capture_contact(0)
  end
 end)
 taps[#taps+1] = cpu:install_read_tap(0x1060e9,0x1060e9,'collision-exit',function(off,data,mask)
  local pc=cpud.state['PC'].value
  if contact_pending and (pc==0xa0e9 or pc==0xa0ea) then capture_contact(1); contact_pending=false end
 end)
 taps[#taps+1] = cpu:install_read_tap(0x1061df,0x1061df,'collision-depleted',function(off,data,mask)
  local pc=cpud.state['PC'].value
  if contact_pending and (pc==0xa1df or pc==0xa1e0) then capture_contact(2); contact_pending=false end
 end)
end
if order then
 for _,address in ipairs({0x90b8,0x8ea1}) do
  taps[#taps+1] = cpu:install_read_tap(0x100000+address-0x4000,0x100000+address-0x4000,'weapon-order-'..address,function(off,data,mask)
   local pc=cpud.state['PC'].value
   if current_frame>=trace_from and (pc==address or pc==address+1) and
      cdram:read_block(address-0x4000,4)==string.char(0xa5,0x94,0xc9,0x80) then
    order:write(string.format('%d,weapons,0\n',current_frame))
    task_record(0)
   end
  end)
 end
 for _,spec in ipairs({{0x9a91,1,0x60},{0x987a,1,0x60},{0x90c5,1,0x60},{0x8eae,1,0x60},{0x9e2a,2,0xa5}}) do
  local address,kind,opcode=table.unpack(spec)
  taps[#taps+1] = cpu:install_read_tap(0x100000+address-0x4000,0x100000+address-0x4000,'weapon-task-'..address,function(off,data,mask)
   local pc=cpud.state['PC'].value
   if current_frame>=trace_from and (pc==address or pc==address+1) and
      cdram:read_block(address-0x4000,1)==string.char(opcode) then task_record(kind) end
  end)
 end
end
local enemy_trace = os.getenv('PCE_ENEMY_TRACE') == '1' and assert(io.open('enemy.bin','wb')) or nil
local enemy_pending = nil
if enemy_trace then
 local function record(phase)
  return string.pack('<I4BB',current_frame,cpud.state['X'].value,phase)..ramitem:read_block(0,8192)
 end
 local function hook(address,phase,entry)
  taps[#taps+1] = cpu:install_read_tap(0x100000+address-0x4000,0x100000+address-0x4000,'enemy-'..address,function(off,data,mask)
   local pc=cpud.state['PC'].value
   if current_frame<trace_from or (pc~=address and pc~=address+1) then return end
   if entry then
    assert(not enemy_pending,'Nested enemy trace')
    enemy_pending=record(phase)
   elseif enemy_pending and (phase~=3 or enemy_pending:byte(6)==0) then
    enemy_trace:write(enemy_pending..record(phase)); enemy_pending=nil
   end
  end)
 end
 hook(0x9eb1,0,true)
 hook(0xa00a,1,false)
 hook(0x9eda,2,false)
 hook(0xa20f,3,false)
 hook(0xa1df,4,true)
 hook(0xa217,5,false)
end
local actor_step = os.getenv('PCE_AI_TRACE')=='1' and assert(io.open('actor-step.bin','wb')) or nil
if actor_step then
 local pending=nil
 for _,address in ipairs({0x9e82,0x9e22}) do
  taps[#taps+1]=cpu:install_read_tap(0x100000+address-0x4000,0x100000+address-0x4000,'actor-step-'..address,function(off,data,mask)
   local pc=cpud.state['PC'].value
   if current_frame<trace_from or (pc~=address and pc~=address+1) then return end
   local record=string.pack('<I4BB',current_frame,cpud.state['X'].value,address==0x9e82 and 0 or 1)..ramitem:read_block(0,8192)
   if address==0x9e82 then assert(not pending,'Nested actor step');pending=record
   elseif pending then actor_step:write(pending..record);pending=nil end
  end)
 end
end
local actor_loop = os.getenv('PCE_AI_TRACE')=='1' and assert(io.open('actor-loop.bin','wb')) or nil
if actor_loop then
 local pending=nil
 for _,address in ipairs({0x9e17,0x9e27}) do
  taps[#taps+1]=cpu:install_read_tap(0x100000+address-0x4000,0x100000+address-0x4000,'actor-loop-'..address,function(off,data,mask)
   local pc=cpud.state['PC'].value
   if current_frame<trace_from or (pc~=address and pc~=address+1) then return end
   local record=string.pack('<I4BB',current_frame,cpud.state['X'].value,address==0x9e17 and 0 or 1)..ramitem:read_block(0,8192)
   if address==0x9e17 then assert(not pending,'Nested actor step');pending=record
   elseif pending then actor_loop:write(pending..record);pending=nil end
  end)
 end
end
local actor_scroll = os.getenv('PCE_AI_TRACE')=='1' and assert(io.open('actor-scroll.bin','wb')) or nil
if actor_scroll then
 local pending=nil
 for _,address in ipairs({0x9e82,0x9e90}) do
  taps[#taps+1]=cpu:install_read_tap(0x100000+address-0x4000,0x100000+address-0x4000,'actor-scroll-'..address,function(off,data,mask)
   local pc=cpud.state['PC'].value
   if current_frame<trace_from or (pc~=address and pc~=address+1) then return end
   local record=string.pack('<I4BB',current_frame,cpud.state['X'].value,address==0x9e82 and 0 or 1)..ramitem:read_block(0,8192)
   if address==0x9e82 then assert(not pending,'Nested actor scroll');pending=record
   elseif pending then actor_scroll:write(pending..record);pending=nil end
  end)
 end
end
local ai_trace = os.getenv('PCE_AI_TRACE') == '1' and assert(io.open('ai.bin','wb')) or nil
local ai_pending = nil
if ai_trace then
 local function record(phase)
  return string.pack('<I4BB',current_frame,cpud.state['X'].value,phase)..ramitem:read_block(0,8192)
 end
 local function hook(address,phase)
  taps[#taps+1] = cpu:install_read_tap(0x100000+address-0x4000,0x100000+address-0x4000,'ai-'..address,function(off,data,mask)
   local pc=cpud.state['PC'].value
   if current_frame<trace_from or (pc~=address and pc~=address+1) then return end
   if phase==0 then
    assert(not ai_pending,'Nested AI trace'); ai_pending=record(0)
   elseif ai_pending and cpud.state['X'].value==ai_pending:byte(5) then
    -- An AI routine can spawn a child and run that child's common task before
    -- finishing its own update. Pair only the original slot's exit.
    ai_trace:write(ai_pending..record(phase)); ai_pending=nil
   end
  end)
 end
 hook(0x9e82,0)
 hook(0x9eb1,1)
 hook(0xa20f,2)
 hook(0x9eda,3)
end
local player_trace = os.getenv('PCE_PLAYER_TRACE') == '1' and assert(io.open('player-contact.bin','wb')) or nil
local player_pending = nil
local pickup_commands = os.getenv('PCE_PICKUP_CASES') == '1' and assert(io.open('pickup-commands.csv','w')) or nil
local player_sequence = 0
if pickup_commands then pickup_commands:write('sequence,kind,value\n') end
if player_trace then
 -- Reference-only branch fixtures. Restore every injected field and option
 -- handler after observing the real routine, so fabricated options never run.
 local cases = os.getenv('PCE_PLAYER_CASES') == '1'
 local pickup_cases = os.getenv('PCE_PICKUP_CASES') == '1'
 local saved = nil
 local case_index = 0
 local function inject()
  local i=cpud.state['X'].value
  local values={[0x49]=0,[0x94]=0x80,[0x95]=0,[0x96]=128,[0x98]=0,[0x99]=112,[0xaf]=0,
   [0xe08+i]=0x80,[0xe28+i]=0,[0xe48+i]=128,[0xe88+i]=0,[0xea8+i]=112,
   [0x1148+i]=0,[0x10c8+i]=0,[0x1068+i]=8,[0x1088+i]=8,[0x1168+i]=0,
   [0xa64]=0,[0xa65]=0}
  local variants={
   {},{[0x1148+i]=2},{[0xe08+i]=0x40},{[0x94]=0x40},{[0xaf]=1},
   {[0x10c8+i]=1},{[0x1148+i]=8},{[0xa64]=0x80},{[0xa65]=0x80},
   {[0xa64]=0x80,[0xa65]=0x80},{[0xa64]=0x40,[0xa65]=0x80},
   {[0x1068+i]=251},{[0x1088+i]=248},{[0xe48+i]=141},{[0xe48+i]=140},
   {[0xea8+i]=128},{[0xea8+i]=127},{[0xe28+i]=255,[0xe48+i]=255},
   {[0xe28+i]=0,[0xe48+i]=0,[0x95]=255,[0x96]=255},
   {[0xe08+i]=0},{[0x1148+i]=1},{[0xa64]=0x40,[0xa65]=0x40},
   {[0xe48+i]=115},{[0xe48+i]=116},{[0xea8+i]=96},{[0xea8+i]=97}}
  for address,value in pairs(variants[case_index%#variants+1]) do values[address]=value end
  if pickup_cases then
   values={[0x49]=0,[0x94]=0x80,[0x95]=0,[0x96]=128,[0x98]=0,[0x99]=112,[0xaf]=0,
    [0xe08+i]=0x80,[0xe28+i]=0,[0xe48+i]=128,[0xe88+i]=0,[0xea8+i]=112,
    [0x1148+i]=0,[0x10c8+i]=0,[0x1068+i]=8,[0x1088+i]=8,
    [0xa5]=0,[0xae]=0,[0x5d]=0,[0x4d]=2,[0x64]=0,[0xa64]=0,[0xa65]=0,
    [0xe06]=3,[0xe07]=3}
   local pv={}
   for item=1,9 do pv[#pv+1]={[0x1168+i]=item} end
   for chain=1,4 do pv[#pv+1]={[0x1168+i]=1,[0x5d]=chain} end
   for item=2,4 do
    for _,power in ipairs({3,4,254,255}) do pv[#pv+1]={[0x1168+i]=item,[0xae]=power} end
   end
   for _,state in ipairs({0,0x40,0x80}) do
    for upper=1,3 do
     for lower=1,3 do pv[#pv+1]={[0x1168+i]=5,[0xa64]=0x80,[0xa65]=state,[0xe06]=upper,[0xe07]=lower} end
    end
   end
   pv[#pv+1]={[0x1168+i]=9,[0x4d]=255,[0x64]=255}
   for address,value in pairs(pv[case_index%#pv+1]) do values[address]=value end
  end
  case_index=case_index+1; saved={}
  if pickup_cases then
   for address=0xa48,0xdea,30 do
    saved[address+28]=cpu:read_u8(0x1f0000+address+28)
    saved[address+29]=cpu:read_u8(0x1f0000+address+29)
   end
  end
  for _,address in ipairs({0xd16,0xd17,0xcf8,0xcf9}) do saved[address]=cpu:read_u8(0x1f0000+address) end
  for address,value in pairs(values) do
   if saved[address]==nil then saved[address]=cpu:read_u8(0x1f0000+address) end
   cpu:write_u8(0x1f0000+address,value)
  end
 end
 local function record(phase)
  return string.pack('<I4BB',current_frame,cpud.state['X'].value,phase)..ramitem:read_block(0,8192)
 end
 local function hook(address,phase)
  taps[#taps+1] = cpu:install_read_tap(0x100000+address-0x4000,0x100000+address-0x4000,'player-contact-'..address,function(off,data,mask)
   local pc=cpud.state['PC'].value
   if current_frame<trace_from or (pc~=address and pc~=address+1) then return end
   if phase==0 then
    assert(not player_pending,'Nested player contact trace')
    if cases or pickup_cases then inject() end
    player_sequence=player_sequence+1
    player_pending=record(0)
   elseif player_pending then
    player_trace:write(player_pending..record(phase)); player_pending=nil
    if saved then
     for address,value in pairs(saved) do cpu:write_u8(0x1f0000+address,value) end
     saved=nil
    end
   end
  end)
 end
 hook(0xa0e9,0)
 hook(0xa20f,1)
end
if pickup_commands then
 for _,spec in ipairs({{0x3d7e,'score'},{0x3dcd,'sound'}}) do
  local address,kind=table.unpack(spec)
  taps[#taps+1] = cpu:install_read_tap(0x1f0000+address-0x2000,0x1f0000+address-0x2000,'pickup-command-'..address,function(off,data,mask)
   local pc=cpud.state['PC'].value
   if player_pending and (pc==address or pc==address+1) then
    pickup_commands:write(string.format('%d,%s,%d\n',player_sequence,kind,cpud.state['A'].value))
   end
  end)
 end
end
for _, key in ipairs({'bxr','byr','mwr','cr','hdr','hsr','vpr','vdw'}) do
    regs[key] = emu.item(vd['0/m_' .. key])
end
local log = assert(io.open('frames.csv', 'w'))
log:write('frame,stage,lives,weapon,power,charge,bxr,byr,mwr,cr,hdr,hsr,vpr,vdw\n')
local function binary(path, bytes)
    local f = assert(io.open(path, 'wb')); f:write(bytes); f:close()
end
local function ram()
    return ramitem:read_block(0,8192)
end
for f=1,frames do
    current_frame = f
    if f==180 or f==630 or f==1500 then buttons['P1 Run']:set_value(1) end
    if f==188 or f==638 or f==1508 then buttons['P1 Run']:set_value(0) end
    if f==600 then direction['P1 Down']:set_value(1) end
    if f==608 then direction['P1 Down']:set_value(0) end
    -- Published PCE cheat addresses use bank F8 + 13-bit offset.
    -- Used only to select/capture reference stages, never as port rules.
    if f>=1400 and f<=1500 then cpu:write_u8(0x1f004b,stage) end
    if f>1800 then
        if invulnerable then cpu:write_u8(0x1f0049,1) end
        if boss_fast then cpu:write_u8(0x1f10e8,1) end
        if not input_path then buttons['P1 Button I']:set_value(fire=='hold' and 1 or fire=='pulse' and (f%4<2 and 1 or 0) or 0)
        buttons['P1 Button II']:set_value(fire=='charge' and (f%180<150 and 1 or 0) or 0) end
    end
    for _,event in ipairs(inputs[f] or {}) do
      if event.addr then cpu:write_u8(tonumber(event.addr,16),tonumber(event.value,16))
      else local field=buttons[event.field] or direction[event.field]; assert(field,event.field); field:set_value(tonumber(event.value)) end
    end
    emu.wait_next_update()
    if logic and f>=trace_from then
      logic:write(string.pack('<I4',f)..ramitem:read_block(0,256)..ramitem:read_block(0x228,8)..ramitem:read_block(0xa5c,5))
    end
    if full_state and f>=trace_from then full_state:write(string.pack('<I4',f)..ram()) end
    if f%interval==0 and f>=snapshot_from then
        if f>=1920 and f<=2160 then binary(string.format('code-%06d.bin',f),cdram:read_block(0,65536)); binary('banks.bin',banks:read_block(0,8)) end
        if late_code_from>0 and f>=late_code_from then
            binary(string.format('code-%06d.bin',f),cdram:read_block(0,65536))
            binary(string.format('banks-%06d.bin',f),banks:read_block(0,8))
        end
        local name=string.format('f%06d',f)
        m.screens[':screen']:snapshot(name..'.png')
        binary(name..'-vram.bin',vram:read_block(0,65536))
        binary(name..'-palette.bin',palette:read_block(0,1024))
        binary(name..'-sat.bin',sat:read_block(0,512))
        binary(name..'-ram.bin',ram())
        log:write(string.format('%d,%d,%d,%d,%d,%d',f,cpu:read_u8(0x1f004b),cpu:read_u8(0x1f004d),cpu:read_u8(0x1f00a5),cpu:read_u8(0x1f00ae),cpu:read_u8(0x1f0056)))
        for _,key in ipairs({'bxr','byr','mwr','cr','hdr','hsr','vpr','vdw'}) do log:write(','..regs[key]:read(0)) end
        log:write('\n'); log:flush()
    end
end
log:close(); trace:close(); if logic then logic:close() end
if full_state then full_state:close() end
if contacts then contacts:close() end
if order then order:close() end
if tasks then tasks:close() end
if enemy_trace then enemy_trace:close() end
if actor_loop then actor_loop:close() end
if actor_step then actor_step:close() end
if actor_scroll then actor_scroll:close() end
if ai_trace then ai_trace:close() end
if player_trace then player_trace:close() end
if pickup_commands then pickup_commands:close() end
if random_trace then random_trace:close() end
if factory_trace then factory_trace:close() end
if bullet_birth then bullet_birth:close() end
if common_trace then common_trace:close() end
if score_trace then score_trace:close() end
if hopper_birth then hopper_birth:close() end
if launcher_birth then launcher_birth:close() end
if hover_birth then hover_birth:close() end
if curve_birth then curve_birth:close() end
if boss_effect_birth then boss_effect_birth:close() end
if boss_effect_task then boss_effect_task:close() end
if round_exit then round_exit:close() end
if final_exit then final_exit:close() end
if gallery_trace then gallery_trace:close();gallery_birth:close() end
if stage_events then stage_events:close() end
if stage_controls then stage_controls:close() end
if stage_trace then stage_trace:close() end
if reset_file then reset_file:close() end
if play_trace then play_trace:close() end
if player_flow then player_flow:close() end
if player_runtime then player_runtime:close() end
binary('complete.txt','COMPLETE\n')
m:exit()
