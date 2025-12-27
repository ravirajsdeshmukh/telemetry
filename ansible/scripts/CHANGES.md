# Push to Prometheus Updates - Summary

## Changes Made

### 1. Updated [`ansible/scripts/push_to_prometheus.py`](ansible/scripts/push_to_prometheus.py)

**Problem**: DOM metrics (tx_bias, tx_power_mw, tx_power, rx_power_mw, rx_power) were only being exported at the lane level, but some interfaces have these metrics directly on the interface without lanes.

**Solution**: Added logic to export DOM metrics at the interface level (without lane label) when they are present in the interface data.

**Code Changes**:
```python
# DOM metrics at interface level (for interfaces without lanes)
if interface.get('tx_bias') is not None:
    lines.append(f'tx_bias{{{base_labels}}} {interface["tx_bias"]}')
if interface.get('tx_power_mw') is not None:
    lines.append(f'tx_power_mw{{{base_labels}}} {interface["tx_power_mw"]}')
if interface.get('tx_power') is not None:
    lines.append(f'tx_power{{{base_labels}}} {interface["tx_power"]}')
if interface.get('rx_power_mw') is not None:
    lines.append(f'rx_power_mw{{{base_labels}}} {interface["rx_power_mw"]}')
if interface.get('rx_power') is not None:
    lines.append(f'rx_power{{{base_labels}}} {interface["rx_power"]}')
```

### 2. Created [`ansible/scripts/test_push_to_prometheus.py`](ansible/scripts/test_push_to_prometheus.py)

Comprehensive test suite with 7 test cases:

1. **test_interface_with_dom_metrics_no_lanes**: Tests interfaces with DOM metrics directly (no lanes)
2. **test_interface_with_null_dom_metrics_and_lanes**: Tests interfaces with null DOM metrics but lanes present
3. **test_mixed_interfaces**: Tests mix of interfaces with and without lane data
4. **test_all_thresholds**: Tests all threshold metrics are properly exported
5. **test_empty_data**: Tests empty data handling
6. **test_multiple_lanes_same_interface**: Tests interface with multiple lanes
7. **test_real_world_data**: Tests with actual production data

All tests pass ✓

## Behavior

### Before Changes
- DOM metrics were **only** exported with lane label
- Interfaces like `xe-0/0/6` with DOM metrics directly on interface were not properly exported

### After Changes
- **Interface-level DOM metrics** (when present): Exported without lane label
  ```
  tx_bias{device="...",interface="xe-0/0/6"} 5.392
  tx_power{device="...",interface="xe-0/0/6"} -2.27
  rx_power{device="...",interface="xe-0/0/6"} -2.01
  ```

- **Lane-level DOM metrics** (when present): Exported with lane label
  ```
  tx_bias{device="...",interface="xe-0/0/48:2",lane="2"} 6.335
  tx_power{device="...",interface="xe-0/0/48:2",lane="2"} -3.77
  rx_power{device="...",interface="xe-0/0/48:2",lane="2"} -1.03
  ```

- **Null values**: Not exported (both at interface and lane level)

## Test Results

```bash
$ python3 test_push_to_prometheus.py -v
test_all_thresholds ... ok
test_empty_data ... ok
test_interface_with_dom_metrics_no_lanes ... ok
test_interface_with_null_dom_metrics_and_lanes ... ok
test_mixed_interfaces ... ok
test_multiple_lanes_same_interface ... ok
test_real_world_data ... ok

Ran 7 tests in 0.000s

OK
```

## Impact

- **Backward Compatible**: Lane-level metrics continue to work as before
- **Complete Coverage**: Now handles both interface-level and lane-level DOM metrics
- **Production Ready**: Tested with real data from dcf-onyx27-jun.englab.juniper.net
