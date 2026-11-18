"""Reusable drawn circuits."""


def ltc7801(s, ox, oy, rail, R, rail_label=None):
    """LTC7801 synchronous buck drawn around the chip at (ox, oy); the input rail runs at y=rail above it.
    R maps roles to reference designators. Returns the output point (end of the output rail)."""
    u = s.put(R["U"], ox, oy)
    net = lambda pin: s.T.info(R["U"])[3][pin]
    if rail_label: s.flag((ox - 784, rail), rail_label)
    s.wire((ox - 784, rail), (ox + 624, rail))
    s.wire(u["VIN"], (u["VIN"][0], rail))
    # RUN / OVLO dividers from the input rail
    _, b = s.two(R["Rrun_t"], (ox - 512, rail), "D"); s.wire(b, (ox - 512, u["RUN"][1]), u["RUN"])
    _, c = s.two(R["Rrun_b"], (ox - 512, u["RUN"][1]), "D"); s.gnd(c)
    _, b = s.two(R["Rov_t"], (ox - 672, rail), "D"); s.wire(b, (ox - 672, u["OVLO"][1]), u["OVLO"])
    _, c = s.two(R["Rov_b"], (ox - 672, u["OVLO"][1]), "D"); s.gnd(c)
    for pin in ("CPUMP_EN", "PGOOD"):
        s.wire(u[pin], (ox - 256, u[pin][1])); s.flag((ox - 256, u[pin][1]), net(pin))
    _, c = s.two(R["Rfreq"], u["FREQ"], "L"); s.gnd(c)
    for pin in ("MODE", "PLLIN"):
        s.wire(u[pin], (ox - 240, u[pin][1]))
        if net(pin) == "0": s.gnd((ox - 240, u[pin][1]))
        else: s.flag((ox - 240, u[pin][1]), net(pin))
    s.wire(u["SS"], (ox - 256, u["SS"][1])); _, c = s.two(R["Css"], (ox - 256, u["SS"][1]), "D"); s.gnd(c)
    s.wire(u["ITH"], (ox - 432, u["ITH"][1])); _, c = s.two(R["Cithb"], (ox - 320, u["ITH"][1]), "D"); s.gnd(c)
    _, b = s.two(R["Rith"], (ox - 432, u["ITH"][1]), "D"); _, c = s.two(R["Cith"], b, "D"); s.gnd(c)
    # INTVCC, EXTVCC
    top = u["INTVCC"][1] - 80
    s.wire(u["INTVCC"], (u["INTVCC"][0], top), (ox + 336, top)); s.flag((u["INTVCC"][0], top), net("INTVCC"))
    _, c = s.two(R["Cint"], (ox + 256, top), "D"); s.gnd(c)
    _, b = s.two(R["Rpg"], (ox + 336, top), "D"); s.flag(b, net("PGOOD"))
    s.wire(u["EXTVCC"], (u["EXTVCC"][0], u["EXTVCC"][1] - 40)); s.flag((u["EXTVCC"][0], u["EXTVCC"][1] - 40), net("EXTVCC"))
    # power stage
    q1 = s.put(R["Q1"], ox + 384, u["TG"][1] - 80); s.wire(u["TG"], q1["G"]); s.wire(q1["D"], (q1["D"][0], rail))
    q2 = s.put(R["Q2"], ox + 384, u["SW"][1]); s.wire(u["BG"], q2["G"]); s.gnd(q2["S"])
    sw = u["SW"][1]
    s.wire(u["SW"], (ox + 272, sw), q2["D"]); s.wire(q1["S"], q2["D"]); s.flag((ox + 448, sw), net("SW"))
    s.wire(u["BOOST"], (ox + 272, u["BOOST"][1])); _, c = s.two(R["Cboost"], (ox + 272, u["BOOST"][1]), "D"); s.wire(c, (ox + 272, sw))
    s.wire(q2["D"], (ox + 528, sw)); _, sns = s.two(R["L"], (ox + 528, sw), "R")
    s.wire(sns, (ox + 688, sw)); _, o = s.two(R["Rsense"], (ox + 688, sw), "R")
    s.wire(u["SENSE+"], (ox + 608, u["SENSE+"][1]), (ox + 608, sw))
    s.wire(u["SENSE-"], (ox + 768, u["SENSE-"][1]), (ox + 768, sw))
    _, c = s.two(R["Csense"], (ox + 608, u["SENSE+"][1] - 64), "R"); s.wire(c, (ox + 768, u["SENSE+"][1] - 64))
    end = (ox + 864 + 96 * len(R["Couts"]) + 288, sw)
    s.wire(o, end); s.flag(end, net("SENSE-"))
    for i, r in enumerate(R["Couts"]):
        _, c = s.two(r, (ox + 864 + 96 * i, sw), "D"); s.gnd(c)
    xf = ox + 864 + 96 * len(R["Couts"]) + 96
    _, b = s.two(R["Rfb_t"], (xf, sw), "D"); s.wire(b, (xf, u["VFB"][1])); s.wire(u["VFB"], (xf, u["VFB"][1]))
    _, c = s.two(R["Rfb_b"], (xf, u["VFB"][1]), "D"); s.gnd(c)
    s.wire(u["DRVSET"], (ox + 336, u["DRVSET"][1])); _, c = s.two(R["Rdrvset"], (ox + 336, u["DRVSET"][1]), "D"); s.gnd(c)
    s.wire(u["DRVUV"], (ox + 256, u["DRVUV"][1]))
    if net("DRVUV") == "0": s.gnd((ox + 256, u["DRVUV"][1]))
    else: s.flag((ox + 256, u["DRVUV"][1]), net("DRVUV"))
    for i, r in enumerate(R["Cins"]):
        x = ox + 528 + 96 * i
        s.wire((x, rail), (x, rail + 16)); _, c = s.two(r, (x, rail + 16), "D"); s.gnd(c)
    # DRVCC pre-regulator from the input rail
    q3 = s.put(R["Q3"], u["NDRV"][0], u["NDRV"][1] + 80, "M0")
    s.wire(u["NDRV"], q3["G"]); s.wire(q3["D"], (q3["D"][0], q3["D"][1] - 32)); s.flag((q3["D"][0], q3["D"][1] - 32), net("VIN"))
    s.wire(q3["S"], (q3["S"][0], q3["S"][1] + 48), (u["DRVCC"][0], q3["S"][1] + 48), u["DRVCC"])
    s.wire((u["DRVCC"][0], u["DRVCC"][1] + 112), (ox + 64, u["DRVCC"][1] + 112)); _, c = s.two(R["Cdrv"], (ox + 64, u["DRVCC"][1] + 112), "D"); s.gnd(c)
    s.gnd(u["GND"])
    return end
