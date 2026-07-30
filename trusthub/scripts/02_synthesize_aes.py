from pathlib import Path
import subprocess
import shutil

# ==========================================================
# CONFIGURATION
# ==========================================================

ROOT = Path(r"C:\trusthub\AES_unzipped")
OUTROOT = Path(r"C:\trusthub\netlists\AES")

YOSYS = shutil.which("yosys") or "yosys"

OUTROOT.mkdir(parents=True, exist_ok=True)

# ==========================================================
# FILE FILTER
# ==========================================================

def is_testbench(file_path: Path):
    """Return True if this Verilog file is a testbench."""

    name = file_path.name.lower()

    # Skip common testbench names
    if (
        name.startswith("test")
        or name.startswith("tb")
        or "testbench" in name
        or name.endswith("_tb.v")
        or name == "tbtop.v"
    ):
        return True

    return False


# ==========================================================
# BUILD YOSYS SCRIPT
# ==========================================================

def build_script(verilog_files, top_module, output_netlist, ys_file):

    with open(ys_file, "w") as f:

        for vf in verilog_files:
            f.write(f'read_verilog "{vf}"\n')

        f.write("\n")

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

        f.write(f'write_verilog "{output_netlist}"\n')


# ==========================================================
# RUN YOSYS
# ==========================================================

def run_yosys(script_file, log_file):

    result = subprocess.run(
        [YOSYS, "-s", str(script_file)],
        capture_output=True,
        text=True
    )

    with open(log_file, "w") as f:
        f.write(result.stdout)
        f.write("\n")
        f.write(result.stderr)

    return result.returncode == 0


# ==========================================================
# SYNTHESIZE ONE DESIGN
# ==========================================================

def synthesize(folder, top_module, output_name, outdir):

    # Collect source files
    verilog_files = []

    for vf in sorted(folder.glob("*.v")):

        if is_testbench(vf):
            continue

        verilog_files.append(vf)

    if len(verilog_files) == 0:
        print("      No Verilog source files.")
        return False

    ys_file = outdir / f"{output_name}.ys"
    log_file = outdir / f"{output_name}.log"
    output_netlist = outdir / f"{output_name}_netlist.v"

    build_script(
        verilog_files,
        top_module,
        output_netlist,
        ys_file
    )

    ok = run_yosys(ys_file, log_file)

    if ok and output_netlist.exists():
        return True

    return False


# ==========================================================
# MAIN
# ==========================================================

benchmarks = sorted(ROOT.glob("AES-*"))

print(f"\nFound {len(benchmarks)} AES benchmarks\n")

success = 0
failed = 0

for bench in benchmarks:

    print("=" * 70)
    print(bench.name)

    src = next(bench.rglob("src"), None)

    if src is None:
        print("   No src folder.")
        continue

    outdir = OUTROOT / bench.name
    outdir.mkdir(parents=True, exist_ok=True)

    # ------------------------------------------------------
    # CLEAN
    # ------------------------------------------------------

    tjfree = src / "TjFree"

    if tjfree.exists():

        print("   CLEAN")

        ok = synthesize(
            folder=tjfree,
            top_module="aes_128",
            output_name="clean",
            outdir=outdir
        )

        if ok:
            print("      SUCCESS")
            success += 1
        else:
            print("      FAILED")
            failed += 1

    # ------------------------------------------------------
    # TROJAN
    # ------------------------------------------------------

    tjin = src / "TjIn"

    if tjin.exists():

        print("   TROJAN")

        ok = synthesize(
            folder=tjin,
            top_module="top",
            output_name="trojan",
            outdir=outdir
        )

        if ok:
            print("      SUCCESS")
            success += 1
        else:
            print("      FAILED")
            failed += 1

print("\n" + "=" * 70)
print("AES synthesis complete")
print(f"Successful : {success}")
print(f"Failed     : {failed}")
print("=" * 70)