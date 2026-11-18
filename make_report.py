#!/usr/bin/env python3
"""Builds D2_Report.docx from the REAL experiment results (results/summary.csv, graphs, detection_time.csv).
Usage:  python3 make_report.py          (needs: sudo apt install python3-docx -y)
Then open D2_Report.docx in LibreOffice Writer, add screenshots / edit the yellow parts, File > Export as PDF."""
import csv, os, sys
from docx import Document
from docx.shared import Pt, RGBColor, Inches
from docx.enum.text import WD_ALIGN_PARAGRAPH, WD_COLOR_INDEX
from docx.enum.table import WD_TABLE_ALIGNMENT
from docx.oxml.ns import qn
from docx.oxml import OxmlElement

HERE = os.path.dirname(os.path.abspath(__file__))
RES = sys.argv[1] if len(sys.argv) > 1 else os.path.join(HERE, 'results')
OUTFILE = os.path.join(HERE, 'D2_Report.docx')
BLUE = RGBColor(0x1F, 0x3B, 0x73); LBLUE = RGBColor(0x3A, 0x6B, 0xC4)
TEAM = [('PES2UG25CS143', 'D ARPITHA'), ('PES2UG25CS152', 'DEEKSHA M REDDY'), ('PES2UG25CS180', 'G M HRITHICK')]

rows = list(csv.DictReader(open(os.path.join(RES, 'summary.csv'))))
loads = sorted({int(r['load_mbps']) for r in rows})
def avg(mode, load, col):
    v = [float(r[col]) for r in rows if r['mode'] == mode and int(r['load_mbps']) == load]
    return sum(v) / len(v) if v else float('nan')

d = Document(); sec = d.sections[0]; sec.left_margin = sec.right_margin = Inches(1); sec.top_margin = sec.bottom_margin = Inches(0.9)
st = d.styles['Normal']; st.font.name = 'Calibri'; st.font.size = Pt(10.5); st.element.rPr.rFonts.set(qn('w:eastAsia'), 'Calibri')

def shade(cell, hexcol):
    tcPr = cell._tc.get_or_add_tcPr(); s = OxmlElement('w:shd'); s.set(qn('w:val'), 'clear'); s.set(qn('w:color'), 'auto'); s.set(qn('w:fill'), hexcol); tcPr.append(s)
def para(text='', size=None, bold=False, color=None, align=None, after=6, italic=False, hl=False):
    p = d.add_paragraph(); r = p.add_run(text); r.bold = bold; r.italic = italic
    if size: r.font.size = Pt(size)
    if color: r.font.color.rgb = color
    if hl: r.font.highlight_color = WD_COLOR_INDEX.YELLOW
    if align is not None: p.alignment = align
    p.paragraph_format.space_after = Pt(after); return p
def h1(t): p = para(t, 16, True, BLUE, after=5); p.paragraph_format.space_before = Pt(12); p.paragraph_format.keep_with_next = True
def h2(t): p = para(t, 12, True, LBLUE, after=3); p.paragraph_format.space_before = Pt(6); p.paragraph_format.keep_with_next = True
def bullet(t): p = d.add_paragraph(style='List Bullet'); p.add_run(t); p.paragraph_format.space_after = Pt(2)
def table(data, widths, fs=9.5):
    t = d.add_table(rows=len(data), cols=len(data[0])); t.style = 'Table Grid'; t.alignment = WD_TABLE_ALIGNMENT.CENTER; t.autofit = False
    for j, w in enumerate(widths): t.columns[j].width = Inches(w)
    for i, row in enumerate(data):
        for j, val in enumerate(row):
            c = t.cell(i, j); c.width = Inches(widths[j]); c.text = ''; r = c.paragraphs[0].add_run(str(val)); r.font.size = Pt(fs)
            if i == 0: r.bold = True; r.font.color.rgb = RGBColor(255, 255, 255); shade(c, '1F3B73')
            elif i % 2 == 0: shade(c, 'EEF3FB')
    d.add_paragraph().paragraph_format.space_after = Pt(2)
def picture(path, caption, width=6.0):
    if os.path.exists(path):
        d.add_picture(path, width=Inches(width)); d.paragraphs[-1].alignment = WD_ALIGN_PARAGRAPH.CENTER
        para(caption, 9, italic=True, align=WD_ALIGN_PARAGRAPH.CENTER, after=8)
    else: para(f'[missing image: {os.path.basename(path)}]', hl=True)
def shot(title, show, cmd):
    para(title, 11, True, BLUE, after=2).paragraph_format.keep_with_next = True; para(show, 9.5, italic=True, after=3).paragraph_format.keep_with_next = True
    t = d.add_table(rows=1, cols=1); t.style = 'Table Grid'; t.alignment = WD_TABLE_ALIGNMENT.CENTER
    c = t.cell(0, 0); c.width = Inches(6.3); shade(c, 'F7F7F7'); c.text = ''
    q = c.paragraphs[0]; q.alignment = WD_ALIGN_PARAGRAPH.CENTER
    r = q.add_run('\n\n[ PASTE YOUR SCREENSHOT HERE — delete this text ]\n'); r.bold = True; r.font.size = Pt(10); r.font.color.rgb = RGBColor(0xB0, 0x30, 0x30)
    q2 = c.add_paragraph(); q2.alignment = WD_ALIGN_PARAGRAPH.CENTER; r2 = q2.add_run('Command(s): ' + cmd + '\n\n\n'); r2.font.size = Pt(8.5); r2.font.name = 'Consolas'
    d.add_paragraph().paragraph_format.space_after = Pt(4)

hp = sec.header.paragraphs[0]; hp.alignment = WD_ALIGN_PARAGRAPH.RIGHT; hp.add_run('COMPUTER NETWORKS MINI-PROJECT | DELIVERABLE 2').font.size = Pt(8)
fp = sec.footer.paragraphs[0]; fp.alignment = WD_ALIGN_PARAGRAPH.CENTER; fp.add_run('Multiplayer Game Communication Network — D2').font.size = Pt(8)

para('MULTIPLAYER GAME COMMUNICATION NETWORK', 24, True, BLUE, WD_ALIGN_PARAGRAPH.CENTER, after=4).paragraph_format.space_before = Pt(24)
para('Computer Networks Mini-Project — Deliverable 2', 14, False, LBLUE, WD_ALIGN_PARAGRAPH.CENTER, after=4)
para('SDN–Socket Programming', 10.5, False, None, WD_ALIGN_PARAGRAPH.CENTER, after=12)
para('TEAM 4', 10.5, True, after=3)
for srn, nm in TEAM: para(f'{srn}   {nm}', 10.5, True, after=2)

h1('1. Problem Statement and Objectives')
para('Online multiplayer games continuously exchange small, time-critical state updates between players and a server. Such traffic is '
     'sensitive to delay, jitter and loss, and suffers when it shares a bottleneck link with bulk traffic. This project builds a '
     'multiplayer game communication system on UDP sockets and uses a Software-Defined Network (Mininet, Open vSwitch and a Ryu '
     'OpenFlow controller) to protect game traffic: the controller monitors the bottleneck link and, when congestion appears, '
     'dynamically prioritises the game traffic.')
for b in ['UDP game-state updates between players and a server, with player registration and sequence numbers (D1).',
          'Detection of lost, duplicate and out-of-order updates; measurement of latency (RTT) and jitter.',
          'Dynamic SDN behaviour: congestion monitoring and on-demand traffic prioritisation (D2).',
          'Evaluation under congestion against a baseline without prioritisation (D2).']: bullet(b)

h1('2. System Architecture')
picture(os.path.join(HERE, 'docs', 'architecture.png'), 'Figure 1. System architecture', 6.2)
table([['Component', 'Role'],
       ['h1 game server (UDP 5000)', 'Registers players; receives STATE updates; detects loss/duplicates/reordering with sequence numbers; measures one-way delay and jitter; broadcasts WORLD state at 20 Hz; reports JOIN/LEAVE events to the controller.'],
       ['h2, h3 players', 'UDP clients: send position + sequence number + timestamp at 20 Hz; receive WORLD state; measure RTT and jitter; write per-sample RTT files.'],
       ['h4 noise source', 'Sends controlled UDP background traffic (5/10/20 Mbps) to h1 to create congestion on the 10 Mbps server port.'],
       ['Switch s1 (Open vSwitch)', 'OpenFlow 1.3; server-facing port shaped to 10 Mbps with two HTB queues: queue 0 best effort, queue 1 game traffic (min 7 Mbps).'],
       ['Ryu controller', 'L2 learning; polls port statistics of the server port every second; detects congestion; installs/removes priority rules (UDP port 5000 to queue 1).']],
      [1.7, 4.6])

h1('3. Implementation')
h2('3.1 Application protocol (UDP)')
table([['Message', 'Direction', 'Fields'],
       ['JOIN / WELCOME', 'Player ↔ Server', 'name; JOIN is retried up to 10 times because UDP can lose it'],
       ['STATE', 'Player → Server', 'name, seq, ts, pos'],
       ['WORLD', 'Server → Player', 'all player positions, echo_seq, echo_ts, server_ts'],
       ['LEAVE', 'Player → Server', 'name']], [1.4, 1.5, 3.4])
para('Packet-loss handling: every STATE carries a sequence number. The server counts gaps as lost updates, ignores duplicates and '
     'out-of-order (stale) updates, and always uses the newest position, so a lost update is simply superseded by the next one. '
     'Registration is made reliable by retrying JOIN.')
h2('3.2 Dynamic SDN: congestion-triggered prioritisation')
para('The controller sends an OpenFlow port-statistics request for the server-facing port every second and computes the load from the '
     'transmitted-byte counter. A hysteresis detector avoids flapping: congestion is declared after 2 consecutive samples at or above '
     '8 Mbps and cleared after 3 consecutive samples below 4 Mbps (link capacity 10 Mbps). While congestion is declared, the controller '
     'installs, for every active player, two priority-10 flow rules (player→server with udp_dst=5000 and server→player with udp_src=5000) '
     'whose action is set_queue:1 and output. When congestion clears, the rules are removed. The active players are learned from JOIN/LEAVE '
     'events written by the game server, which is the socket-to-SDN integration.')
table([['Mode (logs/qos_mode)', 'Behaviour'],
       ['off', 'Baseline: no prioritisation (static network)'],
       ['static', 'Priority rules for every joined player at all times (D1 behaviour)'],
       ['dynamic', 'Priority rules only while congestion is detected (D2 proposal)']], [1.8, 4.5])

h1('4. Test Scenarios and Methodology')
para('Challenging scenario: congestion. Two players (alice on h2, bob on h3) play for 30 s. After 5 s, h4 sends UDP background traffic for 20 s '
     f'at {", ".join(str(l) for l in loads)} Mbps towards the server over the 10 Mbps bottleneck. Each load is run twice: baseline (mode off) and '
     'proposed (mode dynamic). The congested window (t = 10–25 s) is used for the RTT statistics. Metrics: RTT (client), jitter (client and server), '
     'uplink packet loss (updates sent minus updates received by the server) and controller detection delay.')

h1('5. Results')
h2('5.1 Summary table (mean of the two players)')
data = [['Load (Mbps)', 'Mode', 'Avg RTT in congestion (ms)', 'p95 RTT (ms)', 'Jitter (ms)', 'Lost or stale (%)']]
for L in loads:
    for m, lab in (('off', 'Baseline'), ('dynamic', 'Dynamic SDN')):
        data.append([L, lab, f"{avg(m, L, 'congested_window_avg_rtt_ms'):.1f}", f"{avg(m, L, 'congested_window_p95_rtt_ms'):.1f}",
                     f"{avg(m, L, 'client_jitter_ms'):.2f}", f"{avg(m, L, 'uplink_loss_pct'):.2f}"])
table(data, [0.9, 1.1, 1.5, 1.0, 0.9, 0.8], 9)
so = os.path.join(RES, 'server_stats.jsonl')
if os.path.exists(so):
    import json
    st_rows = [json.loads(l) for l in open(so) if l.strip()]
    st_rows = [r for r in st_rows if r['name'].split('_')[0] in ('off', 'dynamic')]
    if st_rows:
        h2('Server-side packet accounting')
        para('"Lost or stale" = updates sent by a player that were not accepted by the server. This includes updates that arrived late and out of order '
             '(older than one already received) and were discarded as stale; the table shows the server counters per run.', 9.5)
        table([['Run', 'Accepted', 'Gaps (lost)', 'Out-of-order (stale)', 'Duplicates']] +
              [[r['name'], r['recv'], r['lost_gap'], r['ooo'], r['dup']] for r in sorted(st_rows, key=lambda r: r['name'])], [2.3, 1.0, 1.0, 1.3, 0.8], 8.5)
for fn, cap in [('g1_rtt_vs_load.png', 'Figure 2. Average RTT during congestion versus background load'),
                ('g2_p95_rtt_vs_load.png', 'Figure 3. 95th-percentile RTT versus background load'),
                ('g3_jitter_vs_load.png', 'Figure 4. Jitter versus background load'),
                ('g4_loss_vs_load.png', 'Figure 5. Packet loss versus background load'),
                ('g5_rtt_timeseries.png', 'Figure 6. RTT over time at the highest load: baseline versus dynamic SDN'),
                ('g6_port_load_detection.png', 'Figure 7. Controller view: server-port load and congestion detection')]:
    picture(os.path.join(RES, 'graphs', fn), cap, 5.6)
dt = os.path.join(RES, 'detection_time.csv')
if os.path.exists(dt):
    h2('5.2 Controller reaction time'); drows = [r.split(',') for r in open(dt).read().split() if r]
    table([['Background load (Mbps)', 'Congestion detection delay (s)']] + [[a, b] for a, b in drows[1:]], [2.5, 3.0])
for fn, title in (('tc_classes.txt', 'Queue counters (tc -s class show dev s1-eth1)'), ('flows.txt', 'Switch flow table at the end of the experiment')):
    p = os.path.join(RES, fn)
    if os.path.exists(p):
        h2(title); q = para(open(p).read()[:1800], 7.5, after=4); q.runs[0].font.name = 'Consolas'

h1('6. Analysis')
hi = max(loads)
if hi > 0:
    b, p_ = avg('off', hi, 'congested_window_avg_rtt_ms'), avg('dynamic', hi, 'congested_window_avg_rtt_ms')
    bl, pl = avg('off', hi, 'uplink_loss_pct'), avg('dynamic', hi, 'uplink_loss_pct')
    bj, pj = avg('off', hi, 'client_jitter_ms'), avg('dynamic', hi, 'client_jitter_ms')
    lo_b, lo_p = avg('off', loads[0], 'congested_window_avg_rtt_ms'), avg('dynamic', loads[0], 'congested_window_avg_rtt_ms')
    pct = lambda a, c: (100.0 * (a - c) / a) if a else 0.0
    bullet(f'Without congestion ({loads[0]} Mbps) both modes behave the same (average RTT {lo_b:.1f} ms vs {lo_p:.1f} ms), so the prioritisation adds no cost when it is not needed.')
    ch = pct(b, p_); chtxt = f'a reduction of {ch:.0f}%' if ch > 0 else f'an increase of {-ch:.0f}% (no improvement)'
    bullet(f'At {hi} Mbps the baseline average RTT during congestion is {b:.1f} ms, with dynamic SDN priority it is {p_:.1f} ms, {chtxt}.')
    bullet(f'Lost or stale updates at {hi} Mbps: {bl:.2f}% (baseline) versus {pl:.2f}% (dynamic). Jitter: {bj:.2f} ms versus {pj:.2f} ms.')
    if pl > bl: bullet('The baseline queue is deep, so game packets are delayed (large RTT) rather than dropped. In dynamic mode a small share of updates is counted as stale: '
                       'packets still queued in the best-effort queue are overtaken by newer packets that use the priority queue, and the server discards them as out of order (see the server-side packet accounting).')
    bullet('The controller needs about two to three seconds to detect congestion (one-second polling and two consecutive samples), so a short transient remains before the priority rules take effect (Figure 6).')
    para('Note: statements above are generated from the measured data in results/summary.csv; if a number does not show an improvement, the report states it as measured.', 9, italic=True)

h1('7. Limitations and Future Work')
for b in ['The game server and the controller exchange JOIN/LEAVE events through a shared file, not through a direct network message.',
          'Detection is polling-based (1 s), so there is a short delay before prioritisation starts.',
          'One bottleneck link, two players and one type of background traffic; larger player counts and multiple switches are future work.',
          'RTT includes the server tick (50 ms) and is measured in an emulated network, which may differ from real hardware.']: bullet(b)

h1('8. Team Contributions')
para('Edit the table below so that it matches who actually did what.', 9.5, italic=True, hl=True)
table([['Member', 'Contribution'],
       [f'{TEAM[0][0]} {TEAM[0][1]}', 'UDP game application: game_server.py, game_client.py, noise.py (sockets, registration, sequence numbers, loss/jitter/RTT measurement)'],
       [f'{TEAM[1][0]} {TEAM[1][1]}', 'Network: Mininet topology, Open vSwitch QoS queues, experiment automation, testing'],
       [f'{TEAM[2][0]} {TEAM[2][1]}', 'SDN controller (Ryu): learning switch, congestion detection, dynamic priority rules; evaluation and graphs']], [2.4, 3.9])

h1('9. Evidence Screenshots')
shot('Figure 8. Topology and connectivity', 'pingall with 0% packet loss for h1–h4.', 'sudo python3 topo.py')
shot('Figure 9. Baseline under congestion', 'Client RTT rising while mode is off and 20 Mbps noise runs.', 'sh echo off > logs/qos_mode; h4 python3 noise.py --target 10.0.0.1 --mbps 20 --duration 20 &')
shot('Figure 10. Controller reaction', 'Ryu output: CONGESTION_ON, QOS_INSTALLED, then CONGESTION_OFF, QOS_REMOVED.', 'sh echo dynamic > logs/qos_mode')
shot('Figure 11. Flow rules and queues', 'priority=10 UDP rules with set_queue:1 and the queue counters.', 'dpctl dump-flows -O OpenFlow13   |   sh tc -s class show dev s1-eth1')

h1('10. How to Reproduce')
para('See README.md in the repository: start Ryu (ryu-manager controller.py), run sudo python3 experiment.py, then python3 plot_results.py and python3 make_report.py.')
h1('11. Conclusion')
para('The system demonstrates UDP game communication integrated with an SDN controller that reacts to network conditions. '
     'The experiments compare the proposed dynamic prioritisation with a baseline under several congestion levels using RTT, jitter and loss, '
     'with the measured results presented above.')
d.save(OUTFILE); print('wrote', OUTFILE)
