"""Run every test suite (tests/*_test.py and verify_meas.py) in parallel, each in
its own process as when run alone, and print each one's result and time, slowest
first. Exits non-zero if any fails, after printing its failing lines.

    C:\\ProgramData\\radioconda\\python.exe tests\\run_all.py              # all of them
    C:\\ProgramData\\radioconda\\python.exe tests\\run_all.py state alarm  # those whose name has a word
    C:\\ProgramData\\radioconda\\python.exe tests\\run_all.py -j 1         # one at a time
"""
import argparse
import concurrent.futures
import glob
import os
import subprocess
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))


def suites(words):
    found = sorted(glob.glob(os.path.join(HERE, '*_test.py'))) + [os.path.join(HERE, 'verify_meas.py')]
    return [p for p in found if not words or any(w in os.path.basename(p) for w in words)]


def run(path):
    t0 = time.monotonic()
    proc = subprocess.run([sys.executable, path], cwd=HERE, capture_output=True, text=True, encoding='utf-8',
                          errors='replace', env={**os.environ, 'QT_QPA_PLATFORM': 'offscreen'})
    return path, proc.returncode, time.monotonic() - t0, proc.stdout + proc.stderr


def main():
    ap = argparse.ArgumentParser(description=__doc__.split('\n\n')[0])
    ap.add_argument('words', nargs='*', help='run only the suites whose file name contains one of these')
    ap.add_argument('-j', '--jobs', type=int, default=max(1, min(8, (os.cpu_count() or 2) // 2)),
                    help='suites at a time (default: half the CPU threads, at most 8)')
    args = ap.parse_args()
    todo = suites(args.words)
    if not todo:
        print('no suite matches')
        return 2
    t0 = time.monotonic()
    with concurrent.futures.ThreadPoolExecutor(args.jobs) as pool:
        results = list(pool.map(run, todo))
    failed = [r for r in results if r[1]]
    for path, code, secs, _ in sorted(results, key=lambda r: -r[2]):
        print(f"{'ok  ' if not code else 'FAIL'}  {secs:6.1f} s  {os.path.basename(path)}")
    for path, code, _, out in failed:
        lines = out.splitlines()
        bad = [l for l in lines if l.startswith(('WRONG', 'FAIL', 'Traceback')) or 'Error' in l]
        print(f'\n--- {os.path.basename(path)} (exit {code})')
        print('\n'.join((bad or lines)[-25:]))
    print(f'\n{len(results) - len(failed)} of {len(results)} suites passed in {time.monotonic() - t0:.0f} s '
          f'({args.jobs} at a time)')
    return 1 if failed else 0


if __name__ == '__main__':
    sys.exit(main())
