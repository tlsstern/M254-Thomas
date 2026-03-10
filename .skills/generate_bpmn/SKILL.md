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

## BPMN 2.0 Semantic Rules

When building or designing BPMN models, always adhere to these rules to maintain proper token semantics and technical validity:

1. **Continuous Sequence Flows (Solid Lines)**:
   - A token must be able to travel continuously from a Start Event to an End Event within the same Pool (Participant).
   - Sequence flows cannot break or cross the boundaries of a Pool.
2. **Message Flows (Dashed Lines)**:
   - Interactions between different Pools (e.g., Tenant vs. Landlord) must be strictly handled via Message Flows.
   - Message Flows may only connect distinct Pools. They cannot connect elements within the same Pool.
3. **Sub-Processes for Logical Grouping**:
   - Use expanded Sub-Processes to group related tasks or loops (e.g., searching for something until found) to keep the main process visually clean and logically structured.
4. **Intermediate Message Catch Events for Wait States**:
   - Do not break sequence flows to represent waiting for an external message. Instead, use explicit Intermediate Catch Events (Message type) connected over sequence flows to securely model wait states.
5. **Event-Based Gateways for Asynchronous Alternatives**:
   - When a process reaches a point where it must wait for one of multiple possible external messages (e.g., waiting for an Acceptance or a Rejection letter), insert an Event-Based Gateway before the Intermediate Message Catch Events representing each possible response.
