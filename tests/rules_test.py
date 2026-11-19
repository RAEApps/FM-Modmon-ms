"""FCC / ISED rule alarms against synthetic transmissions through the real receiver."""
import importlib.util
import os
import sys
import types

os.environ['QT_QPA_PLATFORM'] = 'offscreen'
sys.stdout.reconfigure(encoding='utf-8')  # readouts use − and µ; Windows consoles default to cp1252
spec = importlib.util.spec_from_file_location('fm_modmon', os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'fm-modmon-ms.py'))
rm = importlib.util.module_from_spec(spec)
spec.loader.exec_module(rm)
import numpy as np
import fmtx
from PyQt5 import QtGui, QtWidgets

app = QtWidgets.QApplication([])
CUSTOM = {'custom': {'rules': 'custom', 'mod_base_pct': 110, 'mod_per_sub': 0, 'mod_max_pct': 110},
          'custom-pilot': {'rules': 'custom', 'pilot_min_pct': 7, 'pilot_max_pct': 11}}
real_time = rm.time
clock = {'t': 1000.0}
fake = types.SimpleNamespace(monotonic=lambda: clock['t'], time=real_time.time, strftime=real_time.strftime,
                             sleep=real_time.sleep)


def judge(st, rules, country='CA', keep=(), rds_seen=False, **settings):
    """Alarms a panel raises for this station after 60 s of the same readings
    (RDS, PILOT and SILENCE left out unless in keep). rds_seen: the station had
    RDS before (the synthetic run is over, so there is none now)."""
    p = rm.StationPanel(st, [(st.freq_hz, None)], lambda *a: None, lambda *a: None, country=country)
    p.settings = rm.ReceiverSettings.from_dict({**CUSTOM.get(rules, {'rules': rules}), **settings})
    rm.time = fake
    try:
        p.alarms.reset()
        p.alarms.seen_rds = rds_seen
        for _ in range(70):            # 70 s of refreshes, 1 s apart (grace 5 s, holds up to 30 s)
            clock['t'] += 1.0
            p._groups.clear()
            p.refresh()
    finally:
        rm.time = real_time
    s = st.meter.stats
    plain = f"{QtGui.QTextDocumentFragment.fromHtml(p.values['Limit'].text()).toPlainText()} ({p.readings.get('limit_why')})"
    return sorted(p.alarms.active - ({'RDS', 'PILOT', 'SILENCE'} - set(keep))), s, p, plain


def station(seconds=6.0, rf_amp=0.1, echo=None, **kw):
    dc = kw.pop('dc_hz', 0.0)
    x, _ = fmtx.mpx(rm, seconds, dc_hz=dc, **kw)
    return fmtx.run(rm, x, rf_amp=rf_amp, noise=0.0003, echo=echo)


# Programme with treble (echoes inflate peaks most where the deviation changes fastest)
def bright(level):
    return dict(left=[(997, level), (12000, 0.05)], right=[(1600, level), (14000, 0.04)], pilot=0.09, rds=0.04)


cases = [
    ('compliant stereo, RDS 4%', dict(left=[(997, 0.42)], right=[(1600, 0.42)], pilot=0.09, rds=0.04),
     {'fcc': [], 'ised': [], 'custom': []}),
    ('peaks ~105% with RDS 4% (limit 102%)', dict(left=[(997, 0.86)], right=[(997, 0.86)], pilot=0.09, rds=0.04),
     {'fcc': ['OVERMOD'], 'ised': ['OVERMOD'], 'custom': []}),
    ('pilot 7%', dict(left=[(997, 0.4)], right=[(1600, 0.4)], pilot=0.07, rds=0.04),
     {'fcc': ['PILOT_SPEC'], 'ised': ['PILOT_SPEC'], 'custom-pilot': []}),
    ('pilot 19003 Hz', dict(left=[(997, 0.4)], right=[(1600, 0.4)], pilot=0.09, pilot_hz=19003.0),
     {'fcc': ['PILOT_SPEC'], 'ised': ['PILOT_SPEC']}),
    ('subcarriers: SCA67 12% + SCA92 11% + RDS 4%', dict(left=[(997, 0.35)], right=[(997, 0.35)], pilot=0.09, rds=0.04,
                                                          sca=[(67, 0.12, 1000, 6000), (92, 0.11, 700, 6000)]),
     {'fcc': ['SUBCARRIERS'], 'ised': ['SUBCARRIERS']}),
    # 73.319(d): 20% in stereo, 30% in mono (no pilot); 10% above 75 kHz either way.
    # BPR-3 3.13.2: 20% in stereo or mono while programme is on air
    ('subcarriers 25% in stereo', dict(left=[(997, 0.35)], right=[(997, 0.35)], pilot=0.09, rds=0.04,
                                       sca=[(67, 0.12, 1100, 6000), (92, 0.09, 700, 6000)]),
     {'fcc': ['SUBCARRIERS'], 'ised': ['SUBCARRIERS']}),
    ('subcarriers 25% in mono', dict(left=[(997, 0.35)], right=[(997, 0.35)], pilot=0.0, rds=0.04,
                                     sca=[(67, 0.12, 1100, 6000), (92, 0.09, 700, 6000)]),
     {'fcc': [], 'ised': ['SUBCARRIERS']}),
    ('carrier +1500 Hz', dict(left=[(997, 0.4)], right=[(1600, 0.4)], pilot=0.09, dc_hz=1500.0),
     {'fcc': [], 'ised': ['FREQUENCY']}),
]
bad = 0
for title, kw, expect in cases:
    st = station(**kw)
    s = st.meter.stats
    print(f'--- {title}: peaks +{s["pos_pct"]:.1f}/-{s["neg_pct"]:.1f}%, pilot {s["pilot_pct"]:.1f}% '
          f'{st.pilot_hz and round(st.pilot_hz, 1)} Hz, RDS {s["rds_pct"]:.1f}%, SCA67 {s["sca67_pct"]}, '
          f'SCA92 {s["sca92_pct"]}, offset {s["offset_hz"]:+.0f} Hz, AM {s["am_pct"]:.1f}% (10 s max {s["am_max_pct"]:.1f}%)')
    for rules, want in expect.items():
        got, _, limit, shown = judge(st, rules)
        ok = got == sorted(want)
        bad += not ok
        print(f'   {"ok   " if ok else "WRONG"} {rules:<7} alarms {str(got or "none"):<16} expected {str(want or "none"):<16} limit shown: {shown}')


def check(title, got, want):
    global bad
    ok = got == want
    bad += not ok
    print(f'   {"ok   " if ok else "WRONG"} {title}: {got!r}' + ('' if ok else f', expected {want!r}'))


print('--- station alarms')
music = dict(left=[(997, 0.42)], right=[(1600, 0.42)], pilot=0.09, rds=0.04)
st = station(**music)
check('PI as expected: no alarm', judge(st, '', expected_pi='C6B2')[0], [])
check('PI differs', judge(st, '', expected_pi='ABCD')[0], ['PI'])
check('PI differs, alarm switched off', judge(st, '', expected_pi='ABCD', alarms={'PI': False})[0], [])
check('silent programme', judge(station(pilot=0.09, rds=0.04), '', keep=('SILENCE',))[0], ['SILENCE'])
check('carrier below -75 dBFS', judge(station(rf_amp=0.0001, **music), '')[0], ['CARRIER'])
# Multipath: an echo 20 dB down and 10 us late reads ~10% AM and adds ~6% of false peak.
# Over-modulation is judged only under 5% AM (ITU-R SM.1268); the other rules under 15%.
st = station(**bright(0.44), echo=(10e-6, 0.1, 1.6))
s = st.meter.stats
check('echo: ~97% programme reads over the 102% limit', max(s['pos_pct'], s['neg_pct']) > 102, True)
check('echo: ...but over-modulation is not judged at ~10% AM', judge(st, 'fcc')[0], [])
check('echo: pilot rules still judged under 15% AM', judge(st, 'custom', pilot_min_pct=9.5)[0], ['PILOT_SPEC'])
st = station(**bright(0.52), echo=(2e-6, 0.1, 0.0))
check('weak echo (~1% AM): real over-modulation still raised', judge(st, 'fcc')[0], ['OVERMOD'])
# The limit is per station: 100% + 0.5 x (RDS + SCA injection), never above 110%
# (47 CFR 73.1570(b)(2), BETS-6 A.2.2.4.4)
st = station(left=[(997, 0.72)], right=[(997, 0.72)], pilot=0.09, rds=0.04, sca=[(67, 0.10, 1000, 6000)])
s = st.meter.stats
got, _, p, _ = judge(st, 'fcc')
check(f'limit with SCA 10% + RDS 4%: 107% (peak {max(s["pos_pct"], s["neg_pct"]):.1f}%)',
      round(p.readings['limit_pct'], 1), round(100 + 0.5 * (s['rds_pct'] + s['sca67_pct']), 1))
check('...a peak under it raises nothing', got, [])
check('...a flat 100% limit would have raised it', judge(st, 'custom', mod_base_pct=100, mod_per_sub=0)[0], ['OVERMOD'])
st = station(left=[(997, 0.35)], right=[(997, 0.35)], pilot=0.09, rds=0.04,
             sca=[(67, 0.12, 1000, 6000), (92, 0.11, 700, 6000)])
check('limit with 27% of subcarriers: capped at 110%', round(judge(st, 'fcc')[2].readings['limit_pct'], 1), 110.0)

# ITU-R SM.1268: over 1e-6 of 15 min of valid samples above the limit + 2 kHz. Judged once 15 min is held.
def held(st):
    """The station as if it had held EXCEED_MIN_S of valid time with the same statistics."""
    st.meter.stats = {**st.meter.stats, 'exceed_valid_s': float(rm.EXCEED_MIN_S)}
    return st


st = station(left=[(997, 0.86)], right=[(997, 0.86)], pilot=0.09, rds=0.04)
got, _, p, _ = judge(st, 'fcc')
check('SM.1268: 6 s held, not judged yet (waiting)', (got, p.readings['alarms']['EXCEEDANCE']),
      (['OVERMOD'], 'waiting'))
check('SM.1268: ~107% with RDS 4% (limit 102% + 2 kHz = 78.5 kHz), 15 min held',
      judge(held(st), 'fcc')[0], ['EXCEEDANCE', 'OVERMOD'])
st = held(station(left=[(997, 0.826)], right=[(997, 0.826)], pilot=0.09, rds=0.04))
check(f'SM.1268: ~{max(st.meter.stats["pos_pct"], st.meter.stats["neg_pct"]):.1f}%: over the limit, '
      'not over it + 2 kHz', judge(st, 'fcc')[0], ['OVERMOD'])
check('SM.1268: compliant programme, 15 min held', judge(held(station(**music)), 'fcc')[0], [])
# Another station's PI: peaks withheld (co-channel is caught by signature; AM depth under-reports it)
st = station(left=[(997, 0.86)], right=[(997, 0.86)], pilot=0.09, rds=0.04)
got, _, p, _ = judge(st, 'fcc', expected_pi='ABCD')
check('PI differs from expected: over-modulation withheld', (got, p.readings['alarms']['OVERMOD'],
                                                            p.readings['invalid_why']),
      (['PI'], 'suppressed', 'PI C6B2, not ABCD'))
rm.time = fake
try:
    p.settings = rm.ReceiverSettings()
    p._reset_identity()
    def seen(pi, seconds):
        for _ in range(seconds):
            clock['t'] += 1.0
            why = p._other_station(pi)
        return why
    check('no expected PI: none suspected before one is held 60 s', (seen('C6B2', 30), seen('1234', 1)), (None, None))
    seen('C6B2', 61)
    check('...then another PI is withheld for 60 s after it last shows',
          (seen('1234', 1), seen('C6B2', 59), seen('C6B2', 2), st.meter.interference),
          ('PI 1234, not C6B2', 'PI 1234, not C6B2', None, None))
finally:
    rm.time = real_time
check('S/N ~44 dB under a 50 dB minimum', judge(station(rf_amp=0.0003, **music), '', min_snr_db=50)[0], ['CARRIER'])

print('--- RDS gone: plain fault or an N+1 backup without RDS')
st = station(**music)
check('carrier, pilot and audio fine: possibly on N+1', judge(st, '', keep=('RDS',), rds_seen=True)[0], ['BACKUP'])
check('...with that alarm switched off: RDS lost', judge(st, '', keep=('RDS',), rds_seen=True,
                                                         alarms={'BACKUP': False})[0], ['RDS'])
check('RDS still there: neither', judge(st, '', keep=('RDS',))[0], [])
check('silent programme too: RDS lost, not N+1',
      judge(station(pilot=0.09, rds=0.04), '', keep=('RDS', 'SILENCE'), rds_seen=True)[0], ['RDS', 'SILENCE'])
check('carrier lost too: RDS lost, not N+1',
      judge(station(rf_amp=0.0001, **music), '', keep=('RDS',), rds_seen=True)[0], ['CARRIER', 'RDS'])
check('pilot lost too: RDS lost, not N+1', rm.rds_conditions(True, 0.0, False, False, False), (True, False))
check('mono station (never had a pilot): N+1', rm.rds_conditions(True, 0.0, False, True, False), (False, True))
check('RDS at 11.4 groups/s: neither', rm.rds_conditions(True, 11.4, False, True, False), (False, False))

print('--- wideband ADC overload')
from gnuradio import blocks, gr
x = np.full(rm.ADC_BATCH * 4, 0.1 + 0.1j, np.complex64)
x[rm.ADC_BATCH + 7] = 0.2 - 0.95j                                   # one sample near full scale, on Q
tb = gr.top_block()
meter = rm.AdcMeter()
tb.connect(blocks.vector_source_c(x.tolist(), False), rm._batch(gr.sizeof_gr_complex, rm.ADC_BATCH, 8), meter)
tb.run()
check('peak meter finds the largest |I| or |Q|', round(meter.take(), 3), 0.95)
check('...and starts again after take()', meter.take(), None)
ov = rm.AdcOverload()
seen = []
for t in range(80):
    peak = 0.97 if t in (10, 14, 16, 50, 57, 64) else None if t == 30 else 0.5
    if (got := ov.update(peak, now=float(t))) is not None:
        seen.append((t, got))
check('raised on the 3rd clipping second within 10 s, cleared 30 s after the last; lone peaks 7 s apart '
      'never raise', seen, [(16, True), (46, False)])
check('overload is where gain calibration counts overload', rm.CAL_CLIP <= 0.97, True)

print('--- a named data service (7A = Alert FM)')
DATA_STEADY_S = rm.DATA_STEADY_S
st = station(**music)
p = rm.StationPanel(st, [(st.freq_hz, None)], lambda *a: None, lambda *a: None, country='CA')
p.settings = rm.ReceiverSettings.from_dict({'service_names': '7A=Alert FM'})
rm.time, rm.DATA_STEADY_S = fake, 20.0
changes = []
try:
    p.alarms.reset()
    for second in range(130):
        clock['t'] += 1.0
        st.rds.groups += 11                                          # RDS itself stays fine throughout
        if second < 40:                                              # paging on air for 40 s: steady
            with st.rds._lock:
                st.rds._decode(0xC6B2, (14 << 11), 0x1234, 0x5678)
        changes += p.refresh()
        if second == 39:
            on_air = QtGui.QTextDocumentFragment.fromHtml(p.values['Data services'].text()).toPlainText()
finally:
    rm.time, rm.DATA_STEADY_S = real_time, DATA_STEADY_S
lost = QtGui.QTextDocumentFragment.fromHtml(p.values['Data services'].text()).toPlainText()
check('Data services row names it while on air', on_air.startswith('Alert FM Paging (7A)'), True)
check('...and names it once lost', lost, 'Alert FM Paging (7A) lost')
check('"data service lost" alarm names it', [(desc, raised, detail) for desc, raised, detail in changes],
      [('data service lost (paging, EWS, ODA or SCA data)', True,
        f'not on air for {rm.DATA_GAP_S:.0f}+ s: Alert FM (Paging (7A))')])

rm.time = fake
try:
    al = rm.StationAlarms()
    clock['t'] += rm.ALARM_GRACE_S
    def step(seconds, **on):
        out = []
        for _ in range(seconds):
            clock['t'] += 1.0
            out += al.update(on)
        return [(name, raised) for name, _, raised in out]
    check('raised once its hold has passed', step(6, CARRIER=True), [('CARRIER', True)])
    check('a dip shorter than the hold does not clear', step(3), [])
    check('cleared once the hold has passed again', step(1, CARRIER=True) + step(6), [('CARRIER', False)])
    check('emergency alert raised at once', step(1, ALERT=True), [('ALERT', True)])
    check('silence hold is the receiver setting', al.update({'SILENCE': True, 'ALERT': True}, holds={'SILENCE': 0}),
          [('SILENCE', 'audio silence', True)])
finally:
    rm.time = real_time

print('--- data services and RT+ Alarm (raw groups, no SDR)')
rm.time = fake
try:
    rs = rm.RdsState()
    rs._decode(0xC6B2, (0 << 11) | 0, 0, 0x4142)                    # 0A: programme, not data
    rs._decode(0xC6B2, (14 << 11), 0x1234, 0x5678)                  # 7A, nothing announced on it
    rs._decode(0xC6B2, (2 << 11) | 0x05, 0x03A1, 0)                 # 1A v0: paging codes 05, OPC 3, ECC A1
    rs._decode(0xC6B2, (2 << 11) | 0x05, 0x22B4, 0)                 # 1A v2: paging ID 2B4
    rs._decode(0xC6B2, (26 << 11), 0, 0)                            # 13A: enhanced paging
    rs._decode(0xC6B2, (6 << 11) | 22, 0, 0x4BD7)                   # 3A: RT+ on 11A
    rs._decode(0xC6B2, (6 << 11) | 18, 0, 0x1234)                   # 3A: ODA 1234 on 9A
    rs._decode(0xC6B2, (18 << 11), 0, 0)                            # 9A: that ODA, not EWS
    text = 'EVACUATE NOW'
    for seg in range(4):                                             # 2A: RadioText, then an RT+ Alarm tag
        chunk = (text + '\r').ljust(16)[seg * 4:seg * 4 + 4].encode('latin-1')
        rs._decode(0xC6B2, (4 << 11) | seg, (chunk[0] << 8) | chunk[1], (chunk[2] << 8) | chunk[3])
    n = len(text) - 1
    rs._decode(0xC6B2, (22 << 11) | (1 << 4) | (1 << 3) | (27 >> 3), ((27 & 7) << 13) | (n << 1), 0)
    snap = rs.snapshot()
    check('services seen', sorted(snap['data']), ['ODA 1234', 'Paging (13A)', 'Paging (7A)'])
    check('1A paging codes / OPC / paging ID / ECC', (snap['rp_codes'], snap['opc'], snap['paging_id'], snap['ecc']),
          (5, 3, 0x2B4, 0xA1))
    check('service names', rm.parse_service_names(' 7a = Alert FM; sca67=Muzak, bad, 9A='),
          {'7A': 'Alert FM', 'SCA67': 'Muzak'})
    check('saved names normalised', rm.ReceiverSettings.from_dict({'service_names': '7a=Alert FM;x'}).service_names,
          '7A=Alert FM')
    check('RT+ Alarm', snap['rtplus'], [(27, text)])
    bad_cfg = rm.ReceiverSettings.from_dict({'volume_pct': 'loud', 'silence_s': None, 'min_snr_db': 'x',
                                             'silence_lufs': float('nan'), 'rds_port': '7712', 'alarms': [1],
                                             'name': None})
    d = rm.ReceiverSettings()
    check('hand-edited config: bad values back to defaults',
          (bad_cfg.volume_pct, bad_cfg.silence_s, bad_cfg.min_snr_db, bad_cfg.silence_lufs, bad_cfg.rds_port,
           all(bad_cfg.alarms.values()), bad_cfg.name),
          (d.volume_pct, d.silence_s, d.min_snr_db, d.silence_lufs, 7712, True, ''))

    ds = rm.DataServices()
    for _ in range(int(rm.DATA_STEADY_S) + 1):                      # paging on air for 5 min: steady
        clock['t'] += 1.0
        lost = ds.update({'Paging (7A)': '7A', 'EWS (9A)': '9A'} if clock['t'] % 600 < 60 else
                         {'Paging (7A)': '7A'})                    # EWS only in a short burst
    check('nothing lost while on air', lost, [])
    clock['t'] += 1.0
    check('steady service gone', ds.update({}), ['Paging (7A)'])
    check('burst service never alarms', 'EWS (9A)' in ds.steady, False)
finally:
    rm.time = real_time

print('--- SM.1268: each sample against the limit when it was taken')
# Half the window with no subcarriers (limit 100%: threshold 77 kHz), half with SCA 20%
# (limit 110%: 84.5 kHz); 100 samples at 80 kHz in each half. Only the first half's are over.
fcc = rm.RULES['fcc']['limits']
h0, h20 = np.zeros(rm.EXCEED_BINS, np.int64), np.zeros(rm.EXCEED_BINS, np.int64)
k80 = round((80.0 - rm.EXCEED_LO_KHZ) / rm.EXCEED_BIN_KHZ)
h0[k80] = h20[k80] = 100
stats = {'exceed_n': 1_000_000, 'exceed_hist': h0 + h20, 'exceed_by_inj': {0.0: h0, 20.0: h20}}
check('80 kHz samples taken without SCA count; those with SCA 20% do not',
      rm.exceed_fraction(stats, lambda inj: rm.exceed_khz(rm.limit_at(fcc, inj))), 100 / 1_000_000)
check('...a single threshold (today\'s, SCA 20%) would miss them', rm.exceed_fraction(stats, rm.exceed_khz(rm.limit_at(fcc, 20.0))), 0.0)

print('--- ISED: the modulation allowance only "when more than one subcarrier is used" (BPR-3 3.13.2)')
ised = rm.RULES['ised']['limits']
check('FCC, RDS 4% alone: 102%', rm.mod_limit('fcc', fcc, {'rds_pct': 4.0})[0], 102.0)
check('ISED, RDS 4% alone: no allowance, 100%', rm.mod_limit('ised', ised, {'rds_pct': 4.0})[0], 100.0)
check('ISED, RDS 4% + SCA 67 10%: 107%', rm.mod_limit('ised', ised, {'rds_pct': 4.0, 'sca67_pct': 10.0})[0], 107.0)
check('ISED, no subcarriers: 100%', rm.mod_limit('ised', ised, {})[0], 100.0)
# Samples at 78 kHz: taken with RDS 4% alone they count under ISED (100%: threshold 77 kHz)
# but not FCC (102%: 78.5 kHz); with RDS 4% + SCA 10% (107%: 82.25 kHz) they never do.
k78 = round((78.0 - rm.EXCEED_LO_KHZ) / rm.EXCEED_BIN_KHZ)
h1, h2 = np.zeros(rm.EXCEED_BINS, np.int64), np.zeros(rm.EXCEED_BINS, np.int64)
h1[k78] = h2[k78] = 100
stats = {'exceed_n': 1_000_000, 'exceed_hist': h1 + h2, 'exceed_by_inj': {(4.0, 1): h1, (14.0, 2): h2}}
check('ISED over-deviation: each sample against its own subcarrier count',
      rm.exceed_fraction(stats, lambda inj, n=None: rm.exceed_khz(rm.limit_at(ised, inj, n))), 100 / 1_000_000)
check('...FCC gives both the allowance: none count',
      rm.exceed_fraction(stats, lambda inj, n=None: rm.exceed_khz(rm.limit_at(fcc, inj, n))), 0.0)

print('\nall as expected' if not bad else f'\n{bad} unexpected')
sys.exit(1 if bad else 0)
