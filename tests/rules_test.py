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


def judge(st, rules, country='CA'):
    """Alarms a panel raises for this station after 60 s of the same readings."""
    p = rm.StationPanel(st, [(st.freq_hz, None)], lambda *a: None, lambda *a: None, country=country)
    p.settings = rm.ReceiverSettings.from_dict(CUSTOM.get(rules, {'rules': rules}))
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
    return sorted(p.alarms.active - {'RDS', 'PILOT', 'SILENCE'}), s, None, plain


def station(seconds=6.0, **kw):
    dc = kw.pop('dc_hz', 0.0)
    x, _ = fmtx.mpx(rm, seconds, dc_hz=dc, **kw)
    return fmtx.run(rm, x, rf_amp=0.1, noise=0.0003)


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
          f'SCA92 {s["sca92_pct"]}, offset {s["offset_hz"]:+.0f} Hz')
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
