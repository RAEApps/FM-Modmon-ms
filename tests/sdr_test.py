"""Each SDR profile (SDRS): its rate, window and scan fit together, the command
line and settings pick it, and a synthetic station through a real FmStation at
its sample rate reads right. Exits non-zero on a failure."""
import importlib.util
import os
import random
import sys

os.environ['QT_QPA_PLATFORM'] = 'offscreen'
sys.stdout.reconfigure(encoding='utf-8')
spec = importlib.util.spec_from_file_location('fm_modmon', os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'fm-modmon-ms.py'))
rm = importlib.util.module_from_spec(spec)
spec.loader.exec_module(rm)

import fmtx  # noqa: E402

bad = []


def check(name, ok, detail=''):
    print(f"{'ok   ' if ok else 'WRONG'} {name} {detail}")
    if not ok:
        bad.append(name)


rng = random.Random(1)
x, info = fmtx.mpx(rm, 6.0, left=[(997, 0.40)], right=[(1600, 0.30)], pilot=0.09, rds=0.04, dc_hz=500)
for key, p in rm.SDRS.items():
    rm.use_sdr(key)
    n = p.name
    check(f'{n}: rate is a whole multiple of the station rate', rm.CHAN_DECIM * rm.QUAD_RATE == rm.SAMP_RATE,
          f'({rm.SAMP_RATE / 1e6:g} MS/s / {rm.CHAN_DECIM})')
    check(f'{n}: source buffer holds a channel chunk', rm.SRC_BUFFER > rm.CHAN_CHUNK * rm.CHAN_DECIM)
    check(f'{n}: a station at the window edge stays inside Nyquist',
          rm.EDGE_HZ + rm.CHAN_PASS_HZ + 35e3 < rm.SAMP_RATE / 2,
          f'(edge {rm.EDGE_HZ / 1e6:.2f} MHz, Nyquist {rm.SAMP_RATE / 2e6:.2f})')
    covered = all(any(abs(ch * 1e5 - c) <= rm.SCAN_HALF_WIDTH for c in rm.SCAN_CENTERS) for ch in rm.CHANNELS_MHZ10)
    check(f'{n}: the scan windows cover 88.1-107.9 MHz', covered)
    check(f'{n}: scan windows on even tenths (DC off every channel)',
          all(round(c / 1e5) % 2 == 0 and abs(c / 1e5 - round(c / 1e5)) < 1e-6 for c in rm.SCAN_CENTERS))
    check(f'{n}: a scanned channel\'s IBOC sidebands stay inside Nyquist',
          rm.SCAN_HALF_WIDTH + 199e3 < rm.SAMP_RATE / 2)
    # Random station sets that fit the window: the centre keeps them all inside it.
    grid = [ch / 10 for ch in rm.CHANNELS_MHZ10]
    worst = 0.0
    for _ in range(300):
        lo = rng.choice(grid)
        window = [f for f in grid if lo <= f <= lo + rm.MAX_SPAN / 1e6 + 1e-6]
        freqs = [f * 1e6 for f in rng.sample(window, min(len(window), rng.randint(1, 4)))]
        c = rm._centre(freqs)
        worst = max(worst, max(abs(f - c) for f in freqs))
    check(f'{n}: stations that fit stay within EDGE_HZ of the centre', worst <= rm.EDGE_HZ + 1,
          f'(farthest {worst / 1e6:.3f} MHz)')
    two = len(p.stages) == 2
    check(f'{n}: default gain within range', p.clamp(p.default_gain) == tuple(p.default_gain))
    check(f'{n}: gain text', p.gain_text(p.default_gain) == ('LNA 4 · IFGR 40 dB' if two else
                                                             f'Gain {p.default_gain[0]:g} dB'),
          p.gain_text(p.default_gain))
    less, g = 0, p.default_gain
    while g is not None and less < 50:
        g, less = rm._less_gain(g, 6), less + 1
    check(f'{n}: the scan can always back the gain off to the least', less < 50, f'({less} steps)')

    # A station near the window's edge through the transmitter and a real FmStation at this rate.
    st = fmtx.run(rm, x, rf_amp=0.1, noise=0.0005, offset_hz=rm.EDGE_HZ - 100e3)
    s = st.meter.stats
    check(f'{n}: RF level', abs(s['rf_dbfs'] - -20.0) <= 0.3, f"({s['rf_dbfs']:.2f} dBFS)")
    check(f'{n}: carrier offset', abs(s['offset_hz'] - 500) <= 5, f"({s['offset_hz']:.1f} Hz)")
    check(f'{n}: pilot', abs(s['pilot_pct'] - 9.0) <= 0.1, f"({s['pilot_pct']:.2f} %)")
    check(f'{n}: RDS injection', abs(s['rds_pct'] - 4.0) <= 0.1, f"({s['rds_pct']:.2f} %)")
    check(f'{n}: stereo decoded', st.stereo)
    check(f'{n}: no AM', abs(s['am_pct']) <= 0.3, f"({s['am_pct']:.2f} %)")

# The command line and the settings pick the SDR; each takes its own gain options.
for argv, app_sdr, sdr, gain in ((['--no-scan'], 'rsp1a', 'rsp1a', (4, 40)),
                                 (['--no-scan'], 'b210', 'b210', (40,)),
                                 (['--no-scan', '--sdr', 'rtlsdr', '--gain', '20'], 'rsp1a', 'rtlsdr', (20.0,)),
                                 (['--no-scan', '--sdr', 'rsp1b', '--lna', '2'], 'rtlsdr', 'rsp1b', (2, 40))):
    a = rm.resolve_args(rm.parse_args(argv), rm.AppConfig(sdr=app_sdr))
    check(f'{" ".join(argv)} with Setup on {app_sdr}', (a.sdr, tuple(a.gain), rm.SDR.key) == (sdr, gain, sdr),
          (a.sdr, a.gain))
for argv in (['--sdr', 'rtlsdr', '--lna', '2'], ['--sdr', 'rsp1a', '--gain', '20'],
             ['--sdr', 'rtlsdr', '--freqs', '94.5', '101.7']):
    try:
        rm.resolve_args(rm.parse_args(argv), rm.AppConfig())
        check(f'{" ".join(argv)} refused', False)
    except SystemExit:
        check(f'{" ".join(argv)} refused', True)
a = rm.resolve_args(rm.parse_args(['--no-scan', '--sdr', 'b210', '--freqs', '88.1', '107.9']), rm.AppConfig())
c = rm._centre([88.1e6, 107.9e6])
check('B210: the band\'s two end channels open together', max(abs(88.1e6 - c), abs(107.9e6 - c)) <= rm.EDGE_HZ,
      f'(centre {c / 1e6:.3f} MHz)')
check('B210: the scan is one window', len(rm.SCAN_CENTERS) == 1)
check('settings keep the SDR', rm.AppConfig.from_dict(rm.AppConfig(sdr='b210').to_dict()).sdr == 'b210')
check('an unknown SDR in the settings falls back to automatic', rm.AppConfig.from_dict({'sdr': 'nope'}).sdr == 'auto')
check('automatic by default', rm.AppConfig().sdr == 'auto')

# Saved receivers that don't fit a narrower SDR's window: the first that fit open.
rm.use_sdr('rtlsdr')
a = rm.parse_args(['--no-scan'])
a.sdr, a.gain = 'rtlsdr', (30,)
_, receivers, _ = rm.choose_stations(a, {0: (94.5e6, None), 1: (100.9e6, None), 2: (94.9e6, None)})
check('RTL-SDR: saved receivers that don\'t fit are left closed', receivers == {0: 94.5e6, 2: 94.9e6}, receivers)
rm.use_sdr('rsp1a')

# Detection: what each SoapySDR driver's enumerate() reports, and which profile that is.
B210 = {'driver': 'uhd', 'label': 'B210 209012', 'name': 'MyB210', 'product': 'B210', 'serial': '209012', 'type': 'b200'}
RSP1A = {'driver': 'sdrplay', 'label': 'SDRplay Dev0 RSP1A 1807078093', 'serial': '1807078093'}
RSP1B = {'driver': 'sdrplay', 'label': 'SDRplay Dev0 RSP1B 2304012345', 'serial': '2304012345'}
RSPDX = {'driver': 'sdrplay', 'label': 'SDRplay Dev0 RSPdx 2201012345', 'serial': '2201012345'}
RTL = {'driver': 'rtlsdr', 'label': 'Generic RTL2832U OEM :: 00000001', 'serial': '00000001',
       'tuner': 'Rafael Micro R820T'}
X310 = {'driver': 'uhd', 'label': 'X310', 'type': 'x300', 'serial': '31AB'}
for found, key in ((B210, 'b210'), (RSP1A, 'rsp1a'), (RSP1B, 'rsp1b'), (RTL, 'rtlsdr'), (RSPDX, None), (X310, None)):
    check(f'detect: {found["label"]} -> {key}', rm._profile_for(found) == key, rm._profile_for(found))


def found_list(*records):
    return sorted([(rm._profile_for(r), r['serial'], r['label']) for r in records], key=lambda f: -rm.SDRS[f[0]].span)


both = found_list(RSP1A, B210, RTL)
check('detect: the widest window first', [k for k, _, _ in both] == ['b210', 'rsp1a', 'rtlsdr'], both)
check('auto: the widest attached', rm.choose_sdr('auto', both)[:2] == ('b210', '209012'))
check('auto: an RTL-SDR alone', rm.choose_sdr('auto', found_list(RTL))[0] == 'rtlsdr')
check('Setup\'s choice when attached', rm.choose_sdr('rsp1a', both)[:2] == ('rsp1a', '1807078093'))
key, _, _, note = rm.choose_sdr('rsp1b', found_list(RTL))
check('Setup\'s choice not attached: whichever is, with a note', key == 'rtlsdr' and 'RSP1B' in note, note)
for name, wanted, found, required in (('nothing attached', 'auto', [], False),
                                      ('--sdr not attached', 'b210', found_list(RTL), True)):
    try:
        rm.choose_sdr(wanted, found, required)
        check(f'{name}: refused', False)
    except rm.SdrNotFound as e:
        check(f'{name}: refused', True, f'({e})')

# The one found is the one opened: its serial goes into the device arguments.
rm.use_sdr('b210', '209012')
check('the serial found is opened', rm.SDR.device.endswith(',serial=209012') and rm.SAMP_RATE == 30.72e6,
      rm.SDR.device)
rm.use_sdr('rsp1a')
check('...and not kept for the next one', 'serial' not in rm.SDR.device)

# Automatic: the options wait for the detected SDR; --lna on an RTL-SDR found is refused then.
a = rm.resolve_args(rm.parse_args(['--no-scan']), rm.AppConfig())
check('auto: no SDR chosen before detection', a.sdr == 'auto' and a.gain is None and not a.sdr_required)
rm.configure_sdr(a, 'rtlsdr', '00000001')
check('auto: the RTL-SDR found sets the window and gain', (rm.MAX_SPAN, a.gain) == (1.4e6, (30,)))
a = rm.resolve_args(rm.parse_args(['--no-scan', '--lna', '2']), rm.AppConfig())
try:
    rm.configure_sdr(a, 'rtlsdr', '', lambda text: (_ for _ in ()).throw(ValueError(text)))
    check('auto: --lna on the RTL-SDR found refused', False)
except ValueError as e:
    check('auto: --lna on the RTL-SDR found refused', True, f'({e})')
rm.use_sdr('rsp1a')

print('\nall ok' if not bad else f'\n{len(bad)} WRONG')
sys.exit(1 if bad else 0)
