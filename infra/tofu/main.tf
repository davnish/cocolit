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
    Name = "cocolit-public-sg"
  }
}

resource "aws_instance" "control_plane" {
  key_name = "cocolit-root"
  ami = data.aws_ami.amazon_linux.id
  vpc_security_group_ids = [aws_security_group.sg.id]
  subnet_id = aws_subnet.cocolit_subnet_public.id
  instance_type = "t3.micro"

  root_block_device {
    volume_size = 20
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