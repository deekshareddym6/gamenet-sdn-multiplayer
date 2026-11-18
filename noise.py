#!/usr/bin/env python3
"""Background UDP traffic generator used to create controlled congestion (replaces iperf, no install needed).
Sender:  python3 noise.py --target 10.0.0.1 --port 5001 --mbps 20 --duration 20
Sink:    python3 noise.py --sink --port 5001"""
import argparse, socket, time

def sender(target, port, mbps, duration, size=1200):
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM); payload = b'x' * size
    s.setsockopt(socket.SOL_SOCKET, socket.SO_SNDBUF, 1 << 20)
    bytes_per_sec = mbps * 1e6 / 8; start = time.time(); sent_bytes = 0; end = start + duration
    while True:
        now = time.time()
        if now >= end: break
        allowed = (now - start) * bytes_per_sec          # token-style pacing: send whatever is "owed"
        while sent_bytes < allowed:
            try: s.sendto(payload, (target, port))
            except OSError: pass
            sent_bytes += size
        time.sleep(0.001)
    print(f'noise sent {sent_bytes * 8 / 1e6 / duration:.2f} Mbps average for {duration}s')

def sink(port):
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM); s.setsockopt(socket.SOL_SOCKET, socket.SO_RCVBUF, 1 << 22)
    s.bind(('0.0.0.0', port))
    while True: s.recvfrom(4096)

if __name__ == '__main__':
    ap = argparse.ArgumentParser(); ap.add_argument('--sink', action='store_true'); ap.add_argument('--target', default='10.0.0.1')
    ap.add_argument('--port', type=int, default=5001); ap.add_argument('--mbps', type=float, default=10); ap.add_argument('--duration', type=float, default=20)
    a = ap.parse_args()
    sink(a.port) if a.sink else sender(a.target, a.port, a.mbps, a.duration)
