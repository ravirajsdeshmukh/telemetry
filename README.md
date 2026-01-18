# Junos Telemetry to Prometheus

Ansible playbook for collecting telemetry from Junos devices via NETCONF and exporting metrics to Prometheus.

## Features

- Connect to Junos devices using NETCONF
- Execute multiple RPC commands
- Parse XML output and convert to Prometheus line protocol
- Push metrics to Prometheus Pushgateway
- Extensible parser framework for different RPC commands

## Requirements

### Python Packages
```bash
pip install ansible
pip install junos-eznc
pip install requests
pip install pyarrow>=11.0.0
pip install pandas>=1.5.0
pip install boto3>=1.26.0
pip install botocore>=1.29.0
```

### Ansible Collections
```bash
ansible-galaxy collection install -r requirements.yml
# Installs:
# - junipernetworks.junos >=5.0.0
# - community.aws >=6.0.0
```

## Directory Structure

```
.
├── ansible/
│   ├── junos_telemetry.yml           # Main Ansible playbook
│   ├── inventory.yml                 # Production device inventory
│   ├── junos_devices_semaphore.yaml  # Semaphore inventory (xai, regression groups)
│   ├── rpc_commands.yml              # RPC commands configuration
│   ├── requirements.yml              # Ansible collection dependencies
│   ├── requirements.txt              # Python package dependencies
│   ├── group_vars/                   # Group-level variables
│   │   ├── all/                      # Variables for all hosts
│   │   │   ├── vars.yml              # AWS credential references
│   │   │   └── vault.yml             # Encrypted AWS credentials
│   │   ├── junos/                    # Production device credentials
│   │   │   ├── vars.yml              # Connection settings
│   │   │   └── vault.yml             # Encrypted device credentials
│   │   ├── xai/                      # XAI RMA device credentials
│   │   │   ├── vars.yml              # Connection settings
│   │   │   └── vault.yml             # Encrypted credentials
│   │   └── regression/               # Regression lab credentials
│   │       ├── vars.yml              # Connection settings
│   │       └── vault.yml             # Encrypted credentials
│   ├── vault/
│   │   └── vault_password            # Vault decryption password (DO NOT COMMIT)
│   ├── parsers/                      # Parser scripts for different RPCs
│   │   ├── common/                   # Shared utilities
│   │   │   ├── xml_utils.py          # XML parsing helpers
│   │   │   ├── fiber_detection.py    # Fiber type detection
│   │   │   └── interface_mapping.py  # Interface name mapping
│   │   └── juniper/                  # Juniper-specific parsers
│   │       ├── optics_diagnostics.py # Optical diagnostics parser
│   │       ├── chassis_inventory.py  # Hardware inventory parser
│   │       ├── system_information.py # System info parser
│   │       ├── interface_statistics.py # Interface counters parser
│   │       └── merge_metadata.py     # Metadata merger
│   └── scripts/                      # Utility scripts
│       ├── push_to_prometheus.py     # Push metrics to Prometheus
│       ├── write_hourly_parquet.py   # Aggregate to hourly Parquet files
│       ├── write_to_parquet.py       # Per-device Parquet writer
│       └── collect_pic_details.py    # Collect transceiver details
├── output/                           # Temporary metrics and raw XML
├── raw_ml_data/                      # ML training data (Parquet format)
│   └── dt=YYYY-MM-DD/
│       └── hr=HH/
│           ├── intf-dom/             # Interface-level DOM metrics
│           ├── lane-dom/             # Lane-level DOM metrics
│           └── intf-counters/        # Interface traffic counters
├── infrastructure/
│   ├── docker-compose.yml            # Prometheus, Grafana, Pushgateway
│   ├── prometheus.yml                # Prometheus configuration
│   └── mounts/                       # Docker volume mounts
└── docs/                             # Documentation
    ├── ANSIBLE_VAULT_SETUP.md        # Credential management
    ├── S3_SYNC_SETUP.md              # AWS S3 data lake sync
    ├── SEMAPHORE_SETUP.md            # Semaphore orchestration
    ├── INTERFACE_FILTERING.md        # Interface filtering
    └── ML_DATA_COLLECTION.md         # ML data format and usage
```

## Configuration

### 1. Vault Password

Create a vault password file (this is used to decrypt credentials):

```bash
cd ansible
echo "your_vault_password" > vault/vault_password
chmod 600 vault/vault_password
```

**Important**: Add `vault/vault_password` to `.gitignore` - never commit this file!

### 2. Device Credentials

Credentials are stored in encrypted Ansible Vault files under `group_vars/`. See [docs/ANSIBLE_VAULT_SETUP.md](docs/ANSIBLE_VAULT_SETUP.md) for details.

#### Quick Setup:

```bash
# Create temporary file with credentials
cat > /tmp/vault_temp.yml <<EOF
---
vault_junos_username: root
vault_junos_password: YourPassword
EOF

# Encrypt and save
ansible-vault encrypt /tmp/vault_temp.yml \
  --vault-password-file vault/vault_password \
  --output group_vars/junos/vault.yml

# Clean up
rm /tmp/vault_temp.yml
chmod 600 group_vars/junos/vault.yml
```

### 3. Inventory Files

**inventory.yml** - Production devices:
```yaml
all:
  children:
    junos:
      hosts:
        device1.example.com:
          interface_filter: "et-0/0/32"
        device2.example.com:
          interface_filter: "et-0/0/0,et-0/0/1"
```

**junos_devices_semaphore.yaml** - Organized by device groups:
```yaml
all:
  children:
    junos_devices:
      children:
        xai:  # XAI RMA devices
          hosts:
            xai-qfx5240-01.englab.juniper.net:
              interface_filter: "et-0/0/11:0,et-0/0/9:0"
        regression:  # Regression lab devices
          hosts:
            garnet-qfx5240-a.englab.juniper.net:
```

Credentials are automatically loaded from `group_vars/{group_name}/vault.yml`.

### 4. AWS Credentials (for S3 Sync)

AWS credentials for S3 data lake sync are stored in `group_vars/all/vault.yml`:

```bash
# Create temporary file
cat > /tmp/vault_aws_temp.yml <<EOF
---
vault_aws_access_key_id: "YOUR_ACCESS_KEY"
vault_aws_secret_access_key: "YOUR_SECRET_KEY"
vault_aws_session_token: "YOUR_SESSION_TOKEN"  # Optional, for STS credentials
EOF

# Encrypt
ansible-vault encrypt /tmp/vault_aws_temp.yml \
  --vault-password-file vault/vault_password \
  --output group_vars/all/vault.yml

rm /tmp/vault_aws_temp.yml
```

See [docs/S3_SYNC_SETUP.md](docs/S3_SYNC_SETUP.md) for details.

### 5. RPC Commands (rpc_commands.yml)

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

Run the playbook with vault password file:

```bash
cd ansible
ansible-playbook junos_telemetry.yml \
  -i inventory.yml \
  --vault-password-file vault/vault_password
```

Or with Semaphore inventory:

```bash
ansible-playbook junos_telemetry.yml \
  -i junos_devices_semaphore.yaml \
  --vault-password-file vault/vault_password
```

### Target Specific Device Groups

Run only for XAI devices:
```bash
ansible-playbook junos_telemetry.yml \
  -i junos_devices_semaphore.yaml \
  --vault-password-file vault/vault_password \
  --limit xai
```

Run only for regression devices:
```bash
ansible-playbook junos_telemetry.yml \
  -i junos_devices_semaphore.yaml \
  --vault-password-file vault/vault_password \
  --limit regression
```

### Without Prometheus Pushgateway

If you don't want to push to Prometheus:

```bash
ansible-playbook junos_telemetry.yml \
  -i inventory.yml \
  --vault-password-file vault/vault_password \
  -e "prometheus_pushgateway="
```

### Custom Output Directory

```bash
ansible-playbook junos_telemetry.yml \
  -i inventory.yml \
  --vault-password-file vault/vault_password \
  -e "output_dir=/tmp/metrics"
```

### Filter Specific Interfaces

Monitor only specific interfaces by setting the `interface_filter` variable:

```bash
# Monitor only two specific interfaces (applies to all devices)
ansible-playbook junos_telemetry.yml \
  -i inventory.yml \
  --vault-password-file vault/vault_password \
  -e 'interface_filter="et-0/0/32,et-0/0/33"'

# Monitor single interface
ansible-playbook junos_telemetry.yml \
  -i inventory.yml \
  --vault-password-file vault/vault_password \
  -e 'interface_filter="et-0/0/32"'
```

**Per-Device Filtering:**

For different interfaces on each device, configure `interface_filter` in your inventory file:

```yaml
all:
  children:
    junos:
      hosts:
        device1.example.com:
          interface_filter: "et-0/0/32,et-0/0/33"  # Specific to this device
        
        device2.example.com:
          interface_filter: "et-0/0/48"  # Different interfaces
        
        device3.example.com:
          # No filter - monitors all interfaces
```

Then run without `-e` flag:

```bash
ansible-playbook junos_telemetry.yml \
  -i inventory.yml \
  --vault-password-file vault/vault_password
```

**Filter Precedence:**
1. Device-specific filter (in inventory.yml) - Highest priority
2. Global filter (in junos_telemetry.yml vars or `-e` flag) - Medium priority
3. No filter - Default, monitors all interfaces

You can also configure a global default in the playbook variables section of [junos_telemetry.yml](junos_telemetry.yml):

```yaml
vars:
  interface_filter: "et-0/0/32,et-0/0/33"  # Comma-separated list
```

If `interface_filter` is not set or empty, all interfaces will be monitored (default behavior).

See [docs/INTERFACE_FILTERING.md](docs/INTERFACE_FILTERING.md) for detailed examples and use cases.

### With Prometheus Pushgateway

```bash
ansible-playbook junos_telemetry.yml \
  -i inventory.yml \
  --vault-password-file vault/vault_password \
  -e "prometheus_pushgateway=http://your-pushgateway:9091"
```

## Data Lake and ML Training

The playbook automatically creates hourly Parquet files for ML training:

```
raw_ml_data/
└── dt=2026-01-18/
    └── hr=14/
        ├── intf-dom/
        │   └── interface_dom_20260118_140613.parquet
        ├── lane-dom/
        │   └── lane_dom_20260118_140613.parquet
        └── intf-counters/
            └── interface_counters_20260118_140613.parquet
```

**Features:**
- Hive-style partitioning by date and hour
- Snappy compression for storage efficiency
- Three separate schemas for different metric types
- Automatic S3 sync to `s3://amzn-ds-s3-rrd/datalake/`

See [docs/ML_DATA_COLLECTION.md](docs/ML_DATA_COLLECTION.md) for schema details and query examples.

## S3 Data Lake Sync

After each collection, data is automatically synced to S3:

```yaml
# Configured in group_vars/all/vault.yml
vault_aws_access_key_id: "YOUR_KEY"
vault_aws_secret_access_key: "YOUR_SECRET"
vault_aws_session_token: "YOUR_TOKEN"  # For STS credentials
```

To disable S3 sync, comment out AWS credentials or run without them.

See [docs/S3_SYNC_SETUP.md](docs/S3_SYNC_SETUP.md) for configuration details.

## Semaphore Orchestration

For scheduled execution and enterprise orchestration:

1. Use `junos_devices_semaphore.yaml` inventory
2. Configure task templates in Semaphore UI
3. Set up cron schedules (e.g., `*/5 * * * *` for 5-minute intervals)
4. Configure vault password as environment variable

See [docs/SEMAPHORE_SETUP.md](docs/SEMAPHORE_SETUP.md) for full setup instructions.

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

## Credential Architecture

### Overview

The project uses Ansible Vault for secure credential management with a hierarchical group-based structure:

```
group_vars/
├── all/              # Credentials available to ALL hosts
│   ├── vault.yml     # AWS credentials (encrypted)
│   └── vars.yml      # Variable references
├── junos/            # Production device credentials
│   ├── vault.yml     # Device credentials (encrypted)
│   └── vars.yml      # Connection settings
├── xai/              # XAI RMA device credentials
│   ├── vault.yml     # Device credentials (encrypted)
│   └── vars.yml      # Connection settings
└── regression/       # Regression lab credentials
    ├── vault.yml     # Device credentials (encrypted)
    └── vars.yml      # Connection settings
```

### Group Hierarchy

**inventory.yml** (Production):
```
all
└── junos
    └── hosts: device1.example.com, device2.example.com, ...
```

**junos_devices_semaphore.yaml** (Organized by function):
```
all
└── junos_devices
    ├── xai (RMAed devices for failure analysis)
    │   └── hosts: xai-qfx5240-01, kakao-fa-qfx5220
    └── regression (Lab test devices)
        └── hosts: garnet-qfx5240-a, garnet-qfx5240-c, ...
```

### Variable Precedence

Ansible loads variables in this order (later overrides earlier):
1. `group_vars/all/` - AWS credentials (all hosts)
2. `group_vars/{group_name}/` - Device-specific credentials
3. Host-specific variables in inventory

This allows:
- Shared AWS credentials across all devices
- Different device credentials per group (production vs lab)
- Per-device interface filters

### Security Features

- **Encryption**: All credentials encrypted with AES256
- **Single password file**: `vault/vault_password` decrypts all vaults
- **No plaintext**: Never commit unencrypted credentials
- **Separation**: Device credentials separate from AWS credentials
- **Permissions**: All vault files have 600 permissions (owner read/write only)

See [docs/ANSIBLE_VAULT_SETUP.md](docs/ANSIBLE_VAULT_SETUP.md) for complete documentation.

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
