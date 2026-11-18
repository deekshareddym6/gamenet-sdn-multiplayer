#!/usr/bin/env python3
"""UDP game client (one player): sends position at --hz with sequence numbers + timestamp,
receives world state, measures RTT/jitter and packet loss of received updates."""
import argparse, json, socket, time, random, os, logging
HERE = os.path.dirname(os.path.abspath(__file__)); L = os.path.join(HERE, 'logs'); os.makedirs(L, exist_ok=True)

if __name__ == '__main__':
    ap = argparse.ArgumentParser(); ap.add_argument('--name'); ap.add_argument('--server', default='10.0.0.1'); ap.add_argument('-i', '--interactive', action='store_true')
    ap.add_argument('--port', type=int, default=5000); ap.add_argument('--hz', type=float, default=20)
    ap.add_argument('--duration', type=float, default=30); a = ap.parse_args()
    if a.interactive and not a.name: a.name = input('Enter player ID: ').strip()
    if not a.name: ap.error('--name is required (or use --interactive)')
    logging.basicConfig(level=logging.INFO, format='%(asctime)s %(message)s',
                        handlers=[logging.FileHandler(f'{L}/client_{a.name}.log'), logging.StreamHandler()])
    log = logging.getLogger(a.name)
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM); s.settimeout(0.01); srv = (a.server, a.port)
    # register (retry until WELCOME because UDP is unreliable)
    for _ in range(10):
        s.sendto(json.dumps({'type': 'JOIN', 'name': a.name}).encode(), srv)
        try:
            d, _ = s.recvfrom(4096)
            w = json.loads(d)
            if w.get('type') == 'WELCOME':
                log.info('registered')
                if a.interactive: print('Server:', {k: w[k] for k in ('type', 'player_id', 'message')})
                break
        except socket.timeout: time.sleep(0.5)
    else: log.error('registration failed'); raise SystemExit(1)
    if a.interactive:
        seq = 0
        while True:
            xs = input('Enter x position (or q to quit): ').strip()
            if xs.lower() == 'q': break
            ys = input('Enter y position: ').strip()
            try: x, y = float(xs), float(ys)
            except ValueError: print('Please enter valid numeric coordinates.'); continue
            seq += 1
            s.sendto(json.dumps({'type': 'STATE', 'name': a.name, 'seq': seq, 'ts': time.time(), 'pos': [x, y]}).encode(), srv)
            t0 = time.time(); got_world = False
            while time.time() - t0 < 2 and not got_world:
                try:
                    d, _ = s.recvfrom(4096); m = json.loads(d)
                    if m.get('type') == 'WORLD' and m.get('echo_seq', 0) >= seq:
                        print('World state:', {k: m[k] for k in ('type', 'players', 'echo_seq', 'echo_ts', 'server_ts')}); got_world = True
                except socket.timeout: pass
            if not got_world: print('No server response: request timed out.')
        s.sendto(json.dumps({'type': 'LEAVE', 'name': a.name}).encode(), srv); raise SystemExit(0)
    pos = [random.randint(0, 100), random.randint(0, 100)]; seq = 0; rtts = []; samples = []; last_rtt = None; jit = 0.0
    t_start = time.time(); t_end = t_start + a.duration; nxt = t_start; lastrep = t_start; got = 0
    while time.time() < t_end:
        now = time.time()
        if now >= nxt:
            seq += 1; pos = [pos[0] + random.randint(-2, 2), pos[1] + random.randint(-2, 2)]
            s.sendto(json.dumps({'type': 'STATE', 'name': a.name, 'seq': seq, 'ts': now, 'pos': pos}).encode(), srv); nxt += 1 / a.hz
        try:
            d, _ = s.recvfrom(4096); m = json.loads(d)
            if m.get('type') == 'WORLD':
                got += 1
                if m['echo_ts']:
                    rtt = time.time() - m['echo_ts']; rtts.append(rtt); samples.append((time.time() - t_start, rtt))
                    if last_rtt is not None: jit += (abs(rtt - last_rtt) - jit) / 16
                    last_rtt = rtt
        except socket.timeout: pass
        if now - lastrep >= 5 and rtts:
            w = [r for t, r in samples if t >= (now - t_start) - 5] or [0]      # RTT samples of the last 5 s only
            log.info('sent=%d world_updates=%d last5s_avg_rtt=%.2fms last5s_max_rtt=%.2fms | whole_run_avg=%.2fms jitter=%.2fms', seq, got,
                     1000 * sum(w) / len(w), 1000 * max(w), 1000 * sum(rtts) / len(rtts), 1000 * jit); lastrep = now
    s.sendto(json.dumps({'type': 'LEAVE', 'name': a.name}).encode(), srv)
    # per-sample RTT (for time-series graphs) and summary statistics (for the results table)
    with open(f'{L}/rtt_{a.name}.csv', 'w') as f:
        f.write('t_sec,rtt_ms\n')
        for t, r in samples: f.write(f'{t:.3f},{1000 * r:.3f}\n')
    srt = sorted(rtts)
    pct = lambda q: 1000 * srt[min(len(srt) - 1, int(q * len(srt)))] if srt else 0
    with open(f'{L}/client_stats.jsonl', 'a') as f:
        f.write(json.dumps({'name': a.name, 'sent': seq, 'world_updates': got, 'avg_rtt_ms': 1000 * sum(rtts) / max(1, len(rtts)),
                            'p50_rtt_ms': pct(0.5), 'p95_rtt_ms': pct(0.95), 'max_rtt_ms': 1000 * max(rtts) if rtts else 0,
                            'jitter_ms': 1000 * jit}) + '\n')
    log.info('FINAL sent=%d world_updates=%d avg_rtt=%.2fms jitter=%.2fms', seq, got, 1000 * sum(rtts) / max(1, len(rtts)), 1000 * jit)
