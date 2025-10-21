# Consul client configuration
datacenter = "dc1"
data_dir = "/consul/data"
client_addr = "0.0.0.0"

# Join the server
retry_join = ["consul-server"]

# Enable service mesh
connect = {
  enabled = true
}

# Logging
log_level = "INFO"

# Performance
telemetry {
  prometheus_retention_time = "30s"
  disable_hostname = true
  enable_service_metric = true
}