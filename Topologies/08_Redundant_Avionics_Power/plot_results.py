"""Builds Redundant_Avionics_results.png and extra_metrics.json from Redundant_Avionics.raw / .log (.step Case 0..4)."""
import sys, os, json
import numpy as np, matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
here = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(here, '..', 'tools')); sys.path.insert(0, here)
from ltraw import read_raw, split_steps, read_meas
import hand_calc as h

st = split_steps(read_raw(os.path.join(here, 'Redundant_Avionics.raw')))
m = read_meas(os.path.join(here, 'Redundant_Avionics.log'))
C1, C2, C3, C4, C5, INK, INK2, SURF = '#2a78d6', '#eb6834', '#1baf7a', '#8a5cd6', '#d6a32a', '#0b0b0b', '#52514e', '#fcfcfb'
COL = [C2, C4, C1, C5, C3]
PK = [C1, C2, C3]   # pack 1, 2, 3
plt.rcParams.update({'font.size': 9, 'axes.edgecolor': INK2, 'axes.labelcolor': INK2, 'xtick.color': INK2,
    'ytick.color': INK2, 'axes.spines.top': False, 'axes.spines.right': False, 'axes.grid': True,
    'grid.color': '#e4e3df', 'grid.linewidth': 0.6, 'lines.linewidth': 1.4, 'figure.facecolor': SURF, 'axes.facecolor': SURF})
fig, ax = plt.subplots(3, 2, figsize=(12, 11))
fig.suptitle('08 Redundant avionics power - one 5 V rail from three floating 4S packs '
             '(punch on ESC 1 at 3 ms, pack 1 unplugged at 5 ms, bus 2 shorted at 6 ms)', color=INK, fontsize=11, x=0.01, ha='left')
def style(a, title, yl, xl):
    a.set_title(title, loc='left', color=INK, fontsize=10); a.set_ylabel(yl); a.set_xlabel(xl)
ms = lambda d: d['time'] * 1e3
extra = {}

# A: which pack supplies the BEC (recommended Case 2) - whole timeline
a = ax[0, 0]; d = st[2]; w = (d['time'] > 1.5e-3)
for k in (1, 2, 3):
    a.plot(ms(d)[w], d[f'I(Ltp{k})'][w], color=PK[k - 1], label=f'pack {k} ({h.VB[k-1]} V)')
for x, s in ((3, 'ESC 1\npunch'), (4, 'punch\nends'), (5, 'pack 1\nunplugged'), (6, 'bus 2\nshorted')):
    a.axvline(x, color=INK2, lw=0.6, ls=':'); a.text(x + 0.04, 1.12, s, color=INK2, fontsize=7.5, va='top')
style(a, 'A. Current each pack sends to the BEC (Case 2: + OR + star return)', 'tap current (A)', 'time (ms)')
a.legend(frameon=False, loc='center left', fontsize=8); a.set_ylim(-0.15, 1.2); a.set_xlim(1.5, 7)

# B: signal-wire current by architecture (normal and during the punch), sim bars + hand markers
a = ax[0, 1]; x = np.arange(5); wd = 0.36
sig_n = [sum(abs(m[f'isig{k}_n'][c]) for k in (1, 2, 3)) for c in range(5)]
sig_p = [sum(abs(m[f'isig{k}_p'][c]) for k in (1, 2, 3)) for c in range(5)]
hn, hp = [], []
for c in range(5):
    if c == 4: hn.append(0.0); hp.append(0.0); continue
    for lst, pesc in ((hn, h.PESC), (hp, [h.P1_PUNCH, h.PESC[1], h.PESC[2]])):
        s = h.share(c, pesc); g = h.ground_nodal(c, s['I'], s['iesc']); lst.append(sum(abs(i) for i in g['Isig']))
a.bar(x - wd / 2, sig_n, wd, color=C1, label='normal (pack 1 supplies)')
a.bar(x + wd / 2, sig_p, wd, color=C2, label='ESC 1 punch (packs 2+3 supply)')
a.plot(x - wd / 2, hn, 'k_', ms=14, mew=2, label='hand (nodal analysis)'); a.plot(x + wd / 2, hp, 'k_', ms=14, mew=2)
for i, v in enumerate(sig_n): a.text(i - wd / 2, v + 0.02, f'{v:.2f}', ha='center', fontsize=7.5, color=INK2)
for i, v in enumerate(sig_p): a.text(i + wd / 2, v + 0.02, f'{v:.2f}', ha='center', fontsize=7.5, color=INK2)
a.set_xticks(x); a.set_xticklabels(h.SHORT, fontsize=8)
style(a, 'B. BEC return current flowing in the 26 AWG signal grounds', 'sum of |I| in signal wires (A)', '')
a.legend(frameon=False, fontsize=8, loc='upper right'); a.set_ylim(0, 1.25)

# C: pack 1 unplugged - ESC 1 bus decays, the OR hands over, reverse current blocked (Case 2)
a = ax[1, 0]; d = st[2]; w = (d['time'] > 4.98e-3) & (d['time'] < 5.95e-3)
t = (d['time'][w] - 5e-3) * 1e3
a.plot(t, d['V(bus1)'][w] - d['V(g1)'][w], color=PK[0], label='ESC 1 bus (pack 1 gone)')
a.plot(t, d['V(vin)'][w], color=INK, label='BEC input vin')
a.plot(t, d['V(bus2)'][w] - d['V(g2)'][w], color=PK[1], lw=1, ls='--', label='ESC 2 bus')
a.set_ylim(7.5, 15.5)
a2 = a.twinx(); a2.plot(t, d['I(Ltp1)'][w], color=C4, lw=1.1, label='tap 1 current (right)')
a2.set_ylabel('tap 1 current (A)', color=C4); a2.spines['right'].set_visible(True); a2.grid(False); a2.set_ylim(-0.2, 1.4)
a.axvline(m['t_hand'][2] * 1e3 - 5, color=INK2, lw=0.6, ls=':')
a.text(m['t_hand'][2] * 1e3 - 5 + 0.02, 15.2, f'handover {(m["t_hand"][2] - 5e-3) * 1e6:.0f} µs', color=INK2, fontsize=8)
a.text(0.42, 10.3, f'ESC 1 drains its own caps;\nreverse current through D1:\n{m["itap1_rev"][2] * 1e6:.0f} µA (blocked)', color=INK2, fontsize=8)
style(a, 'C. Pack 1 unplugged at 5 ms: no back-feed into the dead channel', 'volts', 'time after unplug (ms)')
l1, n1 = a.get_legend_handles_labels(); l2, n2 = a2.get_legend_handles_labels()
a.legend(l1 + l2, n1 + n2, frameon=False, fontsize=8, loc='lower left', bbox_to_anchor=(0.0, 0.08))

# D: bus 2 shorted - reverse current through ideal diode 2 until it turns off (Cases 0, 2, 3)
a = ax[1, 1]
for c in (0, 2, 3):
    d = st[c]; w = (d['time'] > 5.99e-3) & (d['time'] < 6.0004e-3)
    a.plot((d['time'][w] - 6e-3) * 1e9, d['I(Ltp2)'][w], color=COL[c], label=f'{h.SHORT[c]}: peak {m["irev2_pk"][c]:.1f} A')
a.axhline(0, color=INK2, lw=0.6)
style(a, 'D. Bus 2 shorted: reverse current through the channel-2 OR device', 'tap 2 current (A)', 'time after the short starts (ns)')
a.legend(frameon=False, fontsize=8, loc='lower left'); a.set_xlim(-20, 400)
for c in range(5):     # turn-off timing from the waveforms
    d = st[c]; w = (d['time'] > 5.999e-3) & (d['time'] < 6.003e-3); tt = d['time'][w]
    vb = d['V(bus2)'][w] - d['V(g2)'][w]; vgs = d['V(gp2)'][w] - d['V(a2)'][w]
    tb = tt[np.argmax(vb < 7)]; extra[f't_collapse_{c}'] = float(tb - 6e-3)
    if c <= 2:
        tg = tt[np.argmax(vgs < h.FET['Vto'])]; extra[f't_det_{c}'] = float(tg - tb)
    extra[f'vgs_reg2_{c}'] = float(vgs[0])

# E: the 5 V rail through all events - BEC architectures vs isolated modules
a = ax[2, 0]
for c in (0, 2, 3, 4):
    d = st[c]; w = d['time'] > 1.5e-3
    a.plot(ms(d)[w], d['V(out)'][w], color=COL[c], lw=1.2 if c != 4 else 1.4, label=h.SHORT[c])
for xx in (3, 5, 6): a.axvline(xx, color=INK2, lw=0.6, ls=':')
style(a, 'E. The 5 V avionics rail (BEC curves overlap within 1 mV)', 'V(out) (V)', 'time (ms)')
a.legend(frameon=False, fontsize=8, loc='lower left', ncol=2); a.set_xlim(1.5, 7); a.set_ylim(4.6, 5.05)
a.text(6.05, 4.72, f'isolated: module 2 lost,\ndip to {m["vout_sh_min"][4]:.2f} V, droop to {m["vout_a"][4]:.2f} V', color=C3, fontsize=7.5)

# F: battery power drawn for the avionics and where the extra goes
a = ax[2, 1]
pav = [m['pav_n'][c] for c in range(5)]; pld = [m['pld_n'][c] for c in range(5)]
bars = a.bar(x, pav, 0.6, color=[COL[c] for c in range(5)])
a.bar(x, pld, 0.6, color='none', edgecolor=INK, hatch='//', lw=0.6, label='delivered to the 5 V load')
for i in range(5):
    a.text(i, pav[i] + 0.15, f'{pav[i]:.2f} W\n{pld[i] / pav[i] * 100:.1f} %', ha='center', fontsize=8, color=INK2)
a.set_xticks(x); a.set_xticklabels(h.SHORT, fontsize=8); a.set_ylim(0, 20.5)
style(a, 'F. Power drawn from the ESC buses for the avionics (normal flight)', 'W', '')
a.legend(frameon=False, fontsize=8, loc='upper left')

fig.tight_layout(rect=(0, 0, 1, 0.97))
fig.savefig(os.path.join(here, 'Redundant_Avionics_results.png'), dpi=130)
json.dump(extra, open(os.path.join(here, 'extra_metrics.json'), 'w'), indent=1)
print(json.dumps(extra, indent=1))
