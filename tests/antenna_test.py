"""Antenna tuning: window_snrs on synthetic IQ (a better antenna, more S/N; an
overloaded ADC flagged), AntennaTuner (smoothing, peak hold, the weakest
station's score, marks ranked, reset, a retuned receiver), and AntennaLoop on
a flowgraph fed from a synthetic source: it measures, its IQ tap survives the
SDR being reopened, and stopping it removes the tap. No SDR is opened.
Exits non-zero on a failure."""
import json
import os
import sys
import threading
import time

import numpy as np

os.environ['QT_QPA_PLATFORM'] = 'offscreen'
sys.stdout.reconfigure(encoding='utf-8')
from loadapp import load_app  # noqa: E402
rm = load_app()
from gnuradio import blocks, gr  # noqa: E402  (after the module set up the DLL paths)

bad = []


def check(name, ok, detail=''):
    print(f"{'ok   ' if ok else 'WRONG'} {name} {detail}")
    if not ok:
        bad.append(name)


CENTER = 98.0e6
FREQS = [96.5e6, 98.9e6, 100.3e6]


def band(stations_db, noise_db=-75.0, n=1 << 19, seed=1):
    """IQ of the SDR window: each station a 120 kHz wide block of noise (an FM signal's
    spread) at its level in dBFS, over white noise at noise_db dBFS."""
    rng = np.random.default_rng(seed)
    f = np.fft.fftfreq(n, 1 / rm.SAMP_RATE)

    def noise(n_):
        return rng.standard_normal(n_) + 1j * rng.standard_normal(n_)

    x = noise(n) * 10 ** (noise_db / 20) / np.sqrt(2)
    for freq, db in stations_db.items():
        spec_ = np.where(np.abs(f - (freq - CENTER)) < 60e3, noise(n), 0)
        s = np.fft.ifft(spec_)
        x = x + s / np.sqrt(np.mean(np.abs(s) ** 2)) * 10 ** (db / 20)
    return x.astype(np.complex64)


# --- window_snrs: what the antenna's improvement does to the readings
print('window_snrs')
weak = {FREQS[0]: -45.0, FREQS[1]: -40.0, FREQS[2]: -50.0}
better = {f: db + 6 for f, db in weak.items()}        # the same stations, 6 dB more antenna gain
p1, c1, s1 = rm.window_snrs(band(weak), CENTER, FREQS)
p2, c2, s2 = rm.window_snrs(band(better), CENTER, FREQS)
print('     ', [f'{v:.1f}' for v in s1], '->', [f'{v:.1f}' for v in s2])
check('weakest station is the weakest', int(np.argmin(s1)) == 2)
check('6 dB more signal: S/N up 5-7 dB on each', all(5 < b - a < 7 for a, b in zip(s1, s2)),
      str([round(b - a, 1) for a, b in zip(s1, s2)]))
check('no overload at these levels', not c1 and not c2 and p2 < rm.CAL_PEAK_DBFS, f'{p2:.1f} dBFS')
x = band({f: db + 49 for f, db in weak.items()})       # far too much: the ADC clips
x = np.clip(x.real, -1, 1) + 1j * np.clip(x.imag, -1, 1)
_, clipped, _ = rm.window_snrs(x.astype(np.complex64), CENTER, FREQS)
check('too much signal: clipped', clipped)

# --- AntennaTuner
print('AntennaTuner')
t = rm.AntennaTuner((4, 40))
check('no score before a measurement', t.score is None and t.mark('x') is None)
t.update(FREQS, -20.0, False, [30.0, 35.0, 20.0], now=0.0)
check('first reading taken as it is', t.snr[FREQS[2]] == 20.0 and t.score == 20.0)
for i in range(30):                                    # the antenna improved: weakest station to 26 dB
    t.update(FREQS, -20.0, False, [30.0, 35.0, 26.0], now=0.2 * (i + 1))
check('smoothed reading settles on the new S/N', abs(t.score - 26.0) < 0.1, f'{t.score:.2f}')
t.update(FREQS, -20.0, False, [30.0, 35.0, 18.0], now=7.0)  # one worse capture
check('smoothing: one bad capture moves the score only part way',
      18.0 < t.score < 25.0, f'{t.score:.2f}')
check('peak hold keeps the best', abs(t.best[FREQS[2]] - 26.0) < 0.1 and abs(t.best_score - 26.0) < 0.1)
m1 = t.mark('dipole 75 cm', {FREQS[0]: 2.0, FREQS[2]: 7.5, 88.1e6: 50.0}, now=7.0)
check('mark keeps the score, weakest and worst multipath of the open stations',
      m1['score'] == t.score and m1['weakest'] == FREQS[2] and m1['multipath'] == 7.5)
for i in range(30):
    t.update(FREQS, -12.0, i == 29, [33.0, 38.0, 29.0], now=7.2 + 0.2 * i)
m2 = t.mark('', now=13.0)
check('unnamed mark gets a number', m2['label'] == 'Mark 2')
check('clip just now: overloaded, marked so', t.overloaded(now=13.0) and m2['overload'])
check(f'overload clears {rm.TUNE_CLIP_S:g} s after the last clip', not t.overloaded(now=13.0 + rm.TUNE_CLIP_S + 0.1))
check('marks ranked best score first', [m['label'] for m in t.ranked()] == ['Mark 2', 'dipole 75 cm'])
t.reset_hold()
check('reset peak hold: best is now', t.best == t.snr and t.best_score == t.score)
state = t.state({FREQS[2]: '100.3 CKXX'}, {FREQS[2]: 3.0}, now=13.0)
check('state names stations and marks', state['stations'][2]['name'] == '100.3 CKXX'
      and state['marks'][0]['weakest'] == '100.3 CKXX' and state['stations'][2]['multipath'] == 3.0)
check('state is JSON for the web page', bool(json.dumps(rm._finite(state))))
check('state stale without fresh readings', t.state(now=20.0)['stale'] and not t.state(now=13.0)['stale'])
t.update(FREQS[:2], -12.0, False, [33.0, 38.0], now=14.0)   # a receiver removed: start again
check('receivers changed: readings and hold restart, marks kept',
      list(t.snr) == FREQS[:2] and t.best_score == 33.0 and len(t.marks) == 2)
for i in range(rm.TUNE_MARKS + 5):
    t.mark(f'm{i}')
check(f'at most {rm.TUNE_MARKS} marks kept', len(t.marks) == rm.TUNE_MARKS)


# --- AntennaLoop on a flowgraph (FmMonitor's tap_iq / untap / detach_sdr / attach_sdr)
print('AntennaLoop')
IQ = band(weak, n=1 << 20)


class Source(gr.hier_block2):
    """The synthetic SDR: the window's IQ, repeated, at the SDR's rate."""

    def __init__(self):
        gr.hier_block2.__init__(self, 'sdr', gr.io_signature(0, 0, 0), gr.io_signature(1, 1, gr.sizeof_gr_complex))
        self.src = blocks.vector_source_c(IQ.tolist(), True)
        self.thr = rm._min_buffer(blocks.throttle(gr.sizeof_gr_complex, rm.SAMP_RATE), rm.SRC_BUFFER)
        self.connect(self.src, self.thr, self)


class Station(gr.hier_block2):
    """A receiver as far as the SDR wiring goes: takes the IQ, has a frequency."""

    def __init__(self, freq_hz):
        gr.hier_block2.__init__(self, 'station', gr.io_signature(1, 1, gr.sizeof_gr_complex), gr.io_signature(0, 0, 0))
        self.freq_hz, self.iboc = freq_hz, None
        self.sink = blocks.null_sink(gr.sizeof_gr_complex)
        self.connect(self, self.sink)


class Tb(gr.top_block):
    """The parts of FmMonitor that antenna tuning uses: a synthetic SDR, receivers that only take its IQ, no audio."""
    tap_iq, untap, detach_sdr, attach_sdr = (rm.FmMonitor.tap_iq, rm.FmMonitor.untap,
                                             rm.FmMonitor.detach_sdr, rm.FmMonitor.attach_sdr)
    stations = rm.FmMonitor.stations

    def __init__(self):
        gr.top_block.__init__(self, 'antenna-test')
        self.center_hz, self.gain = CENTER, (4, 40)
        self._sdr_lock = threading.RLock()
        self._source_factory = Source
        self.src = Source()
        self.adc = rm.AdcMeter()
        self._adc_in = rm._batch(gr.sizeof_gr_complex, rm.ADC_BATCH, 8)
        self.connect(self.src, self._adc_in, self.adc)
        self._taps = []
        self.slots = [Station(f) for f in FREQS]
        for st in self.slots:
            self.connect(self.src, st)


tb = Tb()
tb.start()
loop = rm.AntennaLoop(tb)


def wait_updates(n, timeout=10.0):
    t0 = time.monotonic()
    start = loop.tuner.updates
    while loop.tuner.updates < start + n and time.monotonic() - t0 < timeout:
        time.sleep(0.05)
    return loop.tuner.updates - start


got = wait_updates(5)
check('loop measures (5 in time)', got >= 5, f'{got} updates')
check('loop reading matches window_snrs', loop.tuner.score is not None and abs(loop.tuner.score - min(s1)) < 1.5,
      f'{loop.tuner.score:.1f} vs {min(s1):.1f}')
check('one tap while tuning', len(tb._taps) == 1)
tb.detach_sdr()
tb.attach_sdr()
got = wait_updates(3)
check('tap survives the SDR being reopened', got >= 3, f'{got} updates')
loop.stop()
check('stop removes the tap', tb._taps == [] and not loop.thread.is_alive())

# --- the window's controls and the web page's, on a stub MainWindow (the real methods and AntennaDialog)
print('MainWindow / web')
from PyQt5 import QtWidgets  # noqa: E402

app = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])
MW = rm.MainWindow


class Win(QtWidgets.QWidget):
    antenna_start, antenna_stop, antenna_mark, antenna_reset_hold, _antenna_state, _web_command = (
        MW.antenna_start, MW.antenna_stop, MW.antenna_mark, MW.antenna_reset_hold, MW._antenna_state, MW._web_command)

    def __init__(self):
        super().__init__()
        self.tb, self._cal, self._recovery, self.antenna, self.antenna_dlg = tb, None, None, None, None
        self.logged = []
        self.panels = [type('P', (), {'station': st, 'title': f'{st.freq_hz / 1e6:.1f}', 'readings': {'am_pct': 2.0},
                                      'alarms': type('A', (), {'hold': lambda self: None})()})()
                       for st in tb.slots]

    def log(self, text):
        self.logged.append(text)

    def _update_window(self):
        pass

    def _recalibrate(self):
        self.logged.append('recalibrated')


w = Win()
w._web_command('antenna', {'on': True})
check('web starts tuning, the window opens', w.antenna is not None and w.antenna_dlg is not None
      and w.antenna_dlg.isVisible())
try:
    w._web_command('recalibrate', {})
    check('recalibrate refused while tuning', False)
except ValueError:
    check('recalibrate refused while tuning', 'recalibrated' not in w.logged)
t0 = time.monotonic()
while w.antenna.tuner.updates < 3 and time.monotonic() - t0 < 10:
    time.sleep(0.05)
s = w._antenna_state()
w.antenna_dlg.refresh(s)
check('window shows the score', w.antenna_dlg.score.text().startswith('Score '), w.antenna_dlg.score.text())
w._web_command('antenna_mark', {'label': 'loop NE'})
w.antenna_dlg.refresh(w._antenna_state())
check('web mark lands in the window\'s table', w.antenna_dlg.table.rowCount() == 1
      and w.antenna_dlg.table.item(0, 0).text() == 'loop NE' and w.antenna_dlg.table.item(0, 3).text() == '2.0%')
w.antenna_dlg.close()     # closing the window stops tuning
check('closing the window stops tuning and untaps', w.antenna is None and w.antenna_dlg is None and tb._taps == [])
check('log names the best setting', any("best setting 'loop NE'" in t for t in w.logged), w.logged[-1])
try:
    w._web_command('antenna_mark', {})
    check('mark refused when not tuning', False)
except ValueError:
    check('mark refused when not tuning', True)
tb.stop()
tb.wait()

print('FAILED: ' + ', '.join(bad) if bad else 'all ok')
sys.exit(1 if bad else 0)
