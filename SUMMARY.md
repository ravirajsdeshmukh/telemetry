# Junos Optical Telemetry - Quick Summary

## What Was Delivered

A complete Ansible-based solution for collecting Junos optical interface metrics via NETCONF and exporting them to Prometheus in JSON format.

## Key Features

✅ **Multiple RPC Command Support** - Extensible framework for executing different RPC commands
✅ **JSON Output Format** - Structured data with interface and lane-level metrics  
✅ **Field Mappings** - XPath-based mappings for interface thresholds and lane measurements
✅ **Namespace Handling** - Robust XML parsing that works with any Junos version
✅ **Comprehensive Testing** - Full test suite with sample data
✅ **Prometheus Integration** - Automatic conversion and push to Pushgateway
✅ **Metadata Injection** - Support for custom metadata fields

## Project Structure

```
telemetry/
├── junos_telemetry.yml              # Main Ansible playbook
├── inventory.yml                    # Device inventory
├── rpc_commands.yml                 # RPC configuration
├── ansible.cfg                      # Ansible settings
├── requirements.txt                 # Python dependencies
├── demo.sh                          # Demo/test script
├── README.md                        # Full documentation
├── parsers/
│   ├── optics_diagnostics.py       # Optical diagnostics parser
│   ├── template_parser.py          # Template for new parsers
│   ├── test_optics_diagnostics.py  # Comprehensive test suite
│   └── test_data/
│       ├── optics_rpc_response.xml # Sample RPC output
│       ├── optics_lane_rpc_prom.json # Expected format
│       ├── interface-mapping.meta  # Interface field mappings
│       ├── lane-mapping.meta       # Lane field mappings
│       └── README.md               # Testing documentation
└── scripts/
    └── push_to_prometheus.py       # Prometheus push script
```

## JSON Output Structure

The parser generates two types of metrics:

### Interface Metrics (Thresholds)
- Temperature alarm/warn thresholds
- Voltage alarm/warn thresholds  
- TX/RX power alarm/warn thresholds
- TX bias current alarm/warn thresholds

### Lane Metrics (Measured Values)
- `rx_power_mw` & `rx_power` (dBm)
- `tx_power_mw` & `tx_power` (dBm)
- `tx_bias` (mA)
- Per-lane measurements for multi-lane optics

## Quick Start

```bash
# 1. Install dependencies
pip install -r requirements.txt
ansible-galaxy collection install junipernetworks.junos

# 2. Run tests
cd parsers && python3 test_optics_diagnostics.py

# 3. Run demo
./demo.sh

# 4. Execute playbook
ansible-playbook -i inventory.yml junos_telemetry.yml
```

## Test Results

All 8 tests pass:
- ✅ Numeric value extraction
- ✅ Field mappings validation
- ✅ Interface metrics parsing
- ✅ Lane metrics parsing
- ✅ Not supported interface handling
- ✅ JSON output format
- ✅ Full XML parsing
- ✅ Additional metadata injection

## Sample Output

**Lane Metrics:**
```json
{
  "if_name": "et-0/0/32",
  "device": "10.209.3.39",
  "lane": 0,
  "rx_power_mw": 0.591,
  "rx_power": -2.28,
  "tx_power_mw": 0.585,
  "tx_power": -2.32,
  "tx_bias": 6.157
}
```

**Prometheus Format:**
```
junos_optics_rx_power_dbm{device="10.209.3.39",interface="et-0/0/32",lane="0"} -2.28
junos_optics_tx_power_dbm{device="10.209.3.39",interface="et-0/0/32",lane="0"} -2.32
junos_optics_tx_bias_current_milliamps{device="10.209.3.39",interface="et-0/0/32",lane="0"} 6.157
```

## Adding New RPC Commands

1. Add to `rpc_commands.yml`:
```yaml
- name: new_command
  rpc: get-new-information
  parser: new_parser
  description: "Description"
```

2. Create `parsers/new_parser.py` based on template

3. Add test data and tests

## Device Configuration

The solution connects to:
- **Device:** 10.209.3.39
- **Username:** root
- **Password:** Empe1mpls
- **Protocol:** NETCONF (port 830)

## Next Steps

1. Customize metadata fields for your environment
2. Add additional RPC commands as needed
3. Set up Prometheus Pushgateway
4. Configure Prometheus to scrape metrics
5. Build Grafana dashboards for visualization
6. Schedule playbook execution (cron/Jenkins)

## Support

- Full documentation in [README.md](README.md)
- Test data documentation in [parsers/test_data/README.md](parsers/test_data/README.md)
- Run `./demo.sh` for end-to-end demonstration
