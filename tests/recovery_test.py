"""SDR lost and recovered: the watchdog, reopening in place (MainWindow._sdr_lost /
_recover / _watch_sdr / _sdr_recovered on a stub window with a fake flowgraph whose
SDR fails to open N times), the restart for an SDR that can't be closed in-process
(the B210), the restarted process waiting for it (detect_sdr --recovering),
restart_argv and _retry. No SDR is opened: the device and the clock are fakes."""
import os
import re
import sys
import threading
import types

os.environ['QT_QPA_PLATFORM'] = 'offscreen'
sys.stdout.reconfigure(encoding='utf-8')
from loadapp import load_app  # noqa: E402
rm = load_app()

bad = 0
real_time = rm.time
MW = rm.MainWindow


def check(title, got, want):
    global bad
    ok = got == want
    bad += not ok
    print(f'   {"ok   " if ok else "WRONG"} {title}: {got!r}' + ('' if ok else f', expected {want!r}'))


# Real time, but every sleep is recorded (the reopening loop's waits are its retry schedule).
sleeps = []


def recording_sleep(s):
    sleeps.append(s)
    real_time.sleep(min(s, 0.3))


rm.time = types.SimpleNamespace(monotonic=real_time.monotonic, time=real_time.time, strftime=real_time.strftime,
                                sleep=recording_sleep)
rm.SDR_RETRY_S = (0.1, 0.2, 0.3)
POLL = 0.25   # _recover's own wait for samples, step by step


class FakeFlowgraph:
    """detach_sdr / attach_sdr as the real one, the SDR scripted: each attach either raises,
    opens without samples ('silent'), or opens and samples flow a moment later ('ok')."""

    def __init__(self, script):
        self.script = list(script)
        self.stations = [types.SimpleNamespace(meter=types.SimpleNamespace(last_update=0.0))]
        self.attaches = self.detaches = 0

    def detach_sdr(self):
        self.detaches += 1

    def attach_sdr(self):
        self.attaches += 1
        step = self.script.pop(0)
        if isinstance(step, Exception):
            raise step
        if step == 'ok':
            def samples():
                self.stations[0].meter.last_update = real_time.monotonic()
            threading.Timer(0.05, samples).start()


def counter():
    c = types.SimpleNamespace(n=0)
    c.reset = lambda: setattr(c, 'n', c.n + 1)
    return c


def stub_window(tb, n_panels=2):
    w = types.SimpleNamespace(_recovery=None, tb=tb, logged=[], events=[], sent_now=[], saved=0,
                              switch_to=None, restart_extra=[], _watch_from=None, windows=0, overload_checks=0)
    w.panels = [types.SimpleNamespace(alarms=types.SimpleNamespace(holds=0), station=types.SimpleNamespace(
        meter=counter(), audio_meter=counter(), sca_meter=counter())) for _ in range(n_panels)]
    for p in w.panels:
        p.alarms.hold = (lambda a: lambda: setattr(a, 'holds', a.holds + 1))(p.alarms)
    w.log = w.logged.append
    w.notifier = types.SimpleNamespace(event=lambda kind, text: w.events.append((kind, text)),
                                       send_now=lambda kind, text: w.sent_now.append((kind, text)))
    w.save = lambda: setattr(w, 'saved', w.saved + 1)
    w._update_window = lambda: setattr(w, 'windows', w.windows + 1)
    w._watch_overload = lambda: setattr(w, 'overload_checks', w.overload_checks + 1)
    for name in ('_last_samples', '_sdr_lost', '_sdr_recovered', '_recover'):
        setattr(w, name, getattr(MW, name).__get__(w))
    return w


def run_watchdog(w, timeout=20.0):
    """The GUI's once-a-second _watch_sdr, here every 20 ms, until reopened (or timeout)."""
    end = real_time.monotonic() + timeout
    seen_text = None
    while w._recovery and real_time.monotonic() < end:
        MW._watch_sdr(w)
        if w._recovery and seen_text is None and w._recovery['attempt']:
            seen_text = MW._gain_text(w)
        real_time.sleep(0.02)
    return seen_text


print('--- the watchdog')
tb = FakeFlowgraph([])
w = stub_window(tb)
lost = []
w._sdr_lost = lost.append
MW._watch_sdr(w)
check('before start_watchdog: never lost', (lost, w.overload_checks), ([], 1))
w._watch_from = real_time.monotonic() - 1.0
MW._watch_sdr(w)
check(f'silent for less than SDR_STALL_S ({rm.SDR_STALL_S:g} s): fine', lost, [])
tb.stations[0].meter.last_update = real_time.monotonic() - 1.0
w._watch_from = real_time.monotonic() - 100
MW._watch_sdr(w)
check('samples a second ago: fine', lost, [])
tb.stations[0].meter.last_update = real_time.monotonic() - 5.0
MW._watch_sdr(w)
check('no samples for 5 s: lost', [round(s) for s in lost], [5])

print('--- reopening in place (RSP1A): fails 4 times, then samples flow')
rm.SDR = rm.SDRS['rsp1a']
tb = FakeFlowgraph([RuntimeError('device not found'), RuntimeError(''), RuntimeError('service restarting'),
                    RuntimeError('service restarting'), 'ok'])
w = stub_window(tb)
sleeps.clear()
MW._sdr_lost(w, 4.2)
check('lost: logged and notified', (w.logged[:1], w.events[:1]),
      (['SDR lost: no samples from the RSP1A for 4 s; reopening it'],
       [('sdr', 'SDR lost: no samples from the RSP1A for 4 s; reopening it')]))
check('...alarms held on every receiver', [p.alarms.holds for p in w.panels], [1, 1])
check('...no restart', (w.switch_to, w.restart_extra, w.sent_now), (None, [], []))
gain_text = run_watchdog(w)
check('reopened', w._recovery, None)
check('the header says SDR LOST while reopening',
      bool(gain_text and re.fullmatch(r'SDR LOST – reopening \(attempt \d, \d+ s\)', gain_text)), True)
check('attach tried 5 times', tb.attaches, 5)
check('let go first, then after each failure', tb.detaches, 1 + 4)
retry_waits = [s for s in sleeps if s != POLL]
check('waits between tries follow SDR_RETRY_S (the last repeats)', retry_waits, [0.1, 0.2, 0.3, 0.3])
fails = [t for t in w.logged if t.startswith('SDR: reopening attempt')]
check('each new error logged once, with its attempt', fails,
      ['SDR: reopening attempt 1 failed: device not found',
       'SDR: reopening attempt 2 failed: RuntimeError',      # (an empty message: the exception's name)
       'SDR: reopening attempt 3 failed: service restarting'])  # (attempt 4, the same error: not repeated)
rec_line = w.logged[-1]
check('recovered: logged with the attempt count', bool(re.fullmatch(r'SDR recovered after \d+ s \(5 attempts\)', rec_line)),
      True)
check('...and notified', w.events[-1], ('sdr', rec_line))
check('...meters reset on every receiver',
      [(p.station.meter.n, p.station.audio_meter.n, p.station.sca_meter.n) for p in w.panels], [(1, 1, 1)] * 2)
check('...alarms held again (the gap is no station\'s fault)', [p.alarms.holds for p in w.panels], [2, 2])

print('--- opened, but no samples came; then back on the next try')
tb = FakeFlowgraph(['silent', 'ok'])
w = stub_window(tb, n_panels=1)
sleeps.clear()
t0 = real_time.monotonic()
MW._sdr_lost(w, 3.5)
run_watchdog(w)
check('reopened', w._recovery, None)
check('waited ~6 s for samples on the silent open', 5.5 < real_time.monotonic() - t0 < 12, True)
check('the silent open is let go of again', (tb.attaches, tb.detaches), (2, 2))
check('its error logged', [t for t in w.logged if 'attempt' in t and 'failed' in t],
      ['SDR: reopening attempt 1 failed: opened, but no samples came'])
check('recovered after 2 attempts', bool(re.search(r'\(2 attempts\)$', w.logged[-1])), True)
w = stub_window(FakeFlowgraph([]), n_panels=0)
MW._sdr_recovered(w, {'since': real_time.time(), 'attempt': 1})
check('one try: "1 attempt"', w.logged, ['SDR recovered after 0 s (1 attempt)'])

print('--- the B210 (closes_cleanly False): restart, never reopened in-process')
rm.SDR = rm.SDRS['b210']
check('the B210 profile cannot close cleanly', rm.SDR.closes_cleanly, False)
quits = []
real_qtw = rm.QtWidgets
rm.QtWidgets = types.SimpleNamespace(QApplication=types.SimpleNamespace(quit=lambda: quits.append(1)))
tb = FakeFlowgraph(['ok'])
w = stub_window(tb)
try:
    MW._sdr_lost(w, 7.0)
finally:
    rm.QtWidgets = real_qtw
check('no reopening started', (w._recovery, tb.attaches, tb.detaches), (None, 0, 0))
check('logged', w.logged, ['SDR lost: no samples from the B210 for 7 s; restarting FM-Modmon-ms to reopen it'])
check('notified by the queue (flushed as the process ends), not sent on the GUI thread', (w.sent_now, w.events),
      ([], [('sdr', 'SDR lost: no samples from the B210 for 7 s; restarting FM-Modmon-ms to reopen it')]))
check('settings saved, app quit', (w.saved, len(quits)), (1, 1))
check('restart on the same SDR, recovering', (w.switch_to, w.restart_extra), ('b210', ['--recovering']))
# main() then starts: restart_argv(sys.argv[1:], win.switch_to, os.getpid()) + win.restart_extra
argv = rm.restart_argv(['--config', 'c.json', '--freqs', '101.7', '99.3', '--web-port', '8090'], w.switch_to, 4321) \
    + w.restart_extra
check('the new command line', argv,
      ['--config', 'c.json', '--web-port', '8090', '--sdr', 'b210', '--after-pid', '4321', '--recovering'])
a = rm.parse_args(argv)
check('...parses: recovering, waiting for this process', (a.sdr, a.after_pid, a.recovering), ('b210', 4321, True))
again = rm.restart_argv(argv, 'b210', 5555) + ['--recovering']
check('lost again after a restart: options not doubled', again,
      ['--config', 'c.json', '--web-port', '8090', '--sdr', 'b210', '--after-pid', '5555', '--recovering'])

print('--- restart_argv')
cases = [
    (['--sdr', 'rsp1a', '--lna', '3', '--ifgr', '40', '--no-scan'], ['--no-scan']),
    (['--sdr=rsp1a', '--gain=30', '--setup', '--country', 'US'], ['--country', 'US']),
    (['--freqs', '88.1', '107.9', '--config', 'x.json'], ['--config', 'x.json']),
    (['--config', 'x.json', '--freqs', '101.7'], ['--config', 'x.json']),
    (['--after-pid', '99', '--recovering', '--web-port', '0'], ['--web-port', '0']),
]
for given, kept in cases:
    check(' '.join(given), rm.restart_argv(given, 'rtlsdr', 7), kept + ['--sdr', 'rtlsdr', '--after-pid', '7'])

print('--- the restarted monitor waits for the lost SDR (detect_sdr --recovering)')
clock = {'t': 0.0}
waits, progress, configured = [], [], []


def fake_sleep(s):
    waits.append(s)
    clock['t'] += s


rm.time = types.SimpleNamespace(monotonic=lambda: clock['t'], time=real_time.time, strftime=real_time.strftime,
                                sleep=fake_sleep)
rm.sdrplay_service_state = lambda wait_s=0.0: 'running'
rm.configure_sdr = lambda args, key, serial='', error=None: configured.append((key, serial))
B210 = ('b210', 'S1', 'B210')
RSP = ('rsp1a', 'R1', 'RSP1A')


def detect(argv, attached):
    """attached(look) -> what find_sdrs() finds on that look (0 = the first)."""
    looks = []

    def find_sdrs(inventory=None):
        looks.append(1)
        return attached(len(looks) - 1)
    rm.find_sdrs = find_sdrs
    rm.scan_sdrs = lambda found=None: []   # (no real radios: find_sdrs above says what is attached)
    clock['t'] = 0.0
    waits.clear(), progress.clear(), configured.clear()
    args = rm.parse_args(argv)
    args.sdr_required = True   # (resolve_args: --sdr given)
    return rm.detect_sdr(args, progress.append), len(looks)


recovering = ['--sdr', 'b210', '--after-pid', '1', '--recovering']
got, looks = detect(recovering, lambda n: [B210] if n >= 4 else [])
check('back on the 5th look: reopened', (got, configured), ('B210 (reopened after it was lost)', [('b210', 'S1')]))
check('...looked 5 times, 2 s then 5 s apart', waits, [2, 2, 2, 5])
check('...progress shown while waiting', progress[:1], ['Waiting for the B210 to come back… (0 s)'])
got, looks = detect(recovering, lambda n: [RSP])
check('another SDR attached, the B210 not back: wait RECOVER_WAIT_S, then use it',
      (got, configured, clock['t'] >= rm.RECOVER_WAIT_S), (
          'RSP1A (the B210 chosen in Setup isn\'t attached)', [('rsp1a', 'R1')], True))
check('...and no longer than that', clock['t'] < rm.RECOVER_WAIT_S + 6, True)
got, looks = detect(recovering, lambda n: [B210] if n >= 60 else [])
check('none attached: keep waiting past RECOVER_WAIT_S', (got, looks, clock['t'] > rm.RECOVER_WAIT_S * 4),
      ('B210 (reopened after it was lost)', 61, True))
got, looks = detect(['--sdr', 'b210', '--after-pid', '1'], lambda n: [RSP])
check('switching (not recovering): give up after SWITCH_LOOKS', (got, looks, progress),
      ('RSP1A (the B210 chosen in Setup isn\'t attached)', rm.SWITCH_LOOKS + 1, []))

print('--- _retry (opening a device that has only just been let go of)')
waits.clear()
tries = []


def opener(fail, exc=RuntimeError):
    def open_device():
        tries.append(1)
        if len(tries) <= fail:
            raise exc('busy')
        return 'device'
    return open_device


check('fails twice, then opens', rm._retry(opener(2)), 'device')
check('...a second between tries', waits, [1.0, 1.0])
tries.clear(), waits.clear()
try:
    rm._retry(opener(9), attempts=3)
    got = 'opened'
except RuntimeError as e:
    got = str(e)
check('always busy: the last error raised after `attempts` tries', (got, len(tries), waits), ('busy', 3, [1.0, 1.0]))
tries.clear(), waits.clear()
try:
    rm._retry(opener(1, ValueError))
    got = 'opened'
except ValueError:
    got = 'ValueError'
check('another error: raised at once, no retry', (got, len(tries)), ('ValueError', 1))
rm.time = real_time

# A B210's start-up scan and calibration run in a helper that is killed if it hangs.
calls = []
real_child, real_sdr = rm._in_child, rm.SDR


def fake_child(func, *args, **kw):
    calls.append((func, kw.get('timeout')))
    return ([], {}) if func == 'band_scan' else ([30.0], 'ok')


rm._in_child, rm.SDR = fake_child, rm.replace(rm.SDR, closes_cleanly=False)
try:
    rm.band_scan((30.0,))
    rm.calibrate_startup([98.1e6], (30.0,))
finally:
    rm._in_child, rm.SDR = real_child, real_sdr
check('B210 start-up helpers have a timeout', calls,
      [('band_scan', rm.HELPER_TIMEOUT_S), ('calibrate_startup', rm.HELPER_TIMEOUT_S)])

# At exit a B210 whose samples stalled can leave the flowgraph's wait() stuck: given up on.
stuck = threading.Event()
done = []
stopping = types.SimpleNamespace(stop=lambda: done.append('stop'), wait=lambda: done.append('wait'))
hung = types.SimpleNamespace(stop=lambda: None, wait=stuck.wait)
check('stop_flowgraph: stops and waits', (rm.stop_flowgraph(stopping), done), (True, ['stop', 'wait']))
t0 = real_time.monotonic()
check('...with a timeout, a stuck wait() is given up on', rm.stop_flowgraph(hung, 0.3), False)
check('...after that long', round(real_time.monotonic() - t0, 1), 0.3)
stuck.set()

print('\nall as expected' if not bad else f'\n{bad} unexpected')
sys.exit(1 if bad else 0)
