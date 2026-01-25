#!/bin/bash
curl -sfL https://get.k3s.io | \
  INSTALL_K3S_SKIP_SELINUX_RPM=true \
  K3S_URL=https://${master_ip}:6443 \
  K3S_TOKEN=${token} sh -
