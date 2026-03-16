#!/usr/bin/env python3
"""
bpmn_maker.py — Production-quality BPMN 2.0 generator from JSON definitions.

v4.0 — Major improvements:
  - Smart port selection (top/bottom/left/right based on flow direction)
  - Overlap-aware edge routing with obstacle avoidance
  - Dynamic label sizing based on text length
  - Parallel path vertical distribution
  - Boundary events (interrupting/non-interrupting)
  - Text annotations & data objects
  - Pool width normalization in collaborations
  - Backward loop routing via lane boundaries
"""

import json
import sys
import math
import xml.etree.ElementTree as ET
from xml.dom import minidom
from collections import deque

# ── Namespace helpers ──────────────────────────────────────────────────────────

NS = {
    "bpmn": "http://www.omg.org/spec/BPMN/20100524/MODEL",
    "bpmndi": "http://www.omg.org/spec/BPMN/20100524/DI",
    "dc": "http://www.omg.org/spec/DD/20100524/DC",
    "di": "http://www.omg.org/spec/DD/20100524/DI",
    "xsi": "http://www.w3.org/2001/XMLSchema-instance",
}

def bpmn(tag):
    return f"{{{NS['bpmn']}}}{tag}"

def bpmndi(tag):
    return f"{{{NS['bpmndi']}}}{tag}"

def dc(tag):
    return f"{{{NS['dc']}}}{tag}"

def di(tag):
    return f"{{{NS['di']}}}{tag}"


# ── Element type mappings ──────────────────────────────────────────────────────

TYPE_INFO = {
    # Events
    "StartEvent":              ("startEvent",              36, 36),
    "EndEvent":                ("endEvent",                36, 36),
    "IntermediateCatchEvent":  ("intermediateCatchEvent",  36, 36),
    "IntermediateThrowEvent":  ("intermediateThrowEvent",  36, 36),
    "MessageStartEvent":       ("startEvent",              36, 36),
    "TimerStartEvent":         ("startEvent",              36, 36),
    "BoundaryEvent":           ("boundaryEvent",           36, 36),
    "BoundaryTimerEvent":      ("boundaryEvent",           36, 36),
    "BoundaryMessageEvent":    ("boundaryEvent",           36, 36),
    # Tasks
    "Task":                    ("task",                   100, 80),
    "UserTask":                ("userTask",               100, 80),
    "ServiceTask":             ("serviceTask",            100, 80),
    "SendTask":                ("sendTask",               100, 80),
    "ReceiveTask":             ("receiveTask",            100, 80),
    "ManualTask":              ("manualTask",             100, 80),
    "ScriptTask":              ("scriptTask",             100, 80),
    "BusinessRuleTask":        ("businessRuleTask",       100, 80),
    "CallActivity":            ("callActivity",           100, 80),
    # Gateways
    "ExclusiveGateway":        ("exclusiveGateway",        50, 50),
    "ParallelGateway":         ("parallelGateway",         50, 50),
    "EventBasedGateway":       ("eventBasedGateway",       50, 50),
    "InclusiveGateway":        ("inclusiveGateway",        50, 50),
    # Sub-process
    "SubProcess":              ("subProcess",             350, 200),
    # Annotations
    "TextAnnotation":          ("textAnnotation",         100, 30),
    # Data
    "DataObjectReference":     ("dataObjectReference",     36, 50),
    "DataStoreReference":      ("dataStoreReference",      50, 50),
}

EVENT_DEF_MAP = {
    "message":     "messageEventDefinition",
    "timer":       "timerEventDefinition",
    "conditional": "conditionalEventDefinition",
    "signal":      "signalEventDefinition",
    "error":       "errorEventDefinition",
    "escalation":  "escalationEventDefinition",
    "compensation": "compensateEventDefinition",
    "cancel":      "cancelEventDefinition",
    "link":        "linkEventDefinition",
    "terminate":   "terminateEventDefinition",
}

# ── Layout constants ───────────────────────────────────────────────────────────

X_SPACING = 180          # horizontal gap between columns
Y_NODE_SPACING = 110     # vertical gap between stacked nodes in same column
BASE_X = 250             # first column X inside a pool/lane
POOL_PADDING_X = 150     # right-side padding for pool width
POOL_GAP = 80            # vertical gap between pools
LANE_PAD_TOP = 30        # top padding inside a lane
LANE_PAD_BOTTOM = 20     # bottom padding inside a lane
POOL_HEADER = 30         # width of the pool's left label band
MIN_LANE_HEIGHT = 140    # minimum lane height
SUBPROCESS_PAD = 40      # padding inside a sub-process box
EDGE_CLEARANCE = 30      # clearance around elements for edge routing
BOUNDARY_OFFSET_Y = -18  # y offset for boundary events relative to task bottom


# ── Utility ────────────────────────────────────────────────────────────────────

_id_counter = [0]

def _next_id(prefix="id"):
    _id_counter[0] += 1
    return f"{prefix}_{_id_counter[0]}"


# ── Topological depth assignment (cycle-aware) ────────────────────────────────

def _detect_back_edges(node_ids, outgoing, start_nodes=None):
    """Detect back-edges using DFS to identify cycles.

    start_nodes: preferred DFS roots (start events) to ensure correct traversal order.
    Returns set of (source, target) tuples.
    """
    WHITE, GRAY, BLACK = 0, 1, 2
    color = {nid: WHITE for nid in node_ids}
    back_edges = set()

    def dfs(u):
        color[u] = GRAY
        for v in outgoing.get(u, []):
            if v not in color:
                continue
            if color[v] == GRAY:
                back_edges.add((u, v))
            elif color[v] == WHITE:
                dfs(v)
        color[u] = BLACK

    # Start DFS from start events first (critical for correct back-edge detection)
    if start_nodes:
        for nid in start_nodes:
            if nid in color and color[nid] == WHITE:
                dfs(nid)

    # Then any remaining unvisited nodes
    for nid in node_ids:
        if color[nid] == WHITE:
            dfs(nid)

    return back_edges


def compute_depths(nodes, edges):
    """Return dict node_id -> depth (column index) using longest-path on the DAG.

    Backward edges (loops) are detected and excluded so they don't inflate
    depths of downstream nodes.
    """
    node_ids = {n["id"] for n in nodes if n.get("type") not in
                ("BoundaryEvent", "BoundaryTimerEvent", "BoundaryMessageEvent",
                 "TextAnnotation", "DataObjectReference", "DataStoreReference")}

    # Identify start events for DFS root prioritization
    start_nodes = [n["id"] for n in nodes
                   if n.get("type", "").endswith("StartEvent") and n["id"] in node_ids]

    # Build full adjacency
    full_outgoing = {nid: [] for nid in node_ids}
    for e in edges:
        s, t = e["source"], e["target"]
        if s in node_ids and t in node_ids:
            full_outgoing[s].append(t)

    # Detect backward edges (cycles) starting from start events
    back_edges = _detect_back_edges(node_ids, full_outgoing, start_nodes)

    # Build DAG adjacency (no back-edges)
    outgoing = {nid: [] for nid in node_ids}
    in_degree = {nid: 0 for nid in node_ids}

    for e in edges:
        s, t = e["source"], e["target"]
        if s in node_ids and t in node_ids and (s, t) not in back_edges:
            outgoing[s].append(t)
            in_degree[t] += 1

    # Longest path via Kahn's topological sort on the DAG
    depths = {nid: 0 for nid in node_ids}
    queue = deque(nid for nid, deg in in_degree.items() if deg == 0)
    if not queue and node_ids:
        # Fallback: pick start events first, then any node
        starts = [n["id"] for n in nodes if n.get("type", "").endswith("StartEvent") and n["id"] in node_ids]
        queue.append(starts[0] if starts else next(iter(node_ids)))

    visited = set()
    while queue:
        nid = queue.popleft()
        if nid in visited:
            continue
        visited.add(nid)
        for child in outgoing[nid]:
            new_depth = depths[nid] + 1
            if new_depth > depths.get(child, 0):
                depths[child] = new_depth
            in_degree[child] -= 1
            if in_degree[child] <= 0 and child not in visited:
                queue.append(child)

    # Handle any unvisited nodes
    for nid in node_ids:
        if nid not in visited:
            depths[nid] = max(depths.values(), default=0) + 1

    return depths


def compute_row_offsets(nodes, depths):
    """For nodes sharing the same (lane, depth), assign vertical row offsets."""
    lane_depth_counts = {}
    offsets = {}
    for n in nodes:
        nid = n["id"]
        if nid not in depths:
            continue
        lane = n.get("lane", "default")
        d = depths.get(nid, 0)
        key = (lane, d)
        count = lane_depth_counts.get(key, 0)
        offsets[nid] = count
        lane_depth_counts[key] = count + 1
    return offsets, lane_depth_counts


# ── Build adjacency helpers ───────────────────────────────────────────────────

def build_adjacency(nodes, edges):
    node_ids = {n["id"] for n in nodes}
    incoming_e = {nid: [] for nid in node_ids}
    outgoing_e = {nid: [] for nid in node_ids}
    for e in edges:
        eid = e["id"]
        s, t = e["source"], e["target"]
        if s in node_ids:
            outgoing_e[s].append(eid)
        if t in node_ids:
            incoming_e[t].append(eid)
    return incoming_e, outgoing_e


# ── Port selection logic ──────────────────────────────────────────────────────

def _get_ports(info):
    """Calculate the 4 connection ports for an element."""
    return {
        "right":  (info["right_x"],  info["center_y"]),
        "left":   (info["left_x"],   info["center_y"]),
        "top":    (info["center_x"], info["top_y"]),
        "bottom": (info["center_x"], info["bottom_y"]),
    }


def _select_ports(src_info, tgt_info, src_id, tgt_id, edge, all_edges, all_layout):
    """
    Intelligently select source and target ports based on the flow direction
    and the relationship between the elements (same lane, cross-lane, backward, etc.)
    """
    src_ports = _get_ports(src_info)
    tgt_ports = _get_ports(tgt_info)

    sx_center = src_info["center_x"]
    sy_center = src_info["center_y"]
    tx_center = tgt_info["center_x"]
    ty_center = tgt_info["center_y"]

    is_forward = sx_center < tx_center
    is_backward = sx_center > tx_center + 10
    is_same_y = abs(sy_center - ty_center) < 15
    is_cross_lane_down = ty_center > sy_center + 30
    is_cross_lane_up = ty_center < sy_center - 30
    is_gateway_src = src_info.get("is_gateway", False)

    if is_backward:
        # Backward loop — always exit right, enter left, we'll wrap around
        return "right", "left"

    if is_forward:
        if is_same_y:
            return "right", "left"

        if is_gateway_src:
            # Gateway branching: use top/bottom exits
            # Count outgoing edges to determine branch assignment
            outgoing_edges = [e for e in all_edges if e["source"] == src_id]
            if len(outgoing_edges) >= 2:
                # Determine this edge's branch index
                edge_idx = next((i for i, e in enumerate(outgoing_edges) if e["id"] == edge["id"]), 0)

                if len(outgoing_edges) == 2:
                    # 2 branches: one right, one top or bottom
                    if edge_idx == 0:
                        # First branch: maintain horizontal or go up/down based on target position
                        if is_cross_lane_down:
                            return "bottom", "left"
                        elif is_cross_lane_up:
                            return "top", "left"
                        else:
                            return "right", "left"
                    else:
                        if is_cross_lane_down:
                            return "bottom", "left"
                        elif is_cross_lane_up:
                            return "top", "left"
                        else:
                            return "right", "left"
                elif len(outgoing_edges) == 3:
                    # 3 branches: top, right, bottom
                    if edge_idx == 0:
                        return "top", "left"
                    elif edge_idx == 1:
                        return "right", "left"
                    else:
                        return "bottom", "left"
                else:
                    # 4+ branches
                    if edge_idx == 0:
                        return "top", "left"
                    elif edge_idx == len(outgoing_edges) - 1:
                        return "bottom", "left"
                    else:
                        return "right", "left"

        # Non-gateway forward cross-lane
        if is_cross_lane_down:
            return "bottom", "top" if abs(sx_center - tx_center) < 50 else "left"
        elif is_cross_lane_up:
            return "top", "bottom" if abs(sx_center - tx_center) < 50 else "left"

        # Default forward
        return "right", "left"

    # Directly below/above (same X)
    if is_cross_lane_down:
        return "bottom", "top"
    elif is_cross_lane_up:
        return "top", "bottom"

    return "right", "left"


# ── Overlap detection ─────────────────────────────────────────────────────────

def _rects_overlap(x, y, w, h, bx, by, bw, bh, margin=0):
    """Check if two rectangles overlap (with optional margin)."""
    return not (x + w + margin <= bx or bx + bw + margin <= x or
                y + h + margin <= by or by + bh + margin <= y)


def _segment_crosses_element(x1, y1, x2, y2, elem_info, margin=10):
    """Check if a line segment passes through an element's bounding box."""
    ex, ey = elem_info["x"], elem_info["y"]
    ew, eh = elem_info["width"], elem_info["height"]

    # Expand the element bounds by margin
    rx = ex - margin
    ry = ey - margin
    rw = ew + margin * 2
    rh = eh + margin * 2

    # Line segment bounding box
    lx = min(x1, x2)
    ly = min(y1, y2)
    lw = abs(x2 - x1)
    lh = abs(y2 - y1)

    # Quick rejection
    if not _rects_overlap(lx, ly, lw, lh, rx, ry, rw, rh):
        return False

    # For orthogonal segments (our main case), more precise check
    if abs(x1 - x2) < 2:  # Vertical segment
        return rx <= x1 <= rx + rw and not (max(y1, y2) < ry or min(y1, y2) > ry + rh)
    if abs(y1 - y2) < 2:  # Horizontal segment
        return ry <= y1 <= ry + rh and not (max(x1, x2) < rx or min(x1, x2) > rx + rw)

    return True


def _check_route_overlaps(waypoints, layout_info, exclude_ids):
    """Check if any segment in the route overlaps with elements."""
    for i in range(len(waypoints) - 1):
        x1, y1 = waypoints[i]
        x2, y2 = waypoints[i + 1]
        for nid, info in layout_info.items():
            if nid in exclude_ids:
                continue
            if _segment_crosses_element(x1, y1, x2, y2, info):
                return True, nid
    return False, None


# ── Sub-process layout ────────────────────────────────────────────────────────

def layout_subprocess(sp_node, sp_x, sp_y):
    """Compute inner layout of a sub-process and return (width, height, inner_layout)."""
    inner_nodes = sp_node.get("nodes", [])
    inner_edges = sp_node.get("edges", [])
    if not inner_nodes:
        return 350, 200, {}

    depths = compute_depths(inner_nodes, inner_edges)
    offsets, ld_counts = compute_row_offsets(inner_nodes, depths)
    max_depth = max(depths.values(), default=0)

    inner_layout = {}
    inner_x_base = sp_x + SUBPROCESS_PAD
    inner_y_base = sp_y + SUBPROCESS_PAD

    for n in inner_nodes:
        nid = n["id"]
        if nid not in depths:
            continue
        ntype = n.get("type", "Task")
        _, w, h = TYPE_INFO.get(ntype, ("task", 100, 80))
        d = depths[nid]
        offset = offsets[nid]
        col_center = inner_x_base + d * 140 + 50
        nx = col_center - w / 2
        ny = inner_y_base + offset * 90 + (90 - h) / 2
        inner_layout[nid] = _make_layout_entry(nx, ny, w, h, ntype)

    # Calculate sub-process bounds
    max_stacked = max(ld_counts.values(), default=1)
    sp_w = max((max_depth + 1) * 140 + SUBPROCESS_PAD * 2, 350)
    sp_h = max(max_stacked * 90 + SUBPROCESS_PAD * 2, 200)
    return sp_w, sp_h, inner_layout


def _make_layout_entry(x, y, w, h, ntype="Task"):
    """Create a layout info dict with all port positions."""
    entry = {
        "x": x, "y": y, "width": w, "height": h,
        "center_x": x + w / 2, "center_y": y + h / 2,
        "right_x": x + w, "left_x": x,
        "top_y": y, "bottom_y": y + h,
        "is_gateway": "Gateway" in ntype if ntype else False,
        "is_event": "Event" in ntype if ntype else False,
    }
    return entry


# ── Main BPMN model builder ──────────────────────────────────────────────────

def add_event_definition(elem, node):
    """Add event definition child elements if specified."""
    evt_def = node.get("event_definition")
    evt_type = node.get("type", "")

    # Auto-detect from type name
    if not evt_def:
        if evt_type == "MessageStartEvent":
            evt_def = {"type": "message"}
        elif evt_type == "TimerStartEvent":
            evt_def = {"type": "timer"}
        elif evt_type == "BoundaryTimerEvent":
            evt_def = {"type": "timer"}
        elif evt_type == "BoundaryMessageEvent":
            evt_def = {"type": "message"}

    if not evt_def:
        return

    def_type = evt_def.get("type", "message")
    xml_tag = EVENT_DEF_MAP.get(def_type)
    if not xml_tag:
        return

    def_id = _next_id("EventDef")
    def_elem = ET.SubElement(elem, bpmn(xml_tag), id=def_id)

    if def_type == "timer":
        duration = evt_def.get("duration")
        if duration:
            td = ET.SubElement(def_elem, bpmn("timeDuration"))
            td.set(f"{{{NS['xsi']}}}type", "bpmn:tFormalExpression")
            td.text = duration
        time_date = evt_def.get("timeDate")
        if time_date:
            td = ET.SubElement(def_elem, bpmn("timeDate"))
            td.set(f"{{{NS['xsi']}}}type", "bpmn:tFormalExpression")
            td.text = time_date
        time_cycle = evt_def.get("timeCycle")
        if time_cycle:
            tc = ET.SubElement(def_elem, bpmn("timeCycle"))
            tc.set(f"{{{NS['xsi']}}}type", "bpmn:tFormalExpression")
            tc.text = time_cycle
    elif def_type == "conditional":
        cond = ET.SubElement(def_elem, bpmn("condition"))
        cond.set(f"{{{NS['xsi']}}}type", "bpmn:tFormalExpression")
        expr = evt_def.get("expression", "")
        if expr:
            cond.text = expr


def build_process_elements(process_elem, plane, nodes, edges, layout_info,
                           lanes_data=None, all_subprocess_layouts=None,
                           associations=None):
    """Add BPMN elements (nodes + edges) to a process and their DI shapes to the plane."""
    incoming_e, outgoing_e = build_adjacency(nodes, edges)

    # Lane set
    if lanes_data:
        lane_set_el = ET.SubElement(process_elem, bpmn("laneSet"),
                                    id=f"LaneSet_{process_elem.get('id')}")
        for lane in lanes_data:
            lane_el = ET.SubElement(lane_set_el, bpmn("lane"),
                                   id=lane["id"], name=lane.get("name", lane["id"]))
            lane["_element"] = lane_el

    # Nodes
    for node in nodes:
        nid = node["id"]
        ntype = node.get("type", "Task")
        nname = node.get("name", "")
        bpmn_tag, _, _ = TYPE_INFO.get(ntype, ("task", 100, 80))
        info = layout_info.get(nid)
        if not info:
            continue

        # Register in lane
        if lanes_data and ntype not in ("TextAnnotation", "DataObjectReference", "DataStoreReference"):
            node_lane = node.get("lane", "default")
            for ld in lanes_data:
                if ld["id"] == node_lane and "_element" in ld:
                    ET.SubElement(ld["_element"], bpmn("flowNodeRef")).text = nid
                    break

        # Create semantic element
        attrs = {"id": nid, "name": nname}

        # Boundary events
        if ntype in ("BoundaryEvent", "BoundaryTimerEvent", "BoundaryMessageEvent"):
            attached_to = node.get("attachedTo", "")
            if attached_to:
                attrs["attachedToRef"] = attached_to
            cancel_activity = node.get("cancelActivity", "true")
            if cancel_activity == "false":
                attrs["cancelActivity"] = "false"

        # Text annotation
        if ntype == "TextAnnotation":
            elem = ET.SubElement(process_elem, bpmn(bpmn_tag), id=nid)
            text_el = ET.SubElement(elem, bpmn("text"))
            text_el.text = node.get("text", nname)
        elif ntype in ("DataObjectReference", "DataStoreReference"):
            elem = ET.SubElement(process_elem, bpmn(bpmn_tag), **attrs)
        else:
            elem = ET.SubElement(process_elem, bpmn(bpmn_tag), **attrs)

        # Event definitions
        if ntype not in ("TextAnnotation", "DataObjectReference", "DataStoreReference"):
            add_event_definition(elem, node)

        # Default flow for gateways
        default_flow = node.get("default_flow")
        if default_flow and "Gateway" in ntype:
            elem.set("default", default_flow)

        # Incoming / outgoing refs
        if ntype not in ("TextAnnotation", "DataObjectReference", "DataStoreReference",
                         "BoundaryEvent", "BoundaryTimerEvent", "BoundaryMessageEvent"):
            for eid in incoming_e.get(nid, []):
                ET.SubElement(elem, bpmn("incoming")).text = eid
            for eid in outgoing_e.get(nid, []):
                ET.SubElement(elem, bpmn("outgoing")).text = eid
        elif ntype in ("BoundaryEvent", "BoundaryTimerEvent", "BoundaryMessageEvent"):
            # Boundary events only have outgoing
            for eid in outgoing_e.get(nid, []):
                ET.SubElement(elem, bpmn("outgoing")).text = eid

        # Sub-process inner elements
        if ntype == "SubProcess" and "nodes" in node:
            inner_layout = (all_subprocess_layouts or {}).get(nid, {})
            inner_ie, inner_oe = build_adjacency(node["nodes"], node.get("edges", []))

            for inner_n in node["nodes"]:
                inid = inner_n["id"]
                intype = inner_n.get("type", "Task")
                inname = inner_n.get("name", "")
                in_tag, _, _ = TYPE_INFO.get(intype, ("task", 100, 80))
                in_info = inner_layout.get(inid)
                if not in_info:
                    continue

                in_elem = ET.SubElement(elem, bpmn(in_tag), id=inid, name=inname)
                add_event_definition(in_elem, inner_n)
                for eid in inner_ie.get(inid, []):
                    ET.SubElement(in_elem, bpmn("incoming")).text = eid
                for eid in inner_oe.get(inid, []):
                    ET.SubElement(in_elem, bpmn("outgoing")).text = eid

                # DI shape for inner node
                shape_attrs = {"id": f"{inid}_di", "bpmnElement": inid}
                shape = ET.SubElement(plane, bpmndi("BPMNShape"), **shape_attrs)
                ET.SubElement(shape, dc("Bounds"),
                              x=str(int(in_info["x"])), y=str(int(in_info["y"])),
                              width=str(int(in_info["width"])), height=str(int(in_info["height"])))
                if in_tag.endswith("Event") or in_tag.endswith("Gateway"):
                    _add_label(shape, in_info, inname)

            # Inner sequence flows
            for ie in node.get("edges", []):
                ie_id = ie["id"]
                ET.SubElement(elem, bpmn("sequenceFlow"),
                              id=ie_id, sourceRef=ie["source"],
                              targetRef=ie["target"], name=ie.get("name", ""))
                _add_edge_di(plane, ie, inner_layout, node.get("edges", []))

        # DI shape
        shape_attrs = {"id": f"{nid}_di", "bpmnElement": nid}
        if ntype == "SubProcess":
            shape_attrs["isExpanded"] = "true"
        shape = ET.SubElement(plane, bpmndi("BPMNShape"), **shape_attrs)
        if ntype in ("ExclusiveGateway", "InclusiveGateway"):
            shape.set("isMarkerVisible", "true")
        ET.SubElement(shape, dc("Bounds"),
                      x=str(int(info["x"])), y=str(int(info["y"])),
                      width=str(int(info["width"])), height=str(int(info["height"])))
        if bpmn_tag.endswith("Event") or bpmn_tag.endswith("Gateway"):
            _add_label(shape, info, nname)

    # Sequence flows
    for edge in edges:
        eid = edge["id"]
        ET.SubElement(process_elem, bpmn("sequenceFlow"),
                      id=eid, sourceRef=edge["source"],
                      targetRef=edge["target"], name=edge.get("name", ""))
        _add_edge_di(plane, edge, layout_info, edges)

    # Associations (for text annotations)
    if associations:
        for assoc in associations:
            aid = assoc["id"]
            attrs = {
                "id": aid,
                "sourceRef": assoc["source"],
                "targetRef": assoc["target"],
            }
            if assoc.get("direction"):
                attrs["associationDirection"] = assoc["direction"]
            ET.SubElement(process_elem, bpmn("association"), **attrs)
            # DI for association
            src = layout_info.get(assoc["source"])
            tgt = layout_info.get(assoc["target"])
            if src and tgt:
                edge_di = ET.SubElement(plane, bpmndi("BPMNEdge"),
                                        id=f"{aid}_di", bpmnElement=aid)
                ET.SubElement(edge_di, di("waypoint"),
                              x=str(int(src["center_x"])), y=str(int(src["center_y"])))
                ET.SubElement(edge_di, di("waypoint"),
                              x=str(int(tgt["center_x"])), y=str(int(tgt["center_y"])))


def _add_label(shape, info, name=""):
    """Add a label element positioned below the element."""
    label = ET.SubElement(shape, bpmndi("BPMNLabel"))
    # Dynamic label width based on text length
    text_len = len(name) if name else 0
    label_w = max(text_len * 7, 40)
    lx = info["center_x"] - label_w / 2
    ly = info["bottom_y"] + 4
    # Multi-line labels for longer text
    label_h = 14 if text_len <= 15 else 27
    ET.SubElement(label, dc("Bounds"),
                  x=str(int(lx)), y=str(int(ly)),
                  width=str(int(label_w)),
                  height=str(int(label_h)))


def _add_edge_di(plane, edge, layout_info, all_edges=None):
    """Add DI edge element with smart port selection and routing."""
    eid = edge["id"]
    source_ref = edge["source"]
    target_ref = edge["target"]
    edge_name = edge.get("name", "")

    src = layout_info.get(source_ref)
    tgt = layout_info.get(target_ref)
    if not src or not tgt:
        return

    edge_di = ET.SubElement(plane, bpmndi("BPMNEdge"),
                            id=f"{eid}_di", bpmnElement=eid)

    waypoints = _compute_smart_waypoints(src, tgt, source_ref, target_ref,
                                          edge, all_edges or [], layout_info)
    for wx, wy in waypoints:
        ET.SubElement(edge_di, di("waypoint"), x=str(int(wx)), y=str(int(wy)))

    if edge_name:
        _add_edge_label(edge_di, waypoints, edge_name, src)


def _compute_smart_waypoints(src, tgt, src_id, tgt_id, edge, all_edges, all_layout):
    """Compute orthogonal waypoints using smart port selection."""
    # Self-loop
    if src_id == tgt_id:
        sx, sy = src["right_x"], src["center_y"]
        return [(sx, sy), (sx + 40, sy), (sx + 40, sy - 60),
                (src["left_x"] - 40, sy - 60), (src["left_x"] - 40, sy), (src["left_x"], sy)]

    # Select ports
    src_port, tgt_port = _select_ports(src, tgt, src_id, tgt_id, edge, all_edges, all_layout)

    # Get port coordinates
    src_ports = _get_ports(src)
    tgt_ports = _get_ports(tgt)
    sx, sy = src_ports[src_port]
    ex, ey = tgt_ports[tgt_port]

    is_backward = src["center_x"] > tgt["center_x"] + 10

    if is_backward:
        return _route_backward(src, tgt, sx, sy, ex, ey, all_layout, src_id, tgt_id)

    # Forward routing based on port combination
    return _route_forward(src, tgt, sx, sy, ex, ey, src_port, tgt_port,
                          all_layout, src_id, tgt_id)


def _route_forward(src, tgt, sx, sy, ex, ey, src_port, tgt_port,
                   all_layout, src_id, tgt_id):
    """Route a forward connection between two elements."""

    # Case 1: right → left (horizontal with possible Z-bend)
    if src_port == "right" and tgt_port == "left":
        if abs(sy - ey) <= 5:
            # Perfectly aligned — straight line
            waypoints = [(sx, sy), (ex, ey)]
        else:
            # Z-route: horizontal → vertical → horizontal
            mid_x = sx + (ex - sx) / 2
            waypoints = [(sx, sy), (mid_x, sy), (mid_x, ey), (ex, ey)]

    # Case 2: bottom → left (gateway branch downward then forward)
    elif src_port == "bottom" and tgt_port == "left":
        mid_y = sy + (ey - sy) / 2 if ey > sy else sy + 30
        waypoints = [(sx, sy), (sx, mid_y), (ex - 0, mid_y)]
        # If not aligned, add extra segment
        if abs(mid_y - ey) > 5:
            waypoints = [(sx, sy), (sx, ey), (ex, ey)]
        else:
            waypoints = [(sx, sy), (sx, mid_y), (ex, mid_y)]
            if abs(mid_y - ey) > 5:
                waypoints.append((ex, ey))

    # Case 3: top → left (gateway branch upward then forward)
    elif src_port == "top" and tgt_port == "left":
        waypoints = [(sx, sy), (sx, ey), (ex, ey)]

    # Case 4: bottom → top (direct vertical)
    elif src_port == "bottom" and tgt_port == "top":
        if abs(sx - ex) <= 5:
            waypoints = [(sx, sy), (ex, ey)]
        else:
            mid_y = sy + (ey - sy) / 2
            waypoints = [(sx, sy), (sx, mid_y), (ex, mid_y), (ex, ey)]

    # Case 5: top → bottom (direct vertical upward)
    elif src_port == "top" and tgt_port == "bottom":
        if abs(sx - ex) <= 5:
            waypoints = [(sx, sy), (ex, ey)]
        else:
            mid_y = sy + (ey - sy) / 2
            waypoints = [(sx, sy), (sx, mid_y), (ex, mid_y), (ex, ey)]

    else:
        # Fallback: Z-route
        mid_x = sx + (ex - sx) / 2
        waypoints = [(sx, sy), (mid_x, sy), (mid_x, ey), (ex, ey)]

    # Check for overlaps and adjust if needed
    has_overlap, overlap_id = _check_route_overlaps(
        waypoints, all_layout, {src_id, tgt_id})
    if has_overlap and overlap_id:
        overlap_info = all_layout[overlap_id]
        # Try routing around the obstacle
        waypoints = _route_around_obstacle(waypoints, overlap_info, src, tgt, sx, sy, ex, ey)

    return waypoints


def _route_backward(src, tgt, sx, sy, ex, ey, all_layout, src_id, tgt_id):
    """Route a backward (loop) connection."""
    # Decide whether to route above or below
    # Use the higher/lower of the two elements + clearance
    if sy <= ey:
        # Route above both elements
        route_y = min(src["top_y"], tgt["top_y"]) - 50
    else:
        # Route below both elements
        route_y = max(src["bottom_y"], tgt["bottom_y"]) + 50

    waypoints = [
        (sx, sy),
        (sx + EDGE_CLEARANCE, sy),
        (sx + EDGE_CLEARANCE, route_y),
        (tgt["left_x"] - EDGE_CLEARANCE, route_y),
        (tgt["left_x"] - EDGE_CLEARANCE, ey),
        (ex, ey),
    ]

    # Check for overlaps and push the route further if needed
    has_overlap, overlap_id = _check_route_overlaps(
        waypoints, all_layout, {src_id, tgt_id})
    if has_overlap and overlap_id:
        overlap_info = all_layout[overlap_id]
        if route_y < sy:
            # Push further up
            route_y = min(route_y, overlap_info["top_y"] - 40)
        else:
            # Push further down
            route_y = max(route_y, overlap_info["bottom_y"] + 40)
        waypoints = [
            (sx, sy),
            (sx + EDGE_CLEARANCE, sy),
            (sx + EDGE_CLEARANCE, route_y),
            (tgt["left_x"] - EDGE_CLEARANCE, route_y),
            (tgt["left_x"] - EDGE_CLEARANCE, ey),
            (ex, ey),
        ]

    return waypoints


def _route_around_obstacle(waypoints, obstacle, src, tgt, sx, sy, ex, ey):
    """Reroute waypoints to avoid an obstacle element."""
    ox, oy = obstacle["x"], obstacle["y"]
    ow, oh = obstacle["width"], obstacle["height"]
    o_center_y = obstacle["center_y"]

    # Decide whether to go above or below the obstacle
    avg_y = (sy + ey) / 2
    if avg_y < o_center_y:
        # Route above the obstacle
        detour_y = oy - EDGE_CLEARANCE
    else:
        # Route below the obstacle
        detour_y = oy + oh + EDGE_CLEARANCE

    mid_x = sx + (ex - sx) / 2
    return [
        (sx, sy),
        (mid_x, sy),
        (mid_x, detour_y),
        (ex - 30 if ex > sx else ex + 30, detour_y),
        (ex - 30 if ex > sx else ex + 30, ey),
        (ex, ey),
    ]


def _add_edge_label(edge_di, waypoints, name, src_info=None):
    """Position a label near the source for gateway branches or at midpoint for others."""
    is_gateway_branch = src_info and src_info.get("is_gateway", False) if src_info else False

    if is_gateway_branch and len(waypoints) >= 2:
        # Place label near the source (first segment)
        p1 = waypoints[0]
        p2 = waypoints[1]
        lx = (p1[0] + p2[0]) / 2
        ly = (p1[1] + p2[1]) / 2
        # Offset based on direction
        if abs(p1[0] - p2[0]) > abs(p1[1] - p2[1]):
            ly -= 15  # Above horizontal line
        else:
            lx += 5   # Right of vertical line
    elif len(waypoints) >= 2:
        mid_idx = len(waypoints) // 2
        p1 = waypoints[mid_idx - 1]
        p2 = waypoints[mid_idx]
        lx = (p1[0] + p2[0]) / 2
        ly = (p1[1] + p2[1]) / 2
        # Offset to avoid overlapping the line
        if abs(p1[0] - p2[0]) > abs(p1[1] - p2[1]):
            ly -= 15  # Above horizontal line
        else:
            lx += 5
    else:
        lx, ly = waypoints[0][0], waypoints[0][1]

    # Dynamic label width
    text_len = len(name) if name else 0
    label_w = max(text_len * 7, 30)
    label_h = 14

    label = ET.SubElement(edge_di, bpmndi("BPMNLabel"))
    ET.SubElement(label, dc("Bounds"),
                  x=str(int(lx - label_w / 2)), y=str(int(ly - label_h / 2)),
                  width=str(int(label_w)), height=str(label_h))


def _add_message_flow_di(plane, mf, all_layouts):
    """Add DI edge for a message flow between pools."""
    mf_id = mf["id"]
    src_id = mf["source"]
    tgt_id = mf["target"]

    src = all_layouts.get(src_id)
    tgt = all_layouts.get(tgt_id)
    if not src or not tgt:
        return

    edge_di = ET.SubElement(plane, bpmndi("BPMNEdge"),
                            id=f"{mf_id}_di", bpmnElement=mf_id)

    # Message flows are typically vertical between pools
    sx = src["center_x"]
    sy = src["bottom_y"] if src["center_y"] < tgt["center_y"] else src["top_y"]
    ex = tgt["center_x"]
    ey = tgt["top_y"] if tgt["center_y"] > src["center_y"] else tgt["bottom_y"]

    if abs(sx - ex) < 10:
        waypoints = [(sx, sy), (ex, ey)]
    else:
        mid_y = (sy + ey) / 2
        waypoints = [(sx, sy), (sx, mid_y), (ex, mid_y), (ex, ey)]

    for wx, wy in waypoints:
        ET.SubElement(edge_di, di("waypoint"), x=str(int(wx)), y=str(int(wy)))

    if mf.get("name"):
        _add_edge_label(edge_di, waypoints, mf.get("name", ""))


# ── Layout computation for a single process ───────────────────────────────────

def compute_layout(nodes, edges, lanes_data, pool_x_offset, pool_y_offset):
    """
    Compute layout positions for all nodes in a process.
    Returns (layout_info, lane_configs, pool_width, pool_height, subprocess_layouts).
    """
    # Separate regular nodes from special types
    regular_nodes = [n for n in nodes if n.get("type") not in
                     ("BoundaryEvent", "BoundaryTimerEvent", "BoundaryMessageEvent",
                      "TextAnnotation", "DataObjectReference", "DataStoreReference")]
    boundary_nodes = [n for n in nodes if n.get("type") in
                      ("BoundaryEvent", "BoundaryTimerEvent", "BoundaryMessageEvent")]
    annotation_nodes = [n for n in nodes if n.get("type") in
                        ("TextAnnotation", "DataObjectReference", "DataStoreReference")]

    depths = compute_depths(regular_nodes, edges)
    offsets, ld_counts = compute_row_offsets(regular_nodes, depths)
    max_depth = max(depths.values(), default=0)

    # Pool width
    pool_width = max((max_depth + 1) * X_SPACING + BASE_X + POOL_PADDING_X, 800)

    # Lane configurations
    lane_configs = {}
    current_y = pool_y_offset

    if lanes_data:
        for lane in lanes_data:
            lid = lane["id"]
            # Count max stacked nodes in this lane
            max_stacked = 1
            for (lkey, d), count in ld_counts.items():
                if lkey == lid and count > max_stacked:
                    max_stacked = count
            lane_h = max(max_stacked * Y_NODE_SPACING + LANE_PAD_TOP + LANE_PAD_BOTTOM,
                         MIN_LANE_HEIGHT)
            lane_configs[lid] = {
                "y": current_y,
                "height": lane_h,
                "center_y": current_y + lane_h / 2,
            }
            current_y += lane_h
    else:
        # No lanes: single default lane
        max_stacked = max(ld_counts.values(), default=1) if ld_counts else 1
        lane_h = max(max_stacked * Y_NODE_SPACING + LANE_PAD_TOP + LANE_PAD_BOTTOM,
                     MIN_LANE_HEIGHT)
        lane_configs["default"] = {
            "y": pool_y_offset,
            "height": lane_h,
            "center_y": pool_y_offset + lane_h / 2,
        }
        current_y = pool_y_offset + lane_h

    pool_height = current_y - pool_y_offset

    # Node positions
    layout_info = {}
    subprocess_layouts = {}

    for node in regular_nodes:
        nid = node["id"]
        ntype = node.get("type", "Task")
        _, width, height = TYPE_INFO.get(ntype, ("task", 100, 80))
        lane_id = node.get("lane", "default")
        d = depths.get(nid, 0)
        offset = offsets.get(nid, 0)
        l_cfg = lane_configs.get(lane_id, lane_configs.get("default",
                                 {"y": pool_y_offset, "height": MIN_LANE_HEIGHT}))

        if "x" in node and "y" in node:
            nx = node["x"]
            ny = node["y"]
        else:
            # Center all elements on the same column centerline
            col_center = pool_x_offset + BASE_X + d * X_SPACING + 50
            nx = col_center - width / 2

            # Vertical: place within the lane
            available_y = l_cfg["y"] + LANE_PAD_TOP
            ny = available_y + offset * Y_NODE_SPACING + (Y_NODE_SPACING - height) / 2

        # Handle sub-process sizing
        if ntype == "SubProcess" and "nodes" in node:
            sp_w, sp_h, inner_layout = layout_subprocess(node, nx, ny)
            width = sp_w
            height = sp_h
            subprocess_layouts[nid] = inner_layout

        layout_info[nid] = _make_layout_entry(nx, ny, width, height, ntype)

    # Place boundary events relative to their host task
    for bnode in boundary_nodes:
        bid = bnode["id"]
        attached_to = bnode.get("attachedTo", "")
        host = layout_info.get(attached_to)
        if host:
            bx = host["center_x"] - 18
            by = host["bottom_y"] + BOUNDARY_OFFSET_Y
            layout_info[bid] = _make_layout_entry(bx, by, 36, 36, bnode.get("type", "BoundaryEvent"))

    # Place annotations near their associated elements
    for anode in annotation_nodes:
        aid = anode["id"]
        ntype = anode.get("type", "TextAnnotation")
        _, width, height = TYPE_INFO.get(ntype, ("textAnnotation", 100, 30))
        if "x" in anode and "y" in anode:
            ax, ay = anode["x"], anode["y"]
        else:
            # Place to the right of the last column
            ax = pool_x_offset + BASE_X + (max_depth + 1) * X_SPACING + 20
            ay = pool_y_offset + LANE_PAD_TOP
        layout_info[aid] = _make_layout_entry(ax, ay, width, height, ntype)

    return layout_info, lane_configs, pool_width, pool_height, subprocess_layouts


# ── Main entry point ──────────────────────────────────────────────────────────

def generate_bpmn(input_json_path, output_bpmn_path):
    with open(input_json_path, 'r', encoding='utf-8') as f:
        data = json.load(f)

    for prefix, uri in NS.items():
        ET.register_namespace(prefix, uri)

    root = ET.Element(bpmn("definitions"), {
        "id": "Definitions_1",
        "targetNamespace": "http://bpmn.io/schema/bpmn",
        "exporter": "python-bpmn-maker",
        "exporterVersion": "4.0",
    })

    # Determine mode: multi-pool or single-process
    participants = data.get("participants")
    is_multi = participants is not None and len(participants) > 0

    # Create diagram element detached, then append AFTER semantic elements
    diagram = ET.Element(bpmndi("BPMNDiagram"), id="BPMNDiagram_1")

    if is_multi:
        _build_multi_pool(root, diagram, data, participants)
    else:
        _build_single_process(root, diagram, data)

    # Append diagram last so it appears after collaboration/process in XML
    root.append(diagram)

    # Serialize
    xml_str = ET.tostring(root, 'utf-8')
    parsed = minidom.parseString(xml_str)
    pretty_xml = parsed.toprettyxml(indent="  ")

    with open(output_bpmn_path, 'w', encoding='utf-8') as f:
        clean_xml = '\n'.join(line for line in pretty_xml.split('\n') if line.strip())
        f.write(clean_xml)

    print(f"BPMN generated successfully at {output_bpmn_path}")


def _build_single_process(root, diagram, data):
    """Build a single-process BPMN (with optional lanes)."""
    process_id = data.get("process_id", "Process_1")
    process_name = data.get("name", "Generated Process")
    is_executable = data.get("is_executable", "true")
    nodes = data.get("nodes", [])
    edges = data.get("edges", [])
    lanes_data = data.get("lanes", [])
    associations = data.get("associations", [])
    has_lanes = len(lanes_data) > 0
    participant_id = f"Participant_{process_id}"

    if has_lanes:
        collab = ET.SubElement(root, bpmn("collaboration"), id="Collaboration_1")
        ET.SubElement(collab, bpmn("participant"),
                      id=participant_id, name=process_name, processRef=process_id)
        plane_ref = "Collaboration_1"
    else:
        plane_ref = process_id

    process_el = ET.SubElement(root, bpmn("process"),
                               id=process_id, name=process_name,
                               isExecutable=is_executable)

    plane = ET.SubElement(diagram, bpmndi("BPMNPlane"),
                          id="BPMNPlane_1", bpmnElement=plane_ref)

    # Compute layout
    pool_x = 120
    pool_y = 80
    layout_info, lane_configs, pool_w, pool_h, sp_layouts = compute_layout(
        nodes, edges, lanes_data, pool_x + POOL_HEADER, pool_y
    )

    # Draw pool shape
    if has_lanes:
        pool_shape = ET.SubElement(plane, bpmndi("BPMNShape"),
                                   id=f"{participant_id}_di",
                                   bpmnElement=participant_id,
                                   isHorizontal="true")
        ET.SubElement(pool_shape, dc("Bounds"),
                      x=str(pool_x), y=str(pool_y),
                      width=str(int(pool_w)), height=str(int(pool_h)))

        # Lane shapes
        for lane in lanes_data:
            lid = lane["id"]
            l_cfg = lane_configs.get(lid)
            if not l_cfg:
                continue
            lane_shape = ET.SubElement(plane, bpmndi("BPMNShape"),
                                      id=f"{lid}_di", bpmnElement=lid,
                                      isHorizontal="true")
            ET.SubElement(lane_shape, dc("Bounds"),
                          x=str(pool_x + POOL_HEADER), y=str(int(l_cfg["y"])),
                          width=str(int(pool_w - POOL_HEADER)),
                          height=str(int(l_cfg["height"])))

    # Build process elements
    build_process_elements(process_el, plane, nodes, edges, layout_info,
                           lanes_data if has_lanes else None, sp_layouts, associations)


def _build_multi_pool(root, diagram, data, participants):
    """Build a multi-pool collaboration BPMN with normalized pool widths."""
    collab = ET.SubElement(root, bpmn("collaboration"), id="Collaboration_1")
    plane = ET.SubElement(diagram, bpmndi("BPMNPlane"),
                          id="BPMNPlane_1", bpmnElement="Collaboration_1")

    all_layouts = {}  # Merged layout across all pools for message flow routing
    pool_x = 120

    # First pass: compute all layouts to find max width for normalization
    pool_data_list = []
    max_pool_width = 800

    for p in participants:
        pid = p.get("process_id", _next_id("Process"))
        p_nodes = p.get("nodes", [])
        p_edges = p.get("edges", [])
        p_lanes = p.get("lanes", [])

        # Temporarily compute layout to get pool width
        inner_x = pool_x + POOL_HEADER
        layout_info, lane_configs, pool_w, pool_h, sp_layouts = compute_layout(
            p_nodes, p_edges, p_lanes, inner_x, 0  # y=0 temporarily
        )
        max_pool_width = max(max_pool_width, pool_w)
        pool_data_list.append({
            "participant": p,
            "pid": pid,
            "layout_info": layout_info,
            "lane_configs": lane_configs,
            "pool_w": pool_w,
            "pool_h": pool_h,
            "sp_layouts": sp_layouts,
        })

    # Second pass: place pools with normalized width
    current_pool_y = 80

    for pd in pool_data_list:
        p = pd["participant"]
        pid = pd["pid"]
        pname = p.get("name", pid)
        part_id = p.get("id", f"Participant_{pid}")
        is_executable = p.get("is_executable", "true")
        p_nodes = p.get("nodes", [])
        p_edges = p.get("edges", [])
        p_lanes = p.get("lanes", [])
        associations = p.get("associations", [])
        has_lanes = len(p_lanes) > 0

        # Re-compute layout with correct Y offset
        inner_x = pool_x + POOL_HEADER
        layout_info, lane_configs, pool_w, pool_h, sp_layouts = compute_layout(
            p_nodes, p_edges, p_lanes, inner_x, current_pool_y
        )

        # Use normalized width
        pool_w = max_pool_width

        # Add participant to collaboration
        ET.SubElement(collab, bpmn("participant"),
                      id=part_id, name=pname, processRef=pid)

        # Add process
        process_el = ET.SubElement(root, bpmn("process"),
                                   id=pid, name=pname,
                                   isExecutable=is_executable)

        # Pool shape
        pool_shape = ET.SubElement(plane, bpmndi("BPMNShape"),
                                   id=f"{part_id}_di", bpmnElement=part_id,
                                   isHorizontal="true")
        ET.SubElement(pool_shape, dc("Bounds"),
                      x=str(pool_x), y=str(int(current_pool_y)),
                      width=str(int(pool_w)), height=str(int(pool_h)))

        # Lane shapes
        if has_lanes:
            for lane in p_lanes:
                lid = lane["id"]
                l_cfg = lane_configs.get(lid)
                if not l_cfg:
                    continue
                lane_shape = ET.SubElement(plane, bpmndi("BPMNShape"),
                                          id=f"{lid}_di", bpmnElement=lid,
                                          isHorizontal="true")
                ET.SubElement(lane_shape, dc("Bounds"),
                              x=str(inner_x), y=str(int(l_cfg["y"])),
                              width=str(int(pool_w - POOL_HEADER)),
                              height=str(int(l_cfg["height"])))

        # Build elements
        build_process_elements(process_el, plane, p_nodes, p_edges, layout_info,
                               p_lanes if has_lanes else None, sp_layouts, associations)

        # Merge layout info
        all_layouts.update(layout_info)

        current_pool_y += pool_h + POOL_GAP

    # Message flows
    for mf in data.get("message_flows", []):
        ET.SubElement(collab, bpmn("messageFlow"),
                      id=mf["id"], sourceRef=mf["source"],
                      targetRef=mf["target"], name=mf.get("name", ""))
        _add_message_flow_di(plane, mf, all_layouts)


# ── CLI ───────────────────────────────────────────────────────────────────────

if __name__ == '__main__':
    if len(sys.argv) < 3:
        print("Usage: python bpmn_maker.py <input.json> <output.bpmn>")
        sys.exit(1)
    generate_bpmn(sys.argv[1], sys.argv[2])
