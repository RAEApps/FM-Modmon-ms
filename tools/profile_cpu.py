r"""Where FM-Modmon-ms spends its CPU, on the real RSP1A.

Close the monitor first (this needs the RSP1A), then:

    C:\ProgramData\radioconda\python.exe tools\profile_cpu.py

It starts the monitor beside it (..\fm-modmon-ms.py) with the saved receivers,
waits 40 s, measures for 30 s, closes it, and prints a report and writes it to
fm-modmon-profile.txt on the Desktop. Anything after the script name goes to
the monitor, e.g.  --freqs 94.5 101.7 100.9  or  --config other.json

The report splits the process's CPU into the Qt (GUI) thread, the Python
blocks (meters, RDS), the C++ blocks' work, and the rest: mostly GNU Radio
waking a thread per block and passing buffers between them, plus the SDR
driver. Block work times come from GNU Radio's performance counters and are
wall time inside work(), so the SDR source's includes waiting for samples.
It also totals each thread's CPU by the DLL the thread started in: GNU Radio
and Python threads show as ucrtbase.dll, the SDR driver's as sdrplay_api.dll,
numpy's maths threads as libiomp5md.dll.
"""
import collections
import ctypes
import functools
import importlib.util
import inspect
import json
import os
import platform
import sys
import threading
import time

os.environ['GR_CONF_PERFCOUNTERS_ON'] = 'True'
os.environ['GR_CONF_PERFCOUNTERS_EXPORT'] = 'False'
APP = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'fm-modmon-ms.py')
OUT = os.path.join(os.path.expanduser('~'), 'Desktop', 'fm-modmon-profile.txt')
WARM_S, WINDOW_S = 40.0, 30.0
PYTHON_BLOCKS = ('IqTap', 'FmMeter', 'ScaMeter', 'AudioMeter', 'RdsState', 'IbocPipe', 'PcmTap')
PYTHON_BLOCK_NAMES = {'iq_tap', 'fm_meter', 'sca_meter', 'audio_meter', 'rds_state', 'iboc_pipe', 'pcm_tap'}
sys.argv = [APP] + sys.argv[1:]

from gnuradio import gr  # noqa: E402  (after the perf-counter settings)

blocks = {}  # id -> (owner, block), every block the monitor connects


def _recording(connect):
    def wrapper(self, *args):
        for a in args:
            b = a[0] if isinstance(a, tuple) else a
            if hasattr(b, 'pc_work_time_total'):
                blocks.setdefault(id(b), (self.name(), b))
        return connect(self, *args)
    return wrapper


gr.top_block.connect = _recording(gr.top_block.connect)
gr.hier_block2.connect = _recording(gr.hier_block2.connect)

spec = importlib.util.spec_from_file_location('fm_modmon', APP)
app = importlib.util.module_from_spec(spec)
spec.loader.exec_module(app)

# CPU time inside each method of the Python blocks (inclusive of what they call).
cpu = collections.Counter()


def _timed(fn, key):
    @functools.wraps(fn)
    def wrapper(*a, **kw):
        t = time.thread_time()
        try:
            return fn(*a, **kw)
        finally:
            cpu[key] += time.thread_time() - t
    return wrapper


for name in PYTHON_BLOCKS:
    cls = getattr(app, name, None)
    for attr, v in list(vars(cls).items()) if cls else ():
        if inspect.isfunction(v) and not attr.startswith('__'):  # not static/class methods
            setattr(cls, attr, _timed(v, f'{name}.{attr}'))

kernel32 = ctypes.windll.kernel32
MAIN_TID = threading.get_native_id()


def main_thread_cpu():
    h = kernel32.OpenThread(0x0040, False, MAIN_TID)  # THREAD_QUERY_INFORMATION
    created, exited, kernel, user = (ctypes.c_ulonglong() for _ in range(4))
    kernel32.GetThreadTimes(h, ctypes.byref(created), ctypes.byref(exited), ctypes.byref(kernel), ctypes.byref(user))
    kernel32.CloseHandle(h)
    return (kernel.value + user.value) / 1e7


class THREADENTRY32(ctypes.Structure):
    _fields_ = [('dwSize', ctypes.c_ulong), ('cntUsage', ctypes.c_ulong), ('th32ThreadID', ctypes.c_ulong),
                ('th32OwnerProcessID', ctypes.c_ulong), ('tpBasePri', ctypes.c_long),
                ('tpDeltaPri', ctypes.c_long), ('dwFlags', ctypes.c_ulong)]


ntdll = ctypes.windll.ntdll
kernel32.GetModuleHandleExW.argtypes = [ctypes.c_ulong, ctypes.c_void_p, ctypes.POINTER(ctypes.c_void_p)]
kernel32.GetModuleFileNameW.argtypes = [ctypes.c_void_p, ctypes.c_wchar_p, ctypes.c_ulong]
ntdll.NtQueryInformationThread.argtypes = [ctypes.c_void_p, ctypes.c_int, ctypes.c_void_p, ctypes.c_ulong,
                                           ctypes.c_void_p]
kernel32.OpenThread.restype = ctypes.c_void_p
kernel32.CloseHandle.argtypes = [ctypes.c_void_p]
kernel32.GetThreadTimes.argtypes = [ctypes.c_void_p] + [ctypes.c_void_p] * 4
module_of = {}  # thread id -> DLL its start address is in


def _start_module(h, tid):
    """The DLL a thread started in (sdrplay_api.dll, Qt5Core.dll ...). GNU Radio's
    and Python's threads start in the C runtime (ucrtbase.dll)."""
    if tid not in module_of:
        addr = ctypes.c_void_p()
        name = '?'
        if ntdll.NtQueryInformationThread(h, 9, ctypes.byref(addr), ctypes.sizeof(addr), None) == 0 and addr.value:
            mod = ctypes.c_void_p()
            if kernel32.GetModuleHandleExW(0x4 | 0x2, addr, ctypes.byref(mod)):  # FROM_ADDRESS, UNCHANGED_REFCOUNT
                buf = ctypes.create_unicode_buffer(260)
                kernel32.GetModuleFileNameW(mod, buf, 260)
                name = os.path.basename(buf.value)
        module_of[tid] = name
    return module_of[tid]


def thread_cpu():
    """{thread id: CPU seconds} for this process, noting each thread's start DLL."""
    snap = kernel32.CreateToolhelp32Snapshot(0x4, 0)  # TH32CS_SNAPTHREAD
    te = THREADENTRY32()
    te.dwSize = ctypes.sizeof(te)
    out = {}
    ok = kernel32.Thread32First(snap, ctypes.byref(te))
    while ok:
        if te.th32OwnerProcessID == os.getpid():
            h = kernel32.OpenThread(0x0040, False, te.th32ThreadID)  # THREAD_QUERY_INFORMATION
            if h:
                created, exited, kernel, user = (ctypes.c_ulonglong() for _ in range(4))
                kernel32.GetThreadTimes(h, ctypes.byref(created), ctypes.byref(exited), ctypes.byref(kernel),
                                        ctypes.byref(user))
                _start_module(h, te.th32ThreadID)
                out[te.th32ThreadID] = (kernel.value + user.value) / 1e7
                kernel32.CloseHandle(h)
        ok = kernel32.Thread32Next(snap, ctypes.byref(te))
    kernel32.CloseHandle(snap)
    return out


def snapshot():
    t = os.times()
    work = {}
    for owner, b in blocks.values():
        try:
            work[f'{owner} / {b.alias()}'] = b.pc_work_time_total()
        except RuntimeError:
            pass
    return time.time(), t.user + t.system, main_thread_cpu(), work, dict(cpu), thread_cpu()


def report(a, b):
    dt = b[0] - a[0]
    tps = gr.high_res_timer_tps()
    process, main = (b[1] - a[1]) / dt, (b[2] - a[2]) / dt
    work = {k: (v - a[3].get(k, 0)) / tps / dt for k, v in b[3].items()}
    py = {k: (v - a[4].get(k, 0)) / dt for k, v in b[4].items()}
    threads = {t: (v - a[5].get(t, v)) / dt for t, v in b[5].items()}
    by_module = collections.Counter()
    for t, v in threads.items():
        by_module[module_of.get(t, '?')] += v
    py_blocks = sum(v for k, v in py.items() if k.endswith('.work'))
    cpp = sum(v for k, v in work.items()
              if k.split(' / ')[-1].rstrip('0123456789') not in PYTHON_BLOCK_NAMES | {'source'})
    stations = sorted({k.split(' / ')[0].split('_')[-1] for k in work if k.startswith('fm_station')})
    kinds = collections.Counter()
    for k, v in work.items():
        kinds[k.split(' / ')[-1].rstrip('0123456789')] += v
    lines = [f"FM-Modmon-ms CPU profile, {time.strftime('%Y-%m-%d %H:%M')}",
             f'{platform.processor()}, {os.cpu_count()} logical processors',
             f"receivers: {', '.join(stations)}",
             '',
             f'whole process      {process:5.2f} cores ({process / os.cpu_count():.0%} of the PC)',
             f'Qt (GUI) thread    {main:5.2f}',
             f'Python blocks      {py_blocks:5.2f}',
             f'C++ blocks (work)  {cpp:5.2f}',
             f'rest               {process - main - py_blocks - cpp:5.2f}  (block threads waking, buffers, SDR driver)',
             '',
             'by block type (wall time in work(), cores)']
    lines += [f'  {v:6.3f}  {k}' for k, v in kinds.most_common(15)]
    lines += ['', 'Python block methods (CPU, cores, inclusive)']
    lines += [f'  {v:6.3f}  {k}' for k, v in sorted(py.items(), key=lambda kv: -kv[1])[:12]]
    lines += ['', f'threads by the DLL they started in (CPU, cores; {len(threads)} threads)']
    lines += [f'  {v:6.3f}  {k}' for k, v in by_module.most_common(8)]
    lines += ['', 'busiest threads (CPU, cores)']
    lines += [f'  {v:6.3f}  {module_of.get(t, "?")}' for t, v in sorted(threads.items(), key=lambda kv: -kv[1])[:10]]
    lines += ['', json.dumps({'process': process, 'main': main, 'work': work, 'python': py,
                              'threads': {f'{t} {module_of.get(t, "?")}': v for t, v in threads.items()}})]
    text = '\n'.join(lines) + '\n'
    with open(OUT, 'w', encoding='utf-8') as fh:
        fh.write(text)
    print(text.rsplit('\n\n', 1)[0])
    print(f'\nwritten to {OUT}', flush=True)  # os._exit doesn't flush


def measure():
    time.sleep(WARM_S)
    a = snapshot()
    time.sleep(WINDOW_S)
    report(a, snapshot())
    os._exit(0)  # without the monitor's shutdown: nothing it saves changes


threading.Thread(target=measure, daemon=True).start()
app.main()
