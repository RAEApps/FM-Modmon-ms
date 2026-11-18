"""Where the SDR centres for a set of stations: off the RSP1A's DC offset, off
every other station's IQ image, and no station past the IF filter's usable edge."""
import importlib.util
import itertools
import os
import random
import sys

os.environ['QT_QPA_PLATFORM'] = 'offscreen'
spec = importlib.util.spec_from_file_location('fm_modmon', os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'fm-modmon-ms.py'))
rm = importlib.util.module_from_spec(spec)
spec.loader.exec_module(rm)

bad = 0


def problems(freqs, c):
    edge = max(abs(f - c) for f in freqs)
    dc = min(abs(f - c) for f in freqs)
    image = min((abs((2 * c - a) - b) for a, b in itertools.permutations(freqs, 2)), default=float('inf'))
    return [p for p, ok in (('past the edge', edge <= rm.EDGE_HZ + 1),
                            ('carrier near DC', dc >= rm.DC_CLEAR_HZ - 1),
                            ('carrier on an image', image >= rm.IMAGE_CLEAR_HZ - 1)) if not ok], (edge, dc, image)


def check(freqs_mhz):
    """Fails only if a clean centre exists (5 kHz search) and _centre didn't find one;
    some full-span sets of four have none, and then the best compromise stands."""
    global bad
    freqs = [f * 1e6 for f in freqs_mhz]
    c = rm._centre(freqs)
    found, (edge, dc, image) = problems(freqs, c)
    mid = (min(freqs) + max(freqs)) / 2
    possible = any(not problems(freqs, mid + k * 5e3)[0] for k in range(-int(rm.EDGE_HZ / 5e3), int(rm.EDGE_HZ / 5e3) + 1))
    if found and (possible or 'past the edge' in found):
        bad += 1
        print(f'{freqs_mhz}: centre {c / 1e6:.3f} MHz, {", ".join(found)} '
              f'(edge {edge / 1e3:.0f}, DC {dc / 1e3:.0f}, image {image / 1e3:.0f} kHz)')
    return c


# A lone station is moved off DC, by no more than it needs.
c = check([101.7])
if abs(c - 101.7e6) != rm.DC_CLEAR_HZ:
    bad += 1
    print(f'lone station: centre {c / 1e6:.3f} MHz, expected {rm.DC_CLEAR_HZ / 1e3:.0f} kHz off it')
# The widest pair and the three stations these were found on.
check([94.5, 101.7])
check([94.5, 100.9, 101.7])
# Random sets of up to four stations on the North American grid that fit MAX_SPAN.
grid = [round(87.9 + 0.2 * i, 1) for i in range(101)]
rnd = random.Random(1)
for _ in range(20000):
    lo = rnd.choice(grid)
    window = [f for f in grid if lo <= f <= lo + rm.MAX_SPAN / 1e6 + 1e-6]
    check(sorted(rnd.sample(window, min(rnd.randint(1, rm.MAX_RECEIVERS), len(window)))))

print('all as expected' if not bad else f'{bad} unexpected')
sys.exit(1 if bad else 0)
