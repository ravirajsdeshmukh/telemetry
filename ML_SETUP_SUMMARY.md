# ML Data Collection Setup - Implementation Summary

## What Was Implemented

This document summarizes the ML data collection pipeline implementation for optical transceiver degradation prediction.

## Changes Applied

### 1. New Python Scripts Created

#### a. `parsers/juniper/interface_statistics.py`
- **Purpose**: Parse `get-interface-information` RPC output (non-extensive to reduce compute load)
- **Extracts**:
  - FEC corrected/uncorrected codeword counts (cumulative counters)
  - FEC corrected/uncorrected error rates (from device)
  - Pre-FEC BER (Bit Error Rate in scientific notation)
  - FEC histogram bins 0-15 (live + harvest errors, plus individual components)
  - Admin/oper status, interface speed
  - Traffic statistics (bps, pps)
- **Key Functions**: `extract_numeric_value()`, `parse_speed()`, `parse_interface_statistics()`

#### b. `scripts/calculate_throughput.py`
- **Purpose**: Calculate FEC error deltas between collection runs
- **Features**:
  - Maintains state per device/interface in JSON files
  - Calculates `fec_ccw_delta`, `fec_nccw_delta`
  - Computes error rates (errors per second)
  - Tracks collection intervals
- **State Directory**: `output/throughput_state/{device}/{interface}.json`
- **Usage**: `python3 calculate_throughput.py --metrics-file <file> --state-dir <dir> --device <hostname>`

#### c. `scripts/write_to_parquet.py`
- **Purpose**: Write metrics to date-partitioned Parquet files
- **Features**:
  - Date partitioning: `dt=YYYY-MM-DD`
  - Optional device sub-partitioning: `dt=2026-01-14/device=hostname/`
  - Snappy compression
  - Timestamped filenames: `metric_type_20260114_093000.parquet`
  - Supports multiple metric types: optical_metrics, interface_stats, transceiver_info
- **Usage**: `python3 write_to_parquet.py --metrics-file <file> --output-dir <dir> --metric-type <type> [--partition-by-device]`

### 2. Configuration Updates

#### a. `ansible/rpc_commands.yml`
Added new RPC command:
```yaml
- name: interface_statistics
  rpc: get-interface-information
  rpc_args:
    extensive: true  # Required for FEC histogram and detailed stats
  parser: juniper/interface_statistics
  description: "Collect interface statistics, FEC histogram, errors, and throughput for ML training"
```

#### b. `ansible/junos_telemetry.yml`
Updated playbook to:
1. Handle `rpc_args` parameter in RPC execution
2. Added 4 new tasks after metadata merge:
   - **Calculate FEC error deltas** (runs `calculate_throughput.py`)
   - **Write optical metrics to Parquet** (optical power, temp, bias)
   - **Write interface stats to Parquet** (FEC data, errors, histogram)
   - **Write PIC details to Parquet** (transceiver metadata)

#### c. `ansible/requirements.txt`
Added ML dependencies:
```
pyarrow>=11.0.0
pandas>=1.5.0
```

### 3. Documentation

Created `docs/ML_DATA_COLLECTION.md` with:
- Architecture overview
- Data flow diagram
- Storage structure explanation
- Collected metrics reference
- Python query examples
- Troubleshooting guide

## Data Flow

```
1. Junos Device
   ↓ NETCONF RPC: get-interface-information extensive
2. Raw XML saved to output/
   ↓ Parse with interface_statistics.py
3. JSON metrics: interface_statistics_metrics.json
   ↓ calculate_throughput.py
4. Enhanced JSON with deltas: fec_ccw_delta, fec_nccw_delta, rates
   ↓ write_to_parquet.py
5. Parquet files: output/ml_data/dt=YYYY-MM-DD/device=hostname/*.parquet
   ↓ Read with pandas/pyarrow
6. ML Training: Features + Target (uncorrected FEC errors)
```

## Storage Structure

```
output/
├── ml_data/                           # ML training data (new)
│   ├── dt=2026-01-14/
│   │   └── device=dcf-onyx27-jun.englab.juniper.net/
│   │       ├── optical_metrics_20260114_093000.parquet
│   │       ├── interface_stats_20260114_093000.parquet
│   │       └── transceiver_info_20260114_093000.parquet
│   └── dt=2026-01-15/
│       └── ...
├── throughput_state/                  # State for delta calculations (new)
│   └── dcf-onyx27-jun.englab.juniper.net/
│       ├── et-0_0_32.json
│       └── et-0_0_33.json
└── *_metrics.json                     # Existing JSON metrics
```

## ML Features for Optics Degradation

### Target Variable
- `fec_nccw_delta` or `fec_nccw_rate`: Uncorrected FEC errors (indicates degradation)

### Feature Categories

1. **FEC Statistics** (from interface_stats)
   - `fec_ccw_rate`: Corrected errors per second
   - `histogram_bin_0` to `histogram_bin_15`: Error distribution

2. **Optical Metrics** (from optical_metrics)
   - `rx_dbm`: Receive power level
   - `tx_dbm`: Transmit power level
   - `temperature_c`: Operating temperature
   - `laser_bias_current_ma`: Laser current

3. **Traffic Load** (from interface_stats)
   - `input_bps`, `output_bps`: Throughput
   - `input_pps`, `output_pps`: Packet rate

4. **Transceiver Metadata** (from transceiver_info)
   - `vendor`, `part_number`: Hardware identification
   - `cable_type`, `wavelength`: Physical properties

## Testing the Implementation

### 1. Install Dependencies

```bash
cd /home/ubuntu/workspace/telemetry/ansible
pip install -r requirements.txt
```

### 2. Run Playbook

```bash
ansible-playbook -i inventory.yml junos_telemetry.yml
```

### 3. Verify Output

```bash
# Check Parquet files created
find ../output/ml_data -name "*.parquet"

# Check state files
find ../output/throughput_state -name "*.json"

# View Parquet schema and data
python3 << EOF
import pyarrow.parquet as pq
import pandas as pd

# Read a sample file
files = !find ../output/ml_data -name "*interface_stats*.parquet" | head -1
if files:
    table = pq.read_table(files[0])
    print("Schema:")
    print(table.schema)
    print(f"\nRows: {len(table)}")
    print("\nSample data:")
    print(table.to_pandas().head())
EOF
```

### 4. Query Data for ML

```python
import pandas as pd

# Read data for specific date range
df = pd.read_parquet(
    '../output/ml_data',
    filters=[
        ('dt', '>=', '2026-01-10'),
        ('dt', '<=', '2026-01-14')
    ]
)

# Filter to interfaces with FEC errors
degraded = df[df['fec_nccw_rate'] > 0]

print(f"Total records: {len(df)}")
print(f"Records with uncorrected errors: {len(degraded)}")
print(f"\nDevices: {df['device'].unique()}")
print(f"Interfaces: {df['interface'].unique()}")
```

## Key Benefits

1. **Efficient Storage**: Parquet columnar format with compression
2. **Fast Queries**: Predicate pushdown with date/device partitioning
3. **Time-Series Ready**: Date-based partitioning for chronological analysis
4. **Delta Tracking**: Automatic calculation of counter changes
5. **Schema Evolution**: Parquet supports adding new columns
6. **ML Framework Compatible**: Direct integration with pandas, scikit-learn, PyTorch

## What Wasn't Changed

- Existing Prometheus push pipeline (still works)
- Raw XML outputs (still saved)
- JSON metrics files (still created)
- Metadata merging logic (unchanged)
- PIC detail collection (unchanged)

## Next Steps

### Immediate
1. Run playbook to collect first dataset
2. Verify Parquet files are created correctly
3. Test delta calculations across multiple runs

### ML Model Development
1. Create Jupyter notebook for exploratory data analysis
2. Engineer additional features (rolling averages, trends)
3. Train classification model (healthy vs degrading)
4. Train regression model (predict time to failure)
5. Deploy model for real-time inference

### Infrastructure
1. Add scheduled collection (cron or Ansible Tower)
2. Implement data retention policy
3. Add monitoring for collection pipeline
4. Create dashboards for ML predictions

## Troubleshooting

### Issue: No interface_statistics data collected
- **Check**: RPC command is in `rpc_commands.yml`
- **Check**: Playbook task for parsing ran successfully
- **Check**: Device supports `get-interface-information extensive`

### Issue: No Parquet files created
- **Check**: Python dependencies installed (`pip list | grep -E "pyarrow|pandas"`)
- **Check**: Output directory writable
- **Check**: JSON metrics file exists and is valid
- **Debug**: Run script manually:
  ```bash
  cd /home/ubuntu/workspace/telemetry/ansible
  python3 scripts/write_to_parquet.py \
    --metrics-file ../output/hostname_interface_statistics_metrics.json \
    --output-dir ../output/ml_data \
    --metric-type interface_stats \
    --device hostname \
    --partition-by-device
  ```

### Issue: Delta calculations always zero
- **Check**: State directory exists and has previous run data
- **Note**: First run will have zero deltas (no previous state)
- **Verify**: Run playbook twice, second run should have deltas

### Issue: Memory errors with large datasets
- **Solution**: Use PyArrow directly instead of pandas
- **Solution**: Read only required columns
- **Solution**: Filter by date partitions

## Files Created/Modified

### New Files
- ✅ `parsers/juniper/interface_statistics.py` (310 lines)
- ✅ `scripts/calculate_throughput.py` (220 lines)
- ✅ `scripts/write_to_parquet.py` (260 lines)
- ✅ `docs/ML_DATA_COLLECTION.md` (documentation)
- ✅ `ML_SETUP_SUMMARY.md` (this file)

### Modified Files
- ✅ `ansible/rpc_commands.yml` (added interface_statistics RPC)
- ✅ `ansible/junos_telemetry.yml` (added 4 ML collection tasks)
- ✅ `ansible/requirements.txt` (added pyarrow, pandas)

## Summary

The ML data collection pipeline is now fully integrated into the Ansible playbook. Every playbook run will:

1. Collect interface statistics with FEC histogram
2. Calculate deltas from previous run
3. Write optical metrics to Parquet
4. Write interface stats to Parquet
5. Write transceiver info to Parquet
6. Continue pushing to Prometheus (existing functionality)

The data is ready for ML model training to predict optical transceiver degradation based on FEC error patterns, optical power levels, temperature, and other features.
