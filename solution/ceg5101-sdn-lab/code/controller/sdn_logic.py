"""
Pure-Python logic for the anomaly-aware routing controller.

Nothing in this module imports Ryu, so it can be unit-tested (support/tests/) and
reused by the analysis scripts without Mininet or an OpenFlow switch.

Contents
    Config            tunable parameters (overridable with CEG_* env vars)
    BASE_COSTS        static link costs C0 taken from ceg_mesh_topo.py (delay in ms)
    dynamic_cost()    C(t) = C0 + alpha * R(t)/Rmax + beta * A(t)      (Eq. 1)
    dijkstra()        lowest-cost path on a {node: {nbr: cost}} graph
    AnomalyDetector   per-source EMA baseline + adaptive threshold
"""

import heapq
import math
import os


def _env(name, default, cast=float):
    value = os.environ.get(name)
    if value is None or value == '':
        return default
    return cast(value)


class Config(object):
    """All tunables in one place. Every field can be overridden with an
    environment variable so experiments can sweep parameters without
    editing code (e.g. CEG_BETA=50 ryu-manager ...)."""

    def __init__(self):
        # --- monitoring -------------------------------------------------
        self.poll_interval = _env('CEG_POLL', 2.0)            # s between stats requests
        self.link_capacity_bps = _env('CEG_RMAX_MBPS', 40.0) * 1e6   # Rmax (TCLink bw=40)
        self.load_smoothing = _env('CEG_LOAD_EMA', 0.6)       # EMA weight of newest link-rate sample

        # --- link-cost model (Eq. 1) -----------------------------------
        self.alpha = _env('CEG_ALPHA', 10.0)                  # weight of traffic load
        self.beta = _env('CEG_BETA', 30.0)                    # weight of anomaly flag
        self.reroute_margin = _env('CEG_MARGIN', 2.0)         # hysteresis: new path must be this much cheaper

        # --- anomaly detection -----------------------------------------
        self.ema_alpha = _env('CEG_EMA_ALPHA', 0.3)           # same alpha as anomaly_detection.py
        self.k_mult = _env('CEG_K', 3.0)                      # current > k * baseline (reference rule)
        self.k_sigma = _env('CEG_K_SIGMA', 4.0)               # ... and > baseline + k_sigma * std
        self.min_attack_pps = _env('CEG_MIN_PPS', 500.0)      # absolute floor, ignores tiny bursts
        self.warmup_samples = _env('CEG_WARMUP', 5, int)      # samples before a source can be flagged
        self.consecutive = _env('CEG_CONSEC', 1, int)         # intervals over threshold before blocking

        # --- mitigation lifecycle --------------------------------------
        self.anomaly_hold = _env('CEG_HOLD', 10.0)            # s A_ij stays 1 after attack traffic stops
        self.auto_unblock = bool(_env('CEG_AUTO_UNBLOCK', 1, int))
        self.unblock_quiet = _env('CEG_UNBLOCK_QUIET', 10.0)  # s without dropped packets before unblock

        # --- topology ---------------------------------------------------
        self.expected_links = _env('CEG_EXPECTED_LINKS', 11, int)  # undirected; 0 = don't wait
        self.cost_override = os.environ.get('CEG_COST_OVERRIDE', '')   # applied to BASE_COSTS at import

        # --- output -------------------------------------------------------
        self.log_dir = os.environ.get('CEG_LOG_DIR', os.path.join(os.getcwd(), 'results', 'live'))

    def as_dict(self):
        return dict(self.__dict__)


# ---------------------------------------------------------------------------
# Static link costs C0 (= TCLink delay in ms in code/topology/ceg_mesh_topo.py).
# Keys are undirected (low dpid, high dpid).
# ---------------------------------------------------------------------------
BASE_COSTS = {
    (1, 2): 5,
    (2, 3): 10,
    (4, 5): 15,
    (5, 6): 20,
    (1, 4): 8,
    (2, 5): 12,
    (3, 6): 7,
    (1, 5): 18,
    (2, 4): 6,
    (2, 6): 14,
    (3, 5): 9,
}
DEFAULT_COST = 10


def link_key(a, b):
    """Undirected key for the link between switches a and b."""
    return (a, b) if a < b else (b, a)


def apply_cost_override(spec):
    """Replace C0 of selected links, e.g. CEG_COST_OVERRIDE='5-6:8,2-3:12'.
    Used for controlled experiments (PLAN Phase 6.3)."""
    for item in filter(None, (s.strip() for s in spec.split(','))):
        ends, cost = item.split(':')
        a, b = (int(x.strip().lstrip('s')) for x in ends.split('-'))
        BASE_COSTS[link_key(a, b)] = float(cost)


apply_cost_override(os.environ.get('CEG_COST_OVERRIDE', ''))


def link_name(key):
    return 's%d-s%d' % key


def base_cost(a, b):
    return BASE_COSTS.get(link_key(a, b), DEFAULT_COST)


def path_links(path):
    """[1, 2, 6] -> [(1, 2), (2, 6)]"""
    return [link_key(path[i], path[i + 1]) for i in range(len(path) - 1)]


def path_name(path):
    return '-'.join('s%d' % d for d in path) if path else ''


def dynamic_cost(c0, rate_bps, anomaly, cfg):
    """Eq. (1): C_ij(t) = C0_ij + alpha * R_ij(t) / Rmax_ij + beta * A_ij(t).

    Utilisation is clamped to 1 because the measured rate can briefly
    exceed the shaped capacity due to sampling jitter."""
    util = min(max(rate_bps, 0.0) / cfg.link_capacity_bps, 1.0)
    return c0 + cfg.alpha * util + (cfg.beta if anomaly else 0.0)


def dijkstra(graph, src, dst):
    """Lowest-cost path on {node: {nbr: cost}}. Returns (path, cost) or
    (None, inf). Ties are broken by node id so results are deterministic."""
    if src not in graph or dst not in graph:
        return None, float('inf')
    dist = {src: 0.0}
    prev = {}
    queue = [(0.0, src)]
    visited = set()
    while queue:
        d, node = heapq.heappop(queue)
        if node in visited:
            continue
        visited.add(node)
        if node == dst:
            path = [dst]
            while path[-1] != src:
                path.append(prev[path[-1]])
            return path[::-1], d
        for nbr in sorted(graph[node]):
            nd = d + graph[node][nbr]
            if nd < dist.get(nbr, float('inf')):
                dist[nbr] = nd
                prev[nbr] = node
                heapq.heappush(queue, (nd, nbr))
    return None, float('inf')


def path_cost(graph, path):
    """Sum of edge costs along path, inf if any edge is missing."""
    total = 0.0
    for a, b in zip(path, path[1:]):
        if b not in graph.get(a, {}):
            return float('inf')
        total += graph[a][b]
    return total


class _SourceState(object):
    __slots__ = ('baseline', 'var', 'samples', 'over')

    def __init__(self, rate):
        self.baseline = rate
        self.var = 0.0
        self.samples = 1
        self.over = 0


class AnomalyDetector(object):
    """Per-source traffic baseline with an adaptive threshold.

    Improvements over the reference anomaly_detection.py:
      * the threshold is checked *before* the baseline is updated, and
        anomalous samples are not learned (the reference updates first,
        which makes the effective rule ~21x baseline instead of 3x);
      * threshold = max(k * EMA, EMA + k_sigma * EW-std, min_pps), so it
        adapts to how bursty a source normally is (limitation (a));
      * a warm-up period, so a source is never judged on its first samples.
    """

    def __init__(self, cfg):
        self.cfg = cfg
        self.state = {}

    def threshold(self, ip):
        st = self.state.get(ip)
        if st is None:
            return float('inf')
        c = self.cfg
        return max(c.k_mult * st.baseline,
                   st.baseline + c.k_sigma * math.sqrt(st.var),
                   c.min_attack_pps)

    def baseline(self, ip):
        st = self.state.get(ip)
        return st.baseline if st else 0.0

    def update(self, ip, rate):
        """Feed one rate sample (packets/s). Returns True when the source
        should be treated as anomalous."""
        st = self.state.get(ip)
        if st is None:
            self.state[ip] = _SourceState(rate)
            return False

        over = st.samples >= self.cfg.warmup_samples and rate > self.threshold(ip)
        st.over = st.over + 1 if over else 0
        if not over:
            # Exponentially weighted mean and variance (West, 1979).
            a = self.cfg.ema_alpha
            diff = rate - st.baseline
            st.baseline += a * diff
            st.var = (1 - a) * (st.var + a * diff * diff)
            st.samples += 1
        return st.over >= self.cfg.consecutive

    def reset_alarm(self, ip):
        st = self.state.get(ip)
        if st:
            st.over = 0
