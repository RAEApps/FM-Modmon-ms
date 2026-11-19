"""First-run setup: secrets, config sections, the wizard, the web login with a hash."""
import importlib.util, json, os, socket, sys, tempfile, urllib.request
os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
sys.stdout.reconfigure(encoding='utf-8')
APP = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'fm-modmon-ms.py')
spec = importlib.util.spec_from_file_location('fm', APP); m = importlib.util.module_from_spec(spec); spec.loader.exec_module(m)
from PyQt5 import QtCore, QtWidgets
app = QtWidgets.QApplication([])
m.apply_dark_theme(app)
OUT = tempfile.mkdtemp(prefix='fm-modmon-ms_setup_')   # screenshots
bad = []
def check(name, ok):
    print(('ok    ' if ok else 'WRONG ') + name)
    if not ok: bad.append(name)

# --- password hash
h = m.hash_password('correct horse')
check('hash verifies', m.verify_password('correct horse', h))
check('wrong password rejected', not m.verify_password('correct hors', h))
check('garbage hash rejected', not m.verify_password('x', 'nonsense') and not m.verify_password('x', ''))
check('hash has no plaintext', 'correct' not in h)

# --- credential manager (a test target, not the real one)
T = 'FM-Modmon-ms/selftest'
m.credential_write(T, 'pässwörd-✓', 'me')
check('credential round trip', m.credential_read(T) == 'pässwörd-✓')
m.credential_write(T, '')
check('credential deleted', m.credential_read(T) is None)
m.credential_delete(T)   # deleting nothing is fine

# --- config sections preserved
cfg = os.path.join(tempfile.mkdtemp(), 'c.json')
json.dump({'version': 1, 'receivers': [{'receiver': 1, 'freq_mhz': 101.7, 'settings': {}}], 'notify': {'email': True}}, open(cfg, 'w'))
m.save_config(cfg, None, None, m.AppConfig(setup_done=True, country='US', web_password_hash=h))
d = json.load(open(cfg))
check('save app keeps receivers + notify', d['receivers'][0]['freq_mhz'] == 101.7 and d['notify'] == {'email': True})
check('load_app reads it', m.load_app(cfg).country == 'US' and m.load_app(cfg).setup_done)
check('no plaintext in config', 'correct horse' not in open(cfg).read())
check('AppConfig clamps junk', m.AppConfig.from_dict({'country': 'xyz', 'web_port': 80, 'setup_done': 1}) ==
      m.AppConfig(setup_done=True))

# --- resolve_args: CLI wins, else the app config
a = m.resolve_args(m.parse_args(['--no-scan']), m.AppConfig(country='US', web_port=9000, web_bind='127.0.0.1'))
check('app config fills args', (a.country, a.web_port, a.web_bind) == ('US', 9000, '127.0.0.1'))
a = m.resolve_args(m.parse_args(['--no-scan', '--country', 'ca', '--web-port', '0']), m.AppConfig(country='US', web_port=9000))
check('command line wins', (a.country, a.web_port) == ('CA', 0))

# --- the wizard: pages, validation, results
notifier = m.Notifier(m.NotifySettings(), lambda: ('host', None))
w = m.SetupWizard(None, m.AppConfig(), m.NotifySettings(), notifier, first_run=True)
w.show()
for i, pid in enumerate(w.pageIds()):
    w.setCurrentId(pid) if hasattr(w, 'setCurrentId') else None
shots = []
w.restart()
def shot(n):
    app.processEvents(); p = os.path.join(OUT, f'wiz_{n}.png'); w.grab().save(p); shots.append(p)
shot(0); w.next(); shot(1)
check('Canada preselected', w.country() == 'CA')
w.country_other.setChecked(True); w.country_code.setText('g')
check('bad country blocked', w._check_country() is not None)
w.country_code.setText('gb'); check('GB accepted', w._check_country() is None and w.country() == 'GB')
w.next(); shot(2)
w.web_pw.setText('short'); w.web_pw2.setText('short')
check('short password blocked', w._check_web() is not None)
w.web_pw.setText('longenough1'); w.web_pw2.setText('longenough2')
check('mismatch blocked', w._check_web() is not None)
w.web_pw2.setText('longenough1'); check('good password ok', w._check_web() is None)
w.next(); shot(3)
f = w.notify_form
f.mail.setChecked(True); f.smtp_host.setText('smtp.example.org'); f.email_to.setText('ops@example.org'); f.smtp_user.setText('bot@example.org')
check('email without password blocked', any('password' in p for p in f.problems()) or bool(os.environ.get('FM_MODMON_SMTP_PASSWORD')) or m.credential_read(m.SMTP_CREDENTIAL))
f.smtp_password.setText('smtp-secret')
check('email with typed password ok', f.problems() == [])
f.mail.setChecked(False)
w.next(); shot(4)
check('on the last page', w.currentId() == w.pageIds()[-1])
res = w.app_config()
check('wizard result', res.setup_done and res.country == 'GB' and res.web_port == m.WEB_PORT and res.web_bind == '0.0.0.0'
      and m.verify_password('longenough1', res.web_password_hash))
w.web_on.setChecked(False); w.web_local.setChecked(True)
res = w.app_config(); check('web off -> port 0, local', res.web_port == 0 and res.web_bind == '127.0.0.1')
w.close()

# re-run with a password already set: remove it
w2 = m.SetupWizard(None, m.AppConfig(setup_done=True, web_password_hash=h), m.NotifySettings(), notifier, first_run=False)
check('existing password kept when blank', w2.app_config().web_password_hash == h)
w2.web_pw_remove.setChecked(True); check('remove password', w2.app_config().web_password_hash == '')

# --- web login against the hash
def free_port():
    with socket.socket() as sock:
        sock.bind(('127.0.0.1', 0))
        return sock.getsockname()[1]


PORT = free_port()   # (not a fixed one: another program may hold it)
web = m.WebView('127.0.0.1', PORT, None, h)
def post(path, body, extra=None):
    req = urllib.request.Request(f'http://127.0.0.1:{PORT}{path}', data=json.dumps(body).encode(), method='POST',
                                 headers={'X-FM-Modmon': '1', **(extra or {})})
    try:
        with urllib.request.urlopen(req) as r: return r.status, json.loads(r.read())
    except urllib.error.HTTPError as e: return e.code, json.loads(e.read())
st = json.loads(urllib.request.urlopen(f'http://127.0.0.1:{PORT}/state.json').read())
check('web reports a password', st['access']['password'] is True)
check('wrong web password 403', post('/api/login', {'password': 'nope'})[0] == 403)
code, body = post('/api/login', {'password': 'correct horse'})
check('right web password signs in', code == 200 and body.get('token'))
web.set_password_hash(m.hash_password('another one'))
check('new password ends sessions', not web.sessions)
try:  # (a second server on a port in use answered half the requests: this test was flaky beside another run)
    m.WebView('127.0.0.1', PORT, None, h); taken = False
except OSError:
    taken = True
check('web port already in use fails to open', taken)
web2 = m.WebView('127.0.0.1', free_port(), 'cli-pass', h)
check('--web-password wins over the hash', web2.check_password('cli-pass') and not web2.check_password('correct horse'))

# --- settings dialog has the setup button
dlg = m.AppSettingsDialog(None, m.NotifySettings(), notifier)
QtCore.QTimer.singleShot(0, lambda: [b for b in dlg.findChildren(QtWidgets.QPushButton) if 'setup' in b.text()][0].click())
check('Run setup again returns RUN_SETUP', dlg.exec_() == m.AppSettingsDialog.RUN_SETUP)
dlg.show(); app.processEvents(); dlg.grab().save(os.path.join(OUT, 'settings_dialog.png'))

print('\nscreenshots:', *shots)
print('\nall ok' if not bad else f'\n{len(bad)} WRONG')
sys.exit(1 if bad else 0)
