"""Full build: footprints -> schematic -> ERC -> netlist -> PCB -> DRC -> JLC files.

    python tools/build.py            # everything
    python tools/build.py --no-pcb   # schematic + ERC only

Outputs land in production/: Gerber + drill zip for JLCPCB, BOM (CSV),
ERC/DRC reports and PNG renders of both board sides.
"""
import csv
import os
import shutil
import subprocess
import sys
import zipfile

HERE = os.path.dirname(os.path.abspath(__file__))
PROJ = os.path.dirname(HERE)
sys.path.insert(0, HERE)
import design  # noqa: E402

KICAD_BIN = r"C:\Program Files\KiCad\9.0\bin"
CLI = os.path.join(KICAD_BIN, "kicad-cli.exe")
KPY = os.path.join(KICAD_BIN, "python.exe")
NAME = design.PROJECT
SCH = os.path.join(PROJ, NAME + ".kicad_sch")
PCB = os.path.join(PROJ, NAME + ".kicad_pcb")
OUT = os.path.join(PROJ, "production")


def run(*args, check=True):
    print(">", " ".join(os.path.basename(a) if i == 0 else a for i, a in enumerate(args)))
    r = subprocess.run(args, cwd=PROJ, capture_output=True, text=True, encoding="utf-8",
                       errors="replace")
    out = (r.stdout + r.stderr).strip()
    if out:
        print("  " + out.replace("\n", "\n  "))
    if check and r.returncode != 0:
        sys.exit(f"step failed ({r.returncode})")
    return r


def report_errors(path):
    """Return the number of error-severity entries in a KiCad ERC/DRC report."""
    text = open(path, encoding="utf-8").read()
    return text.count("; error") + text.count("; Fehler") + text.count("error\n")


def bom():
    rows = {}
    for p in design.PARTS:
        if not p["fields"].get("in_bom", True) and p["ref"].startswith("H"):
            continue
        key = (p["value"], p["footprint"], "DNP" if p["fields"].get("dnp") else "")
        rows.setdefault(key, []).append((p["ref"], p["fields"].get("Description", "")))
    path = os.path.join(OUT, NAME + "-bom.csv")
    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["Qty", "References", "Value", "Footprint", "Purpose", "Fit"])
        for (value, fp, dnp), items in sorted(rows.items(), key=lambda kv: kv[1][0][0]):
            refs = [r for r, _ in items]
            purposes = "; ".join(dict.fromkeys(d for _, d in items if d))
            w.writerow([len(refs), " ".join(refs), value, fp.split(":")[1], purposes, dnp or "fit"])
    print("  wrote", path)
    digikey()


def digikey():
    """Upload file for DigiKey's BOM Manager (matched on Manufacturer Part Number)."""
    path = os.path.join(OUT, NAME + "-digikey-order.csv")
    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["Quantity", "Manufacturer Part Number", "Manufacturer", "Customer Reference",
                    "Description", "Qty per board"])
        for refs, (mfr, mpn, order, note) in design.MPN.items():
            if order == 0:
                continue
            w.writerow([order, mpn, mfr, refs, note, len(refs.split())])
    print("  wrote", path)


def main():
    os.makedirs(OUT, exist_ok=True)
    run(sys.executable, os.path.join(HERE, "make_footprints.py"))
    run(sys.executable, os.path.join(HERE, "make_schematic.py"))
    erc = os.path.join(OUT, NAME + "-erc.rpt")
    run(CLI, "sch", "erc", "--severity-all", "-o", erc, SCH, check=False)
    run(CLI, "sch", "export", "netlist", "--format", "kicadsexpr", "-o", NAME + ".net", SCH)
    run(CLI, "sch", "export", "pdf", "-o", os.path.join(OUT, NAME + "-schematic.pdf"), SCH)
    if "--no-pcb" in sys.argv:
        return
    run(KPY, os.path.join(HERE, "make_pcb.py"))
    drc = os.path.join(OUT, NAME + "-drc.rpt")
    run(CLI, "pcb", "drc", "--schematic-parity", "--severity-all", "-o", drc, PCB, check=False)
    iso = run(KPY, os.path.join(HERE, "check_isolation.py"), check=False)
    with open(os.path.join(OUT, NAME + "-isolation.txt"), "w", encoding="utf-8") as f:
        f.write(iso.stdout)

    gdir = os.path.join(OUT, "gerbers")
    shutil.rmtree(gdir, ignore_errors=True)
    os.makedirs(gdir)
    run(CLI, "pcb", "export", "gerbers", "-o", gdir + os.sep,
        "--layers", "F.Cu,B.Cu,F.Paste,B.Paste,F.Silkscreen,B.Silkscreen,F.Mask,B.Mask,Edge.Cuts",
        "--no-x2", "--subtract-soldermask", PCB)
    run(CLI, "pcb", "export", "drill", "-o", gdir + os.sep, "--format", "excellon",
        "--excellon-separate-th", "--excellon-units", "mm", "--generate-map", "--map-format", "gerberx2",
        PCB)
    zpath = os.path.join(OUT, NAME + "-jlcpcb-gerbers.zip")
    with zipfile.ZipFile(zpath, "w", zipfile.ZIP_DEFLATED) as z:
        for f in sorted(os.listdir(gdir)):
            z.write(os.path.join(gdir, f), f)
    print("  wrote", zpath)
    bom()
    for side in ("top", "bottom"):
        run(CLI, "pcb", "render", "--side", side, "--quality", "high", "--width", "1600",
            "--height", "1200", "-o", os.path.join(OUT, f"{NAME}-{side}.png"), PCB, check=False)
    print("\nERC report:", erc)
    print("DRC report:", drc)
    if iso.returncode != 0:
        sys.exit("ISOLATION GAP CHECK FAILED - see production/" + NAME + "-isolation.txt")


if __name__ == "__main__":
    main()
