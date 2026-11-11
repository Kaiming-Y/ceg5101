#!/usr/bin/env python3
"""Slide figures (16:9 deck) from the R1 run (results/validation-abc).

    ~/ryu-venv/bin/python support/presentation/plot_slides.py

Writes PNG (200 dpi) and SVG into presentation/assets/figures/:
    hook_loss_zoom       per-second h1->h6 loss, 100-160 s
    fig6_detector_h2     h2 pkt/s vs baseline and threshold (log y)
    fig5_slide           attack packets sent vs reaching the victim, per case
    cost_s2s6            s2-s6 cost split into C0, load term and beta*A
    fig4b_caseb_zoom     case b: path, link cost, loss (100-165 s)
    task5_fullrun_slide  whole run: attacked-link cost, loss, throughput
"""
import importlib.util
import os

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt  # noqa: E402
from matplotlib.patches import Patch, Rectangle  # noqa: E402

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))
RUN = os.path.join(ROOT, 'results', 'validation-abc')
OUT = os.path.join(ROOT, 'presentation', 'assets', 'figures')

spec = importlib.util.spec_from_file_location('plot_results', os.path.join(ROOT, 'support', 'analysis', 'plot_results.py'))
pr = importlib.util.module_from_spec(spec)
spec.loader.exec_module(pr)

# palette
MAIN = '#2a78d6'
DETOUR = '#eb6834'
ATTACK = '#d62728'
GREY = '#898781'
BAND = '#efeee9'
BG = '#fcfcfb'
INK = '#0b0b0b'
INK2 = '#52514e'
GRIDC = '#e1e0d9'
LW = 2.5

C0 = {'s1-s2': 5, 's2-s3': 10, 's2-s6': 14, 's3-s5': 9, 's3-s6': 7, 's5-s6': 20}
ALPHA, BETA, RMAX = 10.0, 30.0, 40.0

plt.rcParams.update({
    'font.family': ['Inter', 'DejaVu Sans'],
    'font.size': 16,
    'axes.titlesize': 17,
    'axes.labelsize': 16,
    'xtick.labelsize': 15,
    'ytick.labelsize': 15,
    'legend.fontsize': 15,
    'axes.edgecolor': GRIDC,
    'axes.labelcolor': INK2,
    'xtick.color': INK2,
    'ytick.color': INK2,
    'text.color': INK,
    'figure.facecolor': BG,
    'axes.facecolor': BG,
    'savefig.facecolor': BG,
    'hatch.linewidth': 1.2,
    'svg.fonttype': 'path',
})


# ----------------------------------------------------------------------------
# data
# ----------------------------------------------------------------------------
D = pr.load_run(RUN)
T0 = D['t0']
SCN = {s['id']: s for s in D['timeline']['scenarios']}


def rel(t):
    return t - T0


def block_of(sc):
    a, b = sc['attack_start'], sc['attack_end']
    return [e for e in D['events'] if e['event'] == 'block' and e['src'] == sc['attacker'] and a <= e['t'] <= b + 5][0]


BLOCK = {k: block_of(s) for k, s in SCN.items()}
REROUTES = [e for e in D['events'] if e['event'] == 'reroute' and (e['src'], e['dst']) == ('h1', 'h6')]
T_BLOCK_B = rel(BLOCK['b']['t'])
T_BACK = rel(REROUTES[1]['t'])

# per-second iperf rows: (interval start, interval end, Mbps, loss)
SECONDS = [(rel(t) - 1, rel(t), bw, loss) for t, bw, loss in D['iperf']]


def flood_span(k):
    s = SCN[k]
    return rel(s['attack_start']), rel(s['attack_end'])


def link_series(name):
    """[(t_rel, norm, load_term, beta_term)] for one link."""
    out = []
    for t, norm, cost, rate, anom in D['links'][name]:
        c0 = C0[name]
        out.append((rel(t), norm, ALPHA * min(rate / RMAX, 1.0) / c0, BETA * anom / c0))
    return out


# ----------------------------------------------------------------------------
# helpers
# ----------------------------------------------------------------------------
def style(ax, ylabel=None, grid=True):
    ax.set_facecolor(BG)
    for side in ('top', 'right'):
        ax.spines[side].set_visible(False)
    for side in ('left', 'bottom'):
        ax.spines[side].set_color(GRIDC)
    ax.tick_params(length=0, pad=6)
    if grid:
        ax.grid(axis='y', color=GRIDC, linewidth=0.8)
    ax.set_axisbelow(True)
    if ylabel:
        ax.set_ylabel(ylabel)


def bands(ax, ids=('a', 'b', 'c'), label=False, y=1.0, fs=15):
    for k in ids:
        a, b = flood_span(k)
        ax.axvspan(a, b, color=BAND, zorder=0, linewidth=0)
        if label:
            sc = SCN[k]
            ax.text((a + b) / 2, y, '%s: %s→%s' % (k, sc['attacker'], sc['victim']),
                    transform=ax.get_xaxis_transform(), ha='center', va='bottom', fontsize=fs, color=INK2)


def vline_block(ax, t, text=None, y=0.97, ha='left', fs=15):
    ax.axvline(t, color=INK, linewidth=1.6, linestyle=(0, (5, 3)), zorder=4)
    if text:
        ax.text(t + (0.6 if ha == 'left' else -0.6), y, text, transform=ax.get_xaxis_transform(),
                ha=ha, va='top', fontsize=fs, color=INK)


def save(fig, name):
    for ext, kw in (('png', {'dpi': 200}), ('svg', {})):
        fig.savefig(os.path.join(OUT, '%s.%s' % (name, ext)), facecolor=BG, **kw)
    plt.close(fig)
    print('wrote', name)


def loss_bars(ax, lo, hi, label_hi=True, red_from=None, red_to=None, label_fs=16, label_min=5.0):
    """Per-second loss bars over [lo, hi]; bars inside [red_from, red_to] red."""
    for t_a, t_b, bw, loss in SECONDS:
        if t_b <= lo or t_a >= hi:
            continue
        red = red_from is not None and red_from - 0.1 <= t_a and t_b <= red_to + 0.1
        col = ATTACK if red else MAIN
        if loss > 0:
            ax.bar((t_a + t_b) / 2, loss, width=0.82, color=col, linewidth=0, zorder=3)
            if label_hi and loss >= label_min:
                ax.text((t_a + t_b) / 2, loss + 1.2, '%d%%' % round(loss), ha='center', va='bottom',
                        fontsize=label_fs, color=INK, fontweight='semibold', zorder=5)
        else:
            ax.plot([(t_a + t_b) / 2], [0], marker='o', markersize=3, color=GREY, zorder=3, linewidth=0)


# ----------------------------------------------------------------------------
# 1. hook: per-second loss 100-160 s
# ----------------------------------------------------------------------------
def hook_loss_zoom():
    fig = plt.figure(figsize=(6.0, 5.0))
    ax = fig.add_axes([0.14, 0.15, 0.82, 0.70])
    style(ax, 'h1→h6 loss per second (%)')
    a, b = flood_span('b')
    ax.axvspan(a, b, color=BAND, zorder=0, linewidth=0)
    ax.text(b - 0.6, 0.985, 'flood h2→h6', transform=ax.get_xaxis_transform(), ha='right', va='top',
            fontsize=15, color=INK2)
    loss_bars(ax, 100, 160, red_from=112, red_to=116, label_hi=False)
    lossy = [p for p in SECONDS if 112 - 0.1 <= p[0] and p[1] <= 116.1 and p[3] > 0]
    # label positions (x, y, ha) for the four lossy seconds, left of the bars except the last
    spots = [(111.6, None, 'right'), (111.6, None, 'right'), (111.6, 56.5, 'right'), (116.5, None, 'left')]
    for (t_a, t_b, bw, loss), (lx, ly, ha) in zip(lossy, spots):
        x = (t_a + t_b) / 2
        ly = loss if ly is None else ly
        ap = None if abs(ly - loss) < 1 and abs(lx - x) < 1.5 else \
            dict(arrowstyle='-', color=INK2, linewidth=1.0, shrinkA=2, shrinkB=1)
        ax.annotate('%d%%' % round(loss), xy=(x, loss), xytext=(lx, ly), ha=ha, va='center', fontsize=16,
                    color=INK, fontweight='semibold', arrowprops=ap)
    ax.text(111.6, 35.5, '112–116 s', ha='right', va='center', fontsize=14, color=INK2)
    vline_block(ax, T_BLOCK_B)
    ax.text(T_BLOCK_B + 0.9, 0.80, 'h2 blocked\n%.1f s' % T_BLOCK_B, transform=ax.get_xaxis_transform(),
            ha='left', va='top', fontsize=16, color=INK)
    ax.text((T_BLOCK_B + b) / 2 + 1, 4, '0% for the rest\nof the flood', ha='center', va='bottom',
            fontsize=16, color=MAIN, fontweight='semibold')
    ax.set_xlim(100, 160)
    ax.set_ylim(0, 62)
    ax.set_yticks([0, 20, 40, 60])
    ax.set_xticks([100, 112, 116, 130, 145, 160])
    ax.set_xlabel('time since baseline start (s)')
    fig.text(0.02, 0.965, 'Case b, run R1: loss only before the block', fontsize=17, color=INK,
             ha='left', va='top', fontweight='semibold')
    save(fig, 'hook_loss_zoom')


# ----------------------------------------------------------------------------
# 2. detector: h2 pkt/s vs baseline and threshold
# ----------------------------------------------------------------------------
def fig6_detector_h2():
    rows = [r for r in pr.read_csv(os.path.join(RUN, 'controller', 'sources.csv')) if r['ip'] == '10.0.0.2']
    lo, hi = 98, 126.5
    pts = [(rel(float(r['t'])), float(r['pps']), float(r['baseline']), float(r['threshold']), int(r['blocked']))
           for r in rows]
    pts = [p for p in pts if lo <= p[0] <= hi]
    FLOOR = 0.4
    fig = plt.figure(figsize=(5.5, 4.6))
    ax = fig.add_axes([0.15, 0.15, 0.80, 0.70])
    style(ax, 'h2 rate (pkt/s, log)')
    a, b = flood_span('b')
    ax.axvspan(a, b, color=BAND, zorder=0, linewidth=0)
    ts = [p[0] for p in pts]
    ts_ext = ts + [hi]
    ax.step(ts_ext, [p[3] for p in pts] + [pts[-1][3]], where='post', color=INK, linewidth=2.2, linestyle=(0, (5, 3)), zorder=3)
    ax.step(ts_ext, [p[2] for p in pts] + [pts[-1][2]], where='post', color=GREY, linewidth=LW, zorder=3)
    live = [p for p in pts if p[1] > 0]
    ax.plot([p[0] for p in live], [p[1] for p in live], color=ATTACK, linewidth=LW, marker='o',
            markersize=7, zorder=5)
    zeros = [p for p in pts if p[1] == 0]
    ax.plot([p[0] for p in zeros], [FLOOR * 1.25] * len(zeros), linewidth=0, marker='o', markersize=6,
            markerfacecolor=BG, markeredgecolor=ATTACK, markeredgewidth=1.8, zorder=5, clip_on=False)
    ax.set_yscale('log')
    ax.set_ylim(FLOOR, 2.5e4)
    ax.set_yticks([1, 10, 100, 1000, 10000])
    ax.set_yticklabels(['1', '10', '100', '1k', '10k'])
    ax.set_xlim(lo, hi)
    ax.set_xlabel('time since baseline start (s)')
    # annotations
    p_part = [p for p in pts if 400 < p[1] < 500][0]
    p_det = [p for p in pts if p[1] > 4000][0]
    ax.annotate('%d pkt/s partial\n→ learned' % round(p_part[1]), xy=(p_part[0], p_part[1]),
                xytext=(p_part[0] - 1.0, 1.9e3), ha='right', va='center', fontsize=15, color=INK,
                arrowprops=dict(arrowstyle='-', color=INK2, linewidth=1.2))
    ax.annotate('{:,} pkt/s\n→ BLOCK {:.1f} s'.format(round(p_det[1]), p_det[0]), xy=(p_det[0], p_det[1]),
                xytext=(p_det[0] - 1.6, 1.25e4), ha='right', va='center', fontsize=15, color=INK,
                fontweight='semibold', arrowprops=dict(arrowstyle='-', color=INK2, linewidth=1.2))
    t_last = ts[-1]
    ax.text(hi - 0.3, pts[-1][3] * 1.25, 'T = {:,}'.format(round(pts[-1][3])), ha='right', va='bottom',
            fontsize=15, color=INK)
    ax.text(hi - 0.3, pts[-1][2] * 0.78, 'baseline b = %d' % round(pts[-1][2]), ha='right', va='top',
            fontsize=15, color=INK2)
    ax.text(lo + 0.4, 500 * 0.8, 'T = 500 (floor)', ha='left', va='top', fontsize=14, color=INK2)
    ax.text(lo + 0.4, 1.7, 'b ≈ 1', ha='left', va='bottom', fontsize=14, color=INK2)
    ax.text(hi - 0.3, FLOOR * 2.4, '0 = dropped at s2', ha='right', va='bottom', fontsize=14, color=ATTACK)
    fig.text(0.02, 0.965, 'Detector on h2 during case b (R1)', fontsize=17, color=INK, ha='left', va='top',
             fontweight='semibold')
    save(fig, 'fig6_detector_h2')


# ----------------------------------------------------------------------------
# 3. blocking check, per case
# ----------------------------------------------------------------------------
def fig5_slide():
    fig = plt.figure(figsize=(6.0, 5.0))
    gs = fig.add_gridspec(3, 1, left=0.15, right=0.97, top=0.86, bottom=0.13, hspace=0.55)
    axes = [fig.add_subplot(gs[i]) for i in range(3)]
    for ax, k in zip(axes, 'abc'):
        sc = SCN[k]
        a, b = sc['attack_start'], sc['attack_end']
        tb = BLOCK[k]['t']
        style(ax)
        rows = [r for r in D['counters'] if r['scenario'] == k]
        xs, sent = [], []
        for r0, r1 in zip(rows, rows[1:]):
            dt = float(r1['t']) - float(r0['t'])
            if dt > 0:
                xs.append(float(r1['t']) - a)
                sent.append((int(r1['attacker_tx_packets']) - int(r0['attacker_tx_packets'])) / dt)
        x2, recv = pr._per_second(D['captures'].get(k, []), a, b + 2)
        x2 = [x + 0.5 for x in x2]
        ax.plot(xs, [s / 1000 for s in sent], color=ATTACK, linewidth=LW, zorder=3)
        ax.plot(x2, [r / 1000 for r in recv], color=INK, linewidth=LW, zorder=4)
        ax.axvline(tb - a, color=INK, linewidth=1.4, linestyle=(0, (5, 3)), zorder=2)
        cap = D['captures'].get(k, [])
        n_before = sum(1 for t in cap if t < tb)
        n_late = sum(1 for t in cap if t >= tb + 1)
        ax.set_title('%s: %s→%s   blocked after %.1f s' % (k, sc['attacker'], sc['victim'], tb - a),
                     loc='left', fontsize=15, color=INK, pad=4)
        ax.text(26.6, 2.4, 'reached {}: {:,}, then {}'.format(sc['victim'], n_before, n_late),
                ha='right', va='center', fontsize=14, color=INK)
        ax.set_xlim(-1, 27)
        ax.set_ylim(0, 7.2)
        ax.set_yticks([0, 5])
        ax.set_yticklabels(['0', '5k'])
        if k != 'c':
            ax.set_xticklabels([])
    axes[0].text(26.6, 6.3, 'sent by attacker ≈ 4.7k/s', ha='right', va='center', fontsize=14, color=ATTACK)
    axes[1].set_ylabel('packets per second')
    axes[-1].set_xlabel('time since flood start (s)')
    fig.text(0.02, 0.975, 'Flood packets: sent vs reaching the victim', fontsize=17, color=INK, ha='left',
             va='top', fontweight='semibold')
    save(fig, 'fig5_slide')


# ----------------------------------------------------------------------------
# 4. s2-s6 cost decomposition
# ----------------------------------------------------------------------------
def cost_s2s6():
    s = [p for p in link_series('s2-s6') if 98 <= p[0] <= 162]
    t = [p[0] for p in s]
    base = [1.0] * len(s)
    load = [1.0 + p[2] for p in s]
    tot = [1.0 + p[2] + p[3] for p in s]
    fig = plt.figure(figsize=(7.5, 4.4))
    ax = fig.add_axes([0.10, 0.16, 0.87, 0.70])
    style(ax, 'cost of s2-s6 / C0')
    a, b = flood_span('b')
    ax.axvspan(a, b, color=BAND, zorder=0, linewidth=0)
    ax.text(b - 0.6, 0.985, 'flood h2→h6', transform=ax.get_xaxis_transform(), ha='right', va='top',
            fontsize=15, color=INK2)
    kw = dict(step='post', linewidth=0, zorder=2)
    ax.fill_between(t, 0, base, color='#d9d8d2', **kw)
    ax.fill_between(t, base, load, facecolor='#c4c3bc', edgecolor=GREY, hatch='///', **kw)
    ax.fill_between(t, load, tot, color=ATTACK, alpha=0.85, **kw)
    ax.step(t, tot, where='post', color=INK, linewidth=1.6, zorder=3)
    # labels
    def val_at(tt):
        return [p for p in s if p[0] <= tt + 0.05][-1]
    p_before = val_at(110.0)
    p_spike = val_at(T_BLOCK_B)
    p_plat = val_at(145.0)
    p_ret = val_at(T_BACK)
    lab = dict(fontsize=17, color=INK, fontweight='semibold', ha='center', va='bottom')
    ax.text(108.5, p_before[1] + 0.08, '×%.2f' % p_before[1], **lab)
    ax.text(T_BLOCK_B + 2.9, p_spike[1] - 0.02, '×%.2f' % p_spike[1], **dict(lab, ha='left', va='center'))
    ax.text(141, p_plat[1] + 0.08, '×%.2f' % p_plat[1], **lab)
    ax.text(T_BACK + 0.8, p_ret[1] + 0.3, '×%.1f' % p_ret[1], **dict(lab, ha='left'))
    # in-area legend labels
    ax.text(126.5, 0.5, 'C0 = 14', ha='center', va='center', fontsize=15, color=INK)
    ax.text(126.5, 2.1, 'β·A = 30', ha='center', va='center', fontsize=16, color='white', fontweight='semibold')
    ax.annotate('α·R/Rmax\n(load)', xy=(102.5, 1.10), xytext=(102.5, 2.2), ha='center', va='center', fontsize=15,
                color=INK, arrowprops=dict(arrowstyle='-', color=INK2, linewidth=1.2))
    vline_block(ax, T_BLOCK_B)
    ax.axvline(T_BACK, color=INK, linewidth=1.6, linestyle=(0, (1, 2)), zorder=4)
    ax.set_xlim(98, 162)
    ax.set_ylim(0, 4.2)
    ax.set_yticks([0, 1, 2, 3, 4])
    ax.set_xlabel('time since baseline start (s)')
    fig.text(0.02, 0.965, 'Cost of s2-s6 in case b (R1), split by term of Eq. (1)', fontsize=17, color=INK,
             ha='left', va='top', fontweight='semibold')
    save(fig, 'cost_s2s6')


# ----------------------------------------------------------------------------
# path band helper
# ----------------------------------------------------------------------------
def path_band(ax, lo, hi, fs=15):
    seq = D['paths'][('h1', 'h6')]
    segs = []
    for i, (t, p, _) in enumerate(seq):
        t_next = seq[i + 1][0] if i + 1 < len(seq) else t + 2.4
        a, b = rel(t), rel(t_next)
        if segs and segs[-1][2] == p and abs(segs[-1][1] - a) < 0.05:
            segs[-1][1] = b
        else:
            segs.append([a, b, p])
    for a, b, p in segs:
        if b < lo or a > hi:
            continue
        if p == 's1-s2-s6':
            ax.add_patch(Rectangle((a, 0.15), b - a, 0.7, facecolor=MAIN, linewidth=0, zorder=2))
        else:
            ax.add_patch(Rectangle((a, 0.15), b - a, 0.7, facecolor=BG, edgecolor=DETOUR, hatch='///',
                                   linewidth=1.5, zorder=2))
    return segs


# ----------------------------------------------------------------------------
# 5. case b zoom: path, cost, loss
# ----------------------------------------------------------------------------
def fig4b_caseb_zoom():
    lo, hi = 100, 165
    fig = plt.figure(figsize=(12.3, 5.6))
    gs = fig.add_gridspec(3, 1, height_ratios=[0.55, 2.0, 1.45], left=0.075, right=0.985, top=0.90,
                          bottom=0.12, hspace=0.32)
    ax0 = fig.add_subplot(gs[0])
    ax1 = fig.add_subplot(gs[1], sharex=ax0)
    ax2 = fig.add_subplot(gs[2], sharex=ax0)
    a, b = flood_span('b')

    # path band
    style(ax0, grid=False)
    ax0.axvspan(a, b, color=BAND, zorder=0, linewidth=0)
    path_band(ax0, lo, hi)
    ax0.set_ylim(0, 1)
    ax0.set_yticks([])
    ax0.spines['left'].set_visible(False)
    ax0.spines['bottom'].set_visible(False)
    ax0.tick_params(labelbottom=False)
    ax0.text(107, 0.5, 'main  s1-s2-s6', ha='center', va='center', fontsize=15, color='white',
             fontweight='semibold', zorder=5)
    ax0.text((T_BLOCK_B + T_BACK) / 2, 0.5, 'detour  s1-s2-s3-s6', ha='center', va='center', fontsize=15,
             color=INK, fontweight='semibold', zorder=5,
             bbox=dict(boxstyle='round,pad=0.15', facecolor=BG, edgecolor='none'))
    ax0.text(158.5, 0.5, 'main', ha='center', va='center', fontsize=15, color='white', fontweight='semibold',
             zorder=5)
    ax0.set_title('h1→h6 path', loc='left', fontsize=16, color=INK, pad=4)
    ax0.text(a + 0.6, 1.08, 'flood h2→h6 (%.0f–%.0f s)' % (a, b), transform=ax0.transAxes if False else
             ax0.get_xaxis_transform(), ha='left', va='bottom', fontsize=15, color=INK2)

    # cost
    style(ax1, 'cost / C0')
    ax1.axvspan(a, b, color=BAND, zorder=0, linewidth=0)
    s26 = [p for p in link_series('s2-s6') if lo - 3 <= p[0] <= hi + 3]
    ax1.step([p[0] for p in s26], [p[1] for p in s26], where='post', color=ATTACK, linewidth=LW, zorder=4)
    for name in ('s2-s3', 's3-s6'):
        sr = [p for p in link_series(name) if lo - 3 <= p[0] <= hi + 3]
        ax1.step([p[0] for p in sr], [p[1] for p in sr], where='post', color=DETOUR, linewidth=LW,
                 linestyle=(0, (4, 2)), zorder=3)
    ax1.text(101, 1.42, 's2-s6 (attacked)', ha='left', va='bottom', fontsize=15, color=INK)
    ax1.text(141, 1.62, 's2-s3, s3-s6 (detour links)', ha='center', va='bottom', fontsize=15, color=INK)
    plat = min(p[1] for p in s26 if T_BLOCK_B + 15 < p[0] < T_BACK - 1)
    ax1.text(141, plat + 0.12, '×%.2f = (14+30)/14' % plat, ha='center', va='bottom', fontsize=16, color=INK,
             fontweight='semibold')
    spike = [p for p in s26 if abs(p[0] - T_BLOCK_B) < 0.1][0][1]
    ax1.text(T_BLOCK_B + 0.8, spike + 0.02, '×%.2f' % spike, ha='left', va='bottom', fontsize=16, color=INK,
             fontweight='semibold')
    ax1.set_ylim(0.7, 4.3)
    ax1.set_yticks([1, 2, 3, 4])
    ax1.tick_params(labelbottom=False)

    # loss
    style(ax2, 'loss (%)')
    ax2.axvspan(a, b, color=BAND, zorder=0, linewidth=0)
    loss_bars(ax2, lo, hi, red_from=112, red_to=116, label_hi=False)
    peak = max((p for p in SECONDS if 112 - 0.1 <= p[0] and p[1] <= 116.1), key=lambda p: p[3])
    ax2.annotate('worst second %.1f%%' % peak[3], xy=((peak[0] + peak[1]) / 2, peak[3] + 0.5),
                 xytext=(110.6, peak[3] - 12), ha='right', va='center', fontsize=15, color=INK,
                 fontweight='semibold', arrowprops=dict(arrowstyle='-', color=INK2, linewidth=1.0))
    ax2.set_ylim(0, 62)
    ax2.set_yticks([0, 25, 50])
    ax2.set_xlabel('time since baseline start (s)')

    for ax in (ax0, ax1, ax2):
        ax.axvline(T_BLOCK_B, color=INK, linewidth=1.6, linestyle=(0, (5, 3)), zorder=6)
        ax.axvline(T_BACK, color=INK, linewidth=1.8, linestyle=(0, (1, 2)), zorder=6)
    ax1.text(T_BLOCK_B - 0.6, 0.97, 'h2 blocked +\nrerouted %.1f s' % T_BLOCK_B, transform=ax1.get_xaxis_transform(),
             ha='right', va='top', fontsize=15, color=INK)
    ax1.text(T_BACK + 0.6, 0.97, 'back to main\n%.1f s' % T_BACK, transform=ax1.get_xaxis_transform(),
             ha='left', va='top', fontsize=15, color=INK)
    ax2.text(T_BLOCK_B + 2, 30, '0% after the block', ha='left', va='center', fontsize=15, color=MAIN,
             fontweight='semibold')
    ax0.set_xlim(lo, hi)
    save(fig, 'fig4b_caseb_zoom')


# ----------------------------------------------------------------------------
# 6. whole run: cost, loss, throughput
# ----------------------------------------------------------------------------
def task5_fullrun_slide():
    fig = plt.figure(figsize=(12.3, 5.9))
    gs = fig.add_gridspec(3, 1, height_ratios=[2.3, 1.1, 1.1], left=0.075, right=0.985, top=0.91,
                          bottom=0.11, hspace=0.28)
    ax1 = fig.add_subplot(gs[0])
    ax2 = fig.add_subplot(gs[1], sharex=ax1)
    ax3 = fig.add_subplot(gs[2], sharex=ax1)
    end = rel([m['t'] for m in D['timeline']['marks'] if m['name'] == 'end'][0])

    style(ax1, 'cost / C0')
    bands(ax1, label=True, y=1.01, fs=15)
    styles = {
        's3-s5': dict(color=ATTACK, linewidth=LW),
        's2-s3': dict(color=DETOUR, linewidth=LW),
        's3-s6': dict(color=DETOUR, linewidth=LW, linestyle=(0, (4, 2))),
        's2-s6': dict(color=MAIN, linewidth=LW),
        's5-s6': dict(color=GREY, linewidth=2.0),
    }
    for name, kw in styles.items():
        s = link_series(name)
        ax1.step([p[0] for p in s], [p[1] for p in s], where='post', zorder=3, **kw)

    def plateau(name, k):
        a, b = flood_span(k)
        v = [p[1] for p in link_series(name) if a + 15 < p[0] < b]
        return min(v)
    pa = plateau('s2-s3', 'a')
    pb = plateau('s2-s6', 'b')
    pc5 = plateau('s3-s5', 'c')
    pc6 = plateau('s3-s6', 'c')
    lab = dict(fontsize=15, color=INK, fontweight='semibold', va='bottom')
    xa, xb, xc = [sum(flood_span(k)) / 2 for k in 'abc']
    ax1.text(xa + 10, pa + 0.12, 's2-s3 ×%.1f' % pa, ha='center', **lab)
    ax1.text(xb + 10, pb + 0.12, 's2-s6 ×%.2f' % pb, ha='center', **lab)
    ax1.text(xc + 10, pc6 + 0.12, 's3-s6 ×%.2f' % pc6, ha='center', **lab)
    ax1.text(xc + 10, pc5 - 0.15, 's3-s5 ×%.2f' % pc5, ha='center', fontsize=15, color=INK,
             fontweight='semibold', va='top')
    ax1.text(252, 0.93, 's5-s6 stays 1.0', ha='right', va='top', fontsize=15, color=INK2)
    ax1.set_ylim(0.35, 6.4)
    ax1.set_yticks([1, 3, 5])
    ax1.tick_params(labelbottom=False)

    style(ax2, 'loss %')
    bands(ax2)
    ax2.plot([p[1] for p in SECONDS], [p[3] for p in SECONDS], color=MAIN, linewidth=2.0, zorder=3)
    worst_b = max((p for p in SECONDS if flood_span('b')[0] <= p[0] <= flood_span('b')[1]), key=lambda p: p[3])
    worst_c = max((p for p in SECONDS if flood_span('c')[0] <= p[0] <= flood_span('c')[1]), key=lambda p: p[3])
    ax2.text(worst_b[1] + 2.5, worst_b[3] * 0.85, '%.1f%%' % worst_b[3], ha='left', va='center', fontsize=15,
             color=INK, fontweight='semibold')
    ax2.text(worst_c[1] + 2.5, 22, '%.1f%%' % worst_c[3], ha='left', va='center', fontsize=15, color=INK,
             fontweight='semibold')
    ax2.set_ylim(0, 60)
    ax2.set_yticks([0, 50])
    ax2.tick_params(labelbottom=False)

    style(ax3, 'Mbps')
    bands(ax3)
    ax3.plot([p[1] for p in SECONDS], [p[2] for p in SECONDS], color=MAIN, linewidth=2.0, zorder=3)
    low_b = min((p for p in SECONDS if flood_span('b')[0] <= p[0] <= flood_span('b')[1]), key=lambda p: p[2])
    ax3.text(low_b[1] + 2.5, low_b[2] + 0.4, '%.2f' % low_b[2], ha='left', va='center', fontsize=15, color=INK,
             fontweight='semibold')
    ax3.text(4, 10.5 + 0.9, '10.5 Mbps', ha='left', va='bottom', fontsize=15, color=INK2)
    ax3.set_ylim(4, 14)
    ax3.set_yticks([5, 10])
    ax3.set_xlabel('time since baseline start (s)')

    for ax in (ax1, ax2, ax3):
        for k in 'abc':
            ax.axvline(rel(BLOCK[k]['t']), color=INK, linewidth=1.2, linestyle=(0, (5, 3)), zorder=2)
    ax1.set_xlim(0, end)
    ax1.legend(handles=[
        plt.Line2D([], [], color=MAIN, linewidth=LW, label='s2-s6 (main path)'),
        plt.Line2D([], [], color=DETOUR, linewidth=LW, label='s2-s3'),
        plt.Line2D([], [], color=DETOUR, linewidth=LW, linestyle=(0, (4, 2)), label='s3-s6'),
        plt.Line2D([], [], color=ATTACK, linewidth=LW, label='s3-s5'),
        plt.Line2D([], [], color=GREY, linewidth=2.0, label='s5-s6'),
    ], loc='upper left', bbox_to_anchor=(0.0, 0.93), ncol=1, frameon=False, fontsize=13, handlelength=1.8,
        labelcolor=INK2)
    save(fig, 'task5_fullrun_slide')


def main():
    os.makedirs(OUT, exist_ok=True)
    hook_loss_zoom()
    fig6_detector_h2()
    fig5_slide()
    cost_s2s6()
    fig4b_caseb_zoom()
    task5_fullrun_slide()


if __name__ == '__main__':
    main()
