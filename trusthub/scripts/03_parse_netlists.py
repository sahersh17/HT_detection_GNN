from pathlib import Path
import re
import json


# ============================================================
# CONFIG
# ============================================================

NETLIST_ROOT = Path(r"C:\HT_detection_GNN\trusthub\netlists")
OUTPUT_ROOT = Path(r"C:\HT_detection_GNN\trusthub\parsed")

OUTPUT_ROOT.mkdir(
    parents=True,
    exist_ok=True
)
KEYWORDS = {"module", "endmodule", "input", "output", "inout", "wire",
            "reg", "assign", "parameter", "always", "initial", "generate", "endgenerate"}

# ============================================================
# REGEX
# ============================================================

# module declaration
module_re = re.compile(
    r'\bmodule\s+([A-Za-z0-9_$]+)'
)


# Yosys cell instance
#
# Examples:
#
# $_AND_ _123_ (
#
# \$_DFF_P_ \reg[0] (
#
instance_re = re.compile(
    r'^\s*(\\?\S+)\s+(\\?\S+)\s*\('
)


# Port connections
#
# .A(signal)
# .Y(net)
#
port_re = re.compile(
    r'\.([A-Za-z0-9_$]+)\(([^)]*)\)'
)



# ============================================================
# LABEL GENERATION
# ============================================================

def get_label(file):
    stem = file.stem.lower()
    tag = stem.replace("_netlist", "")

    if tag in {"clean", "tjfree"}:
        return 0
    if tag in {"trojan", "tjin"}:
        return 1
    if tag in {"standard", "90nm", "180nm"}:
        return 1   # confirmed via RS232-T100's README: these are Trojan-inserted variants
                    # with no separate clean baseline shipped in the same folder

    return -1


# ============================================================
# NETLIST PARSER
# ============================================================

def parse_netlist(file):

    with open(
        file,
        "r",
        encoding="utf-8",
        errors="ignore"
    ) as f:

        lines = f.readlines()


    module = None

    gates = []

    i = 0


    while i < len(lines):

        line = lines[i]


        # ----------------------------------------------------
        # Find module name
        # ----------------------------------------------------

        if module is None:

            match = module_re.search(line)

            if match:
                module = match.group(1)


        first_token = line.strip().split(" ", 1)[0].split("(")[0]

        if first_token.lower() in KEYWORDS:
            i += 1
            continue
        # ----------------------------------------------------
        # Find gate instances
        # ----------------------------------------------------

        match = instance_re.match(line)


        if match:

            gate_type = match.group(1)

            gate_name = match.group(2)

            block = line


            # collect until );
            while ");" not in block and i + 1 < len(lines):

                i += 1

                block += lines[i]



            ports = {}


            for p in port_re.finditer(block):

                port_name = p.group(1)

                signal = p.group(2).strip()


                ports[port_name] = signal



            gates.append(
                {
                    "type": gate_type,
                    "name": gate_name,
                    "ports": ports
                }
            )


        i += 1



    return {

        "module": module,

        "source": str(file),

        "label": get_label(file),

        "num_gates": len(gates),

        "gates": gates

    }



# ============================================================
# MAIN
# ============================================================


count = 0


failed = 0


for netlist in NETLIST_ROOT.rglob("*_netlist.v"):


    print("--------------------------------")

    print(netlist.name)



    try:


        data = parse_netlist(netlist)



        relative = netlist.relative_to(
            NETLIST_ROOT
        )


        output_file = OUTPUT_ROOT / relative.with_suffix(".json")



        output_file.parent.mkdir(
            parents=True,
            exist_ok=True
        )



        with open(
            output_file,
            "w",
            encoding="utf-8"
        ) as f:

            json.dump(
                data,
                f,
                indent=4
            )



        print(
            f"Module : {data['module']}"
        )

        print(
            f"Gates  : {data['num_gates']}"
        )

        print(
            f"Label  : {data['label']}"
        )

        print(
            f"Saved  : {output_file}"
        )


        count += 1



    except Exception as e:


        print(
            "FAILED:",
            e
        )

        failed += 1





print("\n================================")

print(
    "Netlists parsed :",
    count
)

print(
    "Failed          :",
    failed
)

print(
    "Output folder   :",
    OUTPUT_ROOT
)

print("================================")

#note :One thing worth flagging honestly before you move on: your class balance
#is skewed toward label 1. All 15 RS232 standard/90nm/180nm netlists
#are label 1 with no clean counterpart, plus 40-ish AES/RS232 Trojan
#netlists vs. matching clean ones — so you'll have noticeably more Trojan (1)
#samples than clean (0) samples overall. Not a blocker, but something
#to account for later (class weighting or stratified splitting) when you train the GNN
