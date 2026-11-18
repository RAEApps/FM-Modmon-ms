"""Check every FM-Modmon-ms readout against a synthetic transmitter with known values.
Usage: verify_meas.py [app path]"""
import importlib.util
import math
import os
import sys
from collections import Counter

os.environ['QT_QPA_PLATFORM'] = 'offscreen'
sys.stdout.reconfigure(encoding='utf-8')  # readouts use − and µ; Windows consoles default to cp1252
APP = sys.argv[1] if len(sys.argv) > 1 else os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'fm-modmon-ms.py')
spec = importlib.util.spec_from_file_location('fm_modmon', APP)
rm = importlib.util.module_from_spec(spec)
spec.loader.exec_module(rm)
import numpy as np
from scipy import signal as sps
from PyQt5 import QtGui, QtWidgets

import fmtx

app = QtWidgets.QApplication([])
rows = []


def plain(label):
    return QtGui.QTextDocumentFragment.fromHtml(label.text()).toPlainText()


def check(scn, name, expected, measured, tol=0, unit=""):
    if expected is None or measured is None:
        ok = expected == measured
    elif isinstance(expected, str):
        ok = expected == measured
    else:
        ok = abs(measured - expected) <= tol
    rows.append((scn, name, expected, measured, unit, 'ok' if ok else 'WRONG'))


def panel_for(st):
    p = rm.StationPanel(st, [(st.freq_hz, None)], lambda *a: None, lambda *a: None)
    p.refresh()
    return p


def k_gain(f):
    g = 1.0
    for b, a in rm.K_FILTERS:
        _, h = sps.freqz(b, a, worN=[f], fs=rm.AUDIO_RATE)
        g *= abs(h[0])
    return g


def lufs(tones_l, tones_r):
    p = sum((k_gain(f) * a) ** 2 / 2 for f, a in tones_l) + sum((k_gain(f) * a) ** 2 / 2 for f, a in tones_r)
    return -0.691 + 10 * math.log10(p)


TRIM = 100 * rm.OVERMOD_MIN_S * rm.UPDATE_HZ   # a peak: the level exceeded for 17 us per 100 ms


def mpx_truth(x):
    """The meter's own definitions, applied to the transmitted MPX."""
    tail = x[-int(fmtx.FS * 1.0):]  # the meter holds peaks for 1 s
    return {
        'pos': np.percentile(tail, 100 - TRIM) * 100, 'neg': -np.percentile(tail, TRIM) * 100,
        'dev': np.percentile(np.abs(tail), 100 - TRIM) * 75,
        'dbr': 10 * math.log10(np.mean(x * x) * 75e3 ** 2 / (19e3 ** 2 / 2)),
    }


def num(text):
    """First number in a readout ('-23.1 dBFS' -> -23.1)."""
    import re
    m = re.search(r'[-+]?\d+(\.\d+)?', text.replace('\u2212', '-'))
    return float(m.group()) if m else None


SECS = 12.0

# ================================================================ S1: stereo reference + full RDS
L1, R1 = [(997, 0.40)], [(1600, 0.30)]
x, info = fmtx.mpx(rm, SECS, left=L1, right=R1, pilot=0.09, rds=0.04, dc_hz=500)
st = fmtx.run(rm, x, rf_amp=0.1, noise=0.0005)
p = panel_for(st)
s, a, v = st.meter.stats, st.audio_meter.stats, p.values
t = mpx_truth(info['mpx_ac'])
S = 'S1 stereo+RDS'
check(S, 'RF level dBFS', -20.0, s['rf_dbfs'], 0.3, 'dBFS')
check(S, 'Carrier offset Hz', 500, s['offset_hz'], 5, 'Hz')
check(S, 'Pilot %', 9.0, s['pilot_pct'], 0.1, '%')
check(S, 'Pilot freq Hz', 19000.0, st.pilot_hz, 0.3, 'Hz')
check(S, 'Stereo decoded', 'True', str(st.stereo), 0)
check(S, 'RDS injection % (peak)', 4.0, s['rds_pct'], 0.1, '%')
check(S, 'SCA 67 (none)', None, s['sca67_pct'], 0)
check(S, 'SCA 92 (none)', None, s['sca92_pct'], 0)
check(S, 'Peak +%', t['pos'], s['pos_pct'], 1.0, '%')
check(S, 'Peak -%', t['neg'], s['neg_pct'], 1.0, '%')
check(S, 'Peak deviation kHz', t['dev'], s['peak_dev_khz'], 0.8, 'kHz')
check(S, 'MPX power dBr', t['dbr'], s['mpx_dbr'], 0.2, 'dBr')
check(S, 'Over 100% /min', 0, s['over100_min'], 0)
check(S, 'AM %', 0.0, s['am_pct'], 0.3, '%')
check(S, 'Valid time % (clean)', 100.0, s['valid_pct'], 0, '%')
check(S, 'Valid time (text)', f"100% of {s['valid_window_s']:.0f} s", plain(v['Valid time']))
check(S, 'Sync AM % (none)', 0.0, s['sync_am_pct'], 0.05, '%')
check(S, 'RDS phase deg (in phase)', 0.0, s['rds_phase_deg'], 2.0, 'deg')
check(S, 'RDS lock (steady)', 1.0, s['rds_lock'], 0.02)
check(S, 'RDS phase (text)', '+0° (in phase, locked)', plain(v['RDS phase']))
check(S, 'MPX spectrum @19k dB', 20 * math.log10(0.09), s['mpx_db'][37], 0.5, 'dB')
check(S, 'MPX spectrum @1k dB (L+R/2 tone)', None, None, 0)
txL, txR = info['L_tx'], info['R_tx']
check(S, 'Mod L %', np.max(np.abs(txL[-fmtx.FS:])) * 100, a['mod_l'], 1.0, '%')
check(S, 'Mod R %', np.max(np.abs(txR[-fmtx.FS:])) * 100, a['mod_r'], 1.0, '%')
check(S, 'Mod L+R %', np.max(np.abs((txL + txR)[-fmtx.FS:] / 2)) * 100, a['mod_m'], 1.0, '%')
check(S, 'Mod L-R %', np.max(np.abs((txL - txR)[-fmtx.FS:] / 2)) * 100, a['mod_s'], 1.0, '%')
lu = lufs(L1, R1)
check(S, 'Momentary LUFS', lu, a['momentary'], 0.2, 'LUFS')
check(S, 'Short-term LUFS', lu, a['short_term'], 0.2, 'LUFS')
check(S, 'Integrated LUFS', lu, a['integrated'], 0.2, 'LUFS')
check(S, 'True peak L dBTP', 20 * math.log10(0.40), a['tp_l'], 0.2, 'dBTP')
check(S, 'True peak R dBTP', 20 * math.log10(0.30), a['tp_r'], 0.2, 'dBTP')
check(S, 'RMS L dB', 20 * math.log10(0.40 / math.sqrt(2)), a['rms_l'], 0.2, 'dB')
check(S, 'RMS R dB', 20 * math.log10(0.30 / math.sqrt(2)), a['rms_r'], 0.2, 'dB')
check(S, 'Balance (text)', '2.5 dB L', plain(v['Balance']), 0)
check(S, 'Correlation (uncorrelated)', 0.0, a['correlation'], 0.1)
check(S, 'Width S/M dB', 0.0, a['width_db'], 0.3, 'dB')
# RDS
f = st.rds.fields
raw = st.rds.snapshot()
check(S, 'PI', 'C6B2', f.get(0, '').strip())
check(S, 'PS', 'TESTFM  ', raw['ps'])
check(S, 'PTY (RBDS 6)', 'Classic Rock', plain(v['PTY']))
check(S, 'Flags', 'TP TA Music DI-Stereo AH CMP', plain(v['Flags']))
check(S, 'Alt. freqs', None, None, 0)
rows[-1] = (S, 'Alt. freqs (shown)', '94.5, 101.7', plain(v['Alt. freqs']), '', '?')
check(S, 'Clock', None, None, 0)
rows[-1] = (S, 'Clock (shown)', '2026-11-16 07:34 local (UTC-5:00)', plain(v['Clock']), '', 'ok' if plain(v['Clock']) == '2026-11-16 07:34 local (UTC-5:00)' else 'WRONG')
check(S, 'RT', 'Now playing Bohemian Rhapsody by Queen', f.get(4, '').strip())
rtp = plain(p.rtplus)
check(S, 'RT+ title/artist', True, 'Title: Bohemian Rhapsody' in rtp and 'Artist: Queen' in rtp, 0)
rows[-1] = rows[-1][:3] + (rtp,) + rows[-1][4:]
check(S, 'PTYN', 'CLASSICS', plain(v['PTYN']))
check(S, 'ECC', 'A1', plain(v['ECC']))
check(S, 'ODA', 'RT+', plain(v['ODA']))
sent = Counter(info['rds_kinds'])
decoded = raw['types']
tot_s, tot_d = sum(sent.values()), sum(decoded.values())
for k in ('0A', '2A', '1A', '3A', '11A', '10A', '4A'):
    check(S, f'group share {k} %', sent[k] / tot_s * 100, decoded.get(k, 0) / max(tot_d, 1) * 100, 1.5, '%')
expected_groups = SECS * fmtx.RDS_RATE / 104
check(S, 'groups decoded (of ~sent)', expected_groups, st.rds.groups, expected_groups * 0.05, 'groups')
p1 = p

# ================================================================ S2: mono, over-modulation bursts
L2 = [(997, 0.80)]
bursts = [(2 + 0.7 * i, 3, 1.40) for i in range(6)] + [(7 + 0.7 * i, 3, 1.31) for i in range(4)]
x, info = fmtx.mpx(rm, SECS, left=L2, right=L2, pilot=0.0, stereo=False, bursts=bursts)
st = fmtx.run(rm, x, rf_amp=0.1, noise=0.0005)
p = panel_for(st)
s, a, v = st.meter.stats, st.audio_meter.stats, p.values
xa = info['mpx_ac']
peaks = [np.max(np.abs(xa[int(t0 * fmtx.FS):int((t0 + 0.003) * fmtx.FS)])) for t0, _, _ in bursts]
S = 'S2 mono+bursts'
check(S, 'burst peaks (truth, %)', None, None, 0)
rows[-1] = (S, 'burst peaks (truth)', ' '.join(f'{pk * 100:.0f}' for pk in peaks), '', '%', 'info')
check(S, 'Stereo decoded', 'False', str(st.stereo), 0)
check(S, 'Pilot % (none)', 0.0, s['pilot_pct'], 0.3, '%')
check(S, 'Over 100% /min', sum(pk > 1.0 for pk in peaks), s['over100_min'], 0)
check(S, 'Over 110% /min', sum(pk > 1.1 for pk in peaks), s['over110_min'], 0)
check(S, 'Correlation (L=R)', 1.0, a['correlation'], 0.02)
check(S, 'Width (text)', 'mono', plain(v['Width (S/M)']), 0)
check(S, 'Momentary LUFS', lufs(L2, L2), a['momentary'], 0.2, 'LUFS')
check(S, 'Balance (text)', 'centre', plain(v['Balance']), 0)
check(S, 'Mod L-R % (mono)', 0.0, a['mod_s'], 0.5, '%')

# ================================================================ S3: SCA, AM, noise -> S/N
L3 = [(997, 0.60)]
sca = [(67, 0.10, 1000, 6000), (92, 0.07, 700, 6000)]
noise = 0.004
x, info = fmtx.mpx(rm, SECS, left=L3, right=L3, pilot=0.09, sca=sca)
st = fmtx.run(rm, x, rf_amp=0.1, am=0.10, noise=noise, seed=7)
s = st.meter.stats
S = 'S3 SCA+AM+noise'
check(S, 'SCA 67 %', 10.0, s['sca67_pct'], 0.3, '%')
check(S, 'SCA 92 %', 7.0, s['sca92_pct'], 0.3, '%')
check(S, 'AM % (10% sine AM)', 10.0, s['am_pct'], 0.5, '%')
check(S, 'Valid time % (AM over 5%)', 0.0, s['valid_pct'], 0, '%')
check(S, 'Invalid because', 'multipath', s['invalid_why'])
check(S, 'Sync AM % (AM not tied to modulation)', 0.0, s['sync_am_pct'], 0.1, '%')
check(S, 'RDS phase shown (no RDS; SCA skirt in the band)', '-', plain(panel_for(st).values['RDS phase']))
snr_shown = s['snr_db']
# truth: same noise, no modulation; noise power in 0.05-15 kHz of the demodulated MPX, vs a 100% sine
x0, _ = fmtx.mpx(rm, SECS, pilot=0.0)
st0 = fmtx.run(rm, x0, rf_amp=0.1, noise=noise, seed=7)
fr, psd = st0.meter._freqs, st0.meter._psd
n15 = float(np.sum(psd[(fr >= 50) & (fr <= 15e3)]))
check(S, 'MPX S/N dB (unweighted 15 kHz)', 10 * math.log10(0.5 / n15), snr_shown, 1.0, 'dB')
de = np.abs(np.array([fmtx.deemph_response(rm, f) for f in fr[(fr >= 50) & (fr <= 15e3)]])) ** 2
n15d = float(np.sum(psd[(fr >= 50) & (fr <= 15e3)] * de))
rows.append((S, '  (S/N de-emphasised 75 us, for reference)', round(10 * math.log10(0.5 / n15d), 1), '', 'dB', 'info'))
check(S, 'S/N noise-only run (guard-band est.)', None, None, 0)
rows[-1] = (S, '  noise-only run, shown S/N', '', round(st0.meter.stats['snr_db'], 1), 'dB', 'info')

# ================================================================ S4: L only, pilot off-frequency, RDS 2 kHz
L4 = [(997, 0.80)]
x, info = fmtx.mpx(rm, SECS, left=L4, right=[], pilot=0.08, pilot_hz=19001.0, rds=2.0 / 75)
st = fmtx.run(rm, x, rf_amp=0.03, noise=0.0002, offset_hz=-2.4e6)
p = panel_for(st)
s, a = st.meter.stats, st.audio_meter.stats
S = 'S4 L-only'
check(S, 'RF level dBFS', 20 * math.log10(0.03), s['rf_dbfs'], 0.3, 'dBFS')
check(S, 'Pilot %', 8.0, s['pilot_pct'], 0.1, '%')
check(S, 'Pilot freq Hz', 19001.0, st.pilot_hz, 0.3, 'Hz')
check(S, 'RDS injection % (2 kHz)', 2.0 / 75 * 100, s['rds_pct'], 0.15, '%')
check(S, 'True peak L dBTP', 20 * math.log10(0.80), a['tp_l'], 0.2, 'dBTP')
rows.append((S, 'Separation (R below L)', '>40 dB', a['rms_r'] - a['rms_l'], 'dB', 'ok' if a['rms_r'] - a['rms_l'] < -40 else 'WRONG'))
rows.append((S, 'Correlation (L only; R is crosstalk)', '~+1', a['correlation'], '', 'info'))
check(S, 'Balance shown', None, None, 0)
rows[-1] = (S, 'Balance shown', '>30 dB L', plain(p.values['Balance']), '', 'info')

# ================================================================ S5: RDS in quadrature, synchronous AM
L5, R5 = [(997, 0.50), (240, 0.30)], [(1600, 0.40), (5000, 0.10)]
sync = (0.015, 0.03)  # envelope 1 + a*x + b*(x^2 - mean): a sloped and a narrow RF chain
x, info = fmtx.mpx(rm, SECS, left=L5, right=R5, pilot=0.09, rds=0.045, rds_phase_deg=90)
st = fmtx.run(rm, x, rf_amp=0.1, noise=0.0005, sync_am=sync)
p = panel_for(st)
s, v = st.meter.stats, p.values
S = 'S5 quad+syncAM'
fit = sync[0] * np.linspace(-1, 1, 201) + sync[1] * np.linspace(-1, 1, 201) ** 2
check(S, 'Sync AM % (depth at +/-75 kHz)', (fit.max() - fit.min()) / 2 * 100, s['sync_am_pct'], 0.1, '%')
check(S, 'Sync AM shown (amber > -35 dB)', True, '#' in v['Sync AM'].text(), 0)
rows[-1] = rows[-1][:3] + (plain(v['Sync AM']),) + rows[-1][4:]
check(S, 'RDS phase deg (quadrature)', 90.0, abs(s['rds_phase_deg']), 2.0, 'deg')
check(S, 'RDS lock (steady)', 1.0, s['rds_lock'], 0.02)

# ================================================================ S6: RDS encoder free-running (not locked to the pilot)
x, info = fmtx.mpx(rm, SECS, left=L5, right=R5, pilot=0.09, rds=0.045, rds_hz=57000.7)
st = fmtx.run(rm, x, rf_amp=0.1, noise=0.0005)
p = panel_for(st)
s, v = st.meter.stats, p.values
S = 'S6 RDS unlocked'
check(S, 'RDS lock (drifting)', True, s['rds_lock'] < rm.RDS_LOCKED, 0)
rows[-1] = rows[-1][:3] + (round(s['rds_lock'], 2),) + rows[-1][4:]
check(S, 'RDS phase (text)', 'drifting: not locked to the pilot', plain(v['RDS phase']))

# ================================================================ S7: two-ray multipath, clean transmitter
x, info = fmtx.mpx(rm, SECS, left=L5, right=R5, pilot=0.09, rds=0.045)
st = fmtx.run(rm, x, rf_amp=0.1, noise=0.0005, echo=(3e-6, 0.3, 0.7))
p = panel_for(st)
s, v = st.meter.stats, p.values
S = 'S7 multipath'
check(S, 'RDS phase deg (echo leaves it)', 0.0, s['rds_phase_deg'], 3.0, 'deg')
# a short echo gives AM tied to the modulation, just as a mistuned transmitter does
check(S, 'Sync AM shown as multipath', True, plain(v['Sync AM']).endswith('multipath'), 0)
rows[-1] = rows[-1][:3] + (plain(v['Sync AM']),) + rows[-1][4:]

# ================================================================ S8: programme in the 16-18.3 kHz guard band
# (clipper products, encoder LPF skirt) must not hide RDS; and no RDS reads 0
S = 'S8 guard band'
# (and the last: weak unlocked RDS in heavy noise, as on a distant mono station: measured though undecodable)
for rds_inj, unlocked, noise in ((0.05, 0.0, 0.0005), (0.02, 5.0, 0.0005), (0.0, 0.0, 0.0005), (0.0, 0.0, 0.006),
                                 (0.02, 1.4, 0.006)):
    x, info = fmtx.mpx(rm, SECS, left=[(997, 0.5)], right=[(1500, 0.3)], pilot=0.09)
    t = np.arange(len(x)) / fmtx.FS
    x = x + (0.012 * (np.sin(2 * np.pi * 16.7e3 * t) + np.sin(2 * np.pi * 17.6e3 * t))).astype(np.float32)
    if rds_inj:   # unlocked: the RDS carrier a few Hz off 3 x pilot
        bb, _ = fmtx.rds_baseband(fmtx.RdsContent(), SECS)
        x = x + (rds_inj * bb[:len(x)] * np.sin(2 * np.pi * (57e3 + unlocked) * t)).astype(np.float32)
    st = fmtx.run(rm, x, rf_amp=0.1, noise=noise)
    what = (f'{rds_inj * 100:.0f}%' + (f', carrier +{unlocked:g} Hz' if unlocked else '') if rds_inj else 'none')         + (', noisy' if noise > 0.001 else '')
    check(S, f'RDS injection % ({what})', rds_inj * 100, st.meter.stats['rds_pct'], 0.15, '%')
    if noise > 0.001 and rds_inj:
        rows.append((S, '  groups decoded there', '', st.rds.groups, '', 'info'))

# ================================================================ S9: peaks of treble and of short peaks
S = 'S9 peaks'


def block_peaks(xa):
    """The meter's peak rule per 100 ms block, held for the last 1 s."""
    n = int(fmtx.FS / rm.UPDATE_HZ)
    b = xa[-fmtx.FS:].reshape(-1, n)
    return (np.max(np.percentile(b, 100 - TRIM, axis=1)) * 100, -np.min(np.percentile(b, TRIM, axis=1)) * 100)


# L-R only (34 and 42 kHz), where the demodulator's output is down by sinc(f/fs): 1.6%
x, info = fmtx.mpx(rm, 6.0, left=[(4000, 0.3)], right=[(4000, -0.3)], pilot=0.09, rds=0.04)
st = fmtx.run(rm, x, rf_amp=0.1, noise=0.0005)
pos, neg = block_peaks(info['mpx_ac'])
check(S, 'Peak +% (L-R only)', pos, st.meter.stats['pos_pct'], 0.4, '%')
check(S, 'Peak -% (L-R only)', neg, st.meter.stats['neg_pct'], 0.4, '%')
# a 20 us flat-topped peak to 104% every 100 ms: over 17 us, so a real peak, read in full
t = np.arange(int(6.0 * fmtx.FS)) / fmtx.FS
d = np.abs((t - 0.05025 + 0.05) % 0.1 - 0.05)   # from each pulse's centre (on the tone's crest)
edge = np.clip((d - 10e-6) / 15e-6, 0, 1)
x = (0.8 * np.sin(2 * np.pi * 1000 * t) + 0.24 * np.where(d < 25e-6, 0.5 + 0.5 * np.cos(np.pi * edge), 0)).astype(np.float32)
st = fmtx.run(rm, x, rf_amp=0.1, noise=0.0005)
check(S, 'Peak +% (20 us peaks to 104%)', block_peaks(x)[0], st.meter.stats['pos_pct'], 0.6, '%')

# ================================================================ S10: validity gates the counts, not the meter
S = 'S10 validity'
x, info = fmtx.mpx(rm, SECS, left=L2, right=L2, pilot=0.0, stereo=False, bursts=bursts)
st = fmtx.run(rm, x, rf_amp=0.1, noise=0.0005, am=0.10)
s = st.meter.stats
check(S, 'Over 100% /min (bursts, but 10% AM: invalid)', 0, s['over100_min'], 0)
check(S, 'Valid peak (none valid)', None, s['valid_pos_pct'], 0)
check(S, 'Peak +% still shown live (programme)', mpx_truth(info['mpx_ac'])['pos'], s['pos_pct'], 0.5, '%')
# an RF level step (gain step, aircraft, fade): invalid at once, and for VALID_HOLD_S after it settles
m = rm.FmMeter()
n = int(rm.QUAD_RATE / rm.UPDATE_HZ)
tone = (0.5 * np.sin(2 * np.pi * 1000 * np.arange(n) / rm.QUAD_RATE)).astype(np.float32)
whys = []
for i in range(120):
    power = 0.01 if i < 40 else 0.04       # +6 dB at 4 s
    out = m._measure(tone, power, math.sqrt(power), np.full(n, math.sqrt(power), np.float32), tone)
    whys.append(out['invalid_why'])
check(S, 'valid before the step', None, whys[39])
check(S, 'RF step of 6 dB: invalid at once', 'level step', whys[40])
back = next(i for i in range(41, 120) if whys[i] is None)
check(S, 'valid again within 5 s', True, back < 90, 0)
rows[-1] = rows[-1][:3] + (f'{(back - 40) / rm.UPDATE_HZ:.1f} s',) + rows[-1][4:]

# ================================================================ report
w = max(len(r[1]) for r in rows)
for scn, name, exp, got, unit, verdict in rows:
    fe = f'{exp:.2f}' if isinstance(exp, float) else str(exp)
    fg = f'{got:.2f}' if isinstance(got, float) else str(got)
    print(f'{verdict:<5} {scn:<16} {name:<{w}}  expected {fe:<14} shown {fg:<14} {unit}')
print('\nS1 panel, as displayed:')
for k, lab in p1.values.items():
    print(f'   {k:<16} {plain(lab)}')

sys.exit(1 if any(r[5] == 'WRONG' for r in rows) else 0)
