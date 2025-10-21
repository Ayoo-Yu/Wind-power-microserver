# Consul server configuration
datacenter = "dc1"
data_dir = "/consul/data"
client_addr = "0.0.0.0"
ui_config = {
  enabled = true
}

# Server configuration
server = true
bootstrap_expect = 1
advertise_addr = "{{ GetInterfaceIP `eth0` }}"

# Enable service mesh
connect = {
  enabled = true
}

# Enable ACL (Access Control Lists)
acl = {
  enabled = true
  default_policy = "allow"
  enable_token_persistence = true
}

# Logging
log_level = "INFO"
enable_syslog = false

# Performance
telemetry {
  prometheus_retention_time = "30s"
  disable_hostname = true
  enable_service_metric = true
}

# DNS configuration
enable_update_check = false
recursor = "8.8.8.8"