#!/usr/bin/env bash
set -euo pipefail

PROJECT_ID="${GOOGLE_CLOUD_PROJECT:-aecom-demo-uc1}"
REGION="${GOOGLE_CLOUD_LOCATION:-us-central1}"
SERVICE_NAME="${SERVICE_NAME:-ask-gbs-agent}"

echo "==> Deploying Ask GBS ADK Agent to Google Cloud Run in project ${PROJECT_ID} (${REGION})..."

adk deploy cloud_run \
  --project="${PROJECT_ID}" \
  --region="${REGION}" \
  --service_name="${SERVICE_NAME}" \
  --with_ui \
  ask_gbs_agent

echo "==> Updating Cloud Run service ${SERVICE_NAME} to min-instances=1 for zero-cold-start demos..."
gcloud run services update "${SERVICE_NAME}" \
  --project="${PROJECT_ID}" \
  --region="${REGION}" \
  --min-instances=1 \
  --set-env-vars="GOOGLE_CLOUD_PROJECT=${PROJECT_ID},GOOGLE_CLOUD_LOCATION=${REGION},GOOGLE_GENAI_USE_VERTEXAI=TRUE,ENABLE_CLOUD_LOGGING=true,ENABLE_CLOUD_TRACE=true,ENABLE_SECRET_MANAGER=true"

SERVICE_URL="$(gcloud run services describe "${SERVICE_NAME}" --project="${PROJECT_ID}" --region="${REGION}" --format='value(status.url)')"
echo "==> Deployed Service URL: ${SERVICE_URL}"

echo "==> Pre-warming /warm endpoint..."
curl -fsS -X POST "${SERVICE_URL}/warm" || true
echo ""
echo "==> Deployment complete!"
