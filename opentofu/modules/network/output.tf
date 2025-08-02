# Copyright (c) 2024, 2025, Oracle and/or its affiliates.
# All rights reserved. The Universal Permissive License (UPL), Version 1.0 as shown at http://oss.oracle.com/licenses/upl
# spell-checker: disable

// VCN
output "vcn_ocid" {
  description = "VCN Identifier."
  value       = oci_core_vcn.vcn.id
}

// Private Subnet
output "private_subnet_ocid" {
  description = "Private Subnet Identifier."
  value       = try(oci_core_subnet.private.id, null)
}

// Public Subnet
output "public_subnet_ocid" {
  description = "Public Subnet Identifier."
  value       = oci_core_subnet.public.id
}