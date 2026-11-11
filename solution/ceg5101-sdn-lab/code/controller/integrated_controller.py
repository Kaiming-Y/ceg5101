"""
CEG5101 CA2 - Anomaly-aware Routing and Blocking Controller (Ryu, OpenFlow 1.3)

Integrates the two reference controllers:
  * resilient_controller.py  -> topology discovery + Dijkstra routing
  * anomaly_detection.py     -> flow-stat monitoring, EMA baseline, IP blocking
and adds what neither has:
  * per-link load measurement (port stats) and the dynamic link cost of Eq. (1)
        C_ij(t) = C0_ij + alpha * R_ij(t) / Rmax + beta * A_ij(t)
  * proactive, path-wide rerouting of legitimate flows when costs change,
    with hysteresis, and recovery once the anomaly is over
  * CSV logs for the plots (links.csv, paths.csv, sources.csv, events.csv)

Run:
    ryu-manager --observe-links code/controller/integrated_controller.py
Parameters: see code/controller/sdn_logic.py (Config), overridable via CEG_* env vars.
"""

import csv
import json
import os
import time

from ryu.base import app_manager
from ryu.controller import ofp_event
from ryu.controller.handler import (CONFIG_DISPATCHER, DEAD_DISPATCHER,
                                    MAIN_DISPATCHER, set_ev_cls)
from ryu.lib import hub
from ryu.lib.packet import arp, ether_types, ethernet, icmp, ipv4, packet
from ryu.ofproto import ofproto_v1_3
from ryu.topology import event as topo_event
from ryu.topology.api import get_link, get_switch

from sdn_logic import (AnomalyDetector, Config, base_cost, dijkstra,
                       dynamic_cost, link_key, link_name, path_cost,
                       path_links, path_name)

PRIO_TABLE_MISS = 0
PRIO_FORWARD = 10
PRIO_DROP = 5000            # same priority as the reference blocking rule

COOKIE_FORWARD = 0x10
COOKIE_DROP = 0xD0

ICMP_ECHO_REPLY = 0


def host_name(ip):
    """10.0.0.6 -> h6 (only used for readable logs)."""
    return 'h' + ip.rsplit('.', 1)[-1]


class Host(object):
    __slots__ = ('ip', 'mac', 'dpid', 'port')

    def __init__(self, ip, mac, dpid, port):
        self.ip, self.mac, self.dpid, self.port = ip, mac, dpid, port


class AnomalyAwareController(app_manager.RyuApp):
    OFP_VERSIONS = [ofproto_v1_3.OFP_VERSION]

    def __init__(self, *args, **kwargs):
        super(AnomalyAwareController, self).__init__(*args, **kwargs)
        self.cfg = Config()
        self.detector = AnomalyDetector(self.cfg)

        # topology
        self.datapaths = {}         # dpid -> datapath
        self.adj = {}               # dpid -> {neighbour dpid: local out port}
        self.switch_ports = {}      # dpid -> set(port_no)
        self.topology_ready = False

        # hosts and routed flows
        self.hosts = {}             # ip -> Host
        self.flows = {}             # (src_ip, dst_ip) -> {'path', 'keys', 'rate_bps'}

        # monitoring state
        self.flow_counts = {}       # (dpid, match key) -> (packets, bytes)
        self.drop_counts = {}       # (dpid, ip) -> packets
        self.port_prev = {}         # (dpid, port) -> (tx_bytes, duration_s)
        self.dir_rate = {}          # (dpid, port) -> bps
        self.link_rate = {}         # link key -> smoothed bps
        self.last_eval = None
        self._reset_interval()

        # mitigation state
        self.blocked = {}           # ip -> {'since', 'last_drop', 'links'}
        self.anomaly_until = {}     # link key -> time until which A_ij = 1

        self._open_logs()
        self.logger.info("Config: %s", json.dumps(self.cfg.as_dict()))
        self.monitor_thread = hub.spawn(self._monitor)

    # ==================================================================
    # Logging
    # ==================================================================
    def _open_logs(self):
        os.makedirs(self.cfg.log_dir, exist_ok=True)
        self._csv = {}
        headers = {
            'links': ['t', 'link', 'c0', 'rate_mbps', 'util', 'anomaly', 'cost', 'norm_cost'],
            'paths': ['t', 'src', 'dst', 'path', 'cost', 'rate_mbps'],
            'sources': ['t', 'ip', 'pps', 'baseline', 'threshold', 'blocked'],
            'events': ['t', 'event', 'src', 'dst', 'detail'],
        }
        for name, header in headers.items():
            f = open(os.path.join(self.cfg.log_dir, name + '.csv'), 'w', newline='', buffering=1, encoding='utf-8')
            w = csv.writer(f)
            w.writerow(header)
            self._csv[name] = (f, w)
        with open(os.path.join(self.cfg.log_dir, 'config.json'), 'w', encoding='utf-8') as f:
            json.dump(self.cfg.as_dict(), f, indent=2)

    def _row(self, name, row):
        self._csv[name][1].writerow(row)

    def _event(self, kind, src='', dst='', **detail):
        self._row('events', [round(time.time(), 3), kind, src, dst, json.dumps(detail)])
        self.logger.warning("[EVENT] %s %s->%s %s", kind, src, dst, detail)

    # ==================================================================
    # Switch / topology handling
    # ==================================================================
    @set_ev_cls(ofp_event.EventOFPSwitchFeatures, CONFIG_DISPATCHER)
    def switch_features_handler(self, ev):
        dp = ev.msg.datapath
        ofp, parser = dp.ofproto, dp.ofproto_parser
        # Start from an empty table, then install the table-miss entry.
        dp.send_msg(parser.OFPFlowMod(datapath=dp, command=ofp.OFPFC_DELETE,
                                      table_id=ofp.OFPTT_ALL, out_port=ofp.OFPP_ANY,
                                      out_group=ofp.OFPG_ANY, match=parser.OFPMatch()))
        actions = [parser.OFPActionOutput(ofp.OFPP_CONTROLLER, ofp.OFPCML_NO_BUFFER)]
        self._add_flow(dp, PRIO_TABLE_MISS, parser.OFPMatch(), actions)

    @set_ev_cls(ofp_event.EventOFPStateChange, [MAIN_DISPATCHER, DEAD_DISPATCHER])
    def state_change_handler(self, ev):
        dp = ev.datapath
        if ev.state == MAIN_DISPATCHER:
            self.datapaths[dp.id] = dp
            self.logger.info("Switch connected: s%d", dp.id)
        elif ev.state == DEAD_DISPATCHER and dp.id in self.datapaths:
            del self.datapaths[dp.id]
            self.logger.warning("Switch disconnected: s%d", dp.id)

    @set_ev_cls([topo_event.EventSwitchEnter, topo_event.EventSwitchLeave,
                 topo_event.EventLinkAdd, topo_event.EventLinkDelete])
    def topology_change_handler(self, ev):
        self._refresh_topology()

    def _refresh_topology(self):
        old_links = set(self._links())
        adj, ports = {}, {}
        for sw in get_switch(self, None):
            adj[sw.dp.id] = {}
            ports[sw.dp.id] = set(p.port_no for p in sw.ports)
        for link in get_link(self, None):
            adj.setdefault(link.src.dpid, {})[link.dst.dpid] = link.src.port_no
        self.adj, self.switch_ports = adj, ports

        links = set(self._links())
        expected = self.cfg.expected_links
        ready = len(links) >= expected if expected else len(links) > 0
        if ready and not self.topology_ready:
            self._event('topology_ready', detail_links=len(links))
        # Latched: once the first full discovery is done, a failed link must
        # not stop monitoring and packet-in handling (ARP refreshes would be
        # ignored and hosts would lose reachability during the outage).
        self.topology_ready = self.topology_ready or ready

        with open(os.path.join(self.cfg.log_dir, 'topology.json'), 'w', encoding='utf-8') as f:
            json.dump({'t': time.time(), 'ready': ready,
                       'switches': sorted(adj),
                       'links': [link_name(l) for l in sorted(links)]}, f, indent=2)

        lost = old_links - links
        if lost:
            self._event('link_down', detail_links=[link_name(l) for l in sorted(lost)])
            self._reroute_all(reason='link_down')

    def _links(self):
        """Undirected switch-to-switch links seen in both directions."""
        return [link_key(a, b) for a in self.adj for b in self.adj[a]
                if a < b and a in self.adj.get(b, {})]

    def _inter_switch_ports(self, dpid):
        return set(self.adj.get(dpid, {}).values())

    # ==================================================================
    # Packet-in: host learning, ARP, IPv4 routing
    # ==================================================================
    @set_ev_cls(ofp_event.EventOFPPacketIn, MAIN_DISPATCHER)
    def packet_in_handler(self, ev):
        msg = ev.msg
        dp = msg.datapath
        in_port = msg.match['in_port']
        pkt = packet.Packet(msg.data)
        eth = pkt.get_protocol(ethernet.ethernet)
        if eth is None or eth.ethertype == ether_types.ETH_TYPE_LLDP:
            return
        # Until every link is known we cannot tell host ports from
        # inter-switch ports, and flooding would loop in the mesh.
        if not self.topology_ready:
            return

        from_host = in_port not in self._inter_switch_ports(dp.id)
        arp_pkt = pkt.get_protocol(arp.arp)
        if arp_pkt:
            if from_host:
                self._handle_arp(msg, dp, in_port, arp_pkt)
            return
        ip_pkt = pkt.get_protocol(ipv4.ipv4)
        if ip_pkt:
            self._handle_ipv4(msg, dp, in_port, pkt, eth, ip_pkt, from_host)
        # Anything else (IPv6, ...) is dropped.

    def _learn_host(self, ip, mac, dpid, port):
        if ip in self.hosts or ip == '0.0.0.0':
            return
        self.hosts[ip] = Host(ip, mac, dpid, port)
        self.logger.info("Host learned: %s (%s) at s%d port %d", ip, mac, dpid, port)

    def _handle_arp(self, msg, dp, in_port, a):
        """Proxy ARP when the target is known; otherwise deliver the frame
        directly to every host-facing port (never across switch links, so
        the mesh cannot create a broadcast storm)."""
        self._learn_host(a.src_ip, a.src_mac, dp.id, in_port)
        if a.opcode == arp.ARP_REQUEST and a.src_ip != a.dst_ip:
            target = self.hosts.get(a.dst_ip)
            if target:
                self._send_arp_reply(dp, in_port, a, target.mac)
                return
        elif a.opcode == arp.ARP_REPLY:
            dst = self.hosts.get(a.dst_ip)
            if dst and dst.dpid in self.datapaths:
                self._send_raw(self.datapaths[dst.dpid], dst.port, msg.data)
                return
        self._flood_to_hosts(msg.data, (dp.id, in_port))

    def _send_arp_reply(self, dp, port, req, mac):
        p = packet.Packet()
        p.add_protocol(ethernet.ethernet(ethertype=ether_types.ETH_TYPE_ARP,
                                         dst=req.src_mac, src=mac))
        p.add_protocol(arp.arp(opcode=arp.ARP_REPLY, src_mac=mac, src_ip=req.dst_ip,
                               dst_mac=req.src_mac, dst_ip=req.src_ip))
        p.serialize()
        self._send_raw(dp, port, p.data)

    def _flood_to_hosts(self, data, exclude):
        for dpid, dp in self.datapaths.items():
            for port in self.switch_ports.get(dpid, ()):
                if port >= dp.ofproto.OFPP_MAX or (dpid, port) == exclude:
                    continue
                if port not in self._inter_switch_ports(dpid):
                    self._send_raw(dp, port, data)

    def _handle_ipv4(self, msg, dp, in_port, pkt, eth, ip_pkt, from_host):
        src, dst = ip_pkt.src, ip_pkt.dst
        if src in self.blocked:
            return                                  # drop rule not yet hit / in flight
        if from_host:
            self._learn_host(src, eth.src, dp.id, in_port)
        sh, dh = self.hosts.get(src), self.hosts.get(dst)
        if sh is None or dh is None:
            return

        icmp_type = None
        if ip_pkt.proto == 1:
            ic = pkt.get_protocol(icmp.icmp)
            icmp_type = ic.type if ic else None
        key = (src, dst, ip_pkt.proto, icmp_type)

        entry = self.flows.get((src, dst))
        if entry is None:
            path, cost = dijkstra(self._cost_graph(), sh.dpid, dh.dpid)
            if not path:
                self.logger.warning("No path %s -> %s", src, dst)
                return
            entry = {'path': path, 'keys': set(), 'rate_bps': 0.0}
            self.flows[(src, dst)] = entry
            self._event('path_set', host_name(src), host_name(dst),
                        path=path_name(path), cost=round(cost, 2))
        if key not in entry['keys']:
            entry['keys'].add(key)
            self._install_path(entry['path'], key, dh)

        out_port = self._next_port(dp.id, entry['path'], dh)
        if out_port is not None:
            self._send_raw(dp, out_port, msg.data, in_port)

    def _next_port(self, dpid, path, dh):
        if dpid == dh.dpid:
            return dh.port
        if dpid in path:
            nxt = path[path.index(dpid) + 1]
        else:                                       # packet caught mid-reroute
            p, _ = dijkstra(self._cost_graph(), dpid, dh.dpid)
            if not p:
                return None
            nxt = p[1]
        return self.adj.get(dpid, {}).get(nxt)

    # ==================================================================
    # Flow programming
    # ==================================================================
    def _add_flow(self, dp, priority, match, actions, cookie=0):
        ofp, parser = dp.ofproto, dp.ofproto_parser
        inst = [parser.OFPInstructionActions(ofp.OFPIT_APPLY_ACTIONS, actions)]
        dp.send_msg(parser.OFPFlowMod(datapath=dp, cookie=cookie, priority=priority,
                                      match=match, instructions=inst))

    def _del_flow(self, dp, priority, match):
        ofp, parser = dp.ofproto, dp.ofproto_parser
        dp.send_msg(parser.OFPFlowMod(datapath=dp, command=ofp.OFPFC_DELETE_STRICT,
                                      priority=priority, match=match,
                                      out_port=ofp.OFPP_ANY, out_group=ofp.OFPG_ANY))

    @staticmethod
    def _match(parser, key):
        src, dst, proto, icmp_type = key
        fields = dict(eth_type=ether_types.ETH_TYPE_IP, ipv4_src=src, ipv4_dst=dst,
                      ip_proto=proto)
        if proto == 1 and icmp_type is not None:
            fields['icmpv4_type'] = icmp_type
        return parser.OFPMatch(**fields)

    def _install_path(self, path, key, dh):
        """Install key on every switch of path, egress first so that the
        ingress switch never forwards into a switch without a rule."""
        for i in reversed(range(len(path))):
            dpid = path[i]
            dp = self.datapaths.get(dpid)
            if dp is None:
                continue
            out = dh.port if i == len(path) - 1 else self.adj[dpid][path[i + 1]]
            parser = dp.ofproto_parser
            self._add_flow(dp, PRIO_FORWARD, self._match(parser, key),
                           [parser.OFPActionOutput(out)], COOKIE_FORWARD)

    def _send_raw(self, dp, port, data, in_port=None):
        ofp, parser = dp.ofproto, dp.ofproto_parser
        dp.send_msg(parser.OFPPacketOut(
            datapath=dp, buffer_id=ofp.OFP_NO_BUFFER,
            in_port=ofp.OFPP_CONTROLLER if in_port is None else in_port,
            actions=[parser.OFPActionOutput(port)], data=data))

    # ==================================================================
    # Monitoring loop
    # ==================================================================
    def _reset_interval(self):
        self.iv_src_pkts = {}       # ip -> packets (excl. ICMP echo replies), at ingress switch
        self.iv_pair_pkts = {}      # (src, dst) -> packets (excl. echo replies)
        self.iv_pair_bytes = {}     # (src, dst) -> bytes (all)
        self.iv_drop_pkts = {}      # ip -> packets hitting its drop rule at ingress

    def _monitor(self):
        while True:
            hub.sleep(self.cfg.poll_interval)
            if not self.topology_ready:
                continue
            self._reset_interval()
            for dp in list(self.datapaths.values()):
                ofp, parser = dp.ofproto, dp.ofproto_parser
                dp.send_msg(parser.OFPFlowStatsRequest(dp, 0, ofp.OFPTT_ALL, ofp.OFPP_ANY,
                                                       ofp.OFPG_ANY, 0, 0, parser.OFPMatch()))
                dp.send_msg(parser.OFPPortStatsRequest(dp, 0, ofp.OFPP_ANY))
            hub.sleep(0.4)                          # let the replies arrive
            try:
                self._evaluate()
            except Exception:                       # keep monitoring alive
                self.logger.exception("evaluation failed")

    @set_ev_cls(ofp_event.EventOFPFlowStatsReply, MAIN_DISPATCHER)
    def flow_stats_reply_handler(self, ev):
        dpid = ev.msg.datapath.id
        for st in ev.msg.body:
            src = st.match.get('ipv4_src')
            if not src:
                continue
            host = self.hosts.get(src)
            # Count each packet once: only at the switch the source is attached to.
            if host is None or host.dpid != dpid:
                continue
            if st.cookie == COOKIE_DROP:
                prev = self.drop_counts.get((dpid, src), 0)
                self.drop_counts[(dpid, src)] = st.packet_count
                delta = st.packet_count - prev if st.packet_count >= prev else st.packet_count
                self.iv_drop_pkts[src] = self.iv_drop_pkts.get(src, 0) + delta
                continue
            if st.cookie != COOKIE_FORWARD:
                continue
            dst = st.match.get('ipv4_dst')
            proto = st.match.get('ip_proto')
            icmp_type = st.match.get('icmpv4_type')
            k = (dpid, src, dst, proto, icmp_type)
            pp, pb = self.flow_counts.get(k, (0, 0))
            self.flow_counts[k] = (st.packet_count, st.byte_count)
            # A counter that went backwards means the entry was re-created.
            dp_ = st.packet_count - pp if st.packet_count >= pp else st.packet_count
            db_ = st.byte_count - pb if st.byte_count >= pb else st.byte_count
            pair = (src, dst)
            self.iv_pair_bytes[pair] = self.iv_pair_bytes.get(pair, 0) + db_
            if proto == 1 and icmp_type == ICMP_ECHO_REPLY:
                # Victims answering a ping flood must not be blamed for it.
                continue
            self.iv_pair_pkts[pair] = self.iv_pair_pkts.get(pair, 0) + dp_
            self.iv_src_pkts[src] = self.iv_src_pkts.get(src, 0) + dp_

    @set_ev_cls(ofp_event.EventOFPPortStatsReply, MAIN_DISPATCHER)
    def port_stats_reply_handler(self, ev):
        dpid = ev.msg.datapath.id
        for st in ev.msg.body:
            k = (dpid, st.port_no)
            t = st.duration_sec + st.duration_nsec * 1e-9
            prev = self.port_prev.get(k)
            self.port_prev[k] = (st.tx_bytes, t)
            if prev and t > prev[1]:
                self.dir_rate[k] = max(0, st.tx_bytes - prev[0]) * 8.0 / (t - prev[1])

    # ==================================================================
    # Evaluation: detection -> mitigation lifecycle -> costs -> rerouting
    # ==================================================================
    def _evaluate(self):
        now = time.time()
        dt = (now - self.last_eval) if self.last_eval else self.cfg.poll_interval
        self.last_eval = now
        cfg = self.cfg

        # 1. link load R_ij(t), smoothed
        lam = cfg.load_smoothing
        for l in self._links():
            a, b = l
            raw = max(self.dir_rate.get((a, self.adj[a][b]), 0.0),
                      self.dir_rate.get((b, self.adj[b][a]), 0.0))
            self.link_rate[l] = lam * raw + (1 - lam) * self.link_rate.get(l, raw)

        # per-pair own rate (used to avoid self-induced route flapping)
        for pair, entry in list(self.flows.items()):
            r = self.iv_pair_bytes.get(pair, 0) * 8.0 / dt
            entry['rate_bps'] = lam * r + (1 - lam) * entry['rate_bps']

        # 2. anomaly detection per source IP
        for ip in list(self.hosts):
            pps = self.iv_src_pkts.get(ip, 0) / dt
            blocked = ip in self.blocked
            if not blocked and self.detector.update(ip, pps):
                self._block(ip, pps, dt)
                blocked = True
            self._row('sources', [round(now, 3), ip, round(pps, 1),
                                  round(self.detector.baseline(ip), 2),
                                  round(min(self.detector.threshold(ip), 1e9), 2),
                                  int(blocked)])

        # 3. lifecycle of blocked sources: keep A_ij = 1 while the attack
        #    is still hitting the drop rule, release after it goes quiet.
        #    "Still attacking" means a drop rate near the detection
        #    threshold, so the source's normal traffic (e.g. 1 pps ping)
        #    does not keep it blocked forever.
        for ip, info in list(self.blocked.items()):
            drop_pps = self.iv_drop_pkts.get(ip, 0) / dt
            if drop_pps >= 0.5 * self.detector.threshold(ip):
                info['last_drop'] = now
                for l in info['links']:
                    self.anomaly_until[l] = now + cfg.anomaly_hold
            if cfg.auto_unblock and now - info['last_drop'] >= cfg.unblock_quiet:
                self._unblock(ip, now - info['last_drop'])

        # 4. dynamic link costs (logged) and rerouting
        for l in sorted(self._links()):
            c0 = base_cost(*l)
            r = self.link_rate.get(l, 0.0)
            an = self._anomalous(l, now)
            c = dynamic_cost(c0, r, an, cfg)
            self._row('links', [round(now, 3), link_name(l), c0, round(r / 1e6, 3),
                                round(min(r / cfg.link_capacity_bps, 1.0), 4), int(an),
                                round(c, 3), round(c / c0, 4)])
        self._reroute_all(reason='cost_update')

        plain = self._cost_graph()
        for (src, dst), entry in sorted(self.flows.items()):
            self._row('paths', [round(now, 3), host_name(src), host_name(dst),
                                path_name(entry['path']),
                                round(path_cost(plain, entry['path']), 3),
                                round(entry['rate_bps'] / 1e6, 3)])

    def _anomalous(self, l, now=None):
        return self.anomaly_until.get(l, 0) > (now or time.time())

    def _cost_graph(self, own_bps=0.0, own_links=()):
        """Switch graph weighted by Eq. (1). When evaluating a move for a
        flow, its own rate is added to links it does not use yet, so the
        comparison is 'cost if I move' vs 'cost where I am'."""
        now = time.time()
        g = {}
        for a, nbrs in self.adj.items():
            g[a] = {}
            for b in nbrs:
                l = link_key(a, b)
                r = self.link_rate.get(l, 0.0)
                if own_bps and l not in own_links:
                    r += own_bps
                g[a][b] = dynamic_cost(base_cost(a, b), r, self._anomalous(l, now), self.cfg)
        return g

    def _reroute_all(self, reason):
        for (src, dst), entry in list(self.flows.items()):
            if src in self.blocked:
                continue
            sh, dh = self.hosts.get(src), self.hosts.get(dst)
            if sh is None or dh is None:
                continue
            cur = entry['path']
            g = self._cost_graph(entry['rate_bps'], set(path_links(cur)))
            cur_cost = path_cost(g, cur)
            best, best_cost = dijkstra(g, sh.dpid, dh.dpid)
            if not best or best == cur:
                continue
            if best_cost + self.cfg.reroute_margin < cur_cost:
                self._reroute((src, dst), entry, best, reason, cur_cost, best_cost)

    def _reroute(self, pair, entry, new_path, reason, old_cost, new_cost):
        old_path = entry['path']
        dh = self.hosts[pair[1]]
        for key in entry['keys']:
            self._install_path(new_path, key, dh)
        for dpid in set(old_path) - set(new_path):
            dp = self.datapaths.get(dpid)
            if dp is None:
                continue
            for key in entry['keys']:
                self._del_flow(dp, PRIO_FORWARD, self._match(dp.ofproto_parser, key))
        entry['path'] = new_path
        self._event('reroute', host_name(pair[0]), host_name(pair[1]), reason=reason,
                    old=path_name(old_path), new=path_name(new_path),
                    old_cost=round(old_cost, 2) if old_cost != float('inf') else 'inf',
                    new_cost=round(new_cost, 2))

    # ==================================================================
    # Blocking
    # ==================================================================
    def _block(self, ip, pps, dt):
        for dp in self.datapaths.values():
            parser = dp.ofproto_parser
            match = parser.OFPMatch(eth_type=ether_types.ETH_TYPE_IP, ipv4_src=ip)
            self._add_flow(dp, PRIO_DROP, match, [], COOKIE_DROP)   # empty actions = drop

        # Links carrying the anomalous traffic: paths of this source's
        # high-rate pairs in the interval that triggered detection.
        floor = max(0.2 * pps, self.cfg.min_attack_pps / 2.0)
        links, victims = set(), []
        for (s, d), n in self.iv_pair_pkts.items():
            if s == ip and n / dt >= floor and (s, d) in self.flows:
                links.update(path_links(self.flows[(s, d)]['path']))
                victims.append(host_name(d))
        now = time.time()
        self.blocked[ip] = {'since': now, 'last_drop': now, 'links': links}
        for l in links:
            self.anomaly_until[l] = now + self.cfg.anomaly_hold
        self._event('block', host_name(ip), ','.join(victims), ip=ip, pps=round(pps, 1),
                    baseline=round(self.detector.baseline(ip), 2),
                    threshold=round(self.detector.threshold(ip), 2),
                    links=[link_name(l) for l in sorted(links)])
        self._reroute_all(reason='anomaly')

    def _unblock(self, ip, quiet_for):
        for dp in self.datapaths.values():
            parser = dp.ofproto_parser
            self._del_flow(dp, PRIO_DROP,
                           parser.OFPMatch(eth_type=ether_types.ETH_TYPE_IP, ipv4_src=ip))
        del self.blocked[ip]
        self.detector.reset_alarm(ip)
        self._event('unblock', host_name(ip), ip=ip, quiet_s=round(quiet_for, 1))
