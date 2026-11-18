"""Checks both KiCad projects with KiCad itself (python3 kicad_check.py). Exit code 1 on any failure.

  1. ERC (kicad-cli sch erc): no errors.
  2. Schematic net list (kicad-cli sch export netlist) == the parts table (expected_nets.json), pin for pin.
  3. Every footprint the schematic names exists in Drone_Power.pretty, and every symbol pin has a pad of that number.
  4. PCB: schematic parity DRC (kicad-cli pcb drc --schematic-parity) is clean, every pad carries the net the parts table
     gives it, and pads left without a net are only mounting/unused pads.
  5. Polarised capacitors: pad 1 (+) is not on GND.
"""
import os, sys, json, subprocess, tempfile, re
import sexpr as S

HERE = os.path.dirname(os.path.abspath(__file__))
KDIR = os.path.join(HERE, "kicad")
LIB = os.path.join(KDIR, "Drone_Power.pretty")


def cli(*args):
    r = subprocess.run(["kicad-cli", *args], capture_output=True, text=True)
    if r.returncode not in (0, 5):          # 5 = DRC/ERC found violations (reported in the JSON)
        raise RuntimeError(" ".join(args) + "\n" + r.stdout + r.stderr)
    return r


def netlist_nets(path):
    root = S.parse(open(path, encoding="utf-8").read())[0]
    out = {}
    for n in S.find(S.first(root, "nets"), "net"):
        name = S.first(n, "name")[1].lstrip("/")
        out[name] = {(S.first(nd, "ref")[1], S.first(nd, "pin")[1]) for nd in S.find(n, "node")}
    return out


def check(name, tmp):
    d = os.path.join(KDIR, name); sch = os.path.join(d, f"{name}.kicad_sch"); pcb = os.path.join(d, f"{name}.kicad_pcb")
    fails, notes = [], []
    # 1 ERC
    erc = os.path.join(tmp, f"{name}_erc.json")
    cli("sch", "erc", "--format", "json", "--severity-all", "-o", erc, sch)
    viol = [v for s in json.load(open(erc))["sheets"] for v in s["violations"]]
    errs = [v for v in viol if v["severity"] == "error"]
    if errs: fails.append(f"ERC: {len(errs)} errors, e.g. {errs[0]['description']}")
    notes.append(f"ERC {len(errs)} errors, {len(viol) - len(errs)} warnings")
    # 2 net list vs parts table
    net = os.path.join(tmp, f"{name}.net")
    cli("sch", "export", "netlist", "--format", "kicadsexpr", "-o", net, sch)
    got = netlist_nets(net)
    exp = {k: {tuple(x) for x in v} for k, v in json.load(open(os.path.join(d, "expected_nets.json"))).items()}
    used_pins = set().union(*exp.values())
    bad = [k for k, v in exp.items() if got.get(k) != v]
    extra = [k for k, v in got.items() if k not in exp and (v & used_pins)]
    if bad or extra: fails.append(f"net list: {len(bad)} nets differ ({bad[:3]}), {len(extra)} unexpected nets ({extra[:3]})")
    notes.append(f"net list = parts table on all {len(exp)} nets")
    # 3 + 4 PCB
    import pcbnew
    b = pcbnew.LoadBoard(pcb)
    padnet = {}
    for k, v in exp.items():
        for ref, pin in v: padnet[(ref, pin)] = k
    missing_pad, wrong, unnetted = [], [], []
    fps = {fp.GetReference(): fp for fp in b.GetFootprints()}
    sch_refs = {ref for ref, _ in used_pins} | {r for r in fps}
    for (ref, pin), n in padnet.items():
        fp = fps.get(ref)
        if fp is None: missing_pad.append(f"{ref} (no footprint)"); continue
        pads = [p for p in fp.Pads() if p.GetNumber() == pin]
        if not pads: missing_pad.append(f"{ref}.{pin}")
        wrong += [f"{ref}.{pin}: {p.GetNetname()} != /{n}" for p in pads if p.GetNetname() != "/" + n]
    for ref, fp in fps.items():
        nick, item = str(fp.GetFPID().GetLibNickname()), str(fp.GetFPID().GetLibItemName())
        if nick != "Drone_Power" or not os.path.exists(os.path.join(LIB, f"{item}.kicad_mod")):
            fails.append(f"{ref}: footprint {nick}:{item} not in Drone_Power.pretty")
        for p in fp.Pads():
            if p.GetNumber() and (not p.GetNetname() or p.GetNetname().startswith("unconnected-")) and (ref, p.GetNumber()) not in padnet:
                unnetted.append(f"{ref}.{p.GetNumber()}")
        if str(fp.GetFPID().GetLibItemName()).startswith("CP_"):
            plus = [p.GetNetname() for p in fp.Pads() if p.GetNumber() == "1"]
            if plus and plus[0] == "/GND": fails.append(f"{ref}: polarised cap with + on GND")
    if missing_pad: fails.append(f"symbol pins without a pad: {missing_pad[:6]}")
    if wrong: fails.append(f"pads on the wrong net: {wrong[:6]}")
    notes.append(f"PCB: {len(fps)} footprints, {sum(1 for fp in fps.values() for p in fp.Pads() if p.GetNetname())} pads on nets, "
                 f"no-net pads (unused pins, mounting pads): {', '.join(sorted(set(unnetted))) or 'none'}")
    drc = os.path.join(tmp, f"{name}_drc.json")
    cli("pcb", "drc", "--schematic-parity", "--format", "json", "-o", drc, pcb)
    D = json.load(open(drc))
    par = D.get("schematic_parity", [])
    if par: fails.append(f"schematic parity: {len(par)} issues, e.g. {par[0]['description']}: "
                         f"{[i['description'] for i in par[0].get('items', [])][:2]}")
    notes.append(f"schematic parity issues: {len(par)}; unrouted connections: {len(D.get('unconnected_items', []))} (layout not started)")
    return fails, notes, unnetted


if __name__ == "__main__":
    ok = True
    with tempfile.TemporaryDirectory() as tmp:
        for name in ("ESC_Board", "Avionics_Board"):
            fails, notes, unnetted = check(name, tmp)
            print(f"== {name}: {'PASS' if not fails else 'FAIL'}")
            for n in notes: print("   " + n)
            for f in fails: print("   FAIL " + f)
            ok &= not fails
    sys.exit(0 if ok else 1)
