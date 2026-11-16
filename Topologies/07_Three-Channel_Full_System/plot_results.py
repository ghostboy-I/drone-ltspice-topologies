"""Builds FullSystem_results.png and extra_metrics.json from FullSystem_PlugIn.raw and FullSystem_Flight.raw.
The flight .raw is a few GB, so it is opened with np.memmap and only the needed traces are converted."""
import sys, os, json, math
import numpy as np, matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
here = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, here)
import hand_calc as H


class Raw:
    """Column-selective LTspice binary .raw reader (transient, float32 traces, float64 time)."""
    def __init__(self, path):
        with open(path, 'rb') as f:
            head = f.read(200000)
        m = 'Binary:\n'.encode('utf-16le'); he = head.index(m) + len(m)
        lines = head[:he].decode('utf-16le').splitlines()
        nv = int(next(l for l in lines if l.startswith('No. Variables')).split(':')[1])
        npts = int(next(l for l in lines if l.startswith('No. Points')).split(':')[1])
        vi = lines.index('Variables:')
        self.names = [lines[vi + 1 + k].split('\t')[2] for k in range(nv)]
        dt = np.dtype([(self.names[0], '<f8')] + [(n, '<f4') for n in self.names[1:]])
        self.a = np.memmap(path, dtype=dt, mode='r', offset=he, shape=(npts,))
        self.t = np.abs(np.asarray(self.a['time'], dtype=float))
    def __getitem__(self, n):
        if ',' in n:                                   # 'V(a,b)' -> V(a) - V(b)
            p, q = n[2:-1].split(',')
            return self[f'V({p})'] - self[f'V({q})']
        return np.asarray(self.a[n], dtype=float)


def uniform(t, y, t0, t1, dt):
    tu = np.arange(t0, t1, dt); return tu, np.interp(tu, t, y)
def pwm_avg(t, y, t0, t1, dt=0.25e-6):
    """Moving average over one PWM period (removes the 48 kHz ripple, keeps everything slower)."""
    tu, yu = uniform(t, y, t0, t1, dt); n = int(round(1 / H.Fsw / dt))
    return tu[n:-n], np.convolve(yu, np.ones(n) / n, mode='same')[n:-n]     # drop the zero-padded ends
def win(t, y, t0, t1):
    w = (t >= t0) & (t <= t1); return np.trapezoid(y[w], t[w]) / (t[w][-1] - t[w][0])


P = Raw(os.path.join(here, 'FullSystem_PlugIn.raw'))
Fl = Raw(os.path.join(here, 'FullSystem_Flight.raw'))
C1, C2, C3, C4, INK, INK2, SURF = '#2a78d6', '#eb6834', '#1baf7a', '#8a5cd1', '#0b0b0b', '#52514e', '#fcfcfb'
CC = (C1, C2, C3)
plt.rcParams.update({'font.size': 9, 'axes.edgecolor': INK2, 'axes.labelcolor': INK2, 'xtick.color': INK2,
    'ytick.color': INK2, 'axes.spines.top': False, 'axes.spines.right': False, 'axes.grid': True,
    'grid.color': '#e4e3df', 'grid.linewidth': 0.6, 'lines.linewidth': 1.3, 'figure.facecolor': SURF, 'axes.facecolor': SURF})
fig, ax = plt.subplots(4, 2, figsize=(12, 14.5))
fig.suptitle('07 Full system - 3 packs -> harness -> protection FETs -> switching FOC ESC -> motor + prop, BEC on channel 1',
             color=INK, fontsize=11, x=0.01, ha='left')
def style(a, title, yl, xl='time (ms)'):
    a.set_title(title, loc='left', color=INK, fontsize=10); a.set_ylabel(yl); a.set_xlabel(xl)
ex = {}

# ================= run 1: plug-in, soft-start, arming =================
t = P.t
a = ax[0, 0]
for k in (1, 2, 3):
    vb = P[f'V(bus{k},g{k})']; pl = H.plugin(k - 1)
    tu, vba = pwm_avg(t, vb, 0, 20e-3)
    a.plot(tu * 1e3, vba, color=CC[k - 1], label=f'ch{k} bus: 90 % at {np.interp(0.9 * H.VB[k-1], vb[t < 9.9e-3], t[t < 9.9e-3]) * 1e3:.2f} ms (hand {pl["T90"]*1e3:.2f})')
    a.axvline(H.TON[k - 1] * 1e3, color=CC[k - 1], lw=0.7, ls=':')
a.plot(t * 1e3, P['V(v5fc)'], color=C4, label='5 V rail at the flight controller')
a.axvline(H.TARM * 1e3, color=INK2, lw=0.8, ls='--'); a.text(H.TARM * 1e3 + 0.2, 1, 'ESCs arm', color=INK2, fontsize=8)
style(a, 'A. Plug-in (contacts at 0.5 / 1.5 / 2.5 ms): ~4 ms gate delay, then a 1.5 ms Miller ramp', 'V')
a.legend(frameon=False, fontsize=7.5, loc='center right'); a.set_ylim(-0.5, 17)

a = ax[0, 1]
for k in (1, 2, 3):
    tu, ib = pwm_avg(t, P[f'I(Lpos{k})'], 0, 20e-3)
    a.plot(tu * 1e3, ib, color=CC[k - 1], label=f'ch{k}')
    pl = H.plugin(k - 1)
    a.hlines(pl['I_in'] + pl['Ibec'], (H.TON[k-1] + pl['t_d']) * 1e3, (H.TON[k-1] + pl['t_d'] + pl['t_ramp']) * 1e3, color=CC[k - 1], ls='--', lw=1)
a.axvline(H.TARM * 1e3, color=INK2, lw=0.8, ls='--')
a.text(11, 5.0, 'after arming: spin-up current\n(mostly copper loss at low speed)', color=INK2, fontsize=8)
a.text(0.2, 6.9, 'dashed: hand $(V_b - V_{plat})C_{dc}/(R_gC_m)$ (+ BEC on ch1)', color=INK2, fontsize=8)
style(a, 'B. Battery currents (PWM-averaged): ~5 A soft-start ramps, no spark', 'A')
a.legend(frameon=False, fontsize=8, loc='center left'); a.set_ylim(-0.5, 7.5)

a = ax[1, 0]
for k in (1, 2, 3):
    sp = H.spinup(k - 1)
    tu, iq = pwm_avg(t, P[f'V(iq{k})'], 9e-3, 20e-3)
    a.plot(tu * 1e3, iq, color=CC[k - 1], label=f'ch{k} iq (sim)')
    a.plot(sp['t'] * 1e3, sp['iq'], color=CC[k - 1], ls='--', lw=1)
    ex[f'iq{k}_spin'] = float(win(tu, iq, 15e-3, 20e-3))
a2 = a.twinx(); a2.spines['right'].set_visible(True); a2.grid(False)
for k in (1, 2, 3):
    a2.plot(t[t > 9e-3] * 1e3, P[f'V(rpm{k})'][t > 9e-3], color=CC[k - 1], lw=0.8, alpha=0.6)
a2.set_ylabel('RPM (thin lines)', color=INK2)
style(a, 'C. Spin-up after arming: iq (thick) vs linear speed-loop model (dashed)', 'iq (A)')
a.legend(frameon=False, fontsize=8, loc='upper left')

# ================= run 2: flight =================
t = Fl.t
a = ax[1, 1]
for k in (1, 2, 3):
    a.plot(t * 1e3, Fl[f'V(rpm{k})'], color=CC[k - 1], label=f'motor {k}')
tt = np.linspace(H.TPUNCH, 24e-3, 200); w3 = [H.punch(H.RPM[2] * math.pi / 30, H.TPUNCH, x) * 30 / math.pi for x in tt]
a.plot(tt * 1e3, w3, color=INK, ls='--', lw=1, label='hand: dω/dt = (K_t I_max - kω²)/J')
for x, s in ((H.TPUNCH, 'motor 3 punch'), (H.TOFF, 'pack 1 pulled')):
    a.axvline(x * 1e3, color=INK2, lw=0.8, ls='--'); a.text(x * 1e3 + 0.2, 21000, s, color=INK2, fontsize=8)
style(a, 'D. Flight: speeds. Punch on 3, pack 1 lost: motor 2 untouched', 'RPM')
a.legend(frameon=False, fontsize=8, loc='lower left'); a.set_ylim(0, 22500)

a = ax[2, 0]
for k in (1, 2, 3):
    tu, ib = pwm_avg(t, Fl[f'I(Lpos{k})'], 0, 24e-3)
    a.plot(tu * 1e3, ib, color=CC[k - 1], label=f'ch{k} battery current')
    ex[f'ibat{k}_curve'] = None
tu, i5 = pwm_avg(t, Fl['I(B_BECIN)'], 0, 24e-3)
a.plot(tu * 1e3, i5, color=C4, label='BEC input current (on ch1 bus)')
for x in (H.TPUNCH, H.TOFF): a.axvline(x * 1e3, color=INK2, lw=0.8, ls='--')
style(a, 'E. Flight: battery currents (PWM-averaged)', 'A')
a.legend(frameon=False, fontsize=8, loc='upper left')

a = ax[2, 1]
for k in (1, 2, 3):
    tu, vb = pwm_avg(t, Fl[f'V(bus{k},g{k})'], 0, 24e-3)
    a.plot(tu * 1e3, vb, color=CC[k - 1], label=f'ch{k} bus')
a.plot(t * 1e3, Fl['V(v5fc)'], color=C4, label='5 V rail at FC')
for x in (H.TPUNCH, H.TOFF): a.axvline(x * 1e3, color=INK2, lw=0.8, ls='--')
style(a, 'F. Flight: ESC bus voltages (PWM-averaged) and the 5 V rail', 'V')
a.legend(frameon=False, fontsize=8, loc='lower left'); a.set_ylim(0, 16.5)

# G: independence: deviation of the untouched channels from their steady value, and the signal-ground currents
a = ax[3, 0]
ref = {}
for k in (1, 2):
    tu, vb = pwm_avg(t, Fl[f'V(bus{k},g{k})'], 3e-3, 24e-3, dt=1e-6)
    vb1 = np.convolve(vb, np.ones(1000) / 1000, mode='same')     # 1 ms average: removes 6x electrical-frequency ripple too
    ref[k] = win(tu, vb, 4e-3, 8e-3)
    m = tu < (H.TOFF - 0.6e-3 if k == 1 else 24e-3)
    m = m & (tu > 3.6e-3) & (tu < 23.4e-3)
    a.plot(tu[m] * 1e3, (vb1[m] - ref[k]) * 1e3, color=CC[k - 1], label=f'ch{k} bus - its steady mean (1 ms average)')
    ex[f'dvbus{k}_pu_mV'] = float((win(tu, vb, 13e-3, 16e-3) - ref[k]) * 1e3)
    if k == 2: ex['dvbus2_dc_mV'] = float((win(tu, vb, 21e-3, 23.9e-3) - ref[k]) * 1e3)
tu, vb3 = pwm_avg(t, Fl['V(bus3,g3)'], 3e-3, 24e-3, dt=1e-6)
ex['dvbus3_pu_mV'] = float((win(tu, vb3, 13e-3, 16e-3) - win(tu, vb3, 4e-3, 8e-3)) * 1e3)
a.plot(tu * 1e3, (vb3 - win(tu, vb3, 4e-3, 8e-3)) * 1e3, color=C3, lw=0.8, alpha=0.5, label='ch3 bus (the punched one), for scale')
for x in (H.TPUNCH, H.TOFF): a.axvline(x * 1e3, color=INK2, lw=0.8, ls='--')
a2 = a.twinx(); a2.spines['right'].set_visible(True); a2.grid(False)
for k, ls in ((2, '-'), (3, ':')):
    tu, isg = pwm_avg(t, Fl[f'I(Lsig{k})'], 3e-3, 24e-3, dt=1e-6)
    a2.plot(tu * 1e3, isg * 1e6, color=INK2, ls=ls, lw=0.9, label=f'signal-ground current ch{k} (µA, right)')
a2.set_ylabel('signal-ground current (µA)', color=INK2); a2.set_ylim(-5, 5)
a.set_ylim(-500, 100)
style(a, 'G. Independence: untouched buses vs the punch and the pack loss', 'ΔVbus (mV)')
h1, l1 = a.get_legend_handles_labels(); h2, l2 = a2.get_legend_handles_labels()
a.legend(h1 + h2, l1 + l2, frameon=False, fontsize=7.5, loc='lower left')

# H: zoom on the pack-1 loss: ESC 1 bus, UVLO, BEC and 5 V rail, with the hand-calculated times
a = ax[3, 1]; hu = H.holdup()
w = (t > 15.5e-3) & (t < 24e-3)
a.plot(t[w] * 1e3, Fl['V(bus1,g1)'][w], color=C1, lw=0.8, label='ch1 bus (raw)')
a.plot(t[w] * 1e3, Fl['V(vbf1)'][w], color=C1, ls='--', lw=1, label='ch1 bus as the ESC sees it (3 kHz)')
a.plot(t[w] * 1e3, Fl['V(v5fc)'][w], color=C4, label='5 V rail at FC')
a.plot(t[w] * 1e3, 10 * Fl['V(en1)'][w], color=INK2, lw=0.8, label='ESC 1 enable x10')
for x, s in ((H.TOFF + hu['t_uvlo'], 'hand: UVLO'), (H.TOFF + hu['t_rail'], 'hand: BEC off')):
    a.axvline(x * 1e3, color=INK, lw=0.7, ls=':'); a.text(x * 1e3 + 0.05, 15.6, s, color=INK, fontsize=7.5, rotation=90, va='top')
a.axhline(hu['Vll'], color=C2, lw=0.7, ls=':'); a.text(19.5, hu['Vll'] + 0.25, 'motor-1 back-EMF (l-l peak)', color=C2, fontsize=7.5, ha='center')
style(a, 'H. Pack 1 pulled at 16 ms: ESC 1 hold-up, then the 5 V rail dies', 'V')
a.legend(frameon=False, fontsize=7.5, loc='upper right'); a.set_ylim(0, 16)

fig.tight_layout(rect=(0, 0, 1, 0.98))
fig.savefig(os.path.join(here, 'FullSystem_results.png'), dpi=120)

# ---------------- extra metrics that a .meas cannot give directly ----------------
t = P.t
for k in (1, 2, 3):
    vb = P[f'V(bus{k},g{k})']; ib = P[f'I(Lpos{k})']; Vb = H.VB[k - 1]
    m = t < H.TARM
    t10 = np.interp(0.1 * Vb, vb[m], t[m]); t90 = np.interp(0.9 * Vb, vb[m], t[m])
    ex[f'iavg_ramp{k}'] = float(win(t, ib, t10, t90))
    ex[f'ipk_contact{k}'] = float(np.abs(ib[(t > H.TON[k-1]) & (t < H.TON[k-1] + 0.2e-3)]).max())
    ex[f't_ramp{k}'] = float(t90 - t10)
    vgs = P[f'V(gt{k},s{k})']
    ex[f'vgs_kick{k}'] = float(vgs[(t > H.TON[k-1]) & (t < H.TON[k-1] + 0.5e-3)].max() - vgs[t < H.TON[k-1]].max())
t = Fl.t
for k in (1, 2, 3):
    tu, vb = pwm_avg(t, Fl[f'V(bus{k},g{k})'], 4e-3, 8e-3, dt=0.1e-6)
    ex[f'vrip_avg{k}'] = float(vb.max() - vb.min())
ex['isig2_rms_ss'] = float(np.sqrt(win(t, Fl['I(Lsig2)'] ** 2, 4e-3, 8e-3)))
ex['isig3_rms_ss'] = float(np.sqrt(win(t, Fl['I(Lsig3)'] ** 2, 4e-3, 8e-3)))
ex = {k: v for k, v in ex.items() if v is not None}
json.dump(ex, open(os.path.join(here, 'extra_metrics.json'), 'w'), indent=1)
print(json.dumps(ex, indent=1))
