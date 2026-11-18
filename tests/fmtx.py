"""Synthetic FM broadcast transmitter for checking FM-Modmon-ms's measurements.

Builds the MPX at 240 kS/s from known parts (pre-emphasised stereo audio,
pilot, RDS per IEC 62106, SCA subcarriers, DC = carrier offset), then a GNU
Radio flowgraph upsamples it to 9.6 MS/s, FM-modulates (1.0 = 75 kHz), applies
AM and noise, and feeds a real FM-Modmon-ms FmStation.
"""
import datetime
import math

import numpy as np
from scipy import signal as sps

FS = 240000
RDS_RATE = 1187.5

# ---------------------------------------------------------------- RDS encoder (IEC 62106)
POLY = 0x5B9  # x^10 + x^8 + x^7 + x^5 + x^4 + x^3 + 1
OFFSET = {'A': 0x0FC, 'B': 0x198, 'C': 0x168, "C'": 0x350, 'D': 0x1B4}


def crc10(data16):
    reg = data16 << 10
    for bit in range(25, 9, -1):
        if reg & (1 << bit):
            reg ^= POLY << (bit - 10)
    return reg & 0x3FF


def block_bits(data, offset):
    word = (data << 10) | (crc10(data) ^ OFFSET[offset])
    return [(word >> (25 - i)) & 1 for i in range(26)]


def group_bits(a, b, c, d):
    version_b = (b >> 11) & 1
    return block_bits(a, 'A') + block_bits(b, 'B') + block_bits(c, "C'" if version_b else 'C') + block_bits(d, 'D')


def af_code(mhz):
    return int(round((mhz - 87.5) * 10))


def mjd(date):
    return (date - datetime.date(1858, 11, 17)).days


class RdsContent:
    def __init__(self, pi=0xC6B2, pty=6, tp=1, ta=0, ms=1, stereo=1, ps='TESTFM  ', afs=(94.5, 101.7),
                 rt='Now playing Bohemian Rhapsody by Queen', ecc=0xA1, ptyn='CLASSICS',
                 ct=(datetime.date(2026, 11, 16), 12, 34, -10)):
        self.pi, self.pty, self.tp, self.ta, self.ms, self.stereo = pi, pty, tp, ta, ms, stereo
        self.ps, self.afs, self.ecc, self.ptyn, self.ct = ps.ljust(8)[:8], afs, ecc, ptyn.ljust(8)[:8], ct
        self.rt = (rt + '\r').ljust(64)[:64]
        t1 = rt.index('Bohemian Rhapsody')
        a1 = rt.index('Queen')
        self.rtplus = ((1, t1, len('Bohemian Rhapsody') - 1), (4, a1, len('Queen') - 1))  # (type, start, len-1)

    def b_common(self, gtype, version=0):
        return (gtype << 12) | (version << 11) | (self.tp << 10) | (self.pty << 5)

    def groups(self):
        """An endless sequence of (a, b, c, d) groups."""
        af = [224 + len(self.afs)] + [af_code(f) for f in self.afs]
        if len(af) % 2:
            af.append(205)  # filler
        af_pairs = [(af[i] << 8) | af[i + 1] for i in range(0, len(af), 2)]
        di = [0, 0, 0, self.stereo]  # segment 0..3 carry d3 (dynamic PTY), d2, d1, d0 (stereo)
        ps_seg = rt_seg = af_i = ptyn_seg = 0
        n = 0
        while True:
            for kind in ('0A', '2A', '0A', '2A', '0A', '1A', '0A', '2A', '3A', '11A', '10A', '4A'):
                a = self.pi
                if kind == '0A':
                    s = ps_seg
                    b = self.b_common(0) | (self.ta << 4) | (self.ms << 3) | (di[s] << 2) | s
                    c = af_pairs[af_i % len(af_pairs)]
                    af_i += 1
                    d = (ord(self.ps[2 * s]) << 8) | ord(self.ps[2 * s + 1])
                    ps_seg = (ps_seg + 1) % 4
                elif kind == '2A':
                    s = rt_seg
                    b = self.b_common(2) | (0 << 4) | s
                    t = self.rt[4 * s:4 * s + 4]
                    c = (ord(t[0]) << 8) | ord(t[1])
                    d = (ord(t[2]) << 8) | ord(t[3])
                    rt_seg = (rt_seg + 1) % 16
                elif kind == '1A':
                    b = self.b_common(1)
                    c = (0 << 15) | (0 << 12) | self.ecc  # variant 0: ECC
                    d = 0
                elif kind == '3A':
                    b = self.b_common(3) | 0b10110  # application group 11A
                    c = 0
                    d = 0x4BD7
                elif kind == '11A':
                    (t1, s1, l1), (t2, s2, l2) = self.rtplus
                    b = self.b_common(11) | (0 << 4) | (1 << 3) | (t1 >> 3)
                    c = ((t1 & 7) << 13) | (s1 << 7) | (l1 << 1) | (t2 >> 5)
                    d = ((t2 & 0x1F) << 11) | (s2 << 5) | l2
                elif kind == '10A':
                    s = ptyn_seg
                    b = self.b_common(10) | (0 << 4) | s
                    t = self.ptyn[4 * s:4 * s + 4]
                    c = (ord(t[0]) << 8) | ord(t[1])
                    d = (ord(t[2]) << 8) | ord(t[3])
                    ptyn_seg ^= 1
                else:  # 4A clock
                    date, hh, mm, off = self.ct
                    m = mjd(date)
                    b = self.b_common(4) | (m >> 15)
                    c = ((m & 0x7FFF) << 1) | (hh >> 4)
                    d = ((hh & 0xF) << 12) | (mm << 6) | ((1 if off < 0 else 0) << 5) | abs(off)
                yield kind, (a, b, c, d)
                n += 1


def rds_baseband(content, seconds, fs=None):
    """RDS biphase baseband (IEC 62106 shaping), peak |x| = 1, at fs; plus group count and type list."""
    fs = fs or FS
    nbits = int(seconds * RDS_RATE) + 104
    bits, kinds = [], []
    gen = content.groups()
    while len(bits) < nbits:
        kind, g = next(gen)
        kinds.append(kind)
        bits += group_bits(*g)
    bits = np.array(bits[:nbits])
    diff = np.bitwise_xor.accumulate(bits)  # differential coding: e_i = d_i xor e_(i-1)
    sym = 2 * diff - 1.0
    fs0 = RDS_RATE * 192  # 228 kHz: whole samples per bit and half bit
    td = 1 / RDS_RATE
    n = nbits * 192 + 4096
    imp = np.zeros(n)
    idx = np.arange(nbits) * 192 + 1024
    imp[idx] += sym
    imp[idx + 96] -= sym                      # biphase: +impulse, then -impulse half a bit later
    f = np.fft.rfftfreq(n, 1 / fs0)
    shape = np.where(f <= 2 / td, np.cos(np.pi * f * td / 4), 0.0)
    x = np.fft.irfft(np.fft.rfft(imp) * shape, n)
    from fractions import Fraction
    r = Fraction(int(fs), int(fs0))
    x = sps.resample_poly(x, r.numerator, r.denominator)[: int(seconds * fs)]
    return x / np.max(np.abs(x)), kinds


# ---------------------------------------------------------------- MPX
def deemph_response(rm, f, tau=75e-6):
    b, a = rm._deemph_taps(tau)
    _, h = sps.freqz(b, a, worN=[f], fs=rm.AUDIO_RATE)
    return h[0]


def mpx(rm, seconds, left=(), right=(), pilot=0.09, pilot_hz=19000.0, rds=0.0, rds_content=None,
        sca=(), dc_hz=0.0, stereo=True, bursts=(), rds_phase_deg=0.0, rds_hz=None):
    """MPX at FS. left/right: [(freq, amplitude)] tones as they should come out of
    the receiver's de-emphasis (pre-emphasis is applied here, matched to it).
    sca: [(khz, injection, tone_hz, deviation_hz)]. bursts: [(t, ms, factor)]
    scale the whole MPX by factor for ms (over-modulation peaks)."""
    global FS
    FS = int(rm.QUAD_RATE)
    t = np.arange(int(seconds * FS)) / FS
    info = {}

    def channel(tones):
        x = np.zeros_like(t)
        for f, amp in tones:
            h = deemph_response(rm, f)
            x += amp / abs(h) * np.sin(2 * np.pi * f * t - np.angle(h))
        return x

    L, R = channel(left), channel(right)
    m, s = (L + R) / 2, (L - R) / 2
    theta = 2 * np.pi * pilot_hz * t
    x = m + (s * np.sin(2 * theta) if stereo else 0) + pilot * np.sin(theta)
    info['L_tx'], info['R_tx'] = L, R
    if rds:
        bb, kinds = rds_baseband(rds_content or RdsContent(), seconds)
        # Locked to 3x the pilot at rds_phase_deg (0 = in phase, 90 = quadrature),
        # or free-running at rds_hz.
        carrier = 3 * theta if rds_hz is None else 2 * np.pi * rds_hz * t
        x += rds * bb * np.sin(carrier + math.radians(rds_phase_deg))
        info['rds_kinds'] = kinds
    for khz, inj, tone, dev in sca:
        phase = 2 * np.pi * khz * 1e3 * t + dev / tone * np.sin(2 * np.pi * tone * t)
        x += inj * np.cos(phase)
    for t0, ms, factor in bursts:
        i0, i1 = int(t0 * FS), int((t0 + ms / 1000) * FS)
        x[i0:i1] *= factor
    info['mpx_ac'] = x.copy()
    x = x + dc_hz / rm.MAX_DEV
    return x.astype(np.float32), info


def run(rm, mpx_signal, rf_amp=0.1, am=0.0, am_hz=100.0, noise=0.0, offset_hz=1e6, seed=1, echo=None,
        sync_am=None, interferer=None):
    """Feed the MPX through a transmitter and a real FmStation; returns the station.
    sync_am: (a, b) gives the carrier synchronous AM, envelope 1 + a*x + b*(x^2 - mean)
    of the MPX x (as a mistuned RF chain would).
    echo: (delay_s, gain, phase_rad) adds one reflection (two-ray multipath).
    interferer: (mpx, gain, offset_hz) adds a second FM transmitter (its own MPX, as long),
    gain x rf_amp, offset_hz from the wanted carrier (co-channel: a few Hz to kHz)."""
    from gnuradio import analog, blocks, filter, gr
    from gnuradio.filter import firdes
    tb = gr.top_block()
    src = blocks.vector_source_f(mpx_signal.tolist(), False)
    interp = filter.interp_fir_filter_fff(rm.CHAN_DECIM, firdes.low_pass(rm.CHAN_DECIM, rm.SAMP_RATE, 115e3, 20e3))
    mod = analog.frequency_modulator_fc(2 * math.pi * rm.MAX_DEV / rm.SAMP_RATE)
    rot = blocks.rotator_cc(2 * math.pi * offset_hz / rm.SAMP_RATE)
    gain = blocks.multiply_const_cc(rf_amp)
    chain = [src, interp, mod, rot, gain]
    if am:
        env = analog.sig_source_f(rm.SAMP_RATE, analog.GR_SIN_WAVE, am_hz, am, 1.0)
        mul = blocks.multiply_cc()
        tb.connect(env, blocks.float_to_complex(), (mul, 1))
        chain.append(mul)
    if sync_am:
        a, b = sync_am
        xa = mpx_signal - np.mean(mpx_signal)
        q = xa * xa
        env_src = blocks.vector_source_f((1 + a * xa + b * (q - np.mean(q))).astype(np.float32).tolist(), False)
        env_interp = filter.interp_fir_filter_fff(rm.CHAN_DECIM, interp.taps())  # same delay as the MPX
        mul = blocks.multiply_cc()
        tb.connect(env_src, env_interp, blocks.float_to_complex(), (mul, 1))
        chain.append(mul)
    if echo:
        delay_s, g, phase = echo
        add = blocks.add_cc()
        refl = blocks.multiply_const_cc(g * complex(math.cos(phase), math.sin(phase)))
        tb.connect(chain[-1], blocks.delay(gr.sizeof_gr_complex, round(delay_s * rm.SAMP_RATE)), refl, (add, 1))
        chain.append(add)
    if interferer:
        mpx2, g, df = interferer
        add = blocks.add_cc()
        tb.connect(blocks.vector_source_f(np.asarray(mpx2, np.float32).tolist(), False),
                   filter.interp_fir_filter_fff(rm.CHAN_DECIM, interp.taps()),
                   analog.frequency_modulator_fc(2 * math.pi * rm.MAX_DEV / rm.SAMP_RATE),
                   blocks.rotator_cc(2 * math.pi * (offset_hz + df) / rm.SAMP_RATE),
                   blocks.multiply_const_cc(rf_amp * g), (add, 1))
        chain.append(add)
    if noise:
        add = blocks.add_cc()
        tb.connect(analog.noise_source_c(analog.GR_GAUSSIAN, noise, seed), (add, 1))
        chain.append(add)
    st = rm.FmStation(100e6 + offset_hz, 100e6)
    st.set_audio('analog', False)
    tb.connect(*chain)
    tb.connect(chain[-1], st)
    for ch in range(2):
        tb.connect((st, ch), blocks.null_sink(gr.sizeof_float))
    tb.run()
    return st
