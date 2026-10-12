#!/usr/bin/env python3
"""Capture original HuCard PSG writes for conversion and playback verification."""
import argparse,os,subprocess,shutil
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
def main():
 p=argparse.ArgumentParser(description=__doc__);p.add_argument('name');p.add_argument('--rom',type=Path,default=ROOT/'.local/pce-hucard/SideArms - Hyper Dyne (USA).pce');p.add_argument('--command',type=lambda s:int(s,0));p.add_argument('--frames',type=int,default=1200);p.add_argument('--machine',choices=('tg16','pce'),default='tg16');p.add_argument('--audio',action='store_true',help='Write original emulated PSG audio to source.wav');a=p.parse_args()
 assert Path(a.name).name==a.name
 out=ROOT/'.local/pce-hucard'/a.name;out.mkdir()
 for n in ('cfg','nvram','snap','sta','home'):(out/n).mkdir()
 cmd=[shutil.which('mame'),a.machine,'-cart',str(a.rom.resolve()),'-autoboot_delay','0','-autoboot_script',str(ROOT/'tools/pce_hucard_capture.lua'),'-video','none','-sound','sdl' if a.audio else 'none','-nothrottle','-seconds_to_run',str(a.frames//60+5),'-skip_gameinfo','-noconfirm_quit','-noplugins','-nohttp','-nowriteconfig','-cfg_directory','cfg','-nvram_directory','nvram','-state_directory','sta','-snapshot_directory','snap','-homepath','home','-inipath','home']
 if a.audio:cmd += ['-wavwrite','source.wav','-samplerate','48000']
 with (out/'mame.log').open('w') as log:
  r=subprocess.run(cmd,cwd=out,env=dict(os.environ,SDL_VIDEODRIVER='dummy',SDL_AUDIODRIVER='dummy',PCE_FRAMES=str(a.frames),PCE_COMMAND='' if a.command is None else str(a.command)),stdout=log,stderr=subprocess.STDOUT,timeout=max(45,a.frames/30))
 if r.returncode or not (out/'complete.txt').exists():raise SystemExit(f'Capture failed ({r.returncode}): {out}/mame.log')
 print(out)
if __name__=='__main__':main()
