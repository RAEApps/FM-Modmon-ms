"""RadioDNS slideshow (ETSI TS 101 499) against local fake servers: Server-sent
Events, Stomp and HTTP transports, trigger-time, links, text, bad slides,
download limits, failover and SRV ordering. No network or SDR needed."""
import datetime
import importlib.util
import json
import os
import socket
import socketserver
import sys
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

os.environ['QT_QPA_PLATFORM'] = 'offscreen'
sys.stdout.reconfigure(encoding='utf-8')
spec = importlib.util.spec_from_file_location('fm_modmon', os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'fm-modmon-ms.py'))
rm = importlib.util.module_from_spec(spec)
spec.loader.exec_module(rm)

SERVICE = 'fm/ce1/c479/09580'
PNG = b'\x89PNG\r\n\x1a\n' + b'\0' * 64
failures = []


def check(name, ok, detail=''):
    print(f'{"ok  " if ok else "FAIL"} {name}' + (f'  ({detail})' if detail and not ok else ''))
    if not ok:
        failures.append(name)


def wait_for(cond, timeout=10.0):
    end = time.monotonic() + timeout
    while time.monotonic() < end:
        if cond():
            return True
        time.sleep(0.05)
    return cond()


def iso(t):
    return datetime.datetime.fromtimestamp(t, datetime.timezone.utc).strftime('%Y-%m-%dT%H:%M:%S.000Z')


class Web(BaseHTTPRequestHandler):
    """Slides, plus the Server-sent Events and HTTP (long polling) slideshow servers."""
    protocol_version = 'HTTP/1.0'
    comet = {}   # topic -> [responses, in order]; a response is a frame list
    requests = []
    push_events = []

    def log_message(self, *a):
        pass

    def do_GET(self):
        Web.requests.append(self.path)
        if self.path in ('/a.png', '/b.png', '/c.png'):
            self._send(200, 'image/png', PNG)
        elif self.path == '/octet.png':
            self._send(200, 'application/octet-stream', PNG)
        elif self.path == '/big.png':
            self._send(200, 'image/png', PNG + b'\0' * rm.RADIODNS_IMAGE_MAX)
        elif self.path == '/page.html':
            self._send(200, 'text/html', b'<html>not found</html>')
        elif self.path == f'/radiodns/push/3/{SERVICE}':
            self.send_response(200)
            self.send_header('Content-Type', 'text/event-stream')
            self.end_headers()
            for event, data in Web.push_events:
                self.wfile.write(f'id: 1\nevent: {event}\nretry: 15000\ndata: {json.dumps(data)}\n\n'.encode())
                self.wfile.flush()
            try:
                for _ in range(40):
                    time.sleep(0.25)
                    self.wfile.write(b':\n\n')  # heartbeat
                    self.wfile.flush()
            except OSError:
                pass
        elif self.path.startswith('/radiodns/vis/vis.json?'):
            from urllib.parse import parse_qs, urlsplit
            q = parse_qs(urlsplit(self.path).query)
            queue = Web.comet.get(q['topic'][0])
            if queue is None:
                self._send(404, 'text/plain', b'no such topic')
            elif queue:
                self._send(200, 'application/json', json.dumps(queue.pop(0)).encode())
            else:
                time.sleep(3)  # held open, then a frame with no message ID: the client stops
                self._send(200, 'application/json', b'[]')
        else:
            self._send(404, 'text/plain', b'missing')

    def _send(self, code, ctype, body):
        self.send_response(code)
        self.send_header('Content-Type', ctype)
        self.send_header('Content-Length', str(len(body)))
        self.end_headers()
        self.wfile.write(body)


web = ThreadingHTTPServer(('127.0.0.1', 0), Web)
web.daemon_threads = True
threading.Thread(target=web.serve_forever, daemon=True).start()
WP = web.server_address[1]
BASE = f'http://127.0.0.1:{WP}'


class PlainPush(rm.RadioVis):
    """Server-sent Events over plain HTTP (the fake server has no TLS)."""

    def _push_url(self, host, port):
        return f'http://{host}:{port}/radiodns/push/3/{self.service}'


class Stomp(socketserver.BaseRequestHandler):
    """A Stomp slideshow server: image subscriptions are confirmed, text ones refused."""
    script = []   # (header lines, body) MESSAGE frames sent once subscribed
    subscribes = []

    def handle(self):
        buf = b''
        sock = self.request
        sent = False
        sock.settimeout(0.2)
        end = time.monotonic() + 15
        while time.monotonic() < end:
            try:
                data = sock.recv(4096)
                if not data:
                    return
                buf += data
            except socket.timeout:
                pass
            while b'\0' in buf:
                frame, buf = buf.split(b'\0', 1)
                head = frame.decode().lstrip('\r\n').split('\n\n')[0].splitlines()
                h = dict(l.split(':', 1) for l in head[1:] if ':' in l)
                if head[0] == 'CONNECT':
                    sock.sendall(b'CONNECTED\nversion:1.0\n\n\0')
                elif head[0] == 'SUBSCRIBE':
                    Stomp.subscribes.append(h['destination'])
                    if h['destination'].endswith('/text'):
                        sock.sendall(f'ERROR\nreceipt-id:{h["receipt"]}\nmessage:no text here\n\n\0'.encode())
                    else:
                        sock.sendall(f'RECEIPT\nreceipt-id:{h["receipt"]}\n\n\0'.encode())
            if Stomp.subscribes and not sent and len(Stomp.subscribes) >= 2:
                sent = True
                for i, (headers, body) in enumerate(Stomp.script):
                    head = ['MESSAGE', f'destination: /topic/{SERVICE}/image', f'message-id: {i}'] + ([headers] if headers else [])
                    sock.sendall(('\n'.join(head) + f'\n\n{body}\0').encode())


stomp = socketserver.ThreadingTCPServer(('127.0.0.1', 0), Stomp)
stomp.daemon_threads = True
threading.Thread(target=stomp.serve_forever, daemon=True).start()
SP = stomp.server_address[1]

with socket.socket() as s:  # a port nothing listens on
    s.bind(('127.0.0.1', 0))
    DEAD = s.getsockname()[1]

dns = rm.RadioDns()
fetch = dns._download

# ---- downloads
try:
    path = fetch(f'{BASE}/octet.png')
    check('download: generic content type, image bytes accepted', open(path, 'rb').read() == PNG)
except OSError as e:
    check('download: generic content type, image bytes accepted', False, str(e))
for name, url in (('oversized image refused', '/big.png'), ('HTML page refused', '/page.html'),
                  ('404 refused', '/missing.png')):
    try:
        fetch(BASE + url)
        check(f'download: {name}', False, 'downloaded')
    except OSError:
        check(f'download: {name}', True)

# ---- SRV order (RFC 2782)
recs = [(20, 0, 1, 'c.example.'), (10, 1, 2, 'b.example.'), (10, 1000, 3, 'a.example.'), (5, 0, 4, '.')]
orders = [rm.srv_order(recs) for _ in range(200)]
check('srv: target "." dropped, all others kept', all(sorted(o) == [('a.example', 3), ('b.example', 2), ('c.example', 1)]
                                                  for o in orders))
check('srv: lowest priority first, highest weight usually first',
      all(o[2] == ('c.example', 1) for o in orders) and sum(o[0] == ('a.example', 3) for o in orders) > 180)

# ---- trigger-time parsing
check('trigger-time: NOW / none', rm.RadioVis._when('NOW') is None and rm.RadioVis._when(None) is None)
check('trigger-time: ISO 8601 UTC', rm.RadioVis._when('2012-03-20T11:15:46.271Z') ==
      datetime.datetime(2012, 3, 20, 11, 15, 46, 271000, datetime.timezone.utc).timestamp())

# ---- Server-sent Events, after failing over from a server that's down
now = time.time()
Web.push_events = [
    ('image', {'scope': ['fm:ce1.c479.09580'], 'src': f'{BASE}/missing.png'}),
    ('image', {'scope': ['fm:ce1.c479.09580'], 'src': f'{BASE}/a.png', 'triggerTime': 'NOW',
               'link': 'https://example.org/now'}),
    ('image', {'scope': ['fm:ce1.c479.09580'], 'src': f'{BASE}/b.png', 'triggerTime': iso(now + 2),
               'link': 'https://example.org/later'}),
    ('image', {'scope': ['fm:ce1.c479.09580'], 'src': f'{BASE}/c.png', 'triggerTime': iso(now - 3600)}),
    ('text', {'scope': ['fm:ce1.c479.09580'], 'body': 'You are listening to Example FM'}),
    ('text', {'scope': ['fm:ce1.c479.09580'], 'body': 'x' * 129}),
    ('meta', {'scope': ['fm:ce1.c479.09580'], 'item': {'artist': 'A', 'title': 'B'}}),
]
Web.requests.clear()
vis = PlainPush([('push', '127.0.0.1', DEAD), ('push', '127.0.0.1', WP)], SERVICE, fetch)
ok = wait_for(lambda: vis.image and vis.text)
check('push: fails over to the second server and shows the NOW slide',
      ok and vis.transport == 'push' and vis.link == 'https://example.org/now'
      and open(vis.image, 'rb').read() == PNG, f'state={vis.state} image={vis.image}')
check('push: a 404 slide is skipped without dropping the connection', vis.state == 'showing', vis.state)
check('push: text shown, over-long text ignored', vis.text == 'You are listening to Example FM', vis.text)
first = vis.image
check('push: future slide held until its trigger-time', vis.link == 'https://example.org/now')
check('push: future slide shown at its trigger-time',
      wait_for(lambda: vis.link == 'https://example.org/later', 5) and vis.image != first, f'link={vis.link}')
check('push: slide whose time had passed never downloaded', '/c.png' not in Web.requests)
vis._wanted = 0  # let it go idle

# ---- Stomp: a refused destination doesn't stop the slideshow
Stomp.script = [('', 'SHOW ' + f'{BASE}/missing.png'),
                ('link: https://example.org/stomp\ntrigger-time: NOW', 'SHOW ' + f'{BASE}/a.png')]
vis = rm.RadioVis([('stomp', '127.0.0.1', SP)], SERVICE, fetch)
ok = wait_for(lambda: vis.image)
check('stomp: slide and link after a refused text subscription and a 404 slide',
      ok and vis.link == 'https://example.org/stomp' and vis.state == 'showing' and vis.error is None,
      f'state={vis.state} error={vis.error}')
check('stomp: refused destination remembered', ('stomp', f'/topic/{SERVICE}/text') in vis._done)
vis._wanted = 0

# ---- HTTP long polling, falling back from a Stomp server that's down
img_topic, text_topic = f'/topic/{SERVICE}/image', f'/topic/{SERVICE}/text'
Web.comet = {
    img_topic: [[{'headers': {'RadioVIS-Message-ID': 'm1', 'RadioVIS-Destination': img_topic,
                              'RadioVIS-Link': 'https://example.org/http', 'RadioVIS-Trigger-Time': 'NOW'},
                  'body': f'SHOW {BASE}/a.png'}],
                {'headers': {'RadioVIS-Message-ID': 'm2', 'RadioVIS-Destination': img_topic,
                             'RadioVIS-Trigger-Time': iso(time.time() + 1)},
                 'body': f'SHOW {BASE}/b.png'}],
    text_topic: [{'headers': {'RadioVIS-Message-ID': 't1', 'RadioVIS-Destination': text_topic},
                  'body': 'TEXT Now playing: B by A'}],
}
Web.requests.clear()
vis = rm.RadioVis([('stomp', '127.0.0.1', DEAD), ('http', '127.0.0.1', WP)], SERVICE, fetch)
ok = wait_for(lambda: vis.image and vis.text)
check('http: falls back from Stomp; slide, link and text',
      ok and vis.transport == 'http' and vis.text == 'Now playing: B by A', f'state={vis.state} text={vis.text!r}')
check('http: second poll sends last_id', wait_for(lambda: any('last_id=m1' in r for r in Web.requests), 5))
check('http: timed slide shown at its time', wait_for(lambda: vis.link is None and vis.image, 5), f'link={vis.link}')
check('http: no message ID ends polling for the topic', wait_for(lambda: ('http', img_topic) in vis._done, 10))
vis._wanted = 0

# ---- the panel: slideshow text on the RadioDNS line, the slide's link on the album art
import types
from PyQt5 import QtGui, QtWidgets
app = QtWidgets.QApplication([])
slide = fetch(f'{BASE}/a.png')
QtGui.QImage(8, 8, QtGui.QImage.Format_RGB32).save(slide, 'PNG')  # a real PNG, so the label shows it
show = types.SimpleNamespace(image=slide, link='https://example.org/now', text='Now <b>playing</b>', transport='push')
found = {'state': 'found', 'name': 'Example FM', 'spi': 'spi.example', 'description': '', 'logo': None, 'target': 't'}
p = rm.StationPanel.__new__(rm.StationPanel)  # just the display parts, without a receiver behind them
p.radiodns = types.SimpleNamespace(lookup=lambda fqdn, bearer: found, vis=lambda fqdn: show)
p.station, p.country = types.SimpleNamespace(iboc=None, freq_hz=95.8e6), 'CA'
p.rdns_line, p.logo_img, p.art_img = QtWidgets.QLabel(), QtWidgets.QLabel(), QtWidgets.QLabel()
p._rdns_row = ()
for img in (p.logo_img, p.art_img):
    img.path = img.link = None
p._update_media({0: 'C479'}, {'ecc': 0xE1})
line = QtGui.QTextDocumentFragment.fromHtml(p.rdns_line.text()).toPlainText()
check('panel: transport and slideshow text on the RadioDNS line',
      'slideshow (Server-sent Events): “Now <b>playing</b>”' in line, line)
check('panel: album art shows the slide, with its link', p.art_img.path == slide and p.art_img.link == show.link
      and 'Click to open https://example.org/now' in p.art_img.toolTip(), p.art_img.toolTip())
show.link, show.text = None, ''
p._update_media({0: 'C479'}, {'ecc': 0xE1})
check('panel: link and text cleared with the next slide', p.art_img.link is None and 'Click' not in p.art_img.toolTip()
      and '“' not in p.rdns_line.text())

print('\nall RadioVIS checks passed' if not failures else f'\n{len(failures)} failed: {", ".join(failures)}')
sys.exit(1 if failures else 0)
