"""Builds ThreeChannel_Transmission_results.png from ThreeChannel_Transmission.raw (.step Case 0/1/2)."""
import sys, os, json
import numpy as np, matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
here = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(here, '..', 'tools')); sys.path.insert(0, here)
from ltraw import read_raw, split_steps
from hand_calc import CH, z_bus, hotplug, Fsw

st = split_steps(read_raw(os.path.join(here, 'ThreeChannel_Transmission.raw')))
vb = lambda d, k: d[f'V(bus{k})'] - d[f'V(g{k})']
C1, C2, C3, INK, INK2, SURF = '#2a78d6', '#eb6834', '#1baf7a', '#0b0b0b', '#52514e', '#fcfcfb'
CC = (C1, C2, C3)
plt.rcParams.update({'font.size': 9, 'axes.edgecolor': INK2, 'axes.labelcolor': INK2, 'xtick.color': INK2,
    'ytick.color': INK2, 'axes.spines.top': False, 'axes.spines.right': False, 'axes.grid': True,
    'grid.color': '#e4e3df', 'grid.linewidth': 0.6, 'lines.linewidth': 1.3, 'figure.facecolor': SURF, 'axes.facecolor': SURF})
fig, ax = plt.subplots(4, 2, figsize=(12, 13.5))
fig.suptitle('04 Three-channel power transmission - 3 x (4S pack -> 14 AWG harness + XT60 -> ESC DC link -> motor), 48 kHz ESCs',
             color=INK, fontsize=11, x=0.01, ha='left')
def style(a, title, yl, xl):
    a.set_title(title, loc='left', color=INK, fontsize=10); a.set_ylabel(yl); a.set_xlabel(xl)
def pwm_avg(t, sig, t0, t1, dt=0.1e-6):
    tu = np.arange(t0, t1, dt); y = np.interp(tu, t, sig); n = int(round(1 / Fsw / dt))
    return tu[n:-n], np.convolve(y, np.ones(n) / n, mode='same')[n:-n]
extra = {}

# A: hot plug, ceramic only, all channels
a = ax[0, 0]; d = st[0]; t = d['time']; w = t < 120e-6
for k in (1, 2, 3):
    hp = hotplug(CH[k - 1], False)
    a.plot((t[w] - 10e-6) * 1e6, vb(d, k)[w], color=CC[k - 1], label=f'ch{k} ({CH[k-1]["len"]*100:.0f} cm): peak {vb(d, k)[w].max():.1f} V, hand {hp["Vpk"]:.1f} V')
a.axhline(30, color=INK, ls=':', lw=1); a.text(70, 30.4, 'FET rating 30 V', color=INK, fontsize=8)
style(a, 'A. Plug-in, ceramic only: L-C ringing overshoots to ~1.8 x Vbatt', 'ESC bus voltage (V)', 'time after contact (µs)')
a.legend(frameon=False, loc='lower right', fontsize=8); a.set_ylim(0, 33)

# B: hot plug with the bulk capacitor: no overshoot, but a huge inrush (the spark)
a = ax[0, 1]; d = st[1]; t = d['time']; w = t < 120e-6
for k in (1, 2, 3):
    a.plot((t[w] - 10e-6) * 1e6, d[f'I(Lpos{k})'][w], color=CC[k - 1], label=f'ch{k}: peak {d[f"I(Lpos{k})"][w].max():.0f} A')
style(a, 'B. Plug-in with 470 µF electrolytic: no overshoot, ~270 A inrush', 'battery current (A)', 'time after contact (µs)')
a.legend(frameon=False, loc='upper right')

# C: impedance seen by the ESC switching current
a = ax[1, 0]; f = np.logspace(3, 6.3, 800)
for k in (1, 3):
    a.loglog(f, abs(z_bus(CH[k - 1], f, False)), color=CC[k - 1], label=f'ch{k}, ceramic only')
    a.loglog(f, abs(z_bus(CH[k - 1], f, True)), color=CC[k - 1], ls='--', label=f'ch{k}, + electrolytic')
for m in (1, 2, 3):
    a.axvline(m * Fsw, color=INK2, lw=0.6, ls=':')
a.text(Fsw * 1.04, 3, 'fsw', color=INK2, fontsize=8); a.text(2 * Fsw * 1.04, 3, '2fsw', color=INK2, fontsize=8)
style(a, 'C. Bus impedance |Z(f)|: harness L resonates with the ceramic', '|Z| (Ω)', 'frequency (Hz)')
a.legend(frameon=False, loc='lower left', fontsize=8); a.set_ylim(1e-3, 5)

# D: channel 3 bus during the 25 A punch: ceramic only vs with bulk
a = ax[1, 1]
for c, col, lab in ((0, C2, 'ceramic only'), (1, C1, '+ 470 µF electrolytic')):
    d = st[c]; t = d['time']; w = (t > 7.6e-3) & (t < 9.2e-3)
    a.plot((t[w]) * 1e3, vb(d, 3)[w], color=col, lw=0.5, alpha=0.85, label=f'{lab}: {vb(d,3)[w & (t>8.2e-3)].min():.1f} to {vb(d,3)[w & (t>8.2e-3)].max():.1f} V')
a.axvline(8, color=INK2, lw=0.7); a.text(8.02, 21, 'motor 3: 3.8 -> 25 A', color=INK2, fontsize=8)
style(a, 'D. Channel 3 (60 cm, 57 kHz resonance) during a throttle punch', 'ESC 3 bus voltage (V)', 'time (ms)')
a.legend(frameon=False, loc='lower left', fontsize=8); a.set_ylim(5, 23)
d = st[1]; t = d['time']; tu, va = pwm_avg(t, vb(d, 3), 7.5e-3, 11e-3); extra['vmin_avg_step3_bulk'] = float(va[tu > 8e-3].min())

# E: independence: other channels' buses during the channel-3 punch (case 1)
a = ax[2, 0]; d = st[1]; t = d['time']
for k in (1, 2, 3):
    tu, va = pwm_avg(t, vb(d, k), 6e-3, 11e-3, 0.5e-6)
    a.plot(tu * 1e3, va, color=CC[k - 1], label=f'ESC {k} bus (PWM-averaged)')
a.axvline(8, color=INK2, lw=0.7)
style(a, 'E. Independence: only channel 3 sags when motor 3 punches', 'bus voltage (V)', 'time (ms)')
a.legend(frameon=False, loc='upper center', ncol=3, fontsize=8); a.set_ylim(14.3, 15.4)

# F: ground loop: battery negatives tied (case 2) vs independent (case 1)
a = ax[2, 1]
for c, ls, tag in ((1, '--', 'negatives separate'), (2, '-', 'negatives tied')):
    d = st[c]; t = d['time']
    for k in (1, 3):
        tu, ia = pwm_avg(t, d[f'I(Lsig{k})'], 6e-3, 11e-3, 0.5e-6)
        a.plot(tu * 1e3, ia, color=CC[k - 1], ls=ls, label=f'signal-ground wire {k}, {tag}')
a.axvline(8, color=INK2, lw=0.7)
style(a, 'F. Tie the battery negatives and power current leaks into signal grounds', 'current (A, PWM-averaged)', 'time (ms)')
a.legend(frameon=False, loc='upper left', fontsize=7.5); a.set_ylim(-1.2, 2.0)

# G: ripple at steady state, channel 2 (highest current), both cases
a = ax[3, 0]
for c, col, lab in ((0, C2, 'ceramic only'), (1, C1, '+ electrolytic')):
    d = st[c]; t = d['time']; w = (t > 7.9e-3) & (t < 8.0e-3)
    a.plot((t[w] - 7.9e-3) * 1e6, vb(d, 2)[w], color=col, lw=0.9, label=f'{lab}: {np.ptp(vb(d,2)[(t>6e-3)&(t<8e-3)]):.2f} V p-p')
style(a, 'G. Channel 2 bus ripple at 125 W (20,000 RPM)', 'ESC 2 bus voltage (V)', 'time (µs)')
a.legend(frameon=False, loc='lower left')

# H: where the power goes in each channel (case 1, steady state)
a = ax[3, 1]
from ltraw import read_meas
m = read_meas(os.path.join(here, 'ThreeChannel_Transmission.log'))
from hand_calc import harness, Rbatt, ESRb, ESRc
labels = ['Battery Rint', 'Harness + XT60', 'Cap ESR']
for k in (1, 2, 3):
    i = k - 1; Rl = harness(CH[i])[0]
    ib = m[f'ibat_rms{k}'][1]
    vals = [Rbatt * ib ** 2, Rl * ib ** 2, ESRb * m[f'ibulk_rms{k}'][1] ** 2 + ESRc * m[f'icer_rms{k}'][1] ** 2]
    left = 0
    for j, v in enumerate(vals):
        a.barh(k, v, left=left, color=(C1, C2, C3)[j], height=0.55, label=labels[j] if k == 1 else None); left += v
    a.text(left + 0.03, k, f'{left:.2f} W of {m[f"pload{k}"][1]:.0f} W delivered ({left/(left+m[f"pload{k}"][1])*100:.1f} %)', va='center', fontsize=8, color=INK)
a.set_yticks([1, 2, 3], ['ch1', 'ch2', 'ch3']); a.invert_yaxis(); a.grid(axis='y', visible=False); a.set_xlim(0, 4.6)
style(a, 'H. Transmission losses at steady state (with electrolytic)', '', 'power (W)'); a.legend(frameon=False, loc='lower right')
d = st[2]; t = d['time']
for k in (1, 2, 3):
    w1 = (t > 6e-3) & (t < 8e-3); w2 = (t > 10e-3) & (t < 11e-3)
    extra[f'isig_avg_ss{k}'] = float(np.trapezoid(d[f'I(Lsig{k})'][w1], t[w1]) / (t[w1][-1] - t[w1][0]))
    extra[f'isig_avg_after{k}'] = float(np.trapezoid(d[f'I(Lsig{k})'][w2], t[w2]) / (t[w2][-1] - t[w2][0]))
json.dump(extra, open(os.path.join(here, 'extra_metrics.json'), 'w'), indent=1)
fig.tight_layout(rect=(0, 0, 1, 0.97))
out = os.path.join(here, 'ThreeChannel_Transmission_results.png'); fig.savefig(out, dpi=130); print(out, extra)
