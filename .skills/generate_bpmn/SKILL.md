---
name: Generate BPMN
description: Generates a BPMN 2.0 XML file from a JSON definition to save output tokens.
---
# Generate BPMN

When the user asks you to create or modify a `.bpmn` (Business Process Model and Notation) file, generating the full XML structure can exceed your output token limits or result in broken files. Instead, use the `bpmn_maker.py` script provided by this skill.

## Process
1. Determine the nodes and edges of the process.
2. Write a JSON file (e.g., `process.json`) containing the process definition to disk using `write_to_file`.
3. Execute `python .skills/generate_bpmn/scripts/bpmn_maker.py process.json target_file.bpmn` from the project root using the `run_command` tool.
4. Verify the file was created successfully.
5. (Optional) Remove the `process.json` file.

## Supported Node Types
- StartEvent
- EndEvent
- Task
- UserTask
- ServiceTask
- SendTask
- ReceiveTask
- ExclusiveGateway
- ParallelGateway
- IntermediateCatchEvent
- IntermediateThrowEvent

## JSON Format Example
```json
{
  "process_id": "Process_1",
  "name": "My Process",
  "nodes": [
    {"id": "StartEvent_1", "type": "StartEvent", "name": "Start"},
    {"id": "Task_1", "type": "UserTask", "name": "Do Work"},
    {"id": "EndEvent_1", "type": "EndEvent", "name": "End"}
  ],
  "edges": [
    {"id": "Flow_1", "source": "StartEvent_1", "target": "Task_1", "name": "to task"},
    {"id": "Flow_2", "source": "Task_1", "target": "EndEvent_1", "name": ""}
  ]
}
```

## Node Placement (Optional)
Layout is generated automatically in a naive linear way. If you need explicit placement, you can optionally provide `x` and `y` properties to the nodes in the JSON structure.

The user can always reorganize and refine the layout manually by opening the resulting `.bpmn` file in Camunda Modeler.
