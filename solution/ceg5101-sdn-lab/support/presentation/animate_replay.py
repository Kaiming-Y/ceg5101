#!/usr/bin/env python3
"""Replay of run R1 (results/validation-abc) as a 1920x1080 animation.

    python3 support/presentation/animate_replay.py      (needs matplotlib and ffmpeg)

Inputs (read only):
    results/validation-abc/controller/{links,paths,events}.csv
    results/validation-abc/iperf_server.txt
    results/validation-abc/timeline.json
Outputs:
    presentation/assets/video/replay_r1.mp4          (30 fps, H.264, yuv420p, faststart)
    presentation/assets/figures/replay_r1_still_1..4.png   (t = 60, 114, 135, 200 s)

Link colour/width follow C/C0 of the latest 2.4 s controller sample (step, no
interpolation). The h1->h6 path is drawn from paths.csv, attack arrows follow
the attacker's installed path, banners come from events.csv.
"""
import argparse
import bisect
import importlib.util
import os
import sys

import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt  # noqa: E402
from matplotlib import animation  # noqa: E402
from matplotlib.colors import LinearSegmentedColormap, to_rgb  # noqa: E402
from matplotlib.patches import FancyArrowPatch, FancyBboxPatch, Rectangle  # noqa: E402
from matplotlib.lines import Line2D  # noqa: E402

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))
RUN = os.path.join(ROOT, 'results', 'validation-abc')
VIDEO = os.path.join(ROOT, 'presentation', 'assets', 'video', 'replay_r1.mp4')
FIGDIR = os.path.join(ROOT, 'presentation', 'assets', 'figures')

spec = importlib.util.spec_from_file_location('plot_results', os.path.join(ROOT, 'support', 'analysis', 'plot_results.py'))
pr = importlib.util.module_from_spec(spec)
spec.loader.exec_module(pr)

# ----------------------------------------------------------------------------
# palette (same as the slide figures)
# ----------------------------------------------------------------------------
MAIN = '#2a78d6'
DETOUR = '#eb6834'
ATTACK = '#d62728'
GREY = '#b9b7b0'
BAND = '#efeee9'
BG = '#fcfcfb'
INK = '#0b0b0b'
INK2 = '#52514e'
GRIDC = '#e1e0d9'
OK = '#2e8b57'

FPS = 30
W, H = 1920, 1080

plt.rcParams.update({
    'font.family': ['Inter', 'DejaVu Sans'],
    'font.size': 18,
    'text.color': INK,
    'axes.edgecolor': GRIDC,
    'axes.labelcolor': INK2,
    'xtick.color': INK2,
    'ytick.color': INK2,
    'figure.facecolor': BG,
    'axes.facecolor': BG,
    'savefig.facecolor': BG,
})

# ----------------------------------------------------------------------------
# data
# ----------------------------------------------------------------------------
D = pr.load_run(RUN)
T0 = D['t0']


def rel(t):
    return t - T0


SCN = {s['id']: s for s in D['timeline']['scenarios']}
EVENTS = [dict(e, r=rel(e['t'])) for e in D['events']]

# link samples: name -> (times[], norm[], anomaly[])
LINK_TS = {}
for name, rows in D['links'].items():
    LINK_TS[name] = ([rel(r[0]) for r in rows], [r[1] for r in rows], [r[4] for r in rows])
C0 = {}
for r in pr.read_csv(os.path.join(RUN, 'controller', 'links.csv')):
    C0.setdefault(r['link'], int(float(r['c0'])))


def path_series(src, dst):
    rows = D['paths'][(src, dst)]
    return [rel(r[0]) for r in rows], [r[1] for r in rows], [r[2] for r in rows]


P16 = path_series('h1', 'h6')
ATT_PATH = {}
for k, sc in SCN.items():
    ts, ps, _ = path_series(sc['attacker'], sc['victim'])
    i = max(bisect.bisect_right(ts, rel(sc['attack_start'])) - 1, 0)
    ATT_PATH[k] = ps[i]

# per-second h1->h6 iperf rows: interval [t-1, t)
SEC = [(rel(t) - 1.0, bw, loss) for t, bw, loss in D['iperf']]
SEC_T = np.array([s[0] for s in SEC])
SEC_BW = np.array([s[1] for s in SEC])
SEC_LOSS = np.array([s[2] for s in SEC])
RUN_END = float(SEC_T[-1] + 1.0)


def step_at(ts, vals, t, default=None):
    i = bisect.bisect_right(ts, t) - 1
    return vals[i] if i >= 0 else default


def link_state(name, t):
    ts, norm, anom = LINK_TS[name]
    i = bisect.bisect_right(ts, t) - 1
    if i < 0:
        return 1.0, 0
    return norm[i], anom[i]


def h16_path(t):
    return step_at(P16[0], P16[1], t, P16[1][0])


def flood(k):
    s = SCN[k]
    return rel(s['attack_start']), rel(s['attack_end'])


def first_event(kind, src, a, b, dst=None):
    for e in EVENTS:
        if e['event'] == kind and e['src'] == src and a <= e['r'] <= b and (dst is None or e['dst'] == dst):
            return e
    return None


BLOCK, UNBLOCK = {}, {}
for k, sc in SCN.items():
    a, b = flood(k)
    BLOCK[k] = first_event('block', sc['attacker'], a, b + 5)
    UNBLOCK[k] = first_event('unblock', sc['attacker'], BLOCK[k]['r'], rel(sc['recover_end']) + 5)
RR16 = [e for e in EVENTS if e['event'] == 'reroute' and (e['src'], e['dst']) == ('h1', 'h6')]
T_BLOCK_B = BLOCK['b']['r']
# freeze on the first frame that already shows the block-time link sample and path
_ts_s26 = LINK_TS['s2-s6'][0]
T_FREEZE = max(T_BLOCK_B, _ts_s26[bisect.bisect_left(_ts_s26, T_BLOCK_B - 0.5)], P16[0][bisect.bisect_left(P16[0], T_BLOCK_B - 0.5)]) + 0.02


def fmt_int(x):
    return '{:,}'.format(int(round(x)))


def reroutes_between(a, b):
    return [e for e in EVENTS if e['event'] == 'reroute' and a <= e['r'] <= b]


# banners: (run time, tag, main line, detail line, colour)
SHARED = {'a': 'h1\u2192h6 (s1-s2-s6) does not use s2-s3',
          'b': 's2-s6 is also on h1\u2192h6 (s1-s2-s6)',
          'c': 'h1\u2192h6 shares only h6\u2019s access link with it'}
BANNERS = []
for k in ('a', 'b', 'c'):
    sc = SCN[k]
    fa, fb = flood(k)
    att, vic = sc['attacker'], sc['victim']
    bl, ub = BLOCK[k], UNBLOCK[k]
    flagged = ', '.join(bl['detail']['links'])
    BANNERS.append((fa, 'FLOOD', 'ICMP flood %s \u2192 %s along %s' % (att, vic, ATT_PATH[k]), SHARED[k], ATTACK))
    moved = [e for e in reroutes_between(bl['r'] - 0.01, bl['r'] + 0.05) if e['detail'].get('reason') == 'anomaly']
    rr = [e for e in moved if (e['src'], e['dst']) == ('h1', 'h6')]
    rate = '%s pkt/s > T = %s' % (fmt_int(bl['detail']['pps']), fmt_int(bl['detail']['threshold']))
    if rr:
        e = rr[0]
        BANNERS.append((bl['r'], 'BLOCK + REROUTE', '%s blocked \u00b7 h1\u2192h6 moved to %s' % (att, e['detail']['new']),
                        '%s \u00b7 same control step \u00b7 stay %.1f vs move %.1f'
                        % (rate, e['detail']['old_cost'], e['detail']['new_cost']), ATTACK))
    else:
        BANNERS.append((bl['r'], 'BLOCK', '%s blocked \u00b7 h1\u2192h6 stays on %s' % (att, h16_path(bl['r'])),
                        '%s \u00b7 flagged %s \u00b7 %d other flows rerouted' % (rate, flagged, len(moved)),
                        ATTACK))
    BANNERS.append((fb, 'FLOOD ENDS', 'Flood stops \u00b7 %s stays blocked until it is quiet' % att,
                    'drop rule and flagged links held for the quiet period', INK2))
    back = [e for e in RR16 if abs(e['r'] - ub['r']) < 0.1]
    if back:
        BANNERS.append((ub['r'], 'UNBLOCK', '%s unblocked \u00b7 h1\u2192h6 back on %s' % (att, back[0]['detail']['new']),
                        'after %.0f s quiet \u00b7 path cost %.1f' % (ub['detail']['quiet_s'], back[0]['detail']['new_cost']),
                        OK))
    else:
        BANNERS.append((ub['r'], 'UNBLOCK', '%s unblocked after %.0f s quiet' % (att, ub['detail']['quiet_s']),
                        'flagged links back to \u00d71 \u00b7 h1\u2192h6 never moved', OK))
BANNERS.sort(key=lambda b: b[0])
BANNER_T = [b[0] for b in BANNERS]


def phase(t):
    for k in ('c', 'b', 'a'):
        if t >= flood(k)[0] - 2.0:
            sc = SCN[k]
            return k, 'Case %s \u00b7 %s floods %s (target link %s)' % (k, sc['attacker'], sc['victim'], sc['link'])
    return None, 'Baseline · h1→h6 UDP 10 Mbps (≈890 pkt/s)'


# ----------------------------------------------------------------------------
# time map: video second -> run second (piecewise linear, one freeze)
# ----------------------------------------------------------------------------
TITLE_S = 1.5
END_S = 1.2
SEGMENTS = [  # (run_from, run_to, video_seconds); run_from == run_to is a freeze
    (0.0, 37.0, 1.4),
    (37.0, 82.0, 5.0),
    (82.0, 109.0, 1.0),
    (109.0, T_FREEZE, 2.2),
    (T_FREEZE, T_FREEZE, 2.0),
    (T_FREEZE, 155.0, 4.4),
    (155.0, 181.0, 0.8),
    (181.0, 227.0, 5.0),
    (227.0, RUN_END, 0.6),
]
PLAY_S = sum(s[2] for s in SEGMENTS)
TOTAL_S = TITLE_S + PLAY_S + END_S


def run_time(v):
    """Return (run time, speed factor, frozen) for video time v."""
    if v < TITLE_S:
        return 0.0, 0.0, False
    u = v - TITLE_S
    for a, b, d in SEGMENTS:
        if u < d:
            if a == b:
                return a, 0.0, True
            return a + (b - a) * u / d, (b - a) / d, False
        u -= d
    return RUN_END, 0.0, False


# ----------------------------------------------------------------------------
# geometry
# ----------------------------------------------------------------------------
POS = {'s1': (250, 220), 's2': (450, 220), 's3': (650, 220),
       's4': (250, 420), 's5': (450, 420), 's6': (650, 420),
       'h1': (250, 105), 'h2': (450, 105), 'h3': (650, 105),
       'h4': (250, 535), 'h5': (450, 535), 'h6': (650, 535)}
HOST_SW = {'h%d' % i: 's%d' % i for i in range(1, 7)}
LINKS = sorted(C0)
LABEL_AT = {'s1-s5': 0.27, 's2-s4': 0.73, 's2-s6': 0.27, 's3-s5': 0.73}
CMAP = LinearSegmentedColormap.from_list('cost', [GREY, '#e8a33d', ATTACK])


def key(u, v):
    a, b = sorted((u, v), key=lambda n: (n[0] != 's', n))
    return a + '-' + b if a[0] == b[0] == 's' else None


def unit_normal(u, v):
    """Normal of the canonical (sorted) orientation of edge u-v, pointing 'left'."""
    a, b = sorted((u, v))
    (x0, y0), (x1, y1) = POS[a], POS[b]
    dx, dy = x1 - x0, y1 - y0
    n = np.hypot(dx, dy)
    return np.array([-dy / n, dx / n])


def cost_style(norm):
    f = float(np.clip((norm - 1.0) / 3.0, 0.0, 1.0))
    return CMAP(f), 3.5 + 10.5 * f


def nodes_of(path):
    return path.split('-')


# ----------------------------------------------------------------------------
# figure
# ----------------------------------------------------------------------------
fig = plt.figure(figsize=(W / 100, H / 100), dpi=100)


def px(x0, y0, w, h):
    """Axes rectangle from top-left pixel coordinates."""
    return [x0 / W, 1 - (y0 + h) / H, w / W, h / H]


ax = fig.add_axes(px(20, 175, 1120, 860))
ax.set_xlim(95, 805)
ax.set_ylim(612, 48)
ax.set_aspect('equal')
ax.axis('off')

# header
fig.text(40 / W, 1 - 46 / H, 'Replay of run R1 from controller logs', fontsize=30, fontweight='bold', va='center')
fig.text(40 / W, 1 - 88 / H, 'Link colour and width = C / C₀ from the controller’s 2.4 s samples · '
         'h1→h6 path from its installed flows · loss from h6’s iperf report',
         fontsize=17, color=INK2, va='center')
clock_txt = fig.text(1880 / W, 1 - 46 / H, '', fontsize=30, ha='right', va='center', family='DejaVu Sans Mono')
speed_txt = fig.text(1880 / W, 1 - 88 / H, '', fontsize=18, ha='right', va='center', color=INK2)
phase_txt = fig.text(40 / W, 1 - 128 / H, '', fontsize=22, va='center', fontweight='bold', color=INK)

# banner
banner_box = FancyBboxPatch((40 / W, 1 - 222 / H), 1110 / W, 74 / H, boxstyle='round,pad=0.004,rounding_size=0.006',
                            transform=fig.transFigure, facecolor='white', edgecolor=GRIDC, linewidth=2, zorder=5)
fig.patches.append(banner_box)
banner_tag = fig.text(58 / W, 1 - 185 / H, '', fontsize=17, fontweight='bold', va='center', color='white', zorder=7,
                      bbox=dict(boxstyle='round,pad=0.35', facecolor=ATTACK, edgecolor='none'))
banner_txt = fig.text(318 / W, 1 - 169 / H, '', fontsize=20, va='center', zorder=7, fontweight='bold')
banner_sub = fig.text(318 / W, 1 - 201 / H, '', fontsize=17, va='center', zorder=7, color=INK2)

# topology links
link_art, label_art, mult_art = {}, {}, {}
for name in LINKS:
    u, v = name.split('-')
    (x0, y0), (x1, y1) = POS[u], POS[v]
    link_art[name] = ax.add_line(Line2D([x0, x1], [y0, y1], color=GREY, lw=3.5, solid_capstyle='round', zorder=2))
    f = LABEL_AT.get(name, 0.5)
    lx, ly = x0 + (x1 - x0) * f, y0 + (y1 - y0) * f
    label_art[name] = ax.text(lx, ly, 'C₀=%d' % C0[name], fontsize=15, ha='center', va='center', color=INK2, zorder=8,
                              bbox=dict(boxstyle='round,pad=0.22', facecolor='white', edgecolor=GRIDC, linewidth=1))
    mult_art[name] = ax.text(lx, ly + 27, '', fontsize=17, fontweight='bold', ha='center', va='center', color='white',
                             zorder=9, visible=False,
                             bbox=dict(boxstyle='round,pad=0.22', facecolor=ATTACK, edgecolor='none'))
for h, s in HOST_SW.items():
    (x0, y0), (x1, y1) = POS[h], POS[s]
    ax.add_line(Line2D([x0, x1], [y0, y1], color=GREY, lw=2.5, zorder=1))

# h1->h6 overlays (offset to the +normal side) and attack arrows (-normal side)
OFF = 13.0


def seg_points(u, v, sign):
    n = unit_normal(u, v) * OFF * sign
    p0, p1 = np.array(POS[u], float), np.array(POS[v], float)
    if u[0] == 'h' or v[0] == 'h':          # host access link: vertical, offset sideways
        n = np.array([OFF * sign, 0.0])
    return p0 + n, p1 + n


def full_path(src, dst, sw_path):
    return [src] + nodes_of(sw_path) + [dst]


PATH_OVER = {}
for p in sorted(set(P16[1])):
    hops = full_path('h1', 'h6', p)
    main = (p == P16[1][0])
    arts = []
    for u, v in zip(hops[:-1], hops[1:]):
        a, b = seg_points(u, v, +1)
        arts.append(ax.add_line(Line2D([a[0], b[0]], [a[1], b[1]], color=MAIN if main else DETOUR, lw=5.5,
                                       ls='-' if main else (0, (2.2, 1.3)), solid_capstyle='round',
                                       dash_capstyle='round', zorder=4, visible=False)))
    PATH_OVER[p] = (hops, arts)
flow_dots = ax.scatter([], [], s=60, color=MAIN, zorder=6, edgecolors='white', linewidths=1.2)

ATT_ART = {}
for k in SCN:
    sc = SCN[k]
    hops = full_path(sc['attacker'], sc['victim'], ATT_PATH[k])
    arts = []
    for u, v in zip(hops[:-1], hops[1:]):
        a, b = seg_points(u, v, -1)
        d = (b - a) / np.linalg.norm(b - a)
        a2 = a + d * (36 if u[0] == 's' else 24)
        b2 = b - d * (40 if v[0] == 's' else 28)
        arr = FancyArrowPatch(a2, b2, arrowstyle='-|>,head_length=12,head_width=7', color=ATTACK, lw=4,
                              mutation_scale=1.6, zorder=5, visible=False)
        ax.add_patch(arr)
        arts.append(arr)
    sw = HOST_SW[sc['attacker']]
    xs, ys = POS[sw]
    cross = ax.text(xs + (-34 if sc['attacker'] != 'h5' else -34), ys - 46 if sc['attacker'] != 'h5' else ys + 46,
                    '✕', fontsize=34, color=ATTACK, fontweight='bold', ha='center', va='center', zorder=10,
                    visible=False)
    drop = None
    ATT_ART[k] = (hops, arts, cross, drop)

# nodes
for n, (x, y) in POS.items():
    if n[0] == 's':
        ax.add_patch(FancyBboxPatch((x - 30, y - 22), 60, 44, boxstyle='round,pad=0,rounding_size=9',
                                    facecolor='#2f3a4a', edgecolor='white', linewidth=2, zorder=11))
        ax.text(x, y, n, color='white', fontsize=19, fontweight='bold', ha='center', va='center', zorder=12)
    else:
        ax.add_patch(Rectangle((x - 27, y - 18), 54, 36, facecolor='white', edgecolor='#2f3a4a', linewidth=2,
                               zorder=11))
        ax.text(x, y, n, color=INK, fontsize=18, ha='center', va='center', zorder=12)
host_role = {h: ax.text(POS[h][0] + 36, POS[h][1], '', fontsize=15, ha='left', va='center', zorder=12)
             for h in POS if h[0] == 'h'}

# case c note on s5-s6
x0, y0 = POS['s5']
x1, y1 = POS['s6']
note_c = ax.text((x0 + x1) / 2, y0 + 30, 'not used: 20 > 16 (s5-s3-s6)', fontsize=15, ha='center', va='center',
                 color=INK2, style='italic', zorder=9, visible=False,
                 bbox=dict(boxstyle='round,pad=0.25', facecolor='#f4f3ef', edgecolor=GREY, linewidth=1))

# legend (under the topology)
lx = 40
fig.add_artist(Line2D([lx / W, (lx + 46) / W], [1 - 1040 / H] * 2, color=MAIN, lw=5.5))
fig.text((lx + 56) / W, 1 - 1040 / H, 'h1→h6 main path', fontsize=16, va='center')
fig.add_artist(Line2D([(lx + 290) / W, (lx + 336) / W], [1 - 1040 / H] * 2, color=DETOUR, lw=5.5, ls=(0, (2.2, 1.3))))
fig.text((lx + 346) / W, 1 - 1040 / H, 'h1→h6 detour', fontsize=16, va='center')
fig.add_artist(FancyArrowPatch(((lx + 540) / W, 1 - 1040 / H), ((lx + 590) / W, 1 - 1040 / H),
                               transform=fig.transFigure, arrowstyle='-|>,head_length=10,head_width=6',
                               color=ATTACK, lw=3.5))
fig.text((lx + 600) / W, 1 - 1040 / H, 'flood', fontsize=16, va='center')
cax = fig.add_axes(px(lx + 790, 1030, 220, 20))
cax.imshow(np.linspace(0, 1, 256)[None, :], aspect='auto', cmap=CMAP, extent=[1, 4, 0, 1])
cax.set_yticks([])
cax.set_xticks([1, 2, 3, 4])
cax.set_xticklabels(['×1', '2', '3', '≥×4'], fontsize=14)
cax.tick_params(length=0, pad=3)
for s in cax.spines.values():
    s.set_visible(False)
fig.text((lx + 778) / W, 1 - 1040 / H, 'C / C₀', fontsize=16, va='center', ha='right')

# right-hand panel
RX, RW = 1240, 640
loss_ax = fig.add_axes(px(RX, 215, RW, 330))
strip_ax = fig.add_axes(px(RX, 585, RW, 34))
bw_ax = fig.add_axes(px(RX, 660, RW, 300))
fig.text(RX / W, 1 - 180 / H, 'h1→h6 per second (h6 iperf server)', fontsize=21, fontweight='bold', va='center')


def style(a, ylabel):
    a.set_xlim(0, RUN_END)
    for side in ('top', 'right'):
        a.spines[side].set_visible(False)
    a.tick_params(length=0, pad=6, labelsize=15)
    a.grid(axis='y', color=GRIDC, linewidth=0.8)
    a.set_axisbelow(True)
    a.set_ylabel(ylabel, fontsize=17)
    for k in SCN:
        fa, fb = flood(k)
        a.axvspan(fa, fb, color=BAND, zorder=0, lw=0)


style(loss_ax, 'loss (%)')
loss_ax.set_ylim(0, 60)
loss_ax.set_xticklabels([])
for k in SCN:
    fa, fb = flood(k)
    loss_ax.text((fa + fb) / 2, 57, 'case %s' % k, ha='center', va='top', fontsize=15, color=INK2)
style(bw_ax, 'throughput (Mbps)')
bw_ax.set_ylim(0, 12.5)
bw_ax.set_xlabel('run time (s)', fontsize=17)
strip_ax.set_xlim(0, RUN_END)
strip_ax.set_ylim(0, 1)
strip_ax.set_yticks([])
strip_ax.set_xticks([])
for s in strip_ax.spines.values():
    s.set_visible(False)
strip_ax.text(-4, 0.5, 'path', ha='right', va='center', fontsize=15, color=INK2)

loss_ghost, = loss_ax.step(SEC_T, SEC_LOSS, where='post', color=GRIDC, lw=1.5, zorder=2)
loss_line, = loss_ax.step([], [], where='post', color=ATTACK, lw=2.5, zorder=3)
bw_ghost, = bw_ax.step(SEC_T, SEC_BW, where='post', color=GRIDC, lw=1.5, zorder=2)
bw_line, = bw_ax.step([], [], where='post', color=MAIN, lw=2.5, zorder=3)
strip_rects = []
cursors = [a.axvline(0, color=INK, lw=2, zorder=6) for a in (loss_ax, strip_ax, bw_ax)]
loss_val = loss_ax.text(0, 0, '', fontsize=16, fontweight='bold', color=ATTACK, ha='left', va='bottom', zorder=7)
bw_val = bw_ax.text(0, 0, '', fontsize=16, fontweight='bold', color=MAIN, ha='left', va='bottom', zorder=7)
panel_note = fig.text(RX / W, 1 - 1040 / H, '', fontsize=16, color=INK2, va='center')

# path strip: full timeline drawn once, revealed by a white mask
for i, (ts, p) in enumerate(zip(P16[0], P16[1])):
    t_next = P16[0][i + 1] if i + 1 < len(P16[0]) else RUN_END
    strip_ax.add_patch(Rectangle((max(ts, 0), 0.15), t_next - max(ts, 0), 0.7, color=MAIN if p == P16[1][0] else DETOUR,
                                 lw=0, zorder=2))
strip_mask = strip_ax.add_patch(Rectangle((0, 0), RUN_END, 1, color=BG, lw=0, zorder=3))

# title / end cards
card = fig.add_artist(Rectangle((0, 0), 1, 1, transform=fig.transFigure, facecolor=BG, edgecolor='none', zorder=50))
card_title = fig.text(0.5, 0.58, '', fontsize=50, fontweight='bold', ha='center', va='center', zorder=51)
card_sub = fig.text(0.5, 0.45, '', fontsize=24, ha='center', va='center', color=INK2, zorder=51, linespacing=1.6)

TITLE_SUB = ('CEG5101 CA2 · Group 5 · 6-switch mesh, h1→h6 UDP 10 Mbps (≈890 pkt/s)\n'
             'Three ICMP floods: a (h2→h3), b (h2→h6), c (h5→h6)')
b_loss = SEC_LOSS[(SEC_T >= flood('b')[0] - 1) & (SEC_T < T_BLOCK_B)]
c_loss = SEC_LOSS[(SEC_T >= flood('c')[0] - 1) & (SEC_T < flood('c')[1])]
a_loss = SEC_LOSS[(SEC_T >= flood('a')[0] - 1) & (SEC_T < flood('a')[1])]
END_SUB = ('Case a: h1→h6 stays on %s, worst second %.0f %% loss\n'
           'Case b: detour %s at %.1f s, back at %.1f s; worst second %.0f %% before the block\n'
           'Case c: h1→h6 stays, worst second %.1f %% loss (h6’s access link)'
           % (P16[1][0], a_loss.max(), RR16[0]['detail']['new'], RR16[0]['r'], RR16[1]['r'], b_loss.max(),
              c_loss.max()))


# ----------------------------------------------------------------------------
# frame update
# ----------------------------------------------------------------------------
def poly_points(hops, sign):
    pts = []
    for u, v in zip(hops[:-1], hops[1:]):
        a, b = seg_points(u, v, sign)
        pts.append((a, b))
    return pts


def along(pts, s):
    lens = np.array([np.linalg.norm(b - a) for a, b in pts])
    total = lens.sum()
    d = (s % 1.0) * total
    for (a, b), L in zip(pts, lens):
        if d <= L:
            return a + (b - a) * d / L
        d -= L
    return pts[-1][1]


def draw_state(t, v_clock=0.0, speed=0.0, frozen=False, card_mode=None):
    # links
    for name in LINKS:
        norm, anom = link_state(name, t)
        col, lw = cost_style(norm)
        link_art[name].set_color(col)
        link_art[name].set_linewidth(lw)
        m = mult_art[name]
        if anom:
            m.set_text('×%.2f' % norm)
            m.set_visible(True)
        else:
            m.set_visible(False)

    # h1->h6 path
    cur = h16_path(t)
    for p, (hops, arts) in PATH_OVER.items():
        for a in arts:
            a.set_visible(p == cur)
    hops = PATH_OVER[cur][0]
    pts = poly_points(hops, +1)
    dots = np.array([along(pts, v_clock * 0.35 + i / 7.0) for i in range(7)])
    flow_dots.set_offsets(dots)
    flow_dots.set_color(MAIN if cur == P16[1][0] else DETOUR)
    flow_dots.set_edgecolor('white')

    # attacks
    k_ph, ph_text = phase(t)
    for h in host_role:
        host_role[h].set_text('')
    host_role['h1'].set_text('sender')
    host_role['h1'].set_color(MAIN)
    host_role['h6'].set_text('receiver')
    host_role['h6'].set_color(MAIN)
    for k, (hops_a, arts, cross, drop) in ATT_ART.items():
        fa, fb = flood(k)
        on = fa <= t < fb
        blocked = on and t >= BLOCK[k]['r']
        for i, a in enumerate(arts):
            a.set_visible(on)
            if blocked and i > 0:
                a.set_alpha(0.18)
                a.set_linestyle((0, (2, 2)))
            else:
                a.set_alpha(1.0)
                a.set_linestyle('-')
        cross.set_visible(blocked)
        if on:
            att = SCN[k]['attacker']
            host_role[att].set_text('attacker \u00b7 blocked' if blocked else 'attacker')
            host_role[att].set_color(ATTACK)
            vic = SCN[k]['victim']
            if vic != 'h6':
                host_role[vic].set_text('victim')
                host_role[vic].set_color(ATTACK)
            else:
                host_role['h6'].set_text('receiver + victim')
    note_c.set_visible(k_ph == 'c' and t < UNBLOCK['c']['r'] + 3)

    # header
    clock_txt.set_text('t = %5.1f s' % t)
    if frozen:
        speed_txt.set_text('paused at the case b block')
        speed_txt.set_color(ATTACK)
    elif speed > 0:
        speed_txt.set_text('playback ×%.0f' % speed)
        speed_txt.set_color(INK2)
    else:
        speed_txt.set_text('')
    phase_txt.set_text(ph_text)

    # banner
    i = bisect.bisect_right(BANNER_T, t) - 1
    if i < 0:
        banner_tag.set_text('NORMAL')
        banner_tag.get_bbox_patch().set_facecolor(MAIN)
        banner_txt.set_text('h1\u2192h6 on %s, cost %.0f' % (P16[1][0], P16[2][0]))
        banner_sub.set_text('shortest by C\u2080: %d + %d \u00b7 0 %% loss' % (C0['s1-s2'], C0['s2-s6']))
        banner_box.set_edgecolor(GRIDC)
        banner_box.set_linewidth(2)
    else:
        bt, kind, text, sub, col = BANNERS[i]
        banner_tag.set_text(kind)
        banner_tag.get_bbox_patch().set_facecolor(col)
        banner_txt.set_text(text)
        banner_sub.set_text(sub)
        fresh = (t - bt) < 6.0 or frozen
        banner_box.set_edgecolor(col if fresh else GRIDC)
        banner_box.set_linewidth(5 if frozen else (3 if fresh else 2))

    # right panel
    n = int(np.searchsorted(SEC_T + 1.0, t, side='right'))
    loss_line.set_data(np.append(SEC_T[:n], SEC_T[:n][-1] + 1) if n else [], np.append(SEC_LOSS[:n], SEC_LOSS[:n][-1]) if n else [])
    bw_line.set_data(np.append(SEC_T[:n], SEC_T[:n][-1] + 1) if n else [], np.append(SEC_BW[:n], SEC_BW[:n][-1]) if n else [])
    for c in cursors:
        c.set_xdata([t, t])
    strip_mask.set_x(t)
    strip_mask.set_width(max(RUN_END - t, 0))
    if n:
        lv, bv = SEC_LOSS[n - 1], SEC_BW[n - 1]
        xa = t + 3 if t < RUN_END - 45 else t - 3
        ha = 'left' if t < RUN_END - 45 else 'right'
        loss_val.set_position((xa, min(lv, 48) + 1.5))
        loss_val.set_ha(ha)
        loss_val.set_text('%.1f %%' % lv)
        bw_val.set_position((xa, min(bv, 10.8) + 0.3))
        bw_val.set_ha(ha)
        bw_val.set_text('%.1f Mbps' % bv)
    else:
        loss_val.set_text('')
        bw_val.set_text('')
    panel_note.set_text('grey bands: flood running · strip: path h1→h6 used')

    # cards
    if card_mode is None:
        for a in (card, card_title, card_sub):
            a.set_visible(False)
    else:
        mode, alpha = card_mode
        card.set_visible(True)
        card.set_alpha(alpha)
        card_title.set_visible(True)
        card_sub.set_visible(True)
        card_title.set_alpha(alpha)
        card_sub.set_alpha(alpha)
        if mode == 'title':
            card_title.set_text('Replay of run R1 from controller logs')
            card_sub.set_text(TITLE_SUB)
        else:
            card_title.set_text('Run R1 in one view')
            card_sub.set_text(END_SUB)


def frame(i):
    v = i / FPS
    t, speed, frozen = run_time(v)
    # flow dots advance with video time except while paused
    play_v = v - TITLE_S
    frz_start = TITLE_S + sum(s[2] for s in SEGMENTS[:4])
    if v > frz_start:
        play_v -= min(v - frz_start, SEGMENTS[4][2])
    card_mode = None
    if v < TITLE_S:
        card_mode = ('title', 1.0 if v < TITLE_S - 0.4 else (TITLE_S - v) / 0.4)
    elif v >= TITLE_S + PLAY_S:
        card_mode = ('end', min(1.0, (v - TITLE_S - PLAY_S) / 0.3))
    draw_state(t, max(play_v, 0), speed, frozen, card_mode)
    return []


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--stills-only', action='store_true')
    ap.add_argument('--frame-at', type=float, nargs='*', help='write test PNGs at these run times and exit')
    ap.add_argument('--check-dir', default='.', help='where --frame-at PNGs go')
    args = ap.parse_args()
    os.makedirs(os.path.dirname(VIDEO), exist_ok=True)
    os.makedirs(FIGDIR, exist_ok=True)

    if args.frame_at:
        for t in args.frame_at:
            draw_state(t, 0.3)
            out = os.path.join(args.check_dir, 'check_%05.1f.png' % t)
            fig.savefig(out, dpi=100)
            print(out)
        return

    for i, t in enumerate((60.0, 114.0, 135.0, 200.0), 1):
        draw_state(t, 0.3)
        out = os.path.join(FIGDIR, 'replay_r1_still_%d.png' % i)
        fig.savefig(out, dpi=100)
        print(out)
    if args.stills_only:
        return

    n = int(round(TOTAL_S * FPS))
    print('frames %d (%.1f s), freeze at run t = %.2f s' % (n, TOTAL_S, T_FREEZE), file=sys.stderr)
    writer = animation.FFMpegWriter(fps=FPS, codec='libx264', bitrate=-1,
                                    extra_args=['-pix_fmt', 'yuv420p', '-preset', 'slow', '-crf', '18',
                                                '-movflags', '+faststart', '-tune', 'animation'])
    anim = animation.FuncAnimation(fig, frame, frames=n, blit=False)
    anim.save(VIDEO, writer=writer, dpi=100)
    print(VIDEO)


if __name__ == '__main__':
    main()
