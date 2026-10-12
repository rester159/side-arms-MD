#!/usr/bin/env python3
"""Check nonlinear patch spectra and envelope scaling against source waveforms.

This measures spectral magnitudes, not phase fidelity or subjective sound quality.
The independent cartridge output/register checks exercise production delivery.
"""
import hashlib
import json
import math
import numpy as np
from build_hucard_fm import patches, FM_OVERRIDES
from hucard_fm_probe import PatchProbe
from inspect_hucard_music import ROOT, metadata

rom = (ROOT / '.local/pce-hucard/SideArms - Hyper Dyne (USA).pce').read_bytes()
rows, details = patches(rom)
sources = metadata(rom)['instruments']
probe = PatchProbe()
# Calibrate the emulator's carrier amplitude at the existing TL=16 headroom.
unit = np.std(probe.render([1, 1, 1, 1], [16, 127, 127, 127])) * math.sqrt(2)
results = []

def spectrum(samples):
    v = np.abs(np.fft.rfft(samples))[24 * np.arange(1, 65)]
    return v / np.linalg.norm(v)

for number in sorted(FM_OVERRIDES):
    wave = np.array(sources[number - 1]['wave'], float)
    source_rms = np.std(wave)
    amplitudes = np.abs(np.fft.rfft(wave - wave.mean())) / 16
    target = np.zeros(64)
    target[:15] = amplitudes[1:16]
    target[15] = amplitudes[16] / math.sqrt(2)
    target /= np.linalg.norm(target)
    # Original four strongest representable harmonics, normalized to source power.
    harmonics = sorted(range(1, 16), key=lambda k: -amplitudes[k])[:4]
    gain = source_rms / np.sqrt(sum(amplitudes[k]**2 for k in harmonics) / 2)
    old_levels = [min(127, max(0, round(-20 * math.log10(amplitudes[k] * gain / 16) / .75) + 16)) for k in harmonics]
    old = probe.render(harmonics, old_levels)
    baseline_error = float(np.sum((spectrum(old) - target)**2))
    patch = rows[number - 1]
    control = details[number - 1]['algorithm']
    assert control & 7 in (5, 6)
    windows = []
    for attenuation in (0, 8, 24, 48):
        samples = probe.render(patch[:4], patch[4:], control, attenuation)
        expected_rms = source_rms / 16 * unit * 10**(-attenuation * .75 / 20)
        error_db = 20 * math.log10(np.std(samples) / expected_rms)
        spectral_error = float(np.sum((spectrum(samples) - target)**2))
        power = np.abs(np.fft.rfft(samples - samples.mean())) ** 2
        harmonic_bins = 24 * np.arange(1, (len(power) - 1) // 24 + 1)
        harmonic_fraction = float(power[harmonic_bins].sum() / power.sum())
        # A feedback patch must not appear accurate merely because the
        # normalized comparison ignores noise between the harmonic bins.
        assert harmonic_fraction > .995, (number, attenuation, harmonic_fraction)
        assert abs(error_db) < .6, (number, attenuation, error_db)
        assert spectral_error < baseline_error * .3, (number, attenuation, spectral_error)
        assert np.max(np.abs(samples)) < 8191, (number, 'channel clipping')
        windows.append(dict(attenuation=attenuation,level_error_db=error_db,
                            spectral_error=spectral_error,harmonic_energy_fraction=harmonic_fraction,
                            peak=float(np.max(np.abs(samples)))))
    results.append(dict(instrument=number,algorithm_b0=control,
                        baseline_spectral_error=baseline_error,windows=windows))
report = dict(passed=True,instruments=results,
              metric='Squared distance of unit-normalized harmonic magnitudes (1..64)',
              phase_fidelity_verified=False,subjective_audition_complete=False,
              source_sha256=hashlib.sha256(rom).hexdigest(),
              chip_core_sha256=hashlib.sha256(open(probe.lib._name,'rb').read()).hexdigest())
(ROOT / '.local/pce-hucard/fm-timbre-qa.json').write_text(json.dumps(report,indent=2)+'\n')
print(json.dumps(report,indent=2))
