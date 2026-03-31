#!/usr/bin/env bash
# ============================================================
# validate_bpmn.sh
# Validiert alle BPMN-Dateien im Repository auf XML-Korrektheit
# und prüft grundlegende BPMN 2.0 Struktur.
# ============================================================

set -euo pipefail

PROCESS_DIR="processes"
EXIT_CODE=0
COUNT=0
ERRORS=0

echo "========================================"
echo " BPMN Validierung"
echo "========================================"
echo ""

# Alle .bpmn Dateien finden
BPMN_FILES=$(find "$PROCESS_DIR" -name "*.bpmn" -type f 2>/dev/null || true)

if [ -z "$BPMN_FILES" ]; then
  echo "⚠️  Keine BPMN-Dateien in '$PROCESS_DIR/' gefunden."
  exit 0
fi

for file in $BPMN_FILES; do
  COUNT=$((COUNT + 1))
  echo "📄 Prüfe: $file"

  # 1. XML Wohlgeformtheit prüfen (mit Python, da plattformunabhängig)
  if ! python3 -c "
import xml.etree.ElementTree as ET
import sys
try:
    ET.parse('$file')
    sys.exit(0)
except ET.ParseError as e:
    print(f'  ❌ XML-Fehler: {e}')
    sys.exit(1)
" 2>&1; then
    ERRORS=$((ERRORS + 1))
    EXIT_CODE=1
    continue
  fi

  # 2. BPMN-Namespace prüfen
  if ! grep -q "http://www.omg.org/spec/BPMN/20100524/MODEL" "$file"; then
    echo "  ❌ Fehlender BPMN 2.0 Namespace"
    ERRORS=$((ERRORS + 1))
    EXIT_CODE=1
    continue
  fi

  # 3. Mindestens ein Prozess-Element vorhanden
  if ! grep -q "<bpmn:process\|<bpmn2:process\|<process " "$file"; then
    echo "  ❌ Kein <process>-Element gefunden"
    ERRORS=$((ERRORS + 1))
    EXIT_CODE=1
    continue
  fi

  echo "  ✅ Gültig"
done

echo ""
echo "========================================"
echo " Ergebnis: $COUNT Dateien geprüft, $ERRORS Fehler"
echo "========================================"

exit $EXIT_CODE
