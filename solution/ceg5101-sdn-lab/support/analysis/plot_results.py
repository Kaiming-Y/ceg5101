#!/usr/bin/env python3
"""
Turn one experiment run into the Task 5 figures and a summary table.

    python3 support/analysis/plot_results.py results/<run>

Writes into <run>/figures/:
    fig1_link_cost.png    normalised dynamic link cost C/C0 vs time (small multiples)
    fig2_packet_loss.png  h1->h6 packet loss (%) vs time
    fig3_throughput.png   h1->h6 throughput (Mbps) vs time
    fig4_overview.png     path + cost + loss + throughput + RTT on one time axis
    fig5_blocking.png     attack packets sent vs. reaching the victim (Task 2 check)
and <run>/summary.md (before / during / after table for every case).

Needs only matplotlib (no pandas).
"""

import csv
import datetime as dt
import json
import os
import re
import sys
import time
from collections import Counter, defaultdict

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt  # noqa: E402
from matplotlib.patches import Patch  # noqa: E402

# Reference palette (dataviz skill), light mode for a printed report.
SURFACE = '#fcfcfb'
INK = '#0b0b0b'
INK_2 = '#52514e'
MUTED = '#898781'
GRID = '#e1e0d9'
SERIES = ['#2a78d6', '#eb6834', '#1baf7a', '#6250d6']
WINDOW = '#efeee9'

WATCH = ('h1', 'h6')
# Links shown in the small multiples, with their role in the experiment.
COST_PANELS = [
    ('s1-s2', 'h1→h6 primary + backup path'),
    ('s2-s6', 'h1→h6 primary path · attacked in b'),
    ('s2-s3', 'h1→h6 backup path · attacked in a'),
    ('s3-s6', 'h1→h6 backup path · carries c'),
    ('s3-s5', 'carries c (Dijkstra path s5-s3-s6)'),
    ('s5-s6', 'nominal target of c'),
]
OVERVIEW_LINKS = ['s2-s6', 's2-s3', 's3-s6']


# ----------------------------------------------------------------------------
# Loading
# ----------------------------------------------------------------------------
def read_csv(path):
    if not os.path.exists(path):
        return []
    with open(path, newline='', encoding='utf-8') as f:
        return list(csv.DictReader(f))


IPERF_HDR = re.compile(r' on (\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}(?:\.\d+)?) \((\w+)\)')
IPERF_ROW = re.compile(r'\]\s+([\d.]+)-([\d.]+)\s+sec\s+[\d.]+\s+\w*Bytes\s+([\d.]+)\s+(\w?)bits/sec'
                       r'\s+[\d.]+\s+ms\s+(-?\d+)/\s*(\d+)')
UNIT = {'': 1e-6, 'K': 1e-3, 'M': 1.0, 'G': 1e3}


def read_iperf_server(path, fallback_start):
    """Per-second (t, throughput_mbps, loss_pct) from `iperf -s -u -i 1 -e`."""
    rows, start = [], None
    if not os.path.exists(path):
        return rows
    with open(path, encoding='utf-8') as f:
        for line in f:
            m = IPERF_HDR.search(line)
            if m and start is None:
                stamp, tz = m.groups()
                fmt = '%Y-%m-%d %H:%M:%S.%f' if '.' in stamp else '%Y-%m-%d %H:%M:%S'
                parsed = dt.datetime.strptime(stamp, fmt)
                if tz == 'UTC':
                    start = parsed.replace(tzinfo=dt.timezone.utc).timestamp()
                else:
                    start = time.mktime(parsed.timetuple()) + parsed.microsecond / 1e6
                if fallback_start and abs(start - fallback_start) > 5:
                    start = fallback_start
                continue
            m = IPERF_ROW.search(line)
            if not m:
                continue
            t0, t1, bw, unit, lost, total = m.groups()
            t0, t1 = float(t0), float(t1)
            if t1 - t0 > 1.5:                        # final summary line
                continue
            lost, total = max(int(lost), 0), int(total)
            loss = 100.0 * lost / total if total else 100.0
            rows.append((t1, float(bw) * UNIT.get(unit, 1.0), loss))
    base = start if start is not None else (fallback_start or 0)
    return [(base + t, bw, loss) for t, bw, loss in rows]


PING_ROW = re.compile(r'^\[(\d+\.\d+)\].*time=([\d.]+) ms')


def read_ping(path):
    out = []
    if os.path.exists(path):
        with open(path, encoding='utf-8') as f:
            for line in f:
                m = PING_ROW.match(line)
                if m:
                    out.append((float(m.group(1)), float(m.group(2))))
    return out


def read_capture(path):
    """Timestamps of attacker packets seen by tcpdump on the victim."""
    out = []
    if os.path.exists(path):
        with open(path, encoding='utf-8') as f:
            for line in f:
                head = line.split(' ', 1)[0]
                try:
                    out.append(float(head))
                except ValueError:
                    pass
    return out


def load_run(run):
    ctrl = os.path.join(run, 'controller')
    with open(os.path.join(run, 'timeline.json'), encoding='utf-8') as f:
        timeline = json.load(f)
    marks = {m['name']: m['t'] for m in timeline['marks'] if 'scenario' not in m}

    links = defaultdict(list)                   # name -> [(t, norm_cost, cost, rate, anomaly)]
    for r in read_csv(os.path.join(ctrl, 'links.csv')):
        links[r['link']].append((float(r['t']), float(r['norm_cost']), float(r['cost']),
                                 float(r['rate_mbps']), int(r['anomaly'])))
    paths = defaultdict(list)                   # (src, dst) -> [(t, path, cost)]
    for r in read_csv(os.path.join(ctrl, 'paths.csv')):
        paths[(r['src'], r['dst'])].append((float(r['t']), r['path'], float(r['cost'])))
    events = [dict(r, t=float(r['t']), detail=json.loads(r['detail'] or '{}'))
              for r in read_csv(os.path.join(ctrl, 'events.csv'))]
    counters = read_csv(os.path.join(run, 'attack_counters.csv'))
    captures = {}
    for sc in timeline['scenarios']:
        captures[sc['id']] = read_capture(os.path.join(run, 'victim_capture_%s.txt' % sc['id']))
    t_end = marks.get('end', float('inf'))
    events = [e for e in events if e['t'] <= t_end]          # drop teardown noise
    return {
        'timeline': timeline,
        't0': marks.get('baseline_start') or marks.get('iperf_start'),
        'links': links,
        'paths': paths,
        'events': events,
        'iperf': read_iperf_server(os.path.join(run, 'iperf_server.txt'), marks.get('iperf_start')),
        'ping': read_ping(os.path.join(run, 'ping_h1_h6.txt')),
        'counters': counters,
        'captures': captures,
        'meta': json.load(open(os.path.join(run, 'meta.json'), encoding='utf-8')) if os.path.exists(
            os.path.join(run, 'meta.json')) else {},
    }


# ----------------------------------------------------------------------------
# Plot helpers
# ----------------------------------------------------------------------------
def style_axes(ax, ylabel=None):
    ax.set_facecolor(SURFACE)
    for side in ('top', 'right'):
        ax.spines[side].set_visible(False)
    for side in ('left', 'bottom'):
        ax.spines[side].set_color(GRID)
    ax.tick_params(colors=MUTED, labelcolor=INK_2, labelsize=8, length=0)
    ax.grid(axis='y', color=GRID, linewidth=0.6)
    ax.set_axisbelow(True)
    if ylabel:
        ax.set_ylabel(ylabel, color=INK_2, fontsize=9)


def link_failures(d):
    """[(t_down, t_up, link)] from timeline marks (--fail-link runs)."""
    marks = d['timeline']['marks']
    downs = [m for m in marks if m['name'] == 'link_down']
    ups = [m for m in marks if m['name'] == 'link_up']
    return [(dn['t'], up['t'], dn.get('link', '')) for dn, up in zip(downs, ups)]


def shade_attacks(ax, d, label=True):
    t0 = d['t0']
    for a, b, link in link_failures(d):
        ax.axvspan(a - t0, b - t0, facecolor='none', edgecolor=MUTED, hatch='///', linewidth=0, zorder=0)
        if label:
            ax.text((a + b) / 2 - t0, 1.0, '%s down' % link, transform=ax.get_xaxis_transform(),
                    ha='center', va='bottom', fontsize=7.5, color=INK_2)
    for sc in d['timeline']['scenarios']:
        a, b = sc['attack_start'] - t0, sc['attack_end'] - t0
        ax.axvspan(a, b, color=WINDOW, zorder=0, linewidth=0)
        if label:
            ax.text((a + b) / 2, 1.0, '%s: %s→%s' % (sc['id'], sc['attacker'], sc['victim']),
                    transform=ax.get_xaxis_transform(), ha='center', va='bottom',
                    fontsize=7.5, color=INK_2)


def mark_events(ax, d, kinds=('block',)):
    t0 = d['t0']
    for e in d['events']:
        if e['event'] == 'block' and 'block' in kinds:
            ax.axvline(e['t'] - t0, color=INK_2, linewidth=0.8, linestyle=(0, (4, 3)), zorder=1)
        if e['event'] == 'reroute' and 'reroute' in kinds and (e['src'], e['dst']) == WATCH:
            ax.axvline(e['t'] - t0, color=SERIES[3], linewidth=0.8, linestyle=(0, (1, 2)), zorder=1)


def new_fig(w, h):
    fig = plt.figure(figsize=(w, h), dpi=150)
    fig.patch.set_facecolor(SURFACE)
    return fig


def footnote(fig, text):
    fig.text(0.01, 0.005, text, fontsize=7, color=MUTED, ha='left', va='bottom')


EVENT_NOTE = 'shaded = flood active · hatched = link down · dashed = source blocked · dotted = h1→h6 rerouted'


# ----------------------------------------------------------------------------
# Figures
# ----------------------------------------------------------------------------
def fig_link_cost(d, out):
    fig = new_fig(10, 6.2)
    axes = fig.subplots(3, 2, sharex=True, sharey=True)
    t0 = d['t0']
    ymax = max([p[1] for s in d['links'].values() for p in s] + [1.5])
    for ax, (name, role) in zip(axes.flat, COST_PANELS):
        style_axes(ax)
        shade_attacks(ax, d, label=ax in axes[0])
        mark_events(ax, d, ('block', 'reroute'))
        series = d['links'].get(name, [])
        if series:
            ax.plot([p[0] - t0 for p in series], [p[1] for p in series],
                    color=SERIES[0], linewidth=1.6, solid_capstyle='round', zorder=3)
        ax.axhline(1.0, color=MUTED, linewidth=0.6, zorder=2)
        ax.set_title('%s  ·  %s' % (name, role), loc='left', fontsize=8.5, color=INK, pad=12 if ax in axes[0] else 4)
        ax.set_ylim(0.8, ymax * 1.08)
    for ax in axes[:, 0]:
        ax.set_ylabel('C(t) / C0', color=INK_2, fontsize=9)
    for ax in axes[-1]:
        ax.set_xlabel('time since baseline start (s)', color=INK_2, fontsize=9)
    fig.suptitle('Dynamic link cost (normalised) vs time', x=0.01, ha='left', fontsize=11, color=INK)
    footnote(fig, EVENT_NOTE + ' · grey line = static cost C0')
    fig.tight_layout(rect=(0, 0.02, 1, 0.97))
    fig.savefig(os.path.join(out, 'fig1_link_cost.png'), facecolor=SURFACE)
    plt.close(fig)


def _single_series(d, out, fname, title, ylabel, idx, ylim=None):
    fig = new_fig(10, 3.4)
    ax = fig.subplots()
    style_axes(ax, ylabel)
    shade_attacks(ax, d)
    mark_events(ax, d, ('block', 'reroute'))
    t0 = d['t0']
    pts = d['iperf']
    if pts:
        ax.plot([p[0] - t0 for p in pts], [p[idx] for p in pts], color=SERIES[0],
                linewidth=1.6, marker='o', markersize=2.5, zorder=3)
    if ylim:
        ax.set_ylim(*ylim)
    ax.set_xlabel('time since baseline start (s)', color=INK_2, fontsize=9)
    ax.set_title(title, loc='left', fontsize=11, color=INK, pad=16)
    footnote(fig, EVENT_NOTE + ' · source: iperf UDP server report, 1 s intervals')
    fig.tight_layout(rect=(0, 0.04, 1, 1))
    fig.savefig(os.path.join(out, fname), facecolor=SURFACE)
    plt.close(fig)


def fig_overview(d, out):
    fig = new_fig(10, 9)
    axes = fig.subplots(5, 1, sharex=True, gridspec_kw={'height_ratios': [0.7, 2, 1.4, 1.4, 1.2]})
    t0 = d['t0']

    # (1) h1->h6 path band
    ax = axes[0]
    style_axes(ax)
    ax.grid(False)
    seq = d['paths'].get(WATCH, [])
    names = []
    for _, p, _ in seq:
        if p not in names:
            names.append(p)
    for i in range(len(seq)):
        t, p, _ = seq[i]
        t_next = seq[i + 1][0] if i + 1 < len(seq) else t + 2
        ax.barh(0, t_next - t, left=t - t0, height=0.6,
                color=SERIES[names.index(p) % len(SERIES)], linewidth=0)
    ax.set_yticks([])
    ax.set_title('h1→h6 path', loc='left', fontsize=9, color=INK, pad=14)
    handles = [Patch(color=SERIES[i % len(SERIES)], label=p) for i, p in enumerate(names)]
    ax.legend(handles=handles, loc='upper right', bbox_to_anchor=(1.0, 1.9), fontsize=7.5,
              frameon=False, labelcolor=INK_2, ncol=len(handles))
    shade_attacks(ax, d)

    # (2) normalised cost, three key links
    ax = axes[1]
    style_axes(ax, 'C(t) / C0')
    shade_attacks(ax, d, label=False)
    mark_events(ax, d, ('block', 'reroute'))
    for i, name in enumerate(OVERVIEW_LINKS):
        s = d['links'].get(name, [])
        if not s:
            continue
        x, y = [p[0] - t0 for p in s], [p[1] for p in s]
        ax.plot(x, y, color=SERIES[i], linewidth=1.6, label=name, zorder=3)
    ax.legend(loc='upper left', fontsize=7.5, frameon=False, labelcolor=INK_2, ncol=3)

    # (3) loss, (4) throughput
    pts = d['iperf']
    for ax, idx, label in ((axes[2], 2, 'loss (%)'), (axes[3], 1, 'Mbps')):
        style_axes(ax, label)
        shade_attacks(ax, d, label=False)
        mark_events(ax, d, ('block', 'reroute'))
        if pts:
            ax.plot([p[0] - t0 for p in pts], [p[idx] for p in pts], color=SERIES[0], linewidth=1.4, zorder=3)
    axes[2].set_title('h1→h6 packet loss', loc='left', fontsize=9, color=INK)
    axes[3].set_title('h1→h6 throughput', loc='left', fontsize=9, color=INK)

    # (5) RTT
    ax = axes[4]
    style_axes(ax, 'RTT (ms)')
    shade_attacks(ax, d, label=False)
    mark_events(ax, d, ('block', 'reroute'))
    if d['ping']:
        ax.plot([p[0] - t0 for p in d['ping']], [p[1] for p in d['ping']], color=SERIES[0],
                linewidth=0, marker='o', markersize=2, zorder=3)
    ax.set_title('h1→h6 ping RTT', loc='left', fontsize=9, color=INK)
    ax.set_xlabel('time since baseline start (s)', color=INK_2, fontsize=9)

    fig.suptitle('Anomaly-aware rerouting: overview', x=0.01, ha='left', fontsize=11, color=INK)
    footnote(fig, EVENT_NOTE)
    fig.tight_layout(rect=(0, 0.02, 1, 0.98))
    fig.savefig(os.path.join(out, 'fig4_overview.png'), facecolor=SURFACE)
    plt.close(fig)


def _per_second(times, start, end):
    n = int(end - start) + 1
    bins = [0] * n
    for t in times:
        i = int(t - start)
        if 0 <= i < n:
            bins[i] += 1
    return list(range(n)), bins


def fig_blocking(d, out):
    scs = d['timeline']['scenarios']
    if not scs:
        return
    fig = new_fig(10, 2.8 * len(scs))
    axes = fig.subplots(len(scs), 1, squeeze=False)[:, 0]
    for ax, sc in zip(axes, scs):
        style_axes(ax, 'packets / s')
        a, b = sc['attack_start'], sc['attack_end']
        # attacker side: tx counter deltas (includes its 1 pps ping, negligible)
        rows = [r for r in d['counters'] if r['scenario'] == sc['id']]
        xs, sent = [], []
        for r0, r1 in zip(rows, rows[1:]):
            dt_ = float(r1['t']) - float(r0['t'])
            if dt_ > 0:
                xs.append(float(r1['t']) - a)
                sent.append((int(r1['attacker_tx_packets']) - int(r0['attacker_tx_packets'])) / dt_)
        x2, recv = _per_second(d['captures'].get(sc['id'], []), a, b + 2)
        ax.plot(xs, sent, color=SERIES[1], linewidth=1.6, label='sent by %s' % sc['attacker'], zorder=3)
        ax.plot(x2, recv, color=SERIES[0], linewidth=1.6, label='reaching %s' % sc['victim'], zorder=3)
        for e in d['events']:
            if e['event'] == 'block' and e['src'] == sc['attacker'] and a <= e['t'] <= b + 5:
                ax.axvline(e['t'] - a, color=INK_2, linewidth=0.8, linestyle=(0, (4, 3)))
                ax.text(e['t'] - a, 1.0, ' blocked', transform=ax.get_xaxis_transform(),
                        fontsize=7.5, color=INK_2, va='top')
        ax.set_title('case %s: %s → %s' % (sc['id'], sc['attacker'], sc['victim']), loc='left',
                     fontsize=9, color=INK)
        ax.legend(loc='center right', fontsize=7.5, frameon=False, labelcolor=INK_2)
        ax.set_xlim(-1, b - a + 2)
    axes[-1].set_xlabel('time since flood start (s)', color=INK_2, fontsize=9)
    fig.suptitle('Blocking check: flood packets sent vs. reaching the victim', x=0.01, ha='left',
                 fontsize=11, color=INK)
    footnote(fig, 'sent = attacker interface tx counter · reaching = tcpdump on the victim, ICMP from attacker only')
    fig.tight_layout(rect=(0, 0.02, 1, 0.97))
    fig.savefig(os.path.join(out, 'fig5_blocking.png'), facecolor=SURFACE)
    plt.close(fig)


# ----------------------------------------------------------------------------
# Summary table
# ----------------------------------------------------------------------------
def _window(pts, a, b):
    sel = [p for p in pts if a <= p[0] < b]
    if not sel:
        return '–', '–'
    return ('%.2f' % (sum(p[1] for p in sel) / len(sel)), '%.2f' % (sum(p[2] for p in sel) / len(sel)))


def _path_at(seq, t):
    best = None
    for ts, p, c in seq:
        if ts <= t:
            best = (p, c)
        else:
            break
    return best or ('–', 0)


def _dominant_path(seq, a, b):
    c = Counter(p for t, p, _ in seq if a <= t < b)
    return ', '.join('%s (%d%%)' % (p, 100 * n / sum(c.values())) for p, n in c.most_common()) or '–'


def summary(d, out_path):
    seq = d['paths'].get(WATCH, [])
    lines = ['# Experiment summary', '']
    m = d['meta']
    if m:
        lines += ['- datapath: `%s`, link delay emulated: `%s`' % (m.get('datapath'), m.get('delay_emulated')),
                  '- args: `%s`' % json.dumps({k: v for k, v in m.get('args', {}).items()
                                               if k in ('scenarios', 'baseline', 'attack', 'recover',
                                                        'iperf_rate', 'attack_size')}), '']
    lines += ['| case | detect delay (s) | blocked | anomalous links | h1→h6 path before | '
              'during | after | Mbps b/d/a | loss % b/d/a | attack pkts at victim before block · pps after |',
              '|---|---|---|---|---|---|---|---|---|---|']
    for sc in d['timeline']['scenarios']:
        a, b, r = sc['attack_start'], sc['attack_end'], sc['recover_end']
        blocks = [e for e in d['events'] if e['event'] == 'block' and a <= e['t'] <= b + 5
                  and e['src'] == sc['attacker']]
        delay = '%.1f' % (blocks[0]['t'] - a) if blocks else 'not detected'
        links = ', '.join(blocks[0]['detail'].get('links', [])) if blocks else '–'
        before = _window(d['iperf'], a - 15, a)
        during = _window(d['iperf'], a, b)
        after = _window(d['iperf'], r - 15, r)
        cap = d['captures'].get(sc['id'], [])
        if blocks:
            tb = blocks[0]['t']
            n_before = sum(1 for t in cap if t < tb)
            after_s = max(b - (tb + 1), 1e-6)
            pps_after = sum(1 for t in cap if t >= tb + 1) / after_s
            rx_s = '%d · %.1f' % (n_before, pps_after)
        else:
            rx_s = '%d · –' % len(cap)
        lines.append('| %s (%s→%s, %s) | %s | %s | %s | %s | %s | %s | %s / %s / %s | %s / %s / %s | %s |' % (
            sc['id'], sc['attacker'], sc['victim'], sc['link'], delay,
            'yes' if blocks else 'no', links,
            _path_at(seq, a - 0.5)[0], _dominant_path(seq, a, b), _path_at(seq, r)[0],
            before[0], during[0], after[0], before[1], during[1], after[1], rx_s))

    for a, b, link in link_failures(d):
        t_end = max([m['t'] for m in d['timeline']['marks'] if m['name'] == 'end'] or [b + 45])
        after_end = min(b + 45, t_end - 2)
        lines += ['', '## Link failure: %s' % link, '',
                  '| h1→h6 path before | while down | after restore | Mbps b/d/a | loss % b/d/a |',
                  '|---|---|---|---|---|']
        bf, du, af = _window(d['iperf'], a - 15, a), _window(d['iperf'], a, b), _window(d['iperf'], after_end - 15, after_end)
        lines.append('| %s | %s | %s | %s / %s / %s | %s / %s / %s |' % (
            _path_at(seq, a - 0.5)[0], _dominant_path(seq, a, b), _path_at(seq, after_end)[0],
            bf[0], du[0], af[0], bf[1], du[1], af[1]))
    lines += ['', '## Events (relative to baseline start)', '', '| t (s) | event | src→dst | detail |',
              '|---|---|---|---|']
    for e in d['events']:
        if e['event'] in ('block', 'unblock', 'reroute', 'link_down'):
            if e['event'] == 'reroute' and (e['src'], e['dst']) != WATCH:
                continue
            lines.append('| %.1f | %s | %s→%s | %s |' % (e['t'] - d['t0'], e['event'], e['src'],
                                                         e['dst'] or '·', json.dumps(e['detail'])))
    lines += ['', 'b/d/a = 15 s before the flood / during the flood / last 15 s of recovery.',
              'Only h1→h6 reroutes are listed; all reroutes are in controller/events.csv.', '']
    with open(out_path, 'w', encoding='utf-8') as f:
        f.write('\n'.join(lines))


def main():
    if len(sys.argv) != 2:
        sys.exit(__doc__)
    run = os.path.abspath(sys.argv[1])
    d = load_run(run)
    out = os.path.join(run, 'figures')
    os.makedirs(out, exist_ok=True)
    fig_link_cost(d, out)
    _single_series(d, out, 'fig2_packet_loss.png', 'h1→h6 packet loss vs time', 'packet loss (%)', 2,
                   ylim=(-2, 102))
    _single_series(d, out, 'fig3_throughput.png', 'h1→h6 throughput vs time', 'throughput (Mbps)', 1)
    fig_overview(d, out)
    fig_blocking(d, out)
    summary(d, os.path.join(run, 'summary.md'))
    print('figures ->', out)
    print('summary ->', os.path.join(run, 'summary.md'))


if __name__ == '__main__':
    main()
