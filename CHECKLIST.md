# Pre-Flight Checklist

Use this checklist before running the solution in production.

## ✅ Environment Setup

- [ ] Python 3.7+ installed
- [ ] pip installed and updated
- [ ] Ansible 2.10+ installed
- [ ] All requirements from requirements.txt installed
  ```bash
  pip install -r requirements.txt
  ```
- [ ] Junos Ansible collection installed
  ```bash
  ansible-galaxy collection install junipernetworks.junos
  ```

## ✅ Parser Validation

- [ ] Test suite passes (8/8 tests)
  ```bash
  cd parsers && python3 test_optics_diagnostics.py
  ```
- [ ] Sample data parsing works
  ```bash
  python3 parsers/optics_diagnostics.py \
    --input parsers/test_data/optics_rpc_response.xml \
    --output /tmp/test.json \
    --device test \
    --format json
  ```
- [ ] JSON output is valid
  ```bash
  cat /tmp/test.json | python3 -m json.tool
  ```

## ✅ Network Connectivity

- [ ] Device is reachable
  ```bash
  ping 10.209.3.39
  ```
- [ ] SSH access works
  ```bash
  ssh root@10.209.3.39
  ```
- [ ] NETCONF is enabled on device
  ```bash
  ssh root@10.209.3.39 "show system services" | grep netconf
  ```
- [ ] NETCONF port (830) is accessible
  ```bash
  telnet 10.209.3.39 830
  # or
  nc -zv 10.209.3.39 830
  ```

## ✅ Ansible Configuration

- [ ] Inventory file configured
  - [ ] Device IP/hostname correct
  - [ ] Username correct
  - [ ] Password correct (or use vault)
- [ ] RPC commands file configured
  - [ ] Commands listed
  - [ ] Parsers mapped
- [ ] Ansible can reach device
  ```bash
  ansible -i inventory.yml junos_devices -m ping
  ```

## ✅ File Permissions

- [ ] All Python scripts are executable
  ```bash
  chmod +x parsers/*.py scripts/*.py demo.sh
  ```
- [ ] Output directory is writable
  ```bash
  mkdir -p output
  chmod 755 output
  ```

## ✅ Prometheus Integration (Optional)

- [ ] Pushgateway is running
  ```bash
  curl http://localhost:9091/metrics
  ```
- [ ] Prometheus is running (if scraping Pushgateway)
  ```bash
  curl http://localhost:9090/-/healthy
  ```
- [ ] Push script can connect to Pushgateway
  ```bash
  python3 scripts/push_to_prometheus.py \
    --pushgateway http://localhost:9091 \
    --job test \
    --instance test \
    --metrics-file /tmp/test.json \
    --format json
  ```

## ✅ First Playbook Run

- [ ] Run in check mode first
  ```bash
  ansible-playbook -i inventory.yml junos_telemetry.yml --check
  ```
- [ ] Run without Prometheus push
  ```bash
  ansible-playbook -i inventory.yml junos_telemetry.yml
  ```
- [ ] Verify output files created
  ```bash
  ls -l output/
  ```
- [ ] Verify raw XML is valid
  ```bash
  cat output/*_raw.xml | head
  ```
- [ ] Verify JSON metrics are valid
  ```bash
  cat output/*_metrics.json | python3 -m json.tool
  ```
- [ ] Check for any errors in Ansible output

## ✅ Prometheus Push (if enabled)

- [ ] Run playbook with Prometheus push
  ```bash
  ansible-playbook -i inventory.yml junos_telemetry.yml \
    -e "prometheus_pushgateway=http://localhost:9091"
  ```
- [ ] Verify metrics appear in Pushgateway
  ```bash
  curl http://localhost:9091/metrics | grep junos_optics
  ```
- [ ] Verify metrics appear in Prometheus
  ```bash
  curl 'http://localhost:9090/api/v1/query?query=junos_optics_rx_power_dbm'
  ```

## ✅ Production Readiness

- [ ] Passwords secured with Ansible Vault
  ```bash
  ansible-vault encrypt inventory.yml
  ```
- [ ] Scheduled execution configured (cron/systemd)
- [ ] Log rotation configured
- [ ] Monitoring alerts configured
- [ ] Documentation reviewed
- [ ] Team trained on operations
- [ ] Rollback plan documented
- [ ] Support contacts identified

## ✅ Performance Validation

- [ ] Playbook execution time is acceptable
  - Target: < 2 minutes per device
- [ ] Output file sizes are reasonable
  - Raw XML: typically < 100KB
  - JSON metrics: typically < 50KB
- [ ] System resource usage is acceptable
  - CPU: < 20% during execution
  - Memory: < 500MB
  - Disk: adequate space for logs/output

## ✅ Error Handling

- [ ] Test with non-responsive device
  - [ ] Playbook handles timeout gracefully
- [ ] Test with device without optical interfaces
  - [ ] Parser handles empty data
- [ ] Test with Pushgateway down
  - [ ] Playbook continues, logs error
- [ ] Test with invalid credentials
  - [ ] Clear error message displayed

## ✅ Documentation

- [ ] README.md reviewed
- [ ] SUMMARY.md reviewed
- [ ] IMPLEMENTATION_GUIDE.md followed
- [ ] ARCHITECTURE.md understood
- [ ] Team knows how to:
  - [ ] Run playbook
  - [ ] Check output
  - [ ] Add new devices
  - [ ] Add new RPC commands
  - [ ] Troubleshoot issues

## 🎯 Ready for Production

Once all items are checked:

1. Document initial baseline
   - Number of devices
   - Number of interfaces
   - Expected metric count
   - Collection frequency

2. Set up monitoring
   - Playbook execution success/failure
   - Metric freshness
   - Gap detection

3. Establish operational procedures
   - Who runs it
   - When to run manually
   - Escalation path

4. Schedule regular reviews
   - Weekly: Check for issues
   - Monthly: Review performance
   - Quarterly: Update documentation

## Common Issues Checklist

If something goes wrong, check:

- [ ] Device connectivity (ping, SSH)
- [ ] NETCONF enabled on device
- [ ] Credentials are correct
- [ ] Python dependencies installed
- [ ] Ansible collection installed
- [ ] File permissions correct
- [ ] Disk space available
- [ ] Network firewalls allow traffic
- [ ] Recent Ansible output for errors
- [ ] Recent parser output for errors
- [ ] Output directory for recent files

## Emergency Contacts

Document your support contacts:

- Network Team: ___________________
- Automation Team: ___________________
- Monitoring Team: ___________________
- On-Call: ___________________

## Sign-Off

- [ ] Technical Review Complete
  - Reviewer: ___________________
  - Date: ___________________

- [ ] Security Review Complete
  - Reviewer: ___________________
  - Date: ___________________

- [ ] Operational Review Complete
  - Reviewer: ___________________
  - Date: ___________________

- [ ] Approved for Production
  - Approver: ___________________
  - Date: ___________________
