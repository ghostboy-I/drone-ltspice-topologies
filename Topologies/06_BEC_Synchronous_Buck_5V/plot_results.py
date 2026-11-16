"""Builds BEC_results.png from BEC_Buck.raw (switching, .step FF 0/1) and BEC_Buck_AC.raw (averaged, .ac), plus extra_metrics.json."""
import sys, os, json
import numpy as np, matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
here = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(here, '..', 'tools')); sys.path.insert(0, here)
from ltraw import read_raw, split_steps, read_meas
import hand_calc as h

ac = read_raw(os.path.join(here, 'BEC_Buck_AC.raw')); fq = ac['frequency']
Tac = -ac['V(out)'] / ac['V(x)']
cut = np.where(np.diff(fq) < 0)[0] + 1; acs = np.split(np.arange(len(fq)), cut)
st = split_steps(read_raw(os.path.join(here, 'BEC_Buck.raw')))       # step order: FF=0, FF=1
m = read_meas(os.path.join(here, 'BEC_Buck.log'))
Tsw = 1 / h.fsw
C1, C2, C3, INK, INK2, SURF = '#2a78d6', '#eb6834', '#1baf7a', '#0b0b0b', '#52514e', '#fcfcfb'
plt.rcParams.update({'font.size': 9, 'axes.edgecolor': INK2, 'axes.labelcolor': INK2, 'xtick.color': INK2,
    'ytick.color': INK2, 'axes.spines.top': False, 'axes.spines.right': False, 'axes.grid': True,
    'grid.color': '#e4e3df', 'grid.linewidth': 0.6, 'lines.linewidth': 1.3, 'figure.facecolor': SURF, 'axes.facecolor': SURF})
fig, ax = plt.subplots(3, 2, figsize=(12, 10.5))
fig.suptitle('06 BEC - 4S -> 5 V / 3 A synchronous buck, 500 kHz, voltage mode + Type III + input feed-forward',
             color=INK, fontsize=11, x=0.01, ha='left')
def style(a, title, yl, xl):
    a.set_title(title, loc='left', color=INK, fontsize=10); a.set_ylabel(yl); a.set_xlabel(xl)
def uni(d, key, t0, t1, dt=2e-9):
    tu = np.arange(t0, t1, dt); return tu, np.interp(tu, d['time'], d[key])
def mavg(y, n): return np.convolve(y, np.ones(n) / n, mode='same')
ex = {}

# A: loop gain, hand vs LTspice (averaged model)
a = ax[0, 0]; b = a.twinx()
for idx, (R, col, lab) in enumerate(((5 / 3, C1, '3 A'), (50 / 3, C2, '0.3 A'))):
    p = acs[idx]; f = fq[p]; Th = h.loop(f, h.PARTS, R)
    a.semilogx(f, 20 * np.log10(abs(Tac[p])), color=col, label=f'|T| LTspice, {lab}')
    a.semilogx(f, 20 * np.log10(abs(Th)), color=INK, lw=0.8, ls=':', label='hand calc' if idx == 0 else None)
    b.semilogx(f, np.degrees(np.unwrap(np.angle(Tac[p]))), color=col, ls='--', lw=1)
    i = np.argmax(abs(Tac[p]) < 1); ex[f'fc_sim_{idx}'] = float(f[i]); ex[f'pm_sim_{idx}'] = float(180 + np.degrees(np.angle(Tac[p][i])))
a.axhline(0, color=INK2, lw=0.7); b.set_ylabel('phase of T (deg, dashed)'); b.set_ylim(-300, 0); b.grid(False); b.spines['right'].set_visible(True)
a.set_ylim(-60, 80)
style(a, f'A. Loop gain: fc = {ex["fc_sim_0"]/1e3:.0f} kHz, PM = {ex["pm_sim_0"]:.0f}° (3 A) / {ex["pm_sim_1"]:.0f}° (0.3 A)', 'gain (dB)', 'frequency (Hz)')
a.legend(frameon=False, loc='lower left', fontsize=8)

d1 = st[1]; d0 = st[0]; t = d1['time']
# B: soft start
a = ax[0, 1]; w = t < 1.4e-3
a.plot(t[w] * 1e3, d1['V(out)'][w], color=C1, label='Vout')
a.plot(t[w] * 1e3, d1['V(ref)'][w] * h.Vout_set / h.Vref, color=INK2, ls='--', lw=1, label='Vref · (1 + Rtop/Rbot)')
a2 = a.twinx(); a2.plot(t[w] * 1e3, d1['I(L1)'][w], color=C2, lw=0.6, alpha=0.7); a2.set_ylabel('inductor current (A)', color=C2); a2.grid(False); a2.spines['right'].set_visible(True)
style(a, 'B. Soft-start: reference ramps 0 -> 0.8 V in 1 ms', 'volts', 'time (ms)'); a.legend(frameon=False, loc='upper left')

# C: load step
a = ax[1, 0]
dV_hand = (h.Iout - 0.5) / (2 * np.pi * ex['fc_sim_0'] * h.C)
for d, col, lab in ((d1, C1, 'Vout'),):
    w = (t > 1.45e-3) & (t < 1.9e-3)
    a.plot((t[w] - 1.5e-3) * 1e6, d['V(out)'][w], color=col, lw=0.8, label=lab)
a.axhline(h.Vout_set - dV_hand, color=INK2, ls=':', lw=1); a.text(150, h.Vout_set - dV_hand + 0.01, f'hand: ΔI/(2π fc C) = {dV_hand*1e3:.0f} mV', color=INK2, fontsize=8)
a2 = a.twinx(); a2.plot((t[w] - 1.5e-3) * 1e6, d1['I(L1)'][w], color=C2, lw=0.5, alpha=0.6); a2.plot((t[w] - 1.5e-3) * 1e6, d1['V(iload)'][w], color=INK, lw=1)
a2.set_ylabel('iL (orange), load (black) (A)'); a2.grid(False); a2.spines['right'].set_visible(True)
style(a, f'C. Load step 0.5 -> 3 A: dip {(h.Vout_set - m["vmin_step"][1])*1e3:.0f} mV, recovers in ~{0}'.replace(', recovers in ~0', ''), 'Vout (V)', 'time after step (µs)')

# switching-ripple metrics from a quiet window (detrended)
tu, vo = uni(d1, 'V(out)', 2.84e-3, 2.9e-3); n = int(round(Tsw / 2e-9))
rip = (vo - mavg(vo, n))[n:-n]; ex['vrip_detrended'] = float(np.ptp(rip))
tu, il = uni(d1, 'I(L1)', 2.84e-3, 2.9e-3); ex['il_rms'] = float(np.sqrt(np.mean(il ** 2)))
tu, vsw = uni(d1, 'V(sw)', 2.84e-3, 2.9e-3); ex['diode_frac'] = float(np.mean(vsw < -0.3))

# D: switching waveforms
a = ax[1, 1]; w = (t > 2.88e-3) & (t < 2.88e-3 + 3 * Tsw)
a.plot((t[w] - 2.88e-3) * 1e6, d1['V(sw)'][w], color=INK2, lw=0.8, label='V(sw)')
a2 = a.twinx(); a2.plot((t[w] - 2.88e-3) * 1e6, d1['I(L1)'][w], color=C2, label='iL'); a2.set_ylabel('iL (A)', color=C2); a2.grid(False); a2.spines['right'].set_visible(True)
a3 = a.inset_axes([0.55, 0.55, 0.42, 0.4]); tu2, vo2 = uni(d1, 'V(out)', 2.88e-3, 2.88e-3 + 3 * Tsw)
a3.plot((tu2 - 2.88e-3) * 1e6, (vo2 - vo2.mean()) * 1e3, color=C1, lw=1); a3.set_title(f'Vout ripple {ex["vrip_detrended"]*1e3:.1f} mV p-p', fontsize=7.5); a3.tick_params(labelsize=7)
style(a, 'D. Switch node and inductor current at 3 A', 'V(sw) (V)', 'time (µs)')

# E: ESC bus ripple at the input: output with feed-forward off / on (switching ripple averaged out)
a = ax[2, 0]
for d, col, lab in ((d0, C2, 'feed-forward OFF'), (d1, C1, 'feed-forward ON')):
    tu, vo = uni(d, 'V(out)', 2.6e-3, 4.2e-3, 10e-9); keep = (tu > 2.63e-3) & (tu < 4.17e-3); va = mavg(vo, int(round(Tsw / 10e-9)))
    a.plot(tu[keep] * 1e3, (va[keep] - h.Vout_set) * 1e3, color=col, label=lab)
    k = 'off' if d is d0 else 'on'
    sel = (tu > 3.0e-3) & (tu < 3.4e-3); y = va[sel] - va[sel].mean(); ts = tu[sel]
    ex[f'a48_{k}'] = float(2 * abs(np.mean(y * np.exp(-2j * np.pi * 48e3 * ts))))      # 48 kHz amplitude (lock-in)
    ex[f'sag_{k}'] = float(h.Vout_set - va[(tu > 3.5e-3) & (tu < 3.8e-3)].min())
a.axvline(2.9, color=INK2, lw=0.6); a.text(2.92, 30, '1.5 V p-p\n48 kHz ripple', color=INK2, fontsize=7.5)
a.axvline(3.5, color=INK2, lw=0.6); a.text(3.52, 30, '0.8 V sag', color=INK2, fontsize=7.5)
style(a, 'E. ESC bus disturbances at the BEC input (Vout averaged per cycle)', 'Vout - 4.984 V (mV)', 'time (ms)')
a.legend(frameon=False, loc='lower left'); a.set_ylim(-60, 45)

# F: losses
a = ax[2, 1]
Ron = 4e-3 + 1 / (60 * (5 - 1.6)); Irms2 = ex['il_rms'] ** 2
Vf = 0.8; tdead_eff = ex['diode_frac'] * Tsw / 2
hand = {'HS conduction': h.D * Irms2 * Ron, 'LS conduction': (1 - h.D) * Irms2 * Ron, 'Dead-time diode': 2 * 20e-9 * h.fsw * Vf * h.Iout,
        'Inductor DCR': Irms2 * h.DCR}
Vplat = 1.6 + np.sqrt(2 * h.Iout / 60); Qgd = 150e-12 * h.Vin                 # average Cgd ~150 pF over the swing (400p -> 60p)
tr = Qgd / ((5 - Vplat) / 10); tf = Qgd / (Vplat / 10)                          # RgH = 10 ohm on and off
hand['HS switching'] = 0.5 * h.Vin * h.Iout * (tr + tf) * h.fsw; ex['tr'] = tr; ex['tf'] = tf
tu, gl = uni(d1, 'V(gl)', 2.84e-3, 2.9e-3, 0.2e-9); tu, gh = uni(d1, 'V(gh)', 2.84e-3, 2.9e-3, 0.2e-9); _, vs = uni(d1, 'V(sw)', 2.84e-3, 2.9e-3, 0.2e-9)
ex['vgs_ls_induced'] = float(gl[(gh - vs) > 1.6].max())
labels = ['High-side FET', 'Low-side FET', 'Inductor DCR']
simv = [m['phs'][1], m['pls'][1], m['pdcr'][1]]
handv = [hand['HS conduction'] + hand['HS switching'], hand['LS conduction'] + hand['Dead-time diode'], hand['Inductor DCR']]
y = np.arange(3)
a.barh(y - 0.2, handv, height=0.38, color='#b7d3f6', label='hand (conduction, dead time, HS switching)')
a.barh(y + 0.2, simv, height=0.38, color=C1, label='LTspice')
for yy, v in zip(y + 0.2, simv): a.text(v + 0.01, yy, f'{v:.2f} W', va='center', fontsize=8)
a.set_yticks(y, labels); a.invert_yaxis(); a.grid(axis='y', visible=False); a.set_xlim(0, 0.42)
style(a, f'F. Losses at 3 A: efficiency {m["eff"][1]*100:.1f} %', '', 'power (W)'); a.legend(frameon=False, loc='center right', fontsize=8)
ex['ron'] = Ron; ex.update({f'hand_{k}': v for k, v in hand.items()})
json.dump(ex, open(os.path.join(here, 'extra_metrics.json'), 'w'), indent=1)
fig.tight_layout(rect=(0, 0, 1, 0.96))
out = os.path.join(here, 'BEC_results.png'); fig.savefig(out, dpi=130); print(out); print(json.dumps(ex, indent=1))
