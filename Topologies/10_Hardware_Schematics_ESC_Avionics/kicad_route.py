"""A small grid router for pcbnew boards (two signal layers, F.Cu and B.Cu, with through vias).

Used by pcb_avionics.py after placement and the hand-drawn power pours. It is meant for the signal and control nets of a
power board, where most connections are short; the power paths are pours drawn by the layout script, not routed here.

  R = Router(board, origin, size, group, clear)   rasterise every pad, track, via and (non-GND) zone outline on F.Cu
                                                  and B.Cu: one net code per grid cell (0.05 mm)
        group(netname) -> voltage group ("HVIN", "HVF", "HVSW" or "LV");  clear(ga, gb) -> clearance in mm
  R.connect(net, a, b, width)                     A* from point a to point b, 8 directions per layer, a via costs
                                                  `via_cost` mm of track. A cell is blocked when a track of this width
                                                  there would come closer to other copper than the clearance for that
                                                  pair of voltage groups (Euclidean distance transform per group, scipy)
  R.fanout(pad)                                   short track + via from a ground pad into the inner planes
Every route is written into the board as PCB_TRACK / PCB_VIA objects and rasterised, so later routes avoid it.

Grid error. A cell is marked as copper when its centre lies inside the copper, so the distance transform measures from
a cell centre to the nearest marked centre. The true copper edge lies beyond the outermost marked centre by less than
one cell in each axis, so in the worst case (a corner) it is up to a full cell diagonal (cell * sqrt 2 = 0.071 mm)
closer than measured. Every clearance test adds `slack` = 0.75 cell (0.04 mm): enough for the usual case, and small
enough that a 0.2 mm track still leaves a 0.5 mm-pitch pin (0.375 mm from its centre to the next pin: 0.1 + 0.2 +
0.04 = 0.34); the full worst case would block that. KiCad's DRC checks the rest. `via_extra` (default 0) adds to the
slack for new vias only (the ESC board sets it for its fan-out vias).
"""
import math, heapq
import numpy as np
from scipy import ndimage
from matplotlib.path import Path
import pcbnew

MM = 1e6
OUTER = (pcbnew.F_Cu, pcbnew.B_Cu)
DIRS8 = [(1, 0), (-1, 0), (0, 1), (0, -1), (1, 1), (1, -1), (-1, 1), (-1, -1)]
KEEP, NONET, GUARD = -1, -2, -3          # board edge / NPTH; copper without a net; protected same-net copper (Kelvin)


def mm(v): return v / MM


class Router:
    def __init__(self, board, origin, size, group, clear, cell=0.05, via=(0.6, 0.3), edge_clear=0.45, via_cost=2.5,
                 turn_cost=0.1, exempt=(), min_clear=0.2, exempt_layers=OUTER, nonet_group=None):
        self.b, self.cell, self.via, self.edge_clear = board, cell, via, edge_clear
        self.via_cost, self.turn_cost = via_cost / cell, turn_cost / cell          # in cells
        self.slack = 0.75 * cell
        self.via_extra = 0.0
        self.ox, self.oy = origin
        self.W, self.H = int(round(size[0] / cell)) + 1, int(round(size[1] / cell)) + 1
        self.group, self.clear, self.min_clear = group, clear, min_clear
        self.lab = {L: np.zeros((self.H, self.W), np.int32) for L in OUTER}
        self.through = np.zeros((self.H, self.W), np.int32)      # net code of PTH pads and vias (both layers joined)
        self.padmask = np.zeros((self.H, self.W), bool)
        self.exempt = {L: np.zeros((self.H, self.W), bool) for L in OUTER}     # areas where min_clear applies
        for x0, y0, x1, y1 in exempt:
            i0, j0 = self.ij(x0, y0); i1, j1 = self.ij(x1, y1)
            for L in exempt_layers: self.exempt[L][max(0, i0):i1 + 1, max(0, j0):j1 + 1] = True
        self.nonet_group = nonet_group or (lambda pad: None)
        self.ncode = {}                                               # voltage group -> code for its net-less pads
        self.gcode = {}
        self.added = []
        self._rasterise_board()

    # ------------------------------------------------------------------ rasterising (cell centre inside the copper)
    def ij(self, x, y):
        return int(round((y - self.oy) / self.cell)), int(round((x - self.ox) / self.cell))

    def xy(self, i, j):
        return round(self.ox + j * self.cell, 4), round(self.oy + i * self.cell, 4)

    def _window(self, x0, y0, x1, y1):
        """Cell index ranges and centre coordinates covering the box (x0, y0)-(x1, y1)."""
        i0, j0 = self.ij(x0, y0); i1, j1 = self.ij(x1, y1)
        i0, j0 = max(0, i0 - 1), max(0, j0 - 1); i1, j1 = min(self.H, i1 + 2), min(self.W, j1 + 2)
        if i0 >= i1 or j0 >= j1: return None
        X, Y = np.meshgrid(self.ox + np.arange(j0, j1) * self.cell, self.oy + np.arange(i0, i1) * self.cell)
        return (slice(i0, i1), slice(j0, j1)), X, Y

    def _poly_cells(self, polyset):
        """[(slices, mask)] for every outline of a SHAPE_POLY_SET (holes are ignored: pads and zone outlines have none)."""
        out = []
        for k in range(polyset.OutlineCount()):
            o = polyset.Outline(k)
            pts = np.array([(mm(o.CPoint(i).x), mm(o.CPoint(i).y)) for i in range(o.PointCount())])
            if len(pts) < 3: continue
            w = self._window(*pts.min(0), *pts.max(0))
            if w is None: continue
            sl, X, Y = w
            m = Path(pts).contains_points(np.c_[X.ravel(), Y.ravel()], radius=1e-9).reshape(X.shape)
            out.append((sl, m))
        return out

    def _seg_cells(self, a, b, w):
        r = w / 2
        win = self._window(min(a[0], b[0]) - r, min(a[1], b[1]) - r, max(a[0], b[0]) + r, max(a[1], b[1]) + r)
        if win is None: return []
        sl, X, Y = win
        dx, dy = b[0] - a[0], b[1] - a[1]; L2 = dx * dx + dy * dy
        t = np.clip(((X - a[0]) * dx + (Y - a[1]) * dy) / L2, 0, 1) if L2 > 0 else 0.0
        return [(sl, np.hypot(X - a[0] - t * dx, Y - a[1] - t * dy) <= r + 1e-9)]

    def _circle_cells(self, c, r):
        win = self._window(c[0] - r, c[1] - r, c[0] + r, c[1] + r)
        if win is None: return []
        sl, X, Y = win
        return [(sl, np.hypot(X - c[0], Y - c[1]) <= r + 1e-9)]

    def _paint(self, arr, cells, code, only_free=False):
        for sl, m in cells:
            sub = arr[sl]
            if only_free: m = m & ((sub == 0) | (sub == code))
            sub[m] = code

    def code(self, netname):
        n = self.b.FindNet(netname)
        return n.GetNetCode() if n else 0

    def grp(self, code):
        if code in (NONET, GUARD): return "LV"
        if code <= -10: return next(g for g, c in self.ncode.items() if c == code)
        if code not in self.gcode:
            self.gcode[code] = self.group(self.b.FindNet(int(code)).GetNetname())
        return self.gcode[code]

    def _rasterise_board(self):
        b = self.b
        for z in b.Zones():                                   # zone outlines first: pads and tracks overwrite them
            if z.GetIsRuleArea() or not z.GetNetCode() or z.GetNetname() == "GND": continue
            cells = self._poly_cells(z.Outline())
            for L in OUTER:
                if z.IsOnLayer(L): self._paint(self.lab[L], cells, z.GetNetCode())
        for fp in b.GetFootprints():
            for p in fp.Pads():
                code = p.GetNetCode()
                if not code:                                  # a pad without a net: low voltage unless told otherwise
                    g = self.nonet_group(p)
                    code = self.ncode.setdefault(g, -10 - len(self.ncode)) if g else NONET
                for L in OUTER:
                    if not p.IsOnLayer(L): continue
                    ps = pcbnew.SHAPE_POLY_SET()
                    p.TransformShapeToPolygon(ps, L, 0, int(0.005 * MM), pcbnew.ERROR_OUTSIDE)
                    cells = self._poly_cells(ps)
                    self._paint(self.lab[L], cells, code)
                    for sl, m in cells: self.padmask[sl] |= m
                    if p.GetAttribute() == pcbnew.PAD_ATTRIB_PTH: self._paint(self.through, cells, code)
                if p.GetAttribute() == pcbnew.PAD_ATTRIB_NPTH:
                    cells = self._circle_cells((mm(p.GetPosition().x), mm(p.GetPosition().y)), mm(p.GetDrillSize().x) / 2 + 0.25)
                    for L in OUTER: self._paint(self.lab[L], cells, KEEP)
        for t in b.GetTracks():
            self._add_item(t)
        e = int(round(self.edge_clear / self.cell))
        m = np.ones((self.H, self.W), bool); m[e:self.H - e, e:self.W - e] = False
        for L in OUTER: self.lab[L][m] = KEEP

    def _item_cells(self, t):
        if t.GetClass() == "PCB_VIA":
            return self._circle_cells((mm(t.GetPosition().x), mm(t.GetPosition().y)), mm(t.GetWidth(pcbnew.F_Cu)) / 2)
        return self._seg_cells((mm(t.GetStart().x), mm(t.GetStart().y)), (mm(t.GetEnd().x), mm(t.GetEnd().y)), mm(t.GetWidth()))

    def _add_item(self, t, code=None, only_free=False):
        """Rasterise a track or via. only_free: never overwrite another net's copper (routed items)."""
        code = t.GetNetCode() if code is None else code
        cells = self._item_cells(t)
        if t.GetClass() == "PCB_VIA":
            for L in OUTER: self._paint(self.lab[L], cells, code, only_free)
            self._paint(self.through, cells, t.GetNetCode())
        else:
            self._paint(self.lab[t.GetLayer()], cells, code, only_free)

    def guard(self, items):
        """Mark copper as foreign to every later route (a Kelvin trace must not pick up other connections)."""
        for t in items: self._add_item(t, GUARD)

    def unguard(self, items):
        for t in items: self._add_item(t)

    # ------------------------------------------------------------------ cost maps
    def _room(self, code, win):
        """Per layer, for every cell in the window: how far (mm) a copper edge placed at the cell centre may reach before it
        breaks a clearance, i.e. min over other copper of (distance - required clearance), minus the grid slack.
        A track of width w fits where room >= w/2; one distance transform per voltage group serves every width."""
        i0, i1, j0, j1 = win
        mine = self.grp(code)
        out = {}
        for L in OUTER:
            ex = self.exempt[L][i0:i1, j0:j1]
            lab = self.lab[L][i0:i1, j0:j1]
            room = np.full(lab.shape, 1e9)
            hard = lab == KEEP
            if hard.any(): room = np.minimum(room, ndimage.distance_transform_edt(~hard) * self.cell)
            other = (lab != 0) & (lab != code) & (lab != KEEP)
            if other.any():
                groups = {}
                for c in np.unique(lab[other]): groups.setdefault(self.grp(int(c)), []).append(c)
                for g, cs in groups.items():
                    d = ndimage.distance_transform_edt(~np.isin(lab, cs)) * self.cell
                    room = np.minimum(room, d - np.where(ex, self.min_clear, self.clear(mine, g)))
            out[L] = room - self.slack
        return out

    def _blocked(self, code, width, win, room=None):
        room = room or self._room(code, win)
        return {L: room[L] < width / 2 - 1e-9 for L in OUTER}

    def _via_ok(self, code, win, room=None):
        """Cells where a new via fits: clear of other copper on both layers and clear of every pad (no via-in-pad)."""
        room = room or self._room(code, win)
        r = self.via[0] / 2
        pm = self.padmask[win[0]:win[1], win[2]:win[3]]
        near_pad = (ndimage.distance_transform_edt(~pm) * self.cell < r + 0.1 + self.slack) if pm.any() else np.zeros(pm.shape, bool)
        r += self.via_extra
        return (room[pcbnew.F_Cu] >= r - 1e-9) & (room[pcbnew.B_Cu] >= r - 1e-9) & ~near_pad

    # ------------------------------------------------------------------ search
    def connect(self, netname, start, goal, width, start_layers=OUTER, goal_layers=OUTER, layers=OUTER, margin=8.0,
                layer_cost=None):
        """A* from start (x, y) to goal (x, y) in absolute mm. width: one width or a list, widest first.
        Returns the list of new board items (and the width used, when a list was given), or None.
        Both end cells must be free at the width too, so a track wider than a fine-pitch pin does not reach it: the
        next, narrower width is tried. Before each search a connected-component labelling of the free cells (F.Cu,
        B.Cu and the via spots joining them) tells whether the goal can be reached at all, so a failure costs one
        labelling instead of an exhausted search."""
        many = isinstance(width, (list, tuple))
        widths = list(width) if many else [width]
        code = self.code(netname)
        si, sj = self.ij(*start); gi, gj = self.ij(*goal)
        n = int(margin / self.cell); pad = int(3.5 / self.cell)
        wi0, wi1 = max(0, min(si, gi) - n), min(self.H, max(si, gi) + n + 1)
        wj0, wj1 = max(0, min(sj, gj) - n), min(self.W, max(sj, gj) + n + 1)
        ci0, ci1, cj0, cj1 = max(0, wi0 - pad), min(self.H, wi1 + pad), max(0, wj0 - pad), min(self.W, wj1 + pad)
        win = (ci0, ci1, cj0, cj1)
        room = self._room(code, win)
        via_ok = self._via_ok(code, win, room)
        thru = self.through[ci0:ci1, cj0:cj1] == code               # an existing via or PTH pad of this net
        si, sj, gi, gj = si - ci0, sj - cj0, gi - ci0, gj - cj0
        lo_i, hi_i, lo_j, hi_j = wi0 - ci0, wi1 - ci0 - 1, wj0 - cj0, wj1 - cj0 - 1
        inwin = np.zeros(thru.shape, bool); inwin[lo_i:hi_i + 1, lo_j:hi_j + 1] = True
        for w in widths:
            free = {L: (room[L] >= w / 2 - 1e-9) & inwin for L in layers}
            sl = [L for L in start_layers if L in free and free[L][si, sj]]
            gl = [L for L in goal_layers if L in free and free[L][gi, gj]]
            if not sl or not gl: continue
            # reachability: plane 0 = F.Cu, 1 = via spots, 2 = B.Cu; 4-connected in plane, vertical only at the same cell
            Ls = list(layers)
            if len(Ls) == 2:
                hop = (via_ok | thru) & free[Ls[0]] & free[Ls[1]]
                vol = np.stack([free[Ls[0]], hop, free[Ls[1]]])
                st = np.zeros((3, 3, 3), bool); st[1, 1, :] = st[1, :, 1] = True; st[0, 1, 1] = st[2, 1, 1] = True
                lab, _ = ndimage.label(vol, structure=st)
                plane = {Ls[0]: 0, Ls[1]: 2}
                a = {lab[plane[L], si, sj] for L in sl}; b = {lab[plane[L], gi, gj] for L in gl}
            else:
                lab, _ = ndimage.label(free[Ls[0]])
                a, b = {lab[si, sj]}, {lab[gi, gj]}
            if not (a & b) - {0}: continue
            path = self._astar(free, via_ok, thru, sl, gl, layers, (si, sj), (gi, gj), (lo_i, hi_i, lo_j, hi_j), layer_cost or {})
            if path is None: continue
            items = self._commit(code, [(L, i + ci0, j + cj0) for L, i, j in path], w, start, goal)
            return (items, w) if many else items
        return (None, None) if many else None

    def _astar(self, free, via_ok, thru, start_layers, goal_layers, layers, s, gpt, box, lc):
        si, sj = s; gi, gj = gpt; lo_i, hi_i, lo_j, hi_j = box
        def h(i, j):
            a, c = abs(i - gi), abs(j - gj)
            return 1.1 * (max(a, c) + 0.4142 * min(a, c))           # slightly greedy: much faster, paths a little longer
        openq, g, parent = [], {}, {}
        for L in start_layers:
            st = (L, si, sj); g[st] = 0.0; parent[st] = None
            heapq.heappush(openq, (h(si, sj), 0.0, st, (0, 0)))
        done = None
        while openq:
            f, gc, st, dprev = heapq.heappop(openq)
            if gc > g.get(st, 1e18) + 1e-9: continue
            L, i, j = st
            if i == gi and j == gj and L in goal_layers:
                done = st; break
            fr = free[L]
            for di, dj in DIRS8:
                ni, nj = i + di, j + dj
                if not (lo_i <= ni <= hi_i and lo_j <= nj <= hi_j): continue
                if not fr[ni, nj]: continue
                if di and dj and not (fr[i + di, j] and fr[i, j + dj]): continue
                step = (1.4142 if di and dj else 1.0) * lc.get(L, 1.0)
                if (di, dj) != dprev and dprev != (0, 0): step += self.turn_cost
                ns = (L, ni, nj); ng = gc + step
                if ng < g.get(ns, 1e18):
                    g[ns] = ng; parent[ns] = st; heapq.heappush(openq, (ng + h(ni, nj), ng, ns, (di, dj)))
            if via_ok[i, j] or thru[i, j]:
                for L2 in layers:
                    if L2 == L or not free[L2][i, j]: continue
                    ns = (L2, i, j); ng = gc + (0.0 if thru[i, j] else self.via_cost)
                    if ng < g.get(ns, 1e18):
                        g[ns] = ng; parent[ns] = st; heapq.heappush(openq, (ng + h(i, j), ng, ns, (0, 0)))
        if done is None: return None
        path = []
        st = done
        while st is not None:
            path.append(st); st = parent[st]
        return path[::-1]

    def _commit(self, code, path, width, start, goal):
        pts = []
        for k, (L, i, j) in enumerate(path):
            x, y = self.xy(i, j)
            if k == 0: x, y = start
            if k == len(path) - 1: x, y = goal
            pts.append((L, x, y, i, j))
        out = [pts[0]]
        for k in range(1, len(pts)):                      # merge collinear runs on one layer
            L, x, y, i, j = pts[k]
            if len(out) >= 2 and out[-1][0] == L and out[-2][0] == L:
                (_, x1, y1, _, _), (_, x2, y2, _, _) = out[-2], out[-1]
                if abs((x2 - x1) * (y - y2) - (y2 - y1) * (x - x2)) < 1e-6 and (x2 - x1) * (x - x2) + (y2 - y1) * (y - y2) >= 0:
                    out[-1] = (L, x, y, i, j); continue
            out.append((L, x, y, i, j))
        items = []
        for k in range(1, len(out)):
            (L1, x1, y1, i1, j1), (L2, x2, y2, _, _) = out[k - 1], out[k]
            if L1 != L2:
                if self.through[i1, j1] != code: items.append(self.add_via(code, (x1, y1)))
                continue
            if abs(x1 - x2) < 1e-6 and abs(y1 - y2) < 1e-6: continue
            items.append(self.add_track(code, (x1, y1), (x2, y2), width, L1))
        return items

    def add_track(self, code, a, b, width, layer):
        t = pcbnew.PCB_TRACK(self.b); t.SetStart(pcbnew.VECTOR2I_MM(*a)); t.SetEnd(pcbnew.VECTOR2I_MM(*b))
        t.SetWidth(int(round(width * MM))); t.SetLayer(layer); t.SetNet(self.b.FindNet(code)); self.b.Add(t)
        self._add_item(t, only_free=True); self.added.append(t)
        return t

    def add_via(self, code, c, size=None):
        size = size or self.via
        v = pcbnew.PCB_VIA(self.b); v.SetPosition(pcbnew.VECTOR2I_MM(*c)); v.SetWidth(int(round(size[0] * MM)))
        v.SetDrill(int(round(size[1] * MM))); v.SetNet(self.b.FindNet(code)); v.SetLayerPair(pcbnew.F_Cu, pcbnew.B_Cu)
        self.b.Add(v); self._add_item(v, only_free=True); self.added.append(v)
        return v

    # ------------------------------------------------------------------ ground fan-out
    def fanout(self, pad, width=0.4, reach=2.5):
        """Straight F.Cu stub from an SMD pad centre to the nearest spot where a via fits (into the inner planes).
        The stub is no wider than the pad, and every cell under its centre line must be free at that width."""
        code = pad.GetNetCode()
        sz = pad.GetSize(pcbnew.F_Cu)
        width = min(width, mm(min(sz.x, sz.y)))
        c = pad.GetPosition(); cx, cy = mm(c.x), mm(c.y)
        si, sj = self.ij(cx, cy)
        n = int(reach / self.cell) + 1; pad_ = int(3.5 / self.cell)
        win = (max(0, si - n - pad_), min(self.H, si + n + pad_ + 1), max(0, sj - n - pad_), min(self.W, sj + n + pad_ + 1))
        i0, j0 = win[0], win[2]
        room = self._room(code, win)
        blk = self._blocked(code, width, win, room)[pcbnew.F_Cu]
        if blk[si - i0, sj - j0]: return None
        via_ok = self._via_ok(code, win, room)
        cand = sorted((math.hypot(di, dj), di, dj) for di in range(-n, n + 1) for dj in range(-n, n + 1) if math.hypot(di, dj) <= n)
        for d, di, dj in cand:
            i, j = si + di - i0, sj + dj - j0
            if not (0 <= i < via_ok.shape[0] and 0 <= j < via_ok.shape[1]) or not via_ok[i, j]: continue
            steps = max(1, int(d * 2))
            if any(blk[int(round(si - i0 + di * k / steps)), int(round(sj - j0 + dj * k / steps))] for k in range(steps + 1)):
                continue
            x, y = self.xy(si + di, sj + dj)
            self.add_via(code, (x, y))
            if d > 0: self.add_track(code, (cx, cy), (x, y), width, pcbnew.F_Cu)
            return (x, y)
        return None
