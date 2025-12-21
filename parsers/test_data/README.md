# Testing the Optics Diagnostics Parser

This directory contains test data and test cases for the optical diagnostics parser.

## Test Files

- **optics_rpc_response.xml** - Sample RPC response from Junos device
- **optics_lane_rpc_prom.json** - Expected JSON output format for lane metrics
- **interface-mapping.meta** - XPath to field name mappings for interface-level metrics
- **lane-mapping.meta** - XPath to field name mappings for lane-level metrics

## Running Tests

```bash
# Run all tests
cd /Users/rrd/workspace/telemetry/parsers
python3 test_optics_diagnostics.py

# Run with verbose output
python3 test_optics_diagnostics.py -v
```

## Test Coverage

The test suite validates:

1. **Numeric value extraction** - Parsing values with units
2. **Interface metrics parsing** - Threshold values for temperature, voltage, power, bias
3. **Lane metrics parsing** - Per-lane RX/TX power and bias current
4. **Namespace handling** - Proper XML namespace support
5. **Not supported interfaces** - Handling interfaces without diagnostics
6. **JSON output format** - Proper serialization
7. **Field mappings** - All required fields from mapping files
8. **Additional metadata** - Custom metadata injection

## Expected Output

### Interface Metrics
```json
{
  "if_name": "et-0/0/32",
  "device": "10.209.3.39",
  "timestamp": 1766301679037778,
  "temperature_high_alarm": 90.0,
  "temperature_low_alarm": -10.0,
  "voltage_high_alarm": 3.63,
  "tx_power_high_alarm": 0.0,
  "rx_power_high_alarm": 2.0,
  "tx_bias_high_alarm": 13.0,
  ...
}
```

### Lane Metrics
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

## Manual Testing

Test the parser directly:

```bash
# Parse sample XML
python3 optics_diagnostics.py \
  --input test_data/optics_rpc_response.xml \
  --output /tmp/output.json \
  --device 10.209.3.39 \
  --format json

# View the output
cat /tmp/output.json | python3 -m json.tool

# Test with metadata
python3 optics_diagnostics.py \
  --input test_data/optics_rpc_response.xml \
  --output /tmp/output.json \
  --device 10.209.3.39 \
  --format json \
  --metadata '{"origin_hostname":"test-device","probe_label":"Optical Transceivers"}'
```

## Field Mappings

### Interface Level (from interface-mapping.meta)

These are threshold/alarm values per interface:

- Temperature: `temperature_high_alarm`, `temperature_low_alarm`, `temperature_high_warn`, `temperature_low_warn`
- Voltage: `voltage_high_alarm`, `voltage_low_alarm`, `voltage_high_warn`, `voltage_low_warn`
- TX Power: `tx_power_high_alarm`, `tx_power_low_alarm`, `tx_power_high_warn`, `tx_power_low_warn`
- RX Power: `rx_power_high_alarm`, `rx_power_low_alarm`, `rx_power_high_warn`, `rx_power_low_warn`
- TX Bias: `tx_bias_high_alarm`, `tx_bias_low_alarm`, `tx_bias_high_warn`, `tx_bias_low_warn`

### Lane Level (from lane-mapping.meta)

These are actual measured values per lane:

- `if_name` - Interface name
- `lane` - Lane index (0, 1, 2, 3, etc.)
- `rx_power_mw` - Receive power in milliwatts
- `rx_power` - Receive power in dBm
- `tx_power_mw` - Transmit power in milliwatts
- `tx_power` - Transmit power in dBm
- `tx_bias` - Transmit bias current in milliamps

## Troubleshooting

### XML Namespace Issues

The parser automatically handles XML namespaces. If you encounter namespace-related errors, ensure you're using the namespace-aware helper functions:

- `findall_recursive_ns()` - Find elements ignoring namespace
- `findtext_ns()` - Get element text ignoring namespace
- `find_ns()` - Find single element ignoring namespace

### Missing Data

If the parser returns empty arrays:

1. Check that the XML has `<physical-interface>` elements
2. Verify that interfaces have `<optics-diagnostics>` data
3. Look for `<optic-diagnostics-not-available>` elements (these are skipped)

### Metric Validation

Compare your output against the sample JSON file:
```bash
diff <(jq -S '.lanes[0]' /tmp/output.json) <(jq -S '.' test_data/optics_lane_rpc_prom.json)
```
