"""Builds ChannelProtection_results.png from ChannelProtection.raw (.step Case 0..5)."""
import sys, os, json
import numpy as np, matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
here = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(here, '..', 'tools'))
from ltraw import read_raw, split_steps

st = split_steps(read_raw(os.path.join(here, 'ChannelProtection.raw')))
NAMES = ['bare XT60', 'XT90-S precharge (5 Ω)', 'active FETs, no Cgs', 'active FETs + 2.2 µF Cgs', 'reversed, bare', 'reversed, active FETs']
C1, C2, C3, C4, INK, INK2, SURF = '#2a78d6', '#eb6834', '#1baf7a', '#8a5cd6', '#0b0b0b', '#52514e', '#fcfcfb'
COL = {0: C2, 1: C3, 2: C4, 3: C1}
plt.rcParams.update({'font.size': 9, 'axes.edgecolor': INK2, 'axes.labelcolor': INK2, 'xtick.color': INK2,
    'ytick.color': INK2, 'axes.spines.top': False, 'axes.spines.right': False, 'axes.grid': True,
    'grid.color': '#e4e3df', 'grid.linewidth': 0.6, 'lines.linewidth': 1.4, 'figure.facecolor': SURF, 'axes.facecolor': SURF})
fig, ax = plt.subplots(3, 2, figsize=(12, 10.5))
fig.suptitle('05 Per-channel protection - plugging a 4S pack into an ESC (480 µF DC link) through a 30 cm harness',
             color=INK, fontsize=11, x=0.01, ha='left')
def style(a, title, yl, xl):
    a.set_title(title, loc='left', color=INK, fontsize=10); a.set_ylabel(yl); a.set_xlabel(xl)
vbg = lambda d: d['V(bus)'] - d['V(g)']
extra = {}

# A: bus voltage while plugging in
a = ax[0, 0]
for c in (0, 1, 2, 3):
    d = st[c]; t = d['time']; w = t < 14e-3
    a.plot((t[w] - 1e-3) * 1e3, vbg(d)[w], color=COL[c], label=NAMES[c])
a.axvline(10, color=INK2, lw=0.7, ls=':'); a.text(10.2, 7, 'XT90-S main\ncontact closes', color=INK2, fontsize=8)
style(a, 'A. ESC bus voltage after the connector touches', 'V(bus) - V(ESC gnd) (V)', 'time after contact (ms)')
a.legend(frameon=False, loc='lower right', fontsize=8); a.set_xlim(-0.5, 13)

# B: inrush current (log scale)
a = ax[0, 1]
for c in (0, 1, 2, 3):
    d = st[c]; t = d['time']; w = t < 14e-3
    i = np.clip(d['I(Lpos)'][w], 1e-3, None)
    a.semilogy((t[w] - 1e-3) * 1e3, i, color=COL[c], label=f'{NAMES[c]}: peak {d["I(Lpos)"][w].max():.1f} A')
style(a, 'B. Inrush current from the battery (log scale)', 'current (A)', 'time after contact (ms)')
a.legend(frameon=False, loc='upper right', fontsize=8); a.set_xlim(-0.5, 13); a.set_ylim(1e-2, 1e3)

# C: the soft-start mechanism: gate voltage and the Miller plateau (naive vs fixed)
a = ax[1, 0]
for c, ls in ((2, '--'), (3, '-')):
    d = st[c]; t = d['time']; w = t < 8.5e-3
    a.plot((t[w] - 1e-3) * 1e3, d['V(gt)'][w] - d['V(s)'][w], color=COL[c], ls=ls, label=f'Vgs, {NAMES[c]}')
    a.plot((t[w] - 1e-3) * 1e3, d['V(g)'][w] - d['V(s)'][w], color=INK2 if c == 3 else '#b9b8b3', ls=ls, lw=1, label=f'Vds of Q2, {NAMES[c]}')
a.axhline(2.68, color=INK2, lw=0.6, ls=':'); a.text(0.2, 3.3, 'Miller plateau ≈ 2.7 V', color=INK2, fontsize=8)
style(a, 'C. Gate drive: the 100 nF Miller cap kicks the gate on unless Cgs holds it', 'volts', 'time after contact (ms)')
a.legend(frameon=False, loc='upper right', fontsize=7.5); a.set_xlim(-0.2, 7); a.set_ylim(-1, 32)

# D: FET power and energy during the soft-start
a = ax[1, 1]; d = st[3]; t = d['time']; w = t < 8.5e-3
p = (d['V(g)'] - d['V(s)']) * d['Id(MQ2)'] + (d['V(hn)'] - d['V(s)']) * d['Id(MQ1)']
e = np.concatenate([[0], np.cumsum(0.5 * (p[1:] + p[:-1]) * np.diff(t))])
a.plot((t[w] - 1e-3) * 1e3, p[w], color=C1, label='FET power (W)')
a2 = a.twinx(); a2.plot((t[w] - 1e-3) * 1e3, e[w] * 1e3, color=C2, label='energy (mJ)'); a2.set_ylabel('energy (mJ)', color=C2)
a2.axhline(0.5 * 480e-6 * 15 ** 2 * 1e3, color=C2, lw=0.7, ls=':'); a2.text(5.9, 0.5 * 480e-6 * 225e3 - 4, '½CV² = 54 mJ', color=C2, fontsize=8)
a2.spines['right'].set_visible(True); a2.grid(False)
style(a, 'D. The FET absorbs ½CV² while it limits the current', 'power (W)', 'time after contact (ms)')
a.legend(frameon=False, loc='upper left'); a.set_xlim(-0.2, 7)
# average inrush during the 10..90 % ramp
v = vbg(d); i10 = np.argmax(v > 1.5); i90 = np.argmax(v > 13.5)
extra['iavg_ramp_active'] = float(np.mean(d['I(Lpos)'][i10:i90])); extra['t_ramp_active'] = float(t[i90] - t[i10])
extra['p_avg_ramp_active'] = float(np.mean(p[i10:i90]))

# E: reverse polarity
a = ax[2, 0]
for c, col in ((4, C2), (5, C1)):
    d = st[c]; t = d['time']; w = t < 19e-3
    a.semilogy((t[w] - 1e-3) * 1e3, np.clip(np.abs(d['I(Lpos)'][w]), 1e-10, None), color=col, label=f'{NAMES[c]}: {abs(d["I(Lpos)"][w][-1]):.3g} A')
style(a, 'E. Pack plugged in backwards: |battery current|', '|current| (A)', 'time after contact (ms)')
a.legend(frameon=False, loc='center right'); a.set_ylim(1e-10, 3e3)

# F: protection conduction loss vs current: back-to-back FETs vs a Schottky diode
a = ax[2, 1]
I = np.linspace(0, 30, 100); Ron = 0.6e-3 + 1 / (300 * (12.0 - 2.5))
a.plot(I, 2 * Ron * I ** 2, color=C1, label=f'2 FETs: 2·Ron·I²  (Ron = {Ron*1e3:.2f} mΩ at Vgs = 12 V)')
a.plot(I, 0.45 * I, color=C2, label='Schottky diode: 0.45 V · I')
for c in (3,):
    pass
from ltraw import read_meas
m = read_meas(os.path.join(here, 'ChannelProtection.log'))
a.plot([m['ibat_cruise'][3], m['ibat_punch'][3]], [m['pprot_cruise'][3], m['pprot_punch'][3]], 'o', color=INK, label='LTspice (cruise, punch)')
style(a, 'F. Cost of protection while flying', 'loss (W)', 'battery current (A)'); a.legend(frameon=False, loc='upper left')
d = st[3]; t = d['time']; w = t < 3e-3
extra['vds_q2_pk'] = float(np.max(d['V(g)'][w] - d['V(s)'][w]))
vgs = d['V(gt)'] - d['V(s)']; extra['vgs_kick'] = float(vgs[(t > 1e-3) & (t < 1.2e-3)].max())
v = vbg(d); i10 = np.argmax(v > 1.5); i90 = np.argmax(v > 13.5); extra['t10_active'] = float(t[i10] - 1e-3)
extra['i_q2_start'] = float(d['Id(MQ2)'][i10]); extra['i_q2_end'] = float(d['Id(MQ2)'][i90])
extra['ig_rg'] = float(np.mean((d['V(bus)'][i10:i90] - d['V(gt)'][i10:i90]) / 12e3))
w1 = (t > 28e-3) & (t < 33e-3); w2 = (t > 40e-3) & (t < 45e-3)
extra['vgs_cruise'] = float(np.mean(vgs[w1])); extra['vgs_punch'] = float(np.mean(vgs[w2]))
extra['ig_rgs'] = float(np.mean(vgs[i10:i90]) / 100e3); extra['dvgs_dt'] = float((vgs[i90] - vgs[i10]) / (t[i90] - t[i10]))
json.dump(extra, open(os.path.join(here, 'extra_metrics.json'), 'w'), indent=1)
fig.tight_layout(rect=(0, 0, 1, 0.96))
out = os.path.join(here, 'ChannelProtection_results.png'); fig.savefig(out, dpi=130); print(out, extra)
