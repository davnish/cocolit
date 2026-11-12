locals {
  name = "cocolit"
  tags = { project = "cocolit", managed-by = "opentofu" }

  # The A1 node is the long-term (Always Free) target. The x86 node is a bridge
  # paid from trial credits while A1 capacity is unavailable; it keeps the
  # database on its boot volume, so move data with pg_dump when switching.
  all_nodes = {
    a1 = {
      enabled     = var.a1_enabled
      shape       = "VM.Standard.A1.Flex"
      ocpus       = var.ocpus
      memory_gb   = var.memory_gb
      data_volume = true
    }
    x86 = {
      enabled     = var.x86_enabled
      shape       = var.x86_shape
      ocpus       = var.x86_ocpus
      memory_gb   = var.x86_memory_gb
      data_volume = false
    }
  }
  nodes = { for k, v in local.all_nodes : k => v if v.enabled }
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

# Latest Ubuntu 24.04 LTS image for each node's shape (aarch64 or x86_64).
data "oci_core_images" "ubuntu" {
  for_each                 = local.nodes
  compartment_id           = var.tenancy_ocid
  operating_system         = "Canonical Ubuntu"
  operating_system_version = "24.04"
  shape                    = each.value.shape
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
# Compute: one k3s node per enabled entry in local.nodes.
# ---------------------------------------------------------------------------

resource "oci_core_instance" "node" {
  for_each            = local.nodes
  compartment_id      = oci_identity_compartment.cocolit.id
  availability_domain = data.oci_identity_availability_domains.ads.availability_domains[0].name
  display_name        = "${local.name}-${each.key}"
  shape               = each.value.shape
  freeform_tags       = local.tags

  shape_config {
    ocpus         = each.value.ocpus
    memory_in_gbs = each.value.memory_gb
  }

  source_details {
    source_type             = "image"
    source_id               = data.oci_core_images.ubuntu[each.key].images[0].id
    boot_volume_size_in_gbs = var.boot_volume_gb
  }

  create_vnic_details {
    subnet_id        = oci_core_subnet.public.id
    assign_public_ip = true # needed for outbound internet via the internet gateway
    hostname_label   = each.key
  }

  metadata = {
    ssh_authorized_keys = trimspace(file(pathexpand(var.ssh_public_key_path)))
    user_data = base64encode(templatefile("${path.module}/cloud-init.yaml", {
      k3s_channel = var.k3s_channel
      k3s_version = var.k3s_version
      data_volume = each.value.data_volume
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

# Separate volume so the database survives replacing the A1 node.
resource "oci_core_volume" "data" {
  count               = var.a1_enabled ? 1 : 0
  compartment_id      = oci_identity_compartment.cocolit.id
  availability_domain = data.oci_identity_availability_domains.ads.availability_domains[0].name
  display_name        = "${local.name}-data"
  size_in_gbs         = var.data_volume_gb
  freeform_tags       = local.tags

  lifecycle {
    prevent_destroy = true
  }
}

resource "oci_core_volume_attachment" "data" {
  count           = var.a1_enabled ? 1 : 0
  attachment_type = "paravirtualized"
  instance_id     = oci_core_instance.node["a1"].id
  volume_id       = oci_core_volume.data[0].id
  device          = "/dev/oracleoci/oraclevdb"
}
