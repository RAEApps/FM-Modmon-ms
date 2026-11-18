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


def judge(st, rules, country='CA', keep=(), **settings):
    """Alarms a panel raises for this station after 60 s of the same readings
    (RDS, PILOT and SILENCE left out unless in keep)."""
    p = rm.StationPanel(st, [(st.freq_hz, None)], lambda *a: None, lambda *a: None, country=country)
    p.settings = rm.ReceiverSettings.from_dict({**CUSTOM.get(rules, {'rules': rules}), **settings})
    rm.time = fake
    try:
        p.alarms.reset()
        for _ in range(70):            # 70 s of refreshes, 1 s apart (grace 5 s, holds up to 30 s)
            clock['t'] += 1.0
            p._groups.clear()
            p.refresh()
    finally:
        rm.time = real_time
    s = st.meter.stats
    plain = QtGui.QTextDocumentFragment.fromHtml(p.values['Limit'].text()).toPlainText()
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
check('S/N ~44 dB under a 50 dB minimum', judge(station(rf_amp=0.0003, **music), '', min_snr_db=50)[0], ['CARRIER'])

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

print('\nall as expected' if not bad else f'\n{bad} unexpected')
sys.exit(1 if bad else 0)
