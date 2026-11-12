locals {
  name = "cocolit"
  tags = { project = "cocolit", managed-by = "opentofu" }
}

resource "oci_identity_compartment" "cocolit" {
  compartment_id = var.tenancy_ocid
  name           = local.name
  description    = "cocolit app: k3s node, network, storage"
  enable_delete  = true
  freeform_tags  = local.tags
}

data "oci_identity_availability_domains" "ads" {
  compartment_id = var.tenancy_ocid
}

# Latest Ubuntu 24.04 LTS image for Ampere (aarch64).
data "oci_core_images" "ubuntu" {
  compartment_id           = var.tenancy_ocid
  operating_system         = "Canonical Ubuntu"
  operating_system_version = "24.04"
  shape                    = "VM.Standard.A1.Flex"
  sort_by                  = "TIMECREATED"
  sort_order               = "DESC"
}

# ---------------------------------------------------------------------------
# Network: one public subnet. Only SSH from your IP is allowed in; web traffic
# arrives through the Cloudflare Tunnel, which connects outbound.
# ---------------------------------------------------------------------------

resource "oci_core_vcn" "main" {
  compartment_id = oci_identity_compartment.cocolit.id
  cidr_blocks    = ["10.0.0.0/16"]
  display_name   = "${local.name}-vcn"
  dns_label      = local.name
  freeform_tags  = local.tags
}

resource "oci_core_internet_gateway" "main" {
  compartment_id = oci_identity_compartment.cocolit.id
  vcn_id         = oci_core_vcn.main.id
  display_name   = "${local.name}-igw"
  freeform_tags  = local.tags
}

resource "oci_core_route_table" "public" {
  compartment_id = oci_identity_compartment.cocolit.id
  vcn_id         = oci_core_vcn.main.id
  display_name   = "${local.name}-public-rt"
  freeform_tags  = local.tags

  route_rules {
    destination       = "0.0.0.0/0"
    destination_type  = "CIDR_BLOCK"
    network_entity_id = oci_core_internet_gateway.main.id
  }
}

resource "oci_core_security_list" "node" {
  compartment_id = oci_identity_compartment.cocolit.id
  vcn_id         = oci_core_vcn.main.id
  display_name   = "${local.name}-node-sl"
  freeform_tags  = local.tags

  egress_security_rules {
    destination = "0.0.0.0/0"
    protocol    = "all"
  }

  ingress_security_rules {
    description = "SSH from the admin IP only"
    source      = var.ssh_allowed_cidr
    protocol    = "6" # TCP
    tcp_options {
      min = 22
      max = 22
    }
  }

  ingress_security_rules {
    description = "Path MTU discovery"
    source      = "0.0.0.0/0"
    protocol    = "1" # ICMP
    icmp_options {
      type = 3
      code = 4
    }
  }

  ingress_security_rules {
    description = "ICMP inside the VCN"
    source      = "10.0.0.0/16"
    protocol    = "1"
    icmp_options {
      type = 3
    }
  }
}

resource "oci_core_subnet" "public" {
  compartment_id    = oci_identity_compartment.cocolit.id
  vcn_id            = oci_core_vcn.main.id
  cidr_block        = "10.0.1.0/24"
  display_name      = "${local.name}-public"
  dns_label         = "public"
  route_table_id    = oci_core_route_table.public.id
  security_list_ids = [oci_core_security_list.node.id]
  freeform_tags     = local.tags
}

# ---------------------------------------------------------------------------
# Compute: single A1 node running k3s.
# ---------------------------------------------------------------------------

resource "oci_core_instance" "node" {
  compartment_id      = oci_identity_compartment.cocolit.id
  availability_domain = data.oci_identity_availability_domains.ads.availability_domains[0].name
  display_name        = "${local.name}-node"
  shape               = "VM.Standard.A1.Flex"
  freeform_tags       = local.tags

  shape_config {
    ocpus         = var.ocpus
    memory_in_gbs = var.memory_gb
  }

  source_details {
    source_type             = "image"
    source_id               = data.oci_core_images.ubuntu.images[0].id
    boot_volume_size_in_gbs = var.boot_volume_gb
  }

  create_vnic_details {
    subnet_id        = oci_core_subnet.public.id
    assign_public_ip = true # needed for outbound internet via the internet gateway
    hostname_label   = "node"
  }

  metadata = {
    ssh_authorized_keys = trimspace(file(pathexpand(var.ssh_public_key_path)))
    user_data = base64encode(templatefile("${path.module}/cloud-init.yaml", {
      k3s_channel = var.k3s_channel
      k3s_version = var.k3s_version
    }))
  }

  instance_options {
    are_legacy_imds_endpoints_disabled = true
  }

  availability_config {
    recovery_action = "RESTORE_INSTANCE"
  }

  lifecycle {
    # A newer Ubuntu image or edited cloud-init must not recreate the node.
    ignore_changes = [source_details[0].source_id, metadata["user_data"]]
  }
}

# Separate volume so the database survives replacing the node.
resource "oci_core_volume" "data" {
  compartment_id      = oci_identity_compartment.cocolit.id
  availability_domain = oci_core_instance.node.availability_domain
  display_name        = "${local.name}-data"
  size_in_gbs         = var.data_volume_gb
  freeform_tags       = local.tags

  lifecycle {
    prevent_destroy = true
  }
}

resource "oci_core_volume_attachment" "data" {
  attachment_type = "paravirtualized"
  instance_id     = oci_core_instance.node.id
  volume_id       = oci_core_volume.data.id
  device          = "/dev/oracleoci/oraclevdb"
}
