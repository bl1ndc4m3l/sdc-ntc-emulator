"""Generate sdc-ntc-emulator.kicad_sch from design.py.

Every connected pin gets a local net label at its connection point, unused
pins get a no-connect flag. Library symbols are copied (and flattened) from
the KiCad 9 standard libraries and the project library.

Run with any Python 3: python tools/make_schematic.py
"""
import math
import os
import re
import uuid

import design

HERE = os.path.dirname(os.path.abspath(__file__))
PROJ_DIR = os.path.dirname(HERE)
# KiCad 9 standard symbols; KICAD9_SYMBOL_DIR is KiCad's own variable for them
KICAD_SYMBOLS = os.environ.get("KICAD9_SYMBOL_DIR",
                               r"C:\Program Files\KiCad\9.0\share\kicad\symbols")
PROJECT_LIBS = {"sdc_emulator": os.path.join(PROJ_DIR, "lib", "sdc_emulator.kicad_sym")}
NS = uuid.UUID("6d1b1b0e-6c3a-4a53-9a55-0f5d2a7c9e11")


def uid(*parts):
    return str(uuid.uuid5(NS, "/".join(str(p) for p in parts)))


# ------------------------------------------------------------ s-expressions
TOKEN = re.compile(r'\(|\)|"(?:\\.|[^"\\])*"|[^\s()]+')


def parse(text):
    tokens = TOKEN.findall(text)
    pos = 0

    def rd():
        nonlocal pos
        t = tokens[pos]
        pos += 1
        if t == "(":
            lst = []
            while tokens[pos] != ")":
                lst.append(rd())
            pos += 1
            return lst
        return t

    return rd()


def dump(node, indent=1):
    if not isinstance(node, list):
        return node
    if all(not isinstance(c, list) for c in node):
        return "(" + " ".join(node) + ")"
    pad = "\t" * indent
    out = "(" + node[0]
    for c in node[1:]:
        if isinstance(c, list):
            out += "\n" + pad + dump(c, indent + 1)
        else:
            out += " " + c
    return out + "\n" + "\t" * (indent - 1) + ")"


def q(s):
    return '"' + str(s).replace("\\", "\\\\").replace('"', '\\"').replace("\n", "\\n") + '"'


def unq(s):
    return s[1:-1] if s.startswith('"') else s


def child(node, key):
    for c in node:
        if isinstance(c, list) and c and c[0] == key:
            return c
    return None


# ------------------------------------------------------------ library symbols
_lib_cache = {}


def lib_tree(lib):
    if lib not in _lib_cache:
        path = PROJECT_LIBS.get(lib) or os.path.join(KICAD_SYMBOLS, lib + ".kicad_sym")
        with open(path, encoding="utf-8") as f:
            _lib_cache[lib] = parse(f.read())
    return _lib_cache[lib]


def find(tree, name):
    for n in tree:
        if isinstance(n, list) and n[0] == "symbol" and unq(n[1]) == name:
            return n
    raise KeyError(name)


def flattened(lib_id):
    """Return the symbol node named lib_id with 'extends' resolved."""
    lib, name = lib_id.split(":")
    tree = lib_tree(lib)
    node = find(tree, name)
    ext = child(node, "extends")
    if ext:
        parent = flattened(f"{lib}:{unq(ext[1])}")
        pname = unq(parent[1]).split(":")[1]
        props = {unq(p[1]): p for p in node if isinstance(p, list) and p[0] == "property"}
        new = [parent[0], q(lib_id)]
        for c in parent[2:]:
            if isinstance(c, list) and c[0] == "property" and unq(c[1]) in props:
                new.append(props.pop(unq(c[1])))
            elif isinstance(c, list) and c[0] == "symbol":
                sub = list(c)
                sub[1] = q(unq(c[1]).replace(pname, name, 1))
                new.append(sub)
            else:
                new.append(c)
        # properties only present in the child go before the unit symbols
        extra = list(props.values())
        idx = next(i for i, c in enumerate(new) if isinstance(c, list) and c[0] == "symbol")
        return new[:idx] + extra + new[idx:]
    new = list(node)
    new[1] = q(lib_id)
    return new


def symbol_pins(node):
    """(number, x, y, angle) for unit 0 and unit 1 pins, lib coordinates (y up)."""
    pins = []
    for sub in node:
        if isinstance(sub, list) and sub[0] == "symbol":
            m = re.search(r"_(\d+)_(\d+)$", unq(sub[1]))
            if m and m.group(1) not in ("0", "1"):
                continue
            for p in sub:
                if isinstance(p, list) and p[0] == "pin":
                    at = child(p, "at")
                    num = unq(child(p, "number")[1])
                    hidden = child(p, "hide") is not None and child(p, "hide")[1] == "yes"
                    pins.append((num, float(at[1]), float(at[2]), int(float(at[3])), p[1], hidden))
    return pins


def prop_at(node, name):
    for p in node:
        if isinstance(p, list) and p[0] == "property" and unq(p[1]) == name:
            at = child(p, "at")
            hidden = child(child(p, "effects") or [], "hide") if child(p, "effects") else None
            return float(at[1]), float(at[2]), hidden is not None
    return 0.0, 0.0, True


def xform(px, py, x, y, rot):
    a = math.radians(rot)
    rx = px * math.cos(a) - py * math.sin(a)
    ry = px * math.sin(a) + py * math.cos(a)
    return round(x + rx, 4), round(y - ry, 4)


def fmt(v):
    s = f"{v:.4f}".rstrip("0").rstrip(".")
    return "0" if s in ("-0", "") else s


# ------------------------------------------------------------ schematic items
def effects(size=1.27, justify=None, hide=False):
    e = f"(effects (font (size {size} {size}))"
    if justify:
        e += f" (justify {justify})"
    if hide:
        e += " (hide yes)"
    return e + ")"


def prop(name, value, x, y, hide=False, justify=None):
    return f'(property {q(name)} {q(value)} (at {fmt(x)} {fmt(y)} 0) {effects(justify=justify, hide=hide)})'


def label(net, x, y, angle):
    just = {0: "left bottom", 90: "left bottom", 180: "right bottom", 270: "right bottom"}[angle]
    return (f'(label {q(net)} (at {fmt(x)} {fmt(y)} {angle}) (fields_autoplaced yes) '
            f'{effects(justify=just)} (uuid {q(uid("label", net, x, y))}))')


def no_connect(x, y):
    return f'(no_connect (at {fmt(x)} {fmt(y)}) (uuid {q(uid("nc", x, y))}))'


def symbol_instance(lib_id, ref, value, footprint, x, y, rot, fields, dnp=False, power=False,
                    in_bom=True):
    node = flattened(lib_id)
    sid = uid("sym", ref)
    rx, ry, _ = prop_at(node, "Reference")
    vx, vy, _ = prop_at(node, "Value")
    ds = next((unq(p[2]) for p in node if isinstance(p, list) and p[0] == "property"
               and unq(p[1]) == "Datasheet"), "~")
    desc = fields.get("Description") or next(
        (unq(p[2]) for p in node if isinstance(p, list) and p[0] == "property"
         and unq(p[1]) == "Description"), "")
    ref_xy = xform(rx, ry, x, y, rot)
    val_xy = xform(vx, vy, x, y, rot)
    lines = [f"(symbol (lib_id {q(lib_id)}) (at {fmt(x)} {fmt(y)} {rot}) (unit 1)",
             f"(exclude_from_sim no) (in_bom {'yes' if in_bom and not power else 'no'})"
             f" (on_board {'no' if power else 'yes'})"
             f" (dnp {'yes' if dnp else 'no'})",
             f"(uuid {q(sid)})",
             prop("Reference", ref, *ref_xy, hide=power),
             prop("Value", value, *val_xy),
             prop("Footprint", footprint, x, y, hide=True),
             prop("Datasheet", ds, x, y, hide=True),
             prop("Description", desc, x, y, hide=True)]
    for k, v in fields.items():
        if k not in ("Description", "dnp"):
            lines.append(prop(k, v, x, y, hide=True))
    for num, *_ in symbol_pins(node):
        lines.append(f'(pin {q(num)} (uuid {q(uid("pin", ref, num))}))')
    lines.append(f'(instances (project {q(design.PROJECT)} (path {q("/" + ROOT)} '
                 f'(reference {q(ref)}) (unit 1))))')
    lines.append(")")
    return "\n".join(lines), node


ROOT = uid("root-sheet")


def main():
    items = []
    used_libs = {}
    for p in design.PARTS:
        x, y, rot = p["sch"]
        fields = dict(p["fields"])
        dnp = fields.pop("dnp", False)
        in_bom = fields.pop("in_bom", True)
        m = design.mpn_for(p["ref"])
        if m:
            fields["Manufacturer"], fields["MPN"] = m[0], m[1]
        text, node = symbol_instance(p["symbol"], p["ref"], p["value"], p["footprint"],
                                     x, y, rot, fields, dnp=dnp, in_bom=in_bom)
        used_libs[p["symbol"]] = node
        items.append(text)
        for num, px, py, ang, ptype, hidden in symbol_pins(node):
            ax, ay = xform(px, py, x, y, rot)
            net = p["pins"].get(num)
            if net:
                items.append(label(net, ax, ay, (ang + rot + 180) % 360))
            elif unq(ptype) != "no_connect" and not hidden:
                items.append(no_connect(ax, ay))
            elif not net and unq(ptype) == "no_connect":
                pass
    for i, (net, (x, y)) in enumerate(design.PWR_FLAGS, 1):
        text, node = symbol_instance("power:PWR_FLAG", f"#FLG0{i}", "PWR_FLAG", "", x, y, 0, {},
                                     power=True)
        used_libs["power:PWR_FLAG"] = node
        items.append(text)
        items.append(label(net, x, y, 270))
    for t, (x, y), size in design.TEXTS:
        items.append(f'(text {q(t)} (exclude_from_sim no) (at {fmt(x)} {fmt(y)} 0) '
                     f'{effects(size=size, justify="left bottom")} (uuid {q(uid("text", t))}))')

    lib_block = "\n".join(dump(n, 2) for n in used_libs.values())
    out = [
        "(kicad_sch",
        "(version 20250114)",
        '(generator "eeschema")',
        '(generator_version "9.0")',
        f"(uuid {q(ROOT)})",
        '(paper "A3")',
        '(title_block (title "SDC NTC emulator - wireless room sensor for Smile SDC3-40PM")'
        ' (date "2026-09-29") (rev "1")'
        ' (comment 1 "ESP32-S3 + ISO1540 + AD5272 + fail-safe relay, see docs/design-notes.md")'
        ' (comment 2 "Generated by tools/make_schematic.py from tools/design.py - edit design.py, not this file"))',
        "(lib_symbols",
        lib_block,
        ")",
        *items,
        f'(sheet_instances (path "/" (page "1")))',
        "(embedded_fonts no)",
        ")",
    ]
    text = "\n".join(out)
    # re-indent through the parser for a tidy, KiCad-like file
    tree = parse(text)
    path = os.path.join(PROJ_DIR, design.PROJECT + ".kicad_sch")
    with open(path, "w", encoding="utf-8", newline="\n") as f:
        f.write(dump(tree) + "\n")
    print("wrote", path)


if __name__ == "__main__":
    main()
