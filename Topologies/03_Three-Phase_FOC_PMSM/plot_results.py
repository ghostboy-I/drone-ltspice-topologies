"""Builds ThreePhase_FOC_results.png from ThreePhase_FOC.raw (+ ref_02_torque.npz for the 6-step comparison)."""
import sys, os, json
import numpy as np, matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
here = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(here, '..', 'tools'))
from ltraw import read_raw, read_meas

d = read_raw(os.path.join(here, 'ThreePhase_FOC.raw')); t = d['time']
m = {k: v[0] for k, v in read_meas(os.path.join(here, 'ThreePhase_FOC.log')).items()}
ref = np.load(os.path.join(here, 'ref_02_torque.npz'))
Pp, Fsw, Fci, Tstep = 7, 48e3, 3e3, 170e-3

C1, C2, C3, INK, INK2, SURF = '#2a78d6', '#eb6834', '#1baf7a', '#0b0b0b', '#52514e', '#fcfcfb'
plt.rcParams.update({'font.size': 9, 'axes.edgecolor': INK2, 'axes.labelcolor': INK2, 'xtick.color': INK2,
    'ytick.color': INK2, 'axes.spines.top': False, 'axes.spines.right': False, 'axes.grid': True,
    'grid.color': '#e4e3df', 'grid.linewidth': 0.6, 'lines.linewidth': 1.3, 'figure.facecolor': SURF, 'axes.facecolor': SURF})
fig, ax = plt.subplots(4, 2, figsize=(12, 13.5))
fig.suptitle('03 Three-phase inverter + PMSM, sensored FOC with SVPWM - 4S LiPo, 48 kHz PWM, speed command 14,000 RPM',
             color=INK, fontsize=11, x=0.01, ha='left')
def style(a, title, yl, xl):
    a.set_title(title, loc='left', color=INK, fontsize=10); a.set_ylabel(yl); a.set_xlabel(xl)

def pwm_avg(sig, t0, t1, dt=0.1e-6):
    """Resample uniformly and average over one PWM period (what the motor 'feels')."""
    tu = np.arange(t0, t1, dt); y = np.interp(tu, t, sig); n = int(round(1 / Fsw / dt))
    return tu[n:-n], np.convolve(y, np.ones(n) / n, mode='same')[n:-n]

# A: speed command vs speed
a = ax[0, 0]
a.plot(t * 1e3, d['V(wref)'] * 60 / (2 * np.pi), color=INK2, ls='--', label='command')
a.plot(t * 1e3, d['V(rpm)'], color=C1, label='rotor speed')
style(a, 'A. Speed loop: rotor follows the ramp command', 'RPM', 'time (ms)'); a.legend(frameon=False, loc='lower right')

# B: dq currents over the whole run (PWM-averaged so the DC nature is visible)
a = ax[0, 1]
tq, iq = pwm_avg(d['V(iq)'], 0, t[-1], 1e-6); _, idd = pwm_avg(d['V(id)'], 0, t[-1], 1e-6)
a.plot(t * 1e3, d['V(iqref)'], color=INK2, ls='--', lw=1, label='iq* (speed PI output)')
a.plot(tq * 1e3, iq, color=C1, label='iq (torque current)')
a.plot(tq * 1e3, idd, color=C2, label='id (flux current, held at 0)')
style(a, 'B. In the rotor (d-q) frame the currents are DC', 'current (A)', 'time (ms)'); a.legend(frameon=False, loc='upper right')

# C: phase currents over ~1.25 electrical revolutions at steady state
we = Pp * np.mean(d['V(omega)'][t > t[-1] - 5e-3]); Tel = 2 * np.pi / we
w = t > t[-1] - 1.25 * Tel; x = (t[w] - t[w][0]) * 1e6
a = ax[1, 0]
for n, c in zip('abc', (C1, C2, C3)):
    a.plot(x, d['I(L%s)' % n][w], color=c, lw=1.0, label='phase ' + n.upper())
style(a, 'C. Phase currents: sinusoids (all three phases always conduct)', 'current (A)', 'time (µs)')
a.set_ylim(-11, 14); a.legend(frameon=False, loc='upper right', ncol=3)

# D: SVPWM modulation signals for phase A
a = ax[1, 1]
vb = np.mean(d['V(bus)'][w])
a.plot(x, d['V(va)'][w] / vb + 0.5, color=C1, lw=1.0, label='sine reference  0.5 + va/Vbus')
a.plot(x, -d['V(voff)'][w] / vb + 0.5, color=INK2, lw=1.0, ls=':', label='0.5 - min-max offset')
a.plot(x, d['V(dua)'][w], color=C2, lw=1.6, label='duty A (SVPWM "saddle")')
style(a, 'D. SVPWM = sine + common-mode offset (cancels line-to-line)', 'duty', 'time (µs)')
a.set_ylim(0.15, 0.95); a.legend(frameon=False, loc='upper right', fontsize=8)

# E: torque, FOC vs 6-step (both PWM-averaged), same speed and load
a = ax[2, 0]
tt, te = pwm_avg(d['V(te)'], t[-1] - 4e-3, t[-1])
a.plot(ref['t'] * 1e3, ref['te_avg'] * 1e3, color=C2, label='02 6-step (complementary PWM)')
a.plot((tt - tt[0]) * 1e3, te * 1e3, color=C1, lw=1.8, label='03 FOC')
style(a, 'E. Torque averaged over each PWM period: FOC removes commutation dips', 'torque (mN·m)', 'time (ms)')
a.set_ylim(0, 45); a.legend(frameon=False, loc='upper right')
metrics = {'te_avg_filt_pp': float(np.ptp(te)), 'te_avg_filt_mean': float(np.mean(te)),
           'te_raw_pp': float(np.ptp(d['V(te)'][t > t[-1] - 4e-3])), 'ref02_avg_filt_pp': float(np.ptp(ref['te_avg']))}

# F: d-axis current step: first-order response with tau = 1/(2 pi Fci)
a = ax[2, 1]
w2 = (t > Tstep - 50e-6) & (t < Tstep + 400e-6)
tau = 1 / (2 * np.pi * Fci); tx = np.linspace(Tstep, Tstep + 400e-6, 400)
a.plot((t[w2] - Tstep) * 1e6, d['V(id)'][w2], color=C2, lw=0.9, label='id (simulated, with PWM ripple)')
a.plot((t[w2] - Tstep) * 1e6, d['V(idref)'][w2], color=INK2, ls='--', lw=1, label='id* step')
a.plot((tx - Tstep) * 1e6, -5 * (1 - np.exp(-(tx - Tstep) / tau)), color=INK, lw=1.4, label='hand calc: -5(1 - exp(-t/τ))')
tu_, idu_ = pwm_avg(d['V(id)'], Tstep - 50e-6, Tstep + 400e-6, 0.05e-6)
t63 = (tu_[np.argmax(idu_ < -5 * (1 - np.exp(-1)))] - Tstep)
a.plot((tu_ - Tstep) * 1e6, idu_, color=C1, lw=1.6, label=f'id averaged over 1 PWM period (63 % at {t63*1e6:.1f} µs)')
a.axvline(tau * 1e6, color=INK2, lw=0.7); a.text(tau * 1e6 + 5, -6.7, f'τ = {tau*1e6:.0f} µs', color=INK2, fontsize=8)
style(a, 'F. Current-loop step test: id* 0 -> -5 A', 'id (A)', 'time after step (µs)'); a.legend(frameon=False, loc='lower left', bbox_to_anchor=(0.18, 0.62), fontsize=7.5)
a.set_ylim(-7, 1.5)
metrics['t63_id_step'] = float(t63)
json.dump(metrics, open(os.path.join(here, 'torque_ripple.json'), 'w'), indent=1)

# G: dq voltages vs hand calc
a = ax[3, 0]
tv, vq = pwm_avg(d['V(vq)'], 0, t[-1], 1e-6); _, vd = pwm_avg(d['V(vd)'], 0, t[-1], 1e-6)
a.plot(tv * 1e3, vq, color=C1, label='vq'); a.plot(tv * 1e3, vd, color=C2, label='vd')
a.axhline(vb / np.sqrt(3), color=INK2, ls=':', label='SVPWM limit Vbus/√3')
style(a, 'G. Voltage commands: vq ≈ back-EMF, vd ≈ -ωe·L·iq', 'volts (phase peak)', 'time (ms)'); a.legend(frameon=False, loc='upper center', ncol=3); a.set_ylim(-2.5, 10.5)

# H: losses
a = ax[3, 1]
cats = ['High-side FETs', 'Low-side FETs', 'Copper (windings)', 'Other (caps)']
vals = [m['pfet_hi'], m['pfet_lo'], m['pcu'], m['pin'] - m['pmech'] - m['pfet_hi'] - m['pfet_lo'] - m['pcu']]
bars = a.barh(range(4), vals, color=C1, height=0.55)
for b, v in zip(bars, vals):
    a.text(b.get_width() + 0.05, b.get_y() + b.get_height() / 2, f'{v:.2f} W', va='center', fontsize=8, color=INK)
a.set_yticks(range(4), cats); a.invert_yaxis(); a.grid(axis='y', visible=False); a.set_xlim(0, max(vals) * 1.3)
style(a, f'H. Losses at 14,000 RPM: efficiency {m["efficiency"]*100:.1f} %', '', 'power (W)')

fig.tight_layout(rect=(0, 0, 1, 0.97))
out = os.path.join(here, 'ThreePhase_FOC_results.png'); fig.savefig(out, dpi=130); print(out)
