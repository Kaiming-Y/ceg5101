#!/usr/bin/env python3
"""Print the routes the controller should pick in each case (static C0 plus a
beta penalty on the links the attack uses). Handy for the report's
'expected vs observed' discussion.

    python3 support/analysis/expected_paths.py [beta]
"""
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / 'code' / 'controller'))
from sdn_logic import BASE_COSTS, dijkstra, link_key, path_links, path_name  # noqa: E402


def graph(penalty, beta):
    g = {n: {} for n in range(1, 7)}
    for (a, b), c in BASE_COSTS.items():
        g[a][b] = g[b][a] = c + (beta if (a, b) in penalty else 0)
    return g


def main():
    beta = float(sys.argv[1]) if len(sys.argv) > 1 else 30.0
    g0 = graph(set(), 0)
    p, c = dijkstra(g0, 1, 6)
    print('Static costs: h1->h6 = %s (cost %g)\n' % (path_name(p), c))
    print('%-5s %-8s %-14s %-24s %-16s %s' % ('case', 'flood', 'nominal link', 'attack path (links)',
                                             'h1->h6 during', 'reroute?'))
    for case, (s, d, nominal) in (('a', (2, 3, 's2-s3')), ('b', (2, 6, 's2-s6')), ('c', (5, 6, 's5-s6'))):
        ap, _ = dijkstra(g0, s, d)
        links = set(path_links(ap))
        hp, hc = dijkstra(graph(links, beta), 1, 6)
        print('%-5s h%d->h%d   %-14s %-24s %-16s %s' % (
            case, s, d, nominal, '%s (%s)' % (path_name(ap), ','.join('s%d-s%d' % l for l in sorted(links))),
            '%s (%g)' % (path_name(hp), hc), 'yes' if hp != p else 'no'))
    print('\nNote: with the given C0, h5->h6 takes s5-s3-s6 (16) rather than s5-s6 (20).')


if __name__ == '__main__':
    main()
