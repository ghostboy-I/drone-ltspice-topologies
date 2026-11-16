import sys, os
import numpy as np, matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
here = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(here, '..', 'tools'))
from ltraw import read_raw

d = read_raw(os.path.join(here, 'HalfBridge_MotorDrive.raw'))
t = d['time']; ms = t * 1e3
vgh = d['V(n002)'] - d['V(sw)']; vgl = d['V(n005)']
C1, C2, INK, INK2, SURF = '#2a78d6', '#eb6834', '#0b0b0b', '#52514e', '#fcfcfb'
plt.rcParams.update({'font.size': 9, 'axes.edgecolor': INK2, 'axes.labelcolor': INK2,
    'xtick.color': INK2, 'ytick.color': INK2, 'axes.spines.top': False, 'axes.spines.right': False,
    'axes.grid': True, 'grid.color': '#e4e3df', 'grid.linewidth': 0.6, 'lines.linewidth': 1.4,
    'figure.facecolor': SURF, 'axes.facecolor': SURF})
fig, ax = plt.subplots(3, 2, figsize=(12, 10.5))
fig.suptitle('01 Half-Bridge Motor Drive - 4S LiPo, 24 kHz PWM, 50 % throttle, 2300KV motor + 5" prop',
             color=INK, fontsize=11, x=0.01, ha='left')

def style(a, title, ylabel, xlabel):
    a.set_title(title, loc='left', color=INK, fontsize=10); a.set_ylabel(ylabel); a.set_xlabel(xlabel)

# A: speed
a = ax[0, 0]; a.plot(ms, d['V(rpm)'], color=C1)
style(a, 'A. Motor speed: spin-up after the 30 ms throttle ramp', 'RPM', 'time (ms)')
a.annotate(f"{d['V(rpm)'][-1]:,.0f} RPM", (ms[-1], d['V(rpm)'][-1]), xytext=(-70, -22),
           textcoords='offset points', color=INK)
# B: motor current overview
a = ax[0, 1]; a.plot(ms, d['I(Lm)'], color=C1, linewidth=0.6)
k = np.argmax(d['I(Lm)'])
style(a, 'B. Motor current: inrush while the motor has no back-EMF', 'I motor (A)', 'time (ms)')
a.annotate(f'peak {d["I(Lm)"][k]:.0f} A', (ms[k], d['I(Lm)'][k]), xytext=(12, -4), textcoords='offset points', color=INK)

# steady-state window: 3 PWM periods
t_end = t[-1]; ts = t_end - 3 / 24e3 - 2e-6
w = (t > ts) & (t < ts + 3 / 24e3)
us = (t[w] - t[w][0]) * 1e6
a = ax[1, 0]; a.plot(us, d['V(sw)'][w], color=C1)
style(a, 'C. Switch node V(sw): PWM at 50 % duty', 'V(sw) (V)', 'time (µs)')
a = ax[1, 1]
a.plot(us, d['I(Lm)'][w], color=C1, label='Motor current I(Lm)')
a.plot(us, d['I(Lwire)'][w], color=C2, label='Battery current I(Lwire)')
style(a, 'D. Motor ripple current; the DC-link caps absorb most of it', 'current (A)', 'time (µs)')
a.legend(frameon=False, loc='upper right')

# dead-time zoom: high-side turn-off edge
idx = np.where((t > t_end - 1e-3) & (vgh < 5))[0][0]  # 50 % point of turn-off
t0 = t[idx]; z = (t > t0 - 150e-9) & (t < t0 + 350e-9)
ns = (t[z] - t0) * 1e9
a = ax[2, 0]
a.plot(ns, vgh[z], color=C1, label='High-side gate drive')
a.plot(ns, vgl[z], color=C2, label='Low-side gate drive')
t_on = t[np.where((t > t0) & (vgl > 5))[0][0]]
dead_ns = (t_on - t0) * 1e9
a.axvspan(0, dead_ns, color='#e4e3df', zorder=0)
a.text(dead_ns / 2, 5, f'{dead_ns:.0f} ns\ndead time', ha='center', color=INK2)
style(a, 'E. Dead time: both FETs commanded OFF', 'gate drive (V)', 'time from high-side gate 50 % (ns)')
a.legend(frameon=False, loc='center right')
a = ax[2, 1]; a.plot(ns, d['V(sw)'][z], color=C1)
a.axvspan(0, dead_ns, color='#e4e3df', zorder=0)
vmin = d['V(sw)'][z].min()
a.annotate(f'body diode conducts: {vmin:.2f} V', (ns[np.argmin(d["V(sw)"][z])], vmin), xytext=(20, 30),
           textcoords='offset points', color=INK, arrowprops=dict(arrowstyle='-', color=INK2))
style(a, 'F. Switch node in the dead time: falls below 0 V', 'V(sw) (V)', 'time from high-side gate 50 % (ns)')
fig.tight_layout(rect=(0, 0, 1, 0.97))
out = os.path.join(here, 'HalfBridge_MotorDrive_results.png')
fig.savefig(out, dpi=130); print(out)
