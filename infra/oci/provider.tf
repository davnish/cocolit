terraform {
  required_version = ">= 1.6"

  required_providers {
    oci = {
      source  = "oracle/oci"
      version = "~> 9.13"
    }
  }
}

# Credentials come from ~/.oci/config (set up with `oci setup config`).
provider "oci" {
  config_file_profile = var.oci_profile
  region              = var.region
}
