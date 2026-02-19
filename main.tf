terraform {
  required_version = ">= 1.5.0"

  required_providers {
    openstack = {
      source  = "terraform-provider-openstack/openstack"
      version = ">= 1.54.0"
    }
  }
}

provider "openstack" {

}

variable "vm_name" {
  type    = string
  default = "ia_bakastov_terr"
}

variable "image_name" {
  type    = string
  default = "ununtu-22.04"
}

variable "flavor_name" {
  type    = string
  default = "m1.small"
}

variable "network_name" {
  type    = string
  default = "sutdents-net"
}

variable "keypair_name" {
  type    = string
  default = "ia_bakastov_deploy"
}

variable "secgroup_name" {
  type    = string
  default = "students-general"
}


# Можно оставить только 22, а порты приложения открывать не обязательно,
# если не требуют доступ снаружи. Но часто проверяют, что сервис слушает.


data "openstack_images_image_v2" "img" {
  name        = var.image_name
  most_recent = true
}

data "openstack_networking_network_v2" "net" {
  name = var.network_name
}

resource "openstack_compute_instance_v2" "vm" {
  name            = var.vm_name
  image_id        = data.openstack_images_image_v2.img.id
  flavor_name     = var.flavor_name
  key_pair        = var.keypair_name
  security_groups = [var.secgroup_name]

  network {
    uuid = data.openstack_networking_network_v2.net.id
  }
}

# Если IP назначается сразу на интерфейс — хватит так:
output "vm_ip" {
  value = openstack_compute_instance_v2.vm.access_ip_v4 != "" ? openstack_compute_instance_v2.vm.access_ip_v4 : openstack_compute_instance_v2.vm.network[0].fixed_ip_v4
}
