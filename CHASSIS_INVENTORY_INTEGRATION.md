# Chassis Inventory Integration Summary

## Overview
Added vendor, part_number, and serial_number fields from chassis_inventory to interface-dom parquet files and Prometheus metrics.

## Changes Made

### 1. Parquet File Generation (`write_hourly_parquet.py`)

#### Added chassis_inventory loading:
```python
# Line 298: Added chassis_inventory to device_data
elif metric_type == 'chassis_inventory':
    device_data['chassis_inventory'] = data
```

#### Updated extract_interface_dom_metrics function:
- Added serial_number field to schema
- Built chassis_inventory lookup by interface name
- Enriched interface DOM data with chassis inventory (vendor, part_number, serial_number)
- Falls back to optics_diagnostics data if chassis_inventory not available

**Updated Schema:**
```
origin_hostname, origin_name, timestamp, collection_timestamp,
device_profile, vendor, media_type, fiber_type, if_name,
temperature, voltage, part_number, serial_number
```

### 2. Prometheus Metrics (`push_to_prometheus.py`)

**No changes needed** - Already has support for these labels (lines 43-47):
```python
if interface.get('vendor'):
    labels.append(f'vendor="{interface["vendor"]}"')
if interface.get('part_number'):
    labels.append(f'part_number="{interface["part_number"]}"')
if interface.get('serial_number'):
    labels.append(f'serial_number="{interface["serial_number"]}"')
```

### 3. Data Flow

The complete data flow is:

1. **Data Collection** (junos_telemetry.yml):
   - `get-system-information` → system_information_metrics.json
   - `get-chassis-inventory` → chassis_inventory_metrics.json
   - `get-interface-optics-diagnostics-information` → optics_diagnostics_metrics.json
   - `get-interface-information` → interface_statistics_metrics.json

2. **Metadata Merging** (merge_metadata.py):
   - Combines system_information + chassis_inventory + optics_diagnostics
   - Adds vendor, part_number, serial_number to each interface/lane
   - Output: enriched optics_diagnostics_metrics.json

3. **Prometheus Export** (push_to_prometheus.py):
   - Reads enriched metrics
   - Creates Prometheus labels including vendor, part_number, serial_number
   - Pushes to Prometheus Pushgateway

4. **Parquet Generation** (write_hourly_parquet.py):
   - Reads all metric files per device
   - Loads chassis_inventory data
   - Enriches interface DOM with chassis inventory fields
   - Writes to hourly partitioned parquet files: `dt=YYYY-MM-DD/hr=HH/intf-dom/`

## Files Modified

1. `/home/ubuntu/workspace/telemetry/ansible/scripts/write_hourly_parquet.py`
   - Added chassis_inventory loading in process_all_devices()
   - Enhanced extract_interface_dom_metrics() to merge chassis data
   - Added serial_number field to parquet schema

## Testing

To verify the changes work:

1. **Check Parquet Files:**
   ```bash
   parquet-tools schema infrastructure/mounts/raw_ml_data/dt=*/hr=*/intf-dom/*.parquet | grep -E "vendor|part_number|serial_number"
   ```

2. **Check Prometheus Metrics:**
   ```bash
   curl http://localhost:9091/metrics | grep -E "vendor=|part_number=|serial_number="
   ```

3. **Run Ansible Playbook:**
   ```bash
   cd ansible
   ansible-playbook -i inventory.yml junos_telemetry.yml
   ```

## Notes

- Chassis inventory data takes precedence over optics diagnostics data for vendor/part_number
- Serial number only comes from chassis_inventory (not available in optics_diagnostics)
- Data is matched by interface name (e.g., et-0/0/0)
- For channelized interfaces (e.g., et-0/0/0:0), base interface name is used (et-0/0/0)
