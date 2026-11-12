#!/bin/bash
# Build the images and deploy cocolit to the laptop k3s cluster (Colima).
#
# One-time setup:
#   colima start --cpu 4 --memory 4 --disk 40 --kubernetes
#   kubectl apply --server-side -f https://github.com/cloudnative-pg/cloudnative-pg/releases/download/v1.30.1/cnpg-1.30.1.yaml
#   create infra/charts/cocolit/secrets-laptop.yaml (gitignored; see docs/deploy-laptop.md)
#
# Usage: scripts/deploy_laptop.sh [extra helm args, e.g. --set cloudflared.enabled=true]
set -euo pipefail
cd "$(dirname "$0")/.."

CHART=infra/charts/cocolit
[ -f "$CHART/secrets-laptop.yaml" ] || { echo "missing $CHART/secrets-laptop.yaml" >&2; exit 1; }
[ "$(kubectl config current-context)" = colima ] || { echo "kubectl context is not 'colima'" >&2; exit 1; }

# Colima's k3s uses the same Docker daemon, so local images need no registry.
docker build -f inference.Dockerfile -t cocolit/inference:dev .
docker build -f frontend.Dockerfile -t cocolit/frontend:dev --build-arg ASSET_VERSION="$(date +%s)" .

if command -v helm >/dev/null; then
  HELM=(helm)
else
  # No local helm: run it in a container on the Colima VM. Only $HOME is shared
  # into the VM, so the kubeconfig copy lives under ~/.kube.
  kubectl config view --minify --raw > "$HOME/.kube/colima-vm.yaml"
  chmod 600 "$HOME/.kube/colima-vm.yaml"
  HELM=(docker run --rm --network host
        -v "$HOME/.kube/colima-vm.yaml:/root/.kube/config:ro"
        -v "$PWD:/work" -w /work alpine/helm:3.19.0)
fi

"${HELM[@]}" upgrade --install cocolit "$CHART" -n apps --create-namespace \
  -f "$CHART/values-laptop.yaml" -f "$CHART/secrets-laptop.yaml" "$@"

# Tags stay ":dev", so restart to pick up the freshly built images.
kubectl -n apps rollout restart deploy/cocolit-inference-server deploy/cocolit-streamlit-deployment
kubectl -n apps rollout status deploy/cocolit-inference-server --timeout=180s
kubectl -n apps rollout status deploy/cocolit-streamlit-deployment --timeout=180s
kubectl -n apps get pods
