output "public_ip" {
  value = aws_instance.control_plane.public_ip
}