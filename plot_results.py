#!/usr/bin/env python3
"""Make the D2 graphs from results/ (no root needed; needs matplotlib: sudo apt install python3-matplotlib).
Usage: python3 plot_results.py [results_dir]"""
import csv, json, os, sys
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt

RES = sys.argv[1] if len(sys.argv) > 1 else os.path.join(os.path.dirname(os.path.abspath(__file__)), 'results')
OUT = os.path.join(RES, 'graphs'); os.makedirs(OUT, exist_ok=True)
STYLE = {'off': dict(color='#d55e00', marker='o', ls='-', label='Baseline (no SDN priority)'),
         'dynamic': dict(color='#0072b2', marker='s', ls='--', label='Dynamic SDN priority')}
plt.rcParams.update({'font.size': 10, 'axes.grid': True, 'grid.alpha': 0.3, 'axes.spines.top': False, 'axes.spines.right': False})

rows = list(csv.DictReader(open(os.path.join(RES, 'summary.csv'))))
loads = sorted({int(r['load_mbps']) for r in rows})

def mean_by(mode, col):
    out = []
    for L in loads:
        v = [float(r[col]) for r in rows if r['mode'] == mode and int(r['load_mbps']) == L]
        out.append(sum(v) / len(v) if v else float('nan'))
    return out

def line_chart(col, ylabel, title, fname, log=False):
    fig, ax = plt.subplots(figsize=(6.4, 3.9))
    for m in ('off', 'dynamic'): ax.plot(loads, mean_by(m, col), **STYLE[m])
    ax.set_xlabel('Background (congestion) traffic [Mbps] on a 10 Mbps link'); ax.set_ylabel(ylabel); ax.set_title(title)
    ax.set_xticks(loads)
    if log: ax.set_yscale('log')
    ax.legend(frameon=False); fig.tight_layout(); fig.savefig(os.path.join(OUT, fname), dpi=180); plt.close(fig)

line_chart('congested_window_avg_rtt_ms', 'Average RTT during congestion [ms]', 'Game round-trip time vs congestion', 'g1_rtt_vs_load.png')
line_chart('congested_window_p95_rtt_ms', '95th-percentile RTT during congestion [ms]', 'Worst-case (p95) RTT vs congestion', 'g2_p95_rtt_vs_load.png')
line_chart('client_jitter_ms', 'Jitter [ms]', 'Jitter vs congestion', 'g3_jitter_vs_load.png')
line_chart('uplink_loss_pct', 'Game updates lost or stale [%]', 'Lost / stale updates vs congestion', 'g4_loss_vs_load.png')

# time series: RTT of one player at the highest load, both modes
hi = max(loads)
if hi > 0:
    fig, ax = plt.subplots(figsize=(7.2, 3.9))
    for m in ('off', 'dynamic'):
        p = os.path.join(RES, f'rtt_{m}_{hi}M_alice.csv')
        if not os.path.exists(p): continue
        t, r = [], []
        for l in list(open(p))[1:]:
            a, b = l.split(','); t.append(float(a)); r.append(float(b))
        ax.plot(t, r, color=STYLE[m]['color'], ls='-', lw=1.1, label=STYLE[m]['label'])
    ax.axvspan(5, 25, color='grey', alpha=0.12, label=f'{hi} Mbps congestion ({20} s)')
    ax.set_yscale('log'); ax.set_xlabel('Time since players joined [s]'); ax.set_ylabel('RTT [ms] (log scale)')
    ax.set_title(f'RTT over time under {hi} Mbps congestion'); ax.legend(frameon=False, loc='upper center', bbox_to_anchor=(0.5, -0.2), ncol=3); fig.tight_layout()
    fig.savefig(os.path.join(OUT, 'g5_rtt_timeseries.png'), dpi=180); plt.close(fig)

# controller view: bottleneck port rate with congestion detection
pr = os.path.join(RES, 'port_rate.csv')
if os.path.exists(pr):
    t, rate, cong = [], [], []
    for l in open(pr):
        p = l.strip().split(',')
        if len(p) >= 3: t.append(float(p[0])); rate.append(float(p[1])); cong.append(int(p[2]))
    if t:
        t0 = t[0]; t = [x - t0 for x in t]
        fig, ax = plt.subplots(figsize=(8, 3.6))
        ax.plot(t, rate, color='#0072b2', lw=1)
        ax.fill_between(t, 0, max(rate) * 1.05, where=[bool(c) for c in cong], color='#d55e00', alpha=0.2, label='controller: congestion detected')
        ax.axhline(8, color='grey', ls=':', lw=1); ax.text(t[-1], 8.2, 'ON threshold 8 Mbps', ha='right', fontsize=8)
        ax.set_xlabel('Time [s]'); ax.set_ylabel('Server-port load [Mbps]'); ax.set_title('Controller monitoring of the bottleneck port (OpenFlow port statistics)')
        ax.legend(frameon=False, loc='upper center', bbox_to_anchor=(0.5, -0.22), ncol=2); fig.tight_layout(); fig.savefig(os.path.join(OUT, 'g6_port_load_detection.png'), dpi=180); plt.close(fig)

# detection time table
ev = [json.loads(l) for l in open(os.path.join(RES, 'events.jsonl'))] if os.path.exists(os.path.join(RES, 'events.jsonl')) else []
exps = [e['experiment'] for e in ev if 'experiment' in e and e['experiment']['mode'] == 'dynamic' and e['experiment']['noise_start']]
ons = [e for e in ev if e.get('event') == 'CONGESTION_ON']
lines = ['load_Mbps,detection_delay_s']
for x in exps:
    after = [o['time'] - x['noise_start'] for o in ons if 0 <= o['time'] - x['noise_start'] < 15]
    # was congestion still flagged from the previous run when this run started?
    prev = [e for e in ev if e.get('event') in ('CONGESTION_ON', 'CONGESTION_OFF') and e['time'] < x['noise_start']]
    carried = bool(prev) and max(prev, key=lambda e: e['time'])['event'] == 'CONGESTION_ON'
    lines.append(f"{x['load']},{min(after):.2f}" if after else (f"{x['load']},already_active_from_previous_run" if carried else f"{x['load']},not_detected"))
open(os.path.join(RES, 'detection_time.csv'), 'w').write('\n'.join(lines) + '\n')
print('graphs written to', OUT); print('\n'.join(lines))
