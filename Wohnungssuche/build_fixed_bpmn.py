import os
import xml.etree.ElementTree as ET
from xml.dom import minidom

XML_CONTENT = """<?xml version="1.0" encoding="UTF-8"?>
<bpmn:definitions xmlns:bpmn="http://www.omg.org/spec/BPMN/20100524/MODEL"
                  xmlns:bpmndi="http://www.omg.org/spec/BPMN/20100524/DI"
                  xmlns:dc="http://www.omg.org/spec/DD/20100524/DC"
                  xmlns:di="http://www.omg.org/spec/DD/20100524/DI"
                  id="Definitions_1" targetNamespace="http://bpmn.io/schema/bpmn">

  <bpmn:collaboration id="Collaboration_1">
    <bpmn:participant id="Participant_Tenant" name="Wohnungssuchender" processRef="Process_Tenant" />
    <bpmn:participant id="Participant_Landlord" name="Vermieter" processRef="Process_Landlord" />
    <bpmn:messageFlow id="Msg_1" sourceRef="Task_SendRequest" targetRef="Start_Vermieter" />
    <bpmn:messageFlow id="Msg_2" sourceRef="Task_SendRejection" targetRef="Catch_Rejection" />
    <bpmn:messageFlow id="Msg_3" sourceRef="Task_SendInvite" targetRef="Catch_Invite" />
    <bpmn:messageFlow id="Msg_4" sourceRef="Task_InformInterest" targetRef="Catch_Interest" />
    <bpmn:messageFlow id="Msg_5" sourceRef="Task_SendContract" targetRef="Catch_Contract" />
    <bpmn:messageFlow id="Msg_6" sourceRef="Task_SendContractBack" targetRef="Catch_ContractBack" />
    
    <!-- New explicit rejection message flow for Mieter Deadlock 2 -->
    <bpmn:messageFlow id="Msg_7" sourceRef="Task_SendFinalRejection" targetRef="Catch_FinalRejection" />
  </bpmn:collaboration>

  <bpmn:process id="Process_Tenant" isExecutable="true">
    <bpmn:startEvent id="Start_1" name="Wohnung wird benötigt">
      <bpmn:outgoing>Flow_T1</bpmn:outgoing>
    </bpmn:startEvent>

    <bpmn:subProcess id="SubProcess_WohnungFinden" name="Wohnung finden">
      <bpmn:incoming>Flow_T1</bpmn:incoming>
      <bpmn:outgoing>Flow_T2</bpmn:outgoing>
      <bpmn:startEvent id="SubStart">
        <bpmn:outgoing>Flow_S1</bpmn:outgoing>
      </bpmn:startEvent>
      <bpmn:task id="Task_ReadAds" name="Anzeigen lesen und bewerten">
        <bpmn:incoming>Flow_S1</bpmn:incoming>
        <bpmn:incoming>Flow_S3</bpmn:incoming>
        <bpmn:outgoing>Flow_S2</bpmn:outgoing>
      </bpmn:task>
      <bpmn:exclusiveGateway id="Gw_Found" name="Passende gefunden?">
        <bpmn:incoming>Flow_S2</bpmn:incoming>
        <bpmn:outgoing>Flow_S3</bpmn:outgoing>
        <bpmn:outgoing>Flow_S4</bpmn:outgoing>
      </bpmn:exclusiveGateway>
      <bpmn:endEvent id="SubEnd">
        <bpmn:incoming>Flow_S4</bpmn:incoming>
      </bpmn:endEvent>
      <bpmn:sequenceFlow id="Flow_S1" sourceRef="SubStart" targetRef="Task_ReadAds" />
      <bpmn:sequenceFlow id="Flow_S2" sourceRef="Task_ReadAds" targetRef="Gw_Found" />
      <bpmn:sequenceFlow id="Flow_S3" name="Nein" sourceRef="Gw_Found" targetRef="Task_ReadAds" />
      <bpmn:sequenceFlow id="Flow_S4" name="Ja" sourceRef="Gw_Found" targetRef="SubEnd" />
    </bpmn:subProcess>

    <bpmn:task id="Task_PrepRequest" name="Anfrage vorbereiten">
      <bpmn:incoming>Flow_T2</bpmn:incoming>
      <bpmn:outgoing>Flow_T3</bpmn:outgoing>
    </bpmn:task>
    
    <bpmn:sendTask id="Task_SendRequest" name="Anfrage versenden">
      <bpmn:incoming>Flow_T3</bpmn:incoming>
      <bpmn:outgoing>Flow_T4</bpmn:outgoing>
    </bpmn:sendTask>
    
    <bpmn:eventBasedGateway id="Gw_EventBased">
      <bpmn:incoming>Flow_T4</bpmn:incoming>
      <bpmn:outgoing>Flow_T5</bpmn:outgoing>
      <bpmn:outgoing>Flow_T6</bpmn:outgoing>
    </bpmn:eventBasedGateway>

    <bpmn:intermediateCatchEvent id="Catch_Rejection" name="Absage erhalten">
      <bpmn:incoming>Flow_T5</bpmn:incoming>
      <bpmn:outgoing>Flow_T7</bpmn:outgoing>
      <bpmn:messageEventDefinition id="MessageEventDefinition_1" />
    </bpmn:intermediateCatchEvent>
    
    <bpmn:intermediateCatchEvent id="Catch_Invite" name="Einladung erhalten">
      <bpmn:incoming>Flow_T6</bpmn:incoming>
      <bpmn:outgoing>Flow_T8</bpmn:outgoing>
      <bpmn:messageEventDefinition id="MessageEventDefinition_2" />
    </bpmn:intermediateCatchEvent>
    
    <bpmn:endEvent id="End_Rejection" name="Abgeschlossen (Absage)">
      <bpmn:incoming>Flow_T7</bpmn:incoming>
    </bpmn:endEvent>

    <bpmn:task id="Task_Visit" name="Wohnung besichtigen">
      <bpmn:incoming>Flow_T8</bpmn:incoming>
      <bpmn:outgoing>Flow_T9</bpmn:outgoing>
    </bpmn:task>

    <bpmn:exclusiveGateway id="Gw_Rent" name="Mieten?">
      <bpmn:incoming>Flow_T9</bpmn:incoming>
      <bpmn:outgoing>Flow_T10</bpmn:outgoing>
      <bpmn:outgoing>Flow_T11</bpmn:outgoing>
    </bpmn:exclusiveGateway>

    <bpmn:endEvent id="End_NoRent" name="Abgeschlossen (Kein Interesse)">
      <bpmn:incoming>Flow_T10</bpmn:incoming>
    </bpmn:endEvent>

    <bpmn:sendTask id="Task_InformInterest" name="Interesse mitteilen">
      <bpmn:incoming>Flow_T11</bpmn:incoming>
      <bpmn:outgoing>Flow_T12</bpmn:outgoing>
    </bpmn:sendTask>

    <!-- NEW: Event-Based Gateway to prevent Tenant Deadlock 2 -->
    <bpmn:eventBasedGateway id="Gw_WaitDecision">
      <bpmn:incoming>Flow_T12</bpmn:incoming>
      <bpmn:outgoing>Flow_T18</bpmn:outgoing>
      <bpmn:outgoing>Flow_T19</bpmn:outgoing>
    </bpmn:eventBasedGateway>

    <bpmn:intermediateCatchEvent id="Catch_FinalRejection" name="Absage erhalten">
      <bpmn:incoming>Flow_T18</bpmn:incoming>
      <bpmn:outgoing>Flow_T20</bpmn:outgoing>
      <bpmn:messageEventDefinition id="MessageEventDefinition_7" />
    </bpmn:intermediateCatchEvent>
    
    <bpmn:endEvent id="End_FinalRejection" name="Abgeschlossen (Absage)">
      <bpmn:incoming>Flow_T20</bpmn:incoming>
    </bpmn:endEvent>

    <bpmn:intermediateCatchEvent id="Catch_Contract" name="Vertrag erhalten">
      <bpmn:incoming>Flow_T19</bpmn:incoming>
      <bpmn:outgoing>Flow_T13</bpmn:outgoing>
      <bpmn:messageEventDefinition id="MessageEventDefinition_3" />
    </bpmn:intermediateCatchEvent>

    <bpmn:task id="Task_SignContract" name="Vertrag unterschreiben">
      <bpmn:incoming>Flow_T13</bpmn:incoming>
      <bpmn:outgoing>Flow_T14</bpmn:outgoing>
    </bpmn:task>

    <bpmn:sendTask id="Task_SendContractBack" name="Vertrag zurücksenden">
      <bpmn:incoming>Flow_T14</bpmn:incoming>
      <bpmn:outgoing>Flow_T15</bpmn:outgoing>
    </bpmn:sendTask>

    <bpmn:endEvent id="End_TenantSuccess" name="Erfolgreich gemietet">
      <bpmn:incoming>Flow_T15</bpmn:incoming>
    </bpmn:endEvent>

    <!-- Tenant Sequence Flows -->
    <bpmn:sequenceFlow id="Flow_T1" sourceRef="Start_1" targetRef="SubProcess_WohnungFinden" />
    <bpmn:sequenceFlow id="Flow_T2" sourceRef="SubProcess_WohnungFinden" targetRef="Task_PrepRequest" />
    <bpmn:sequenceFlow id="Flow_T3" sourceRef="Task_PrepRequest" targetRef="Task_SendRequest" />
    <bpmn:sequenceFlow id="Flow_T4" sourceRef="Task_SendRequest" targetRef="Gw_EventBased" />
    <bpmn:sequenceFlow id="Flow_T5" sourceRef="Gw_EventBased" targetRef="Catch_Rejection" />
    <bpmn:sequenceFlow id="Flow_T6" sourceRef="Gw_EventBased" targetRef="Catch_Invite" />
    <bpmn:sequenceFlow id="Flow_T7" sourceRef="Catch_Rejection" targetRef="End_Rejection" />
    <bpmn:sequenceFlow id="Flow_T8" sourceRef="Catch_Invite" targetRef="Task_Visit" />
    <bpmn:sequenceFlow id="Flow_T9" sourceRef="Task_Visit" targetRef="Gw_Rent" />
    <bpmn:sequenceFlow id="Flow_T10" name="Nein" sourceRef="Gw_Rent" targetRef="End_NoRent" />
    <bpmn:sequenceFlow id="Flow_T11" name="Ja" sourceRef="Gw_Rent" targetRef="Task_InformInterest" />
    
    <bpmn:sequenceFlow id="Flow_T12" sourceRef="Task_InformInterest" targetRef="Gw_WaitDecision" />
    <bpmn:sequenceFlow id="Flow_T18" sourceRef="Gw_WaitDecision" targetRef="Catch_FinalRejection" />
    <bpmn:sequenceFlow id="Flow_T19" sourceRef="Gw_WaitDecision" targetRef="Catch_Contract" />
    <bpmn:sequenceFlow id="Flow_T20" sourceRef="Catch_FinalRejection" targetRef="End_FinalRejection" />
    
    <bpmn:sequenceFlow id="Flow_T13" sourceRef="Catch_Contract" targetRef="Task_SignContract" />
    <bpmn:sequenceFlow id="Flow_T14" sourceRef="Task_SignContract" targetRef="Task_SendContractBack" />
    <bpmn:sequenceFlow id="Flow_T15" sourceRef="Task_SendContractBack" targetRef="End_TenantSuccess" />
  </bpmn:process>

  <bpmn:process id="Process_Landlord" isExecutable="true">
    <!-- NEW: Start Event is a Message Start Event -->
    <bpmn:startEvent id="Start_Vermieter" name="Anfrage erhalten">
      <bpmn:outgoing>Flow_V1</bpmn:outgoing>
      <bpmn:messageEventDefinition id="MessageEventDefinition_4" />
    </bpmn:startEvent>

    <bpmn:exclusiveGateway id="Gw_Interesting" name="Interessant?">
      <bpmn:incoming>Flow_V1</bpmn:incoming>
      <bpmn:outgoing>Flow_V2</bpmn:outgoing>
      <bpmn:outgoing>Flow_V3</bpmn:outgoing>
    </bpmn:exclusiveGateway>

    <bpmn:sendTask id="Task_SendRejection" name="Absage senden">
      <bpmn:incoming>Flow_V2</bpmn:incoming>
      <bpmn:outgoing>Flow_V4</bpmn:outgoing>
    </bpmn:sendTask>

    <bpmn:endEvent id="End_V_Rejection" name="Abgeschlossen">
      <bpmn:incoming>Flow_V4</bpmn:incoming>
    </bpmn:endEvent>

    <bpmn:sendTask id="Task_SendInvite" name="Einladung senden">
      <bpmn:incoming>Flow_V3</bpmn:incoming>
      <bpmn:outgoing>Flow_V5</bpmn:outgoing>
    </bpmn:sendTask>

    <!-- NEW: Event-Based Gateway for Timeout to prevent Landlord Deadlock 1 -->
    <bpmn:eventBasedGateway id="Gw_WaitInterest">
      <bpmn:incoming>Flow_V5</bpmn:incoming>
      <bpmn:outgoing>Flow_V12</bpmn:outgoing>
      <bpmn:outgoing>Flow_V13</bpmn:outgoing>
    </bpmn:eventBasedGateway>

    <bpmn:intermediateCatchEvent id="Catch_InterestTimeout" name="Keine Antwort (z.B. 1 Woche)">
      <bpmn:incoming>Flow_V12</bpmn:incoming>
      <bpmn:outgoing>Flow_V14</bpmn:outgoing>
      <bpmn:timerEventDefinition id="TimerEventDefinition_1">
        <bpmn:timeDuration>P7D</bpmn:timeDuration>
      </bpmn:timerEventDefinition>
    </bpmn:intermediateCatchEvent>

    <bpmn:endEvent id="End_V_Ghosted" name="Abgeschlossen (Kein Interesse)">
      <bpmn:incoming>Flow_V14</bpmn:incoming>
    </bpmn:endEvent>

    <bpmn:intermediateCatchEvent id="Catch_Interest" name="Interesse empfangen">
      <bpmn:incoming>Flow_V13</bpmn:incoming>
      <bpmn:outgoing>Flow_V6</bpmn:outgoing>
      <bpmn:messageEventDefinition id="MessageEventDefinition_5" />
    </bpmn:intermediateCatchEvent>

    <bpmn:task id="Task_FinalDecision" name="Entscheidung treffen">
      <bpmn:incoming>Flow_V6</bpmn:incoming>
      <bpmn:outgoing>Flow_V7</bpmn:outgoing>
    </bpmn:task>

    <bpmn:exclusiveGateway id="Gw_RentFinal" name="Vermieten?">
      <bpmn:incoming>Flow_V7</bpmn:incoming>
      <bpmn:outgoing>Flow_V8</bpmn:outgoing>
      <bpmn:outgoing>Flow_V9</bpmn:outgoing>
    </bpmn:exclusiveGateway>

    <!-- NEW: We must actually SEND the final rejection to the tenant -->
    <bpmn:sendTask id="Task_SendFinalRejection" name="Absage senden">
      <bpmn:incoming>Flow_V8</bpmn:incoming>
      <bpmn:outgoing>Flow_V15</bpmn:outgoing>
    </bpmn:sendTask>

    <bpmn:endEvent id="End_NoRentFinal" name="Keine Vermietung">
      <bpmn:incoming>Flow_V15</bpmn:incoming>
    </bpmn:endEvent>

    <bpmn:sendTask id="Task_SendContract" name="Mietvertrag senden">
      <bpmn:incoming>Flow_V9</bpmn:incoming>
      <bpmn:outgoing>Flow_V10</bpmn:outgoing>
    </bpmn:sendTask>

    <!-- Added timeout for contract signing too, to prevent deadlock if tenant never signs -->
    <bpmn:eventBasedGateway id="Gw_WaitContract">
      <bpmn:incoming>Flow_V10</bpmn:incoming>
      <bpmn:outgoing>Flow_V16</bpmn:outgoing>
      <bpmn:outgoing>Flow_V17</bpmn:outgoing>
    </bpmn:eventBasedGateway>

    <bpmn:intermediateCatchEvent id="Catch_ContractTimeout" name="Kein Vertrag (z.B. 2 Wochen)">
      <bpmn:incoming>Flow_V16</bpmn:incoming>
      <bpmn:outgoing>Flow_V18</bpmn:outgoing>
      <bpmn:timerEventDefinition id="TimerEventDefinition_2">
        <bpmn:timeDuration>P14D</bpmn:timeDuration>
      </bpmn:timerEventDefinition>
    </bpmn:intermediateCatchEvent>

    <bpmn:endEvent id="End_V_Ghosted2" name="Abgeschlossen (Frist abgelaufen)">
      <bpmn:incoming>Flow_V18</bpmn:incoming>
    </bpmn:endEvent>

    <bpmn:intermediateCatchEvent id="Catch_ContractBack" name="Vertrag erhalten">
      <bpmn:incoming>Flow_V17</bpmn:incoming>
      <bpmn:outgoing>Flow_V11</bpmn:outgoing>
      <bpmn:messageEventDefinition id="MessageEventDefinition_6" />
    </bpmn:intermediateCatchEvent>

    <bpmn:endEvent id="End_VermieterSuccess" name="Wohnung vermietet">
      <bpmn:incoming>Flow_V11</bpmn:incoming>
    </bpmn:endEvent>

    <!-- Landlord Sequence Flows -->
    <bpmn:sequenceFlow id="Flow_V1" sourceRef="Start_Vermieter" targetRef="Gw_Interesting" />
    <bpmn:sequenceFlow id="Flow_V2" name="Nein" sourceRef="Gw_Interesting" targetRef="Task_SendRejection" />
    <bpmn:sequenceFlow id="Flow_V3" name="Ja" sourceRef="Gw_Interesting" targetRef="Task_SendInvite" />
    <bpmn:sequenceFlow id="Flow_V4" sourceRef="Task_SendRejection" targetRef="End_V_Rejection" />
    
    <bpmn:sequenceFlow id="Flow_V5" sourceRef="Task_SendInvite" targetRef="Gw_WaitInterest" />
    <bpmn:sequenceFlow id="Flow_V12" sourceRef="Gw_WaitInterest" targetRef="Catch_InterestTimeout" />
    <bpmn:sequenceFlow id="Flow_V14" sourceRef="Catch_InterestTimeout" targetRef="End_V_Ghosted" />
    <bpmn:sequenceFlow id="Flow_V13" sourceRef="Gw_WaitInterest" targetRef="Catch_Interest" />
    
    <bpmn:sequenceFlow id="Flow_V6" sourceRef="Catch_Interest" targetRef="Task_FinalDecision" />
    <bpmn:sequenceFlow id="Flow_V7" sourceRef="Task_FinalDecision" targetRef="Gw_RentFinal" />
    <bpmn:sequenceFlow id="Flow_V8" name="Nein" sourceRef="Gw_RentFinal" targetRef="Task_SendFinalRejection" />
    <bpmn:sequenceFlow id="Flow_V15" sourceRef="Task_SendFinalRejection" targetRef="End_NoRentFinal" />
    <bpmn:sequenceFlow id="Flow_V9" name="Ja" sourceRef="Gw_RentFinal" targetRef="Task_SendContract" />
    
    <bpmn:sequenceFlow id="Flow_V10" sourceRef="Task_SendContract" targetRef="Gw_WaitContract" />
    <bpmn:sequenceFlow id="Flow_V16" sourceRef="Gw_WaitContract" targetRef="Catch_ContractTimeout" />
    <bpmn:sequenceFlow id="Flow_V18" sourceRef="Catch_ContractTimeout" targetRef="End_V_Ghosted2" />
    <bpmn:sequenceFlow id="Flow_V17" sourceRef="Gw_WaitContract" targetRef="Catch_ContractBack" />
    
    <bpmn:sequenceFlow id="Flow_V11" sourceRef="Catch_ContractBack" targetRef="End_VermieterSuccess" />
  </bpmn:process>
</bpmn:definitions>
"""

# Restructured layout coordinates to fit all the new nodes
layout = {
    # Participant Bounds
    "Participant_Tenant": (120, 60, 2400, 250),
    "Participant_Landlord": (120, 420, 2400, 420),

    # Tenant Pool
    "Start_1": (180, 202, 36, 36),
    "SubProcess_WohnungFinden": (260, 100, 450, 180),
    "SubStart": (290, 202, 36, 36),
    "Task_ReadAds": (360, 180, 120, 80),
    "Gw_Found": (530, 195, 50, 50),
    "SubEnd": (640, 202, 36, 36),

    "Task_PrepRequest": (760, 180, 100, 80),
    "Task_SendRequest": (900, 180, 100, 80),
    "Gw_EventBased": (1040, 195, 50, 50),
    
    "Catch_Rejection": (1130, 112, 36, 36),
    "End_Rejection": (1230, 112, 36, 36),
    
    "Catch_Invite": (1130, 202, 36, 36),
    "Task_Visit": (1230, 180, 100, 80),
    "Gw_Rent": (1370, 195, 50, 50),
    
    "End_NoRent": (1470, 112, 36, 36),
    
    "Task_InformInterest": (1470, 180, 100, 80),
    
    # New Event Gateway Tenant
    "Gw_WaitDecision": (1610, 195, 50, 50),
    
    "Catch_FinalRejection": (1710, 112, 36, 36),
    "End_FinalRejection": (1810, 112, 36, 36),
    
    "Catch_Contract": (1710, 202, 36, 36),
    "Task_SignContract": (1810, 180, 100, 80),
    "Task_SendContractBack": (1960, 180, 100, 80),
    "End_TenantSuccess": (2110, 202, 36, 36),

    # Landlord Pool
    "Start_Vermieter": (930, 602, 36, 36),
    "Gw_Interesting": (1020, 595, 50, 50),
    
    "Task_SendRejection": (1130, 470, 100, 80),
    "End_V_Rejection": (1250, 492, 36, 36),
    
    "Task_SendInvite": (1130, 580, 100, 80),
    
    # New Event Gateway Landlord
    "Gw_WaitInterest": (1280, 595, 50, 50),
    
    "Catch_InterestTimeout": (1380, 682, 36, 36),
    "End_V_Ghosted": (1480, 682, 36, 36),
    
    "Catch_Interest": (1380, 602, 36, 36),
    "Task_FinalDecision": (1480, 580, 100, 80),
    "Gw_RentFinal": (1620, 595, 50, 50),
    
    "Task_SendFinalRejection": (1730, 470, 100, 80),
    "End_NoRentFinal": (1870, 492, 36, 36),
    
    "Task_SendContract": (1730, 580, 100, 80),
    
    "Gw_WaitContract": (1870, 595, 50, 50),
    
    "Catch_ContractTimeout": (1970, 682, 36, 36),
    "End_V_Ghosted2": (2070, 682, 36, 36),
    
    "Catch_ContractBack": (1970, 602, 36, 36),
    "End_VermieterSuccess": (2100, 602, 36, 36)
}

# Calculated Waypoints
waypoints = {
    # Tenant Pool
    "Flow_S1": [(326, 220), (360, 220)],
    "Flow_S2": [(480, 220), (530, 220)],
    "Flow_S3": [(555, 195), (555, 140), (420, 140), (420, 180)],
    "Flow_S4": [(580, 220), (640, 220)],
    "Flow_T1": [(216, 220), (260, 220)],
    "Flow_T2": [(710, 220), (760, 220)],
    "Flow_T3": [(860, 220), (900, 220)],
    "Flow_T4": [(1000, 220), (1040, 220)],
    "Flow_T5": [(1065, 195), (1065, 130), (1130, 130)],
    "Flow_T6": [(1090, 220), (1130, 220)],
    "Flow_T7": [(1166, 130), (1230, 130)],
    "Flow_T8": [(1166, 220), (1230, 220)],
    "Flow_T9": [(1330, 220), (1370, 220)],
    "Flow_T10": [(1395, 195), (1395, 130), (1470, 130)],
    "Flow_T11": [(1420, 220), (1470, 220)],
    "Flow_T12": [(1570, 220), (1610, 220)],
    
    "Flow_T18": [(1635, 195), (1635, 130), (1710, 130)],
    "Flow_T19": [(1660, 220), (1710, 220)],
    "Flow_T20": [(1746, 130), (1810, 130)],
    
    "Flow_T13": [(1746, 220), (1810, 220)],
    "Flow_T14": [(1910, 220), (1960, 220)],
    "Flow_T15": [(2060, 220), (2110, 220)],
    
    # Landlord Pool
    "Flow_V1": [(966, 620), (1020, 620)],
    "Flow_V2": [(1045, 595), (1045, 510), (1130, 510)],
    "Flow_V3": [(1070, 620), (1130, 620)],
    "Flow_V4": [(1230, 510), (1250, 510)],
    "Flow_V5": [(1230, 620), (1280, 620)],
    "Flow_V12": [(1305, 645), (1305, 700), (1380, 700)],
    "Flow_V14": [(1416, 700), (1480, 700)],
    "Flow_V13": [(1330, 620), (1380, 620)],
    
    "Flow_V6": [(1416, 620), (1480, 620)],
    "Flow_V7": [(1580, 620), (1620, 620)],
    "Flow_V8": [(1645, 595), (1645, 510), (1730, 510)],
    "Flow_V15": [(1830, 510), (1870, 510)],
    "Flow_V9": [(1670, 620), (1730, 620)],
    
    "Flow_V10": [(1830, 620), (1870, 620)],
    "Flow_V16": [(1895, 645), (1895, 700), (1970, 700)],
    "Flow_V18": [(2006, 700), (2070, 700)],
    "Flow_V17": [(1920, 620), (1970, 620)],
    "Flow_V11": [(2006, 620), (2100, 620)],
    
    # Msg Flows
    "Msg_1": [(950, 260), (950, 431), (948, 431), (948, 602)],
    "Msg_2": [(1180, 470), (1180, 148)],
    "Msg_3": [(1180, 580), (1180, 238)],
    "Msg_4": [(1520, 260), (1520, 431), (1398, 431), (1398, 602)],
    "Msg_7": [(1780, 470), (1780, 309), (1728, 309), (1728, 148)],
    "Msg_5": [(1780, 580), (1780, 409), (1728, 409), (1728, 238)],
    "Msg_6": [(2010, 260), (2010, 430), (1988, 430), (1988, 602)]
}

def generate_bpmn():
    ET.register_namespace("bpmn", "http://www.omg.org/spec/BPMN/20100524/MODEL")
    ET.register_namespace("bpmndi", "http://www.omg.org/spec/BPMN/20100524/DI")
    ET.register_namespace("dc", "http://www.omg.org/spec/DD/20100524/DC")
    ET.register_namespace("di", "http://www.omg.org/spec/DD/20100524/DI")

    root = ET.fromstring(XML_CONTENT)
    diagram = ET.SubElement(root, "{http://www.omg.org/spec/BPMN/20100524/DI}BPMNDiagram", id="BPMNDiagram_1")
    plane = ET.SubElement(diagram, "{http://www.omg.org/spec/BPMN/20100524/DI}BPMNPlane", id="BPMNPlane_1", bpmnElement="Collaboration_1")

    for node_id, bounds in layout.items():
        is_horizontal = "true" if node_id.startswith("Participant") else "false"
        shape = ET.SubElement(plane, "{http://www.omg.org/spec/BPMN/20100524/DI}BPMNShape", id=f"{node_id}_di", bpmnElement=node_id)
        if is_horizontal == "true": shape.set("isHorizontal", "true")
            
        is_expanded = "true" if node_id.startswith("SubProcess") else "false"
        if is_expanded == "true": shape.set("isExpanded", "true")

        x, y, w, h = bounds
        ET.SubElement(shape, "{http://www.omg.org/spec/DD/20100524/DC}Bounds", x=str(x), y=str(y), width=str(w), height=str(h))

        if "End_" in node_id or "Start_" in node_id or "Catch_" in node_id or "Gw_" in node_id:
            label = ET.SubElement(shape, "{http://www.omg.org/spec/BPMN/20100524/DI}BPMNLabel")
            ET.SubElement(label, "{http://www.omg.org/spec/DD/20100524/DC}Bounds", x=str(x - 10), y=str(y + h + 5), width="60", height="14")


    all_flows = []
    for proc in root.findall(".//{http://www.omg.org/spec/BPMN/20100524/MODEL}sequenceFlow"): all_flows.append(proc)
    for flow in root.findall(".//{http://www.omg.org/spec/BPMN/20100524/MODEL}messageFlow"): all_flows.append(flow)

    for flow in all_flows:
        f_id = flow.get("id")
        if f_id in waypoints:
            edge_di = ET.SubElement(plane, "{http://www.omg.org/spec/BPMN/20100524/DI}BPMNEdge", id=f"{f_id}_di", bpmnElement=f_id)
            for wp in waypoints[f_id]:
                ET.SubElement(edge_di, "{http://www.omg.org/spec/DD/20100524/DI}waypoint", x=str(wp[0]), y=str(wp[1]))
            
            if flow.get("name"):
                pts = waypoints[f_id]
                hx = (pts[0][0] + pts[-1][0]) / 2 - 10
                hy = (pts[0][1] + pts[-1][1]) / 2 + 10
                label = ET.SubElement(edge_di, "{http://www.omg.org/spec/BPMN/20100524/DI}BPMNLabel")
                ET.SubElement(label, "{http://www.omg.org/spec/DD/20100524/DC}Bounds", x=str(int(hx)), y=str(int(hy)), width="40", height="14")

    xml_str = ET.tostring(root, 'utf-8')
    parsed = minidom.parseString(xml_str)
    pretty_xml = parsed.toprettyxml(indent="  ")

    with open(r"wohnungssuche.bpmn", 'w', encoding='utf-8') as f:
        clean_xml = '\\n'.join([line for line in pretty_xml.split('\\n') if line.strip()])
        f.write(clean_xml)

    print("Successfully generated valid BPMN 2.0 without deadlocks!")

if __name__ == "__main__":
    generate_bpmn()
