#!/usr/bin/env python3
"""Render aligned R7 source/linked-ROM comparisons, without archived captures."""
import hashlib
import json
import shutil
import struct

import numpy as np
from PIL import Image, ImageDraw

from arcade_source import ROOT
from bc_background_equivalence import symbols, rendered_cell
from inspect_bc_background import cell_index, source_cell


def main():
    out = ROOT / '.local/bc-r7-materials'
    out.mkdir(parents=True, exist_ok=True)
    rom = (ROOT / 'out/release/rom.bin').read_bytes()
    digest = hashlib.sha256(rom).hexdigest()
    sy = symbols(ROOT / 'out/release/symbol.txt')
    code = rom[sy['bc_round7_code']:sy['bc_round7_code'] + 65536]
    cap = ROOT / '.local/pce-reference/round07-reference'
    definition = json.loads((ROOT / 'tools/data/bc_background_r7_materials.json').read_text())
    assert hashlib.sha256(code).hexdigest() == definition['source_code_sha256']
    for suffix in ('vram', 'palette'):
        assert hashlib.sha256((cap / f'f002400-{suffix}.bin').read_bytes()).hexdigest() == definition[f'source_{suffix}_sha256']
    vram = np.fromfile(cap / 'f002400-vram.bin', '<u2')
    words = np.fromfile(cap / 'f002400-palette.bin', '<u2')
    colors = np.array([((int(w) >> 3 & 7) * 36, (int(w) >> 6 & 7) * 36,
                       (int(w) & 7) * 36) for w in words], np.uint8)
    pal = struct.unpack_from('>32H', rom, sy['bc_bg7_palette'])
    remap = struct.unpack_from('>256H', rom, sy['bc_bg7_remap'])
    vivid = struct.unpack_from('>512H', rom, sy['vivid_lut'])
    cells = [{}, {}, {}]
    for c, entry in enumerate(remap):
        if entry == 4095:
            continue
        cells[0][c] = Image.fromarray(source_cell(code, vram, colors, c))
        pixels = rendered_cell(rom, sy, 'bc_bg7', entry)
        for mode in (1, 2):
            rgb = []
            for px in pixels:
                w = pal[(px[1] >> 13 & 1) * 16 + px[0]] if px and px[0] else 0
                if mode == 2:
                    w = vivid[(w >> 1 & 7) | (w >> 5 & 7) << 3 | (w >> 9 & 7) << 6]
                rgb.append(((w >> 1 & 7) * 36, (w >> 5 & 7) * 36, (w >> 9 & 7) * 36))
            im = Image.new('RGB', (32, 32))
            im.putdata(rgb)
            cells[mode][c] = im
    cameras = [(535, 1536), (934, 1536), (1412, 1536), (1890, 1536),
               (2368, 1536), (2784, 1536)]
    sections, checks = [], []
    native_dir = ROOT / '.local/bc-background-draft7'
    native_result = native_dir / 'result.json'
    native = json.loads(native_result.read_text()) if native_result.exists() else {}
    for i, (cx, cy) in enumerate(cameras):
        images = []
        wx, wy = cx // 32 * 32, cy // 32 * 32
        for atlas in cells:
            im = Image.new('RGB', (384, 288))
            for y in range(9):
                for x in range(12):
                    cell = code[0xc000 + cell_index(wx + x * 32, wy + y * 32)]
                    im.paste(atlas[cell], (x * 32, y * 32))
            images.append(im.crop((cx-wx, cy-wy, cx-wx+320, cy-wy+224)))
        images[0].save(out / f'pce-{i}.png')
        for mode, name in ((1, 'standard'), (2, 'vivid')):
            images[mode].save(out / f'linked-{i}-{name}.png')
            pair = Image.new('RGB', (1280, 480), '#182030')
            draw = ImageDraw.Draw(pair)
            for j, (im, label) in enumerate(((images[0], 'PCE source'),
                                            (images[mode], f'Genesis {name}'))):
                draw.text((j*640+8, 8), label, fill='white')
                pair.paste(im.resize((640, 448), Image.Resampling.NEAREST), (j*640, 32))
            pair.save(out / f'pair-{i}-{name}-{digest[:12]}.png')
        count = int(np.any(np.array(images[0]) != np.array(images[1]), axis=2).sum())
        assert count == 0, (i, 'Standard background differs from PCE source', count)
        checks.append(dict(camera=[cx, cy], standard_different_pixels=count))
        native_html = ''
        capture = native_dir / f'camera-{cx}-{cy}.png'
        if native.get('rom_sha256') == digest and str(capture) in native.get('captures', []) and capture.exists():
            filename = f'native-{i}-{digest[:12]}.png'
            shutil.copyfile(capture, out / filename)
            native_html = f'<h3>Emulator rendering</h3><p>Current ROM, debug camera preview; includes preview sprites. This is not a gameplay-performance test.</p><img style="width:640px" src="{filename}" alt="Round 7 emulator capture">'
        sections.append(f'<section><h2>View {i+1} · camera {cx}, {cy}</h2>'
                        f'<p>Standard differs from the decoded source at {count:,} pixels.</p>'
                        f'<div class="pair"><figure><figcaption>PCE source</figcaption><img src="pce-{i}.png?v={digest[:12]}" alt="PCE source view {i+1}"></figure><figure><figcaption>Genesis Standard</figcaption><img src="linked-{i}-standard.png?v={digest[:12]}" alt="Genesis Standard view {i+1}"></figure></div>'
                        f'<details><summary>Vivid comparison (brightness adjustment)</summary><div class="pair"><figure><figcaption>PCE source</figcaption><img src="pce-{i}.png?v={digest[:12]}" alt="PCE source view {i+1}"></figure><figure><figcaption>Genesis Vivid</figcaption><img src="linked-{i}-vivid.png?v={digest[:12]}" alt="Genesis Vivid view {i+1}"></figure></div></details>{native_html}</section>')
    (out / 'screen-audit.json').write_text(json.dumps(dict(rom_sha256=digest, views=checks), indent=2)+'\n')
    live_sections = []
    for mode in ('standard', 'vivid'):
        folder = ROOT / '.local/bc-r7-live-palette' / mode
        result_path = folder / 'result.json'
        if not result_path.exists():
            continue
        report = json.loads(result_path.read_text())
        audit = report.get('background_audit', {})
        palette = audit.get('palette', {})
        if (report.get('rom_sha256') != digest or not audit.get('passed')
                or not palette or not report.get('replay_verified')
                or report.get('color_mode_fixture') != mode):
            continue
        filename = f'live-palette-{mode}-{digest[:12]}.png'
        shutil.copyfile(folder / 'frame.png', out / filename)
        live_sections.append(f'<section><h2>Gameplay palette check · {mode.title()}</h2>'
                             f'<p>{palette["checked_cram_words"]:,} background color entries checked after uploads '
                             f'across {audit["samples"]:,} sampled updates. All match the linked palette and selected color mode. '
                             'The independent run without the observer reaches exactly the same final RAM state. '
                             'This is a protected four-player fixture; it excludes sprite colors, fades, raster effects and full-speed certification.</p>'
                             f'<img src="{filename}" alt="Round 7 gameplay with {mode} colors"></section>')
    campaign_folder = ROOT / '.local/bc-r7-live-background/campaign4'
    campaign_result = campaign_folder / 'result.json'
    if campaign_result.exists():
        campaign = json.loads(campaign_result.read_text())
        audit = campaign.get('live_background_audit', {})
        if campaign.get('rom_sha256') == digest and audit.get('passed'):
            gallery = []
            for i, capture_path in enumerate(audit['captures']):
                capture = campaign_folder/'background-audit'/f'gameplay-{i:02d}.png'
                assert capture.resolve() == ROOT.joinpath(capture_path).resolve()
                filename = f'campaign-{i}-{digest[:12]}.png'
                shutil.copyfile(capture, out/filename)
                gallery.append(f'<figure><figcaption>Gameplay capture {i+1}</figcaption><img style="width:640px" src="{filename}" alt="Round 7 four-player campaign capture {i+1}"></figure>')
            cameras = audit['cameras']
            live_sections.append('<section><h2>Round 7 during the four-player campaign</h2>'
                                 '<p>Actual gameplay using the unchanged default color setting, HuCard music and the campaign controller. '
                                 f'Every observed simulation update in this round was checked after video uploads: {audit["samples"]:,} samples, '
                                 f'{audit["visible_tile_checks"]:,} visible tile checks, camera range {cameras[0]} to {cameras[-1]}. '
                                 'The observer checks background mapping, nametable and pattern bytes; it does not certify palette fades, raster timing or gameplay speed.</p>'
                                 +''.join(gallery)+'</section>')
    for name, label in (('opening', 'Opening gameplay'), ('route', 'Later gameplay')):
        folder = ROOT / '.local/bc-r7-live-background' / name
        result_path = folder / 'result.json'
        if not result_path.exists():
            continue
        report = json.loads(result_path.read_text())
        audit = report.get('background_audit', {})
        if report.get('rom_sha256') != digest or not audit.get('passed') or not (folder/'frame.png').exists():
            continue
        filename = f'gameplay-{name}-{digest[:12]}.png'
        shutil.copyfile(folder/'frame.png', out/filename)
        cameras = audit['cameras']
        live_sections.append(f'<section><h2>{label}</h2><p>Four-player HuCard fixture, sampled during active gameplay after video uploads. '
                             f'{audit["visible_tile_checks"]:,} visible tile checks and {audit["resident_pattern_checks"]:,} resident-pattern checks passed '
                             f'at {audit["samples"]:,} sampled updates, from camera {cameras[0]} to {cameras[-1]}. '
                             'Checks cover tile placement and pattern bytes; they do not certify palette fades, every intervening frame or gameplay speed. '
                             'The fixture uses damage protection; terrain can still crush players.</p>'
                             f'<img style="width:640px" src="{filename}" alt="Round 7 live gameplay capture"></section>')
    (out / 'index.html').write_text('''<!doctype html><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1"><title>Round 7 · current ROM comparison</title>
<style>body{background:#111827;color:#eef2ff;font:16px system-ui;margin:24px}p{max-width:1000px;line-height:1.6}section{margin:36px 0}.pair{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:16px;max-width:1296px}figure{margin:0}figcaption{margin:8px 0}img{width:640px;max-width:100%;height:auto;image-rendering:pixelated}.pair img{width:100%}@media(max-width:680px){.pair{grid-template-columns:1fr}}summary{cursor:pointer;margin:16px 0}code{overflow-wrap:anywhere}</style>
<h1>Round 7 · current ROM comparison</h1>
<p>Left: decoded PCE background. Right: artwork read from the current Genesis ROM. Both show the same 320×224 region. Each pair fits the available width; on narrow screens PCE appears above Genesis. These are background reconstructions, not gameplay screenshots.</p>
<p>The mismatched Normal floor panels have been replaced with the original BC green floor. Walls, machinery and lava retain the previous source imports. The hanging assembly now also retains every source shade. Standard pixel differences below are checked explicitly. Vivid intentionally changes brightness.</p>
<p>Archived before-repair images are excluded from this current-build comparison.</p><p>ROM: <code>'''+digest+'</code></p>'+''.join(sections)+''.join(live_sections))
    print(json.dumps(checks, indent=2))


if __name__ == '__main__':
    main()
