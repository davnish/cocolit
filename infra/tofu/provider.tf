terraform {
  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.0"
    }
  }
}

provider "aws" {
  profile = "cocolit-dev"
  region = "ap-south-1"

  default_tags {
    tags = {
      project = "cocolit"
      org     = "prithvilabs"
      owner   = "nischal"
    }
  }
}
