# Camunda + GitHub CI/CD Pipeline
## Automatisches Deployment von BPMN-Prozessen

Dieses Repository enthält einen vollständigen DevOps-Workflow für Geschäftsprozesse, die in **Camunda Platform 8** modelliert und über **GitHub Actions** automatisch deployed werden.

---

## 1. Projektbeschreibung

Das Ziel dieses Projekts ist die Verknüpfung von Geschäftsprozessmanagement mit modernen Software-Engineering-Praktiken. Prozessmodelle werden versioniert, validiert und über eine CI/CD-Pipeline in verschiedene Umgebungen (Dev, Staging, Prod) verteilt.

### Kernfunktionen
* **Modellierung**: Nutzung des Camunda Web Modelers.
* **Versionierung**: Synchronisation der BPMN-Modelle mit diesem GitHub-Repository.
* **Automatisierung**: Validierung und Deployment der Prozesse mittels GitHub Actions.
* **Infrastruktur**: Lokale Camunda-Instanz via Docker Desktop.

---

## 2. Technologiestack

| Technologie | Version / Variante | Zweck |
| :--- | :--- | :--- |
| **Camunda Platform 8** | SaaS / Self-hosted (v8.6) | Process Engine und Web Modeler |
| **GitHub** | github.com | Versionierung und CI/CD |
| **GitHub Actions** | YAML Workflows | Automatisches Deployment |
| **Docker** | Docker Desktop | Lokale Camunda-Instanz |
| **BPMN 2.0** | Standard | Prozessmodellierung |
| **Python 3.12** | Skripte | Deployment-Automatisierung |
| **Elasticsearch** | 8.15.3 | Prozess-Indizierung |

---

## 3. Repository Struktur

```
├── .github/
│   └── workflows/
│       ├── validate.yml          # BPMN-Validierung bei Pull Requests
│       └── deploy.yml            # Automatisches Deployment bei Merge
├── processes/
│   ├── dev/                      # Entwicklungs-Prozesse
│   │   └── urlaubsantrag.bpmn   # Urlaubsantragsprozess
│   └── prod/                     # Produktions-Prozesse
├── scripts/
│   ├── validate_bpmn.sh          # XML-Validierungsskript
│   └── deploy_process.py         # Deployment via Camunda REST API
├── docker-compose.yml            # Lokale Camunda 8 Instanz
└── README.md                     # Diese Dokumentation
```

---

## 4. CI/CD Workflow

Die Pipeline automatisiert den Weg vom Entwurf bis zur Produktion:

### 4.1 Validierung (Pull Request)

Bei jedem Pull Request auf `main` oder `staging` wird automatisch geprüft:

1. **XML-Wohlgeformtheit**: Alle `.bpmn`-Dateien werden auf korrektes XML geprüft.
2. **BPMN-Namespace**: Vorhandensein des BPMN 2.0 Namespaces.
3. **Prozess-Elemente**: Mindestens ein `<process>`-Element muss vorhanden sein.

```
Pull Request → validate.yml → scripts/validate_bpmn.sh → ✅/❌
```

### 4.2 Deployment (Merge)

Nach dem Merge auf `staging` oder `main`:

1. **Umgebung bestimmen**: `main` → Produktion (`processes/prod/`), `staging` → Staging (`processes/dev/`).
2. **Änderungen ermitteln**: Nur geänderte BPMN-Dateien werden deployed.
3. **Authentifizierung**: OAuth 2.0 Client Credentials gegen Camunda Cloud.
4. **Deployment**: Upload via Zeebe REST API.

```
Merge → deploy.yml → OAuth 2.0 → Zeebe REST API → ✅
```

---

## 5. Setup & Installation

Die Umgebung wurde unter **Ubuntu 24.04 LTS** getestet.

### 5.1 Voraussetzungen

* [Docker Desktop](https://www.docker.com/products/docker-desktop/) installiert und gestartet
* Git installiert
* Python 3.12+ (für Deployment-Skript)
* Camunda Cloud Account (für SaaS-Deployment)

### 5.2 Lokale Camunda-Instanz starten

```bash
# Repository klonen
git clone https://github.com/<DEIN-USERNAME>/Github-Pipeline.git
cd Github-Pipeline

# Camunda Platform 8 starten
docker compose up -d
```

Nach dem Start sind folgende Services verfügbar:

| Service | URL | Beschreibung |
| :--- | :--- | :--- |
| **Operate** | http://localhost:8081 | Prozess-Monitoring |
| **Tasklist** | http://localhost:8082 | Aufgabenverwaltung |
| **Zeebe Gateway** | localhost:26500 | gRPC API |
| **Connectors** | http://localhost:8085 | Konnektoren |
| **Elasticsearch** | http://localhost:9200 | Suchmaschine |

### 5.3 GitHub Secrets konfigurieren

Für das automatische Deployment müssen folgende Secrets im Repository unter **Settings → Secrets and variables → Actions** konfiguriert werden:

| Secret | Beschreibung |
| :--- | :--- |
| `CAMUNDA_CLIENT_ID` | OAuth 2.0 Client ID aus der Camunda Cloud Console |
| `CAMUNDA_CLIENT_SECRET` | OAuth 2.0 Client Secret |
| `CAMUNDA_CLUSTER_ID` | ID des Camunda Cloud Clusters |

So erstellst du die Credentials:
1. Logge dich in die [Camunda Cloud Console](https://console.cloud.camunda.io/) ein.
2. Gehe zu **Organization → API → Create New Client**.
3. Wähle die Scopes: `Zeebe`.
4. Kopiere die generierten Werte in die GitHub Secrets.

### 5.4 Branch-Strategie

```
feature/* ─── Pull Request ──→ staging ──→ main
                   │                          │
              Validierung              Prod-Deployment
                   │
            Staging-Deployment
```

* **Feature-Branches**: Entwicklung neuer/geänderter Prozesse
* **staging**: Testumgebung, automatisches Deployment nach Merge
* **main**: Produktionsumgebung, automatisches Deployment nach Merge

---

## 6. Beispielprozess — Urlaubsantrag

Als Demonstrationsobjekt dient ein **Urlaubsantragsprozess** mit drei Pools:

### Pool 1: Mitarbeiter/in
* Urlaubsantrag ausfüllen und einreichen
* Entscheid empfangen
* Bei Genehmigung: Urlaub planen
* Bei Ablehnung: Antrag anpassen oder verzichten

### Pool 2: Vorgesetzte/r
* Antrag prüfen
* Genehmigung erteilen oder Ablehnung mitteilen
* Entscheid an Mitarbeiter senden
* HR-System benachrichtigen

### Pool 3: HR-System
* Benachrichtigung empfangen
* Bei Genehmigung: Urlaubstage in Datenbank eintragen und Bestätigung senden
* Bei Ablehnung: Ablehnung protokollieren

Die Kommunikation zwischen den Pools erfolgt über **Message Flows** (BPMN 2.0-konform).

---

## 7. Nutzung

### Neuen Prozess hinzufügen

```bash
# 1. Feature-Branch erstellen
git checkout -b feature/neuer-prozess

# 2. BPMN-Datei in processes/dev/ ablegen
cp mein-prozess.bpmn processes/dev/

# 3. Änderungen committen und pushen
git add .
git commit -m "feat: Neuen Prozess hinzufügen"
git push origin feature/neuer-prozess

# 4. Pull Request erstellen → Automatische Validierung
# 5. Nach Review: Merge → Automatisches Deployment
```

### Lokales Testen

```bash
# Validierung lokal ausführen
bash scripts/validate_bpmn.sh

# Manuelles Deployment (erfordert Credentials)
python scripts/deploy_process.py \
  --file processes/dev/urlaubsantrag.bpmn \
  --client-id <CLIENT_ID> \
  --client-secret <CLIENT_SECRET> \
  --cluster-id <CLUSTER_ID>
```

---

## Lizenz

Dieses Projekt wurde im Rahmen des Moduls **M254** erstellt.
