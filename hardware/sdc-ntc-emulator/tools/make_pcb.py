"""Build sdc-ntc-emulator.kicad_pcb: placement, routing, pours, silkscreen.

Must run with KiCad's Python (pcbnew + numpy):
  "C:\\Program Files\\KiCad\\9.0\\bin\\python.exe" tools/make_pcb.py

Inputs: tools/design.py (parts, footprints) and sdc-ntc-emulator.net
(exported by kicad-cli from the schematic, gives nets and symbol UUIDs).

Routing is done by a small grid router (A*, two layers, 45 degree moves,
vias). Each net may only use its own domain area (ESP or isolated SDC side),
which keeps the isolation gap free of copper by construction.
"""
import heapq
import math
import os
import re
import sys

import numpy as np
import pcbnew

HERE = os.path.dirname(os.path.abspath(__file__))
PROJ_DIR = os.path.dirname(HERE)
sys.path.insert(0, HERE)
import design  # noqa: E402

KICAD_FP = r"C:\Program Files\KiCad\9.0\share\kicad\footprints"
PCB_PATH = os.path.join(PROJ_DIR, design.PROJECT + ".kicad_pcb")
NET_PATH = os.path.join(PROJ_DIR, design.PROJECT + ".net")

# ------------------------------------------------------------------ geometry
BOARD_W, BOARD_H = 104.0, 76.0
OX, OY = 100.0, 50.0            # board origin on the KiCad page (mm)

# DevKit clone (photo 2026-09-29): pinout = official DevKitC-1, board ~56.6 mm long,
# ~27.7 mm wide, module antenna overhangs the DevKit edge ~7 mm beyond pin 1.
DEVKIT_ROWS = 25.1               # measured: outer 25.6 / inner 24.6 mm -> centre 25.1 mm
DEVKIT_X0, DEVKIT_PIN1_Y = 10.0, 58.34

# (x, y, rotation) in board coordinates (mm, y down), footprint origin = pad 1
PLACEMENT = {
    "J2": (DEVKIT_X0, DEVKIT_PIN1_Y, 180),                # DevKit header J3 (left row)
    "J1": (DEVKIT_X0 + DEVKIT_ROWS, DEVKIT_PIN1_Y, 180),  # DevKit header J1 (right row)
    "J3": (47.08, 6.0, 180),     # 5 V in, wire entry towards top edge
    "Q2": (53.5, 6.0, 180),      # reverse-polarity P-FET between J3 and C1
    "C1": (62.0, 6.0, 0),
    "C9": (30.6, 7.54, 0),       # 10 uF ceramic under the DevKit, next to its 5V pin J1.21
    "C2": (62.3, 16.5, 90),      # TEM input decoupling, beside pin 24
    "PS1": (42.0, 16.5, 0),      # TEM 2-0511, pin 1 top left
    "U1": (60.3, 50.5, 0),       # ISO1540 straddles the isolation gap
    "R1": (47.0, 48.4, 0),
    "R2": (47.0, 50.8, 0),
    "C3": (55.4, 50.5, 270),     # right at U1 VCC1/GND1 (TI: <= 2 mm)
    "D1": (51.8, 51.6, 180),
    "R11": (38.0, 47.9, 90),     # relay sense divider
    "R12": (41.3, 47.7, 0),
    "K1": (45.0, 55.0, 0),       # coil (pins 1/16) on ESP side, contacts below
    "Q1": (41.0, 55.6, 0),
    "R4": (39.6, 51.8, 90),
    "R3": (41.0, 58.5, 0),
    "C4": (63.0, 40.63, 90),
    "R8": (84.0, 35.5, 0),       # optional preload, kept away from the TEM
    "R7": (67.2, 36.8, 0),
    "D2": (71.6, 36.8, 180),
    "C5": (65.2, 50.5, 270),     # right at U1 VCC2/GND2
    "R5": (69.0, 51.0, 0),
    "R6": (69.0, 53.4, 0),
    "U2": (80.0, 56.05, 180),    # pad rows land exactly on router grid centres
    "C8": (86.2, 53.6, 0),
    "C6": (86.6, 58.6, 0),
    "C7": (86.6, 61.0, 0),
    "R10": (58.5, 67.9, 0),
    "R9": (86.0, 48.0, 0),       # R_series above U2: the wiper leaves upwards, away from VDD/A
    "J4": (97.5, 64.0, 90),      # SDC terminal, wire entry towards right edge
    "H1": (4.0, 4.0, 0),
    "H2": (100.0, 4.0, 0),
    "H3": (4.0, 72.0, 0),
    "H4": (100.0, 72.0, 0),
}

# Reference designator positions on the silkscreen (board coordinates), where the
# footprint default would collide with neighbours. Size 1.0 mm (JLC minimum).
REF_POS = {
    "R1": (44.0, 48.4), "R2": (44.0, 50.8), "C3": (55.4, 47.3), "D1": (51.8, 49.5),
    "Q1": (41.6, 53.3), "R3": (41.0, 60.4), "R4": (37.7, 51.8), "C2": (64.9, 16.5), "C9": (30.6, 9.8),
    "J3": (44.55, 13.0), "PS1": (49.6, 19.6), "U1": (61.5, 46.9), "C5": (65.2, 47.3), "R5": (72.7, 51.0),
    "R6": (72.7, 53.4), "C8": (89.6, 53.6), "C6": (90.0, 58.6), "C7": (90.0, 61.0),
    "R7": (67.2, 38.5), "D2": (74.9, 36.8), "C4": (65.3, 40.63), "Q2": (53.5, 9.6),
    "R11": (38.0, 44.8, 90), "R12": (41.3, 49.6),
    "U2": (80.0, 59.5), "K1": (49.0, 64.5), "J4": (92.0, 70.5),
}
HIDE_REFS = {"H1", "H2", "H3", "H4", "J1", "J2", "R8", "R9", "R10"}

# Copper areas per domain (board coordinates). Gap between them >= 1 mm.
# Tracks are kept inside their outline (eroded by half their width), so the outline
# gap is also the minimum copper gap between the domains. tools/check_isolation.py
# verifies >= 1.0 mm on the finished board.
ESP_POLY = [(0.5, 0.5), (71.0, 0.5), (71.0, 30.0), (59.8, 30.0), (59.8, 34.9), (39.8, 34.9),
            (39.8, 43.7), (59.8, 43.7), (59.8, 58.8), (42.2, 58.8), (42.2, 75.5), (0.5, 75.5)]
ISO_POLY = [(72.4, 0.5), (103.5, 0.5), (103.5, 75.5), (43.4, 75.5), (43.4, 60.0), (61.2, 60.0),
            (61.2, 42.4), (41.0, 42.4), (41.0, 36.2), (61.2, 36.2), (61.2, 31.4), (72.4, 31.4)]
# No copper under the ESP32-S3 module antenna (DevKit antenna end, bottom left).
ANTENNA_KEEPOUT = [(7.0, 59.6), (39.0, 59.6), (39.0, 75.9), (7.0, 75.9)]
# No copper around the M3 mounting holes (screw heads, washers).
MOUNT_KEEPOUT_R = 3.5
# THT ground pads that additionally get a via (pour access is cramped there).
THT_GROUND_VIAS = {("PS1", "12"), ("PS1", "13")}

POWER_W = {"/+5V_IN": 0.6, "/+5V": 0.6, "/VDD_ISO": 0.6, "/COIL_N": 0.6, "/+3V3": 0.4}
SIGNAL_W = 0.25
GND_NETS = {"/GND", "/GND_ISO"}
VIA_D, VIA_DRILL = 0.8, 0.4

# ------------------------------------------------------------------ router grid
G = 0.1
NX, NY = int(round(BOARD_W / G)), int(round(BOARD_H / G))
CLR = 0.25 + 0.05          # clearance incl. rasterisation margin
CLR_FINE = 0.13 + 0.07     # inside the MSOP-10 area; +half cell for pad rasterisation
FINE_BOX = None            # set from U2 courtyard
VIA_COST = 25.0
HARD = -2


def mm(v):
    return pcbnew.FromMM(float(v))


def vec(x, y):
    return pcbnew.VECTOR2I(mm(OX + x), mm(OY + y))


def to_board(p):
    return pcbnew.ToMM(p.x) - OX, pcbnew.ToMM(p.y) - OY


# ------------------------------------------------------------------ netlist
def parse_netlist(path):
    text = open(path, encoding="utf-8").read()
    comps = {}
    for block in text.split("(comp (ref ")[1:]:
        ref = re.match(r'"([^"]+)"', block).group(1)
        m = re.search(r'\(tstamps "([0-9a-f-]{36})"\)', block)
        if m:
            comps[ref] = m.group(1)
    nets = {}
    for block in text.split("(net (code ")[1:]:
        name = re.search(r'\(name "([^"]+)"\)', block).group(1)
        nets[name] = re.findall(r'\(node \(ref "([^"]+)"\) \(pin "([^"]+)"\)', block)
    return comps, nets


# ------------------------------------------------------------------ helpers
def points_in_poly(xs, ys, poly):
    inside = np.zeros(xs.shape, dtype=bool)
    n = len(poly)
    for k in range(n):
        x1, y1 = poly[k]
        x2, y2 = poly[(k + 1) % n]
        cond = ((y1 > ys) != (y2 > ys))
        with np.errstate(divide="ignore", invalid="ignore"):
            xint = (x2 - x1) * (ys - y1) / (y2 - y1) + x1
        inside ^= cond & (xs < xint)
    return inside


CX = (np.arange(NX) + 0.5) * G
CY = (np.arange(NY) + 0.5) * G
GX, GY = np.meshgrid(CX, CY)


def disk(r_cells):
    r = int(math.ceil(r_cells))
    return [(dy, dx) for dy in range(-r, r + 1) for dx in range(-r, r + 1)
            if dx * dx + dy * dy <= r_cells * r_cells]


def dilate(mask, r_cells):
    out = mask.copy()
    for dy, dx in disk(r_cells):
        if dy == 0 and dx == 0:
            continue
        src = mask[max(0, -dy):NY - max(0, dy), max(0, -dx):NX - max(0, dx)]
        out[max(0, dy):NY - max(0, -dy), max(0, dx):NX - max(0, -dx)] |= src
    return out


def seg_mask(x1, y1, x2, y2, half_w):
    """Boolean grid of cells whose centre lies within half_w of the segment."""
    x0, x1b = min(x1, x2) - half_w, max(x1, x2) + half_w
    y0, y1b = min(y1, y2) - half_w, max(y1, y2) + half_w
    i0, i1 = max(0, int(x0 / G) - 1), min(NX, int(x1b / G) + 2)
    j0, j1 = max(0, int(y0 / G) - 1), min(NY, int(y1b / G) + 2)
    px, py = GX[j0:j1, i0:i1], GY[j0:j1, i0:i1]
    dx, dy = x2 - x1, y2 - y1
    L2 = dx * dx + dy * dy
    if L2 == 0:
        t = np.zeros_like(px)
    else:
        t = np.clip(((px - x1) * dx + (py - y1) * dy) / L2, 0, 1)
    d2 = (px - (x1 + t * dx)) ** 2 + (py - (y1 + t * dy)) ** 2
    m = np.zeros((NY, NX), dtype=bool)
    m[j0:j1, i0:i1] = d2 <= half_w * half_w
    return m


def cell_of(x, y):
    return min(NY - 1, max(0, int(y / G))), min(NX - 1, max(0, int(x / G)))


# ------------------------------------------------------------------ board build
def load_fp(fpid):
    lib, name = fpid.split(":")
    path = (os.path.join(PROJ_DIR, "lib", lib + ".pretty") if lib == "sdc_emulator"
            else os.path.join(KICAD_FP, lib + ".pretty"))
    fp = pcbnew.FootprintLoad(path, name)
    if fp is None:
        raise RuntimeError(f"footprint not found: {fpid}")
    fp.SetFPID(pcbnew.LIB_ID(lib, name))
    return fp


def build_board():
    comps, nets = parse_netlist(NET_PATH)
    if os.path.exists(PCB_PATH):
        os.remove(PCB_PATH)
    board = pcbnew.NewBoard(PCB_PATH)
    netinfo = {}
    for name in nets:
        ni = pcbnew.NETINFO_ITEM(board, name)
        board.Add(ni)
        netinfo[name] = ni
    pad_net = {(ref, pin): name for name, nodes in nets.items() for ref, pin in nodes}

    fps = {}
    for p in design.PARTS:
        ref = p["ref"]
        fp = load_fp(p["footprint"])
        fp.SetReference(ref)
        fp.SetValue(p["value"])
        x, y, rot = PLACEMENT[ref]
        fp.SetPosition(vec(x, y))
        fp.SetOrientationDegrees(rot)
        if ref in comps:
            fp.SetPath(pcbnew.KIID_PATH("/" + comps[ref]))
        fp.SetSheetfile(design.PROJECT + ".kicad_sch")
        fp.SetSheetname("/")
        if p["fields"].get("dnp"):
            fp.SetDNP(True)
        rf = fp.Reference()
        rf.SetTextSize(pcbnew.VECTOR2I(mm(1.0), mm(1.0)))
        rf.SetTextThickness(mm(0.15))
        if ref in HIDE_REFS:
            rf.SetVisible(False)
        elif ref in REF_POS:
            pos = REF_POS[ref]
            rf.SetPosition(vec(pos[0], pos[1]))
            rf.SetTextAngleDegrees(pos[2] if len(pos) > 2 else 0)
        if ref == "K1":
            # Omron recommends 1.0 mm holes for the G5V-2 (library footprint: 0.7 mm)
            for pad in fp.Pads():
                pad.SetDrillSize(pcbnew.VECTOR2I(mm(1.0), mm(1.0)))
                pad.SetSize(pcbnew.VECTOR2I(mm(1.8), mm(1.8)))
        for pad in fp.Pads():
            name = pad_net.get((ref, pad.GetNumber()))
            if name:
                pad.SetNet(netinfo[name])
            if (ref, pad.GetNumber()) in THT_GROUND_VIAS:
                # too little pour around these pins for two thermal spokes
                pad.SetLocalZoneConnection(pcbnew.ZONE_CONNECTION_FULL)
        board.Add(fp)
        fps[ref] = fp
    return board, fps, netinfo, nets


def add_outline(board):
    r = pcbnew.PCB_SHAPE(board, pcbnew.SHAPE_T_RECTANGLE)
    r.SetStart(vec(0, 0))
    r.SetEnd(vec(BOARD_W, BOARD_H))
    r.SetLayer(pcbnew.Edge_Cuts)
    r.SetWidth(mm(0.1))
    board.Add(r)


# ------------------------------------------------------------------ router
class Router:
    def __init__(self, board, fps, netinfo):
        self.board = board
        self.fps = fps
        self.netinfo = netinfo
        self.names = list(netinfo)
        self.idx = {n: i for i, n in enumerate(self.names)}
        self.owner = np.full((2, NY, NX), -1, dtype=np.int32)
        self.padcell = np.zeros((2, NY, NX), dtype=bool)
        self.pads = []   # (ref, num, net, layers, cells(mask per layer), cx, cy, is_smd)
        self.esp = points_in_poly(GX, GY, ESP_POLY)
        self.iso = points_in_poly(GX, GY, ISO_POLY)
        self.fine = np.zeros((NY, NX), dtype=bool)
        self.holes = []   # (x, y, drill) of every drilled hole, for hole-to-hole spacing
        self._raster_pads()
        self._hard_blocks()
        self.tracks = []  # (net, layer, x1, y1, x2, y2, w)
        self.vias = []    # (net, x, y)
        self.failed = []  # ground connections that could not be made

    def _raster_pads(self):
        u2 = self.fps["U2"].GetCourtyard(pcbnew.F_Cu).BBox()
        fx0, fy0 = to_board(u2.GetOrigin())
        fx1, fy1 = to_board(u2.GetEnd())
        self.fine = (GX > fx0 - 1.0) & (GX < fx1 + 1.0) & (GY > fy0 - 1.0) & (GY < fy1 + 1.0)
        extra = len(self.names)
        for ref, fp in self.fps.items():
            for pad in fp.Pads():
                net = pad.GetNetname()
                if net in self.idx:
                    nid = self.idx[net]
                else:
                    nid = extra
                    extra += 1
                layers = [li for li, L in enumerate((pcbnew.F_Cu, pcbnew.B_Cu)) if pad.IsOnLayer(L)]
                bb = pad.GetBoundingBox()
                x0, y0 = to_board(bb.GetOrigin())
                x1, y1 = to_board(bb.GetEnd())
                i0, i1 = max(0, int(x0 / G)), min(NX, int(x1 / G) + 1)
                j0, j1 = max(0, int(y0 / G)), min(NY, int(y1 / G) + 1)
                m = np.zeros((NY, NX), dtype=bool)
                lay = pcbnew.F_Cu if 0 in layers else pcbnew.B_Cu
                poly = pad.GetEffectivePolygon(lay, pcbnew.ERROR_INSIDE)
                for j in range(j0, j1):
                    for i in range(i0, i1):
                        if poly.Contains(vec(CX[i], CY[j])):
                            m[j, i] = True
                if not m.any():
                    j, i = cell_of(*to_board(pad.GetPosition()))
                    m[j, i] = True
                for li in layers:
                    self.owner[li][m] = nid
                    self.padcell[li] |= m
                cx, cy = to_board(pad.GetPosition())
                drill = pad.GetDrillSize().x > 0
                if drill:
                    # holes block vias on both layers regardless of pad copper
                    self.holes.append((cx, cy, pcbnew.ToMM(pad.GetDrillSize().x)))
                    hm = seg_mask(cx, cy, cx, cy, pcbnew.ToMM(pad.GetDrillSize().x) / 2)
                    for li in (0, 1):
                        self.owner[li][hm & (self.owner[li] == -1)] = nid
                self.pads.append(dict(ref=ref, num=pad.GetNumber(), net=net, nid=nid, layers=layers,
                                      mask=m, x=cx, y=cy, smd=not drill))

    def _hard_blocks(self):
        edge = ((GX < 0.5) | (GX > BOARD_W - 0.5) | (GY < 0.5) | (GY > BOARD_H - 0.5))
        keep = points_in_poly(GX, GY, ANTENNA_KEEPOUT)
        holes = np.zeros((NY, NX), dtype=bool)
        for ref in ("H1", "H2", "H3", "H4"):
            x, y, _ = PLACEMENT[ref]
            holes |= seg_mask(x, y, x, y, MOUNT_KEEPOUT_R)
        for li in (0, 1):
            self.owner[li][edge | keep | holes] = HARD
        # AD5272: no tracks under the MSOP body, no vias anywhere in its courtyard
        # (hand-soldering bridge risk)
        cy = self.fps["U2"].GetCourtyard(pcbnew.F_Cu).BBox()
        cx0, cy0 = to_board(cy.GetOrigin())
        cx1, cy1 = to_board(cy.GetEnd())
        self.novia = (GX > cx0) & (GX < cx1) & (GY > cy0) & (GY < cy1)
        # Under the body only GND_ISO may run (it ties A/VSS to the outer GND pins)
        ux, uy, _ = PLACEMENT["U2"]
        self.body = (GX > ux - 1.2) & (GX < ux + 1.2) & (GY > uy - 1.6) & (GY < uy + 1.6)

    # -------------------------------------------------------------- masks
    def blocked(self, nid, half_w):
        out = np.zeros((2, NY, NX), dtype=bool)
        for li in (0, 1):
            foreign = (self.owner[li] != -1) & (self.owner[li] != nid)
            coarse = dilate(foreign, (half_w + CLR) / G)
            fine = dilate(foreign, (half_w + CLR_FINE) / G)
            out[li] = np.where(self.fine, fine, coarse)
        return out

    def domain(self, net):
        return self.iso if net.lstrip("/") in design.ISO_NETS else self.esp

    @staticmethod
    def inside(dom, half_w):
        """Domain eroded so that a track of this half width stays inside the outline."""
        return ~dilate(~dom, (half_w + 0.1) / G)

    def via_ok(self, nid, net):
        both = np.zeros((NY, NX), dtype=bool)
        for li in (0, 1):
            foreign = (self.owner[li] != -1) & (self.owner[li] != nid)
            both |= dilate(foreign, (VIA_D / 2 + CLR) / G)
        own_pads = self.padcell[0] | self.padcell[1]
        dom = dilate(~self.domain(net), (VIA_D / 2 + 0.2) / G)
        near_hole = np.zeros((NY, NX), dtype=bool)
        for hx, hy, hd in self.holes:
            near_hole |= seg_mask(hx, hy, hx, hy, hd / 2 + 0.5 + VIA_DRILL / 2 + 0.05)
        return ~both & ~own_pads & ~dom & ~near_hole & ~self.novia

    def exit_corridors(self, except_net=None, half=0.8):
        """Cells in front of the AD5272 signal pins (3 mm outwards), so every 0.5 mm-pitch
        pin keeps a straight way out. half=0.8: keep vias out; half=0.45: keep other nets'
        top-layer tracks out (adjacent pins at 0.5 mm pitch can still leave in parallel)."""
        ux = PLACEMENT["U2"][0]
        m = np.zeros((NY, NX), dtype=bool)
        for q in self.pads:
            if q["ref"] != "U2" or q["net"] in GND_NETS or q["net"] == except_net:
                continue
            side = 1 if q["x"] > ux else -1
            x_end = q["x"] + side * 0.81
            xs = (GX - x_end) * side
            m |= (np.abs(GY - q["y"]) < half) & (xs > 0) & (xs < 3.0)
        return m

    def add_via(self, net, nid, x, y, tree=None):
        self.vias.append((net, x, y))
        self.holes.append((x, y, VIA_DRILL))
        vm = seg_mask(x, y, x, y, VIA_D / 2)
        for li in (0, 1):
            self.owner[li][vm] = nid
            if tree is not None:
                tree[li] |= vm

    # -------------------------------------------------------------- search
    def astar(self, starts, goal, free, vok, target_xy):
        tx, ty = target_xy
        tj, ti = cell_of(tx, ty)
        dirs = [(0, 1, 1.0), (1, 0, 1.0), (0, -1, 1.0), (-1, 0, 1.0),
                (1, 1, 1.414), (1, -1, 1.414), (-1, 1, 1.414), (-1, -1, 1.414)]
        openh = []
        best = {}
        came = {}
        for s in starts:
            best[s] = 0.0
            came[s] = None
            heapq.heappush(openh, (0.0, s))
        expanded = 0
        while openh:
            f, s = heapq.heappop(openh)
            l, j, i = s
            gcost = best[s]
            if goal[l, j, i]:
                path = []
                while s is not None:
                    path.append(s)
                    s = came[s]
                return path[::-1]
            expanded += 1
            if expanded > 1_500_000:
                return None
            for dj, di, c in dirs:
                nj, ni = j + dj, i + di
                if not (0 <= nj < NY and 0 <= ni < NX) or not free[l, nj, ni]:
                    continue
                if dj and di and not (free[l, j, ni] and free[l, nj, i]):
                    continue    # no corner cutting past obstacles on a diagonal step
                ns = (l, nj, ni)
                ng = gcost + c + (0.3 if (dj and di) else 0.0)
                if ng < best.get(ns, 1e18):
                    best[ns] = ng
                    came[ns] = s
                    h = max(abs(nj - tj), abs(ni - ti)) + 0.414 * min(abs(nj - tj), abs(ni - ti))
                    heapq.heappush(openh, (ng + h, ns))
            if vok[j, i]:
                ns = (1 - l, j, i)
                if free[1 - l, j, i]:
                    ng = gcost + VIA_COST
                    if ng < best.get(ns, 1e18):
                        best[ns] = ng
                        came[ns] = s
                        h = max(abs(j - tj), abs(i - ti))
                        heapq.heappush(openh, (ng + h, ns))
        return None

    # -------------------------------------------------------------- commit
    def commit_path(self, net, nid, path, width, start_xy, tree):
        pts = [(path[0][0], start_xy[0], start_xy[1])]
        for (l, j, i) in path:
            pts.append((l, CX[i], CY[j]))
        # split into same-layer runs, put vias at layer changes
        segs = []
        prev = pts[0]
        for cur in pts[1:]:
            if cur[0] != prev[0]:
                self.add_via(net, nid, prev[1], prev[2], tree)
            else:
                segs.append((cur[0], prev[1], prev[2], cur[1], cur[2]))
            prev = cur
        # merge collinear segments
        merged = []
        for s in segs:
            if merged:
                l, x1, y1, x2, y2 = merged[-1]
                if s[0] == l and abs(x2 - s[1]) < 1e-9 and abs(y2 - s[2]) < 1e-9:
                    d1 = (x2 - x1, y2 - y1)
                    d2 = (s[3] - s[1], s[4] - s[2])
                    if abs(d1[0] * d2[1] - d1[1] * d2[0]) < 1e-9 and (d1[0] * d2[0] + d1[1] * d2[1]) >= 0:
                        merged[-1] = (l, x1, y1, s[3], s[4])
                        continue
            merged.append(s)
        for l, x1, y1, x2, y2 in merged:
            if abs(x1 - x2) < 1e-9 and abs(y1 - y2) < 1e-9:
                continue
            self.tracks.append((net, l, x1, y1, x2, y2, width))
            m = seg_mask(x1, y1, x2, y2, width / 2)
            self.owner[l][m] = nid
            tree[l] |= m

    def route_net(self, net, only=None, width=None):
        nid = self.idx[net]
        width = width or POWER_W.get(net, SIGNAL_W)
        pads = [p for p in self.pads if p["net"] == net
                and (only is None or (p["ref"], p["num"]) in only)]
        if len(pads) < 2:
            return True
        dom = self.domain(net)

        def free_for(w):
            # recomputed per connection: earlier connections of this net are own copper.
            # Own pad cells are only free where they also keep clearance, so a track
            # never runs off-centre inside a fine-pitch pad towards its neighbour.
            f = ~self.blocked(nid, w / 2)
            inner = self.inside(dom, w / 2)
            for li in (0, 1):
                f[li] &= inner
                if w > SIGNAL_W:
                    f[li] &= ~self.fine      # wide power tracks stay out of the MSOP area
            f[0] &= ~self.exit_corridors(except_net=net, half=0.45) & ~self.body
            return f

        vok = self.via_ok(nid, net) & ~self.exit_corridors(except_net=net, half=0.8)
        # fine-pitch pads (MSOP-10) must not be the tree seed: they get thin tracks
        pads.sort(key=lambda p: bool(self.fine[cell_of(p["x"], p["y"])]))
        tree = np.zeros((2, NY, NX), dtype=bool)
        first = pads[0]
        for li in first["layers"]:
            tree[li] |= first["mask"]
        done = [first]
        todo = pads[1:]
        ok = True
        while todo:
            todo.sort(key=lambda p: min(math.hypot(p["x"] - d["x"], p["y"] - d["y"]) for d in done))
            p = todo.pop(0)
            if any(tree[li][p["mask"]].any() for li in p["layers"]):
                done.append(p)
                continue
            w = SIGNAL_W if self.fine[cell_of(p["x"], p["y"])] else width
            free = free_for(w)
            # start exactly at the pad centre cell
            j, i = cell_of(p["x"], p["y"])
            starts = [(li, j, i) for li in p["layers"]]
            for li in p["layers"]:
                free[li, j, i] = True
            # end on own copper that is clearance-safe for this width (or own tracks)
            goal = tree & (free | ~self.padcell)
            near = min(done, key=lambda d: math.hypot(p["x"] - d["x"], p["y"] - d["y"]))
            path = self.astar(starts, goal, free | goal, vok, (near["x"], near["y"]))
            if path is None:
                print(f"  !! could not route {net}: {p['ref']}.{p['num']}")
                ok = False
                continue
            self.commit_path(net, nid, path, w, (p["x"], p["y"]), tree)
            for li in p["layers"]:
                tree[li] |= p["mask"]
            done.append(p)
        return ok

    def ground_vias(self, fine=None, only=None, own_only=False):
        """Give every SMD ground pad (and the listed THT pads) a via to the bottom pour.
        fine=True: only the fine-pitch (MSOP) pads, fine=False: all others.
        only: set of (ref, pin) to restrict to. Pads that already have a via are skipped."""
        for p in self.pads:
            if p["net"] not in GND_NETS:
                continue
            if fine is not None and bool(self.fine[cell_of(p["x"], p["y"])]) != fine:
                continue
            if only is not None and (p["ref"], p["num"]) not in only:
                continue
            if p.get("via_done"):
                continue
            p["via_done"] = True
            if not p["smd"] and (p["ref"], p["num"]) not in THT_GROUND_VIAS:
                continue
            net, nid = p["net"], p["nid"]
            width = SIGNAL_W if self.fine[cell_of(p["x"], p["y"])] else 0.4
            free = (~self.blocked(nid, width / 2)[0] & self.inside(self.domain(net), width / 2)
                    & ~self.exit_corridors(half=0.45))
            if net != "/GND_ISO":
                free &= ~self.body
            j0, i0 = cell_of(p["x"], p["y"])
            free[j0, i0] = True
            vok = self.via_ok(nid, net)
            goal = np.zeros((2, NY, NX), dtype=bool)
            # via candidates at least 0.9 mm from the pad centre
            far = (GX - p["x"]) ** 2 + (GY - p["y"]) ** 2 > 1.0 ** 2
            near = (GX - p["x"]) ** 2 + (GY - p["y"]) ** 2 < 6.0 ** 2
            goal[0] = vok & free & far & near & ~self.exit_corridors()
            # ... or any existing copper of the same ground net (pads, tracks, vias)
            own = (self.owner[0] == nid) & ~p["mask"] & near
            if own_only:
                goal[0] = own
            goal[0] |= own
            fr = np.zeros((2, NY, NX), dtype=bool)
            fr[0] = free | own
            path = self.astar([(0, j0, i0)], goal, fr, np.zeros((NY, NX), dtype=bool),
                              (p["x"], p["y"]))
            if path is None:
                print(f"  !! no ground via for {p['ref']}.{p['num']}")
                self.failed.append(f"ground {p['ref']}.{p['num']}")
                continue
            tree = np.zeros((2, NY, NX), dtype=bool)
            self.commit_path(net, nid, path, width, (p["x"], p["y"]), tree)
            l, j, i = path[-1]
            if not own[j, i]:
                self.add_via(net, nid, CX[i], CY[j])

    def emit(self):
        for net, l, x1, y1, x2, y2, w in self.tracks:
            t = pcbnew.PCB_TRACK(self.board)
            t.SetStart(vec(x1, y1))
            t.SetEnd(vec(x2, y2))
            t.SetWidth(mm(w))
            t.SetLayer(pcbnew.F_Cu if l == 0 else pcbnew.B_Cu)
            t.SetNet(self.netinfo[net])
            self.board.Add(t)
        for net, x, y in self.vias:
            v = pcbnew.PCB_VIA(self.board)
            v.SetPosition(vec(x, y))
            v.SetDrill(mm(VIA_DRILL))
            v.SetWidth(mm(VIA_D))
            v.SetNet(self.netinfo[net])
            self.board.Add(v)


# ------------------------------------------------------------------ zones, silk
def add_zone(board, netinfo, net, poly, layer, rule_area=False):
    z = pcbnew.ZONE(board)
    z.SetLayer(layer)
    ol = z.Outline()
    ol.NewOutline()
    for x, y in poly:
        ol.Append(mm(OX + x), mm(OY + y))
    if rule_area:
        z.SetIsRuleArea(True)
        z.SetDoNotAllowTracks(True)
        z.SetDoNotAllowVias(True)
        z.SetDoNotAllowPads(False)
        z.SetDoNotAllowFootprints(False)
        z.SetDoNotAllowCopperPour(True)
        ls = pcbnew.LSET()
        ls.AddLayer(pcbnew.F_Cu)
        ls.AddLayer(pcbnew.B_Cu)
        z.SetLayerSet(ls)
        z.SetZoneName("antenna keep-out")
    else:
        z.SetNet(netinfo[net])
        z.SetLocalClearance(mm(0.3))
        z.SetMinThickness(mm(0.25))
        z.SetPadConnection(pcbnew.ZONE_CONNECTION_THT_THERMAL)   # SMD pads solid
        z.SetThermalReliefGap(mm(0.4))
        z.SetThermalReliefSpokeWidth(mm(0.5))
        z.SetIslandRemovalMode(pcbnew.ISLAND_REMOVAL_MODE_ALWAYS)
    board.Add(z)
    return z


def silk_text(board, text, x, y, size=1.0, layer=pcbnew.F_SilkS, bold=False, angle=0, justify=None):
    t = pcbnew.PCB_TEXT(board)
    t.SetText(text)
    t.SetPosition(vec(x, y))
    t.SetLayer(layer)
    t.SetTextSize(pcbnew.VECTOR2I(mm(size), mm(size)))
    t.SetTextThickness(mm(size * (0.2 if bold else 0.15)))
    if angle:
        t.SetTextAngleDegrees(angle)
    if justify == "left":
        t.SetHorizJustify(pcbnew.GR_TEXT_H_ALIGN_LEFT)
    board.Add(t)


def silk_line(board, x1, y1, x2, y2, w=0.15, layer=pcbnew.F_SilkS):
    s = pcbnew.PCB_SHAPE(board, pcbnew.SHAPE_T_SEGMENT)
    s.SetStart(vec(x1, y1))
    s.SetEnd(vec(x2, y2))
    s.SetLayer(layer)
    s.SetWidth(mm(w))
    board.Add(s)


def dashed(board, pts, dash=1.0, gap=0.8, layer=pcbnew.F_SilkS):
    for (x1, y1), (x2, y2) in zip(pts, pts[1:]):
        L = math.hypot(x2 - x1, y2 - y1)
        n = int(L // (dash + gap))
        for k in range(n + 1):
            a = k * (dash + gap) / L
            b = min(1.0, (k * (dash + gap) + dash) / L)
            if a >= 1:
                break
            silk_line(board, x1 + (x2 - x1) * a, y1 + (y2 - y1) * a,
                      x1 + (x2 - x1) * b, y1 + (y2 - y1) * b, layer=layer)


def add_silk(board):
    # DevKit outline (clone: pin 22 ~1.7 mm from USB end, pin 1 ~1.4 mm from antenna end)
    x0, x1 = DEVKIT_X0 - 1.15, DEVKIT_X0 + DEVKIT_ROWS + 1.15
    y0, y1 = DEVKIT_PIN1_Y - 21 * 2.54 - 1.7, DEVKIT_PIN1_Y + 1.4
    for a, b in [((x0, y0), (x1, y0)), ((x1, y0), (x1, y1)), ((x1, y1), (x0, y1)), ((x0, y1), (x0, y0))]:
        silk_line(board, *a, *b, layer=pcbnew.F_Fab)
    # module antenna overhang (~18 mm wide, ~7.5 mm beyond the DevKit edge)
    xm = DEVKIT_X0 + DEVKIT_ROWS / 2
    dashed(board, [(xm - 9, y1), (xm - 9, y1 + 7.5), (xm + 9, y1 + 7.5), (xm + 9, y1)])
    silk_text(board, "ESP32-S3 DevKit - USB-C this end", xm, y0 - 1.4, 1.0)
    silk_text(board, "ANTENNA", xm, y1 + 3.0, 1.0)
    silk_text(board, "no copper below", xm, y1 + 10.0, 1.0)
    silk_text(board, "DK-J1", DEVKIT_X0 + DEVKIT_ROWS, y1 + 1.5, 1.0)
    silk_text(board, "DK-J3", DEVKIT_X0, y1 + 1.5, 1.0)
    # isolation gap (centre line): full outline on F.Fab, top run also on silkscreen
    dashed(board, [(71.7, 1.0), (71.7, 30.7), (60.5, 30.7), (60.5, 35.6), (40.4, 35.6), (40.4, 43.05),
                   (60.5, 43.05), (60.5, 59.4), (42.8, 59.4), (42.8, 75.0)], layer=pcbnew.F_Fab)
    dashed(board, [(71.7, 2.0), (71.7, 30.7), (66.0, 30.7)])
    silk_text(board, "ESP SIDE", 50.0, 33.2, 1.0, bold=True)
    silk_text(board, "ISOLATED SDC SIDE", 82.0, 44.5, 1.2, bold=True)
    silk_text(board, "+5V", 47.08, 13.0, 1.0)
    silk_text(board, "GND", 41.9, 13.0, 1.0)
    silk_text(board, "TO SDC", 97.5, 52.0, 1.0, bold=True)
    silk_text(board, "GND X5-2..12", 97.2, 54.3, 1.0)
    silk_text(board, "VE1 X6-6", 97.5, 68.4, 1.0)
    silk_text(board, "R8: DNP", 79.0, 33.3, 1.0, justify="left")
    silk_text(board, "SDC NTC emulator", 88.0, 8.0, 1.2, bold=True)
    silk_text(board, "SDC3-40PM VE1  rev 2  2026-09", 88.0, 10.4, 1.0)
    silk_text(board, "R9 R_series 18k2 0.1%", 91.1, 50.2, 1.0)
    silk_text(board, "R10 R_failsafe 24k9 0.1%", 66.0, 65.7, 1.0)


# ------------------------------------------------------------------ main
# AD5272 nets first (after its ground stubs), so its 0.5 mm-pitch pins are not walled in.
ROUTE_ORDER = ["/SDA_ISO", "/SCL_ISO", "/EXT_CAP", "/WIPER", "/VDD_ISO",
               "/+5V_IN", "/+5V", "/COIL_N", "/RELAY_SENSE", "/GATE", "/RELAY_EN", "/+3V3", "/SDA_ESP",
               "/SCL_ESP", "/LED_ISO",
               "/VE1", "/NC_PATH", "/NO_PATH", "/GND", "/GND_ISO"]


def main():
    board, fps, netinfo, nets = build_board()
    add_outline(board)
    router = Router(board, fps, netinfo)
    failed = []
    # The antenna keep-out and the J1 fan-out split the ESP ground pour; tie the
    # DevKit GND to the TEM input ground with a real track first.
    print("routing /GND link")
    if not router.route_net("/GND", only={("J1", "22"), ("PS1", "12")}, width=0.8):
        failed.append("/GND link")
    # AD5272 fan-out in a fixed order so no 0.5 mm-pitch pin gets walled in:
    # left side SDA/SCL, right side EXT_CAP, then pin 2 (A) ground, then the wiper,
    # then the remaining ground pins; everything else afterwards.
    for net in ("/SDA_ISO", "/SCL_ISO", "/EXT_CAP"):
        print("routing", net)
        if not router.route_net(net):
            failed.append(net)
    print("ground (AD5272)")
    router.ground_vias(fine=True, only={("U2", "6"), ("U2", "10")})   # outer pins: vias outwards
    router.ground_vias(fine=True, only={("U2", "2"), ("U2", "4")}, own_only=True)  # under the body
    print("routing /WIPER")
    if not router.route_net("/WIPER"):
        failed.append("/WIPER")
    for net in ROUTE_ORDER[4:]:      # the first four (AD5272) are done above
        if net in GND_NETS:
            continue
        print("routing", net)
        if not router.route_net(net):
            failed.append(net)
    print("ground vias")
    router.ground_vias(fine=False)
    failed += router.failed
    router.emit()
    for layer in (pcbnew.F_Cu, pcbnew.B_Cu):
        add_zone(board, netinfo, "/GND", ESP_POLY, layer)
        add_zone(board, netinfo, "/GND_ISO", ISO_POLY, layer)
    add_zone(board, netinfo, None, ANTENNA_KEEPOUT, pcbnew.F_Cu, rule_area=True)
    for ref in ("H1", "H2", "H3", "H4"):
        x, y, _ = PLACEMENT[ref]
        circle = [(x + MOUNT_KEEPOUT_R * math.cos(a * math.pi / 8),
                   y + MOUNT_KEEPOUT_R * math.sin(a * math.pi / 8)) for a in range(16)]
        z = add_zone(board, netinfo, None, circle, pcbnew.F_Cu, rule_area=True)
        z.SetZoneName(f"{ref} screw keep-out")
    add_silk(board)
    filler = pcbnew.ZONE_FILLER(board)
    filler.Fill(board.Zones())
    pcbnew.SaveBoard(PCB_PATH, board)
    print("wrote", PCB_PATH)
    if failed:
        print("UNROUTED:", failed)
        sys.exit(1)


if __name__ == "__main__":
    main()
