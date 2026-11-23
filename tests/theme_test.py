"""The visual system: every colour in the window and the web page comes from THEME
(the palette), type sizes from TYPE, corners from RADIUS; no emoji; and the text
colours keep their contrast. No SDR needed. Exits non-zero on a failure."""
import os
import re
import sys

os.environ['QT_QPA_PLATFORM'] = 'offscreen'
sys.stdout.reconfigure(encoding='utf-8')
here = os.path.dirname(os.path.abspath(__file__))
from loadapp import load_app  # noqa: E402
rm = load_app()

bad = []


def check(name, ok, detail=''):
    print(f"{'ok   ' if ok else 'WRONG'} {name} {detail if not ok else ''}")
    if not ok:
        bad.append(name)


palette = {v.lower() for v in rm.THEME.values()}
src = open(os.path.join(here, '..', 'fm-modmon-ms.py'), encoding='utf-8').read().split('\n')
gui = next(i for i, l in enumerate(src) if l.startswith('# --------------------------------------------------------------------------- GUI'))
icon = next(i for i, l in enumerate(src) if l.startswith('def draw_icon('))
icon_end = next(i for i in range(icon + 1, len(src)) if src[i].startswith('def '))   # (the app icon: its own art)
theme = (next(i for i, l in enumerate(src) if l.startswith('def _mix(')),
         next(i for i, l in enumerate(src) if l.startswith('# Type: four sizes')))
HEX = re.compile(r'#[0-9a-fA-F]{6}\b')
off = [(i + 1, h) for i, l in enumerate(src) if i >= gui and not icon <= i < icon_end and not theme[0] <= i < theme[1]
       for h in HEX.findall(l) if h.lower() not in palette]
check('window: every colour is in the palette', not off, off[:10])
web = open(os.path.join(here, '..', 'fm-modmon-ms-web.html'), encoding='utf-8').read()
off = sorted({h for h in HEX.findall(web) if h.lower() not in palette})
check('web page: every colour is in the palette', not off, off)
short = re.findall(r'(?:color|background|border[\w-]*|fill|stroke):\s*[^;{}]*?(#[0-9a-fA-F]{3})\b(?![\w-])', web)
check('web page: no short #rgb colours (they bypass the palette check)', not short, short)
root = dict(re.findall(r'--([\w-]+):\s*(#[0-9a-fA-F]{6})', web[web.index(':root'):web.index('}', web.index(':root'))]))
check('web page: its colour variables are palette colours', all(v.lower() in palette for v in root.values()), root)

qss = rm.app_qss('a.png', 't.png')
check('stylesheet: every placeholder filled', not re.findall(r'%\w+%', qss), re.findall(r'%\w+%', qss))
gui_src = '\n'.join(src[gui:])
sizes = set(re.findall(r'font-size:\s*([\d.]+pt)', gui_src + qss))
check('window: type sizes from the scale', sizes <= set(rm.TYPE.values()), sorted(sizes))
radii = set(re.findall(r'border-radius:\s*([\d.]+px)', qss + gui_src)) - {'%radius%'}
check('window: corners 2-3 px (radio buttons stay round)', radii <= {rm.RADIUS, '2px', '9px'}, sorted(radii))
css = web[:web.index('</style>')]
wsizes = {s for line in css.split('\n') if '.lamp' not in line
          for s in re.findall(r'(?:font-size:\s*|font:\s*(?:\d{3}\s+|bold\s+)?)([\d.]+px)', line)}
check('web page: type sizes from the scale', wsizes <= {'11px', '13px', '16px', '20px'}, sorted(wsizes))
wradii = set(re.findall(r'border-radius:\s*([\d.]+(?:px|%))', css))
check('web page: corners 2-3 px', wradii <= {'3px', '2px', '1.5px', '9px', '0'}, sorted(wradii))

EMOJI = re.compile('[\U0001F300-\U0001FAFF☀-⛿✀-➿⧉↩⟲]')
for name, text in (('window', '\n'.join(src[gui:icon] + src[icon_end:])), ('web page', web)):
    found = sorted({c for c in EMOJI.findall(text) if c not in '✓✕⚙▶■'})
    check(f'{name}: no emoji or pictographs', not found, found)
    # (✓ ✕ and ▶ ■ are plain symbols; ⚙ only with the text-style selector)
    check(f'{name}: ⚙ only as a text symbol', all(m.group(1) for m in re.finditer(r'⚙(︎|\\ufe0e|\\uFE0E)?', text)
                                                  if not text[m.start() - 5:m.start()].endswith('\\u')))


def luminance(h):
    c = [int(h[i:i + 2], 16) / 255 for i in (1, 3, 5)]
    c = [x / 12.92 if x <= 0.03928 else ((x + 0.055) / 1.055) ** 2.4 for x in c]
    return 0.2126 * c[0] + 0.7152 * c[1] + 0.0722 * c[2]


def contrast(a, b):
    la, lb = sorted((luminance(a), luminance(b)), reverse=True)
    return (la + 0.05) / (lb + 0.05)


T = rm.THEME
rows = ('window', 'panel', 'accent_tint', 'p1_tint')   # (a selected row, a row with an alarm waiting)
for fg, need, on in (('label', 4.5, rows), ('text', 4.5, rows), ('bright', 4.5, rows), ('accent', 4.5, rows),
                     ('amber', 4.5, rows), ('p1', 4.5, rows), ('p2', 4.5, rows), ('p3', 4.5, rows),
                     ('outline', 3.0, ('window', 'panel'))):   # (control outlines: on the window and cards)
    worst = min(contrast(T[fg], T[bg]) for bg in on)
    check(f'contrast: {fg} on the backgrounds {worst:.1f}:1 (needs {need})', worst >= need, f'{worst:.2f}')
check('contrast: ink on the priority fills', min(contrast(T['ink'], T[p]) for p in ('p1', 'p2', 'p3')) >= 4.5)
check('palette: a dozen-odd base colours, plus their tints',
      len([k for k in T if not k.endswith(('_tint', '_line'))]) <= 22, len(T))

print('\nall ok' if not bad else f'\n{len(bad)} WRONG')
sys.exit(1 if bad else 0)
