"""Measurement records (Recorder: a CSV line a minute per receiver, on demand) and the
deletion of old event logs and records (prune_files), with their settings."""
import csv
import datetime
import importlib.util
import os
import sys
import tempfile
import time
import types

os.environ['QT_QPA_PLATFORM'] = 'offscreen'
sys.stdout.reconfigure(encoding='utf-8')
spec = importlib.util.spec_from_file_location('fm_modmon', os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'fm-modmon-ms.py'))
rm = importlib.util.module_from_spec(spec)
spec.loader.exec_module(rm)
from PyQt5 import QtWidgets

app = QtWidgets.QApplication([])
bad = 0


def check(name, got, expected):
    global bad
    ok = got == expected
    bad += not ok
    print(f'   {"ok   " if ok else "WRONG"} {name}: {got!r}' + ('' if ok else f', expected {expected!r}'))


def panel(slot, mhz, ps=''):
    """What Recorder reads of a StationPanel."""
    return types.SimpleNamespace(slot=slot, station=types.SimpleNamespace(freq_hz=int(mhz * 1e6)),
                                 history=rm.History(), alarms=types.SimpleNamespace(active=set()),
                                 static_ps=lambda: ps, settings=types.SimpleNamespace(name='spare'))


def feed(p, t0, seconds, pos=lambda i: 90.0, rf=-40.0):
    """seconds of 10-a-second readings from t0: pos_pct from pos(i), the rest steady."""
    for i in range(seconds * rm.UPDATE_HZ):
        t = t0 + i / rm.UPDATE_HZ
        p.history.add(t, {'pos_pct': pos(i), 'neg_pct': 80.0, 'rf_dbfs': rf, 'snr_db': None})


def rows(path):
    with open(path, encoding='utf-8', newline='') as fh:
        return list(csv.reader(fh))


folder = tempfile.mkdtemp(prefix='fmmm-record-')
# A local-time minute boundary, so a day's file name is the date of t0
t0 = time.mktime(datetime.datetime(2026, 11, 23, 23, 57).timetuple())

print('--- off by default; on, it starts at the next whole minute')
check('AppConfig: recording off by default', rm.AppConfig().record, False)
check('AppConfig: logs kept for ever by default', rm.AppConfig().keep_days, 0)
rec = rm.Recorder(folder)
a, b = panel(0, 101.7, 'WEXA'), panel(1, 94.5)
check('off: nothing written', (rec.tick([a, b], t0 + 200), os.listdir(folder)), (None, []))
rec.start(now=t0 + 10)          # part-way into the 23:57 minute: the first line is 23:58's
feed(a, t0, 180, pos=lambda i: 90.0 + (i == 700) * 15.0)  # one 105% peak at 23:58:10
feed(b, t0, 180)
a.history.log_alarm(t0 + 75, 'OVERMOD', True)
a.history.log_alarm(t0 + 80, 'OVERMOD', False)
b.alarms.active = {'RDS'}
for s in range(0, 181):          # the GUI's refreshes, a second apart here
    rec.tick([a, b], t0 + 10 + s)
pa = rec.path(t0 + 60, a.station.freq_hz)
got = rows(pa)
check('file per station and day', os.path.basename(pa), 'fm-modmon-ms_101.7_2026-11-23.csv')
check('header', got[0], list(rm.Recorder.COLUMNS))
check('the partial first minute is skipped; 23:58 and 23:59 written', [r[0] for r in got[1:]],
      ['2026-11-23 23:58', '2026-11-23 23:59'])
col = {k: i for i, k in enumerate(rm.Recorder.COLUMNS)}
r58 = got[1]
check('receiver, frequency, name (PS)', (r58[col['receiver']], r58[col['freq_mhz']], r58[col['station']]),
      ('1', '101.7', 'WEXA'))
check('seconds with readings', r58[col['seconds']], '60')
check('a peak reading: the minute\'s maximum', r58[col['pos_pct']], '105.00')
check('...the next minute without it', got[2][col['pos_pct']], '90.00')
check('a level: the minute\'s mean', r58[col['rf_dbfs']], '-40.00')
check('a reading never available: blank', r58[col['snr_db']], '')
check('an alarm raised and cleared within the minute', r58[col['alarms']], 'OVERMOD')
check('...not the next minute', got[2][col['alarms']], '')
pb = rec.path(t0 + 60, b.station.freq_hz)
gb = rows(pb)
check('other receiver: its own file, its saved name while no PS', (gb[1][col['receiver']], gb[1][col['station']]),
      ('2', 'spare'))
check('an alarm raised all minute', gb[1][col['alarms']], 'RDS')

print('--- a new file each day')
feed(a, t0 + 180, 70)
feed(b, t0 + 180, 70)
rec.tick([a, b], t0 + 241)
check('00:00 goes to the next day\'s file', rows(rec.path(t0 + 180, a.station.freq_hz))[1:][0][0], '2026-11-24 00:00')
check('...which has its own header', rows(rec.path(t0 + 180, a.station.freq_hz))[0], list(rm.Recorder.COLUMNS))

print('--- off again: nothing more')
rec.stop()
before = len(rows(pa)), len(os.listdir(folder))
rec.tick([a, b], t0 + 600)
check('stopped: no new lines or files', (len(rows(pa)), len(os.listdir(folder))), before)

print('--- a folder that can\'t be written: reported once, then again only once it works and fails anew')
blocked = os.path.join(folder, 'blocked')
open(blocked, 'w').close()           # a file where the folder should be
rec2 = rm.Recorder(blocked)
rec2.start(now=t0)
msg = rec2.tick([a], t0 + 125)
check('failure reported', bool(msg) and msg.startswith('recording: could not write'), True)
check('...not repeated every minute', rec2.tick([a], t0 + 185), None)

print('--- old event logs and records deleted')
logs = tempfile.mkdtemp(prefix='fmmm-logs-')
today = datetime.date(2026, 11, 23)
names = [f'fm-modmon-ms_events_{today - datetime.timedelta(days=d):%Y-%m-%d}.log' for d in (0, 89, 90, 400)]
names += ['fm-modmon-ms_101.7_2026-01-01.csv', 'notes_2020-01-01.log', 'fm-modmon-ms_config.json',
          'fm-modmon-ms_events_2026-13-01.log']
for n in names:
    open(os.path.join(logs, n), 'w').close()
check('keep 0: nothing deleted', rm.prune_files(logs, 0, today), [])
gone = rm.prune_files(logs, 90, today)
check('90 days: files 90 days old or more deleted, today\'s and 89 days kept',
      gone, sorted([names[2], names[3], 'fm-modmon-ms_101.7_2026-01-01.csv']))
check('other files and bad dates left alone', sorted(os.listdir(logs)),
      sorted([names[0], names[1], 'notes_2020-01-01.log', 'fm-modmon-ms_config.json',
              'fm-modmon-ms_events_2026-13-01.log']))
check('a missing folder is fine', rm.prune_files(os.path.join(logs, 'none'), 90, today), [])

print('--- settings')
c = rm.AppConfig.from_dict({'record': 1, 'keep_days': '30'})
check('saved settings read back', (c.record, c.keep_days), (True, 30))
check('bad keep_days: the default (kept)', rm.AppConfig.from_dict({'keep_days': 'x'}).keep_days, 0)
check('keep_days kept within 0-3650', (rm.AppConfig.from_dict({'keep_days': -5}).keep_days,
                                       rm.AppConfig.from_dict({'keep_days': 99999}).keep_days), (0, 3650))
check('round trip', rm.AppConfig.from_dict(c.to_dict()), c)
notifier = rm.Notifier(rm.NotifySettings(), lambda: ('host', None))
d = rm.AppSettingsDialog(None, rm.NotifySettings(), notifier, record=True, keep_days=30)
check('settings dialog shows them', (d.record.isChecked(), d.keep_days.value()), (True, 30))
d.keep_days.setValue(0)
check('0 days reads "for ever"', d.keep_days.text(), 'ever')

print('--- the window: REC chip and saved setting')
rm.LOG_DIR = tempfile.mkdtemp(prefix='fmmm-winlog-')   # not the real event log
cfg_path = os.path.join(tempfile.mkdtemp(prefix='fmmm-cfg-'), 'config.json')
tb = types.SimpleNamespace(slots=[None] * rm.MAX_RECEIVERS, center_hz=98_000_000, gain_auto=False,
                           window_hz=lambda: (94_400_000, 101_600_000), gain=rm.SDR.default_gain)
try:
    win = rm.MainWindow(tb, [], {}, config_path=cfg_path)
except Exception as e:   # a stub flowgraph the window outgrew: say so rather than pass silently
    win = None
    check('window builds with a stub flowgraph', repr(e), None)
if win:
    win.recorder.folder = folder
    win.app_config = rm.AppConfig(setup_done=True)
    check('starts not recording', (win.recorder.on, win.chips['rec'].text()), (False, 'REC off  ▾'))
    menu = win._record_menu()
    check('chip menu offers to start', menu.actions()[0].text().startswith('Start recording'), True)
    menu.actions()[0].trigger()
    check('started from the chip', (win.recorder.on, win.chips['rec'].text()), (True, '●  REC'))
    check('...saved', rm.load_app(cfg_path).record, True)
    check('...logged', 'recording: on' in win.events[-1], True)
    win._record_menu().actions()[0].trigger()
    check('stopped from the chip, saved', (win.recorder.on, rm.load_app(cfg_path).record), (False, False))
    old = os.path.join(rm.LOG_DIR, 'fm-modmon-ms_events_2000-01-01.log')
    open(old, 'w').close()
    win._pruned_on = None
    win.prune()
    check('prune by default (keep_days 0): old event log kept', os.path.exists(old), True)
    win.app_config.keep_days = 90
    win._pruned_on = None
    win.prune()
    check('prune with keep_days 90: old event log deleted and logged', (os.path.exists(old), 'deleted 1 event log' in win.events[-1]),
          (False, True))

print('\nall as expected' if not bad else f'\n{bad} unexpected')
sys.exit(1 if bad else 0)
