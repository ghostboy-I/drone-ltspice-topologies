"""Builds kicad/Drone_Power.pretty: every footprint the ESC board and the avionics board need, in one project library.

  python3 kicad_footprints.py

* Stock footprints are copied unchanged from KiCad 9's own libraries (same names), so the projects open on any machine.
* Four footprints are not in KiCad's libraries and are generated here from the manufacturers' drawings:
    Linear_UDC-18-2EP_3x4mm_P0.5mm                 LT8641 UDC package, ADI/LTC DWG 05-08-1956 Rev C (UDC20(18))
    Linear_HTSSOP-24-1EP_4.4x7.8mm_P0.65mm_EP2.74x3.25mm
                                                   LTC7801 FE package, LTC DWG 05-08-1771 Rev B, exposed pad variation AA
    SolderWire-8AWG_1x01_D4.2mm_OD7mm              motor phase lead pad (J2-J4), 8 AWG silicone wire
    AMASS_AS150_Pigtail_2x8AWG_P15mm               battery input (J1): the AS150's two 8 AWG pigtail leads
  Pad sizes are the "recommended solder pad layout" of each drawing; outline, silkscreen and courtyard follow the KiCad
  library conventions (0.12 mm silk, 0.05 mm courtyard, 0.25 mm courtyard clearance).
"""
import os, glob, shutil
import sexpr as S
from sexpr import Sym

HERE = os.path.dirname(os.path.abspath(__file__))
LIB = os.path.join(HERE, "kicad", "Drone_Power.pretty")
STOCK = "/usr/share/kicad/footprints"
LIBNAME = "Drone_Power"


# ------------------------------------------------------------------ s-expression building blocks
def _font(size=1.0, th=0.15):
    return [Sym("effects"), [Sym("font"), [Sym("size"), size, size], [Sym("thickness"), th]]]


def prop(k, v, x, y, layer, hide=False, size=1.0):
    n = [Sym("property"), k, v, [Sym("at"), x, y, 0], [Sym("layer"), layer]]
    if hide: n.append([Sym("hide"), Sym("yes")])
    return n + [_font(size, 0.15 if size >= 1 else 0.08)]


def line(x1, y1, x2, y2, layer, w):
    return [Sym("fp_line"), [Sym("start"), x1, y1], [Sym("end"), x2, y2],
            [Sym("stroke"), [Sym("width"), w], [Sym("type"), Sym("solid")]], [Sym("layer"), layer]]


def rect(x1, y1, x2, y2, layer, w):
    return [Sym("fp_rect"), [Sym("start"), x1, y1], [Sym("end"), x2, y2],
            [Sym("stroke"), [Sym("width"), w], [Sym("type"), Sym("solid")]], [Sym("fill"), Sym("no")], [Sym("layer"), layer]]


def circle(x, y, r, layer, w):
    return [Sym("fp_circle"), [Sym("center"), x, y], [Sym("end"), x + r, y],
            [Sym("stroke"), [Sym("width"), w], [Sym("type"), Sym("solid")]], [Sym("fill"), Sym("no")], [Sym("layer"), layer]]


def poly(pts, layer, w=0.1, fill=False):
    return [Sym("fp_poly"), [Sym("pts")] + [[Sym("xy"), x, y] for x, y in pts],
            [Sym("stroke"), [Sym("width"), w], [Sym("type"), Sym("solid")]], [Sym("fill"), Sym("yes" if fill else "no")],
            [Sym("layer"), layer]]


def text(t, x, y, layer, size=1.0):
    return [Sym("fp_text"), Sym("user"), t, [Sym("at"), x, y, 0], [Sym("layer"), layer], _font(size, 0.15 if size >= 1 else 0.08)]


def smd(num, x, y, w, h, rr=0.25, layers=("F.Cu", "F.Mask", "F.Paste")):
    return [Sym("pad"), num, Sym("smd"), Sym("roundrect"), [Sym("at"), x, y], [Sym("size"), w, h],
            [Sym("layers")] + list(layers), [Sym("roundrect_rratio"), rr]]


def tht(num, x, y, size, drill):
    return [Sym("pad"), num, Sym("thru_hole"), Sym("circle"), [Sym("at"), x, y], [Sym("size"), size, size],
            [Sym("drill"), drill], [Sym("layers"), "*.Cu", "*.Mask"], [Sym("remove_unused_layers"), Sym("no")]]


def footprint(name, descr, tags, attr, items, ref_y, val_y):
    return [Sym("footprint"), name, [Sym("version"), Sym("20241229")], [Sym("generator"), "kicad_footprints.py"],
            [Sym("generator_version"), "9.0"], [Sym("layer"), "F.Cu"], [Sym("descr"), descr], [Sym("tags"), tags],
            prop("Reference", "REF**", 0, ref_y, "F.SilkS"), prop("Value", name, 0, val_y, "F.Fab"),
            prop("Datasheet", "", 0, 0, "F.Fab", hide=True), prop("Description", descr, 0, 0, "F.Fab", hide=True),
            [Sym("attr")] + [Sym(a) for a in attr.split()]] + items + [[Sym("embedded_fonts"), Sym("no")]]


def r(v): return round(v, 4)


# ------------------------------------------------------------------ LT8641: UDC 20(18)-lead 3 x 4 mm QFN, two exposed pads
def udc18():
    """Top view, pin 1 top left. Lands from the 'recommended solder pad pitch and dimensions' of DWG 05-08-1956 Rev C:
    0.25 x 0.70 mm lands at 0.50 mm pitch; outer/inner land extents 3.50/2.10 mm across the 3 mm body and 4.50/3.10 mm
    across the 4 mm body, so land centres sit at x = +-1.40 and y = +-1.90. Pins 5 and 12 are removed.
    Exposed pads (both SW): 0.220 wide, 0.770 mm apart (centres), 22 = 0.356 long with its top edge 2.127 mm below the
    body's top edge, 21 = 0.400 long below it."""
    name = "Linear_UDC-18-2EP_3x4mm_P0.5mm"
    bw, bh, cx, cy, L, Wd = 3.0, 4.0, 1.40, 1.90, 0.70, 0.25
    pads = []
    side = [-1.25, -0.75, -0.25, 0.25, 0.75, 1.25]
    for i, y in enumerate(side):                       # pins 1-6 down the left side
        if i + 1 != 5: pads.append(smd(str(i + 1), -cx, y, L, Wd))
    for i, x in enumerate([-0.75, -0.25, 0.25, 0.75]):  # pins 7-10 along the bottom, left to right
        pads.append(smd(str(7 + i), x, cy, Wd, L))
    for i, y in enumerate(reversed(side)):             # pins 11-16 up the right side
        if 11 + i != 12: pads.append(smd(str(11 + i), cx, y, L, Wd))
    for i, x in enumerate([0.75, 0.25, -0.25, -0.75]):  # pins 17-20 along the top, right to left
        pads.append(smd(str(17 + i), x, -cy, Wd, L))
    ep22_top = -bh / 2 + 2.127
    ep22 = (0.0, r(ep22_top + 0.356 / 2), 0.220, 0.356)
    ep21 = (0.0, r(ep22[1] + 0.770), 0.220, 0.400)
    for num, (x, y, w, h) in (("22", ep22), ("21", ep21)):
        pads.append(smd(num, x, y, w, h, rr=0.5))
    hx, hy = bw / 2, bh / 2
    s, ext = 0.12, 0.11                               # silk width, silk offset outside the body
    sx, sy = hx + ext, hy + ext
    items = [  # silkscreen corners, clear of the lands; pin-1 mark at top left
        line(-sx, -sy, -1.1, -sy, "F.SilkS", s), line(1.1, -sy, sx, -sy, "F.SilkS", s), line(sx, -sy, sx, -1.6, "F.SilkS", s),
        line(-sx, sy, -1.1, sy, "F.SilkS", s), line(1.1, sy, sx, sy, "F.SilkS", s),
        line(-sx, sy, -sx, 1.6, "F.SilkS", s), line(sx, sy, sx, 1.6, "F.SilkS", s),
        poly([(-2.05, -1.25), (-2.30, -1.45), (-2.30, -1.05)], "F.SilkS", 0.12, fill=True),
        poly([(-hx + 0.75, -hy), (hx, -hy), (hx, hy), (-hx, hy), (-hx, -hy + 0.75)], "F.Fab", 0.1),
        rect(-2.0, -2.5, 2.0, 2.5, "F.CrtYd", 0.05), text("${REFERENCE}", 0, 0, "F.Fab", 0.6)]
    return name, footprint(name, "LT8641 UDC package: 20(18)-lead plastic QFN 3x4 mm, pins 5 and 12 removed, two exposed SW pads "
                           "(pins 21, 22). Land pattern from ADI/LTC DWG 05-08-1956 Rev C, recommended solder pad layout "
                           "(https://www.analog.com/media/en/technical-documentation/data-sheets/LT8641.pdf#page=24)",
                           "QFN UDC LT8641 Linear Analog", "smd", pads + items, -3.2, 3.2)


# ------------------------------------------------------------------ LTC7801: FE24 HTSSOP, exposed pad variation AA
def fe24():
    """Lands from LTC DWG 05-08-1771 Rev B: 0.45 x 1.05 mm at 0.65 mm pitch, outer/inner row extents 6.60/4.50 mm
    (centres at x = +-2.775); exposed pad land 3.25 mm along the body x 2.74 mm across (pin 25 = GND)."""
    name = "Linear_HTSSOP-24-1EP_4.4x7.8mm_P0.65mm_EP2.74x3.25mm"
    cx, L, Wd, p = 2.775, 1.05, 0.45, 0.65
    pads = []
    for i in range(12):
        y = r((i - 5.5) * p)
        pads.append(smd(str(i + 1), -cx, y, L, Wd))         # 1-12 down the left
        pads.append(smd(str(24 - i), cx, y, L, Wd))         # 24-13 down the right
    epw, eph = 2.74, 3.25
    pads.append(smd("25", 0, 0, epw, eph, rr=0.05, layers=("F.Cu", "F.Mask")))
    pw, ph = 1.12, 1.37                                      # 2 x 2 paste windows, ~69 % of the exposed pad
    for sx_ in (-1, 1):
        for sy_ in (-1, 1):
            pads.append(smd("", r(sx_ * epw / 4), r(sy_ * eph / 4), pw, ph, rr=0.2, layers=("F.Paste",)))
    hx, hy = 2.2, 3.9
    s = 0.12
    items = [line(-hx, -hy - 0.11, hx, -hy - 0.11, "F.SilkS", s), line(-hx, hy + 0.11, hx, hy + 0.11, "F.SilkS", s),
             line(-hx, -hy - 0.11, -3.3, -hy - 0.11, "F.SilkS", s),          # pin-1 side extension
             poly([(-hx + 1.0, -hy), (hx, -hy), (hx, hy), (-hx, hy), (-hx, -hy + 1.0)], "F.Fab", 0.1),
             rect(-3.55, -4.15, 3.55, 4.15, "F.CrtYd", 0.05), text("${REFERENCE}", 0, 0, "F.Fab", 0.8)]
    return name, footprint(name, "LTC7801 FE package: 24-lead plastic TSSOP 4.4 mm with exposed pad (variation AA). Land pattern "
                           "from LTC DWG 05-08-1771 Rev B, recommended solder pad layout; exposed pad 3.25 x 2.74 mm = GND (pin 25)",
                           "TSSOP HTSSOP FE24 LTC7801 Linear Analog", "smd", pads + items, -5.0, 5.0)


# ------------------------------------------------------------------ wire pads
D8, OD8, DRILL8, PAD8 = 4.2, 7.0, 5.1, 8.4      # 8 AWG silicone wire: conductor ~4.2 mm, insulation 7 mm; KiCad rule drill = D + 0.9


def wire8():
    name = "SolderWire-8AWG_1x01_D4.2mm_OD7mm"
    c = PAD8 / 2 + 0.5
    items = [tht("1", 0, 0, PAD8, DRILL8), circle(0, 0, OD8 / 2, "F.Fab", 0.1), circle(0, 0, PAD8 / 2 + 0.25, "F.SilkS", 0.12),
             rect(-c, -c, c, c, "F.CrtYd", 0.05), text("${REFERENCE}", 0, 0, "F.Fab", 1.0)]
    return name, footprint(name, "Soldered wire connection for one 8 AWG (8.4 mm2) silicone wire: conductor 4.2 mm, insulation 7 mm, "
                           "drill 5.1 mm (KiCad SolderWire rule: conductor + 0.9 mm). Motor phase lead.",
                           "connector wire 8AWG phase", "exclude_from_pos_files", items, -5.3, 5.3)


def as150():
    """AS150 anti-spark plug with its factory pigtail: the board end is two 8 AWG leads. Pad 1 = +, pad 2 = -.
    15 mm pitch leaves 6.6 mm copper-to-copper between the pads (100 V bus) and room for two 7 mm insulated leads."""
    name = "AMASS_AS150_Pigtail_2x8AWG_P15mm"
    P = 15.0
    c = PAD8 / 2 + 0.5
    items = [tht("1", 0, 0, PAD8, DRILL8), tht("2", P, 0, PAD8, DRILL8),
             circle(0, 0, OD8 / 2, "F.Fab", 0.1), circle(P, 0, OD8 / 2, "F.Fab", 0.1),
             circle(0, 0, PAD8 / 2 + 0.25, "F.SilkS", 0.12), circle(P, 0, PAD8 / 2 + 0.25, "F.SilkS", 0.12),
             text("+", 0, -5.6, "F.SilkS", 1.5), text("-", P, -5.6, "F.SilkS", 1.5),
             text("AS150 pigtail 2 x 8 AWG", P / 2, 5.6, "F.Fab", 0.8),
             rect(-c, -c - 2.0, P + c, c, "F.CrtYd", 0.05), text("${REFERENCE}", P / 2, 0, "F.Fab", 1.0)]
    return name, footprint(name, "AMASS AS150 anti-spark connector, PCB end of its pigtail: two 8 AWG solder pads, "
                           "pad 1 = + (VBUS), pad 2 = - (GND), 15 mm pitch",
                           "AMASS AS150 battery anti-spark 8AWG", "exclude_from_pos_files", items, -7.6, 7.6)


CUSTOM = dict(fn() for fn in (udc18, fe24, wire8, as150))
CUSTOM_NAMES = set(CUSTOM)


def used_footprints():
    """Footprint names (library:name) used by both boards, from their parts tables."""
    import esc, avionics
    out = {}
    for b in (esc.build(), avionics.build()):
        for p in b.parts:
            if p.sim: continue
            fp = (p.fp or "").split(" (")[0]
            if ":" not in fp: raise ValueError(f"{b.name} {p.ref}: no footprint ({p.fp!r})")
            out.setdefault(fp, []).extend(p.refs())
    return out


def build():
    os.makedirs(LIB, exist_ok=True)
    for f in glob.glob(os.path.join(LIB, "*.kicad_mod")): os.remove(f)
    used = used_footprints()
    copied, made = [], []
    for fp in sorted(used):
        lib, name = fp.split(":", 1)
        if lib == LIBNAME:
            if name not in CUSTOM: raise KeyError(f"{fp}: no generator for this footprint")
            open(os.path.join(LIB, name + ".kicad_mod"), "w").write(S.dump(CUSTOM[name]) + "\n"); made.append(name)
        else:
            src = os.path.join(STOCK, lib + ".pretty", name + ".kicad_mod")
            if not os.path.exists(src): raise FileNotFoundError(f"{fp} is not in KiCad's library ({src})")
            shutil.copyfile(src, os.path.join(LIB, name + ".kicad_mod")); copied.append(fp)
    return used, copied, made


if __name__ == "__main__":
    used, copied, made = build()
    print(f"{LIB}: {len(copied)} stock footprints copied, {len(made)} generated ({', '.join(made)})")
