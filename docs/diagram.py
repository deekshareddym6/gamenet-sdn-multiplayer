import matplotlib; matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.patches import FancyBboxPatch
fig, ax = plt.subplots(figsize=(8.4, 4.6)); ax.set_xlim(0, 10.5); ax.set_ylim(0, 5.6); ax.axis('off')
def box(x, y, w, h, t, fc):
    ax.add_patch(FancyBboxPatch((x, y), w, h, boxstyle='round,pad=0.05', fc=fc, ec='#1f3b73', lw=1.4))
    ax.text(x + w/2, y + h/2, t, ha='center', va='center', fontsize=8.5, color='#14233f')
box(0.1, 3.7, 2.2, 1.0, 'h2  Player alice\n10.0.0.2 (UDP client)', '#e3ecfa')
box(0.1, 2.2, 2.2, 1.0, 'h3  Player bob\n10.0.0.3 (UDP client)', '#e3ecfa')
box(0.1, 0.7, 2.2, 1.0, 'h4  Noise source\n10.0.0.4 (congestion)', '#f3e3fa')
box(3.9, 2.2, 2.4, 1.6, 'Open vSwitch s1\nOpenFlow 1.3\nport s1-eth1 = 10 Mbps\nqueue 0: best effort\nqueue 1: game (7 Mbps min)', '#fff3d6')
box(7.9, 2.2, 2.4, 1.6, 'h1  Game server\nUDP 5000 (game)\nUDP 5001 (noise sink)', '#e3f5e6')
box(3.9, 4.3, 2.4, 1.0, 'Ryu SDN controller\nport stats every 1 s\ncongestion detector', '#fde4e4')
def arr(a, b, t='', col='#1f3b73', ls='-'):
    ax.annotate('', xy=b, xytext=a, arrowprops=dict(arrowstyle='<->' if ls == '-' else '->', color=col, lw=1.3, ls=ls))
    if t: ax.text((a[0]+b[0])/2, (a[1]+b[1])/2 + 0.15, t, fontsize=7.5, ha='center', color='#333')
arr((2.35, 4.2), (3.85, 3.4)); arr((2.35, 2.7), (3.85, 3.0)); arr((2.35, 1.2), (3.85, 2.5), 'UDP flood', '#7a3b9c')
arr((6.35, 3.0), (7.85, 3.0), 'bottleneck')
arr((5.1, 3.85), (5.1, 4.25), 'OpenFlow', '#b03030')
ax.annotate('', xy=(6.35, 4.8), xytext=(9.1, 3.85), arrowprops=dict(arrowstyle='->', color='#b03030', lw=1.2, ls='--'))
ax.text(8.2, 4.7, 'JOIN / LEAVE events\n(logs/game_events.jsonl)', fontsize=7.5, color='#b03030', ha='center')
ax.text(5.2, 0.25, 'Figure A. D2 architecture: the controller turns on game-traffic priority only while the server port is congested',
        ha='center', fontsize=8, style='italic')
plt.savefig('architecture.png', dpi=200, bbox_inches='tight')
