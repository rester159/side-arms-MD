#!/usr/bin/env python3
"""Resolve explicit BC art choices without treating skipped cards as approvals.
Review images/manifests remain local; authoritative user choices are versioned.
"""
import json,re
from pathlib import Path
from collections import Counter,defaultdict
ROOT=Path(__file__).resolve().parents[1]

def identity(key):
    if key.startswith('launcher-'):return 0x3688,int(key.split('-')[1],16),5
    if m:=re.fullmatch(r'sprite-(?:0x)?([0-9a-f]+)-([0-9a-f]+)-(?:pal(\d+)|0x([0-9a-f]+))',key):
        return int(m[1],16),int(m[2],16),int(m[3]) if m[3] else int(m[4],16)&15
    if m:=re.fullmatch(r'actor-([0-9a-f]+)-([0-9a-f]+)-p(\d+)',key):
        return int(m[1],16),int(m[2],16),int(m[3])
    return None

def resolve(cards,export):
    assert export['schema']==1 and export['review']=='bc-art-review-v1'
    known={c['id'] for c in cards};explicit={};groups=defaultdict(list)
    for d in export['decisions']:
        assert d['id'] in known, f'Unknown review card: {d["id"]}'
        assert d['id'] not in explicit, f'Duplicate review card: {d["id"]}'
        assert d['decision'] in ('keep','recolor','new','pending')
        explicit[d['id']]=d
        ident=identity(d['id'])
        if ident and d['decision']!='pending':groups[(ident[0],ident[2])].append(d)
    result=[]
    for c in cards:
        key=c['id'];ident=identity(key);d=explicit.get(key)
        row=dict(id=key,title=c['title'],decision='pending',provenance='unresolved',evidence=[])
        if ident:row.update(family=f'0x{ident[0]:04x}',pose=f'0x{ident[1]:02x}',source_palette=ident[2])
        if d and d['decision']!='pending':
            row.update(decision=d['decision'],provenance='user',evidence=[key],note=d.get('note',''))
        elif c['kind']=='Backgrounds':
            row.update(decision='keep',provenance='user_global_default',reason='User: backgrounds appear unchanged; preserve Genesis colors. Tile identity remains unverified.',identity_verified=False)
        elif ident:
            if ident in ((0x36c8,0,1),(0x36b4,0,9),(0x367a,0x28,0)):
                row.update(decision='new',provenance='inferred',evidence=['tools/data/bc_unique_shapes.json'],reason='BC-specific effect or pickup geometry; retain verified captured shape with shade-preserving Genesis palette conversion.')
                result.append(row)
                continue
            if ident in ((0x3682,12,5),(0x367a,0x24,0),(0x367a,0x2a,1),(0x367a,0x2e,2)):
                row.update(decision='recolor',provenance='inferred',evidence=['docs/bc-art-review-decisions.md#remaining-pickup-and-missile-pairings'],reason='Corrected and visually verified Genesis pose; infer BC recoloring from user direction without propagating to unrelated pickups.')
                result.append(row)
                continue
            if ident[0]==0x36cc:
                row.update(decision='new',provenance='inferred',evidence=['tools/data/bc_beam_shapes.json'],reason='BC growth, turn and corner geometry has no direct ordinary Genesis beam match; retain captured shape with the existing Genesis palette ramps.')
                result.append(row)
                continue
            if ident[2]==1 and ((ident[0]==0x36c8 and ident[1]==2) or (ident[0]==0x36ce and ident[1] in (0,2))):
                row.update(decision='recolor',provenance='inferred',evidence=['docs/bc-art-review-decisions.md#radial-shot-and-rain-colors'],reason='Verified horizontal beam or rain-orb correspondence; infer orange BC recoloring from user direction.')
                result.append(row)
                continue
            if ident[0]==0x3690 and ident[1] in range(0,64,8) and ident[2] in (5,11,15):
                row.update(decision='recolor',provenance='inferred',evidence=['docs/bc-art-review-decisions.md#rotating-pod-correspondence'],reason='Verified rotating-pod sequence 7C0/7C2/7C4/7C6/7D0/7E0/7E2/7E4; infer BC recoloring from user direction, keeping source palettes separate.')
                result.append(row)
                continue
            if ident[0]==0x3696 and ident[1] in (0,8,16,18,20) and ident[2] in (8,15):
                row.update(decision='recolor',provenance='inferred',evidence=['docs/bc-art-review-decisions.md#splitting-capsule-correspondence'],reason='Verified capsule poses 344/346 and drone poses 350/351/352; infer BC recoloring from user direction. Gallery palette remains separate.')
                result.append(row)
                continue
            if ident[0]==0x3694 and ident[1] in (0,8,16,24) and ident[2] in (7,15):
                row.update(decision='recolor',provenance='inferred',evidence=['docs/bc-art-review-decisions.md#shell-to-robot-correspondence'],reason='Verified shell-to-robot poses 2E0/2E2/2E4/2E6; infer BC recoloring from user direction. Gallery palette remains separate.')
                result.append(row)
                continue
            candidates=groups[(ident[0],ident[2])]
            choices={x['decision'] for x in candidates}
            poses={identity(x['id'])[1] for x in candidates}
            # Pickups share one bank across unrelated objects. Effect/flight
            # poses 3682 likewise cannot inherit from its one accepted image.
            if ident[0] in (0x367a,0x3682):
                candidates=[x for x in candidates if identity(x['id'])[1]==ident[1]]
                choices={x['decision'] for x in candidates};poses={ident[1]} if candidates else set()
                safe=bool(candidates)
            else:safe=len(poses)>=2
            if safe and len(choices)==1 and 'new' not in choices:
                row.update(decision=next(iter(choices)),provenance='inferred',evidence=[x['id'] for x in candidates],reason='Consistent reviewed poses in this family and source palette; no cross-palette or unrelated-item propagation.')
            else:row['reason']='Skipped or questionable match; no consistent same-family/pose evidence. Keep unresolved, not rejected.'
        result.append(row)
    return dict(schema=1,review='bc-art-review-v1',summary=dict(Counter(r['provenance'] for r in result)),explicit_counts=dict(Counter(d['decision'] for d in explicit.values())),decisions=result)

if __name__=='__main__':
    cards=json.loads((ROOT/'.local/bc-asset-review/review-manifest.json').read_text())
    export=json.loads((ROOT/'tools/data/bc_art_user_decisions.json').read_text())
    resolved=resolve(cards,export)
    (ROOT/'tools/data/bc_art_resolved_decisions.json').write_text(json.dumps(resolved,indent=2)+'\n')
    print(json.dumps({k:v for k,v in resolved.items() if k!='decisions'},indent=2))
