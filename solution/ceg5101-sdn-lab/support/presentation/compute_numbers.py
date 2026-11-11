#!/usr/bin/env python3
"""Recompute every number used on the slides from the raw result files.

    ~/ryu-venv/bin/python support/presentation/compute_numbers.py

Prints plain text; presentation/source/numbers.md is written from this output.
"""
import importlib.util
import json
import os
import re
import statistics as st

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))
spec = importlib.util.spec_from_file_location('pr', os.path.join(ROOT, 'support', 'analysis', 'plot_results.py'))
pr = importlib.util.module_from_spec(spec)
spec.loader.exec_module(pr)

RUNS = {'R1': 'validation-abc', 'R2': 'run1-abc', 'R3': 'run2-abc', 'VM': 'vm-delay-abc'}
C0 = {'s2-s3': 10, 's2-s6': 14, 's3-s5': 9, 's3-s6': 7, 's5-s6': 20, 's1-s2': 5}


def load(name):
    return pr.load_run(os.path.join(ROOT, 'results', name))


def blocks(d, sc):
    a, b = sc['attack_start'], sc['attack_end']
    return [e for e in d['events'] if e['event'] == 'block' and e['src'] == sc['attacker'] and a <= e['t'] <= b + 5]


def h1_reroutes(d):
    return [e for e in d['events'] if e['event'] == 'reroute' and (e['src'], e['dst']) == ('h1', 'h6')]


def marks(d, name):
    return [m for m in d['timeline']['marks'] if m['name'] == name]


def main():
    for rid, name in RUNS.items():
        d = load(name)
        t0 = d['t0']
        print('=' * 70)
        print(rid, name, 't0', t0)
        end_marks = {m['scenario']: m['t'] for m in marks(d, 'attack_end') if 'scenario' in m}
        for sc in d['timeline']['scenarios']:
            a, b = sc['attack_start'], sc['attack_end']
            bl = blocks(d, sc)
            tb = bl[0]['t'] if bl else None
            win = [p for p in d['iperf'] if a <= p[0] < b]
            worst = max(win, key=lambda p: p[2])
            low = min(win, key=lambda p: p[1])
            mean_loss = sum(p[2] for p in win) / len(win)
            cap = d['captures'].get(sc['id'], [])
            n_before = sum(1 for t in cap if t < tb)
            after = [t for t in cap if t >= tb]
            n_1s = sum(1 for t in after if t < tb + 1)
            last_after = (max(after) - tb) if after else None
            n_late = sum(1 for t in cap if t >= tb + 1)
            rows = [r for r in d['counters'] if r['scenario'] == sc['id']]
            tx = [(float(r['t']), int(r['attacker_tx_packets'])) for r in rows]
            pre = [x for x in tx if x[0] <= tb]
            rate = None
            if len(pre) >= 2:
                rate = (pre[-1][1] - pre[0][1]) / (pre[-1][0] - pre[0][0])
            tx_total = tx[-1][1] if tx else None
            print('case %s  start %.2f  end(scn) %.2f  end(mark) %.2f  block %.3f  delay %.3f  pps %s base %s T %s links %s' % (
                sc['id'], a - t0, b - t0, end_marks.get(sc['id'], 0) - t0, tb - t0, tb - a,
                bl[0]['detail']['pps'], bl[0]['detail']['baseline'], bl[0]['detail']['threshold'],
                bl[0]['detail']['links']))
            print('   mean loss %.2f  worst 1s %.1f%% @%.0f  lowest Mbps %.2f @%.0f' % (
                mean_loss, worst[2], worst[0] - t0, low[1], low[0] - t0))
            print('   leaked before block %d  in [tb,tb+1) %d  last after-block pkt +%s ms  after tb+1 %d  '
                  'attacker pre-block rate %s pkt/s  attacker tx total %s' % (
                      n_before, n_1s, None if last_after is None else round(last_after * 1000, 1), n_late,
                      None if rate is None else round(rate), tx_total))
            lossy = [(round(p[0] - t0), round(p[2], 1), round(p[1], 2)) for p in d['iperf']
                     if a - 1 <= p[0] < a + 8 and p[2] > 0]
            print('   lossy seconds (t_end_rel, loss, Mbps):', lossy)
        rr = h1_reroutes(d)
        for e in rr:
            print('reroute h1->h6 t=%.3f %s %s->%s %s/%s' % (e['t'] - t0, e['detail']['reason'], e['detail']['old'],
                                                           e['detail']['new'], e['detail']['old_cost'],
                                                           e['detail']['new_cost']))
        scb = [s for s in d['timeline']['scenarios'] if s['id'] == 'b']
        if scb and len(rr) >= 2:
            sc = scb[0]
            back = rr[1]['t']
            print('return: %.2f s after flood start, %.2f after start+25, %.2f after scn attack_end, %.2f after end mark' % (
                back - sc['attack_start'], back - sc['attack_start'] - 25, back - sc['attack_end'],
                back - end_marks['b']))
            old = rr[0]['detail']
            st_cost = old['old_cost'] - 30
            print('beta needed at block: > %.2f  (old-30=%.2f, new=%.2f, margin 2)' % (
                old['new_cost'] + 2 - st_cost, st_cost, old['new_cost']))
        # plateaus: median norm_cost while A=1 and rate < 0.5 Mbps
        for link in ('s2-s3', 's2-s6', 's3-s5', 's3-s6', 's5-s6', 's1-s2'):
            s = d['links'].get(link, [])
            plat = [p[1] for p in s if p[4] == 1 and p[3] < 0.5]
            peak = max(p[1] for p in s)
            base = st.median([p[1] for p in s if p[0] - t0 < 38])
            anom = [p for p in s if p[4] == 1]
            span = (anom[0][0] - t0, anom[-1][0] - t0) if anom else None
            print('  %s C0=%s plateau(min A=1,rate<0.5)=%s  peak %.3f  base(median <38 s) %.3f  A=1 span %s'
                  % (link, s[0][2] if False else '', round(min(plat), 3) if plat else '-', peak, base,
                     None if not span else '%.1f-%.1f' % span))
        # ping RTT
        ping = d['ping']
        if ping:
            print('  ping median before first flood %.2f ms' % st.median(
                [r for t, r in ping if t < d['timeline']['scenarios'][0]['attack_start']]))
            if len(rr) >= 2:
                det = [r for t, r in ping if rr[0]['t'] + 1 <= t < rr[1]['t']]
                det_after = [r for t, r in ping if scb[0]['attack_end'] + 1 <= t < rr[1]['t']]
                back = [r for t, r in ping if rr[1]['t'] + 1 <= t < d['timeline']['scenarios'][2]['attack_start']]
                print('  ping median on detour %.2f ms, detour after flood ended %.2f, after return %.2f' % (
                    st.median(det), st.median(det_after), st.median(back)))
            bwin = [(t, r) for t, r in ping if scb[0]['attack_start'] <= t < blocks(d, scb[0])[0]['t'] + 1]
            print('  case b max RTT before block %.1f ms' % max(r for t, r in bwin))
        # h1 rate
        pps = []
        with open(os.path.join(ROOT, 'results', name, 'iperf_server.txt')) as f:
            for line in f:
                m = re.search(r'sec .* (\d+)/\s*(\d+) \(.*?\) .* (\d+) pps', line)
                if m and '0.0000-2' not in line:
                    pps.append(int(m.group(2)))
        print('  iperf datagrams per 1 s interval: median %s, min %s, max %s' % (
            st.median(pps), min(pps), max(pps)))
        h1 = [r for r in pr.read_csv(os.path.join(ROOT, 'results', name, 'controller', 'sources.csv'))
              if r['ip'] == '10.0.0.1']
        print('  controller h1 pps median %.1f' % st.median(float(r['pps']) for r in h1[3:]))
        ts = sorted({float(r['t']) for r in h1})
        gaps = [b - a for a, b in zip(ts, ts[1:])]
        print('  sample interval median %.3f s (min %.3f max %.3f)' % (st.median(gaps), min(gaps), max(gaps)))
        with open(os.path.join(ROOT, 'results', name, 'iperf_server.txt')) as f:
            tot = [l for l in f if re.search(r'0\.0000-\d{2,}\.\d+ sec .*/', l)]
        print('  iperf total:', tot[-1].strip() if tot else '-')

    # extended experiments
    for name in ('exp-beta0-b', 'exp-beta2-b', 'exp-c-s5s6-cost8', 'exp-linkfail-s2s6', 'vm-autowarmup-b'):
        d = load(name)
        t0 = d['t0']
        print('=' * 70)
        print(name)
        for sc in d['timeline']['scenarios']:
            a, b = sc['attack_start'], sc['attack_end']
            bl = blocks(d, sc)
            tb = bl[0]['t']
            win = [p for p in d['iperf'] if a <= p[0] < b]
            worst = max(win, key=lambda p: p[2])
            post = [p for p in d['iperf'] if tb + 1 <= p[0] < b]
            link = bl[0]['detail']['links']
            print(' case %s delay %.3f links %s worst %.1f%% loss after block (max) %.2f' % (
                sc['id'], tb - a, link, worst[2], max(p[2] for p in post)))
            for ln in link:
                s = d['links'][ln]
                during = [p[1] for p in s if tb <= p[0] <= b]
                aft = [p[1] for p in s if tb + 2 <= p[0] <= b]
                print('   %s cost/C0 at block %.3f, mean during flood after block %.3f, min %.3f, last %.3f' % (
                    ln, during[0], st.mean(during), min(aft), aft[-1]))
        print(' h1->h6 reroutes:', [(round(e['t'] - t0, 3), e['detail']['reason'], e['detail']['new'])
                                    for e in h1_reroutes(d)])
        for dn in marks(d, 'link_down'):
            rr = [e for e in h1_reroutes(d) if e['t'] >= dn['t']]
            up = marks(d, 'link_up')[0]['t']
            ev = [e for e in d['events'] if e['event'] == 'link_down']
            print(' link_down mark %.3f, controller link_down %.3f, reroute %.3f (%.1f ms after controller event,'
                  ' %.1f ms after mark); link_up mark %.3f; back %.3f (%.2f s after up)' % (
                      dn['t'] - t0, ev[0]['t'] - t0, rr[0]['t'] - t0, (rr[0]['t'] - ev[0]['t']) * 1000,
                      (rr[0]['t'] - dn['t']) * 1000, up - t0, rr[1]['t'] - t0, rr[1]['t'] - up))
            lossy = [(round(p[0] - t0), round(p[2], 2)) for p in d['iperf'] if p[2] > 0]
            print(' lossy seconds', lossy)
        with open(os.path.join(ROOT, 'results', name, 'iperf_server.txt')) as f:
            tot = [l for l in f if re.search(r'0\.0000-\d{2,}\.\d+ sec .*/', l)]
        print('  iperf total:', tot[-1].strip() if tot else '-')


if __name__ == '__main__':
    main()
