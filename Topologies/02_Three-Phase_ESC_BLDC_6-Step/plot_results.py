import sys, os, re
import numpy as np, matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
here = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(here, '..', 'tools'))
from ltraw import read_raw, split_steps

steps = split_steps(read_raw(os.path.join(here, 'ThreePhase_ESC_BLDC.raw')))
async_, sync = steps[0], steps[1]          # .step param Sync list 0 1
log = open(os.path.join(here, 'ThreePhase_ESC_BLDC.log'), 'rb').read().replace(b'\x00', b'').decode('utf-8', 'ignore')

from ltraw import read_meas
_m = read_meas(os.path.join(here, 'ThreePhase_ESC_BLDC.log'))
meas = lambda name: _m[name.lower()]   # per-step values from the stepped .meas table

C1, C2, C3, INK, INK2, SURF = '#2a78d6', '#eb6834', '#1baf7a', '#0b0b0b', '#52514e', '#fcfcfb'
plt.rcParams.update({'font.size': 9, 'axes.edgecolor': INK2, 'axes.labelcolor': INK2, 'xtick.color': INK2,
    'ytick.color': INK2, 'axes.spines.top': False, 'axes.spines.right': False, 'axes.grid': True,
    'grid.color': '#e4e3df', 'grid.linewidth': 0.6, 'lines.linewidth': 1.3, 'figure.facecolor': SURF, 'axes.facecolor': SURF})
fig, ax = plt.subplots(3, 2, figsize=(12, 10.5))
fig.suptitle('02 Three-Phase ESC + BLDC, 6-step - 4S LiPo, 48 kHz PWM, 50 % throttle, 2300KV 7-pole-pair motor + 5" prop',
             color=INK, fontsize=11, x=0.01, ha='left')
def style(a, title, yl, xl):
    a.set_title(title, loc='left', color=INK, fontsize=10); a.set_ylabel(yl); a.set_xlabel(xl)

# A: speed, both modes
a = ax[0, 0]
a.plot(async_['time'] * 1e3, async_['V(rpm)'], color=C2, label='Sync=0: high-side PWM, diode freewheel')
a.plot(sync['time'] * 1e3, sync['V(rpm)'], color=C1, label='Sync=1: complementary PWM')
style(a, 'A. Motor speed for the two PWM modes', 'RPM', 'time (ms)'); a.legend(frameon=False, loc='lower right')

# steady-state window: one electrical revolution (Sync=1)
d = sync; t = d['time']; Pp = 7
we = Pp * np.mean(d['V(omega)'][t > t[-1] - 5e-3])
Te_el = 2 * np.pi / we
w = (t > t[-1] - 1.25 * Te_el)
x = (t[w] - t[w][0]) * 1e6
the = d['V(the)'][w]
a = ax[0, 1]
for n, c in zip('abc', (C1, C2, C3)):
    a.plot(x, d['I(L%s)' % n][w], color=c, label='phase ' + n.upper(), linewidth=1.0)
style(a, 'B. Phase currents: 120-degree blocks, one phase floats', 'current (A)', 'time (µs)')
a.set_ylim(-13, 17); a.legend(frameon=False, loc='upper right', ncol=3)

a = ax[1, 0]
for n, c in zip('abc', (C1, C2, C3)):
    a.plot(x, d['V(x%s)' % n][w] - d['V(n)'][w], color=c, label='e' + n)
style(a, 'C. Trapezoidal back-EMF of each phase (to neutral)', 'back-EMF (V)', 'time (µs)')
a.set_ylim(-4, 5); a.legend(frameon=False, loc='upper right', ncol=3)

a = ax[1, 1]
a.plot(x, d['V(pa)'][w], color=C1, linewidth=0.6)
style(a, 'D. Phase-A terminal: PWM / low / floating (EMF visible)', 'V(pa) (V)', 'time (µs)')

a = ax[2, 0]
# average the torque over one PWM period to separate the commutation dips from the PWM ripple
tu = np.arange(t[w][0], t[w][-1], 0.1e-6); teu = np.interp(tu, t, d['V(te)'])
n = int(round(1 / 48e3 / 0.1e-6)); tavg = np.convolve(teu, np.ones(n) / n, mode='same')
core = slice(n, -n)
a.plot(x, d['V(te)'][w] * 1e3, color='#b7d3f6', linewidth=0.8, label='instantaneous (PWM ripple)')
a.plot((tu[core] - t[w][0]) * 1e6, tavg[core] * 1e3, color=C1, linewidth=1.8, label='averaged over 1 PWM period')
style(a, 'E. Torque: PWM ripple + a dip at every commutation', 'torque (mN·m)', 'time (µs)')
a.set_ylim(0, 60); a.legend(frameon=False, loc='upper right', ncol=1)
import json
json.dump({'te_avg_filt_pp': float(np.ptp(tavg[core])), 'te_avg_filt_mean': float(np.mean(tavg[core])),
           'te_raw_pp': float(np.ptp(d['V(te)'][w]))}, open(os.path.join(here, 'torque_ripple.json'), 'w'), indent=1)

# F: loss breakdown per mode (horizontal grouped bars)
a = ax[2, 1]
pin, pm, pcu, ph, pl = (meas(k) for k in ('pin', 'pmech', 'pcu', 'pfet_hi', 'pfet_lo'))
cats = ['High-side FETs', 'Low-side FETs\n(incl. body diodes)', 'Copper (windings)', 'Other\n(caps, battery)']
vals = [[ph[i], pl[i], pcu[i], pin[i] - pm[i] - ph[i] - pl[i] - pcu[i]] for i in range(2)]
yy = np.arange(len(cats))
for i, (lab, c) in enumerate([('Sync=0', C2), ('Sync=1', C1)]):
    bars = a.barh(yy + (-0.2 if i == 0 else 0.2), vals[i], height=0.38, color=c, label=lab)
    for b, v in zip(bars, vals[i]):
        a.text(b.get_width() + 0.08, b.get_y() + b.get_height() / 2, f'{v:.2f} W', va='center', fontsize=8, color=INK)
a.set_yticks(yy, cats); a.invert_yaxis(); a.grid(axis='y', visible=False)
a.set_xlim(0, max(max(v) for v in vals) * 1.25)
style(a, f'F. Losses: efficiency {pm[0]/pin[0]*100:.1f} % (Sync=0) vs {pm[1]/pin[1]*100:.1f} % (Sync=1)', '', 'power (W)')
a.legend(frameon=False, loc='lower right')
fig.tight_layout(rect=(0, 0, 1, 0.97))
out = os.path.join(here, 'ThreePhase_ESC_BLDC_results.png'); fig.savefig(out, dpi=130); print(out)
