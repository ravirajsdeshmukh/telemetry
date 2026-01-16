# ML Data Collection for Optics Degradation Prediction

## Overview

This document describes the machine learning data collection pipeline for predicting optical transceiver degradation.

## Architecture

The ML data collection pipeline collects metrics from Junos devices and stores them in Parquet files with date-based partitioning for efficient time-series analysis.

### Data Flow

```
Junos Device → NETCONF/RPC → Parser → Calculate Deltas → Write to Parquet
                                ↓
                         Push to Prometheus
```

### Storage Structure

Data is stored in Parquet format with the following directory structure:

```
output/ml_data/
├── dt=2026-01-14/
│   ├── device=dcf-onyx27-jun.englab.juniper.net/
│   │   ├── optical_metrics_20260114_093000.parquet
│   │   ├── interface_stats_20260114_093000.parquet
│   │   └── transceiver_info_20260114_093000.parquet
│   └── device=garnet-qfx5240-a.englab.juniper.net/
│       ├── optical_metrics_20260114_093000.parquet
│       ├── interface_stats_20260114_093000.parquet
│       └── transceiver_info_20260114_093000.parquet
├── dt=2026-01-15/
│   └── ...
```

## Collected Metrics

### 1. Optical Metrics (optical_metrics)

From `optics_diagnostics_metrics.json`:
- **Optical Power**: tx_dbm, rx_dbm
- **Temperature**: temperature_c
- **Bias Current**: laser_bias_current_ma
- **Status**: status (OK, Warning, Alarm)
- **Metadata**: vendor, part_number, serial_number, media_type, fiber_type, cable_type, wavelength

**Source RPC**: `get-interface-optics-diagnostics-information`

### 2. Interface Statistics (interface_stats)

From `interface_statistics_metrics.json`:
- **FEC Counters**: 
  - `fec_ccw` (Corrected Codewords) - cumulative counter
  - `fec_nccw` (Uncorrected Codewords) - cumulative counter
  - `fec_ccw_delta` - change since last collection (from calculate_throughput.py)
  - `fec_nccw_delta` - change since last collection (from calculate_throughput.py)
  - `fec_ccw_rate` - errors per second (from device)
  - `fec_nccw_rate` - errors per second (from device)
- **FEC Histogram**: `histogram_bin_0` through `histogram_bin_15` (total live + harvest)
  - Also available: `histogram_bin_N_live` and `histogram_bin_N_harvest` for detailed analysis
- **Pre-FEC BER**: `pre_fec_ber` - Bit Error Rate in scientific notation
- **Interface Status**: admin_status, oper_status, speed_bps
- **Traffic**: input_bps, output_bps, input_pps, output_pps

**Source RPC**: `get-interface-information` (standard, not extensive - minimizes compute load)

### 3. Transceiver Information (transceiver_info)

From `pic_detail_metrics.json`:
- **Vendor Info**: vendor, part_number, serial_number
- **Cable Properties**: cable_type, wavelength, fiber_type
- **Hardware Location**: fpc, pic, port

**Source RPC**: `get-pic-detail` (per FPC/PIC slot)

## Delta Calculations

The `calculate_throughput.py` script maintains state between collection runs to calculate:

1. **FEC Error Deltas**: Changes in corrected/uncorrected codeword counts
2. **Error Rates**: Errors per second based on time interval
3. **Collection Interval**: Time elapsed between collections

State is stored in `output/throughput_state/{device}/{interface}.json`

## ML Use Cases

### Predicting Transceiver Degradation

**Target Variable**: `fec_nccw_delta` or `fec_nccw_rate` (uncorrected errors)

**Features**:
- FEC corrected codeword rate (`fec_ccw_rate`)
- FEC histogram distribution (bins 0-15) - live and harvest errors
- Pre-FEC BER (`pre_fec_ber`)
- Optical power levels (tx_dbm, rx_dbm)
- Temperature (temperature_c)
- Laser bias current (laser_bias_current_ma)
- Interface throughput (input_bps, output_bps)
- Transceiver metadata (vendor, part_number, cable_type, wavelength)

**Model Objectives**:
1. Predict future uncorrected FEC errors (degradation indicator)
2. Classify transceiver health status (healthy, degrading, critical)
3. Estimate remaining useful life (time to failure)

## Querying Parquet Data

### Python Example

```python
import pandas as pd
import pyarrow.parquet as pq

# Read data for specific date range
df = pd.read_parquet(
    'output/ml_data',
    filters=[
        ('dt', '>=', '2026-01-10'),
        ('dt', '<=', '2026-01-14'),
        ('device', '==', 'dcf-onyx27-jun.englab.juniper.net')
    ]
)

# Read specific metric type
optical_df = pd.read_parquet(
    'output/ml_data',
    filters=[
        ('dt', '==', '2026-01-14'),
        ('metric_type', '==', 'optical_metrics')
    ]
)

# Join optical metrics with interface stats
merged = pd.merge(
    optical_df, 
    interface_df,
    on=['device', 'interface', 'timestamp'],
    how='inner'
)
```

### Using PyArrow for Efficient Queries

```python
import pyarrow.parquet as pq
import pyarrow.compute as pc

# Read specific columns only
dataset = pq.ParquetDataset('output/ml_data', partitioning='hive')
table = dataset.read(
    columns=['timestamp', 'interface', 'fec_nccw_rate', 'rx_dbm'],
    filters=[
        ('dt', '>=', '2026-01-10'),
        ('fec_nccw_rate', '>', 0)  # Only rows with uncorrected errors
    ]
)
```

## Running the Pipeline

### 1. Install Dependencies

```bash
cd ansible
pip install -r requirements.txt
```

### 2. Run Collection

```bash
ansible-playbook -i inventory.yml junos_telemetry.yml
```

### 3. Verify Data

```bash
# Check Parquet files created
find output/ml_data -name "*.parquet"

# View schema
python3 << EOF
import pyarrow.parquet as pq
table = pq.read_table('output/ml_data/dt=2026-01-14/device=*/optical_metrics_*.parquet')
print(table.schema)
print(f"Rows: {len(table)}")
EOF
```

## Configuration

### Playbook Variables

In `junos_telemetry.yml`:
- `output_dir`: Output directory for raw and processed data (default: `../output`)
- `interface_filter`: Optional comma-separated list of interfaces to monitor

### Parquet Settings

In `write_to_parquet.py`:
- Compression: `snappy` (fast compression, good ratio)
- Partitioning: Date (`dt=YYYY-MM-DD`) and device
- Timestamp: Added automatically to all records

## Troubleshooting

### Issue: No interface_statistics data collected

**Check**: Verify RPC is configured in `rpc_commands.yml`:
```yaml
- name: interface_statistics
  rpc: get-interface-information
  rpc_args:
    extensive: true
```

### Issue: Delta calculations not working

**Check**: State directory exists and is writable:
```bash
ls -la output/throughput_state/
```

**Reset state** (will recalculate from scratch):
```bash
rm -rf output/throughput_state/*
```

### Issue: Parquet files not created

**Check logs** in playbook output:
```bash
ansible-playbook -i inventory.yml junos_telemetry.yml -vv
```

**Verify Python dependencies**:
```bash
python3 -c "import pyarrow; import pandas; print('OK')"
```

## Future Enhancements

1. **Aggregation**: Add hourly/daily aggregation for long-term trends
2. **Feature Engineering**: Add derived features (rate of change, moving averages)
3. **Data Validation**: Add schema validation and quality checks
4. **Compression Optimization**: Evaluate different compression algorithms
5. **Incremental Writes**: Optimize for append operations
6. **Data Retention**: Add cleanup for old partitions

## References

- [Apache Parquet Documentation](https://parquet.apache.org/docs/)
- [PyArrow Parquet](https://arrow.apache.org/docs/python/parquet.html)
- [FEC Error Analysis](https://www.juniper.net/documentation/us/en/software/junos/interfaces-ethernet-switches/topics/topic-map/switches-interface-fec.html)
