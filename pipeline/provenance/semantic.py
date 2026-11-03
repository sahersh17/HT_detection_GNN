"""Versioned, bit-preserving constant and shared-memory graph view."""
import hashlib
import json
import re

import torch
from torch_geometric.data import Data

if __package__:
    from .build import CELL_EXCLUDE, graph_from_json
else:
    from build import CELL_EXCLUDE, graph_from_json

VERSION = "semantic_v1"
ROLES = ("cell", "net", "pin", "port", "parameter", "value_bit", "memory", "initial")
VALUES = ("0", "1", "x", "z")
DIRECTIONS = ("input", "output", "inout")
CELL_TYPES = tuple(sorted(set("""
$_AND_ $_OR_ $_XOR_ $_XNOR_ $_NOT_ $_BUF_ $_MUX_ $_NAND_ $_NOR_
$_ANDNOT_ $_ORNOT_ $_DFF_P_ $_DFF_N_ $_DFF_PN0_ $_DFF_PN1_
$_DFF_PP0_ $_DFF_PP1_ $_DFF_NN0_ $_DFF_NP0_
$_DFFE_PP_ $_DFFE_PN_ $_DFFE_PN0P_ $_DFFE_PN1P_
$_DFFE_PN0N_ $_DFFE_PN1N_ $_DFFE_PP0P_ $_DFFE_PP1P_ $_DFFE_PP0N_ $_DFFE_NN0P_
$_SDFF_PN0_ $_SDFF_PN1_ $_SDFF_PP0_ $_SDFF_PP1_
$_SDFFE_PN0P_ $_SDFFE_PN1P_ $_SDFFE_PP0P_ $_SDFFE_PP1P_
$_SDFFE_PN0N_ $_SDFFE_PP0N_ $_SDFFCE_PP0P_ $_SDFFCE_PP1P_
$_SDFFCE_PN0P_ $_SDFFCE_PN1P_ $_DLATCH_N_ $_DLATCH_P_ $_DLATCH_NP0_
$mem $mem_v2 $memrd $memrd_v2 $memwr $memwr_v2 $meminit $meminit_v2
$and $or $xor $not $mux $dff $adff $sdff $add $sub $mul $eq $lt $shiftx
and2 and3 and3b or2 or3 inv nand2 nand2b nand3 nand3b nand4
nor2 nor2b nor3 nor3b nor4 a21oi a22oi a31oi a211oi a221oi a21boi
a21o a211o o21ai o22ai o211ai o31a o21a sync
""".split())))
TYPE_INDEX = {name: index + 1 for index, name in enumerate(CELL_TYPES)}
ROLE_START = 20
VALUE_START = ROLE_START + len(ROLES)
DIRECTION_START = VALUE_START + len(VALUES)
POSITION_START = DIRECTION_START + len(DIRECTIONS)
WIDTH_START = POSITION_START + 32
SLOT_START = WIDTH_START + 32
TYPE_START = SLOT_START + 16
SIGN_INDEX = TYPE_START + 8
KIND_START = SIGN_INDEX + 1
NODE_DIM = KIND_START + 3
VECTOR_KINDS = ("connection", "parameter", "memory_field", "cell_initial")
LAYOUT = dict(legacy_gate_features=[0, 16], legacy_log_numeric=[16, 20],
              roles=[ROLE_START, len(ROLES)], values=[VALUE_START, len(VALUES)],
              directions=[DIRECTION_START, len(DIRECTIONS)], position=[POSITION_START, 32],
              width=[WIDTH_START, 32], slot=[SLOT_START, 16], cell_type=[TYPE_START, 8],
              sign=[SIGN_INDEX, 1], vector_kind=[KIND_START, 3])
SCHEMA_SHA256 = hashlib.sha256(json.dumps(dict(version=VERSION, layout=LAYOUT,
    cell_types=CELL_TYPES, roles=ROLES, values=VALUES, directions=DIRECTIONS,
    vector_kinds=VECTOR_KINDS), sort_keys=True).encode()).hexdigest()


def binary_features(value, width):
    if type(value) is not int or not 0 <= value < 1 << width:
        raise ValueError(f"Unsigned {width}-bit feature out of range: {value}")
    return [float((value >> bit) & 1) for bit in range(width)]


def decode_unsigned(features, start, width):
    values = features[start:start + width].tolist()
    if any(value not in (0.0, 1.0) for value in values):
        raise ValueError("Invalid integer feature encoding")
    return sum(int(value) << bit for bit, value in enumerate(values))


def memory_key(name):
    return str(name).removeprefix("\\")


def semantic_graph_from_json(document, top, graph_id, label, source_line_counts=None):
    module = document["modules"][top]
    cells = {name: cell for name, cell in module.get("cells", {}).items()
             if cell["type"].lower() not in CELL_EXCLUDE}
    names = sorted(cells)
    if names:
        base, metadata = graph_from_json(document, top, graph_id, label, source_line_counts)
    else:
        base = Data(x=torch.empty((0, 20)), edge_index=torch.empty((2, 0), dtype=torch.long))
        metadata = dict(node_names=[], node_types=[], node_gate_classes=[],
                        node_src=[], source_ranges=[])
    features = []
    edge_pairs = base.edge_index.T.tolist()
    edge_types = [0] * len(edge_pairs)
    node_names = list(metadata["node_names"])
    node_types = list(metadata["node_types"])
    gate_classes = list(metadata["node_gate_classes"])
    node_src = list(metadata["node_src"])
    spans = list(metadata["source_ranges"])
    vectors = []
    memory_bindings = []
    cell_index = {name: index for index, name in enumerate(names)}

    def feature(role, position=0, width=0, slot=0, value=None, direction=None, cell_type=None):
        row = [0.0] * NODE_DIM
        row[ROLE_START + ROLES.index(role)] = 1.0
        row[POSITION_START:POSITION_START + 32] = binary_features(position, 32)
        row[WIDTH_START:WIDTH_START + 32] = binary_features(width, 32)
        row[SLOT_START:SLOT_START + 16] = binary_features(slot, 16)
        if value is not None:
            if value not in VALUES:
                raise ValueError(f"Unsupported four-state bit: {value}")
            row[VALUE_START + VALUES.index(value)] = 1.0
        if direction is not None:
            row[DIRECTION_START + DIRECTIONS.index(direction)] = 1.0
        if cell_type is not None:
            if cell_type not in TYPE_INDEX:
                raise ValueError(f"Unsupported semantic cell type: {cell_type}")
            row[TYPE_START:TYPE_START + 8] = binary_features(TYPE_INDEX[cell_type], 8)
        return row

    for index, name in enumerate(names):
        row = feature("cell", cell_type=cells[name]["type"])
        row[:16] = base.x[index, :16].tolist()
        row[16:20] = torch.log1p(base.x[index, 16:20].clamp(min=0)).tolist()
        features.append(row)

    used_names = set(node_names)

    def add_node(row, role, owner=None):
        index = len(features)
        features.append(row)
        name = "$semantic$" + str(index)
        while name in used_names:
            name += "$"
        used_names.add(name)
        node_names.append(name)
        node_types.append("semantic_" + role)
        gate_classes.append("SEMANTIC")
        node_src.append(node_src[owner] if owner is not None else "")
        spans.append(spans[owner] if owner is not None else [])
        return index

    def connect(source, target, kind):
        edge_pairs.extend(((source, target), (target, source)))
        edge_types.extend((kind * 2, kind * 2 + 1))

    nets = {}

    def net_node(bit):
        if not ((type(bit) is int and bit >= 0) or (type(bit) is str and bit in VALUES)):
            raise ValueError(f"Unsupported net connection: {bit!r}")
        key = (type(bit).__name__, bit)
        if key not in nets:
            nets[key] = add_node(feature("net", value=bit if isinstance(bit, str) else None), "net")
        return nets[key]

    def vector(owner, name, slot, bits, kind, direction=None, number=False):
        bits = list(bits)
        role = "port" if kind == "connection" else "parameter"
        header = add_node(feature(role, width=len(bits), slot=slot, direction=direction), role, owner)
        features[header][KIND_START:KIND_START + 3] = binary_features(VECTOR_KINDS.index(kind), 3)
        connect(owner, header, 1 if kind == "connection" else 3)
        indices = []
        for position, bit in enumerate(bits):
            bit_role = "pin" if kind == "connection" else "value_bit"
            value = bit if isinstance(bit, str) else None
            node = add_node(feature(bit_role, position=position, value=value), bit_role, owner)
            connect(header, node, 1 if kind == "connection" else 3)
            if kind == "connection":
                connect(node, net_node(bit), 2)
            indices.append(node)
        vectors.append(dict(owner=owner, header=header, name=name, slot=slot,
                            kind=kind, bit_nodes=indices, direction=direction, number=number))
        return header

    memories = {}

    def memory_node(identifier):
        key = memory_key(identifier)
        if key not in memories:
            memories[key] = add_node(feature("memory"), "memory")
        return memories[key]

    def parameter(owner, name, slot, value, kind="parameter"):
        if isinstance(value, int):
            bits = list(reversed(format(abs(value), "b")))
            header = vector(owner, name, slot, bits, kind, number=True)
            features[header][SIGN_INDEX] = float(value < 0)
        elif isinstance(value, str) and re.fullmatch("[01xz]*", value):
            # Parameter strings are MSB-first, unlike connection arrays.
            vector(owner, name, slot, reversed(value), kind)
        else:
            raise ValueError(f"Unsupported semantic parameter {name}: {value!r}")

    for name in names:
        cell = cells[name]
        owner = cell_index[name]
        for slot, port in enumerate(sorted(cell["connections"])):
            if port not in cell["port_directions"]:
                raise ValueError(f"Missing pin direction: {name}/{port}")
            vector(owner, port, slot, cell["connections"][port], "connection",
                   cell["port_directions"][port])
        for slot, key in enumerate(sorted(cell.get("parameters", {}))):
            value = cell["parameters"][key]
            if key == "MEMID":
                target = memory_node(value)
                connect(owner, target, 4)
                memory_bindings.append(dict(cell=owner, memory=target, identifier=memory_key(value)))
            else:
                parameter(owner, key, slot, value)
        if "init" in cell.get("attributes", {}):
            parameter(owner, "init", 0, cell["attributes"]["init"], "cell_initial")

    declared = set()
    for name, memory in module.get("memories", {}).items():
        key = memory_key(name)
        if key in declared:
            raise ValueError("Ambiguous canonical memory identifier")
        declared.add(key)
        owner = memory_node(name)
        fields = {k: v for k, v in memory.items() if k not in ("attributes", "hide_name")}
        if "init" in memory.get("attributes", {}):
            fields["attribute:init"] = memory["attributes"]["init"]
        for slot, name in enumerate(sorted(fields)):
            parameter(owner, name, slot, fields[name], "memory_field")

    for slot, name in enumerate(sorted(module.get("ports", {}))):
        port = module["ports"][name]
        owner = add_node(feature("port", slot=slot, direction=port["direction"]), "port")
        vector(owner, name, slot, port["bits"], "connection", port["direction"])

    initial_bits = []
    for name, net in module.get("netnames", {}).items():
        initial = net.get("attributes", {}).get("init")
        if initial is None:
            continue
        if not isinstance(initial, str) or len(initial) != len(net["bits"]):
            raise ValueError(f"Initialization width mismatch: {name}")
        for position, (bit, value) in enumerate(zip(net["bits"], reversed(initial))):
            node = add_node(feature("initial", value=value), "initial")
            target = net_node(bit)
            connect(node, target, 5)
            initial_bits.append(dict(node=node, net=target, signal=name, position=position))

    if not features:
        raise ValueError("Empty design has no representable cells, memories or ports")
    graph = Data(x=torch.tensor(features, dtype=torch.float32),
                 edge_index=torch.tensor(edge_pairs, dtype=torch.long).T.contiguous()
                 if edge_pairs else torch.empty((2, 0), dtype=torch.long),
                 edge_type=torch.tensor(edge_types, dtype=torch.long),
                 y=torch.tensor([label], dtype=torch.long))
    graph.graph_id = graph_id
    graph.n_cell = len(names)
    graph.representation = VERSION
    metadata.update(graph_id=graph_id, label=label, representation=VERSION,
                    node_dim=NODE_DIM, cell_types=list(CELL_TYPES), feature_layout=LAYOUT,
                    schema_sha256=SCHEMA_SHA256, num_nodes=graph.num_nodes,
                    num_edges=graph.num_edges, node_names=node_names, node_types=node_types,
                    node_gate_classes=gate_classes, node_src=node_src, source_ranges=spans,
                    source_covered_nodes=sum(bool(value) for value in spans),
                    raw_src_nodes=sum(bool(value) for value in node_src), reviewed=False,
                    node_names_sha256=hashlib.sha256(json.dumps(node_names, ensure_ascii=False,
                        separators=(",", ":")).encode()).hexdigest(),
                    vectors=vectors, memory_bindings=memory_bindings, initial_bits=initial_bits,
                    memory_nodes=[dict(node=node, identifier=key) for key, node in memories.items()],
                    net_nodes=[dict(node=node, bit=key[1]) for key, node in nets.items()])
    return graph, metadata


def decode_vector(graph, record):
    width = decode_unsigned(graph.x[record["header"]], WIDTH_START, 32)
    if width != len(record["bit_nodes"]):
        raise ValueError("Vector width differs from model features")
    bits = [None] * width
    occupied = set()
    for node in record["bit_nodes"]:
        position = decode_unsigned(graph.x[node], POSITION_START, 32)
        if position >= width or position in occupied:
            raise ValueError("Duplicate or out-of-range bit position")
        occupied.add(position)
        values = graph.x[node, VALUE_START:VALUE_START + 4].tolist()
        if sum(values) != 1.0:
            if record["kind"] == "connection" and sum(values) == 0.0:
                continue
            raise ValueError("Invalid bit value encoding")
        bits[position] = VALUES[values.index(1.0)]
    if record["kind"] == "connection":
        return bits
    if record["number"]:
        magnitude = int("".join(reversed(bits)), 2)
        return -magnitude if graph.x[record["header"], SIGN_INDEX] else magnitude
    return "".join(reversed(bits))

def verify_semantic_values(document, top, graph, metadata):
    """Reconstruct semantic values from model tensors and check their attachments."""
    module = document["modules"][top]
    edge_set = set(map(tuple, graph.edge_index.T.tolist()))
    net_nodes = {(type(row["bit"]).__name__, row["bit"]): row["node"]
                 for row in metadata["net_nodes"]}
    memory_ids = {row["node"]: row["identifier"] for row in metadata["memory_nodes"]}
    memory_fields = {}
    for name, memory in module.get("memories", {}).items():
        fields = {key: value for key, value in memory.items()
                  if key not in ("attributes", "hide_name")}
        if "init" in memory.get("attributes", {}):
            fields["attribute:init"] = memory["attributes"]["init"]
        memory_fields[memory_key(name)] = fields
    cells = [cell for cell in module.get("cells", {}).values()
             if cell["type"].lower() not in CELL_EXCLUDE]
    expected_vectors = sum(len(cell["connections"]) + len(cell.get("parameters", {}))
                           - int("MEMID" in cell.get("parameters", {}))
                           + int("init" in cell.get("attributes", {})) for cell in cells)
    expected_vectors += len(module.get("ports", {})) + sum(map(len, memory_fields.values()))
    keys = [(row["owner"], row["kind"], row["name"]) for row in metadata["vectors"]]
    if len(keys) != expected_vectors or len(set(keys)) != len(keys):
        raise ValueError("Missing or duplicated semantic vectors")
    if len(metadata["memory_bindings"]) != sum("MEMID" in cell.get("parameters", {}) for cell in cells):
        raise ValueError("Missing memory operation binding")
    if len(metadata["initial_bits"]) != sum(len(net["bits"]) for net in module.get("netnames", {}).values()
                                            if "init" in net.get("attributes", {})):
        raise ValueError("Missing net initialization bits")
    checked_bits = 0
    for record in metadata["vectors"]:
        owner = record["owner"]
        if (owner, record["header"]) not in edge_set:
            raise ValueError("Detached semantic vector")
        if decode_unsigned(graph.x[record["header"]], SLOT_START, 16) != record["slot"]:
            raise ValueError("Incorrect port/parameter slot")
        if decode_unsigned(graph.x[record["header"]], KIND_START, 3) != VECTOR_KINDS.index(record["kind"]):
            raise ValueError("Incorrect semantic vector kind")
        for node in record["bit_nodes"]:
            if (record["header"], node) not in edge_set:
                raise ValueError("Detached semantic bit")
        actual = decode_vector(graph, record)
        kind, name = record["kind"], record["name"]
        if kind == "connection":
            if owner < graph.n_cell:
                cell = module["cells"][metadata["node_names"][owner]]
                source = cell["connections"][name]
                direction = cell["port_directions"][name]
                slot = sorted(cell["connections"]).index(name)
            else:
                source = module["ports"][name]["bits"]
                direction = module["ports"][name]["direction"]
                slot = sorted(module["ports"]).index(name)
            if slot != record["slot"] or graph.x[record["header"], DIRECTION_START:DIRECTION_START+3].tolist() != [
                    float(direction == value) for value in DIRECTIONS]:
                raise ValueError("Pin identity/direction mismatch")
            expected = [value if isinstance(value, str) else None for value in source]
            if actual != expected:
                raise ValueError("Constant connection bit mismatch")
            for node in record["bit_nodes"]:
                position = decode_unsigned(graph.x[node], POSITION_START, 32)
                bit = source[position]
                if (node, net_nodes[type(bit).__name__, bit]) not in edge_set:
                    raise ValueError("Pin connected to incorrect net/constant")
        elif kind == "memory_field":
            if actual != memory_fields[memory_ids[owner]][name]:
                raise ValueError("Memory declaration mismatch")
        else:
            cell = module["cells"][metadata["node_names"][owner]]
            source = cell["attributes"] if kind == "cell_initial" else cell["parameters"]
            if actual != source[name]:
                raise ValueError("Cell parameter/initialization mismatch")
        checked_bits += len(record["bit_nodes"])
    for binding in metadata["memory_bindings"]:
        cell = module["cells"][metadata["node_names"][binding["cell"]]]
        if memory_key(cell["parameters"]["MEMID"]) != memory_ids[binding["memory"]]:
            raise ValueError("Memory state identity mismatch")
        if (binding["cell"], binding["memory"]) not in edge_set:
            raise ValueError("Detached memory operation")
    for record in metadata["initial_bits"]:
        initial = module["netnames"][record["signal"]]["attributes"]["init"]
        expected = initial[-1-record["position"]]
        vector = graph.x[record["node"], VALUE_START:VALUE_START + 4].tolist()
        if vector != [float(expected == value) for value in VALUES]:
            raise ValueError("Net initial value mismatch")
        if (record["node"], record["net"]) not in edge_set:
            raise ValueError("Detached net initial value")
    return dict(vectors=len(metadata["vectors"]), bits=checked_bits,
                memory_operations=len(metadata["memory_bindings"]),
                memory_states=len(metadata["memory_nodes"]), initial_bits=len(metadata["initial_bits"]))
