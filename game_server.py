#!/usr/bin/env python3
"""UDP game server: registers players, receives state updates (with sequence numbers),
detects loss/duplicates/reordering, measures one-way delay + jitter, broadcasts world state."""
import argparse, json, socket, time, threading, os, logging
HERE = os.path.dirname(os.path.abspath(__file__)); L = os.path.join(HERE, 'logs'); os.makedirs(L, exist_ok=True)
logging.basicConfig(level=logging.INFO, format='%(asctime)s %(message)s',
                    handlers=[logging.FileHandler(f'{L}/server.log'), logging.StreamHandler()])
log = logging.getLogger('server')
players = {}   # name -> dict(addr, pos, last_seq, recv, lost, dup, ooo, jitter, last_transit, delay_sum, last_ts, last_seen)
lock = threading.Lock()

def event(kind, **kw):   # read by the SDN controller (app -> network integration)
    with open(f'{L}/game_events.jsonl', 'a') as f: f.write(json.dumps({'time': time.time(), 'event': kind, **kw}) + '\n')

def handle(sock, data, addr):
    try: m = json.loads(data)
    except ValueError: return
    now = time.time(); name = m.get('name')
    if m.get('type') == 'JOIN':
        with lock:
            players[name] = dict(addr=addr, pos=[0, 0], last_seq=0, recv=0, lost=0, dup=0, ooo=0, jitter=0.0,
                                 last_transit=None, delay_sum=0.0, last_ts=0, last_seen=now)
        log.info('Player %s joined from %s', name, addr); event('JOIN', name=name, ip=addr[0])
        sock.sendto(json.dumps({'type': 'WELCOME', 'player_id': name, 'name': name, 'message': 'Successfully joined'}).encode(), addr)
    elif m.get('type') == 'STATE' and name in players:
        with lock:
            p = players[name]; seq = m['seq']; p['addr'] = addr; p['last_seen'] = now
            if seq == p['last_seq']: p['dup'] += 1; return
            if seq < p['last_seq']: p['ooo'] += 1; return
            if p['last_seq'] and seq > p['last_seq'] + 1: p['lost'] += seq - p['last_seq'] - 1
            p['last_seq'] = seq; p['recv'] += 1; p['pos'] = m['pos']; p['last_ts'] = m['ts']
            transit = now - m['ts']; p['delay_sum'] += transit
            if p['last_transit'] is not None: p['jitter'] += (abs(transit - p['last_transit']) - p['jitter']) / 16  # RFC3550
            p['last_transit'] = transit
    elif m.get('type') == 'LEAVE' and name in players:
        with lock:
            p = players.pop(name, None)
        if p:   # final per-player statistics, used by the experiment/plot scripts
            with open(f'{L}/server_stats.jsonl', 'a') as f:
                f.write(json.dumps({'name': name, 'recv': p['recv'], 'lost_gap': p['lost'], 'dup': p['dup'], 'ooo': p['ooo'],
                                    'avg_delay_ms': 1000 * p['delay_sum'] / p['recv'] if p['recv'] else 0,
                                    'jitter_ms': 1000 * p['jitter']}) + '\n')
        log.info('Player %s left', name); event('LEAVE', name=name, ip=addr[0])

def broadcaster(sock, hz):
    while True:
        time.sleep(1.0 / hz)
        with lock:
            world = {n: p['pos'] for n, p in players.items()}
            plist = {n: {'x': float(p['pos'][0]), 'y': float(p['pos'][1])} for n, p in players.items()}
            for n, p in players.items():
                pkt = {'type': 'WORLD', 'players': plist, 'world': world, 'echo_seq': p['last_seq'], 'echo_ts': p['last_ts'], 'server_ts': time.time()}
                try: sock.sendto(json.dumps(pkt).encode(), p['addr'])
                except OSError: pass

def reporter(period):
    while True:
        time.sleep(period)
        with lock:
            for n, p in players.items():
                tot = p['recv'] + p['lost']
                log.info('STATS %s recv=%d lost=%d (%.1f%%) dup=%d ooo=%d avg_delay=%.2fms jitter=%.2fms', n, p['recv'], p['lost'],
                         100.0 * p['lost'] / tot if tot else 0, p['dup'], p['ooo'],
                         1000 * p['delay_sum'] / p['recv'] if p['recv'] else 0, 1000 * p['jitter'])

if __name__ == '__main__':
    ap = argparse.ArgumentParser(); ap.add_argument('--bind', default='0.0.0.0'); ap.add_argument('--port', type=int, default=5000)
    ap.add_argument('--hz', type=float, default=20); a = ap.parse_args()
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM); s.bind((a.bind, a.port))
    threading.Thread(target=broadcaster, args=(s, a.hz), daemon=True).start()
    threading.Thread(target=reporter, args=(5,), daemon=True).start()
    log.info('Game server on %s:%d', a.bind, a.port)
    while True:
        d, addr = s.recvfrom(4096); handle(s, d, addr)
