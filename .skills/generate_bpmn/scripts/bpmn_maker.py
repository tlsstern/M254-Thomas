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
        "exporterVersion": "1.0"
    })
    
    process = ET.SubElement(root, "{http://www.omg.org/spec/BPMN/20100524/MODEL}process", {
        "id": process_id,
        "name": process_name,
        "isExecutable": is_executable
    })
    
    diagram = ET.SubElement(root, "{http://www.omg.org/spec/BPMN/20100524/DI}BPMNDiagram", {"id": "BPMNDiagram_1"})
    plane = ET.SubElement(diagram, "{http://www.omg.org/spec/BPMN/20100524/DI}BPMNPlane", {
        "id": "BPMNPlane_1",
        "bpmnElement": process_id
    })

    nodes = data.get("nodes", [])
    edges = data.get("edges", [])
    
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

    x_cursor = 150
    y_center = 120
    
    for node in nodes:
        node_id = node.get("id")
        node_type = node.get("type", "Task")
        node_name = node.get("name", "")
        
        bpmn_tag, width, height = type_info.get(node_type, ("task", 100, 80))
        
        elem = ET.SubElement(process, f"{{http://www.omg.org/spec/BPMN/20100524/MODEL}}{bpmn_tag}", {
            "id": node_id,
            "name": node_name
        })
        
        node_x = node.get("x", x_cursor)
        node_y = node.get("y", y_center - (height / 2))
        
        layout_info[node_id] = {
            "x": node_x,
            "y": node_y,
            "width": width,
            "height": height,
            "center_x": node_x + width / 2,
            "center_y": node_y + height / 2,
            "right_x": node_x + width,
            "left_x": node_x
        }
        
        x_cursor = node_x + width + 50
        
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
        
        if bpmn_tag.endswith("Event") or bpmn_tag.endswith("Gateway"):
            label = ET.SubElement(shape, "{http://www.omg.org/spec/BPMN/20100524/DI}BPMNLabel")
            ET.SubElement(label, "{http://www.omg.org/spec/DD/20100524/DC}Bounds", {
                "x": str(int(node_x - 10)),
                "y": str(int(node_y + height + 5)),
                "width": "60",
                "height": "14"
            })
            
    incoming = {n["id"]: [] for n in nodes}
    outgoing = {n["id"]: [] for n in nodes}
    
    for edge in edges:
        edge_id = edge.get("id")
        source_ref = edge.get("source")
        target_ref = edge.get("target")
        edge_name = edge.get("name", "")
        
        if source_ref in outgoing:
            outgoing[source_ref].append(edge_id)
        if target_ref in incoming:
            incoming[target_ref].append(edge_id)
            
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
            ET.SubElement(edge_di, "{http://www.omg.org/spec/DD/20100524/DI}waypoint", {
                "x": str(int(source_info["right_x"])),
                "y": str(int(source_info["center_y"]))
            })
            ET.SubElement(edge_di, "{http://www.omg.org/spec/DD/20100524/DI}waypoint", {
                "x": str(int(target_info["left_x"])),
                "y": str(int(target_info["center_y"]))
            })
            if edge_name:
                label = ET.SubElement(edge_di, "{http://www.omg.org/spec/BPMN/20100524/DI}BPMNLabel")
                ET.SubElement(label, "{http://www.omg.org/spec/DD/20100524/DC}Bounds", {
                    "x": str(int((source_info["right_x"] + target_info["left_x"])/2)),
                    "y": str(int(source_info["center_y"] - 15)),
                    "width": "60",
                    "height": "14"
                })
            
    for node in process:
        tag = node.tag.split('}')[-1]
        node_id = node.get("id")
        if tag in ["startEvent", "endEvent", "task", "userTask", "serviceTask", "sendTask", "receiveTask", "exclusiveGateway", "parallelGateway", "intermediateCatchEvent", "intermediateThrowEvent"]:
            for in_f in incoming.get(node_id, []):
                ET.SubElement(node, "{http://www.omg.org/spec/BPMN/20100524/MODEL}incoming").text = in_f
            for out_f in outgoing.get(node_id, []):
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
