"""RDS group feed (RdsGroupServer): a client that stops reading is dropped
without ever holding up the RDS decoder, and a healthy client keeps its feed.
Exits non-zero on a failure."""
import os
import socket
import sys
import threading
import time

os.environ['QT_QPA_PLATFORM'] = 'offscreen'
from loadapp import load_app  # noqa: E402
m = load_app(sys.argv[1] if len(sys.argv) > 1 else None)

bad = []


def check(name, ok, detail=''):
    print(f"{'ok   ' if ok else 'WRONG'} {name} {detail}")
    if not ok:
        bad.append(name)


s = socket.socket()
s.bind(('127.0.0.1', 0))
port = s.getsockname()[1]
s.close()
srv = m.RdsGroupServer('127.0.0.1', port)
good = socket.create_connection(('127.0.0.1', port))
good.setblocking(False)
stalled = socket.socket()
stalled.setsockopt(socket.SOL_SOCKET, socket.SO_RCVBUF, 1024)
stalled.connect(('127.0.0.1', port))  # never reads
time.sleep(0.3)
check('two clients connected', srv.clients == 2, srv.clients)

# ~5000 groups/s, hundreds of times the real rate, until the stalled client's buffers fill
worst = 0.0
for i in range(12000):
    time.sleep(0.001)
    for _ in range(5):
        t = time.perf_counter()
        srv.send_group(0x618F, i & 0xFFFF, 0, 0)
        worst = max(worst, time.perf_counter() - t)
    try:
        while good.recv(65536):
            pass
    except BlockingIOError:
        pass
time.sleep(m.RdsGroupServer.SEND_TIMEOUT_S + 0.5)
check('send_group never blocks', worst < 0.05, f'(worst {worst * 1000:.2f} ms)')
check('stalled client dropped, healthy one kept', srv.clients == 1, srv.clients)
writers = lambda: sum(t.name == 'rds-feed-writer' for t in threading.enumerate())  # noqa: E731
check("the stalled client's writer ended (its queue full, so no None to read)", writers() == 1, writers())

srv.close()
time.sleep(0.5)
check('close(): every writer ended', writers() == 0, writers())
try:
    socket.create_server(('127.0.0.1', port)).close()
    free = True
except OSError:
    free = False
check('port free after close()', free)

print('\nall ok' if not bad else f'\n{len(bad)} WRONG')
sys.exit(1 if bad else 0)
