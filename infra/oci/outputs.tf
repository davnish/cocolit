output "public_ip" {
  value = oci_core_instance.node.public_ip
}

output "ssh" {
  value = "ssh ubuntu@${oci_core_instance.node.public_ip}"
}

output "kubeconfig_command" {
  description = "Copy the kubeconfig, then reach the API through an SSH tunnel (6443 is not open)"
  value       = "ssh ubuntu@${oci_core_instance.node.public_ip} sudo cat /etc/rancher/k3s/k3s.yaml > ~/.kube/cocolit.yaml && ssh -fN -L 6443:127.0.0.1:6443 ubuntu@${oci_core_instance.node.public_ip}"
}

output "image" {
  value = data.oci_core_images.ubuntu.images[0].display_name
}
