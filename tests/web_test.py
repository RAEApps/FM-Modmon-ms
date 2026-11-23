"""The web version's server (WebView): pages and JSON, the X-FM-Modmon header,
bad bodies, signing in and out, idle sessions, and control requests through
MainWindow._web_commands / _web_command (on a stub window: no SDR, no flowgraph).
Localhost only, on an ephemeral port."""
import http.client
import importlib.util
import json
import os
import sys
import threading
import time
import types

os.environ['QT_QPA_PLATFORM'] = 'offscreen'
sys.stdout.reconfigure(encoding='utf-8')
spec = importlib.util.spec_from_file_location('fm_modmon', os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'fm-modmon-ms.py'))
rm = importlib.util.module_from_spec(spec)
spec.loader.exec_module(rm)
from PyQt5 import QtWidgets

app = QtWidgets.QApplication([])   # the favicon is drawn with Qt
bad = 0


def check(title, got, want):
    global bad
    ok = got == want
    bad += not ok
    print(f'   {"ok   " if ok else "WRONG"} {title}: {got!r}' + ('' if ok else f', expected {want!r}'))


def request(view, method, path, body=None, headers=None, raw=False):
    """(status, parsed JSON body or raw bytes)."""
    conn = http.client.HTTPConnection('127.0.0.1', view.server.server_address[1], timeout=30)
    hdrs = {'Host': 'localhost'} | (headers or {})
    data = body if isinstance(body, bytes) or body is None else json.dumps(body).encode()
    conn.request(method, path, body=data, headers=hdrs)
    r = conn.getresponse()
    payload = r.read()
    conn.close()
    if raw:
        return r.status, payload, r
    try:
        return r.status, json.loads(payload)
    except ValueError:
        return r.status, payload


def post(view, path, body=None, token=None, headers=None):
    h = {'X-FM-Modmon': '1', 'Content-Type': 'application/json'}
    if token:
        h['X-FM-Modmon-Session'] = token
    return request(view, 'POST', path, {} if body is None else body, h | (headers or {}))


# ------------------------------------------------------------ a stub window
# MainWindow's own _web_commands / _web_command, on a stand-in with one receiver,
# drained on a thread as the GUI timer would.
resets = []
panel = types.SimpleNamespace(slot=0, station=types.SimpleNamespace(
    audio_meter=types.SimpleNamespace(reset_integrated=lambda: resets.append(1))),
    settings=rm.ReceiverSettings())
win = types.SimpleNamespace(_recovery=None, _cal=None, panels=[panel], open_feed=None, logged=[], published=[])
win.log = win.logged.append
win._publish = lambda: win.published.append(1)
win._web_command = lambda action, args: rm.MainWindow._web_command(win, action, args)


def gui_loop(view, stop):
    win.web = view
    while not stop.is_set():
        rm.MainWindow._web_commands(win)
        time.sleep(0.02)


def start(**kw):
    view = rm.WebView('127.0.0.1', 0, **kw)
    stop = threading.Event()
    threading.Thread(target=gui_loop, args=(view, stop), daemon=True).start()
    return view, stop


print('--- pages and JSON (no password)')
view, stop = start()
view.state = json.dumps({'ready': True, 'receivers': []}).encode()
view.events = json.dumps(['10:00:00  something']).encode()
code, body, r = request(view, 'GET', '/', raw=True)
check('GET / 200, the page', (code, r.getheader('Content-Type'), b'<html' in body.lower()),
      (200, 'text/html; charset=utf-8', True))
check('hardening headers', (r.getheader('X-Frame-Options'), r.getheader('X-Content-Type-Options')), ('DENY', 'nosniff'))
code, body = request(view, 'GET', '/state.json?t=1')
check('/state.json 200 (query ignored)', code, 200)
check('/state.json: access, then the state', body if code == 200 else None,
      {'access': {'control': True, 'password': False}, 'ready': True, 'receivers': []})
code, body = request(view, 'GET', '/help.json')
check('/help.json 200, sections', (code, isinstance(body, dict) and len(body.get('sections', [])) > 0), (200, True))
code, body = request(view, 'GET', '/readouts.json')
check('/readouts.json 200, JSON', (code, isinstance(body, (dict, list))), (200, True))
code, body = request(view, 'GET', '/events.json')
check('/events.json 200', (code, body), (200, ['10:00:00  something']))
check('/favicon.ico 200', request(view, 'GET', '/favicon.ico', raw=True)[0], 200)
for path in ('/nope', '/state.jsonx', '/img/1/logo', '/audio/1.mp3', '/../fm-modmon-ms.py'):
    check(f'GET {path} 404', request(view, 'GET', path)[0], 404)

print('--- POST checks (no password: from localhost only)')
code, body = request(view, 'POST', '/api/reset_integrated', {'receiver': 1}, {'Content-Type': 'application/json'})
check('no X-FM-Modmon header: 403', code, 403)
code, body = request(view, 'POST', '/api/reset_integrated', {'receiver': 1}, {'X-FM-Modmon': 'yes'})
check('X-FM-Modmon not 1: 403', code, 403)
check('invalid JSON: 400', post(view, '/api/reset_integrated', b'{not json')[0], 400)
check('JSON not an object: 400', post(view, '/api/reset_integrated', b'[1, 2]')[0], 400)
check('Content-Length over 64 kB: 400',
      post(view, '/api/reset_integrated', b'{}', headers={'Content-Length': '70000'})[0], 400)
check('bad Content-Length: 400', post(view, '/api/reset_integrated', b'{}', headers={'Content-Length': 'x'})[0], 400)
check('a POST outside /api/: 404', post(view, '/other')[0], 404)
check('login with no password set: 400', post(view, '/api/login', {'password': 'x'})[0], 400)
check('Host not localhost (DNS rebinding): 403',
      post(view, '/api/reset_integrated', {'receiver': 1}, headers={'Host': 'evil.example:8080'})[0], 403)
resets.clear()
check('from localhost: the command runs', post(view, '/api/reset_integrated', {'receiver': 1}), (200, {'ok': True}))
check('...reset_integrated called on the receiver', len(resets), 1)
check('...and the state published after it', len(win.published) > 0, True)
stop.set()
view.server.shutdown()
view.server.server_close()

print('--- signing in (a password set)')
view, stop = start(password='right-password')
check('/state.json says signed out', request(view, 'GET', '/state.json')[1]['access'], {'control': False, 'password': True})
check('a control without a token: 403', post(view, '/api/reset_integrated', {'receiver': 1})[0], 403)
check('a made-up token: 403', post(view, '/api/reset_integrated', {'receiver': 1}, token='made-up')[0], 403)
t0 = time.monotonic()
check('wrong password: 403', post(view, '/api/login', {'password': 'wrong'}), (403, {'error': 'wrong password'}))
check('...after a delay (slows guessing)', time.monotonic() - t0 >= 0.9, True)
time.sleep(0.1)
check('...and logged', any('failed sign-in from 127.0.0.1' in t for t in win.logged), True)
code, body = post(view, '/api/login', {'password': 'right-password'})
token = body.get('token') if isinstance(body, dict) else None
check('right password: 200 with a token', (code, bool(token) and len(token) >= 24), (200, True))
check('/state.json with the token says control',
      request(view, 'GET', '/state.json', headers={'X-FM-Modmon-Session': token})[1]['access'],
      {'control': True, 'password': True})

print('--- commands through the queue (MainWindow._web_commands / _web_command)')
resets.clear()
check('reset_integrated: 200 ok', post(view, '/api/reset_integrated', {'receiver': 1}, token), (200, {'ok': True}))
check('...ran on the receiver', len(resets), 1)
check('unknown action: 400 with the reason', post(view, '/api/frobnicate', {'receiver': 1}, token),
      (400, {'error': "unknown action 'frobnicate'"}))
check('no such receiver: 400', post(view, '/api/reset_integrated', {'receiver': 4}, token),
      (400, {'error': 'no such receiver'}))
check('removing the last receiver: 400', post(view, '/api/remove', {'receiver': 1}, token),
      (400, {'error': 'the last receiver cannot be removed'}))
check('settings without settings: 400', post(view, '/api/settings', {'receiver': 1}, token),
      (400, {'error': 'no settings'}))
check('settings with a bad PI: 400', post(view, '/api/settings', {'receiver': 1, 'settings': {'expected_pi': 'XYZ'}}, token),
      (400, {'error': 'Expected PI is four hex digits (such as 618F), or empty.'}))
win._recovery = {'since': time.time(), 'attempt': 1, 'error': None}
check('while the SDR is reopened, add is refused', post(view, '/api/add', {}, token),
      (400, {'error': 'the SDR is being reopened; try again when it is back'}))
win._recovery = None
win._cal = {'was': ''}
check('while calibrating, recalibrate is refused', post(view, '/api/recalibrate', {}, token),
      (400, {'error': 'the gain is being calibrated already'}))
win._cal = None
win._web_command = lambda action, args: {'echo': action, 'args': args}   # a command's own answer goes back
check('a command\'s result is the response', post(view, '/api/anything', {'x': 1}, token),
      (200, {'echo': 'anything', 'args': {'x': 1}}))
win._web_command = lambda action, args: 1 / 0
check('an unexpected error: 400 naming it', post(view, '/api/anything', {}, token),
      (400, {'error': 'ZeroDivisionError: division by zero'}))
win._web_command = lambda action, args: rm.MainWindow._web_command(win, action, args)
view.note('a note from the server')
time.sleep(0.1)
check('note(): a log line, not a command', win.logged[-1], 'a note from the server')

print('--- signing out and idle sessions')
check('logout: 200', post(view, '/api/logout', {}, token), (200, {'ok': True}))
check('the token no longer works', post(view, '/api/reset_integrated', {'receiver': 1}, token)[0], 403)
check('logout again (no session): still 200', post(view, '/api/logout', {}, token), (200, {'ok': True}))
_, body = post(view, '/api/login', {'password': 'right-password'})
token = body['token']
view.SESSION_IDLE_S = 0.5
check('used within SESSION_IDLE_S: kept', post(view, '/api/reset_integrated', {'receiver': 1}, token)[0], 200)
time.sleep(0.3)
check('...still (each request keeps it alive)', post(view, '/api/reset_integrated', {'receiver': 1}, token)[0], 200)
time.sleep(0.8)
check('idle longer than SESSION_IDLE_S: dropped', post(view, '/api/reset_integrated', {'receiver': 1}, token)[0], 403)
check('...and gone from sessions', token in view.sessions, False)
view.SESSION_IDLE_S = 600
_, body = post(view, '/api/login', {'password': 'right-password'})
token = body['token']
view.set_password_hash(rm.hash_password('new-password'))
check('a new password from Setup signs everyone out', post(view, '/api/reset_integrated', {'receiver': 1}, token)[0], 403)
view.password = None   # (as with no --web-password: the hash decides)
check('the new hashed password signs in', post(view, '/api/login', {'password': 'new-password'})[0], 200)
check('the old one does not', post(view, '/api/login', {'password': 'right-password'})[0], 403)
stop.set()
view.server.shutdown()
view.server.server_close()

print('\nall as expected' if not bad else f'\n{bad} unexpected')
sys.exit(1 if bad else 0)
