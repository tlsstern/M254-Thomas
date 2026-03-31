# Camunda + GitHub CI/CD Pipeline
## Automatisches Deployment von BPMN-Prozessen

[cite_start]Dieses Repository enthält einen vollständigen DevOps-Workflow für Geschäftsprozesse, die in **Camunda Platform 8** modelliert und über **GitHub Actions** automatisch deployed werden[cite: 3, 4, 32].

---

## 1. Projektbeschreibung
[cite_start]Das Ziel dieses Projekts ist die Verknüpfung von Geschäftsprozessmanagement mit modernen Software-Engineering-Praktiken[cite: 38]. [cite_start]Prozessmodelle werden versioniert, validiert und über eine CI/CD-Pipeline in verschiedene Umgebungen (Dev, Staging, Prod) verteilt[cite: 31, 37].

### Kernfunktionen
* [cite_start]**Modellierung**: Nutzung des Camunda Web Modelers[cite: 35].
* [cite_start]**Versionierung**: Synchronisation der BPMN-Modelle mit diesem GitHub-Repository[cite: 35].
* [cite_start]**Automatisierung**: Validierung und Deployment der Prozesse mittels GitHub Actions[cite: 36].
* [cite_start]**Infrastruktur**: Lokale Camunda-Instanz via Docker Desktop[cite: 58, 59].

---

## 2. Technologiestack
| Technologie | Version / Variante | Zweck |
| :--- | :--- | :--- |
| **Camunda Platform 8** | SaaS / Self-hosted | [cite_start]Process Engine und Web Modeler [cite: 48, 49, 50] |
| **GitHub** | github.com | [cite_start]Versionierung und CI/CD [cite: 51, 52, 53] |
| **GitHub Actions** | YAML Workflows | [cite_start]Automatisches Deployment [cite: 54, 55, 56] |
| **Docker** | Docker Desktop | [cite_start]Lokale Camunda-Instanz [cite: 57, 58, 59] |
| **BPMN 2.0** | Standard | [cite_start]Prozessmodellierung [cite: 63, 64, 65] |

---

## 3. Repository Struktur
[cite_start]Das Repository ist wie folgt aufgebaut[cite: 83]:

* [cite_start]`.github/workflows/`: Enthält die YAML-Dateien für die GitHub Actions[cite: 86, 87].
* [cite_start]`processes/`: Speicherort für BPMN-Dateien, unterteilt in `dev/` und `prod/`[cite: 88, 90, 92].
* [cite_start]`scripts/`: Deployment-Hilfsskripte (Shell/Python) für die Interaktion mit der Camunda API[cite: 94, 95].
* [cite_start]`README.md`: Diese Dokumentation[cite: 96, 97].

---

## 4. CI/CD Workflow
[cite_start]Die Pipeline automatisiert den Weg vom Entwurf bis zur Produktion[cite: 106]:

1.  [cite_start]**Modellierung**: Prozess im Camunda Web Modeler bearbeiten[cite: 107].
2.  [cite_start]**Sync**: Push der BPMN-Datei in den GitHub Branch via Web Modeler[cite: 108].
3.  [cite_start]**Validierung**: Bei einem Pull Request prüft die Pipeline automatisch die XML-Validität der BPMN-Datei[cite: 99, 100].
4.  [cite_start]**Deployment**: Nach dem Merge (auf `staging` oder `main`) authentifiziert sich die Pipeline via OAuth 2.0 und deployed den Prozess über die Camunda REST API[cite: 102, 103, 104].


---

## 5. Setup & Installation
[cite_start]Die Umgebung wurde erfolgreich unter **Ubuntu 24.04 LTS** getestet[cite: 73].

### Voraussetzungen
* [cite_start]Docker Desktop installiert und gestartet[cite: 67].
* [cite_start]Camunda 8 via Docker Compose aufgesetzt (Standard-Port: 8080)[cite: 68, 69].

### GitHub Secrets
[cite_start]Für das automatische Deployment müssen folgende Secrets im Repository konfiguriert werden[cite: 71]:
* `CAMUNDA_CLIENT_ID`
* `CAMUNDA_CLIENT_SECRET`
* `CAMUNDA_CLUSTER_ID`

---

## 6. Beispielprozess
[cite_start]Als Demonstrationsobjekt dient ein **Urlaubsantragsprozess** mit drei Pools[cite: 74]:
* [cite_start]**Mitarbeiter/in**: Antrag einreichen und Entscheid empfangen[cite: 76].
* [cite_start]**Vorgesetzte/r**: Prüfung und Genehmigung/Ablehnung[cite: 78].
* [cite_start]**HR-System**: Automatisierter Eintrag in die Datenbank und Benachrichtigung[cite: 80].