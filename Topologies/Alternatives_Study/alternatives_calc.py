"""Hand calculations for the parts-alternatives study (python3 alternatives_calc.py).

Every alternative is judged at the operating points of topology 09 (hover and throttle punch of one U15XL on 24S),
with ONE loss method applied to every part, so the comparison is fair. All device numbers are datasheet typicals
(sources in README.md); the assumptions are named where they are made."""
import math, os, importlib.util

HERE = os.path.dirname(os.path.abspath(__file__))
_spec = importlib.util.spec_from_file_location(
    "hand_calc_09", os.path.join(HERE, "..", "09_24S_FOC_Drive_Low-Voltage_Rails", "hand_calc.py"))
h09 = importlib.util.module_from_spec(_spec); _spec.loader.exec_module(h09)

FSW = h09.Fsw                     # 20 kHz PWM
HOT_SI, HOT_GAN = 1.6, 1.5        # ASSUMED Rds(on) factor at Tj ~ 110 C (OptiMOS / eGaN normalised curves)


def op_points():
    out = {}
    for name, fn in (("hover", h09.hover), ("punch", h09.punch)):
        r = fn(); mp = r["mp"]
        out[name] = dict(iq=mp["iq"], vbus=r["vbus"], vd=mp["vd"], vq=mp["vq"], icap=r["icap"],
                         p_el=mp["p_el"], m09=mp["inv"])
    return out


# ---------------------------------------------------------------------------------------------------- 1. inverter FETs
# name: package, n per switch, Rds typ 25C (ohm), Qg, Qsw, Qoss(75 V), Qrr (C, at the datasheet's own condition), Rg int,
#       Vplateau, Vsd in dead time, drive volts, driver pull-up / pull-down (ohm), external gate R per FET, dead time
LTC7063 = dict(vdrv=10.0, rup=1.5, rdn=0.8, rgx=10.0, tdead=300e-9)      # the design today (DRVSET 10 V, 10 ohm per FET)
FETS = {
    "IPB065N15N3 G (today)": dict(pkg="TO-263-2 (D2PAK)", n=4, rds=5.2e-3, rds_max=6.5e-3, qg=70e-9, qsw=25e-9,
                                  qoss=179e-9, qrr=478e-9, qrr_at="130 A, 100 A/us", rg=2.3, vpl=5.5, vsd=0.9,
                                  area=10.2 * 15.4, **LTC7063),
    "IPB065N15N3 G, 3.3 ohm Rg": dict(pkg="TO-263-2 (D2PAK)", n=4, rds=5.2e-3, rds_max=6.5e-3, qg=70e-9, qsw=25e-9,
                                  qoss=179e-9, qrr=478e-9, qrr_at="130 A, 100 A/us", rg=2.3, vpl=5.5, vsd=0.9,
                                  area=10.2 * 15.4, **dict(LTC7063, rgx=3.3)),
    "IPB060N15N5": dict(pkg="TO-263-7", n=4, rds=4.8e-3, rds_max=6.0e-3, qg=54.5e-9, qsw=18.9e-9, qoss=153e-9,
                        qrr=60e-9, qrr_at="68 A, 100 A/us", rg=0.9, vpl=5.7, vsd=0.9, area=10.2 * 15.4, **LTC7063),
    "IPB044N15N5": dict(pkg="TO-263-7", n=4, rds=3.4e-3, rds_max=4.4e-3, qg=80e-9, qsw=27e-9, qoss=225e-9,
                        qrr=42e-9, qrr_at="87 A, 100 A/us", rg=0.8, vpl=5.6, vsd=0.9, area=10.2 * 15.4, **LTC7063),
    "IPT039N15N5": dict(pkg="TOLL (HSOF-8)", n=3, rds=3.3e-3, rds_max=3.9e-3, qg=78e-9, qsw=24e-9, qoss=219e-9,
                        qrr=77.2e-9, qrr_at="50 A, 100 A/us", rg=1.1, vpl=5.3, vsd=0.9, area=10.0 * 11.7, **LTC7063),
    "IPT025N15NM6": dict(pkg="TOLL (HSOF-8)", n=2, rds=2.1e-3, rds_max=2.5e-3, qg=105e-9, qsw=38e-9, qoss=310e-9,
                         qrr=184e-9, qrr_at="60 A, 500 A/us", rg=1.06, vpl=5.4, vsd=0.9, area=10.0 * 11.7, **LTC7063),
    # GaN: 5 V drive. ASSUMED driver: LMG1210-class 200 V half-bridge GaN driver, 1.5 A / 3 A at 5 V -> ~3.3 / 1.7 ohm;
    # 2 ohm per FET; dead time cut to 50 ns because GaN reverse conduction drops ~Vth + I R (about 2.5 V), not 0.9 V.
    "EPC2305 (GaN)": dict(pkg="QFN 3 x 5 mm", n=3, rds=2.2e-3, rds_max=3.0e-3, qg=22e-9, qsw=2.1e-9 + 6.6e-9 - 4.6e-9,
                          qoss=103e-9, qrr=0.0, qrr_at="none (no body diode)", rg=0.5, vpl=2.5, vsd=2.5,
                          area=3.0 * 5.0, vdrv=5.0, rup=3.3, rdn=1.7, rgx=2.0, tdead=50e-9, gan=True),
}


def inverter_loss(f, iq, vbus):
    """Three-phase two-level inverter, sinusoidal phase current of amplitude iq, n FETs in parallel per switch.
      conduction  3 (iq^2/2) R/n                     (each phase's current always flows through one switch)
      switching   3 * 1/2 Vbus <|i|> (t_on + t_off) fsw,  t = Qsw (Rg_ext + Rg_int + n R_drv) / (V across the gate R)
      Qoss        3 n Qoss Vbus fsw                   (one hard turn-on per phase per period: Eoss(own) + Qoss V - Eoss(other))
      Qrr         3 n Qrr Vbus fsw                    (the recovering body diode's charge is pulled through at full Vbus)
      dead time   3 * 2 tdead fsw Vsd <|i|>
      gate        6 n Qg Vdrv fsw                     (from the 12 V aux supply, burnt in the gate resistors and driver)"""
    n = f["n"]; hot = HOT_GAN if f.get("gan") else HOT_SI
    iabs = 2 / math.pi * iq
    cond = 1.5 * iq ** 2 * f["rds"] * hot / n
    t_on = f["qsw"] * (f["rgx"] + f["rg"] + n * f["rup"]) / (f["vdrv"] - f["vpl"])
    t_off = f["qsw"] * (f["rgx"] + f["rg"] + n * f["rdn"]) / f["vpl"]
    sw = 1.5 * vbus * iabs * (t_on + t_off) * FSW
    oss = 3 * n * f["qoss"] * math.sqrt(vbus / 75) * vbus * FSW       # Qoss ~ sqrt(V) above a few volts
    rr = 3 * n * f["qrr"] * vbus * FSW
    dead = 6 * f["tdead"] * FSW * f["vsd"] * iabs
    gate = 6 * n * f["qg"] * f["vdrv"] * FSW
    tot = cond + sw + oss + rr + dead
    return dict(cond=cond, sw=sw, oss=oss, rr=rr, dead=dead, total=tot, gate=gate, t_on=t_on, t_off=t_off,
                per_fet=tot / (6 * n))


# ---------------------------------------------------------------------------------------------------- 2. DC link
CAP_N, CAP_RIPPLE, CAP_ESR = 16, 3.5, 20e-3        # 16 x 150 uF 125 V hybrid polymer, 3.5 A each (spec), ESR 20 mohm
K_FREQ = 0.8                                       # ASSUMED ripple multiplier at 20-40 kHz vs. the 100 kHz rating


def dc_link(icap):
    per = icap / CAP_N
    need = math.ceil(icap / (CAP_RIPPLE * K_FREQ))
    return dict(per=per, ratio=per / CAP_RIPPLE, p_each=per ** 2 * CAP_ESR, need=need)


# ---------------------------------------------------------------------------------------------------- 3. ESC aux supply
I12_ESC = 0.123                                     # topology 10 hand calc: gate drive + LDO loads at 12 V
AUX = {
    "LTC7801 + 2 FETs + BSP89 (today)": dict(eff=0.807, vmax=150, parts=14, note="topology 10 hand calc at 100.8 V"),
    "LM5169 (TI, 120 V abs max)": dict(eff=0.73, vmax=120, parts=6,
                                       note="TI Fig. 8-16, VOUT 12 V, VIN 100 V, 0.12 A, 500 kHz"),
    "LTC7138 (ADI, 140 V)": dict(eff=None, vmax=140, parts=7, note="400 mA, internal switch; efficiency not checked"),
}


# ---------------------------------------------------------------------------------------------------- 4. current sense
def shunt_loss(iq, r): return (iq / math.sqrt(2)) ** 2 * r


ACS770_RANGE, ACS772_RANGE = 200.0, 250.0


# ---------------------------------------------------------------------------------------------------- 5. avionics TVS
TVS = dict(vrwm=110, vbr_min=122, vc=177, ipp=3.4)   # SMBJ110A (Littelfuse)
LTC7801_VMAX = 150


def collect():
    ops = op_points()
    fets = {k: {op: inverter_loss(f, o["iq"], o["vbus"]) for op, o in ops.items()} for k, f in FETS.items()}
    links = {op: dc_link(o["icap"]) for op, o in ops.items()}
    aux = {k: dict(v, pin=(12 * I12_ESC / v["eff"]) if v["eff"] else None) for k, v in AUX.items()}
    return dict(ops=ops, fets=fets, links=links, aux=aux)


if __name__ == "__main__":
    c = collect()
    for op, o in c["ops"].items():
        print(f"{op}: iq {o['iq']:.1f} A  Vbus {o['vbus']:.2f} V  Icap_rms {o['icap']:.1f} A  "
              f"09 inverter model {o['m09']['total']:.1f} W")
    for k, d in c["fets"].items():
        f = FETS[k]
        for op in ("hover", "punch"):
            L = d[op]
            print(f"{k:24s} n={f['n']} {op:5s} cond {L['cond']:5.1f} sw {L['sw']:5.1f} oss {L['oss']:4.1f} "
                  f"rr {L['rr']:5.1f} dead {L['dead']:4.1f} | total {L['total']:6.1f} W  per FET {L['per_fet']:4.2f} W"
                  f"  gate {L['gate']:.2f} W  ton/toff {L['t_on']*1e9:.0f}/{L['t_off']*1e9:.0f} ns")
    for op, l in c["links"].items():
        print(f"DC link {op}: {l['per']:.2f} A per cap = {l['ratio']:.2f} x rating, {l['p_each']*1e3:.0f} mW each, "
              f"need {l['need']} caps at {CAP_RIPPLE * K_FREQ:.1f} A")
    for k, a in c["aux"].items():
        print(f"aux {k}: eff {a['eff']}  Pin {a['pin']}")
    for op, o in c["ops"].items():
        print(f"shunt 100 uohm {op}: {shunt_loss(o['iq'], 100e-6):.2f} W per phase; "
              f"ACS770 {o['iq']/ACS770_RANGE*100:.0f} % of range, ACS772-250B {o['iq']/ACS772_RANGE*100:.0f} %")
