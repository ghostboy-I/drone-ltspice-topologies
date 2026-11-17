"""Hand calculations for topology 08: redundant avionics power from three floating packs.
Shared by gen_schematic.py (every component value comes from here), plot_results.py and make_design_doc.py.

Five architectures (.step param Case):
  0  + rail ideal-diode OR only           BEC return reaches the packs only through the 26 AWG signal grounds
  1  + and - rail ideal-diode OR          an ideal diode in each return wire as well (signal grounds still present)
  2  + rail ideal-diode OR + star return  a plain 18 AWG return wire from the power board to each ESC ground (recommended)
  3  same as 2 with Schottky diodes       for the forward-drop / loss comparison
  4  isolated DC-DC per pack              three isolated 5 V modules, outputs ideal-diode OR'ed on the 5 V rail
"""
import math, importlib.util, os
import numpy as np

here = os.path.dirname(os.path.abspath(__file__))
def _load(name, rel):
    spec = importlib.util.spec_from_file_location(name, os.path.join(here, "..", rel, "hand_calc.py"))
    m = importlib.util.module_from_spec(spec); spec.loader.exec_module(m); return m
h04 = _load("h04", "04_Three-Channel_Power_Transmission")        # packs, harnesses, ESC operating points
h06 = _load("h06", "06_BEC_Synchronous_Buck_5V")                 # the BEC

CASES = ["+ OR only (ideal diodes)", "+ and - OR (ideal diodes)", "+ OR + star return (ideal)",
         "+ OR + star return (Schottky)", "isolated DC-DC per pack"]
SHORT = ["+OR only", "+/- OR", "+OR + star", "Schottky + star", "isolated"]

# ---------------- packs, harnesses, ESC loads (topology 04, Case 1: 470 uF bulk at each ESC) ----------------
Rbatt = h04.Rbatt
VB = [c["Vb"] for c in h04.CH]
RH = [h04.harness(c)[0] for c in h04.CH]                        # harness loop resistance (+ and - conductor)
LH = [h04.harness(c)[1] for c in h04.CH]
PESC = [h04.op_point(c)["P"] for c in h04.CH]                   # ESC input power at the 04 operating point (W)
P1_PUNCH = 365.0                                                # ESC 1 punch: ~25 A from a sagging bus
Rsig, Lsig = h04.Rsig, 200e-9                                   # 20 cm of 26 AWG signal ground, ESC -> flight controller

# ---------------- taps from each ESC's power pads to the avionics power board ----------------
R_AWG18, r18, s_tap, len_tap = 20.95e-3, 0.512e-3, 2.5e-3, 0.15
Rtap = R_AWG18 * len_tap + 1e-3                                 # per conductor: 15 cm of 18 AWG + small connector
Ltap = h04.mu0 / math.pi * math.log(s_tap / r18) * len_tap / 2  # half of the pair's loop inductance per conductor
Rret, Lret = Rtap, Ltap                                         # the return (star) wire is the same 18 AWG

# ---------------- ideal-diode controller (LM74700-style, representative values) ----------------
Vreg = 20e-3          # forward regulation target V_AK
Vrev = -11e-3         # reverse comparator threshold
Ichg = 2.7e-3         # gate charge-pump current (slow turn-on)
Ipd = 2.4             # gate pull-down current on reverse (fast turn-off)
Vlin = 50e-3          # regulation amplifier: gm = Ichg/Vlin into the gate capacitance (an integrator)
Tsense = 0.3e-6       # comparator response, modelled as a first-order lag on V_AK
# OR FET: 40 V, ~2.7 mOhm fully on
FET = dict(Rd=1e-3, Rs=0.5e-3, Vto=2.0, Kp=100.0, Cgs=2.5e-9, BV=40.0)
def rds(vgs): return FET["Rd"] + FET["Rs"] + 1 / (FET["Kp"] * max(vgs - FET["Vto"], 1e-6))
RDS_ON = rds(11.0)
# Schottky for comparison: 3 A / 40 V class
SCH = dict(Is=5e-6, N=1.05, Rs=30e-3, Cjo=300e-12, BV=40.0)
Vt = 0.025865                                                   # kT/q at 27 C
def vf_schottky(i): return SCH["N"] * Vt * math.log(i / SCH["Is"] + 1) + i * SCH["Rs"] if i > 0 else 0.0
def vf_ideal(i): return max(Vreg, i * RDS_ON) if i > 0 else 0.0

# ---------------- BEC (06), as an averaged model ----------------
Vout = h06.Vout_set; Iload = 3.0
P_DCR = Iload ** 2 * h06.DCR
P_FET = 0.33          # 06's switching measurement: 0.46 W total loss at 3 A, minus the 0.135 W DCR loss the averaged model has
P_BEC = Vout * Iload + P_DCR + P_FET                            # BEC input power
Cin = h06.Cin

# ---------------- isolated modules (Case 4) ----------------
VSET = [5.025, 5.000, 4.975]   # +-0.5 % trim tolerance
Rdroop, Leq, Cmo, ESRmo = 50e-3, 1e-6, 47e-6, 20e-3
ETA_ISO = 0.85

# ================= 1. which pack supplies the BEC? =================
def vret(case, I):
    """Voltage from the FC/BEC ground down to the ESC ground g_k when the BEC return current I flows to channel k."""
    if case in (0, 4): return I * Rsig
    if case in (2, 3): return I * Rsig * Rret / (Rsig + Rret)
    # case 1: the return ideal diode (20 mV regulated + wire) sits in parallel with the signal ground
    if I * Rsig <= Vreg: return I * Rsig
    Id = (I * Rsig - Vreg) / (Rsig + Rret)
    return Vreg + Id * Rret

def share(case, pesc, pbec=P_BEC, tol=1e-12, alive=(1, 1, 1)):
    """Solve the OR: each pack k delivers I_k >= 0 such that every conducting path ends at the same vin
    (vin measured against the FC ground). Constant-power ESC and BEC loads, so iterate."""
    vf = vf_schottky if case == 3 else vf_ideal
    iesc = [p / v for p, v in zip(pesc, VB)]
    for _ in range(60):
        def path_v(k, I):    # vin reached through pack k carrying BEC current I
            return VB[k] - (iesc[k] + I) * (Rbatt + RH[k]) - I * Rtap - vf(I) - vret(case, I)
        def I_at(k, vin):    # invert path_v (monotonic) by bisection; 0 if the diode is off
            if not alive[k] or path_v(k, 1e-9) <= vin: return 0.0
            lo, hi = 1e-9, 200.0
            for _ in range(100):
                mid = (lo + hi) / 2
                (lo, hi) = (mid, hi) if path_v(k, mid) > vin else (lo, mid)
            return (lo + hi) / 2
        lo, hi = 5.0, max(VB)
        for _ in range(100):
            vin = (lo + hi) / 2
            tot = sum(I_at(k, vin) for k in range(3))
            (lo, hi) = (vin, hi) if tot > pbec / vin else (lo, vin)
        I = [I_at(k, vin) for k in range(3)]
        vbus = [VB[k] - (iesc[k] + I[k]) * (Rbatt + RH[k]) for k in range(3)]
        iesc_new = [p / v for p, v in zip(pesc, vbus)]
        if max(abs(a - b) for a, b in zip(iesc, iesc_new)) < tol: break
        iesc = iesc_new
    return dict(I=I, vin=vin, vbus=vbus, iesc=iesc, ibec=pbec / vin)

# ================= 2. ground currents: nodal analysis of the ground network =================
def ground_nodal(case, Ibec_k, iesc, tie=False):
    """DC nodal analysis. Nodes g1..g3 (ESC grounds), bn1..bn3 (pack negatives), tie; FC ground = reference.
    Injections: ESC k sinks iesc_k into g_k; the BEC returns sum(I_k) into the FC ground; pack k takes iesc_k + I_k
    out of bn_k. The case-1 return ideal diodes are piecewise: off, or a 20 mV source behind Rret (Norton form)."""
    names = ["g1", "g2", "g3", "bn1", "bn2", "bn3", "tie"]; idx = {n: i for i, n in enumerate(names)}
    on = [True] * 3
    for _ in range(10):
        G = np.zeros((7, 7)); J = np.zeros(7)
        def r(a, b, R):
            g = 1 / R
            for p, q in ((a, b), (b, a)):
                if p != "fc": G[idx[p], idx[p]] += g
                if p != "fc" and q != "fc": G[idx[p], idx[q]] -= g
        for k in range(3):
            r(f"g{k+1}", f"bn{k+1}", RH[k] / 2); r(f"g{k+1}", "fc", Rsig)
            r(f"bn{k+1}", "tie", 1e-3 if tie else 1e9)
            if case in (2, 3): r(f"g{k+1}", "fc", Rret)
            if case == 1 and on[k]:          # fc --(+Vreg drop)-- Rret -- g_k  : source pushes Vreg/Rret out of g_k
                r(f"g{k+1}", "fc", Rret); J[idx[f"g{k+1}"]] -= Vreg / Rret
            J[idx[f"g{k+1}"]] += iesc[k]; J[idx[f"bn{k+1}"]] -= iesc[k] + Ibec_k[k]
        J_fc = sum(Ibec_k)   # enters the reference node: implied by KCL
        v = np.linalg.solve(G, J)
        Isig = [-v[idx[f"g{k+1}"]] / Rsig for k in range(3)]          # + = from FC ground toward the ESC
        Idn = [(-v[idx[f"g{k+1}"]] - Vreg) / Rret if (case == 1 and on[k]) else 0.0 for k in range(3)]
        new = [(-v[idx[f"g{k+1}"]] > Vreg) if case == 1 else False for k in range(3)]
        if case != 1 or new == on: break
        on = new
    Iret = [(-v[idx[f"g{k+1}"]]) / Rret if case in (2, 3) else Idn[k] for k in range(3)]
    return dict(Isig=Isig, Iret=Iret, vg=[v[idx[f"g{k+1}"]] for k in range(3)])

# ================= 3. isolated modules: droop sharing behind ideal diodes =================
def iso_share(vset=VSET, Iload=Iload):
    on = [True] * 3
    for _ in range(5):
        n = sum(on)
        vout = (sum(v - Vreg for v, o in zip(vset, on) if o) - Iload * Rdroop) / n
        I = [(v - Vreg - vout) / Rdroop if o else 0.0 for v, o in zip(vset, on)]
        on2 = [i > 0 for i in I]
        if on2 == on: break
        on = on2
    vmo = [v - i * Rdroop for v, i in zip(vset, I)]
    pin = [vm * i / ETA_ISO for vm, i in zip(vmo, I)]
    return dict(vout=vout, I=I, pin=pin, vmo=vmo)

# ================= 4. switchover and reverse current =================
def unplug_handover(sh):
    """Pack 1 unplugged: ESC 1's 480 uF keeps bus 1 up; packs 2/3 take over once bus 1 has fallen to their level."""
    C = h04.Ccer + h04.Cbulk
    I = sh["iesc"][0] + sh["I"][0]
    sh_after = share(2, [0, PESC[1], PESC[2]], alive=(0, 1, 1))    # vin with pack 1 gone
    dV = (sh["vbus"][0] - sh["I"][0] * Rtap) - (sh_after["vin"] + Vreg)
    return dict(C=C, I=I, dV=dV, t=C * dV / I, vin_after=sh_after["vin"], I_after=sh_after["I"])

def holdup(C, V0, Vmin=5.5, P=P_BEC):
    """Constant-power hold-up time from a capacitor alone (no pack left): energy / power."""
    return C * (V0 ** 2 - Vmin ** 2) / (2 * P)

R_SHORT = 5e-3   # the fault: bus 2 shorted through 5 mOhm (closes in 50 ns)
def short_reverse(case, V0, I0):
    """Bus 2 shorted while ideal diode 2 conducts I0 in regulation. The BEC input capacitor drives a reverse current
    through the still-on FET, the + tap and the return path. The short is not 0 V: pack 2 pushes ~480 A through the
    5 mOhm fault, so V_drive = V0 - V_short. In regulation the FET is barely on, Rds = Vreg/I0, so the raw V_AK ramps down
    at k = Rds*di/dt; the comparator sees it through the lag tau and fires when the filtered value has fallen
    Vreg - Vrev = 31 mV. For a ramp into a first-order lag: k*(t - tau*(1 - exp(-t/tau))) = 31 mV  ->  t ~ sqrt(2*tau*31mV/k)."""
    Lret_path = Lsig if case in (0, 1) else Lsig * Lret / (Lsig + Lret)
    L = Ltap + Lret_path + 0.5e-9
    Vshort = VB[1] / (Rbatt + RH[1] + R_SHORT) * R_SHORT
    didt = (V0 - Vshort) / L
    Rds_reg = Vreg / I0
    k = Rds_reg * didt
    D = Vreg - Vrev
    lo, hi = 0.0, 10 * Tsense
    for _ in range(200):
        t = (lo + hi) / 2
        (lo, hi) = (t, hi) if k * (t - Tsense * (1 - math.exp(-t / Tsense))) < D else (lo, t)
    t_det = (lo + hi) / 2
    Ipk = didt * t_det - I0
    Q = didt * t_det ** 2 / 2 - I0 * t_det          # net charge pulled back out of vin during detection
    return dict(L=L, Vshort=Vshort, didt=didt, Rds_reg=Rds_reg, t_det=t_det, t_approx=math.sqrt(2 * Tsense * D / k),
                Ipk=Ipk, Q=Q, E=0.5 * L * Ipk ** 2)

def vin_dip_after_short(I3_before, I3_after, Q_rev):
    """After diode 2 opens, pack 3 must pick up pack 2's share at once. The new current has to build up in the tap
    inductance (ESC 3's 480 uF sits at the far end, so pack 3's own harness is out of the picture): a current step
    into an L-C dips the capacitor by about dI*sqrt(L/C). The charge the reverse pulse pulled out of Cin adds Q/C."""
    L = Ltap + Lsig * Lret / (Lsig + Lret)
    return (I3_after - I3_before) * math.sqrt(L / Cin) + Q_rev / Cin

if __name__ == "__main__":
    print(f"Rtap={Rtap*1e3:.2f} mOhm  Ltap={Ltap*1e9:.1f} nH  RDS_on={RDS_ON*1e3:.2f} mOhm  P_BEC={P_BEC:.3f} W  PESC={[round(p,2) for p in PESC]}")
    for case in range(4):
        for lab, pesc in (("normal", PESC), ("punch", [P1_PUNCH, PESC[1], PESC[2]])):
            s = share(case, pesc)
            g = ground_nodal(case, s["I"], s["iesc"])
            print(f"case {case} {lab:6s} vin={s['vin']:.4f} I={[round(i,4) for i in s['I']]} Isig={[round(i,4) for i in g['Isig']]} Iret={[round(i,4) for i in g['Iret']]}")
    s = share(2, PESC); print("tie (04 loop) with + OR:", ground_nodal(0, s["I"], s["iesc"], tie=True)["Isig"])
    print("iso", iso_share())
    print("unplug", unplug_handover(share(2, PESC)))
    print("holdup 10u", holdup(Cin, 14.77))
    ua = unplug_handover(share(2, PESC))
    for c in (0, 2): print("short", c, short_reverse(c, ua["vin_after"], ua["I_after"][1]))
    print("Vf ideal 1A", vf_ideal(1.04), "schottky", vf_schottky(1.04))
