"""Band scan and gain calibration against a simulated RSP1A whose ADC clips:
a strong station must not hide the others in its scan window, and calibration
must keep the ADC peaks at CAL_PEAK_DBFS. Exits non-zero on a failure."""
import importlib.util
import os
import sys

import numpy as np

os.environ['QT_QPA_PLATFORM'] = 'offscreen'
spec = importlib.util.spec_from_file_location('fm_modmon', os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'fm-modmon-ms.py'))
rm = importlib.util.module_from_spec(spec)
spec.loader.exec_module(rm)

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

    def tune(self, hz):
        self.center = hz

    def set_gain(self, lna, ifgr):
        self.lna, self.ifgr = lna, min(max(ifgr, 20), 59)

    def capture(self, n):
        n = min(n, 1 << 18)   # (enough for the scan's spectra; keeps the test quick)
        t = np.arange(n) / rm.SAMP_RATE
        lna, if_ = 10 ** (-6 * self.lna / 20), 10 ** (-(self.ifgr - 20) / 20)

        def noise(db):
            return (self.rng.standard_normal(n) + 1j * self.rng.standard_normal(n)) * 10 ** (db / 20) / np.sqrt(2)

        x = noise(self.ant)
        for f, db in self.stations.items():
            if abs(f - self.center) < 4.2e6:   # FM: +/-50 kHz of slowly wandering deviation
                dev = np.convolve(self.rng.standard_normal(n), np.ones(400) / 20, 'same') * 50e3 * self.fm
                x = x + 10 ** (db / 20) * np.exp(1j * (2 * np.pi * (f - self.center) * t
                                                       + 2 * np.pi * np.cumsum(dev) / rm.SAMP_RATE))
        for f, dbc in self.sidebands.items():   # many random-phase tones: flat, noise-like sidebands
            offs = np.concatenate([np.linspace(-199e3, -129e3, 60), np.linspace(129e3, 199e3, 60)])
            a = 10 ** ((self.stations[f] + dbc) / 20) / np.sqrt(len(offs))
            for o, ph in zip(offs, self.rng.uniform(0, 2 * np.pi, len(offs))):
                x = x + a * np.exp(1j * (2 * np.pi * (f + o - self.center) * t + ph))
        x = (x * lna + noise(self.rx)) * if_
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
x = rm._scan_capture(rsp, *rm.CAL_DEFAULT)
peak = 20 * np.log10(np.percentile(np.abs(x), 99.99))
check('scan: a window with a strong station is captured unclipped', np.abs(x).max() < rm.CAL_CLIP,
      f'(LNA {rsp.lna}, IFGR {rsp.ifgr}; peaks {peak:.1f} dBFS)')
check('...within the headroom', peak <= rm.CAL_PEAK_DBFS + rm.SCAN_HEADROOM_DB, f'({peak:.1f} dBFS)')
rsp = FakeRsp(STRONG)
rsp.tune(103e6)
rsp.set_gain(*rm.CAL_DEFAULT)
check('...where the starting gain clips it (what this guards)', np.abs(rsp.capture(1 << 18)).max() >= rm.CAL_CLIP)
found, _ = rm._scan(FakeRsp(STRONG), False, *rm.CAL_DEFAULT)
got = {round(f / 1e5) / 10 for f, _ in found}
check('scan: the stations are found', {94.5, 100.9, 101.7} <= got, sorted(got))

# IBOC: real hybrid sidebands (-10 to -23 dBc) are flagged; a strong analog station's skirts (-40 dBc) aren't.
# (The HD station is a weak one, its sidebands ~10 dB over the floor, as 103.1's were on air: a strong one's
# sidebands read as stations on the channels either side, and it is then marked 'adjacent'.)
_, iboc = rm._scan(FakeRsp({97.5e6: -6.0, 99.1e6: 30.0}, sidebands={97.5e6: -15.0, 99.1e6: -43.0}, fm=False), False,
                   *rm.CAL_DEFAULT)
check('IBOC: -15 dBc sidebands flagged', isinstance(iboc.get(97.5e6), float), iboc)
check('IBOC: -43 dBc (an analog skirt) not flagged', iboc.get(99.1e6) is None, iboc)

rsp = FakeRsp(STRONG)
rsp.tune(rm._centre([94.5e6, 100.9e6, 101.7e6]))
lna, ifgr, report = rm.calibrate_gain(rsp, rsp.center, [94.5e6, 100.9e6, 101.7e6])
rsp.set_gain(lna, ifgr)
peak = 20 * np.log10(np.percentile(np.abs(rsp.capture(1 << 18)), 99.99))
check('calibration: ADC peaks held near CAL_PEAK_DBFS', abs(peak - rm.CAL_PEAK_DBFS) <= 2.0,
      f'({report}; peaks {peak:.1f} dBFS)')

print('\nall ok' if not bad else f'\n{len(bad)} WRONG')
sys.exit(1 if bad else 0)
