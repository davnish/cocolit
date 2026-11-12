#!/bin/bash
# Deploy cocolit to an Oracle Cloud k3s node (infra/oci) over SSH.
# The k3s API port is not open, so helm runs on the node itself; secrets are
# streamed over SSH on stdin and never written to the node's disk.
#
# One-time setup:
#   tofu -chdir=infra/oci apply                  (creates the node)
#   create infra/charts/cocolit/secrets-oci.yaml (gitignored; same keys as secrets-laptop.yaml)
#   the cloudflared-token secret in namespace apps (see values-oci.yaml)
#
# Usage: NODE=x86|a1 scripts/deploy_oci.sh [extra helm args, e.g. --set cloudflared.enabled=false]
set -euo pipefail
cd "$(dirname "$0")/.."

NODE="${NODE:-x86}"
CHART=infra/charts/cocolit
SECRETS="$CHART/secrets-oci.yaml"
HELM_VERSION=v3.19.0
CNPG_MANIFEST=https://github.com/cloudnative-pg/cloudnative-pg/releases/download/v1.30.1/cnpg-1.30.1.yaml

[ -f "$SECRETS" ] || { echo "missing $SECRETS" >&2; exit 1; }
IP=$(tofu -chdir=infra/oci output -json public_ip |
     python3 -c "import sys, json; print(json.load(sys.stdin)['$NODE'])")
SSH=(ssh -o BatchMode=yes "ubuntu@$IP")
KUBE="sudo KUBECONFIG=/etc/rancher/k3s/k3s.yaml"
echo "deploying to $NODE ($IP)"

# Helm and the CloudNativePG operator (idempotent).
"${SSH[@]}" "set -e
  if ! command -v helm >/dev/null; then
    arch=\$(dpkg --print-architecture)
    curl -fsSL https://get.helm.sh/helm-$HELM_VERSION-linux-\$arch.tar.gz |
      sudo tar -xz -C /usr/local/bin --strip-components=1 linux-\$arch/helm
  fi
  $KUBE kubectl apply --server-side -f $CNPG_MANIFEST >/dev/null
  $KUBE kubectl -n cnpg-system rollout status deploy/cnpg-controller-manager --timeout=180s"

rsync -a --delete --exclude 'secrets-*.yaml' "$CHART/" "ubuntu@$IP:cocolit-chart/"

"${SSH[@]}" "$KUBE helm upgrade --install cocolit ~/cocolit-chart -n apps --create-namespace \
  -f ~/cocolit-chart/values-oci.yaml -f - $*" < "$SECRETS"

"${SSH[@]}" "$KUBE kubectl -n apps rollout status deploy/cocolit-inference-server --timeout=300s &&
  $KUBE kubectl -n apps rollout status deploy/cocolit-streamlit-deployment --timeout=300s &&
  $KUBE kubectl -n apps get pods"
