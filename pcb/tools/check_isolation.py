"""Measure the copper gap between the ESP domain and the isolated SDC domain.

KiCad's DRC cannot express "these two groups of nets must be >= X apart"
(and kicad-cli ignores the .kicad_dru file), so this script does it:
all copper (tracks, vias, pads, filled pours) of each domain is merged per
layer, and the minimum distance between the two unions is found by growing
the ESP copper until it touches the SDC copper.

Must run with KiCad's Python. Exit code 1 if the gap is below MIN_GAP_MM.
"""
import os
import sys

import pcbnew

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import design  # noqa: E402

MIN_GAP_MM = 1.0
PCB = os.path.join(os.path.dirname(HERE), design.PROJECT + ".kicad_pcb")
ISO = {"/" + n for n in design.ISO_NETS}
MAXERR = pcbnew.FromMM(0.005)


def domain_copper(board, layer):
    polys = {"esp": pcbnew.SHAPE_POLY_SET(), "iso": pcbnew.SHAPE_POLY_SET()}

    def dom(net):
        return "iso" if net in ISO else "esp"

    for t in board.GetTracks():
        if t.IsOnLayer(layer) and t.GetNetCode() > 0:
            t.TransformShapeToPolygon(polys[dom(t.GetNetname())], layer, 0, MAXERR, pcbnew.ERROR_OUTSIDE)
    for fp in board.GetFootprints():
        for pad in fp.Pads():
            if pad.IsOnLayer(layer) and pad.GetNetCode() > 0:
                pad.TransformShapeToPolygon(polys[dom(pad.GetNetname())], layer, 0, MAXERR,
                                            pcbnew.ERROR_OUTSIDE)
    for z in board.Zones():
        if z.GetIsRuleArea() or not z.IsOnLayer(layer) or not z.HasFilledPolysForLayer(layer):
            continue
        polys[dom(z.GetNetname())].Append(z.GetFilledPolysList(layer))
    for p in polys.values():
        p.Simplify()
    return polys["esp"], polys["iso"]


def touches(a, b, gap_mm):
    grown = pcbnew.SHAPE_POLY_SET(a)
    grown.Inflate(pcbnew.FromMM(gap_mm / 2), pcbnew.CORNER_STRATEGY_ROUND_ALL_CORNERS, MAXERR)
    other = pcbnew.SHAPE_POLY_SET(b)
    other.Inflate(pcbnew.FromMM(gap_mm / 2), pcbnew.CORNER_STRATEGY_ROUND_ALL_CORNERS, MAXERR)
    grown.BooleanIntersection(other)
    return grown.OutlineCount() > 0, grown


def main():
    board = pcbnew.LoadBoard(PCB)
    pcbnew.ZONE_FILLER(board).Fill(board.Zones())
    worst = None
    for layer in (pcbnew.F_Cu, pcbnew.B_Cu):
        esp, iso = domain_copper(board, layer)
        hit, _ = touches(esp, iso, 0.0)
        if hit:
            print(f"{board.GetLayerName(layer)}: ESP and SDC copper OVERLAP")
            worst = 0.0
            continue
        lo, hi = 0.0, 5.0
        for _ in range(12):
            mid = (lo + hi) / 2
            if touches(esp, iso, mid)[0]:
                hi = mid
            else:
                lo = mid
        _, spot = touches(esp, iso, hi + 0.01)
        bb = spot.BBox()
        where = (pcbnew.ToMM(bb.Centre().x), pcbnew.ToMM(bb.Centre().y))
        print(f"{board.GetLayerName(layer)}: min copper gap ESP <-> SDC = {lo:.2f} mm "
              f"near ({where[0]:.1f}, {where[1]:.1f}) mm page coordinates")
        worst = lo if worst is None else min(worst, lo)
    ok = worst is not None and worst >= MIN_GAP_MM
    print(f"isolation gap check: {'PASS' if ok else 'FAIL'} (min {worst:.2f} mm, required {MIN_GAP_MM} mm)")
    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()
