variable "tenancy_ocid" {
  description = "Tenancy OCID (root compartment); the cocolit compartment is created under it"
  type        = string
}

variable "region" {
  description = "Home region; Always Free compute must live here"
  type        = string
  default     = "ap-hyderabad-1"
}

variable "oci_profile" {
  description = "Profile in ~/.oci/config"
  type        = string
  default     = "DEFAULT"
}

variable "ssh_public_key_path" {
  description = "Public key installed for the ubuntu user"
  type        = string
  default     = "~/.ssh/id_ed25519.pub"
}

variable "ssh_allowed_cidr" {
  description = "Only this CIDR may SSH in, e.g. \"203.0.113.7/32\" (curl -s https://checkip.amazonaws.com)"
  type        = string

  validation {
    condition     = can(cidrhost(var.ssh_allowed_cidr, 0)) && var.ssh_allowed_cidr != "0.0.0.0/0"
    error_message = "Use a specific CIDR such as your IP with /32, not 0.0.0.0/0."
  }
}

# Always Free A1 allowance is 2 OCPU / 12 GB in total.
variable "ocpus" {
  type    = number
  default = 2
}

variable "memory_gb" {
  type    = number
  default = 12
}

# Always Free block storage is 200 GB total, boot volumes included.
variable "boot_volume_gb" {
  type    = number
  default = 50
}

variable "data_volume_gb" {
  description = "Volume mounted at /var/lib/rancher/k3s/storage (k3s local-path PVCs, i.e. PostGIS data)"
  type        = number
  default     = 100
}

variable "k3s_channel" {
  description = "k3s release channel used when k3s_version is empty"
  type        = string
  default     = "stable"
}

variable "k3s_version" {
  description = "Pin an exact k3s version (e.g. from `k3s --version` after first boot); empty = channel"
  type        = string
  default     = ""
}
