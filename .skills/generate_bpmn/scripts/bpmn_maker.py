import json
import sys
import xml.etree.ElementTree as ET
from xml.dom import minidom

def generate_bpmn(input_json_path, output_bpmn_path):
    with open(input_json_path, 'r', encoding='utf-8') as f:
        data = json.load(f)

    process_id = data.get("process_id", "Process_1")
    process_name = data.get("name", "Generated Process")
    is_executable = data.get("is_executable", "true")
    
    # XML Namespaces
    namespaces = {
        "bpmn": "http://www.omg.org/spec/BPMN/20100524/MODEL",
        "bpmndi": "http://www.omg.org/spec/BPMN/20100524/DI",
        "dc": "http://www.omg.org/spec/DD/20100524/DC",
        "di": "http://www.omg.org/spec/DD/20100524/DI"
    }
    
    for prefix, uri in namespaces.items():
        ET.register_namespace(prefix, uri)

    root = ET.Element("{http://www.omg.org/spec/BPMN/20100524/MODEL}definitions", {
        "id": "Definitions_1",
        "targetNamespace": "http://bpmn.io/schema/bpmn",
        "exporter": "python-bpmn-maker",
        "exporterVersion": "2.0"
    })
    
    # Check if we have lanes for a Collaboration diagram
    lanes_data = data.get("lanes", [])
    has_lanes = len(lanes_data) > 0
    participant_id = f"Participant_{process_id}"

    if has_lanes:
        collaboration = ET.SubElement(root, "{http://www.omg.org/spec/BPMN/20100524/MODEL}collaboration", {"id": "Collaboration_1"})
        ET.SubElement(collaboration, "{http://www.omg.org/spec/BPMN/20100524/MODEL}participant", {
            "id": participant_id,
            "name": process_name,
            "processRef": process_id
        })

    process = ET.SubElement(root, "{http://www.omg.org/spec/BPMN/20100524/MODEL}process", {
        "id": process_id,
        "name": process_name,
        "isExecutable": is_executable
    })
    
    lane_set = None
    if has_lanes:
        lane_set = ET.SubElement(process, "{http://www.omg.org/spec/BPMN/20100524/MODEL}laneSet", {"id": f"LaneSet_{process_id}"})
        for lane in lanes_data:
            l_elem = ET.SubElement(lane_set, "{http://www.omg.org/spec/BPMN/20100524/MODEL}lane", {
                "id": lane["id"],
                "name": lane.get("name", lane["id"])
            })
            lane["_element"] = l_elem

    diagram = ET.SubElement(root, "{http://www.omg.org/spec/BPMN/20100524/DI}BPMNDiagram", {"id": "BPMNDiagram_1"})
    
    # The BPMNPlane references the Collaboration if it exists, otherwise the Process
    plane_bpmn_element = "Collaboration_1" if has_lanes else process_id
    plane = ET.SubElement(diagram, "{http://www.omg.org/spec/BPMN/20100524/DI}BPMNPlane", {
        "id": "BPMNPlane_1",
        "bpmnElement": plane_bpmn_element
    })

    nodes = data.get("nodes", [])
    edges = data.get("edges", [])
    
    # 1. Build adjacency
    incoming = {n["id"]: [] for n in nodes}
    outgoing = {n["id"]: [] for n in nodes}
    incoming_edges = {n["id"]: [] for n in nodes}
    outgoing_edges = {n["id"]: [] for n in nodes}

    for edge in edges:
        edge_id = edge.get("id")
        source = edge.get("source")
        target = edge.get("target")
        if source in outgoing:
            outgoing[source].append(target)
            outgoing_edges[source].append(edge_id)
        if target in incoming:
            incoming[target].append(source)
            incoming_edges[target].append(edge_id)

    # 2. X-axis Depth calculation
    depths = {n["id"]: 0 for n in nodes}
    start_nodes = [n["id"] for n in nodes if not incoming[n["id"]]]
    if not start_nodes and nodes:
        start_nodes = [nodes[0]["id"]]

    def dfs_depth(node_id, current_depth, path_visited):
        if node_id in path_visited:
            return
        if current_depth > depths[node_id]:
            depths[node_id] = current_depth
        path_visited.add(node_id)
        for child in outgoing.get(node_id, []):
            dfs_depth(child, depths[node_id] + 1, path_visited.copy())

    for start in start_nodes:
        dfs_depth(start, 0, set())

    # Resolve parallel overlaps at same depth within the same lane
    lane_depth_counts = {}
    row_offsets = {n["id"]: 0 for n in nodes}
    
    for n in nodes:
        n_id = n["id"]
        n_lane = n.get("lane", "default")
        n_depth = depths[n_id]
        key = f"{n_lane}_{n_depth}"
        count = lane_depth_counts.get(key, 0)
        row_offsets[n_id] = count
        lane_depth_counts[key] = count + 1

    # Constants
    x_spacing = 180
    y_node_spacing = 100
    base_x = 250
    lane_width_base = max(depths.values(), default=0) * x_spacing + x_spacing * 2 if depths else 800

    # Y-axis calculation
    lane_configs = {}
    current_y = 100
    pool_y = 100
    
    if has_lanes:
        # Fallback default lane if missing
        lane_configs["default"] = {"y": 100, "height": 300, "center_y": 250}
        for lane in lanes_data:
            lane_id = lane["id"]
            # Find max nodes stacked vertically in this lane
            max_stacked = 1
            for key, count in lane_depth_counts.items():
                if key.startswith(f"{lane_id}_") and count > max_stacked:
                    max_stacked = count
            
            lane_height = max_stacked * y_node_spacing + 40
            lane_configs[lane_id] = {
                "y": current_y,
                "height": lane_height,
                "center_y": current_y + (lane_height / 2)
            }
            current_y += lane_height
    else:
        lane_configs["default"] = {"y": 100, "height": 300, "center_y": 250}

    total_pool_height = current_y - pool_y if current_y > pool_y else 300

    # Draw Pool (Participant) and Lanes
    if has_lanes:
        pool_shape = ET.SubElement(plane, "{http://www.omg.org/spec/BPMN/20100524/DI}BPMNShape", {
            "id": f"{participant_id}_di",
            "bpmnElement": participant_id,
            "isHorizontal": "true"
        })
        ET.SubElement(pool_shape, "{http://www.omg.org/spec/DD/20100524/DC}Bounds", {
            "x": "150",
            "y": str(pool_y),
            "width": str(lane_width_base),
            "height": str(total_pool_height)
        })
        
        for lane in lanes_data:
            lane_id = lane["id"]
            l_cfg = lane_configs[lane_id]
            lane_shape = ET.SubElement(plane, "{http://www.omg.org/spec/BPMN/20100524/DI}BPMNShape", {
                "id": f"{lane_id}_di",
                "bpmnElement": lane_id,
                "isHorizontal": "true"
            })
            ET.SubElement(lane_shape, "{http://www.omg.org/spec/DD/20100524/DC}Bounds", {
                "x": "180",
                "y": str(l_cfg["y"]),
                "width": str(lane_width_base - 30),
                "height": str(l_cfg["height"])
            })

    layout_info = {}
    type_info = {
        "StartEvent": ("startEvent", 36, 36),
        "EndEvent": ("endEvent", 36, 36),
        "Task": ("task", 100, 80),
        "UserTask": ("userTask", 100, 80),
        "ServiceTask": ("serviceTask", 100, 80),
        "SendTask": ("sendTask", 100, 80),
        "ReceiveTask": ("receiveTask", 100, 80),
        "ExclusiveGateway": ("exclusiveGateway", 50, 50),
        "ParallelGateway": ("parallelGateway", 50, 50),
        "IntermediateCatchEvent": ("intermediateCatchEvent", 36, 36),
        "IntermediateThrowEvent": ("intermediateThrowEvent", 36, 36)
    }

    # 3. Add Nodes
    for node in nodes:
        node_id = node.get("id")
        node_type = node.get("type", "Task")
        node_name = node.get("name", "")
        lane_id = node.get("lane", "default")
        bpmn_tag, width, height = type_info.get(node_type, ("task", 100, 80))

        # Register node in lane XML if lanes exist
        if has_lanes and lane_id != "default":
            for l_data in lanes_data:
                if l_data["id"] == lane_id:
                    ET.SubElement(l_data["_element"], "{http://www.omg.org/spec/BPMN/20100524/MODEL}flowNodeRef").text = node_id
                    break

        if "x" in node and "y" in node:
            node_x = node["x"]
            node_y = node["y"]
        else:
            d = depths.get(node_id, 0)
            offset = row_offsets.get(node_id, 0)
            l_cfg = lane_configs.get(lane_id, lane_configs["default"])
            
            column_center = base_x + (d * x_spacing) + 50
            node_x = column_center - (width / 2)
            node_y = l_cfg["y"] + 20 + (offset * y_node_spacing) + ( (y_node_spacing - height) / 2 )

        layout_info[node_id] = {
            "x": node_x,
            "y": node_y,
            "width": width,
            "height": height,
            "center_x": node_x + width / 2,
            "center_y": node_y + height / 2,
            "right_x": node_x + width,
            "left_x": node_x,
            "top_y": node_y,
            "bottom_y": node_y + height
        }

        elem = ET.SubElement(process, f"{{http://www.omg.org/spec/BPMN/20100524/MODEL}}{bpmn_tag}", {
            "id": node_id,
            "name": node_name
        })

        shape = ET.SubElement(plane, "{http://www.omg.org/spec/BPMN/20100524/DI}BPMNShape", {
            "id": f"{node_id}_di",
            "bpmnElement": node_id
        })

        bounds = ET.SubElement(shape, "{http://www.omg.org/spec/DD/20100524/DC}Bounds", {
            "x": str(int(node_x)),
            "y": str(int(node_y)),
            "width": str(int(width)),
            "height": str(int(height))
        })

        # Gateway/Event labels
        if bpmn_tag.endswith("Event") or bpmn_tag.endswith("Gateway"):
            label = ET.SubElement(shape, "{http://www.omg.org/spec/BPMN/20100524/DI}BPMNLabel")
            ET.SubElement(label, "{http://www.omg.org/spec/DD/20100524/DC}Bounds", {
                "x": str(int(node_x - 10)),
                "y": str(int(node_y + height + 5)),
                "width": "60",
                "height": "14"
            })

    # 4. Add Edges
    for edge in edges:
        edge_id = edge.get("id")
        source_ref = edge.get("source")
        target_ref = edge.get("target")
        edge_name = edge.get("name", "")
        
        flow = ET.SubElement(process, "{http://www.omg.org/spec/BPMN/20100524/MODEL}sequenceFlow", {
            "id": edge_id,
            "sourceRef": source_ref,
            "targetRef": target_ref,
            "name": edge_name
        })
        
        edge_di = ET.SubElement(plane, "{http://www.omg.org/spec/BPMN/20100524/DI}BPMNEdge", {
            "id": f"{edge_id}_di",
            "bpmnElement": edge_id
        })
        
        source_info = layout_info.get(source_ref)
        target_info = layout_info.get(target_ref)
        
        if source_info and target_info:
            start_x = source_info["right_x"]
            start_y = source_info["center_y"]
            end_x = target_info["left_x"]
            end_y = target_info["center_y"]
            
            ET.SubElement(edge_di, "{http://www.omg.org/spec/DD/20100524/DI}waypoint", {
                "x": str(int(start_x)),
                "y": str(int(start_y))
            })
            
            if start_x >= end_x and source_ref != target_ref:
                # Loop back routing - route down below the tasks and back
                ET.SubElement(edge_di, "{http://www.omg.org/spec/DD/20100524/DI}waypoint", {"x": str(int(start_x)), "y": str(int(start_y + 60))})
                ET.SubElement(edge_di, "{http://www.omg.org/spec/DD/20100524/DI}waypoint", {"x": str(int(end_x - 30)), "y": str(int(start_y + 60))})
                ET.SubElement(edge_di, "{http://www.omg.org/spec/DD/20100524/DI}waypoint", {"x": str(int(end_x - 30)), "y": str(int(end_y))})
            elif abs(start_y - end_y) > 10 and source_ref != target_ref:
                # Forward orthogonal routing
                mid_x = start_x + (end_x - start_x) / 2
                ET.SubElement(edge_di, "{http://www.omg.org/spec/DD/20100524/DI}waypoint", {"x": str(int(mid_x)), "y": str(int(start_y))})
                ET.SubElement(edge_di, "{http://www.omg.org/spec/DD/20100524/DI}waypoint", {"x": str(int(mid_x)), "y": str(int(end_y))})
            
            ET.SubElement(edge_di, "{http://www.omg.org/spec/DD/20100524/DI}waypoint", {
                "x": str(int(end_x)),
                "y": str(int(end_y))
            })
            
            if edge_name:
                label = ET.SubElement(edge_di, "{http://www.omg.org/spec/BPMN/20100524/DI}BPMNLabel")
                ET.SubElement(label, "{http://www.omg.org/spec/DD/20100524/DC}Bounds", {
                    "x": str(int(start_x + (end_x - start_x)/2 - 10)),
                    "y": str(int((start_y + end_y)/2 - 15)),
                    "width": "60",
                    "height": "14"
                })

    for node in process:
        tag = node.tag.split('}')[-1]
        node_id = node.get("id")
        if tag in ["startEvent", "endEvent", "task", "userTask", "serviceTask", "sendTask", "receiveTask", "exclusiveGateway", "parallelGateway", "intermediateCatchEvent", "intermediateThrowEvent"]:
            for in_f in incoming_edges.get(node_id, []):
                ET.SubElement(node, "{http://www.omg.org/spec/BPMN/20100524/MODEL}incoming").text = in_f
            for out_f in outgoing_edges.get(node_id, []):
                ET.SubElement(node, "{http://www.omg.org/spec/BPMN/20100524/MODEL}outgoing").text = out_f

    xml_str = ET.tostring(root, 'utf-8')
    parsed = minidom.parseString(xml_str)
    pretty_xml = parsed.toprettyxml(indent="  ")
    
    with open(output_bpmn_path, 'w', encoding='utf-8') as f:
        clean_xml = '\n'.join([line for line in pretty_xml.split('\n') if line.strip()])
        f.write(clean_xml)

    print(f"BPMN generated successfully at {output_bpmn_path}")

if __name__ == '__main__':
    if len(sys.argv) < 3:
        print("Usage: python bpmn_maker.py <input.json> <output.bpmn>")
        sys.exit(1)
    generate_bpmn(sys.argv[1], sys.argv[2])
