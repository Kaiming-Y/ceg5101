"""Small helpers shared by the live-demo panes (standard library only, Python 3.6+)."""
import csv
import io
import json
import os
import sys
import time

RED, GREEN, YELLOW, BLUE, ORANGE, GREY, BOLD, RESET = (
    '\033[31m', '\033[32m', '\033[33m', '\033[34m', '\033[38;5;208m', '\033[90m', '\033[1m', '\033[0m')
CASES = {'a': 'case a: h2 floods h3 (link s2-s3)',
         'b': 'case b: h2 floods h6 (link s2-s6, shared with h1->h6)',
         'c': 'case c: h5 floods h6 (via s5-s3-s6)'}


def wait_for(path, quiet=False):
    """Block until a file exists."""
    shown = False
    while not os.path.exists(path):
        if not quiet and not shown:
            print(GREY + 'waiting for ' + path + ' ...' + RESET, flush=True)
            shown = True
        time.sleep(0.5)


def follow(path):
    """Yield complete new lines of a growing file (like tail -F from the start)."""
    wait_for(path, quiet=True)
    with open(path, encoding='utf-8', errors='replace') as f:
        buf = ''
        while True:
            chunk = f.read()
            if not chunk:
                time.sleep(0.3)
                continue
            buf += chunk
            *lines, buf = buf.split('\n')
            for line in lines:
                yield line


def timeline(out):
    try:
        with open(os.path.join(out, 'timeline.json'), encoding='utf-8') as f:
            return json.load(f)
    except Exception:
        return {'marks': []}


def t0(out):
    for m in timeline(out)['marks']:
        if m['name'] == 'baseline_start':
            return m['t']
    return None


def phase(out, now=None):
    """Return a human-readable phase of the experiment timeline."""
    now = now or time.time()
    marks = timeline(out)['marks']
    names = [m['name'] for m in marks]
    if 'end' in names:
        return 'finished'
    if 'baseline_start' not in names:
        return 'starting (topology discovery, pingall)'
    last = None
    for m in marks:
        if m.get('scenario') and m['name'] in ('attack_start', 'attack_end'):
            last = m
    if last is None:
        return 'baseline: normal traffic'
    case = CASES.get(last['scenario'], last['scenario'])
    if last['name'] == 'attack_start':
        return 'FLOOD  ' + case
    return 'recovery after ' + case.split(':')[0]


def last_rows(path, n_bytes=200000):
    """Read the tail of a CSV with its header; returns list of dicts."""
    if not os.path.exists(path):
        return []
    with open(path, encoding='utf-8', errors='replace') as f:
        header = f.readline()
        f.seek(0, 2)
        size = f.tell()
        f.seek(max(len(header), size - n_bytes))
        tail = f.read()
    if size > n_bytes:
        tail = tail.split('\n', 1)[-1]
    return list(csv.DictReader(io.StringIO(header + tail)))


def rel(t, base):
    return '%6.1f s' % (float(t) - base) if base else time.strftime('%H:%M:%S', time.localtime(float(t)))


def out_dir_from_argv():
    if len(sys.argv) < 2:
        sys.exit('usage: %s <results/run-dir>' % sys.argv[0])
    return sys.argv[1]
