"""The SDR inventory and profiler: radios found are classified (built-in, learned,
new, failed, unusable), a simulated radio the monitor has no profile for is
profiled (its fastest clean rate, its filter's flat part, a starting gain, whether
it closes cleanly) into a usable profile, and learned profiles are saved, chosen,
forgotten and redone. No SDR needed. Exits non-zero on a failure."""
import json
import os
import sys
import tempfile
import threading

import numpy as np

os.environ['QT_QPA_PLATFORM'] = 'offscreen'
sys.stdout.reconfigure(encoding='utf-8')
from loadapp import load_app  # noqa: E402
rm = load_app()

bad = []


def check(name, ok, detail=''):
    print(f"{'ok   ' if ok else 'WRONG'} {name} {detail}")
    if not ok:
        bad.append(name)


class Range:
    def __init__(self, lo, hi, step=0.0):
        self.lo, self.hi, self.st = lo, hi, step

    def minimum(self):
        return self.lo

    def maximum(self):
        return self.hi

    def step(self):
        return self.st


class Result:
    def __init__(self, ret):
        self.ret = ret


class FakeDev:
    """A simulated SoapySDR radio. Streams cleanly up to max_rate (above it, every
    fifth read overflows); its filter is flat to flat_frac of Nyquist and falls
    steeply past it; noise and two carriers scale with the gain (dB) so the ADC
    peaks reach -10 dBFS near gain 30."""

    def __init__(self, rates=None, rate_range=(1e6, 20e6), max_rate=12e6, flat_frac=0.8, tunes=(24e6, 1.7e9),
                 gains=(('LNA', 0, 15), ('MIX', 0, 15), ('VGA', 0, 15)), overall=(0, 45), reclocks=False):
        self.rates, self.rate_range, self.max_rate, self.flat_frac = rates, rate_range, max_rate, flat_frac
        self.reclocks = reclocks     # lists only some rates, but takes any (UHD: its master clock follows)
        self.tunes, self.gains, self.overall = tunes, gains, overall
        self.rate, self.freq, self.gain, self.calls, self.closed = 2e6, 98e6, 0.0, 0, False
        self._block = None

    def getHardwareKey(self):
        return 'Fake'

    def getFrequencyRange(self, d, ch):
        return [Range(*self.tunes)]

    def getSampleRateRange(self, d, ch):
        return [Range(r, r) for r in self.rates] if self.rates else [Range(*self.rate_range)]

    def listSampleRates(self, d, ch):
        return list(self.rates or [])

    def getBandwidthRange(self, d, ch):
        return []

    def listBandwidths(self, d, ch):
        return []

    def listGains(self, d, ch):
        return [g[0] for g in self.gains]

    def getGainRange(self, d, ch, name=None):
        if name is None:
            if self.overall is None:
                raise RuntimeError('no overall gain')
            return Range(*self.overall)
        return Range(*next(g[1:] for g in self.gains if g[0] == name))

    def setGainMode(self, d, ch, on):
        pass

    def setGain(self, d, ch, *a):
        self.gain = float(a[-1])

    def setSampleRate(self, d, ch, rate):
        if self.rates and not self.reclocks:       # (the nearest it has)
            rate = min(self.rates, key=lambda r: abs(r - rate))
        elif not self.rates:
            rate = min(max(rate, self.rate_range[0]), self.rate_range[1])
        self.rate, self._block = rate, None

    def getSampleRate(self, d, ch):
        return self.rate

    def setBandwidth(self, d, ch, bw):
        pass

    def setFrequency(self, d, ch, hz):
        self.freq, self._block = hz, None

    def setupStream(self, d, fmt):
        return 'stream'

    def activateStream(self, s):
        pass

    def deactivateStream(self, s):
        pass

    def closeStream(self, s):
        pass

    def close(self):
        self.closed = True

    def _make(self):
        n = 1 << 16
        rng = np.random.default_rng(int(self.freq / 1e5))
        spec = rng.normal(size=n) + 1j * rng.normal(size=n)
        f = np.fft.fftfreq(n, 1 / self.rate)
        edge = self.flat_frac * self.rate / 2
        h = np.where(np.abs(f) <= edge, 1.0, 10 ** (-(np.abs(f) - edge) / (0.02 * self.rate) * 2))  # 40 dB per 0.02 x rate
        x = np.fft.ifft(spec * h) / 3
        t = np.arange(n) / self.rate
        for carrier in (94.5e6, 101.7e6):        # two stations, wherever they fall in the window
            off = carrier - self.freq
            if abs(off) < self.rate / 2:
                x = x + 3 * np.exp(2j * np.pi * off * t)
        self._block = x.astype(np.complex64)

    def readStream(self, s, bufs, n, timeoutUs=0):
        self.calls += 1
        if self.rate > self.max_rate and self.calls % 5 == 0:
            return Result(-4)
        if self._block is None:
            self._make()
        scale = 10 ** ((self.gain - 30) / 20) * 0.03
        bufs[0][:n] = self._block[:n] * scale
        return Result(n)


# ------------------------------------------------------------ classifying what SoapySDR finds
B210 = {'driver': 'uhd', 'label': 'B210 301234', 'product': 'B210', 'serial': '301234', 'type': 'b200'}
RTL = {'driver': 'rtlsdr', 'label': 'Generic RTL2832U OEM :: 09236637', 'manufacturer': 'Nooelec',
       'product': 'NESDR SMArt v5', 'serial': '09236637', 'tuner': 'Rafael Micro R820T'}
RSPDX = {'driver': 'sdrplay', 'label': 'SDRplay Dev0 RSPdx 2203000001', 'serial': '2203000001'}
FAKE = {'driver': 'fakesdr', 'label': 'FakeSDR One [f00d]', 'serial': 'f00d', 'product': 'FakeSDR One'}
AUDIO = {'driver': 'audio', 'label': 'Voicemeeter Virtual ASIO', 'device_id': '3'}

rm.LEARNED.clear()
inv = rm.scan_sdrs([B210, RTL, RSPDX, FAKE, AUDIO, dict(B210)])
check('scan: sound cards left out, a radio found twice listed once', len(inv) == 4, [r.label for r in inv])
status = {r.label: r.status for r in inv}
check('scan: the built-in kinds are known', status['B210 301234'] == 'known' and status[RTL['label']] == 'known')
check('scan: an RSP without a built-in profile (RSPdx) is new', status[RSPDX['label']] == 'new')
check('scan: another SoapySDR radio is new', status[FAKE['label']] == 'new')
check('scan: usable first, widest window first', [r.key for r in inv][:2] == ['b210', 'rtlsdr'], [r.key for r in inv])
check('find_sdrs: only the usable ones', [k for k, _, _ in rm.find_sdrs(inv)] == ['b210', 'rtlsdr'])
fake = next(r for r in inv if r.driver == 'fakesdr')
check('a radio\'s id: driver and serial', fake.id == 'fakesdr-f00d', fake.id)
check('a radio\'s short name: its product', rm.sdr_name(fake) == 'FakeSDR One')
check('...else its label without the serial', rm.sdr_name(rm.classify_sdr(RSPDX)) == 'SDRplay Dev0 RSPdx',
      rm.sdr_name(rm.classify_sdr(RSPDX)))

# ------------------------------------------------------------ the profiler on a simulated radio
steps = []
probe = rm.probe_device(FakeDev(), lambda step, text: steps.append((step, text)))
check('probe: steps 1-4 reported in order', [s for s, _ in steps] == sorted(s for s, _ in steps) and steps[-1][0] == 4,
      [s for s, _ in steps])
check('probe: the fastest rate (a multiple of 384 kS/s) that streams clean', probe['rate'] == 28 * rm.QUAD_RATE,
      f'({probe["rate"] / 1e6:g} MS/s; tried {probe["tried"]})')
check('probe: the faster ones refused for their overflows', all('overflow' in t for t in probe['tried'][:-1])
      and len(probe['tried']) == 3, probe['tried'])
check('probe: several gain elements -> its overall gain', probe['stage']['name'] == '' and
      (probe['stage']['lo'], probe['stage']['hi']) == (0, 45))
want_flat = 0.8 * probe['rate'] / 2
check('probe: the filter\'s flat part measured', abs(probe['flat_half'] - want_flat) < 0.1e6,
      f'({probe["flat_half"] / 1e6:.3f} MHz, filter flat to {want_flat / 1e6:.3f})')
dev = FakeDev()
dev.setSampleRate(1, 0, probe['rate'])
dev.setFrequency(1, 0, 98e6)
dev.setGain(1, 0, probe['gain'])
buf = np.empty(65536, np.complex64)
dev.readStream(0, [buf], len(buf))
peak = 20 * np.log10(np.percentile(np.abs(buf), 99.99))
check('probe: the starting gain keeps the ADC peaks at most -10 dBFS', peak <= rm.CAL_PEAK_DBFS + 0.01,
      f'({probe["gain"]:g} dB: {peak:.1f} dBFS)')
check('probe: ...and is near the most that does', probe['gain'] >= 25, f'({probe["gain"]:g} dB)')

p = rm.derive_profile(fake, probe, True)
check('profile: passes profile_problems', not rm.profile_problems(p), rm.profile_problems(p))
check('profile: its window fits the flat part, each station\'s channel inside it',
      p.span / 2 + 150e3 + rm.CHAN_PASS_HZ <= probe['flat_half'] + 1 and p.span >= 7.5e6, f'({p.span / 1e6:g} MHz)')
check('profile: opened by its serial', p.device == 'driver=fakesdr,serial=f00d', p.device)
check('profile: its scan windows cover the band', len(p.scan_centers) == 3, p.scan_centers)
check('profile: round trip through the settings file', rm.profile_from_dict(json.loads(json.dumps(rm.profile_to_dict(p)))) == p)
rm.SDRS[p.key] = p
rm.use_sdr(p.key, 'f00d')
check('use_sdr: a learned profile\'s serial not given twice', rm.SDR.device.count('serial=') == 1, rm.SDR.device)
check('use_sdr: its rate set', (rm.SAMP_RATE, rm.CHAN_DECIM) == (p.rate, 28))
del rm.SDRS[p.key]
rm.use_sdr('rsp1a')

# Wide and narrow windows: the scan windows always cover the band, on even tenths.
for half in (0.25e6, 0.9e6, 3.0e6, 6.6e6, 10.0e6, 12.0e6):
    centres = rm.scan_centres(half)
    q = rm.SdrProfile('x', 'X', 'driver=x', 30.72e6, 0, 0, centres, half, (rm.GainStage('', 'Gain', 0, 1),), (0,))
    check(f'scan windows of ±{half / 1e6:g} MHz', not rm.profile_problems(q), f'{len(centres)}: {rm.profile_problems(q)}')
check('the whole band in one window, centred', rm.scan_centres(10.0e6) == (98.0e6,))

# Radios the monitor can't use.
for name, d, want in (('doesn\'t tune FM', FakeDev(tunes=(400e6, 6e9)), 'tune'),
                      ('no gain control', FakeDev(gains=(), overall=None), 'gain'),
                      ('none of the rates (an Airspy: 10 and 2.5 MS/s)', FakeDev(rates=(10e6, 2.5e6)), 'none of the sample rates')):
    try:
        rm.probe_device(d)
        check(f'unusable: {name}', False)
    except rm.SdrUnusable as e:
        check(f'unusable: {name}', want in str(e), f'({e})')
try:
    rm.probe_device(FakeDev(max_rate=1e6))
    check('a radio that streams nothing cleanly: an error, not unusable', False)
except rm.SdrUnusable:
    check('a radio that streams nothing cleanly: an error, not unusable', False)
except RuntimeError as e:
    check('a radio that streams nothing cleanly: an error, not unusable', 'without losing samples' in str(e))
one = rm.probe_device(FakeDev(rates=[2.304e6, 3.2e6], max_rate=2.5e6, gains=(('TUNER', 0, 49.6),), overall=(0, 49.6)))
check('one gain element: that one, by name', one['stage']['name'] == 'TUNER' and one['rate'] == 2.304e6,
      (one['stage'], one['rate']))
uhd_like = rm.probe_device(FakeDev(rates=[8e6 / d for d in range(1, 257)], reclocks=True, max_rate=40e6,
                                   gains=(('PGA', 0, 76),), overall=(0, 76)))
check('a rate it doesn\'t list but takes (UHD re-clocks): used', uhd_like['rate'] == 30.72e6, uhd_like['tried'])
check('a listed rate within 1 S/s is the one set (UHD\'s 30720000.024)',
      rm._offered(30.72e6, [(30720000.024, 30720000.024, 0)], [30720000.024]) == 30720000.024)

# ------------------------------------------------------------ profile_sdr: the steps in helpers (simulated here)
calls = []


def fake_child(func, *args, progress=None, timeout=None, cancel=None, what=None):
    calls.append(func)
    if cancel and cancel.is_set():
        raise rm.ProfileCancelled('cancelled')
    if func == 'profile_probe':
        return json.loads(json.dumps(rm._finite(rm.probe_device(FakeDev(), lambda s, t: progress(f'{s}|{t}')))))
    if func == 'close_test':
        if calls.count('close_test') == 2 and closes_crash:
            raise RuntimeError('the helper process ended (3221225477)')
        return True
    if func == 'cpu_check':
        return 37
    raise AssertionError(func)


real_child, rm._in_child = rm._in_child, fake_child
closes_crash = True
seen = []
entry = rm.profile_sdr(fake, lambda step, text: seen.append(step))
check('profile_sdr: every step reported', sorted(set(seen)) == list(range(1, 8)), sorted(set(seen)))
check('profile_sdr: three closes, each in its own helper', calls.count('close_test') == rm.PROFILE_CLOSES)
check('profile_sdr: a close that crashed -> never closed in-process',
      entry.get('profile') and entry['profile']['closes_cleanly'] is False, entry.get('error'))
check('profile_sdr: the CPU check noted', entry.get('cpu') == 37 and any('37%' in t for t in entry['report']))
closes_crash = False
calls.clear()
entry = rm.profile_sdr(fake)
check('profile_sdr: clean closes -> closes cleanly', entry['profile']['closes_cleanly'] is True)
stop = threading.Event()
stop.set()
try:
    rm.profile_sdr(fake, cancel=stop)
    check('profile_sdr: cancelled', False)
except rm.ProfileCancelled:
    check('profile_sdr: cancelled', True)
rm._in_child = real_child

# ------------------------------------------------------------ learned profiles in the settings file
folder = tempfile.mkdtemp()
cfg = os.path.join(folder, 'config.json')
with open(cfg, 'w', encoding='utf-8') as fh:
    json.dump({'version': 1, 'app': {'setup_done': True, 'sdr': 'fakesdr-f00d'}, 'receivers': []}, fh)
check('a preference for an SDR not profiled (yet) falls back to automatic',
      rm.AppConfig.from_dict({'sdr': 'fakesdr-f00d'}).sdr == 'auto')
rm.save_learned(cfg, fake.id, entry)
with open(cfg, encoding='utf-8') as fh:
    saved = json.load(fh)
check('saved: in the settings file\'s sdrs section, the rest kept',
      'fakesdr-f00d' in saved['sdrs'] and saved['app']['sdr'] == 'fakesdr-f00d')
rm.load_learned(cfg)
check('loaded: in SDRS under its own key', 'fakesdr-f00d' in rm.SDRS and rm.SDRS['fakesdr-f00d'].name == 'FakeSDR One')
check('loaded: the preference for it kept', rm.AppConfig.from_dict({'sdr': 'fakesdr-f00d'}).sdr == 'fakesdr-f00d')
inv = rm.scan_sdrs([RTL, FAKE])
check('scan: a profiled radio is learned, and usable', [(r.key, r.status) for r in inv] ==
      [('fakesdr-f00d', 'learned'), ('rtlsdr', 'known')], [(r.key, r.status) for r in inv])
check('auto: the widest window, a learned one too', rm.choose_sdr('auto', rm.find_sdrs(inv))[0] == 'fakesdr-f00d')
a = rm.resolve_args(rm.parse_args(['--no-scan', '--sdr', 'FakeSDR-F00D']), rm.AppConfig())
check('--sdr takes a learned key (any case)', a.sdr == 'fakesdr-f00d' and a.sdr_required and rm.SDR.key == 'fakesdr-f00d')
check('--gain for a learned SDR', rm.configure_sdr(a, 'fakesdr-f00d') is None and len(a.gain) == 1)
rm.use_sdr('rsp1a')
try:
    rm.resolve_args(rm.parse_args(['--sdr', 'nosuch']), rm.AppConfig())
    check('--sdr refuses an unknown key', False)
except SystemExit:
    check('--sdr refuses an unknown key', True)
check('a radio still listed after a restart reads its profile', rm.FoundSdr.from_dict(inv[0].to_dict()) == inv[0])

# Failed, unusable and outdated entries.
rm.save_learned(cfg, 'rspdx-2203000001'.replace('rspdx', 'sdrplay'), {'version': rm.PROFILER_VERSION,
                'label': RSPDX['label'], 'error': 'it streamed none of the rates without losing samples'})
rm.save_learned(cfg, 'fakesdr-dead', {'version': rm.PROFILER_VERSION, 'label': 'Dead', 'error': 'it doesn\'t tune 87.5-108 MHz',
                                      'unusable': True})
old = dict(entry, version=rm.PROFILER_VERSION - 1, label='Old')
rm.save_learned(cfg, 'fakesdr-beef', dict(old, profile=dict(old['profile'], key='fakesdr-beef')))
inv = {r.id: r for r in rm.scan_sdrs([RSPDX, dict(FAKE, serial='dead', label='Dead'), dict(FAKE, serial='beef', label='Old')])}
check('failed: listed as failed, not profiled again at each start', inv['sdrplay-2203000001'].status == 'failed')
check('unusable: listed as such', inv['fakesdr-dead'].status == 'unusable' and 'tune' in inv['fakesdr-dead'].note)
check('a profile from an older profiler: new again', inv['fakesdr-beef'].status == 'new' and 'fakesdr-beef' not in rm.SDRS)
check('an unreadable learned entry is ignored', (rm.save_learned(cfg, 'fakesdr-bad', {'version': rm.PROFILER_VERSION,
                                                                                     'profile': {'key': 'x'}}) or
                                                  'fakesdr-bad' not in rm.SDRS))

# Forgetting.
rm.save_learned(cfg, 'fakesdr-f00d', None)
check('forgotten: out of SDRS and the file', 'fakesdr-f00d' not in rm.SDRS and
      'fakesdr-f00d' not in json.load(open(cfg, encoding='utf-8'))['sdrs'])
check('forgotten: the radio is new again', rm.classify_sdr(FAKE).status == 'new')
check('built-in profiles never overridden from the file', all(k in rm.SDRS for k in rm.BUILTIN_SDRS))

# The event log / notification line.
text = rm.profile_event(fake, entry)
check('event: what it was profiled as', 'FakeSDR One' in text and 'MS/s' in text and '37%' in text, text)
check('event: a failure says why', 'none of the rates' in rm.profile_event(fake, {'error': 'none of the rates'}))

# A real helper process: cancelled and timed out before it touches a radio.
stop = threading.Event()
stop.set()
try:
    real_child('enumerate_sdrs', cancel=stop)
    check('helper: cancel kills it', False)
except rm.ProfileCancelled:
    check('helper: cancel kills it', True)
try:
    real_child('enumerate_sdrs', timeout=0.3, what='SDR')
    check('helper: a timeout kills it', False)
except rm.ProfileCancelled:
    check('helper: a timeout kills it', False)
except RuntimeError as e:
    check('helper: a timeout kills it', 'no answer in 0.3 s' in str(e), f'({e})')

# ------------------------------------------------------------ the dialogs (profile_sdr simulated)
from PyQt5 import QtCore, QtWidgets  # noqa: E402

app = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])
real_profile = rm.profile_sdr


def quick_profile(found, progress=None, cancel=None):
    for step in range(1, 8):
        progress and progress(step, f'step {step}')
    return dict(entry, label=found.label)


def stuck_profile(found, progress=None, cancel=None):
    progress and progress(2, 'waiting')
    while not cancel.wait(0.05):
        pass
    raise rm.ProfileCancelled('cancelled')


rm.profile_sdr = quick_profile
got = rm.run_profile_dialog(None, fake)
check('dialog: returns the profile', got and got.get('profile') and got['label'] == fake.label)
rm.profile_sdr = stuck_profile
QtCore.QTimer.singleShot(400, lambda: [w.cancel() for w in app.topLevelWidgets()
                                       if isinstance(w, QtWidgets.QProgressDialog) and w.isVisible()])
check('dialog: Skip / Cancel -> None', rm.run_profile_dialog(None, fake, 'Skip') is None)

# At the start: each new radio profiled and saved, a skipped one left new; the radios classified again.
rm.load_learned(cfg)
args = rm.parse_args(['--config', cfg, '--no-scan'])
args.sdr_inventory = rm.scan_sdrs([RTL, FAKE, dict(FAKE, serial='cafe', label='FakeSDR Two [cafe]')])
order = iter((quick_profile, stuck_profile))
rm.profile_sdr = lambda *a, **k: next(order)(*a, **k)
QtCore.QTimer.singleShot(1500, lambda: [w.cancel() for w in app.topLevelWidgets()
                                        if isinstance(w, QtWidgets.QProgressDialog) and w.isVisible()])
events = rm.profile_new_sdrs(args)
status = {r.id: r.status for r in args.sdr_inventory}
check('start: the first new radio profiled, saved and usable', status.get('fakesdr-f00d') == 'learned', status)
check('start: the skipped one stays new', status.get('fakesdr-cafe') == 'new')
check('start: a line for each', len(events) == 2 and 'profiled' in events[0] and 'skipped' in events[1], events)
rm.profile_sdr = real_profile


class Win:   # what SdrList uses of MainWindow
    _sdr_job = None
    _in_use = staticmethod(rm.MainWindow._in_use)
    sdr_inventory = args.sdr_inventory


rm.use_sdr('rtlsdr', '09236637')
box = rm.SdrList(Win())
rows = {box.tree.topLevelItem(i).text(0): box.tree.topLevelItem(i).text(1) for i in range(box.tree.topLevelItemCount())}
check('settings list: in use, profiled here, new', rows.get(RTL['label']) == 'in use' and
      rows.get(FAKE['label']) == 'profiled here' and rows.get('FakeSDR Two [cafe]', '').startswith('new'), rows)
check('settings list: profiled here but not plugged in still listed', 'Dead' in rows or 'Old' in rows, rows)
box.tree.setCurrentItem(next(box.tree.topLevelItem(i) for i in range(box.tree.topLevelItemCount())
                             if box.tree.topLevelItem(i).text(0) == RTL['label']))
check('settings list: the SDR in use can\'t be profiled or forgotten here',
      not box.profile_btn.isEnabled() and not box.forget_btn.isEnabled())
box.tree.setCurrentItem(next(box.tree.topLevelItem(i) for i in range(box.tree.topLevelItemCount())
                             if box.tree.topLevelItem(i).text(0) == FAKE['label']))
check('settings list: a learned one can be profiled again, reported and forgotten',
      box.profile_btn.isEnabled() and box.report_btn.isEnabled() and box.forget_btn.isEnabled())
dlg = rm.AppSettingsDialog(None, rm.NotifySettings(), rm.Notifier(rm.NotifySettings(), lambda: ('host', None)),
                           'fakesdr-f00d', win=Win())
check('settings: a learned SDR can be the one to use', dlg.sdr() == 'fakesdr-f00d')
rm.use_sdr('rsp1a')

print('\nall ok' if not bad else f'\n{len(bad)} WRONG')
sys.exit(1 if bad else 0)
