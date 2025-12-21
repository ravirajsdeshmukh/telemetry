# Junos Telemetry to Prometheus

Ansible playbook for collecting telemetry from Junos devices via NETCONF and exporting metrics to Prometheus.

## Features

- Connect to Junos devices using NETCONF
- Execute multiple RPC commands
- Parse XML output and convert to Prometheus line protocol
- Push metrics to Prometheus Pushgateway
- Extensible parser framework for different RPC commands

## Requirements

```bash
pip install ansible
pip install junos-eznc
pip install requests
ansible-galaxy collection install junipernetworks.junos
```

## Directory Structure

```
.
├── junos_telemetry.yml           # Main Ansible playbook
├── inventory.yml                 # Device inventory
├── rpc_commands.yml              # RPC commands configuration
├── parsers/                      # Parser scripts for different RPCs
│   ├── optics_diagnostics.py    # Parser for optical diagnostics
│   └── template_parser.py       # Template for creating new parsers
├── scripts/                      # Utility scripts
│   └── push_to_prometheus.py    # Push metrics to Prometheus
└── output/                       # Generated metrics and raw XML (created at runtime)
```

## Configuration

### 1. Inventory (inventory.yml)

Update the device IP, username, and password:

```yaml
junos_devices:
  hosts:
    10.209.3.39:
      ansible_user: root
      ansible_password: Empe1mpls
```

### 2. RPC Commands (rpc_commands.yml)

Define the RPC commands to execute and their parsers:

```yaml
rpc_commands:
  - name: optics_diagnostics
    rpc: get-interface-optics-diagnostics-information
    parser: optics_diagnostics
    description: "Collect optical interface diagnostics"
```

## Usage

### Basic Execution

Run the playbook to collect metrics from all devices:

```bash
ansible-playbook -i inventory.yml junos_telemetry.yml
```

### Without Prometheus Pushgateway

If you don't want to push to Prometheus, just collect and save metrics:

```bash
ansible-playbook -i inventory.yml junos_telemetry.yml -e "prometheus_pushgateway="
```

### Custom Output Directory

```bash
ansible-playbook -i inventory.yml junos_telemetry.yml -e "output_dir=/tmp/metrics"
```

### Filter Specific Interfaces

Monitor only specific interfaces by setting the `interface_filter` variable:

```bash
# Monitor only two specific interfaces
ansible-playbook -i inventory.yml junos_telemetry.yml \
  -e 'interface_filter="et-0/0/32,et-0/0/33"'

# Monitor single interface
ansible-playbook -i inventory.yml junos_telemetry.yml \
  -e 'interface_filter="et-0/0/32"'
```

You can also configure this in the playbook variables section of [junos_telemetry.yml](junos_telemetry.yml):

```yaml
vars:
  interface_filter: "et-0/0/32,et-0/0/33"  # Comma-separated list
```

If `interface_filter` is not set or empty, all interfaces will be monitored (default behavior).

### With Prometheus Pushgateway

```bash
ansible-playbook -i inventory.yml junos_telemetry.yml \
  -e "prometheus_pushgateway=http://your-pushgateway:9091"
```

## Metrics Generated

### JSON Output Format

The parser now generates JSON output with two arrays:

#### 1. Interface-Level Metrics (Thresholds)

One record per interface containing alarm and warning thresholds:

```json
{
  "if_name": "et-0/0/32",
  "device": "10.209.3.39",
  "timestamp": 1766301679037778,
  "temperature_high_alarm": 90.0,
  "temperature_low_alarm": -10.0,
  "temperature_high_warn": 85.0,
  "temperature_low_warn": -5.0,
  "voltage_high_alarm": 3.63,
  "voltage_low_alarm": 2.97,
  "tx_power_high_alarm": 0.0,
  "tx_power_low_alarm": -5.99,
  "rx_power_high_alarm": 2.0,
  "rx_power_low_alarm": -13.9,
  "tx_bias_high_alarm": 13.0,
  "tx_bias_low_alarm": 4.0
}
```

#### 2. Lane-Level Metrics (Actual Values)

One record per lane containing measured values:

```json
{
  "if_name": "et-0/0/32",
  "device": "10.209.3.39",
  "lane": 0,
  "timestamp": 1766301679038761,
  "rx_power_mw": 0.591,
  "rx_power": -2.28,
  "tx_power_mw": 0.585,
  "tx_power": -2.32,
  "tx_bias": 6.157
}
```

### Prometheus Conversion

When pushed to Prometheus Pushgateway, lane metrics are converted to:

```
junos_optics_rx_power_milliwatts{job="junos_telemetry",instance="10.209.3.39",device="10.209.3.39",interface="et-0/0/32",lane="0"} 0.591
junos_optics_rx_power_dbm{job="junos_telemetry",instance="10.209.3.39",device="10.209.3.39",interface="et-0/0/32",lane="0"} -2.28
junos_optics_tx_power_dbm{job="junos_telemetry",instance="10.209.3.39",device="10.209.3.39",interface="et-0/0/32",lane="0"} -2.32
junos_optics_tx_bias_current_milliamps{job="junos_telemetry",instance="10.209.3.39",device="10.209.3.39",interface="et-0/0/32",lane="0"} 6.157
```

## Testing

### Run Parser Tests

```bash
cd parsers
python3 test_optics_diagnostics.py
```

### Run Demo Script

```bash
./demo.sh
```

The demo script will:
1. Parse sample XML to JSON
2. Display parsed metrics
3. Test with additional metadata
4. Convert to Prometheus format
5. Run the test suite
6. Optionally push to Prometheus Pushgateway

## Field Mappings

The parser uses XPath to field mappings defined in:

- **parsers/test_data/interface-mapping.meta** - Interface-level thresholds
- **parsers/test_data/lane-mapping.meta** - Lane-level measured values

### Adding Custom Metadata

You can inject custom metadata into the JSON output:

```bash
python3 parsers/optics_diagnostics.py \
  --input input.xml \
  --output output.json \
  --device 10.209.3.39 \
  --metadata '{"origin_hostname":"router1","site_id":"dc1","probe_label":"Optical Transceivers"}'
```

## Adding New RPC Commands

### 1. Add RPC to Configuration

Edit [rpc_commands.yml](rpc_commands.yml):

```yaml
rpc_commands:
  - name: my_new_rpc
    rpc: get-my-information
    parser: my_parser
    description: "Description of what this RPC collects"
```

### 2. Create Parser Script

Create `parsers/my_parser.py` based on [parsers/template_parser.py](parsers/template_parser.py):

```python
#!/usr/bin/env python3
import argparse
import xml.etree.ElementTree as ET
import sys

def parse_rpc_output(xml_content: str, device: str):
    metrics = []
    root = ET.fromstring(xml_content)
    
    # Your parsing logic here
    for element in root.findall('.//your-element'):
        name = element.findtext('name')
        value = element.findtext('value')
        labels = f'device="{device}",name="{name}"'
        metrics.append(f'junos_my_metric{{{labels}}} {value}')
    
    return metrics

# Use the same main() function as template_parser.py
```

### 3. Make Parser Executable

```bash
chmod +x parsers/my_parser.py
```

## Prometheus Setup

### Install Prometheus Pushgateway

```bash
docker run -d -p 9091:9091 prom/pushgateway
```

### Configure Prometheus

Add to your `prometheus.yml`:

```yaml
scrape_configs:
  - job_name: 'pushgateway'
    honor_labels: true
    static_configs:
      - targets: ['localhost:9091']
```

## Troubleshooting

### NETCONF Connection Issues

1. Verify NETCONF is enabled on the device:
```
show system services
```

2. Test NETCONF connectivity:
```bash
ssh -s root@10.209.3.39 -p 830 netconf
```

### Check Raw XML Output

Raw XML files are saved in the output directory:
```bash
cat output/10.209.3.39_optics_diagnostics_raw.xml
```

### Verify Generated Metrics

Check the generated Prometheus metrics:
```bash
cat output/10.209.3.39_optics_diagnostics_metrics.prom
```

### Enable Ansible Verbose Mode

```bash
ansible-playbook -i inventory.yml junos_telemetry.yml -vvv
```

## Scheduling with Cron

To collect metrics every 5 minutes:

```bash
*/5 * * * * cd /path/to/telemetry && ansible-playbook -i inventory.yml junos_telemetry.yml
```

## License

MIT
