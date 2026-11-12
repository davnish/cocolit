#!/bin/bash
# Deploy the inference image to Cloud Run as scale-to-zero overflow, then point
# the cluster's frontend at it.
#
# Needs: gcloud (logged in), a GCP project with billing + a budget alert.
# Usage: PROJECT=my-project scripts/deploy_cloud_run.sh
#   REGION (default asia-south1), SERVICE (default cocolit-inference)
#
# Cost guard rails: min-instances 0, max-instances 2, concurrency 1, 1 vCPU/1 GiB.
# Each request runs alone on its instance, like on the local node; requests beyond
# 2 concurrent overflow requests get 429 and the frontend reports an error.
set -euo pipefail
cd "$(dirname "$0")/.."

: "${PROJECT:?set PROJECT to your GCP project id}"
REGION="${REGION:-asia-south1}"
SERVICE="${SERVICE:-cocolit-inference}"
REPO=cocolit
IMAGE="$REGION-docker.pkg.dev/$PROJECT/$REPO/inference:$(git rev-parse --short HEAD)$(git diff --quiet || echo -dirty)"

gcloud config set project "$PROJECT" >/dev/null
gcloud services enable run.googleapis.com artifactregistry.googleapis.com cloudbuild.googleapis.com

gcloud artifacts repositories describe "$REPO" --location "$REGION" >/dev/null 2>&1 ||
  gcloud artifacts repositories create "$REPO" --location "$REGION" --repository-format docker \
    --description "cocolit images"
# Keep storage inside the 0.5 GB free tier: only the newest 2 images.
cat > /tmp/cocolit-ar-cleanup.json <<'EOF'
[{"name": "keep-2", "action": {"type": "Keep"}, "mostRecentVersions": {"keepCount": 2}},
 {"name": "delete-rest", "action": {"type": "Delete"}, "condition": {"tagState": "ANY"}}]
EOF
gcloud artifacts repositories set-cleanup-policies "$REPO" --location "$REGION" \
  --policy /tmp/cocolit-ar-cleanup.json --no-dry-run >/dev/null

# Cloud Build builds linux/amd64 (what Cloud Run runs); free tier covers this.
cat > /tmp/cocolit-cloudbuild.yaml <<EOF
steps:
- name: gcr.io/cloud-builders/docker
  args: [build, -f, inference.Dockerfile, -t, "$IMAGE", .]
images: ["$IMAGE"]
EOF
gcloud builds submit --region "$REGION" --config /tmp/cocolit-cloudbuild.yaml .

# Shared secret between the frontend and Cloud Run (the service URL is public).
API_KEY="$(kubectl -n apps get secret inference-overflow -o jsonpath='{.data.apiKey}' 2>/dev/null | base64 -d || true)"
API_KEY="${API_KEY:-$(LC_ALL=C tr -dc 'A-Za-z0-9' </dev/urandom | head -c 40)}"

gcloud run deploy "$SERVICE" --image "$IMAGE" --region "$REGION" \
  --allow-unauthenticated \
  --cpu 1 --memory 1Gi --concurrency 1 \
  --min-instances 0 --max-instances 2 \
  --timeout 120 --cpu-boost \
  --set-env-vars "INFERENCE_API_KEY=$API_KEY,ORT_THREADS=1"

URL="$(gcloud run services describe "$SERVICE" --region "$REGION" --format 'value(status.url)')/predict"

kubectl -n apps create secret generic inference-overflow \
  --from-literal=url="$URL" --from-literal=apiKey="$API_KEY" \
  --dry-run=client -o yaml | kubectl apply -f -

echo
echo "Cloud Run: $URL"
echo "Now enable overflow: scripts/deploy_laptop.sh --set overflow.enabled=true"
