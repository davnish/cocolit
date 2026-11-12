output "public_ip" {
  value = { for k, n in oci_core_instance.node : k => n.public_ip }
}

output "ssh" {
  value = { for k, n in oci_core_instance.node : k => "ssh ubuntu@${n.public_ip}" }
}

output "kubeconfig_command" {
  description = "Copy the kubeconfig, then reach the API through an SSH tunnel (6443 is not open)"
  value = { for k, n in oci_core_instance.node : k =>
    "ssh ubuntu@${n.public_ip} sudo cat /etc/rancher/k3s/k3s.yaml > ~/.kube/cocolit-${k}.yaml && ssh -fN -L 6443:127.0.0.1:6443 ubuntu@${n.public_ip}"
  }
}

output "image" {
  value = { for k, d in data.oci_core_images.ubuntu : k => d.images[0].display_name }
}
