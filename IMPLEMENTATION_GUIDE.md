# Implementation Guide

## Overview

This solution provides a production-ready system for collecting optical telemetry from Junos devices and storing it in Prometheus for analytics.

## Architecture

```
Junos Device (NETCONF) → Ansible Playbook → Parser (XML→JSON) → Prometheus Pushgateway → Prometheus → Grafana
```

## Implementation Steps

### Phase 1: Setup and Testing (30 minutes)

#### 1.1 Install Prerequisites

```bash
# Python packages
pip install -r requirements.txt

# Ansible collection
ansible-galaxy collection install junipernetworks.junos
```

#### 1.2 Verify Parser Functionality

```bash
# Run test suite
cd parsers
python3 test_optics_diagnostics.py

# Expected: 8/8 tests pass
```

#### 1.3 Test with Sample Data

```bash
# Run demo script
./demo.sh

# This will:
# - Parse sample XML
# - Generate JSON output
# - Show metrics structure
# - Run full test suite
```

### Phase 2: Device Connection (15 minutes)

#### 2.1 Verify NETCONF Access

```bash
# Test SSH connection
ssh root@10.209.3.39

# Verify NETCONF is enabled
show system services
# Look for: netconf { ssh; }

# Test NETCONF subsystem
ssh -s root@10.209.3.39 -p 830 netconf
# Press Ctrl+C to exit
```

#### 2.2 Update Inventory

Edit `inventory.yml` if needed:

```yaml
junos_devices:
  hosts:
    10.209.3.39:
      ansible_user: root
      ansible_password: Empe1mpls
```

#### 2.3 Test Playbook Connectivity

```bash
# Dry run
ansible-playbook -i inventory.yml junos_telemetry.yml --check

# If successful, run actual collection
ansible-playbook -i inventory.yml junos_telemetry.yml
```

### Phase 3: Prometheus Integration (30 minutes)

#### 3.1 Deploy Prometheus Pushgateway

```bash
# Using Docker
docker run -d --name pushgateway \
  -p 9091:9091 \
  prom/pushgateway

# Verify it's running
curl http://localhost:9091/metrics
```

#### 3.2 Configure Prometheus

Edit `prometheus.yml`:

```yaml
global:
  scrape_interval: 15s

scrape_configs:
  - job_name: 'pushgateway'
    honor_labels: true
    static_configs:
      - targets: ['localhost:9091']
```

Start Prometheus:

```bash
docker run -d --name prometheus \
  -p 9090:9090 \
  -v $PWD/prometheus.yml:/etc/prometheus/prometheus.yml \
  prom/prometheus
```

#### 3.3 Run Playbook with Prometheus Push

```bash
ansible-playbook -i inventory.yml junos_telemetry.yml \
  -e "prometheus_pushgateway=http://localhost:9091"
```

#### 3.4 Verify Metrics in Prometheus

```bash
# Check Pushgateway
curl http://localhost:9091/metrics | grep junos_optics

# Query Prometheus
curl 'http://localhost:9090/api/v1/query?query=junos_optics_rx_power_dbm'
```

### Phase 4: Visualization (30 minutes)

#### 4.1 Deploy Grafana

```bash
docker run -d --name grafana \
  -p 3000:3000 \
  grafana/grafana
```

Access: http://localhost:3000 (admin/admin)

#### 4.2 Add Prometheus Data Source

1. Configuration → Data Sources → Add data source
2. Select Prometheus
3. URL: http://localhost:9090
4. Save & Test

#### 4.3 Create Dashboard

Sample PromQL queries:

```promql
# RX Power per interface/lane
junos_optics_rx_power_dbm{device="10.209.3.39"}

# TX Power per interface/lane
junos_optics_tx_power_dbm{device="10.209.3.39"}

# TX Bias Current
junos_optics_tx_bias_current_milliamps{device="10.209.3.39"}

# Average RX power per interface (across all lanes)
avg by (interface) (junos_optics_rx_power_dbm{device="10.209.3.39"})
```

### Phase 5: Production Deployment (1 hour)

#### 5.1 Add Multiple Devices

Update `inventory.yml`:

```yaml
junos_devices:
  hosts:
    router1.example.com:
      ansible_user: automation
      ansible_password: "{{ vault_password }}"
    router2.example.com:
      ansible_user: automation
      ansible_password: "{{ vault_password }}"
```

Use Ansible Vault for passwords:

```bash
ansible-vault encrypt_string 'SecurePassword123' --name 'vault_password'
```

#### 5.2 Add More RPC Commands

Edit `rpc_commands.yml`:

```yaml
rpc_commands:
  - name: optics_diagnostics
    rpc: get-interface-optics-diagnostics-information
    parser: optics_diagnostics
    description: "Optical interface metrics"
  
  - name: interface_stats
    rpc: get-interface-information
    parser: interface_stats
    description: "Interface statistics"
```

Create parser for new RPC:

```bash
cp parsers/template_parser.py parsers/interface_stats.py
# Edit parser to handle interface statistics
```

#### 5.3 Schedule Collection

Using cron:

```bash
# Edit crontab
crontab -e

# Add entry (every 5 minutes)
*/5 * * * * cd /path/to/telemetry && ansible-playbook -i inventory.yml junos_telemetry.yml
```

Using systemd timer:

```ini
# /etc/systemd/system/junos-telemetry.timer
[Unit]
Description=Collect Junos Telemetry Every 5 Minutes

[Timer]
OnBootSec=5min
OnUnitActiveSec=5min

[Install]
WantedBy=timers.target
```

```ini
# /etc/systemd/system/junos-telemetry.service
[Unit]
Description=Junos Telemetry Collection

[Service]
Type=oneshot
WorkingDirectory=/path/to/telemetry
ExecStart=/usr/bin/ansible-playbook -i inventory.yml junos_telemetry.yml
User=automation
```

Enable:

```bash
systemctl enable junos-telemetry.timer
systemctl start junos-telemetry.timer
```

#### 5.4 Monitoring and Alerting

Configure Prometheus alerts (`alert_rules.yml`):

```yaml
groups:
  - name: optics_alerts
    rules:
      - alert: LowOpticalPower
        expr: junos_optics_rx_power_dbm < -10
        for: 5m
        labels:
          severity: warning
        annotations:
          summary: "Low optical RX power on {{ $labels.interface }}"
          description: "RX power is {{ $value }}dBm on {{ $labels.device }}/{{ $labels.interface }}/lane{{ $labels.lane }}"
      
      - alert: HighLaserBias
        expr: junos_optics_tx_bias_current_milliamps > 80
        for: 5m
        labels:
          severity: critical
        annotations:
          summary: "High laser bias on {{ $labels.interface }}"
          description: "TX bias is {{ $value }}mA on {{ $labels.device }}/{{ $labels.interface }}/lane{{ $labels.lane }}"
```

## Troubleshooting

### NETCONF Connection Issues

```bash
# Check network connectivity
ping 10.209.3.39

# Verify SSH works
ssh root@10.209.3.39 "show version"

# Test NETCONF with verbose SSH
ssh -v -s root@10.209.3.39 -p 830 netconf

# Check Ansible connection
ansible -i inventory.yml junos_devices -m ping
```

### Parser Issues

```bash
# Check raw XML output
cat output/10.209.3.39_optics_diagnostics_raw.xml

# Test parser manually
python3 parsers/optics_diagnostics.py \
  --input output/10.209.3.39_optics_diagnostics_raw.xml \
  --output /tmp/test.json \
  --device 10.209.3.39 \
  --format json

# Validate JSON
cat /tmp/test.json | python3 -m json.tool
```

### Prometheus Push Issues

```bash
# Check Pushgateway is accessible
curl http://localhost:9091/metrics

# Test push manually
python3 scripts/push_to_prometheus.py \
  --pushgateway http://localhost:9091 \
  --job test \
  --instance test-device \
  --metrics-file output/10.209.3.39_optics_diagnostics_metrics.json \
  --format json

# Check if metrics appear
curl http://localhost:9091/metrics | grep junos_optics
```

## Performance Considerations

### Collection Frequency

- **Recommended:** 5-15 minutes
- **High-frequency:** 1-5 minutes (for critical interfaces)
- **Low-frequency:** 15-60 minutes (for stable networks)

### Data Retention

Configure Prometheus retention:

```bash
# Keep 30 days of data
prometheus --storage.tsdb.retention.time=30d
```

### Scalability

- Single Ansible controller can handle ~100 devices
- Use multiple Pushgateway instances for high scale
- Consider Prometheus federation for multi-site deployments

## Security Best Practices

1. **Use Ansible Vault** for credentials
2. **Restrict NETCONF access** to specific IPs
3. **Use dedicated service accounts** instead of root
4. **Enable TLS** for Prometheus/Pushgateway
5. **Implement RBAC** in Grafana
6. **Regular credential rotation**

## Next Steps

1. ✅ Complete Phase 1-3 (Setup, Connection, Integration)
2. 📊 Build Grafana dashboards
3. 🔔 Configure alerting rules
4. 📈 Add more RPC commands for comprehensive telemetry
5. 🔄 Implement automated anomaly detection
6. 📝 Document operational procedures

## Support Resources

- **Documentation:** See README.md and SUMMARY.md
- **Test Data:** parsers/test_data/README.md
- **Demo:** Run ./demo.sh
- **Logs:** Check output/ directory for raw XML and JSON

## Success Criteria

- ✅ All tests pass (8/8)
- ✅ Parser generates valid JSON
- ✅ Metrics appear in Prometheus
- ✅ Grafana displays data
- ✅ Scheduled collection running
- ✅ Alerts configured and testing
