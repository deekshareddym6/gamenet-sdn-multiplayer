#!/usr/bin/env python3
"""Ryu OpenFlow 1.3 controller for the Multiplayer Game Communication Network (D2).

* L2 learning switch.
* Monitors the load on the server-facing switch port (OpenFlow port statistics, every 1 s).
* Game traffic (UDP port 5000) can be given priority (QoS queue 1) in three modes, read from logs/qos_mode:
    off      baseline: no prioritisation at all (static network)
    static   priority rules for every joined player, always on (D1 behaviour)
    dynamic  priority rules are installed ONLY while congestion is detected and removed when it clears (default)
* Player JOIN/LEAVE events written by the game server (logs/game_events.jsonl) tell the controller who is playing.
* Events and measurements are written to logs/ctrl_events.jsonl and logs/port_rate.csv for the report.
Run: ryu-manager controller.py"""
import json, os, time
from ryu.base import app_manager
from ryu.controller import ofp_event
from ryu.controller.handler import CONFIG_DISPATCHER, MAIN_DISPATCHER, set_ev_cls
from ryu.ofproto import ofproto_v1_3
from ryu.lib.packet import packet, ethernet, ipv4, arp
from ryu.lib import hub

HERE = os.path.dirname(os.path.abspath(__file__)); LOGS = os.path.join(HERE, 'logs')
EVENTS = os.path.join(LOGS, 'game_events.jsonl'); MODE_FILE = os.path.join(LOGS, 'qos_mode')
CTRL_EVENTS = os.path.join(LOGS, 'ctrl_events.jsonl'); RATE_CSV = os.path.join(LOGS, 'port_rate.csv')
STATS = os.path.join(LOGS, 'flow_stats.log')
GAME_PORT = 5000; GAME_QUEUE = 1; SERVER_IP = '10.0.0.1'; QOS_PRIO = 10
ON_MBPS = 8.0; OFF_MBPS = 4.0; ON_SAMPLES = 2; OFF_SAMPLES = 3      # congestion thresholds (link capacity = 10 Mbps)
MODES = ('off', 'static', 'dynamic')


class CongestionDetector:
    """Hysteresis detector: ON after ON_SAMPLES consecutive samples >= ON_MBPS,
    OFF after OFF_SAMPLES consecutive samples < OFF_MBPS."""
    def __init__(self):
        self.congested = False; self.hi = 0; self.lo = 0

    def update(self, mbps):
        """Feed one rate sample; returns 'ON', 'OFF' or None when the state changes."""
        if mbps >= ON_MBPS: self.hi += 1; self.lo = 0
        elif mbps < OFF_MBPS: self.lo += 1; self.hi = 0
        else: self.hi = 0; self.lo = 0
        if not self.congested and self.hi >= ON_SAMPLES: self.congested = True; return 'ON'
        if self.congested and self.lo >= OFF_SAMPLES: self.congested = False; return 'OFF'
        return None


class GameController(app_manager.RyuApp):
    OFP_VERSIONS = [ofproto_v1_3.OFP_VERSION]

    def __init__(self, *a, **k):
        super().__init__(*a, **k)
        self.mac_to_port = {}; self.ip_to_port = {}; self.dps = {}
        self.players = {}                 # player name -> ip (from JOIN/LEAVE events)
        self.installed = set()            # player IPs that currently have priority rules
        self.mode = 'dynamic'; self.detector = CongestionDetector()
        self.event_pos = 0; self.last_tx = None
        os.makedirs(LOGS, exist_ok=True)
        hub.spawn(self._poll_loop); hub.spawn(self._ctl_loop); hub.spawn(self._stats_loop)

    # ------------------------------------------------------------ logging helpers
    def log_event(self, kind, **kw):
        with open(CTRL_EVENTS, 'a') as f: f.write(json.dumps({'time': time.time(), 'event': kind, **kw}) + '\n')
        self.logger.warning('%s %s', kind, kw if kw else '')

    # ------------------------------------------------------------ basic switching
    @set_ev_cls(ofp_event.EventOFPSwitchFeatures, CONFIG_DISPATCHER)
    def features(self, ev):
        dp = ev.msg.datapath; p = dp.ofproto_parser; o = dp.ofproto; self.dps[dp.id] = dp
        self.add_flow(dp, 0, p.OFPMatch(), [p.OFPActionOutput(o.OFPP_CONTROLLER, o.OFPCML_NO_BUFFER)])
        self.logger.info('Switch %s connected', dp.id)

    def add_flow(self, dp, prio, match, actions, idle=0):
        p = dp.ofproto_parser; o = dp.ofproto
        inst = [p.OFPInstructionActions(o.OFPIT_APPLY_ACTIONS, actions)] if actions else []
        dp.send_msg(p.OFPFlowMod(datapath=dp, priority=prio, match=match, instructions=inst, idle_timeout=idle))

    @set_ev_cls(ofp_event.EventOFPPacketIn, MAIN_DISPATCHER)
    def packet_in(self, ev):
        msg = ev.msg; dp = msg.datapath; o = dp.ofproto; p = dp.ofproto_parser; in_port = msg.match['in_port']
        pkt = packet.Packet(msg.data); eth = pkt.get_protocol(ethernet.ethernet)
        if eth.ethertype == 0x88cc: return
        self.mac_to_port.setdefault(dp.id, {})[eth.src] = in_port
        ip = pkt.get_protocol(ipv4.ipv4); ar = pkt.get_protocol(arp.arp)
        if ip: self.ip_to_port[ip.src] = in_port
        if ar: self.ip_to_port[ar.src_ip] = in_port
        out = self.mac_to_port[dp.id].get(eth.dst, o.OFPP_FLOOD); actions = [p.OFPActionOutput(out)]
        if out != o.OFPP_FLOOD:
            self.add_flow(dp, 1, p.OFPMatch(in_port=in_port, eth_dst=eth.dst, eth_src=eth.src), actions, idle=30)
        data = msg.data if msg.buffer_id == o.OFP_NO_BUFFER else None
        dp.send_msg(p.OFPPacketOut(datapath=dp, buffer_id=msg.buffer_id, in_port=in_port, actions=actions, data=data))

    # ------------------------------------------------------------ congestion monitoring (port statistics)
    def _poll_loop(self):
        while True:
            hub.sleep(1)
            port = self.ip_to_port.get(SERVER_IP)
            if port is None: continue
            for dp in list(self.dps.values()):
                dp.send_msg(dp.ofproto_parser.OFPPortStatsRequest(dp, 0, port))

    @set_ev_cls(ofp_event.EventOFPPortStatsReply, MAIN_DISPATCHER)
    def port_stats(self, ev):
        port = self.ip_to_port.get(SERVER_IP); now = time.time()
        for st in ev.msg.body:
            if st.port_no != port: continue
            if self.last_tx is not None:
                dt = now - self.last_tx[0]
                if dt > 0.2:
                    mbps = (st.tx_bytes - self.last_tx[1]) * 8 / dt / 1e6
                    change = self.detector.update(mbps)
                    with open(RATE_CSV, 'a') as f: f.write(f'{now:.3f},{mbps:.3f},{int(self.detector.congested)},{self.mode}\n')
                    if change == 'ON': self.log_event('CONGESTION_ON', mbps=round(mbps, 2))
                    elif change == 'OFF': self.log_event('CONGESTION_OFF', mbps=round(mbps, 2))
                    if change: self._sync()
                    self.last_tx = (now, st.tx_bytes)
            else:
                self.last_tx = (now, st.tx_bytes)

    # ------------------------------------------------------------ socket app -> SDN integration + policy
    def _ctl_loop(self):
        while True:
            hub.sleep(1)
            self._read_mode(); self._read_events(); self._sync()

    def _read_mode(self):
        try: m = open(MODE_FILE).read().strip().lower()
        except OSError: return
        if m in MODES and m != self.mode:
            old, self.mode = self.mode, m; self.log_event('MODE_CHANGE', old=old, new=m)

    def _read_events(self):
        if not os.path.exists(EVENTS): return
        if os.path.getsize(EVENTS) < self.event_pos: self.event_pos = 0      # file was cleared
        with open(EVENTS) as f: f.seek(self.event_pos); lines = f.readlines(); self.event_pos = f.tell()
        for l in lines:
            try: e = json.loads(l)
            except ValueError: continue
            if e['event'] == 'JOIN': self.players[e['name']] = e['ip']; self.log_event('PLAYER_JOIN', name=e['name'], ip=e['ip'])
            elif e['event'] == 'LEAVE': self.players.pop(e['name'], None); self.log_event('PLAYER_LEAVE', name=e['name'], ip=e['ip'])

    def _sync(self):
        """Make the installed priority rules match the policy for the current mode."""
        want = set(self.players.values()) if (self.mode == 'static' or (self.mode == 'dynamic' and self.detector.congested)) else set()
        for ip in want - self.installed:
            if self._qos(ip, True): self.installed.add(ip); self.log_event('QOS_INSTALLED', ip=ip, mode=self.mode, queue=GAME_QUEUE)
        for ip in self.installed - want:
            self._qos(ip, False); self.installed.discard(ip); self.log_event('QOS_REMOVED', ip=ip, mode=self.mode)

    def _qos(self, ip, install):
        ok = False
        for dp in self.dps.values():
            p = dp.ofproto_parser; o = dp.ofproto
            srv_port, pl_port = self.ip_to_port.get(SERVER_IP), self.ip_to_port.get(ip)
            if srv_port is None or pl_port is None: continue
            rules = [(p.OFPMatch(eth_type=0x0800, ip_proto=17, ipv4_src=ip, udp_dst=GAME_PORT), srv_port),     # player -> server
                     (p.OFPMatch(eth_type=0x0800, ip_proto=17, ipv4_dst=ip, udp_src=GAME_PORT), pl_port)]      # server -> player
            for m, port in rules:
                if install: self.add_flow(dp, QOS_PRIO, m, [p.OFPActionSetQueue(GAME_QUEUE), p.OFPActionOutput(port)])
                else: dp.send_msg(p.OFPFlowMod(datapath=dp, command=o.OFPFC_DELETE_STRICT, out_port=o.OFPP_ANY,
                                               out_group=o.OFPG_ANY, priority=QOS_PRIO, match=m))
            ok = True
        return ok

    # ------------------------------------------------------------ flow statistics log (kept from D1)
    def _stats_loop(self):
        while True:
            for dp in list(self.dps.values()): dp.send_msg(dp.ofproto_parser.OFPFlowStatsRequest(dp))
            hub.sleep(5)

    @set_ev_cls(ofp_event.EventOFPFlowStatsReply, MAIN_DISPATCHER)
    def flow_stats_reply(self, ev):
        with open(STATS, 'a') as f:
            for s in ev.msg.body:
                f.write(f'{time.strftime("%H:%M:%S")} prio={s.priority} match={dict(s.match.items())} pkts={s.packet_count} bytes={s.byte_count}\n')
