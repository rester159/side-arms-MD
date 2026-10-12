#!/usr/bin/env python3
"""Capture each distinct original music command, with isolated per-run state."""
import concurrent.futures,json,subprocess,sys
from inspect_hucard_music import ROOT,metadata,inspect_capture

def main():
    data=metadata((ROOT/'.local/pce-hucard/SideArms - Hyper Dyne (USA).pce').read_bytes())
    tracks=[t for t in data['music'] if 'alias_of' not in t]
    def capture(track):
        command=track['command'];name=f'music-{command:02x}-reference-v1';out=ROOT/'.local/pce-hucard'/name
        if out.exists():
            assert (out/'complete.txt').exists(),f'Incomplete capture exists: {out}; inspect its process before retrying'
        else:subprocess.run([sys.executable,str(ROOT/'tools/capture_pce_hucard.py'),name,'--command',str(command),'--frames','9000'],check=True,stdout=subprocess.DEVNULL)
        result=dict(command=command,capture=str(out.relative_to(ROOT)),**inspect_capture(out))
        print(f'Captured music {command:02x}: {result["ticks"]} sound ticks',flush=True)
        return result
    with concurrent.futures.ThreadPoolExecutor(max_workers=3) as pool:results=list(pool.map(capture,tracks))
    manifest=dict(source_sha256=data['source_sha256'],captures=results)
    (ROOT/'.local/pce-hucard/music-captures.json').write_text(json.dumps(manifest,indent=2)+'\n')
    print(f'{len(results)} source captures complete',flush=True)
if __name__=='__main__':main()
