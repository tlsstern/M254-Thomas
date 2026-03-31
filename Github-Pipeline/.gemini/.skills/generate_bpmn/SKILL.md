---
name: Generate BPMN
description: Generates a BPMN 2.0 XML file from a JSON definition with full support for multi-pool collaborations, message flows, event definitions, sub-processes, boundary events, text annotations, and production-quality auto-layout.
---
# Generate BPMN

When the user asks you to create or modify a `.bpmn` file, use the `bpmn_maker.py` script provided by this skill.

## Process
1. Analyze the business process and determine: participants/pools, lanes, nodes, edges, message flows.
2. Write a JSON file (e.g., `process.json`) using `write_to_file`.
3. Run: `python .skills/generate_bpmn/scripts/bpmn_maker.py process.json target_file.bpmn`
4. Verify the file was created.
5. (Optional) Remove the JSON file.

## Supported Element Types

### Events
`StartEvent`, `EndEvent`, `IntermediateCatchEvent`, `IntermediateThrowEvent`, `MessageStartEvent`, `TimerStartEvent`

### Boundary Events
`BoundaryEvent`, `BoundaryTimerEvent`, `BoundaryMessageEvent`
- Attach to a task using `"attachedTo": "Task_Id"`
- Non-interrupting: add `"cancelActivity": "false"`

### Tasks
`Task`, `UserTask`, `ServiceTask`, `SendTask`, `ReceiveTask`, `ManualTask`, `ScriptTask`, `BusinessRuleTask`, `CallActivity`

### Gateways
`ExclusiveGateway`, `ParallelGateway`, `EventBasedGateway`, `InclusiveGateway`
- Use `"default_flow": "Flow_Id"` for default outgoing branch

### Other
- `SubProcess` (expanded, with nested `nodes` and `edges`)
- `TextAnnotation` (with `"text": "..."`, linked via `associations` array)
- `DataObjectReference`, `DataStoreReference`

## Event Definitions

Add an `event_definition` object to any event node:

```json
{"id": "Timer_1", "type": "IntermediateCatchEvent", "name": "3 Tage vergangen",
 "event_definition": {"type": "timer", "duration": "P3D"}}
```

```json
{"id": "Msg_1", "type": "IntermediateCatchEvent", "name": "Nachricht erhalten",
 "event_definition": {"type": "message"}}
```

Supported types: `message`, `timer`, `conditional`, `signal`, `error`, `escalation`, `compensation`, `cancel`, `link`, `terminate`.

Timer specifics: `duration` (ISO 8601, e.g. `P3D`), `timeDate` (specific date), `timeCycle` (repeating).
`MessageStartEvent`, `TimerStartEvent`, `BoundaryTimerEvent`, `BoundaryMessageEvent` add definitions automatically.

---

## JSON Format — Single Process (with Lanes)

```json
{
  "process_id": "Process_1",
  "name": "Fahrradreparatur",
  "lanes": [
    {"id": "Lane_Kunde", "name": "Kunde"},
    {"id": "Lane_Radladen", "name": "Radladenbesitzer"}
  ],
  "nodes": [
    {"id": "Start_1", "type": "StartEvent", "name": "Fahrrad gebracht", "lane": "Lane_Kunde"},
    {"id": "Task_1", "type": "UserTask", "name": "Defekte identifizieren", "lane": "Lane_Radladen"},
    {"id": "Gw_1", "type": "EventBasedGateway", "name": "Warten", "lane": "Lane_Radladen"},
    {"id": "Timer_1", "type": "IntermediateCatchEvent", "name": "3 Tage",
     "lane": "Lane_Radladen", "event_definition": {"type": "timer", "duration": "P3D"}},
    {"id": "End_1", "type": "EndEvent", "name": "Ende", "lane": "Lane_Kunde"}
  ],
  "edges": [
    {"id": "Flow_1", "source": "Start_1", "target": "Task_1"},
    {"id": "Flow_2", "source": "Task_1", "target": "Gw_1"},
    {"id": "Flow_3", "source": "Gw_1", "target": "Timer_1"},
    {"id": "Flow_4", "source": "Timer_1", "target": "End_1"}
  ]
}
```

## JSON Format — Multi-Pool Collaboration

```json
{
  "participants": [
    {
      "id": "Participant_Tenant",
      "process_id": "Process_Tenant",
      "name": "Wohnungssuchender",
      "nodes": [
        {"id": "Start_T", "type": "StartEvent", "name": "Wohnung benötigt"},
        {"id": "Task_Search", "type": "Task", "name": "Wohnungen suchen"},
        {"id": "Task_Send", "type": "SendTask", "name": "Anfrage senden"},
        {"id": "End_T", "type": "EndEvent", "name": "Ende"}
      ],
      "edges": [
        {"id": "F_T1", "source": "Start_T", "target": "Task_Search"},
        {"id": "F_T2", "source": "Task_Search", "target": "Task_Send"},
        {"id": "F_T3", "source": "Task_Send", "target": "End_T"}
      ]
    },
    {
      "id": "Participant_Landlord",
      "process_id": "Process_Landlord",
      "name": "Vermieter",
      "nodes": [
        {"id": "Start_L", "type": "MessageStartEvent", "name": "Anfrage erhalten"},
        {"id": "Task_Review", "type": "Task", "name": "Anfrage prüfen"},
        {"id": "End_L", "type": "EndEvent", "name": "Ende"}
      ],
      "edges": [
        {"id": "F_L1", "source": "Start_L", "target": "Task_Review"},
        {"id": "F_L2", "source": "Task_Review", "target": "End_L"}
      ]
    }
  ],
  "message_flows": [
    {"id": "Msg_1", "source": "Task_Send", "target": "Start_L", "name": "Bewerbung"}
  ]
}
```

## Boundary Events

Attach events to the bottom border of a task:

```json
{"id": "Boundary_Timer", "type": "BoundaryTimerEvent", "name": "Timeout",
 "attachedTo": "Task_Main", "lane": "Lane_1",
 "event_definition": {"type": "timer", "duration": "P1D"}}
```

Non-interrupting boundary event:
```json
{"id": "Boundary_Msg", "type": "BoundaryMessageEvent", "name": "Nachricht",
 "attachedTo": "Task_Main", "lane": "Lane_1", "cancelActivity": "false"}
```

## Text Annotations & Associations

```json
{
  "nodes": [
    {"id": "Annotation_1", "type": "TextAnnotation", "text": "Wichtiger Hinweis"}
  ],
  "associations": [
    {"id": "Assoc_1", "source": "Task_1", "target": "Annotation_1"}
  ]
}
```

## Sub-Processes

Nest `nodes` and `edges` inside a SubProcess node:

```json
{"id": "SP_1", "type": "SubProcess", "name": "Wohnung finden", "lane": "Lane_1",
 "nodes": [
   {"id": "SP_Start", "type": "StartEvent", "name": ""},
   {"id": "SP_Task", "type": "Task", "name": "Anzeigen lesen"},
   {"id": "SP_End", "type": "EndEvent", "name": ""}
 ],
 "edges": [
   {"id": "SP_F1", "source": "SP_Start", "target": "SP_Task"},
   {"id": "SP_F2", "source": "SP_Task", "target": "SP_End"}
 ]}
```

## Default Flows

Set a default outgoing flow on an exclusive/inclusive gateway:

```json
{"id": "Gw_1", "type": "ExclusiveGateway", "name": "Prüfung?",
 "default_flow": "Flow_Default"}
```

## Layout

- **Smart port selection**: Gateway branches exit from top/bottom ports; forward flows use right→left; backward loops wrap around with clearance
- **Overlap avoidance**: Edges are rerouted around elements they would cross
- **Dynamic labels**: Label width scales with text length; gateway branch labels positioned near the source
- **Pool width normalization**: In multi-pool mode, all pools use the same width for visual alignment
- **Lanes**: Sized proportionally based on node count
- **Manual override**: You can set explicit `"x"` and `"y"` on any node
- Open the result in **Camunda Modeler** for final adjustments if needed

## BPMN 2.0 Semantic Rules

Always follow these when designing processes:

1. **Continuous Sequence Flows**: A token must travel from Start to End within one Pool. Sequence flows cannot cross pool boundaries.
2. **Message Flows**: Communication between Pools uses Message Flows (dashed lines). They connect elements in different pools only.
3. **Sub-Processes**: Group related tasks/loops inside expanded Sub-Processes.
4. **Intermediate Catch Events**: Use Message/Timer Catch Events for wait states.
5. **Event-Based Gateways**: When waiting for one of multiple possible messages, use an Event-Based Gateway before the Catch Events.
6. **Message Start Events**: If a participant's process starts because of a message, use `MessageStartEvent`.
7. **Deadlock Prevention**: Always ensure tokens can reach an End Event. Use Timer Catch Events via Event-Based Gateways for timeouts.
8. **Gateway Labels**: Exclusive Gateways should have a question as their name. Outgoing edges should have condition labels (e.g., "Ja", "Nein").
9. **Parallel Gateways**: Use matching split/join pairs. All forked paths must converge.
10. **Boundary Events**: Use boundary events for exception handling and timeouts on tasks. Always provide an outgoing sequence flow from a boundary event.
11. **Default Flows**: Mark one outgoing flow from exclusive/inclusive gateways as default when not all conditions are labeled.
