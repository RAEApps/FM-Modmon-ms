"""Alarm acknowledgement and priorities: every alarm episode waits to be
acknowledged (raised or since cleared), from the log, a lamp, a row, the banner
or the web page; each alarm has a priority (1-3) per receiver, shown as a colour,
a shape and its number on the lamps, the row's status cell, the banner and the
log. No SDR needed. Exits non-zero on a failure."""
import csv
import os
import sys
import tempfile
import time
import types

os.environ['QT_QPA_PLATFORM'] = 'offscreen'
sys.stdout.reconfigure(encoding='utf-8')
from loadapp import load_app  # noqa: E402
rm = load_app()

from PyQt5 import QtWidgets  # noqa: E402

app = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])
bad = []


_ = object()


def check(name, ok, detail=_):
    """check(name, condition[, detail]) for a True/False condition, else check(name, got, want)."""
    if detail is not _ and not isinstance(ok, bool):
        ok, detail = ok == detail, f'(got {ok!r}, want {detail!r})'
    print(f"{'ok   ' if ok else 'WRONG'} {name} {'' if detail is _ else detail}")
    if not ok:
        bad.append(name)


# ------------------------------------------------------------ priorities
prio = {d.name: d.priority for d in rm.ALARM_DEFS}
check('defaults: off air, silent, wrong station are priority 1', [n for n, p in prio.items() if p == 1] ==
      ['CARRIER', 'SILENCE', 'PI'], prio)
check('defaults: over-deviation, pilot, RDS, alerts, AUX are 2',
      {n for n, p in prio.items() if p == 2} == {'EXCEEDANCE', 'PILOT', 'RDS', 'ALERT', 'BACKUP'})
check('defaults: the rest 3', {n for n, p in prio.items() if p == 3} ==
      {'OVERMOD', 'PILOT_SPEC', 'SUBCARRIERS', 'FREQUENCY', 'DATA'})
s = rm.ReceiverSettings()
check('a receiver starts with the defaults', s.priorities == prio)
s2 = rm.ReceiverSettings.from_dict({'priorities': {'OVERMOD': 1, 'PILOT': '3', 'RDS': 7, 'DATA': 'x', 'NOPE': 1}})
check('settings: chosen priorities kept, bad ones back to the default, unknown alarms dropped',
      (s2.priorities['OVERMOD'], s2.priorities['PILOT'], s2.priorities['RDS'], s2.priorities['DATA'], 'NOPE' in s2.priorities)
      == (1, 3, 2, 3, False), s2.priorities)
check('settings: saved files without priorities get the defaults', rm.ReceiverSettings.from_dict({}).priorities == prio)
check('settings round trip', rm.ReceiverSettings.from_dict(s2.to_dict()).priorities == s2.priorities)
dlg = rm.ReceiverDialog(None, 0, s2, 7711)
check('receiver dialog: a priority for each alarm, as set', {n: b.currentData() for n, b in dlg.priority_boxes.items()}
      == s2.priorities)
dlg.priority_boxes['FREQUENCY'].setCurrentIndex(dlg.priority_boxes['FREQUENCY'].findData(1))
check('receiver dialog: a changed priority is in its result', dlg.settings().priorities['FREQUENCY'] == 1)
dlg.alarm_checks['FREQUENCY'].setChecked(False)
check('receiver dialog: an alarm switched off has its priority greyed', not dlg.priority_boxes['FREQUENCY'].isEnabled())
check('app setting: the alarm sound is off unless chosen', (rm.AppConfig().alarm_sound,
      rm.AppConfig.from_dict({'alarm_sound': 1}).alarm_sound) == (False, True))

# ------------------------------------------------------------ lamp states
al = rm.StationAlarms()
al._t0 -= 60
al.active = {'SILENCE', 'RDS'}
al.unacked = {'SILENCE', 'PILOT_SPEC'}
fake = types.SimpleNamespace(settings=rm.ReceiverSettings(), alarms=al)
fake.settings.alarms['DATA'] = False
states = rm.StationPanel._alarm_states(fake, {})
check('raised, not acknowledged: unack', states['SILENCE'], 'unack')
check('raised, acknowledged: raised', states['RDS'], 'raised')
check('cleared, not acknowledged: cleared_unack', states['PILOT_SPEC'], 'cleared_unack')
check('switched off stays off', states['DATA'], 'off')
check('the rest clear', states['CARRIER'], 'clear')
al.reset()
check('retuned: nothing waits on the new station', (al.unacked, al.active), (set(), set()))

# the row's status cell: the highest priority lit, raised or only cleared, and whether any waits
P = rm.ReceiverSettings().priorities
check('status: nothing lit', rm.alarm_status({'CARRIER': 'clear', 'RDS': 'pending'}, P), None)
check('status: a priority 2 raised and acknowledged', rm.alarm_status({'RDS': 'raised', 'FREQUENCY': 'clear'}, P),
      (2, True, False))
check('status: priority 1 cleared (unack) outranks a 3 raised',
      rm.alarm_status({'SILENCE': 'cleared_unack', 'OVERMOD': 'raised'}, P), (1, False, True))
check('status: own priorities count', rm.alarm_status({'OVERMOD': 'unack'}, {**P, 'OVERMOD': 1}), (1, True, True))

# lamps and the status cell draw every state (offscreen)
ann = rm.Annunciator()
ann.resize(190, 50)
ann.set_states({d.name: st for d, st in zip(rm.ALARM_DEFS, ['unack', 'raised', 'cleared_unack', 'pending', 'clear',
                                                              'suppressed', 'waiting', 'off'] * 2)}, {}, P)
check('lamps draw every state', not ann.grab().isNull())
cell = rm.AlarmStatus()
cell.resize(26, 50)
for st in ((1, True, True), (2, False, True), (3, True, False), None):
    cell.set_status(st)
    cell.grab()
check('status cell draws each priority', 'Priority 3' in cell.toolTip() or cell.status is None)

# ------------------------------------------------------------ the log, the banner and acknowledging
table = rm.AlarmTable()
t0 = time.time() - 600
table.raised((0, 98.1e6), '98.1 ONE', 'stereo pilot out of tolerance', 'pilot 10.4%', t=t0, name='PILOT_SPEC',
             priority=3, slot=0)
table.raised((1, 101.7e6), '101.7 TWO', 'audio silence', '', t=t0 + 100, name='SILENCE', priority=1, slot=1)
table.raised((0, 98.1e6), '98.1 ONE', 'RDS lost', '', t=t0 + 200, name='RDS', priority=2, slot=0)
table.cleared((0, 98.1e6), 'stereo pilot out of tolerance', t=t0 + 60)
check('every new episode waits to be acknowledged', [e['name'] for e in table.unacked()] == ['PILOT_SPEC', 'SILENCE', 'RDS'])
row0 = [table.item(0, c).text() for c in range(len(table.COLS))]
check('log: priority first, Acknowledge in the Ack column', (row0[0], row0[table.ACK_COL]) == ('2', 'Acknowledge'), row0)
check('banner: the highest priority, raised before cleared, then newest',
      rm.banner_episode(table.unacked())['name'], 'SILENCE')

panels = []
for slot, freq, active in ((0, 98.1e6, {'RDS'}), (1, 101.7e6, {'SILENCE'})):
    p = types.SimpleNamespace(slot=slot, station=types.SimpleNamespace(freq_hz=freq), alarms=rm.StationAlarms(),
                              settings=rm.ReceiverSettings(), shown=[])
    p.alarms.active = set(active)
    p.show_alarms = (lambda p=p: p.shown.append(set(p.alarms.unacked)))
    panels.append(p)
win = types.SimpleNamespace(alarm_table=table, panels=panels, logged=[], banner=rm.AlarmBanner(lambda ids: None),
                            log_tabs=QtWidgets.QTabBar(), _recovery=None)
win.log_tabs.addTab('Alarms')
win.log = win.logged.append
for m in ('acknowledge', '_ack_panel', '_sync_unacked', '_alarm_tab', '_web_command'):
    setattr(win, m, types.MethodType(getattr(rm.MainWindow, m), win))
win._sync_unacked()
check('each receiver\'s lamps know what waits on its station', (panels[0].alarms.unacked, panels[1].alarms.unacked)
      == ({'PILOT_SPEC', 'RDS'}, {'SILENCE'}))
check('log tab: raised and waiting counts', win.log_tabs.tabText(0) == 'Alarms · 2 raised, 3 to acknowledge',
      win.log_tabs.tabText(0))
check('banner shows (isHidden false) with the priority 1 alarm', (not win.banner.isHidden(),
      win.banner.shown['name']) == (True, 'SILENCE'))
check('banner: Acknowledge all counts them', win.banner.all.text() == 'Acknowledge all (3)')

win._ack_panel(panels[0], 'RDS')
check('a lamp: acknowledges that alarm only', (panels[0].alarms.unacked, table.episodes[2]['acked_by']) ==
      ({'PILOT_SPEC'}, 'this PC'))
check('...logged once', sum('acknowledged' in t for t in win.logged) == 1, win.logged)
check('...and the row redrawn at once', panels[0].shown[-1] == {'PILOT_SPEC'})
check('acknowledging again does nothing', win.acknowledge([table.episodes[2]['id']]) == 0)
row_ack = [table.item(r, table.ACK_COL).text() for r in range(table.rowCount())]
check('log: when and where it was acknowledged', any(t.endswith('· this PC') for t in row_ack), row_ack)

got = win._web_command('ack', {'receiver': 2})
check('web: a receiver\'s alarms', (got, panels[1].alarms.unacked, table.episodes[1]['acked_by']) ==
      ({'acknowledged': 1}, set(), 'web'))
try:
    win._web_command('ack', {'ids': ['x']})
    check('web: bad ids refused', False)
except ValueError:
    check('web: bad ids refused', True)
check('web: every one left', win._web_command('ack', {}) == {'acknowledged': 1} and not table.unacked())
check('banner hidden once nothing waits', win.banner.isHidden())
check('log tab: only the raised count left', win.log_tabs.tabText(0) == 'Alarms · 2 raised', win.log_tabs.tabText(0))

# the optional sound: only with the setting on and a priority 1 alarm waiting
starts = []
real_thread = rm.threading.Thread
rm.threading.Thread = lambda *a, **k: types.SimpleNamespace(start=lambda: starts.append(1))
try:
    win.app_config = rm.AppConfig(alarm_sound=False)
    table.raised((1, 101.7e6), '101.7 TWO', 'audio silence', '', name='SILENCE', priority=1, slot=1)
    rm.MainWindow._alarm_sound(win)
    off = len(starts)
    win.app_config.alarm_sound = True
    rm.MainWindow._alarm_sound(win)
    on = len(starts)
    win.acknowledge([e['id'] for e in table.unacked()])
    rm.MainWindow._alarm_sound(win)
finally:
    rm.threading.Thread = real_thread
check('sound: off by default', off == 0)
check('sound: on, a priority 1 waiting: a tone', on == 1 if os.name == 'nt' else True)
check('sound: acknowledged: quiet', len(starts) == on)

# the log's length: only episodes acknowledged and cleared are forgotten, never one still waiting
log = rm.AlarmTable()
log.KEEP = 5
log.raised('k', 'S', 'waits', '', name='OLD', slot=0)          # cleared, never acknowledged
log.cleared('k', 'waits')
log.raised('k', 'S', 'up', '', name='UP', slot=0)              # acknowledged, still raised
log.acknowledge([log.episodes[-1]['id']])
for i in range(20):                                             # a flapping alarm, each acknowledged
    log.raised('k', 'S', 'flap', '', name='FLAP', slot=0)
    log.cleared('k', 'flap')
    log.acknowledge([log.episodes[-1]['id']])
names = [e['name'] for e in log.episodes]
check('log: trimmed to KEEP', len(log.episodes), 5)
check('log: an old one waiting to be acknowledged is kept', 'OLD' in names and len(log.unacked()) == 1, names)
check('log: one still raised is kept', 'UP' in names, names)
log.cleared('k', 'up')
check('log: ...and can still be cleared', [e['end'] is not None for e in log.episodes if e['name'] == 'UP'], [True])

# ------------------------------------------------------------ on and off delays, shelving
s3 = rm.ReceiverSettings.from_dict({'delays': {'OVERMOD': [2, 30], 'PILOT': ['x', 5], 'FREQUENCY': [9999, -4]},
                                    'silence_s': 20})
check('delays: set ones kept, bad ones back to the default, out of range clipped',
      (s3.delays['OVERMOD'], s3.delays['PILOT'], s3.delays['FREQUENCY']), ([2, 30], [5, 5], [600, 0]))
check("delays: SILENCE's on-delay is its silence time", s3.delay('SILENCE'), (20, 10))
check("delays: saved files without them get the alarms' own", rm.ReceiverSettings.from_dict({}).delay('CARRIER'), (5, 5))
dlg = rm.ReceiverDialog(None, 0, s3, 7711)
on, off = dlg.delay_spins['OVERMOD']
check('receiver dialog: on and off delays as set', (on.value(), off.value()), (2, 30))
check("receiver dialog: SILENCE's on-delay is the silence time (no spin of its own)",
      dlg.delay_spins['SILENCE'][0] is None)
off.setValue(45)
check('receiver dialog: a changed off-delay is in its result', dlg.settings().delays['OVERMOD'], [2, 45])

al = rm.StationAlarms()
clock = [1000.0]
real_mono = rm.time.monotonic
rm.time.monotonic = lambda: clock[0]
al._t0 = clock[0] - 60
holds = {'OVERMOD': (2, 30)}


def step(dt, on):
    clock[0] += dt
    return [(n, up) for n, _, up in al.update({'OVERMOD': on}, holds)]


step(0, True)
check('on-delay: not raised before it', step(1.5, True), [])
check('on-delay: raised once it has held', step(1, True), [('OVERMOD', True)])
step(0, False)
check('off-delay: still raised after the on-delay', step(5, False), [])
check('off-delay: cleared once gone for it', step(26, False), [('OVERMOD', False)])
al.shelve('OVERMOD', 3600)
check('shelved: its condition counts as gone', (step(0, True), step(10, True)), ([], []))
check('shelved: listed until when', 'OVERMOD' in al.shelved_now())
fake = types.SimpleNamespace(settings=rm.ReceiverSettings(), alarms=al)
check('shelved: its lamp says so', rm.StationPanel._alarm_states(fake, {})['OVERMOD'], 'shelved')
al.shelved['OVERMOD'] = rm.time.time() - 1
check('shelving ends by itself', al.shelved_now(), {})
step(0, True)
check('unshelved: it raises again', step(3, True), [('OVERMOD', True)])
rm.time.monotonic = real_mono
check('when it raises and clears, in words', rm.alarm_when(rm.ALARM_DEFS[2], 2, 30),
      'It raises once its condition has held 2 s, and clears once it has been gone 30 s. '
      + rm.ALARM_JUDGED['OVERMOD'] + ' While it is not judged it counts as clear, so a raised alarm clears 30 s later.')

# ------------------------------------------------------------ the log: filter, CSV export
log = rm.AlarmTable()
log.raised('a', '98.1 CLASSIC', 'audio silence', 'below -45 LUFS', name='SILENCE', priority=1, slot=0)
log.raised('b', '101.7 NEWS', 'RDS lost', 'under 1 group/s', name='RDS', priority=2, slot=1)
log.cleared('b', 'RDS lost')
check('log: an Rx column', [log.item(r, 2).text() for r in range(log.rowCount())], ['2', '1'])
log.set_filter('news rds')
check('log: the filter shows the rows with every word', [log.isRowHidden(r) for r in range(2)], [False, True])
log.set_filter('')
check('log: no filter, every row', [log.isRowHidden(r) for r in range(2)], [False, False])
path = os.path.join(tempfile.mkdtemp(), 'alarms.csv')
check('log: export writes every alarm', log.export_csv(path), 2)
with open(path, encoding='utf-8') as fh:
    rows = list(csv.DictReader(fh))
check('log: CSV columns and values', (rows[0]['receiver'], rows[0]['alarm'], rows[0]['cleared'], rows[1]['duration_s'],
                                      rows[1]['priority']), ('1', 'audio silence', '', '0', '2'))
check('app setting: the log height kept in range', (rm.AppConfig().log_height,
      rm.AppConfig.from_dict({'log_height': 5}).log_height, rm.AppConfig.from_dict({'log_height': 'x'}).log_height),
      (200, rm.LOG_MIN_H, 200))

eps = [{'id': i, 'acked': None if i == 3 else 1.0} for i in range(150)]
web = types.SimpleNamespace(alarm_table=types.SimpleNamespace(episodes=eps))
sent = [e['id'] for e in rm.MainWindow._web_episodes(web)]
check('web: the newest 100 and an older one still waiting, oldest first', sent, [3] + list(range(50, 150)))

print('\nall ok' if not bad else f'\n{len(bad)} WRONG')
sys.exit(1 if bad else 0)
