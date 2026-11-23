"""Notifications (Notifier): email through a local fake SMTP server, each webhook
format to a local HTTP server, which events are sent, batching, retries and
test(). Nothing leaves this PC: localhost only, ephemeral ports, and the SMTP
password from FM_MODMON_SMTP_PASSWORD (Credential Manager is never read)."""
import base64
import email
import email.policy
import importlib.util
import json
import os
import queue
import socket
import socketserver
import sys
import threading
import time
import urllib.request
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

os.environ['QT_QPA_PLATFORM'] = 'offscreen'
sys.stdout.reconfigure(encoding='utf-8')
spec = importlib.util.spec_from_file_location('fm_modmon', os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'fm-modmon-ms.py'))
rm = importlib.util.module_from_spec(spec)
spec.loader.exec_module(rm)

os.environ['FM_MODMON_SMTP_PASSWORD'] = 'env-secret'
rm.credential_read = lambda target: None   # never the real Credential Manager entry
urllib.request.install_opener(urllib.request.build_opener(urllib.request.ProxyHandler({})))  # no proxy for localhost
# Quick retries and batches. _deliver's retries default is bound when the class is
# made, so patching NOTIFY_RETRY_S alone would not reach it: patch the default too.
rm.NOTIFY_BATCH_S = 0.6
RETRY = (0.2, 0.2)
rm.NOTIFY_RETRY_S = RETRY
d = list(rm.Notifier._deliver.__defaults__)
d[1] = RETRY
rm.Notifier._deliver.__defaults__ = tuple(d)

bad = 0


def check(title, got, want):
    global bad
    ok = got == want
    bad += not ok
    print(f'   {"ok   " if ok else "WRONG"} {title}: {got!r}' + ('' if ok else f', expected {want!r}'))


def wait_for(cond, timeout=5.0):
    end = time.monotonic() + timeout
    while time.monotonic() < end:
        if cond():
            return True
        time.sleep(0.02)
    return cond()


def free_port():
    s = socket.socket()
    s.bind(('127.0.0.1', 0))
    port = s.getsockname()[1]
    s.close()
    return port


def drain(q):
    out = []
    while True:
        try:
            out.append(q.get_nowait())
        except queue.Empty:
            return out


# ------------------------------------------------------------ fake servers
class FakeSmtp(socketserver.StreamRequestHandler):
    """Just enough SMTP (EHLO, AUTH PLAIN, MAIL, RCPT, DATA, QUIT) for smtplib."""

    def reply(self, line):
        self.wfile.write(line.encode() + b'\r\n')

    def handle(self):
        srv = self.server
        self.reply('220 fake ESMTP')
        rcpt, sender = [], None
        while line := self.rfile.readline():
            cmd = line.decode().rstrip('\r\n')
            verb = cmd.split(' ', 1)[0].upper()
            if verb in ('EHLO', 'HELO'):
                self.reply('250-fake')
                self.reply('250-AUTH PLAIN')
                self.reply('250 8BITMIME')
            elif verb == 'AUTH':
                _, _, user, password = (b'\0' + base64.b64decode(cmd.split()[2])).split(b'\0')
                srv.logins.append((user.decode(), password.decode()))
                self.reply('235 ok')
            elif verb == 'MAIL':
                sender = cmd[cmd.index('<') + 1:cmd.index('>')]
                self.reply('250 ok')
            elif verb == 'RCPT':
                rcpt.append(cmd[cmd.index('<') + 1:cmd.index('>')])
                self.reply('250 ok')
            elif verb == 'DATA':
                self.reply('354 go on')
                data = b''
                while (part := self.rfile.readline()) not in (b'.\r\n', b''):
                    data += part[1:] if part.startswith(b'..') else part
                srv.mails.append((sender, rcpt, email.message_from_bytes(data, policy=email.policy.default)))
                rcpt = []
                self.reply('250 2.0.0 Ok: queued as FAKE123')
            elif verb == 'QUIT':
                self.reply('221 bye')
                return
            else:
                self.reply('250 ok')


class SmtpServer(socketserver.ThreadingTCPServer):
    daemon_threads = True

    def __init__(self):
        super().__init__(('127.0.0.1', 0), FakeSmtp)
        self.mails, self.logins = [], []
        threading.Thread(target=self.serve_forever, daemon=True).start()


class Hook(BaseHTTPRequestHandler):
    def do_POST(self):
        srv = self.server
        body = self.rfile.read(int(self.headers.get('Content-Length') or 0))
        srv.posts.append((self.path, self.headers.get('Content-Type'), json.loads(body)))
        code = 500 if srv.fail > 0 else 200
        srv.fail -= 1
        self.send_response(code)
        self.send_header('Content-Length', '2')
        self.end_headers()
        self.wfile.write(b'ok')

    def log_message(self, *args):
        pass


class HookServer(ThreadingHTTPServer):
    daemon_threads = True

    def __init__(self):
        super().__init__(('127.0.0.1', 0), Hook)
        self.posts, self.fail = [], 0
        threading.Thread(target=self.serve_forever, daemon=True).start()

    @property
    def url(self):
        return f'http://127.0.0.1:{self.server_address[1]}/hook'


smtp, hook = SmtpServer(), HookServer()
WHERE = lambda: ('testhost', 'http://testhost:8080/')  # noqa: E731
APP = rm.APP_NAME


def mail_settings(**kw):
    return rm.NotifySettings(**{'email': True, 'smtp_host': '127.0.0.1', 'smtp_port': smtp.server_address[1],
                                'smtp_security': 'none', 'smtp_user': 'bot@example.org',
                                'email_from': 'Monitor <monitor@example.org>',
                                'email_to': 'ops@example.org; eng@example.org', **kw})


def hook_settings(fmt='json', **kw):
    return rm.NotifySettings(**{'webhook': True, 'webhook_url': hook.url, 'webhook_format': fmt, **kw})


print('--- which events are sent (enabled)')
n = rm.Notifier(rm.NotifySettings(), WHERE)
check('nothing on: no kind enabled', [bool(n.enabled(k)) for k in ('raise', 'clear', 'sdr', 'startstop')],
      [False] * 4)
n.settings = hook_settings(on_raise=False, on_sdr=False)
check('webhook on, on_raise / on_sdr off', [bool(n.enabled(k)) for k in ('raise', 'clear', 'sdr', 'startstop')],
      [False, True, False, True])
n.settings = mail_settings(on_clear=False, on_start_stop=False)
check('email on, on_clear / on_start_stop off', [bool(n.enabled(k)) for k in ('raise', 'clear', 'sdr', 'startstop')],
      [True, False, True, False])
check('an unknown kind follows on_raise', bool(n.enabled('other')), True)
n.settings = hook_settings(on_raise=False)
hook.posts.clear()
n.event('raise', 'not wanted')
time.sleep(rm.NOTIFY_BATCH_S + 0.4)
check('a disabled kind is not queued or sent', len(hook.posts), 0)

print('--- email through the fake SMTP server')
n = rm.Notifier(mail_settings(), WHERE)
n.event('raise', 'Receiver 1 101.7: MOD over 110%')
wait_for(lambda: smtp.mails, rm.NOTIFY_BATCH_S + 5)
check('one message delivered', len(smtp.mails), 1)
if smtp.mails:
    sender, rcpt, msg = smtp.mails[-1]
    check('envelope sender', sender, 'monitor@example.org')
    check('envelope recipients (, and ; split)', rcpt, ['ops@example.org', 'eng@example.org'])
    check('Subject', msg['Subject'], f'[{APP} testhost] Receiver 1 101.7: MOD over 110%')
    check('From', msg['From'], 'Monitor <monitor@example.org>')
    check('To', msg['To'], 'ops@example.org, eng@example.org')
    check('has a Date', bool(msg['Date']), True)
    check('Message-ID uses the sender\'s domain', msg['Message-ID'].rstrip('>').endswith('@example.org'), True)
    body = msg.get_content().splitlines()
    check('body: the event line', body[0].endswith('  Receiver 1 101.7: MOD over 110%'), True)
    check('body: footer with the web address', body[-2:], [f'{APP} on testhost', 'web: http://testhost:8080/'])
check('logged in with the FM_MODMON_SMTP_PASSWORD password', smtp.logins[-1:], [('bot@example.org', 'env-secret')])
check('the server\'s answer kept (queue ID)', n.last_reply.get('email'), '250 2.0.0 Ok: queued as FAKE123')
check('nothing reported', drain(n.results), [])

print('--- webhook formats to the local HTTP server')
batch = [('2026-11-23 10:00:00', 'raise', 'first event'), ('2026-11-23 10:00:01', 'clear', 'second event')]
subject = f'[{APP} testhost] 2 events: first event …'
text = '\n'.join([subject, '2026-11-23 10:00:00  first event', '2026-11-23 10:00:01  second event'])
want = {
    'json': {'app': APP, 'host': 'testhost', 'web': 'http://testhost:8080/', 'summary': subject, 'text': text,
             'events': [{'time': '2026-11-23 10:00:00', 'kind': 'raise', 'text': 'first event'},
                        {'time': '2026-11-23 10:00:01', 'kind': 'clear', 'text': 'second event'}]},
    'slack': {'text': text},
    'discord': {'content': text},
}
for fmt in ('json', 'slack', 'teams', 'discord'):
    hook.posts.clear()
    got = n._deliver(batch, hook_settings(fmt), retries=(), report=False)
    check(f'{fmt}: delivered', got, [('webhook', None)])
    path, ctype, payload = hook.posts[-1] if hook.posts else (None, None, None)
    check(f'{fmt}: POST to the URL as JSON', (path, ctype), ('/hook', 'application/json'))
    if fmt == 'teams':
        att = (payload or {}).get('attachments', [{}])[0]
        card = att.get('content', {})
        check('teams: an Adaptive Card message', (payload.get('type'), att.get('contentType'), card.get('type')),
              ('message', 'application/vnd.microsoft.card.adaptive', 'AdaptiveCard'))
        check('teams: subject in bold, then a line per event',
              [(b['text'], b.get('weight')) for b in card.get('body', [])],
              [(subject, 'Bolder'), ('2026-11-23 10:00:00  first event', None),
               ('2026-11-23 10:00:01  second event', None)])
    else:
        check(f'{fmt}: payload', payload, want[fmt])
long = [('2026-11-23 10:00:00', 'raise', 'x' * 3000)]
n._deliver(long, hook_settings('discord'), retries=(), report=False)
check('discord: content cut to Discord\'s 2000 limit', len(hook.posts[-1][2]['content']), 1990)

print('--- events within NOTIFY_BATCH_S go out as one message')
n = rm.Notifier(hook_settings('json'), WHERE)
hook.posts.clear()
for i in range(3):
    n.event('raise', f'event {i}')
    time.sleep(0.1)
wait_for(lambda: hook.posts, rm.NOTIFY_BATCH_S + 3)
time.sleep(0.3)
check('three close events: one POST', len(hook.posts), 1)
if hook.posts:
    p = hook.posts[0][2]
    check('...carrying all three', [e['text'] for e in p['events']], ['event 0', 'event 1', 'event 2'])
    check('...summary counts them', p['summary'], f'[{APP} testhost] 3 events: event 0 …')
time.sleep(rm.NOTIFY_BATCH_S)
hook.posts.clear()
n.event('clear', 'later event')
wait_for(lambda: hook.posts, rm.NOTIFY_BATCH_S + 3)
check('a later event: its own message', [e['text'] for e in hook.posts[0][2]['events']] if hook.posts else None,
      ['later event'])

print('--- a failing endpoint is retried after NOTIFY_RETRY_S')
hook.posts.clear()
hook.fail = 2                    # two 500s, then OK
t0 = time.monotonic()
n.event('raise', 'retried')
wait_for(lambda: len(hook.posts) >= 3, rm.NOTIFY_BATCH_S + 5)
took = time.monotonic() - t0
check('sent three times (two failures, then OK)', len(hook.posts), 3)
check('waits between tries follow NOTIFY_RETRY_S', took >= rm.NOTIFY_BATCH_S + sum(RETRY) - 0.05, True)
time.sleep(0.2)
check('succeeded in the end: nothing reported', drain(n.results), [])
hook.posts.clear()
hook.fail = 99
n.event('raise', 'never gets through')
got = None
try:
    got = n.results.get(timeout=rm.NOTIFY_BATCH_S + sum(RETRY) + 5)
except queue.Empty:
    pass
check('every try failing: tried 1 + len(NOTIFY_RETRY_S) times', len(hook.posts), 1 + len(RETRY))
check('...and the failure reported on results', got,
      'notification by webhook failed (3 attempts): HTTPError: HTTP Error 500: Internal Server Error')
hook.fail = 0

print('--- test(): an error per channel, nothing reported on results')
n = rm.Notifier(rm.NotifySettings(), WHERE)
both = mail_settings(webhook=True, webhook_url=hook.url)
smtp.mails.clear()
hook.posts.clear()
check('both working', n.test(both), [('email', None), ('webhook', None)])
check('test email subject', smtp.mails[-1][2]['Subject'] if smtp.mails else None,
      f'[{APP} testhost] test message from {APP} on testhost')
check('test webhook kind', hook.posts[-1][2]['events'][0]['kind'] if hook.posts else None, 'test')
n.test(mail_settings(), password='typed-not-stored')
check('a typed password is used over the stored one', smtp.logins[-1], ('bot@example.org', 'typed-not-stored'))
dead = free_port()
broken = rm.NotifySettings(**{**both.to_dict(), 'smtp_port': dead, 'webhook_url': f'http://127.0.0.1:{dead}/x'})
t0 = time.monotonic()
res = n.test(broken)
check('channels in order', [c for c, _ in res], ['email', 'webhook'])
check('email error given', (res[0][1] or '').startswith('ConnectionRefusedError'), True)
check('webhook error given', (res[1][1] or '').startswith('URLError'), True)
check('test() does not retry', time.monotonic() - t0 < sum(RETRY) + 4, True)
check('test() reports nothing on results', drain(n.results), [])
hook.fail = 1
check('an HTTP error status is an error', n.test(hook_settings('slack')),
      [('webhook', 'HTTPError: HTTP Error 500: Internal Server Error')])

print('\nall as expected' if not bad else f'\n{bad} unexpected')
sys.exit(1 if bad else 0)
