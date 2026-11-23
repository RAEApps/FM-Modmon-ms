"""The panel's plain readings (StationPanel.readings), the alarm states an
annunciator shows, and the per-receiver History, against synthetic stations."""
import os
import sys
import types

os.environ['QT_QPA_PLATFORM'] = 'offscreen'
sys.stdout.reconfigure(encoding='utf-8')
from loadapp import load_app  # noqa: E402
rm = load_app()
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
      [(d, up) for _, d, up, _ in changes] == [('possibly on the auxiliary/backup transmitter, without RDS (AUX)', True)]
      and 'auxiliary/backup transmitter, without RDS' in changes[0][3] and 'pilot' in changes[0][3], changes)
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

# ---- the audio sources a station doesn't carry: greyed, still selectable (as SCA, IBOC)
def sources(p):
    return {s['value']: s for s in p.web_state(None, None, 0)['sources']}


p, st = panel(left=[(997, 0.8)], right=[(997, 0.8)], pilot=0.09, rds=0.04)
settle(p, n=12)                    # long enough to find there is no SCA
p.slot = 0
p.iboc_scan = {st.freq_hz: None}   # the start-up scan saw no IBOC (it can miss weak sidebands)
p.set_sources('nrsc5')
src = sources(p)
check('no SCA: greyed "(none)", still selectable', src['sca67']['dim'] and src['sca67']['enabled']
      and src['sca67']['label'].endswith('(none)'), src['sca67'])
check('no IBOC seen: greyed "(none seen)", still selectable', src['iboc0']['dim'] and src['iboc0']['enabled']
      and src['iboc0']['label'] == 'IBOC MPS (none seen)', src['iboc0'])
p.iboc_scan = {st.freq_hz: -20.0}
p.set_sources('nrsc5')
src = sources(p)
check('IBOC seen: plain', not src['iboc0']['dim'] and src['iboc0']['label'] == 'IBOC MPS', src['iboc0'])
p.set_sources(None)
src = sources(p)
check('no nrsc5: IBOC disabled', not src['iboc0']['enabled'] and 'nrsc5' in src['iboc0']['tip'], src['iboc0'])
check('analog never greyed', not src['analog']['dim'] and src['analog']['enabled'], src['analog'])

# The detail view sits right under the row of the receiver it shows.
host = QtWidgets.QWidget()
win = types.SimpleNamespace(rows_box=QtWidgets.QVBoxLayout(host), details=QtWidgets.QStackedWidget(), panels=[],
                            selected=None)
win.rows_box.addWidget(win.details)
for slot in range(3):
    p = types.SimpleNamespace(slot=slot, row=rm.StationRow(), detail=QtWidgets.QWidget(), window=None)
    win.panels.append(p)
    win.rows_box.removeWidget(win.details)
    win.rows_box.insertWidget(slot, p.row)
    win.details.addWidget(p.detail)
for name in ('focus', '_place_details'):
    setattr(win, name, types.MethodType(getattr(rm.MainWindow, name), win))
win._sync_player = lambda: None     # (the header's player: checked below)


def layout_order():
    items = [win.rows_box.itemAt(i).widget() for i in range(win.rows_box.count())]
    return ['detail' if w is win.details else f'row{next(p.slot for p in win.panels if p.row is w)}' for w in items]


for sel, want, title in ((0, ['row0', 'detail', 'row1', 'row2'], 'detail under the first row when it is selected'),
                         (2, ['row0', 'row1', 'row2', 'detail'], '...under the last row when that is selected'),
                         (1, ['row0', 'row1', 'detail', 'row2'], '...and back up under the middle one')):
    win.focus(win.panels[sel])
    check(title, layout_order() == want, layout_order())
# popped out: its window is raised, and the detail stays under the receiver it still shows
win.panels[0].window = types.SimpleNamespace(raise_=lambda: None, activateWindow=lambda: None)
win.focus(win.panels[0])
check('a popped-out receiver leaves the detail where it is', layout_order() == ['row0', 'row1', 'detail', 'row2'],
      layout_order())

# The header's player plays the selected receiver; selecting another while listening switches to it.
plays = []
pwin = types.SimpleNamespace(listen_btn=QtWidgets.QPushButton(), listen_label=QtWidgets.QLabel(), panels=[],
                             selected=None)
pwin.listen_btn.setCheckable(True)
for slot in range(2):
    p = types.SimpleNamespace(slot=slot, play=QtWidgets.QPushButton(), source=QtWidgets.QComboBox(),
                              station=types.SimpleNamespace(freq_hz=(94.5e6, 101.7e6)[slot]),
                              title=('94.5 ONE', '101.7 TWO')[slot])
    p.play.setCheckable(True)
    pwin.panels.append(p)
for name in ('_sync_player', '_listen'):
    setattr(pwin, name, types.MethodType(getattr(rm.MainWindow, name), pwin))


def on_play(panel, on):   # MainWindow._on_play: one at a time, then the player follows
    plays.append((panel.slot, on))
    if on:
        for q in pwin.panels:
            if q is not panel and q.play.isChecked():
                q.play.setChecked(False)
    pwin._sync_player()


for p in pwin.panels:
    p.play.toggled.connect(lambda on, p=p: on_play(p, on))
pwin.listen_btn.toggled.connect(lambda on: pwin._listen(on))   # (as MainWindow wires it)
pwin.selected = pwin.panels[0]
pwin._sync_player()
check('player: the selected receiver\'s source shows, the other\'s is hidden',
      (pwin.panels[0].source.isHidden(), pwin.panels[1].source.isHidden()) == (False, True))
pwin.listen_btn.setChecked(True)
check('player: Listen plays the selected receiver', [p.play.isChecked() for p in pwin.panels] == [True, False])
check('...and says which, the button now Stop', (pwin.listen_label.text(), pwin.listen_btn.text())
      == ('Rx 1 · 94.5 ONE', '■  Stop'), (pwin.listen_label.text(), pwin.listen_btn.text()))
pwin.selected = pwin.panels[1]
pwin._sync_player()
check('player: selecting another receiver while listening switches the audio to it',
      [p.play.isChecked() for p in pwin.panels] == [False, True] and pwin.listen_label.text() == 'Rx 2 · 101.7 TWO',
      ([p.play.isChecked() for p in pwin.panels], pwin.listen_label.text()))
pwin.listen_btn.setChecked(False)
check('player: Stop stops it', not any(p.play.isChecked() for p in pwin.panels) and not pwin.listen_btn.isChecked())
pwin.selected = pwin.panels[0]
pwin._sync_player()
check('player: not listening, selecting another plays nothing', not any(p.play.isChecked() for p in pwin.panels))

print('\nall state checks passed' if not failed else f'\n{len(failed)} FAILED: {failed}')
sys.exit(1 if failed else 0)
