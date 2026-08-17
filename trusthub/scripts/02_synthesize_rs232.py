from pathlib import Path
import subprocess
import shutil
import tempfile
import re

# =====================================================
# CONFIGURATION
# =====================================================

ROOT = Path(r"C:\HT_detection_GNN\trusthub\AES_unzipped")
OUTROOT = Path(r"C:\HT_detection_GNN\trusthub\netlists\RS232")

YOSYS = shutil.which("yosys") or "yosys"

OUTROOT.mkdir(parents=True, exist_ok=True)

# =====================================================
# HELPERS
# =====================================================

def is_testbench(name):
    name = name.lower()
    return (
        name.startswith("test")
        or name.startswith("tb")
        or "testbench" in name
        or name.endswith("_tb.v")
    )



def patch_file(src, dst):

    """

    Copy Verilog file and fix absolute include paths

    (different TrustHub contributors baked in different

    hardcoded Linux paths).

    """

    text = src.read_text(errors="ignore")

    # Rewrite `include "/any/absolute/path/whatever.h" -> `include "whatever.h"

    text = re.sub(

        r'(`include\s+")([^"]*[\\/])?([^"/\\]+\.h)(")',

        r'\1\3\4',

        text

    )

    dst.write_text(text)


  

def synthesize(folder, top_module, outdir, tag):

    temp = Path(tempfile.mkdtemp())

    verilog_files = []

    # copy files into temp directory
    for f in folder.glob("*"):

        if not f.is_file():
            continue

        if f.suffix.lower() not in [".v", ".h"]:
            continue

        if is_testbench(f.name):
            continue

        dst = temp / f.name
        patch_file(f, dst)

        if dst.suffix == ".v":
            verilog_files.append(dst)

    if len(verilog_files) == 0:
        print("      No Verilog files.")
        shutil.rmtree(temp)
        return False

    ys = outdir / f"{tag}.ys"
    log = outdir / f"{tag}.log"
    netlist = outdir / f"{tag}_netlist.v"

    with open(ys, "w") as f:

        for vf in sorted(verilog_files):
            f.write(f'read_verilog "{vf}"\n')

        f.write("\n")

        if top_module is None:
            f.write("hierarchy -auto-top\n")
        else:
            f.write(f"hierarchy -top {top_module}\n")

        f.write("""
proc
opt
flatten
opt
techmap
opt
abc
opt
""")

        f.write(f'write_verilog -noexpr "{netlist}"\n')

    result = subprocess.run(
        [YOSYS, "-s", str(ys)],
        capture_output=True,
        text=True
    )

    with open(log, "w") as f:
        f.write(result.stdout)
        f.write("\n")
        f.write(result.stderr)

    shutil.rmtree(temp)

    return result.returncode == 0 and netlist.exists()


# =====================================================
# MAIN
# =====================================================

success = 0
failed = 0

benchmarks = sorted(ROOT.glob("RS232-*"))

print(f"\nFound {len(benchmarks)} RS232 benchmarks\n")

for bench in benchmarks:

    print("=" * 70)
    print(bench.name)

    src = next(bench.rglob("src"), None)

    if src is None:
        continue

    outdir = OUTROOT / bench.name
    outdir.mkdir(parents=True, exist_ok=True)

    # -------------------------------------------------
    # CASE 1
    # T100-T900
    # -------------------------------------------------

    if (src / "uart.v").exists():

        print("   STANDARD")

        ok = synthesize(
            src,
            "uart",
            outdir,
            "standard"
        )

        if ok:
            print("      SUCCESS")
            success += 1
        else:
            print("      FAILED")
            failed += 1

        continue

    # -------------------------------------------------
    # CASE 2
    # 90nm / 180nm
    # -------------------------------------------------

    if (src / "90nm").exists():

        for tech in ["90nm", "180nm"]:

            folder = src / tech

            if not folder.exists():
                continue

            print("   ", tech)

            ok = synthesize(
                folder,
                "uart",
                outdir,
                tech
            )

            if ok:
                print("      SUCCESS")
                success += 1
            else:
                print("      FAILED")
                failed += 1

        continue

    # -------------------------------------------------
    # CASE 3
    # TjFree / TjIn
    # -------------------------------------------------

    if (src / "TjFree").exists():

        for version in ["TjFree", "TjIn"]:

            folder = src / version

            if not folder.exists():
                continue

            print("   ", version)

            ok = synthesize(
                folder,
                "uart",
                outdir,
                version.lower()
            )

            if ok:
                print("      SUCCESS")
                success += 1
            else:
                print("      FAILED")
                failed += 1

        continue

print("\n" + "=" * 70)
print("RS232 synthesis complete")
print("Successful :", success)
print("Failed     :", failed)
print("=" * 70)