"""Offline unit tests for the core logic (no Mininet / Ryu / root needed).
Run from the repository root:  python3 -m unittest discover -s tests -v"""
import importlib, json, os, sys, types, unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)


def _stub_ryu():
    """Minimal stand-ins so controller.py can be imported without Ryu installed."""
    if 'ryu' in sys.modules and hasattr(sys.modules['ryu'], '__file__'): return
    def mod(name, **attrs):
        m = types.ModuleType(name); m.__dict__.update(attrs); sys.modules[name] = m; return m
    class RyuApp: pass
    dec = lambda *a, **k: (lambda f: f)
    mod('ryu'); mod('ryu.base'); mod('ryu.base.app_manager', RyuApp=RyuApp)
    mod('ryu.controller'); mod('ryu.controller.ofp_event', EventOFPSwitchFeatures=1, EventOFPPacketIn=2,
                              EventOFPPortStatsReply=3, EventOFPFlowStatsReply=4)
    mod('ryu.controller.handler', CONFIG_DISPATCHER=1, MAIN_DISPATCHER=2, set_ev_cls=dec)
    mod('ryu.ofproto'); mod('ryu.ofproto.ofproto_v1_3', OFP_VERSION=4)
    mod('ryu.lib'); mod('ryu.lib.hub'); mod('ryu.lib.packet')
    mod('ryu.lib.packet.packet'); mod('ryu.lib.packet.ethernet'); mod('ryu.lib.packet.ipv4'); mod('ryu.lib.packet.arp')
    sys.modules['ryu.lib'].hub = sys.modules['ryu.lib.hub']
    lp = sys.modules['ryu.lib.packet']
    lp.packet, lp.ethernet, lp.ipv4, lp.arp = (sys.modules['ryu.lib.packet.' + n] for n in ('packet', 'ethernet', 'ipv4', 'arp'))
    sys.modules['ryu.ofproto'].ofproto_v1_3 = sys.modules['ryu.ofproto.ofproto_v1_3']


class FakeSock:
    def __init__(self): self.sent = []
    def sendto(self, data, addr): self.sent.append((json.loads(data), addr))


class CongestionDetectorTests(unittest.TestCase):
    def setUp(self):
        _stub_ryu(); self.c = importlib.import_module('controller'); self.d = self.c.CongestionDetector()

    def test_needs_two_consecutive_high_samples(self):
        self.assertIsNone(self.d.update(9.9)); self.assertEqual(self.d.update(9.9), 'ON'); self.assertTrue(self.d.congested)

    def test_single_spike_is_ignored(self):
        self.d.update(9.9); self.d.update(1.0); self.assertIsNone(self.d.update(9.9)); self.assertFalse(self.d.congested)

    def test_needs_three_low_samples_to_clear(self):
        self.d.update(9.9); self.d.update(9.9)
        self.assertIsNone(self.d.update(1)); self.assertIsNone(self.d.update(1)); self.assertEqual(self.d.update(1), 'OFF')
        self.assertFalse(self.d.congested)

    def test_hysteresis_band_keeps_state(self):          # 4 <= rate < 8 Mbps changes nothing
        self.d.update(9.9); self.d.update(9.9)
        for _ in range(10): self.assertIsNone(self.d.update(6.0))
        self.assertTrue(self.d.congested)


class ServerLogicTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls): cls.s = importlib.import_module('game_server')

    def setUp(self):
        self.s.players.clear(); self.sock = FakeSock(); self.addr = ('10.0.0.2', 4000)
        self.s.event = lambda *a, **k: None               # do not write the events file during tests
        self.send(dict(type='JOIN', name='alice'))

    def send(self, m): self.s.handle(self.sock, json.dumps(m).encode(), self.addr)
    def state(self, seq, ts=None):
        import time; self.send(dict(type='STATE', name='alice', seq=seq, ts=ts or time.time(), pos=[1, 2]))

    def test_join_gets_welcome(self):
        msg, addr = self.sock.sent[0]
        self.assertEqual(msg['type'], 'WELCOME'); self.assertEqual(msg['message'], 'Successfully joined'); self.assertEqual(addr, self.addr)

    def test_gap_counts_lost_packets(self):
        self.state(1); self.state(2); self.state(6)
        self.assertEqual(self.s.players['alice']['lost'], 3)

    def test_duplicate_detected(self):
        self.state(1); self.state(1); self.assertEqual(self.s.players['alice']['dup'], 1)

    def test_out_of_order_discarded(self):
        self.state(1); self.state(5); self.state(3)
        p = self.s.players['alice']; self.assertEqual(p['ooo'], 1); self.assertEqual(p['last_seq'], 5)

    def test_jitter_zero_for_constant_delay(self):
        import time
        for i in range(1, 30): self.state(i, ts=time.time() - 0.010)
        self.assertLess(self.s.players['alice']['jitter'], 0.002)


if __name__ == '__main__':
    unittest.main()
