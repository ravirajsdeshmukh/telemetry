# Parser Architecture

This directory contains parsers for converting network device telemetry data into structured JSON format.

## Directory Structure

```
parsers/
├── common/                      # Shared utilities for all vendors
│   ├── __init__.py
│   ├── xml_utils.py            # XML parsing helpers (namespace handling, element access)
│   ├── fiber_detection.py      # Fiber type detection (SMF vs MMF)
│   └── interface_mapping.py    # Interface name mapping (FPC/PIC/Port -> interface name)
├── juniper/                     # Juniper Networks parsers
│   ├── __init__.py
│   ├── optics_diagnostics.py   # Optical diagnostics (show interfaces diagnostics optics)
│   ├── chassis_inventory.py    # Hardware inventory (show chassis hardware)
│   ├── system_information.py   # System info (show system information)
│   └── merge_metadata.py       # Merge system/chassis data with optics metrics
├── cisco/                       # Future: Cisco parsers
├── arista/                      # Future: Arista parsers
└── test_data/
    └── juniper/                 # Test data for Juniper parsers
        ├── optics_rpc_response.xml
        ├── optics_interface_rpc_prom.json
        └── ...
```

## Parser Organization

### Common Utilities

Shared code that can be used across all vendor parsers:

- **xml_utils.py**: Namespace-agnostic XML parsing functions
  - `strip_namespace()`: Remove namespace from XML tags
  - `findtext_ns()`, `find_ns()`, `findall_ns()`: Find elements ignoring namespaces
  - `extract_numeric_value()`: Extract numbers from text with units

- **fiber_detection.py**: Determine fiber type from media type or description
  - `determine_fiber_type()`: Returns FIBER_TYPE_SINGLE_MODE or FIBER_TYPE_MULTI_MODE
  - Pattern matching for SR/LR/ER/ZR indicators
  - Wavelength-based detection (850nm=MMF, 1310/1550nm=SMF)

- **interface_mapping.py**: Map hardware locations to interface names
  - `parse_juniper_interface_name()`: FPC/PIC/Port → interface name
  - `parse_interface_base_name()`: Remove channel suffix (et-0/0/6:2 → et-0/0/6)
  - Platform-specific prefix mapping (QFX5240 → et, MX → et, EX4300 → ge)

### Juniper Parsers

#### system_information.py
- **RPC**: `get-system-information`
- **CLI**: `show system information`
- **Extracts**:
  - `origin_hostname`: Device hostname
  - `device_profile`: "Juniper_{model}" (e.g., "Juniper_QFX5240-64D")
  - `hardware_model`: Raw model name
  - `os_name`: Operating system name
  - `os_version`: OS version

#### chassis_inventory.py
- **RPC**: `get-chassis-inventory`
- **CLI**: `show chassis hardware`
- **Extracts**:
  - `origin_name`: Device serial number (from chassis)
  - Per-transceiver metadata:
    - `vendor`: Vendor name (e.g., "JUNIPER")
    - `part_number`: Part number (e.g., "740-021308")
    - `serial_number`: Serial number
    - `media_type`: Media type (e.g., "100GBASE-SR4")
    - `fiber_type`: FIBER_TYPE_SINGLE_MODE or FIBER_TYPE_MULTI_MODE

#### optics_diagnostics.py
- **RPC**: `get-interface-optics-diagnostics-information`
- **CLI**: `show interfaces diagnostics optics`
- **Extracts**:
  - Temperature metrics and thresholds
  - Voltage metrics and thresholds
  - TX/RX power metrics and thresholds (per interface and per lane)
  - TX bias current metrics and thresholds

#### merge_metadata.py
- Combines data from system_information, chassis_inventory, and optics_diagnostics
- Adds device-level metadata to all interface and lane records
- Maps transceiver metadata to interfaces using FPC/PIC/Port mapping

## Usage

### Individual Parser
```bash
python3 parsers/juniper/system_information.py \
  --input device_system_info.xml \
  --output device_system_info.json \
  --device device.example.com
```

### Via Ansible Playbook
The playbook automatically:
1. Executes RPCs defined in `rpc_commands.yml`
2. Calls appropriate parsers based on `parser` field
3. Merges metadata from multiple sources
4. Outputs unified JSON files

```bash
ansible-playbook junos_telemetry.yml -i inventory.yml
```

## Field Names

### Device-Level Fields
- `origin_hostname`: Device hostname
- `origin_name`: Device serial number
- `device_profile`: "Juniper_{model}"
- `device`: Device identifier (hostname/IP)

### Transceiver-Level Fields
- `vendor`: Optical transceiver vendor
- `part_number`: Transceiver part number
- `serial_number`: Transceiver serial number
- `media_type`: Media type (e.g., "100GBASE-SR4")
- `fiber_type`: FIBER_TYPE_SINGLE_MODE or FIBER_TYPE_MULTI_MODE

### Optical Metrics
- `if_name`: Interface name (e.g., "et-0/0/32")
- `temperature`, `voltage`: Current measurements
- `tx_power`, `rx_power`: Optical power (dBm)
- `tx_bias`: Laser bias current (mA)
- `*_high_alarm`, `*_low_alarm`: Alarm thresholds
- `*_high_warn`, `*_low_warn`: Warning thresholds

## Adding New Vendors

To add support for a new vendor (e.g., Cisco):

1. Create vendor directory:
   ```bash
   mkdir parsers/cisco
   ```

2. Create parser files using common utilities:
   ```python
   from common.xml_utils import findtext_ns, extract_numeric_value
   from common.fiber_detection import determine_fiber_type
   ```

3. Update `rpc_commands.yml`:
   ```yaml
   - name: cisco_optics
     rpc: show_interface_transceiver
     parser: cisco/optics_parser
     description: "Cisco optical diagnostics"
   ```

4. Add test data:
   ```bash
   mkdir parsers/test_data/cisco
   ```

## Testing

Test individual parsers:
```bash
cd ansible
python3 parsers/juniper/optics_diagnostics.py \
  --input parsers/test_data/juniper/optics_rpc_response.xml \
  --output /tmp/test.json \
  --device test-device
```

Test common utilities:
```python
from common.fiber_detection import determine_fiber_type

fiber_type = determine_fiber_type(media_type="100GBASE-SR4")
# Returns: "FIBER_TYPE_MULTI_MODE"
```

## Benefits of This Architecture

1. **Code Reuse**: Common utilities shared across all vendors
2. **Maintainability**: Each parser is self-contained
3. **Extensibility**: Easy to add new vendors/platforms
4. **Testability**: Each component can be tested independently
5. **Clarity**: Clear separation of concerns
