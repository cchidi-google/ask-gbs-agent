#!/usr/bin/env bash
set -euo pipefail

PROJECT_ID="${GOOGLE_CLOUD_PROJECT:-aecom-demo-uc1}"
GE_LOCATION="${GEMINI_ENTERPRISE_LOCATION:-global}"
GE_APP_ID="${GEMINI_ENTERPRISE_APP_ID:-ask-gbs-enterprise-app}"
AGENT_ENDPOINT_URI="${AGENT_ENDPOINT_URI:-}"

if [[ -z "${AGENT_ENDPOINT_URI}" ]]; then
  echo "Usage: AGENT_ENDPOINT_URI=https://ask-gbs-agent-...a.run.app ./register_gemini_enterprise.sh"
  exit 1
fi

ACCESS_TOKEN="$(gcloud auth print-access-token)"
API_BASE="https://discoveryengine.googleapis.com/v1alpha"
PARENT="projects/${PROJECT_ID}/locations/${GE_LOCATION}/collections/default_collection/engines/${GE_APP_ID}/assistants/default_assistant"

echo "==> Registering Ask GBS Agent in Gemini Enterprise (${PARENT})..."

curl -fsS -X POST "${API_BASE}/${PARENT}/agents" \
  -H "Authorization: Bearer ${ACCESS_TOKEN}" \
  -H "Content-Type: application/json" \
  -H "X-Goog-User-Project: ${PROJECT_ID}" \
  -d "{
    \"displayName\": \"Ask GBS — Enterprise Finance & Procurement Helpdesk\",
    \"description\": \"Multi-agent ADK assistant for Supplier Invoice Support, Payment Diagnostics, Coupa KB Guidance, and ServiceNow Case Creation with A2UI v0.9 Canvas.\",
    \"a2aAgentDefinition\": {
      \"jsonAgentCard\": \"{\\\"name\\\":\\\"ask_gbs_orchestrator\\\",\\\"url\\\":\\\"${AGENT_ENDPOINT_URI}\\\",\\\"version\\\":\\\"1.0.0\\\"}\"
    }
  }"

echo ""
echo "==> Registration request submitted to Gemini Enterprise!"
