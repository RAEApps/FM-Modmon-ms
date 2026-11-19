"""The panel's plain readings (StationPanel.readings), the alarm states an
annunciator shows, and the per-receiver History, against synthetic stations."""
import importlib.util
import os
import sys
import types

os.environ['QT_QPA_PLATFORM'] = 'offscreen'
sys.stdout.reconfigure(encoding='utf-8')
spec = importlib.util.spec_from_file_location('fm_modmon', os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'fm-modmon-ms.py'))
rm = importlib.util.module_from_spec(spec)
spec.loader.exec_module(rm)
import numpy as np
import fmtx
from PyQt5 import QtWidgets

app = QtWidgets.QApplication([])
failed = []


def check(name, ok, detail=''):
    print(f'{"ok  " if ok else "FAIL"}  {name}' + (f'   ({detail})' if detail and not ok else ''))
    if not ok:
        failed.append(name)


# ---- History: ring order, the 1 s summary (peaks: max, others: mean), series spans
h = rm.History()
t0 = 1_000_000.0
for i in range(3500):                       # more than the fast ring holds (300 s at 10 Hz)
    h.add(t0 + i / rm.UPDATE_HZ, {'pos_pct': float(i % 10), 'rf_dbfs': float(i % 10), 'snr_db': None})
t, v = h.series('pos_pct')
check('fast ring keeps the last 300 s in time order', len(t) == 3000 and np.all(np.diff(t) > 0), f'{len(t)}')
check('fast ring ends at the newest sample', t[-1] == t0 + 3499 / rm.UPDATE_HZ and v[-1] == 9.0)
ts, vs = h.series('pos_pct', 3600)
_, rf = h.series('rf_dbfs', 3600)
_, snr = h.series('snr_db', 3600)
check('slow ring: one point per completed second', len(ts) == 349 and np.all(np.diff(ts) == 1.0), f'{len(ts)}')
check('slow ring: a peak reading keeps the second\'s maximum', np.all(vs == 9.0), f'{vs[:3]}')
check('slow ring: other readings keep the mean', np.allclose(rf, 4.5), f'{rf[:3]}')
check('a reading never given is NaN', np.all(np.isnan(snr)))
ts, _ = h.series('pos_pct', 60)
check('series() limits to the span asked', len(ts) == 601 and ts[-1] - ts[0] <= 60, f'{len(ts)}')
h.log_alarm(t0, 'RDS', True)
h.log_alarm(t0 + 90_000, 'RDS', False)
check('alarm log forgets changes older than 24 h', list(h.alarm_log) == [(t0 + 90_000, 'RDS', False)])
h.reset()
check('reset empties everything', len(h.series('pos_pct')[0]) == 0 and not h.alarm_log)

# ---- readings and alarm states through a real receiver
real_time = rm.time
clock = {'t': 1000.0}
fake = types.SimpleNamespace(monotonic=lambda: clock['t'], time=real_time.time, strftime=real_time.strftime,
                             sleep=real_time.sleep)


def panel(seconds=6.0, run=None, **mpx):
    x, _ = fmtx.mpx(rm, seconds, **mpx)
    st = fmtx.run(rm, x, **{'rf_amp': 0.1, 'noise': 0.0005, **(run or {})})
    p = rm.StationPanel(st, [(st.freq_hz, None)], lambda *a: None, lambda *a: None, country='CA')
    return p, st


def settle(p, n=40, rds_seen=False, changes=None, **settings):
    """Alarm states over n refreshes 1 s apart. rds_seen: the station had RDS
    before (the synthetic run is over, so there is none now)."""
    p.settings = rm.ReceiverSettings.from_dict(settings)
    rm.time = fake
    try:
        p.alarms.reset()
        p.alarms.seen_rds = rds_seen
        states = []
        for _ in range(n):
            clock['t'] += 1.0
            got = p.refresh()
            if changes is not None:
                changes += got
            states.append(dict(p.readings['alarms']))
    finally:
        rm.time = real_time
    return states


p, st = panel(left=[(997, 1.15)], right=[(997, 1.15)], pilot=0.09, rds=0.05)
states = settle(p, expected_pi='ABCD', alarms={'PI': False})
r, s, a = p.readings, st.meter.stats, st.audio_meter.stats
check('readings carry the meter values', r['rf_dbfs'] == s['rf_dbfs'] and r['pos_pct'] == s['pos_pct']
      and r['short_term'] == a['short_term'] and r['rds_pct'] == s['rds_pct'])
# (the synthetic run is over before these refreshes, so the RDS rate itself is 0 here)
# The panel is in Canada (ISED rules): RDS alone gets no subcarrier allowance (BPR-3 3.13.2), so 100%.
check('readings: stereo, RDS decoded and the limit', r['stereo_mode'] == 'stereo' and r['pi'] and r['group_types']
      and r['limit_pct'] == 100.0, f"{r['stereo_mode']} {r['pi']} limit {r['limit_pct']}")
check('levels: peak over the limit is an alarm', r['levels'].get('pos_pct') == 'alarm', r['levels'])
check('levels: L over 110% is an alarm', r['levels'].get('mod_l') == 'alarm', r['levels'])
check('flags decoded to booleans', r['flags'] is not None and set(r['flags']) == set(rm.RDS_FLAGS))
check('first refreshes: alarms waiting (grace period)', states[0]['OVERMOD'] == 'waiting', states[0]['OVERMOD'])
check('over-modulation: pending, then raised', 'pending' in [x['OVERMOD'] for x in states]
      and states[-1]['OVERMOD'] == 'raised', [x['OVERMOD'] for x in states][:12])
check('an alarm switched off shows off (PI differs, but PI is off)', states[-1]['PI'] == 'off')
check('alarms not met show clear', states[-1]['CARRIER'] == 'clear' and states[-1]['PILOT'] == 'clear')
check('history logs the raise', [(n, up) for _, n, up in p.history.alarm_log] == [('OVERMOD', True)],
      list(p.history.alarm_log))
check('history holds every refresh', len(p.history.series('pos_pct')[0]) == 40)

p, st = panel(left=[(997, 1.15)], right=[(997, 1.15)], pilot=0.09, run={'am': 0.25, 'seed': 3})
states = settle(p)
r = p.readings
check('heavy multipath: AM level is an alarm', r['levels'].get('am_pct') == 'alarm', f"{r['am_pct']:.1f}%")
check('heavy multipath: over-modulation not judged (suppressed)', states[-1]['OVERMOD'] == 'suppressed'
      and 'OVERMOD' not in p.alarms.active, states[-1]['OVERMOD'])
check('heavy multipath: other alarms still judged', states[-1]['CARRIER'] == 'clear')
check('no RDS: no PI, no flags, no loss figure', r['pi'] is None and r['flags'] is None and r['rds_loss_pct'] is None)

# ---- RDS gone while the carrier, pilot and audio stay fine: possibly on the AUX (auxiliary/backup) transmitter
p, st = panel(left=[(997, 0.42)], right=[(1600, 0.42)], pilot=0.09, rds=0.04)
changes = []
states = settle(p, rds_seen=True, changes=changes)
check('AUX: possibly-on-AUX pending, then raised', 'pending' in [x['BACKUP'] for x in states]
      and states[-1]['BACKUP'] == 'raised', [x['BACKUP'] for x in states][:16])
check('AUX: not shown as an RDS fault', states[-1]['RDS'] == 'clear', states[-1]['RDS'])
lamps = p.annunciator.states
check('AUX: the annunciator lights AUX, not RDS', lamps.get('BACKUP') == 'raised' and lamps.get('RDS') == 'clear'
      and rm.Annunciator.SHORT['BACKUP'] == 'AUX', lamps)
check('AUX: the event names the AUX transmitter and what is fine',
      [(d, up) for d, up, _ in changes] == [('possibly on the auxiliary/backup transmitter, without RDS (AUX)', True)]
      and 'auxiliary/backup transmitter, without RDS' in changes[0][2] and 'pilot' in changes[0][2], changes)
check('AUX: logged in the history', [(n, up) for _, n, up in p.history.alarm_log] == [('BACKUP', True)],
      list(p.history.alarm_log))
states = settle(p, rds_seen=True, alarms={'BACKUP': False})
check('AUX alarm off: off, and RDS lost raised instead', states[-1]['BACKUP'] == 'off'
      and states[-1]['RDS'] == 'raised', (states[-1]['BACKUP'], states[-1]['RDS']))
p, st = panel(pilot=0.09, rds=0.04)
states = settle(p, rds_seen=True)
check('silent programme: RDS lost, not AUX', states[-1]['RDS'] == 'raised' and states[-1]['BACKUP'] == 'clear',
      (states[-1]['RDS'], states[-1]['BACKUP']))

# ---- the large MPX spectrum window: opens on a click, follows the panel, holds peaks
p, st = panel(left=[(997, 0.4)], right=[(1600, 0.4)], pilot=0.09, rds=0.04)
settle(p, n=3)
p.mpx.on_click()
win = p._mpx_win
check('MPX window opens on the spectrum and shows the readings', win is not None and win.isVisible()
      and np.array_equal(win.spectrum._db, p.readings['mpx_db']) and 'RDS injection:' in win.readouts.text())
db = p.readings['mpx_db']
win.spectrum.set_data(db - 20)          # everything 20 dB lower: the hold falls slowly from the old trace
check('peak hold falls MPX_HOLD_DECAY_DB per update', np.allclose(win.spectrum._hold, db - rm.MPX_HOLD_DECAY_DB),
      float(np.max(np.abs(win.spectrum._hold - db))))
p.reset_display()
check('retuning clears the peak hold', win.spectrum._hold is None)
win.close()

# ---- IBOC lines from readings
ib = {'program': 0, 'service': 'MPS', 'synced': True, 'kbps': 48.0, 'mer_db': 7.5, 'ber': 2e-5, 'dropped': 0,
      'artist': 'A', 'title': 'B', 'album': '', 'genre': 'Rock', 'comment': '', 'name': 'TESTFM', 'slogan': '',
      'message': '', 'alert': ''}
line = rm.StationPanel._iboc_line_text(ib)
psd, sis = rm.StationPanel._psd_sis_text(ib)
check('IBOC line from readings', '(MPS)' in line and 'synchronized' in line and '48 kbps' in line
      and 'MER 7.5 dB' in line and 'BER 2.0e-05' in line, line)
check('PSD and SIS lines from readings', psd == 'A – B  ·  Rock' and sis == 'TESTFM', f'{psd!r} {sis!r}')
check('no IBOC: dashes', rm.StationPanel._iboc_line_text(None) == '-' and rm.StationPanel._psd_sis_text(None) == ('-', '-'))

# ---- the station's title (event log, notifications): never a frame of a scrolling PS
p, st = panel(pilot=0.09, rds=0.04)
snap = st.rds.snapshot


def ps_on_air(ps, dynamic, age=60.0):
    st.rds.snapshot = lambda: {**snap(), 'ps': ps, 'ps_dynamic': dynamic, 'ps_age': age}


ps_on_air('TESTFM  ', False)
check('static PS: the title names it', p.title == '101.0 TESTFM', p.title)
ps_on_air('LIKE:   ', True)
check('scrolling PS: no word of it in the title', p.title == '101.0', p.title)
p.settings = rm.ReceiverSettings.from_dict({'name': 'Hits FM'})
check("scrolling PS: the receiver's own name instead", p.title == '101.0 Hits FM', p.title)
ps_on_air('TES     ', False, age=1.0)
check('PS not yet held long enough: not used either', p.title == '101.0 Hits FM', p.title)
st.rds.snapshot = snap

print('\nall state checks passed' if not failed else f'\n{len(failed)} FAILED: {failed}')
sys.exit(1 if failed else 0)
