#!/usr/bin/env python3
"""D2 automated experiment: game traffic under increasing congestion, WITHOUT SDN priority (baseline, mode=off)
versus WITH dynamic SDN priority (mode=dynamic).

Start Ryu first (ryu-manager controller.py), then:   sudo python3 experiment.py [--quick]
Output: results/summary.csv, results/rtt_<mode>_<load>M_<player>.csv, results/events.jsonl, results/port_rate.csv
Then plot with:   python3 plot_results.py"""
import argparse, json, os, shutil, time
from mininet.log import setLogLevel
import topo

HERE = os.path.dirname(os.path.abspath(__file__)); LOGS = os.path.join(HERE, 'logs'); RES = os.path.join(HERE, 'results')
DUR = 30          # seconds per run (players)
NOISE_START = 5   # congestion starts 5 s after the players
NOISE_DUR = 20    # congestion lasts 20 s, so the last 5 s show recovery


def jsonl(path):
    out = []
    if os.path.exists(path):
        for l in open(path):
            try: out.append(json.loads(l))
            except ValueError: pass
    return out


def wait_clear(timeout=60):
    """Wait until the controller reports no active congestion (last CONGESTION_* event is OFF or there is none),
    so every run starts from a clean state."""
    t_end = time.time() + timeout
    while time.time() < t_end:
        ev = [e for e in jsonl(os.path.join(LOGS, 'ctrl_events.jsonl')) if e.get('event') in ('CONGESTION_ON', 'CONGESTION_OFF')]
        if not ev or ev[-1]['event'] == 'CONGESTION_OFF': return
        time.sleep(1)
    print('WARNING: congestion flag did not clear within', timeout, 's')


def main():
    ap = argparse.ArgumentParser(); ap.add_argument('--quick', action='store_true', help='fewer load levels (faster)')
    a = ap.parse_args()
    loads = [0, 10, 20] if a.quick else [0, 5, 10, 20]       # Mbps of background UDP traffic (link = 10 Mbps)
    modes = ['off', 'dynamic']                               # baseline vs dynamic SDN priority
    os.makedirs(LOGS, exist_ok=True); shutil.rmtree(RES, ignore_errors=True); os.makedirs(RES)
    for f in ('client_stats.jsonl', 'server_stats.jsonl', 'ctrl_events.jsonl', 'port_rate.csv'):   # start from clean statistics
        try: os.remove(os.path.join(LOGS, f))
        except OSError: pass
    net, h, s1 = topo.build()
    print('*** waiting for controller / pingall'); time.sleep(3); net.pingAll()
    topo.start_server(h); time.sleep(2)
    summary = []; exp_log = []
    try:
        for load in loads:
            for mode in modes:
                tag = f'{mode}_{load}M'
                wait_clear(); time.sleep(2)
                with open(os.path.join(LOGS, 'qos_mode'), 'w') as f: f.write(mode)
                time.sleep(3)                                         # let the controller apply the mode
                print(f'*** run {tag}: mode={mode}, background load={load} Mbps')
                t0 = time.time()
                for host, who in ((h[2], 'alice'), (h[3], 'bob')):
                    host.cmd(f'python3 {topo.HERE}/game_client.py --name {tag}_{who} --server 10.0.0.1 --duration {DUR} > /dev/null 2>&1 &')
                time.sleep(NOISE_START)
                noise_t = time.time()
                if load > 0: h[4].cmd(f'python3 {topo.HERE}/noise.py --target 10.0.0.1 --mbps {load} --duration {NOISE_DUR} > /dev/null 2>&1 &')
                exp_log.append({'tag': tag, 'mode': mode, 'load': load, 'players_start': t0, 'noise_start': noise_t if load else None})
                time.sleep(DUR - NOISE_START + 4)                     # wait for clients to finish and send LEAVE
        # proof that queue 1 really carried game traffic (per-class byte counters on the bottleneck port)
        print(s1.cmd('tc -s class show dev s1-eth1'))
        with open(os.path.join(RES, 'tc_classes.txt'), 'w') as f: f.write(s1.cmd('tc -s class show dev s1-eth1'))
        with open(os.path.join(RES, 'flows.txt'), 'w') as f: f.write(s1.cmd('ovs-ofctl -O OpenFlow13 dump-flows s1'))
        with open(os.path.join(LOGS, 'qos_mode'), 'w') as f: f.write('dynamic')
    finally:
        net.stop()
    # ---- collect results
    srv = {r['name']: r for r in jsonl(os.path.join(LOGS, 'server_stats.jsonl'))}
    cli = {r['name']: r for r in jsonl(os.path.join(LOGS, 'client_stats.jsonl'))}
    ctrl = jsonl(os.path.join(LOGS, 'ctrl_events.jsonl'))
    rows = []
    for e in exp_log:
        for who in ('alice', 'bob'):
            n = f"{e['tag']}_{who}"
            if n not in cli or n not in srv: print('WARNING: missing stats for', n); continue
            c, s = cli[n], srv[n]
            loss = 100.0 * max(0, c['sent'] - s['recv']) / c['sent'] if c['sent'] else 0
            # congestion window statistics from the per-sample RTT file
            win = []
            p = os.path.join(LOGS, f'rtt_{n}.csv')
            if os.path.exists(p):
                shutil.copy(p, os.path.join(RES, f'rtt_{n}.csv'))
                for l in list(open(p))[1:]:
                    t, r = l.split(','); t = float(t)
                    if NOISE_START + 5 <= t <= NOISE_START + NOISE_DUR: win.append(float(r))
            win.sort()
            p95 = win[min(len(win) - 1, int(0.95 * len(win)))] if win else 0
            rows.append({'mode': e['mode'], 'load_mbps': e['load'], 'player': who, 'avg_rtt_ms': round(c['avg_rtt_ms'], 2),
                         'p95_rtt_ms': round(c['p95_rtt_ms'], 2), 'max_rtt_ms': round(c['max_rtt_ms'], 2),
                         'client_jitter_ms': round(c['jitter_ms'], 2), 'server_jitter_ms': round(s['jitter_ms'], 2),
                         'uplink_loss_pct': round(loss, 2), 'congested_window_avg_rtt_ms': round(sum(win) / len(win), 2) if win else 0,
                         'congested_window_p95_rtt_ms': round(p95, 2)})
    import csv
    if rows:
        with open(os.path.join(RES, 'summary.csv'), 'w', newline='') as f:
            w = csv.DictWriter(f, fieldnames=list(rows[0])); w.writeheader(); w.writerows(rows)
    with open(os.path.join(RES, 'events.jsonl'), 'w') as f:
        for r in exp_log: f.write(json.dumps({'experiment': r}) + '\n')
        for r in ctrl: f.write(json.dumps(r) + '\n')
    if os.path.exists(os.path.join(LOGS, 'port_rate.csv')): shutil.copy(os.path.join(LOGS, 'port_rate.csv'), RES)
    uid, gid = int(os.environ.get('SUDO_UID', 0)), int(os.environ.get('SUDO_GID', 0))
    if uid: os.system(f"chown -R {uid}:{gid} '{RES}' '{LOGS}'")        # so plot_results.py / make_report.py work without sudo
    print('\n*** DONE. Results in', RES)
    print(f"{'mode':8}{'load':>6}{'player':>8}{'avg_rtt':>9}{'p95':>8}{'jitter':>8}{'loss%':>7}")
    for r in rows: print(f"{r['mode']:8}{r['load_mbps']:>6}{r['player']:>8}{r['avg_rtt_ms']:>9}{r['p95_rtt_ms']:>8}{r['client_jitter_ms']:>8}{r['uplink_loss_pct']:>7}")


if __name__ == '__main__':
    setLogLevel('warning'); main()
