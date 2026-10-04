"""Write the project footprint library (lib/sdc_emulator.pretty).

Traco TEM 2 (single output): DIP-24 grid, 15.24 mm row spacing, but only
pins 1-3, 10-15 and 22-24 exist (datasheet, bottom view). Body 31.8 x 20.3 mm.

Run with any Python 3: python tools/make_footprints.py
"""
import os

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(os.path.dirname(HERE), "lib", "sdc_emulator.pretty")

PINS = [1, 2, 3, 10, 11, 12, 13, 14, 15, 22, 23, 24]


def pin_xy(n):
    if n <= 12:
        return 0.0, (n - 1) * 2.54
    return 15.24, (24 - n) * 2.54


def rect(layer, x0, y0, x1, y1, width):
    return (f'\t(fp_rect (start {x0:.3f} {y0:.3f}) (end {x1:.3f} {y1:.3f}) '
            f'(stroke (width {width}) (type solid)) (fill no) (layer "{layer}"))\n')


def tem2():
    cx, cy = 7.62, 13.97
    bx0, bx1 = cx - 10.15, cx + 10.15
    by0, by1 = cy - 15.9, cy + 15.9
    s = '(footprint "Traco_TEM2_Single_DIP24"\n'
    s += '\t(version 20241229)\n\t(generator "make_footprints.py")\n\t(layer "F.Cu")\n'
    s += ('\t(descr "Traco TEM 2 series single output, DIP-24 outline 31.8 x 20.3 mm, '
          'pins 4-9 and 16-21 not present")\n')
    s += '\t(tags "Traco TEM2 DC-DC isolated DIP24")\n'
    s += (f'\t(property "Reference" "PS**" (at {cx:.2f} {by0 - 1.5:.2f} 0) (layer "F.SilkS") '
          '(effects (font (size 1 1) (thickness 0.15))))\n')
    s += (f'\t(property "Value" "TEM2-0511" (at {cx:.2f} {by1 + 1.5:.2f} 0) (layer "F.Fab") '
          '(effects (font (size 1 1) (thickness 0.15))))\n')
    s += '\t(attr through_hole)\n'
    s += rect("F.Fab", bx0, by0, bx1, by1, 0.1)
    s += rect("F.SilkS", bx0 - 0.11, by0 - 0.11, bx1 + 0.11, by1 + 0.11, 0.12)
    s += rect("F.CrtYd", bx0 - 0.25, by0 - 0.25, bx1 + 0.25, by1 + 0.25, 0.05)
    # pin 1 marker
    s += (f'\t(fp_line (start {bx0 - 0.6:.2f} -1.0) (end {bx0 - 0.6:.2f} 1.0) '
          '(stroke (width 0.2) (type solid)) (layer "F.SilkS"))\n')
    s += (f'\t(fp_text user "IN" (at {cx:.2f} 2.0 0) (layer "F.Fab") '
          '(effects (font (size 1 1) (thickness 0.15))))\n')
    s += (f'\t(fp_text user "OUT" (at {cx:.2f} 24.0 0) (layer "F.Fab") '
          '(effects (font (size 1 1) (thickness 0.15))))\n')
    # Oval pads, narrow along the row: 1.24 mm copper gap between neighbouring pins,
    # which matters between pin 11 (+Vout, isolated) and pin 12 (-Vin, ESP side).
    for n in PINS:
        x, y = pin_xy(n)
        shape = "rect" if n == 1 else "oval"
        s += (f'\t(pad "{n}" thru_hole {shape} (at {x:.2f} {y:.2f}) (size 1.8 1.3) (drill 0.8) '
              '(layers "*.Cu" "*.Mask"))\n')
    s += ')\n'
    return s


def main():
    os.makedirs(OUT, exist_ok=True)
    path = os.path.join(OUT, "Traco_TEM2_Single_DIP24.kicad_mod")
    with open(path, "w", encoding="utf-8", newline="\n") as f:
        f.write(tem2())
    print("wrote", path)


if __name__ == "__main__":
    main()
