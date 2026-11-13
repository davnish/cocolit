#!/bin/bash
# Deploy monitoring over SSH (helm runs on the nodes; no API port is opened).
#
#   scripts/deploy_monitoring.sh server   Grafana, Prometheus, Loki, Tempo on the monitoring node
#   scripts/deploy_monitoring.sh agent    Alloy collectors on the app node, sending to the monitoring node
#
# Nodes come from `tofu -chdir=infra/oci output` (MON_NODE=mon, APP_NODE=x86 by default).
# Grafana admin password (generated on first run, never printed):
#   ssh ubuntu@<mon ip> sudo k3s kubectl -n monitoring get secret grafana-admin -o jsonpath='{.data.admin-password}' | base64 -d
set -euo pipefail
cd "$(dirname "$0")/.."

TARGET="${1:?usage: $0 server|agent}"
MON_NODE="${MON_NODE:-mon}"
APP_NODE="${APP_NODE:-x86}"
HELM_VERSION=v3.19.0
KPS_VERSION=93.3.0
LOKI_VERSION=7.6.0
TEMPO_VERSION=1.24.4
K8S_MONITORING_VERSION=4.6.0

ip() { tofu -chdir=infra/oci output -json "$1" | python3 -c "import sys, json; print(json.load(sys.stdin)['$2'])"; }
KUBE="sudo KUBECONFIG=/etc/rancher/k3s/k3s.yaml"

# Remote snippet: download a chart once into ~/charts, retrying, because
# chart downloads from GitHub time out now and then.
pull() { # $1 = repo/chart, $2 = version
  local f="\$HOME/charts/${1##*/}-$2.tgz"
  echo "mkdir -p ~/charts; sudo test -f $f || for i in 1 2 3 4 5; do $KUBE helm pull $1 --version $2 -d ~/charts && break; sleep 5; done; sudo test -f $f"
}

prepare() { # $1 = public ip: helm, chart repos, namespace, config files
  ssh -o BatchMode=yes "ubuntu@$1" "set -e
    if ! command -v helm >/dev/null; then
      arch=\$(dpkg --print-architecture)
      curl -fsSL https://get.helm.sh/helm-$HELM_VERSION-linux-\$arch.tar.gz |
        sudo tar -xz -C /usr/local/bin --strip-components=1 linux-\$arch/helm
    fi
    $KUBE helm repo add prometheus-community https://prometheus-community.github.io/helm-charts >/dev/null 2>&1 || true
    $KUBE helm repo add grafana https://grafana.github.io/helm-charts >/dev/null 2>&1 || true
    $KUBE helm repo update >/dev/null
    $KUBE kubectl create namespace monitoring --dry-run=client -o yaml | $KUBE kubectl apply -f - >/dev/null"
  rsync -a --delete infra/monitoring/ "ubuntu@$1:cocolit-monitoring/"
}

case "$TARGET" in
  server)
    IP=$(ip public_ip "$MON_NODE")
    echo "monitoring server on $MON_NODE ($IP)"
    prepare "$IP"
    ssh -o BatchMode=yes "ubuntu@$IP" "set -e
      K='$KUBE kubectl -n monitoring'; H='$KUBE helm -n monitoring'
      \$K get secret grafana-admin >/dev/null 2>&1 ||
        \$K create secret generic grafana-admin --from-literal=admin-user=admin \
          --from-literal=admin-password=\"\$(openssl rand -base64 24)\" >/dev/null
      $(pull prometheus-community/kube-prometheus-stack $KPS_VERSION)
      $(pull grafana/loki $LOKI_VERSION)
      $(pull grafana/tempo $TEMPO_VERSION)
      \$H upgrade --install kps ~/charts/kube-prometheus-stack-$KPS_VERSION.tgz \
        -f ~/cocolit-monitoring/kube-prometheus-stack.yaml --wait --timeout 10m
      \$H upgrade --install loki ~/charts/loki-$LOKI_VERSION.tgz -f ~/cocolit-monitoring/loki.yaml --wait --timeout 10m
      \$H upgrade --install tempo ~/charts/tempo-$TEMPO_VERSION.tgz -f ~/cocolit-monitoring/tempo.yaml --wait --timeout 10m
      \$K apply -f ~/cocolit-monitoring/nodeports.yaml
      if [ -d ~/cocolit-monitoring/dashboards ]; then
        \$K create configmap cocolit-dashboards --from-file ~/cocolit-monitoring/dashboards \
          --dry-run=client -o yaml | \$K label --local -f - grafana_dashboard=1 -o yaml | \$K apply --server-side -f -
      fi
      [ ! -f ~/cocolit-monitoring/rules.yaml ] || \$K apply -f ~/cocolit-monitoring/rules.yaml
      if \$K get secret cloudflared-token >/dev/null 2>&1; then
        \$K apply -f ~/cocolit-monitoring/cloudflared.yaml
      else
        echo 'no cloudflared-token secret yet: Grafana is reachable only by SSH port-forward'
      fi
      \$K get pods"
    ;;
  agent)
    IP=$(ip public_ip "$APP_NODE")
    MON_PRIVATE=$(ip private_ip "$MON_NODE")
    echo "collectors on $APP_NODE ($IP) -> $MON_PRIVATE"
    prepare "$IP"
    ssh -o BatchMode=yes "ubuntu@$IP" "set -e
      $(pull grafana/k8s-monitoring $K8S_MONITORING_VERSION)
      sed 's/MON_HOST/$MON_PRIVATE/g' ~/cocolit-monitoring/agent.yaml |
        $KUBE helm -n monitoring upgrade --install agent ~/charts/k8s-monitoring-$K8S_MONITORING_VERSION.tgz \
          -f - --wait --timeout 10m
      $KUBE kubectl -n monitoring get pods"
    ;;
  *)
    echo "usage: $0 server|agent" >&2; exit 1 ;;
esac
