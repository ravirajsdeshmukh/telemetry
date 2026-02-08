#!/usr/bin/env python3
"""
Write aggregated telemetry metrics from all devices to hourly Parquet files.
Creates 3 separate files per hour:
  - interface_dom.parquet: Interface-level DOM metrics
  - lane_dom.parquet: Lane-level DOM metrics  
  - interface_counters.parquet: Interface statistics and FEC metrics
"""

import argparse
import json
import sys
import os
from datetime import datetime
from pathlib import Path
from typing import Dict, List

try:
    import pyarrow as pa
    import pyarrow.parquet as pq
    import pandas as pd
except ImportError:
    print("Error: Required packages not installed. Run: pip install pyarrow pandas", file=sys.stderr)
    sys.exit(1)

# Import interface mapping utilities
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
from parsers.common.interface_mapping import parse_interface_base_name


def create_hourly_partition_path(base_dir: str, dt: datetime) -> Path:
    """
    Create hourly partitioned directory path: dt=YYYY-MM-DD/hr=HH
    
    Args:
        base_dir: Base directory for parquet files
        dt: Datetime for partitioning
    
    Returns:
        Path object for the partition directory
    """
    date_str = dt.strftime('%Y-%m-%d')
    hour_str = dt.strftime('%H')
    
    partition_path = Path(base_dir) / f"dt={date_str}" / f"hr={hour_str}"
    partition_path.mkdir(parents=True, exist_ok=True)
    return partition_path


def extract_interface_dom_metrics(device_data: Dict, run_timestamp: int = None) -> List[Dict]:
    """
    Extract interface-level DOM metrics from optics_diagnostics data.
    Enriches with chassis_inventory data (part_number, serial_number).
    
    Note: Vendor name comes from PIC detail (show chassis pic fpc-slot X pic-slot Y),
    which is already merged into optics_diagnostics via merge_metadata.py.
    Chassis inventory description is NOT a reliable source for vendor name.
    
    Schema:
        origin_hostname, origin_name, inventory_instance, timestamp, collection_timestamp,
        device_profile, vendor, media_type, fiber_type, if_name,
        temperature, voltage, part_number, serial_number
    """
    rows = []
    
    origin_hostname = device_data.get('origin_hostname', '')
    origin_name = device_data.get('origin_name', '')
    inventory_instance = device_data.get('inventory_instance', '')
    device_profile = device_data.get('device_profile', '')
    timestamp = run_timestamp if run_timestamp else int(datetime.utcnow().timestamp())
    collection_timestamp = datetime.utcfromtimestamp(timestamp).isoformat() + 'Z'
    
    # Build chassis inventory lookup by interface name (for part_number and serial_number only)
    chassis_inventory = {}
    for if_name, transceiver in device_data.get('chassis_inventory', {}).get('transceivers', {}).items():
        chassis_inventory[if_name] = {
            'part_number': transceiver.get('part_number', ''),
            'serial_number': transceiver.get('serial_number', '')
        }
    
    # Process interface-level metrics from optics_diagnostics
    for interface in device_data.get('optics_diagnostics', {}).get('interfaces', []):
        if_name = interface.get('if_name', '')
        
        if not if_name:
            raise ValueError("Interface name missing in optics_diagnostics data")

        # Strip channelization suffix (e.g., et-0/0/0:1 -> et-0/0/0) for chassis lookup
        parent_if_name = parse_interface_base_name(if_name)
        
        # Use chassis inventory data for part/serial numbers only
        chassis_data = chassis_inventory.get(parent_if_name, {})
        
        row = {
            'origin_hostname': origin_hostname,
            'origin_name': origin_name,
            'inventory_instance': inventory_instance,
            'timestamp': timestamp,
            'collection_timestamp': collection_timestamp,
            'device_profile': device_profile,
            'vendor': interface.get('vendor', ''),  # Vendor from PIC detail (via merge_metadata.py)
            'media_type': interface.get('media_type', ''),
            'fiber_type': interface.get('fiber_type', ''),
            'if_name': if_name,
            'temperature': interface.get('temperature'),
            'voltage': interface.get('voltage'),
            'part_number': chassis_data.get('part_number') or interface.get('part_number', ''),
            'serial_number': chassis_data.get('serial_number', '')
        }
        rows.append(row)
    
    return rows


def extract_lane_dom_metrics(device_data: Dict, run_timestamp: int = None) -> List[Dict]:
    """
    Extract lane-level DOM metrics from optics_diagnostics data.
    
    Schema:
        origin_hostname, origin_name, inventory_instance, timestamp, collection_timestamp,
        if_name, lane, tx_bias, tx_power, rx_power
    """
    rows = []
    
    origin_hostname = device_data.get('origin_hostname', '')
    origin_name = device_data.get('origin_name', '')
    inventory_instance = device_data.get('inventory_instance', '')
    timestamp = run_timestamp if run_timestamp else int(datetime.utcnow().timestamp())
    collection_timestamp = datetime.utcfromtimestamp(timestamp).isoformat() + 'Z'
    
    # Process lane-level metrics from optics_diagnostics
    for lane in device_data.get('optics_diagnostics', {}).get('lanes', []):
        if_name = lane.get('if_name', '')
        lane_id = lane.get('lane')
        tx_bias = lane.get('tx_bias')
        tx_power = lane.get('tx_power')
        rx_power = lane.get('rx_power')
        
        if (not if_name or 
            not isinstance(lane_id, int) or 
            not isinstance(tx_bias, (int, float)) or 
            not isinstance(tx_power, (int, float)) or 
            not isinstance(rx_power, (int, float))):
            raise ValueError("Invalid lane DOM data in optics_diagnostics - if_name: %s, lane: %s (int), tx_bias: %s (float), "
                           "tx_power: %s (float), rx_power: %s (float)" % (if_name, lane_id, tx_bias, tx_power, rx_power))

        row = {
            'origin_hostname': origin_hostname,
            'origin_name': origin_name,
            'inventory_instance': inventory_instance,
            'timestamp': timestamp,
            'collection_timestamp': collection_timestamp,
            'if_name': if_name,
            'lane': lane_id,
            'tx_bias': tx_bias,
            'tx_power': tx_power,
            'rx_power': rx_power
        }
        rows.append(row)
    
    return rows


def extract_interface_counters(device_data: Dict, run_timestamp: int = None) -> List[Dict]:
    """
    Extract interface counter metrics from interface_statistics data.
    
    Schema:
        origin_hostname, origin_name, inventory_instance, timestamp, collection_timestamp,
        if_name, admin_status, oper_status, speed_bps,
        input_bps, input_pps, output_bps, output_pps,
        fec_ccw, fec_nccw, fec_ccw_error_rate, fec_nccw_error_rate, pre_fec_ber
    """
    rows = []
    
    origin_hostname = device_data.get('origin_hostname', '')
    origin_name = device_data.get('origin_name', '')
    inventory_instance = device_data.get('inventory_instance', '')
    timestamp = run_timestamp if run_timestamp else int(datetime.utcnow().timestamp())
    collection_timestamp = datetime.utcfromtimestamp(timestamp).isoformat() + 'Z'
    
    # Process interface statistics
    for interface in device_data.get('interface_statistics', {}).get('interfaces', []):
        row = {
            'origin_hostname': origin_hostname,
            'origin_name': origin_name,
            'inventory_instance': inventory_instance,
            'timestamp': timestamp,
            'collection_timestamp': collection_timestamp,
            'if_name': interface.get('if_name', ''),
            'admin_status': interface.get('admin_status', ''),
            'oper_status': interface.get('oper_status', ''),
            'speed_bps': interface.get('speed_bps'),
            'input_bps': interface.get('input_bps'),
            'input_pps': interface.get('input_pps'),
            'output_bps': interface.get('output_bps'),
            'output_pps': interface.get('output_pps'),
            'fec_ccw': interface.get('fec_ccw'),
            'fec_nccw': interface.get('fec_nccw'),
            'fec_ccw_error_rate': interface.get('fec_ccw_error_rate'),
            'fec_nccw_error_rate': interface.get('fec_nccw_error_rate'),
            'pre_fec_ber': interface.get('pre_fec_ber')
        }
        rows.append(row)
    
    return rows


def write_parquet_file(rows: List[Dict], file_path: Path, compression: str = 'snappy'):
    """
    Write rows to a Parquet file with consistent schema.
    
    Args:
        rows: List of dictionaries to write
        file_path: Path to output file
        compression: Compression algorithm
    """
    if not rows:
        print(f"No rows to write for {file_path.name}", file=sys.stderr)
        return
    
    # Create DataFrame
    df = pd.DataFrame(rows)
    
    # Ensure string columns remain as strings (not dictionary-encoded)
    string_columns = ['origin_hostname', 'origin_name', 'inventory_instance', 'collection_timestamp',
                     'device_profile', 'vendor', 'media_type', 'fiber_type',
                     'if_name', 'part_number', 'admin_status', 'oper_status']
    for col in string_columns:
        if col in df.columns:
            df[col] = df[col].astype(str)
    
    # Convert to PyArrow Table
    table = pa.Table.from_pandas(df, preserve_index=False)
    
    # Write parquet file (append if exists)
    if file_path.exists():
        # Read existing table and concatenate
        existing_table = pq.read_table(file_path)
        table = pa.concat_tables([existing_table, table])
    
    pq.write_table(
        table,
        file_path,
        compression=compression,
        use_dictionary=False,  # Prevent dictionary encoding for schema consistency
        write_statistics=True
    )
    
    print(f"Wrote {len(rows)} rows to {file_path}")


def process_all_devices(metrics_dir: str, base_dir: str, cluster_name: str, runner_name: str, partition_dir: str = None, run_timestamp: int = None, compression: str = 'snappy'):
    """
    Process all device metrics and write to 3 hourly Parquet files.
    
    Args:
        metrics_dir: Directory containing *_metrics_with_metadata.json files
        base_dir: Base directory for parquet storage
        cluster_name: Cluster identifier to include in filenames
        runner_name: Semaphore runner name to include in filenames
        partition_dir: Hourly partition directory (e.g., 'dt=2026-01-25/hr=06'), if None will use current UTC time
        run_timestamp: Unix timestamp for this playbook run, if None will use current UTC time
        compression: Compression algorithm
    """
    all_interface_dom = []
    all_lane_dom = []
    all_interface_counters = []
    
    metrics_path = Path(metrics_dir)
    
    # Group metrics files by device
    # Files are named: {device}_{metric_type}_metrics.json
    device_files = {}
    for json_file in metrics_path.glob('*_metrics.json'):
        # Skip files that are aggregated outputs
        if 'metrics_with_metadata' in json_file.name:
            continue
        
        # Parse filename: {device}_{metric_type}_metrics.json
        # Extract device and metric_type
        filename = json_file.stem  # Remove .json
        if not filename.endswith('_metrics'):
            continue
        
        # Remove '_metrics' suffix
        name_without_suffix = filename[:-8]  # Remove '_metrics'
        
        # Split by underscore to find metric type
        # Metric types: system_information, chassis_inventory, optics_diagnostics, interface_statistics
        metric_type = None
        device = None
        
        if name_without_suffix.endswith('_system_information'):
            metric_type = 'system_information'
            device = name_without_suffix[:-19]
        elif name_without_suffix.endswith('_chassis_inventory'):
            metric_type = 'chassis_inventory'
            device = name_without_suffix[:-18]
        elif name_without_suffix.endswith('_optics_diagnostics'):
            metric_type = 'optics_diagnostics'
            device = name_without_suffix[:-19]
        elif name_without_suffix.endswith('_interface_statistics'):
            metric_type = 'interface_statistics'
            device = name_without_suffix[:-21]
        
        if device and metric_type:
            if device not in device_files:
                device_files[device] = {}
            device_files[device][metric_type] = json_file
    
    if not device_files:
        print(f"No metrics files found in {metrics_dir}", file=sys.stderr)
        sys.exit(1)
    
    print(f"Processing metrics from {len(device_files)} devices...")
    
    # Aggregate data from all devices
    for device, metric_files in device_files.items():
        try:
            print(f"  Processing {device}...")
            
            # Load all metric types for this device
            device_data = {'origin_hostname': device, 'origin_name': device}
            
            for metric_type, file_path in metric_files.items():
                with open(file_path, 'r') as f:
                    data = json.load(f)
                    if metric_type == 'system_information':
                        device_data.update(data)
                        # Set inventory_instance from device field (FQDN from inventory)
                        device_data['inventory_instance'] = data.get('device', device)
                    elif metric_type == 'optics_diagnostics':
                        device_data['optics_diagnostics'] = data
                    elif metric_type == 'interface_statistics':
                        device_data['interface_statistics'] = data
                    elif metric_type == 'chassis_inventory':
                        device_data['chassis_inventory'] = data
                        # Merge top-level fields like origin_name (device serial number)
                        if 'origin_name' in data:
                            device_data['origin_name'] = data['origin_name']
            
            # Extract metrics for each type
            interface_dom = extract_interface_dom_metrics(device_data, run_timestamp)
            lane_dom = extract_lane_dom_metrics(device_data, run_timestamp)
            interface_counters = extract_interface_counters(device_data, run_timestamp)
            
            all_interface_dom.extend(interface_dom)
            all_lane_dom.extend(lane_dom)
            all_interface_counters.extend(interface_counters)
            
            print(f"    Interface DOM: {len(interface_dom)} rows")
            print(f"    Lane DOM: {len(lane_dom)} rows")
            print(f"    Interface Counters: {len(interface_counters)} rows")
            
        except Exception as e:
            print(f"Error processing {device}: {e}", file=sys.stderr)
            import traceback
            traceback.print_exc()
            continue
    
    # Use provided partition directory or create from current UTC time
    if partition_dir:
        partition_path = Path(base_dir) / partition_dir
        partition_path.mkdir(parents=True, exist_ok=True)
    else:
        now_utc = datetime.utcnow()
        partition_path = create_hourly_partition_path(base_dir, now_utc)
    
    # Generate timestamp suffix for filenames to avoid overwriting
    timestamp_str = datetime.utcnow().strftime('%Y%m%d_%H%M%S')
    
    print(f"\nWriting hourly Parquet files to {partition_path}...")
    
    # Create separate subdirectories for each metric type
    intf_dom_dir = partition_path / 'intf-dom'
    lane_dom_dir = partition_path / 'lane-dom'
    intf_counters_dir = partition_path / 'intf-counters'
    
    intf_dom_dir.mkdir(exist_ok=True)
    lane_dom_dir.mkdir(exist_ok=True)
    intf_counters_dir.mkdir(exist_ok=True)
    
    # Write 3 Parquet files to their respective directories with cluster, runner, and timestamp
    write_parquet_file(
        all_interface_dom,
        intf_dom_dir / f'interface_dom_{cluster_name}_{runner_name}_{timestamp_str}.parquet',
        compression
    )
    
    write_parquet_file(
        all_lane_dom,
        lane_dom_dir / f'lane_dom_{cluster_name}_{runner_name}_{timestamp_str}.parquet',
        compression
    )
    
    write_parquet_file(
        all_interface_counters,
        intf_counters_dir / f'interface_counters_{cluster_name}_{runner_name}_{timestamp_str}.parquet',
        compression
    )
    
    print(f"\nSummary:")
    print(f"  Total interface DOM rows: {len(all_interface_dom)}")
    print(f"  Total lane DOM rows: {len(all_lane_dom)}")
    print(f"  Total interface counter rows: {len(all_interface_counters)}")


def main():
    parser = argparse.ArgumentParser(
        description='Write aggregated device metrics to hourly Parquet files'
    )
    parser.add_argument('--metrics-dir', required=True,
                       help='Directory containing *_metrics_with_metadata.json files')
    parser.add_argument('--base-dir', required=True,
                       help='Base directory for parquet storage (e.g., output/ml_data)')
    parser.add_argument('--cluster-name', required=True,
                       help='Cluster identifier')
    parser.add_argument('--runner-name', required=True,
                       help='Semaphore runner name (must be set)'))
    parser.add_argument('--partition-dir', required=False,
                       help='Hourly partition directory relative to base-dir (e.g., dt=2026-01-25/hr=06)')
    parser.add_argument('--run-timestamp', type=int, required=False,
                       help='Unix timestamp for this playbook run (if not provided, current time will be used)')
    parser.add_argument('--compression', default='snappy',
                       choices=['snappy', 'gzip', 'brotli', 'none'],
                       help='Compression algorithm')
    
    args = parser.parse_args()
    
    if not args.runner_name or args.runner_name.strip() == '':
        raise ValueError("SEMAPHORE_RUNNER_NAME must be set and cannot be empty")
    
    try:
        process_all_devices(
            args.metrics_dir, 
            args.base_dir, 
            args.cluster_name,
            args.runner_name, 
            args.partition_dir,
            args.run_timestamp,
            args.compression
        )
        print("\nSuccessfully wrote hourly Parquet files!")
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == '__main__':
    main()
