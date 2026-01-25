data "aws_availability_zones" "available" {
  state = "available"
}

data "aws_ami" "amazon_linux" {
  most_recent = true
  owners      = ["amazon"]

  filter {
    name   = "name"
    values = ["amzn2-ami-hvm-*-x86_64-gp2"]
  }
}

resource "aws_vpc" "vpc" {
  cidr_block = "10.0.0.0/16"

  tags = {
    Name = "cocolit-vpc"
  }
}

resource "aws_internet_gateway" "igw" {
  vpc_id = aws_vpc.vpc.id
  tags = {
    Name = "cocolit-igw"
  }
}

resource "aws_route_table" "public" {
  vpc_id = aws_vpc.vpc.id

  route {
    cidr_block = "0.0.0.0/0"
    gateway_id = aws_internet_gateway.igw.id
  }
  tags = {
    Name = "cocolit-routetable"
  }
}

resource "aws_eip" "control_plane_eip" {
  domain = "vpc"
  tags = {
    Name = "cocolit-eip"
  }
}

resource "aws_security_group" "sg" {
  name        = "k3s-sg"
  description = "Security group for k3s cluster"
  vpc_id      = aws_vpc.vpc.id

  # SSH
  ingress {
    description = "SSH access"
    from_port   = 22
    to_port     = 22
    protocol    = "tcp"
    cidr_blocks = ["0.0.0.0/0"]
  }

  # workers to node
  ingress {
  description = "Kusudobernetes API"
  from_port   = 6443
  to_port     = 6443
  protocol    = "tcp"
  self        = true
}

  # Kubelet
  ingress {
    description     = "Kubelet"
    from_port       = 10250
    to_port         = 10250
    protocol        = "tcp"
    self            = true
  }

  # Flannel VXLAN
  ingress {
    description     = "Flannel VXLAN"
    from_port       = 8472
    to_port         = 8472
    protocol        = "udp"
    self            = true
  }

  # Allow all egress
  egress {
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }
  tags = {
    Name = "cocolit-sg"
  }
}

resource "aws_subnet" "cocolit_subnet_public"  {
  vpc_id                  = aws_vpc.vpc.id
  cidr_block              = "10.0.1.0/24"
  availability_zone = data.aws_availability_zones.available.names[0]
  map_public_ip_on_launch = true
  tags = {
    Name = "cocolit-public-subnet"
  }
}

resource "aws_instance" "control_plane" {
  key_name = "cocolit-root"
  ami = data.aws_ami.amazon_linux.id
  vpc_security_group_ids = [aws_security_group.sg.id]
  subnet_id = aws_subnet.cocolit_subnet_public.id
  instance_type = "t3.small"

  user_data = <<-EOF
#!/bin/bash
curl -sfL https://get.k3s.io | \
  INSTALL_K3S_SKIP_SELINUX_RPM=true sh -
EOF

  root_block_device {
    volume_size = 60
    volume_type = "gp3"
  }
  tags = {
    Name = "cocolit-control-plane"
  }
}

resource "aws_route_table_association" "public_subnet_assoc" {
  subnet_id      = aws_subnet.cocolit_subnet_public.id
  route_table_id = aws_route_table.public.id
}


resource "aws_eip_association" "control_plane_eip_assoc" {
  instance_id   = aws_instance.control_plane.id
  allocation_id = aws_eip.control_plane_eip.id
}

resource "null_resource" "fetch_k3s_token" {
  depends_on = [aws_instance.control_plane, aws_eip_association.control_plane_eip_assoc]

  connection {
    type        = "ssh"
    user        = "ec2-user"
    host        = aws_eip.control_plane_eip.public_ip
    private_key = file(var.ssh_private_key_path)
  }

  provisioner "remote-exec" {
    inline = [
      "timeout 300 bash -c 'sudo until [ -f /var/lib/rancher/k3s/server/node-token ]; do sleep 5; done'",
      "sudo cat /var/lib/rancher/k3s/server/node-token > /tmp/k3s_token"
    ]
  }
}


data "external" "k3s_token" {
  depends_on = [null_resource.fetch_k3s_token]

  program = [
    "bash",
    "-c",
    "ssh -i ${var.ssh_private_key_path} ec2-user@${aws_eip.control_plane_eip.public_ip} 'cat /tmp/k3s_token' 2>/dev/null | awk '{print \"{\\\"token\\\":\\\"\" $0 \"\\\"}\"}'"
  ]
}

resource "aws_instance" "worker" {
  count = 2

  key_name               = "cocolit-root"
  ami                    = data.aws_ami.amazon_linux.id
  instance_type          = "t3.micro"
  subnet_id              = aws_subnet.cocolit_subnet_public.id
  vpc_security_group_ids = [aws_security_group.sg.id]

  user_data = templatefile("${path.module}/worker-init.sh", {
    master_ip = aws_instance.control_plane.private_ip
    token     = data.external.k3s_token.result.token
  })

  tags = {
    Name = "cocolit-worker-${count.index}"
  }
}