"""Band scan and gain calibration against a simulated RSP1A whose ADC clips:
a strong station must not hide the others in its scan window, and calibration
must keep the ADC peaks at CAL_PEAK_DBFS. Exits non-zero on a failure."""
import os
import sys

import numpy as np

os.environ['QT_QPA_PLATFORM'] = 'offscreen'
from loadapp import load_app  # noqa: E402
rm = load_app()

bad = []


def check(name, ok, detail=''):
    print(f"{'ok   ' if ok else 'WRONG'} {name} {detail}")
    if not ok:
        bad.append(name)


class FakeRsp:
    """Carriers (dB re full scale at LNA 0 / IFGR 20) plus antenna noise, through an LNA
    (6 dB a state), receiver noise, IF gain (1 dB a dB) and an ADC that clips at full scale."""

    def __init__(self, stations_db, antenna_noise_db=-20.0, rx_noise_db=-35.0, sidebands=None, fm=True):
        self.stations = stations_db
        self.fm = fm
        self.sidebands = sidebands or {}   # freq -> dBc of IBOC-like sidebands 129-199 kHz either side
        self.ant, self.rx = antenna_noise_db, rx_noise_db
        self.center = 98e6
        self.lna, self.ifgr = 4, 40
        self.rng = np.random.default_rng(1)
        self.adc_noise_db = None   # the ADC's own noise (dBFS), when it matters

    def tune(self, hz):
        self.center = hz

    def set_gain(self, lna, ifgr):
        self.lna, self.ifgr = lna, min(max(ifgr, 20), 59)

    def gains(self):
        """(ahead of the receiver noise, after it), linear"""
        return 10 ** (-6 * self.lna / 20), 10 ** (-(self.ifgr - 20) / 20)

    def capture(self, n):
        n = min(n, 1 << 18)   # (enough for the scan's spectra; keeps the test quick)
        t = np.arange(n) / rm.SAMP_RATE
        lna, if_ = self.gains()

        def noise(db):
            return (self.rng.standard_normal(n) + 1j * self.rng.standard_normal(n)) * 10 ** (db / 20) / np.sqrt(2)

        x = noise(self.ant)
        for f, db in self.stations.items():
            if abs(f - self.center) < 0.44 * rm.SAMP_RATE:   # FM: +/-50 kHz of slowly wandering deviation
                dev = np.convolve(self.rng.standard_normal(n), np.ones(400) / 20, 'same') * 50e3 * self.fm
                x = x + 10 ** (db / 20) * np.exp(1j * (2 * np.pi * (f - self.center) * t
                                                       + 2 * np.pi * np.cumsum(dev) / rm.SAMP_RATE))
        for f, dbc in self.sidebands.items():   # many random-phase tones: flat, noise-like sidebands
            offs = np.concatenate([np.linspace(-199e3, -129e3, 60), np.linspace(129e3, 199e3, 60)])
            a = 10 ** ((self.stations[f] + dbc) / 20) / np.sqrt(len(offs))
            for o, ph in zip(offs, self.rng.uniform(0, 2 * np.pi, len(offs))):
                x = x + a * np.exp(1j * (2 * np.pi * (f + o - self.center) * t + ph))
        x = (x * lna + noise(self.rx)) * if_
        if self.adc_noise_db is not None:
            x = x + noise(self.adc_noise_db)
        mag = np.abs(x)
        return (x / np.maximum(mag, 1.0)).astype(np.complex64)   # the ADC clips


# A strong local station (as a big outdoor antenna gives) beside weaker ones in the same window
# (dB re full scale at LNA 0 / IFGR 20: at the scan's starting gain 101.7 is ~6 dB over full scale,
# as the RSP1A measured it; 100.9 17 dB below it, as measured)
STRONG = {101.7e6: 50.0, 100.9e6: 33.0, 102.3e6: 15.0, 104.9e6: 15.0, 94.5e6: 42.0, 91.5e6: 15.0}

# The scan backs a window's gain off until its capture is clean. (On the RSP1A with an outdoor
# antenna, the clipped 100-106 MHz window lost 100.9 and every station from 102 to 106 MHz.)
rsp = FakeRsp(STRONG)
rsp.tune(103e6)
x = rm._scan_capture(rsp, rm.SDR.default_gain)
peak = 20 * np.log10(np.percentile(np.abs(x), 99.99))
check('scan: a window with a strong station is captured unclipped', np.abs(x).max() < rm.CAL_CLIP,
      f'(LNA {rsp.lna}, IFGR {rsp.ifgr}; peaks {peak:.1f} dBFS)')
check('...within the headroom', peak <= rm.CAL_PEAK_DBFS + rm.SCAN_HEADROOM_DB, f'({peak:.1f} dBFS)')
rsp = FakeRsp(STRONG)
rsp.tune(103e6)
rsp.set_gain(*rm.SDR.default_gain)
check('...where the starting gain clips it (what this guards)', np.abs(rsp.capture(1 << 18)).max() >= rm.CAL_CLIP)
found, _ = rm._scan(FakeRsp(STRONG), False)
got = {round(f / 1e5) / 10 for f, _ in found}
check('scan: the stations are found', {94.5, 100.9, 101.7} <= got, sorted(got))

# IBOC: real hybrid sidebands (-10 to -23 dBc) are flagged; a strong analog station's skirts (-40 dBc) aren't.
# (The HD station is a weak one, its sidebands ~10 dB over the floor, as 103.1's were on air: a strong one's
# sidebands read as stations on the channels either side, and it is then marked 'adjacent'.)
_, iboc = rm._scan(FakeRsp({97.5e6: -6.0, 99.1e6: 30.0}, sidebands={97.5e6: -15.0, 99.1e6: -43.0}, fm=False), False,
                   rm.SDR.default_gain)
check('IBOC: -15 dBc sidebands flagged', isinstance(iboc.get(97.5e6), float), iboc)
check('IBOC: -43 dBc (an analog skirt) not flagged', iboc.get(99.1e6) is None, iboc)

rsp = FakeRsp(STRONG)
rsp.tune(rm._centre([94.5e6, 100.9e6, 101.7e6]))
(lna, ifgr), report = rm.calibrate_gain(rsp, rsp.center, [94.5e6, 100.9e6, 101.7e6])
rsp.set_gain(lna, ifgr)
peak = 20 * np.log10(np.percentile(np.abs(rsp.capture(1 << 18)), 99.99))
check('calibration: ADC peaks held near CAL_PEAK_DBFS', abs(peak - rm.CAL_PEAK_DBFS) <= 2.0,
      f'({report}; peaks {peak:.1f} dBFS)')



class FakeOneStage(FakeRsp):
    """The same antenna through one gain control in dB (an RTL-SDR or B210: 0 dB is
    70 dB below the reference), and an 8-bit ADC whose noise sits at -45 dBFS, so
    too little gain costs S/N and too much clips."""

    def __init__(self, *a, **k):
        super().__init__(*a, **k)
        self.g = 30
        self.adc_noise_db = -45.0

    def set_gain(self, g):
        self.g = min(max(g, 0), 49.6)

    def gains(self):
        return 1.0, 10 ** ((self.g - 70) / 20)


rm.use_sdr('rtlsdr')
rsp = FakeOneStage(STRONG)
rsp.tune(101.3e6)
x = rm._scan_capture(rsp, (45,))
check('one gain stage: the scan backs a clipping window off', np.abs(x).max() < rm.CAL_CLIP, f'(gain {rsp.g:g} dB)')
found, _ = rm._scan(FakeOneStage(STRONG), False)
got = {round(f / 1e5) / 10 for f, _ in found}
check('one gain stage: the scan finds the stations', {94.5, 100.9, 101.7} <= got, sorted(got))
rsp = FakeOneStage(STRONG)
freqs = [100.9e6, 101.7e6]
rsp.tune(rm._centre(freqs))
(g,), report = rm.calibrate_gain(rsp, rsp.center, freqs)
rsp.set_gain(g)
peak = 20 * np.log10(np.percentile(np.abs(rsp.capture(1 << 18)), 99.99))
check('one gain stage: calibration brings the peaks up to CAL_PEAK_DBFS without passing it',
      rm.CAL_PEAK_DBFS - rm.CAL_STEP_DB - rm.CAL_TOLERANCE_DB - 0.5 <= peak <= rm.CAL_PEAK_DBFS + 2.0,
      f'({report}; peaks {peak:.1f} dBFS)')
rm.use_sdr('rsp1a')

print('\nall ok' if not bad else f'\n{len(bad)} WRONG')
sys.exit(1 if bad else 0)
