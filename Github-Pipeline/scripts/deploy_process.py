#!/usr/bin/env python3
"""
deploy_process.py
=================
Deployt eine BPMN-Datei auf Camunda Platform 8 (SaaS) via Zeebe REST API.

Authentifizierung erfolgt über OAuth 2.0 Client Credentials.

Verwendung:
    python deploy_process.py \
        --file processes/dev/urlaubsantrag.bpmn \
        --client-id <CLIENT_ID> \
        --client-secret <CLIENT_SECRET> \
        --cluster-id <CLUSTER_ID> \
        --region bru-2
"""

import argparse
import json
import os
import sys

import requests


# ── Konstanten ──────────────────────────────────────────────
OAUTH_URL = "https://login.cloud.camunda.io/oauth/token"
AUDIENCE = "zeebe.camunda.io"


def get_access_token(client_id: str, client_secret: str) -> str:
    """Holt ein OAuth 2.0 Access-Token von Camunda Cloud."""
    print("🔐 Authentifizierung bei Camunda Cloud...")

    payload = {
        "grant_type": "client_credentials",
        "client_id": client_id,
        "client_secret": client_secret,
        "audience": AUDIENCE,
    }

    response = requests.post(OAUTH_URL, json=payload, timeout=30)

    if response.status_code != 200:
        print(f"❌ Authentifizierung fehlgeschlagen: {response.status_code}")
        print(f"   {response.text}")
        sys.exit(1)

    token = response.json().get("access_token")
    if not token:
        print("❌ Kein Access-Token in der Antwort erhalten.")
        sys.exit(1)

    print("✅ Authentifizierung erfolgreich.")
    return token


def deploy_bpmn(
    file_path: str,
    token: str,
    cluster_id: str,
    region: str,
) -> None:
    """Deployt eine BPMN-Datei über die Zeebe REST API."""
    zeebe_url = f"https://{cluster_id}.{region}.zeebe.camunda.io/v2/deployments"

    file_name = os.path.basename(file_path)
    print(f"🚀 Deploye '{file_name}' auf Cluster {cluster_id}...")

    headers = {
        "Authorization": f"Bearer {token}",
    }

    with open(file_path, "rb") as bpmn_file:
        files = {
            "resources": (file_name, bpmn_file, "application/octet-stream"),
        }

        response = requests.post(
            zeebe_url,
            headers=headers,
            files=files,
            timeout=60,
        )

    if response.status_code in (200, 201):
        result = response.json()
        print(f"✅ Deployment erfolgreich!")
        print(f"   Key: {result.get('deploymentKey', 'N/A')}")

        # Deployment-Details ausgeben
        deployments = result.get("deployments", [])
        for dep in deployments:
            process_def = dep.get("processDefinition", {})
            if process_def:
                print(f"   Prozess: {process_def.get('bpmnProcessId', 'N/A')}")
                print(f"   Version: {process_def.get('version', 'N/A')}")
    else:
        print(f"❌ Deployment fehlgeschlagen: {response.status_code}")
        print(f"   {response.text}")
        sys.exit(1)


def main():
    parser = argparse.ArgumentParser(
        description="Deployt BPMN-Prozesse auf Camunda Platform 8 (SaaS)"
    )
    parser.add_argument(
        "--file",
        required=True,
        help="Pfad zur BPMN-Datei",
    )
    parser.add_argument(
        "--client-id",
        required=True,
        help="Camunda OAuth Client ID",
    )
    parser.add_argument(
        "--client-secret",
        required=True,
        help="Camunda OAuth Client Secret",
    )
    parser.add_argument(
        "--cluster-id",
        required=True,
        help="Camunda Cluster ID",
    )
    parser.add_argument(
        "--region",
        default="bru-2",
        help="Camunda Cloud Region (Standard: bru-2)",
    )

    args = parser.parse_args()

    # Prüfen ob die Datei existiert
    if not os.path.isfile(args.file):
        print(f"❌ Datei nicht gefunden: {args.file}")
        sys.exit(1)

    # Access-Token holen
    token = get_access_token(args.client_id, args.client_secret)

    # BPMN deployen
    deploy_bpmn(args.file, token, args.cluster_id, args.region)


if __name__ == "__main__":
    main()
