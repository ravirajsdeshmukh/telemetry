#!/usr/bin/env python3
"""
Write telemetry metrics to partitioned Parquet files for ML training.
Supports appending to existing partitions and date-based partitioning (dt=YYYY-MM-DD).
"""

import argparse
import json
import sys
import os
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional

try:
    import pyarrow as pa
    import pyarrow.parquet as pq
    import pandas as pd
except ImportError:
    print("Error: Required packages not installed. Run: pip install pyarrow pandas", file=sys.stderr)
    sys.exit(1)


def create_partition_path(base_dir: str, date: datetime, device: str = None) -> Path:
    """
    Create partitioned directory path with dt=YYYY-MM-DD format.
    
    Args:
        base_dir: Base directory for parquet files
        date: Date for partitioning
        device: Optional device name for additional partitioning
    
    Returns:
        Path object for the partition directory
    """
    date_str = date.strftime('%Y-%m-%d')
    
    if device:
        # Create path: base_dir/dt=2026-01-14/device=hostname/
        partition_path = Path(base_dir) / f"dt={date_str}" / f"device={device}"
    else:
        # Create path: base_dir/dt=2026-01-14/
        partition_path = Path(base_dir) / f"dt={date_str}"
    
    partition_path.mkdir(parents=True, exist_ok=True)
    return partition_path


def flatten_metrics(data: Dict, metric_type: str) -> List[Dict]:
    """
    Flatten JSON metrics into rows for DataFrame.
    
    Args:
        data: JSON data with metrics
        metric_type: Type of metrics ('optical', 'interface_stats', etc.)
    
    Returns:
        List of flattened metric dictionaries
    """
    rows = []
    
    if metric_type == 'optical':
        # Flatten interfaces
        for interface in data.get('interfaces', []):
            row = interface.copy()
            row['metric_type'] = 'interface'
            rows.append(row)
        
        # Flatten lanes
        for lane in data.get('lanes', []):
            row = lane.copy()
            row['metric_type'] = 'lane'
            rows.append(row)
    
    elif metric_type == 'interface_stats':
        # Interface statistics
        for interface in data.get('interfaces', []):
            rows.append(interface.copy())
    
    elif metric_type == 'pic_detail':
        # Transceiver details
        for if_name, transceiver in data.get('transceivers', {}).items():
            row = transceiver.copy()
            row['if_name'] = if_name
            row['device'] = data.get('device')
            rows.append(row)
    
    return rows


def write_to_parquet(data: Dict, base_dir: str, metric_type: str, 
                     device: str, partition_by_device: bool = True,
                     compression: str = 'snappy') -> str:
    """
    Write metrics to partitioned Parquet file with appending support.
    
    Args:
        data: Metrics data (JSON format)
        base_dir: Base directory for parquet storage
        metric_type: Type of metrics (optical, interface_stats, pic_detail)
        device: Device hostname
        partition_by_device: Whether to partition by device
        compression: Compression algorithm (snappy, gzip, brotli)
    
    Returns:
        Path to written parquet file
    """
    # Flatten metrics to rows
    rows = flatten_metrics(data, metric_type)
    
    if not rows:
        print(f"No rows to write for {metric_type}", file=sys.stderr)
        return None
    
    # Create DataFrame
    df = pd.DataFrame(rows)
    
    # Add collection date column
    df['collection_date'] = datetime.now().strftime('%Y-%m-%d')
    df['collection_timestamp'] = datetime.now().isoformat()
    
    # Create partition path
    collection_date = datetime.now()
    partition_dir = create_partition_path(
        base_dir, 
        collection_date,
        device if partition_by_device else None
    )
    
    # Generate filename with timestamp
    timestamp_str = collection_date.strftime('%Y%m%d_%H%M%S')
    filename = f"{metric_type}_{timestamp_str}.parquet"
    file_path = partition_dir / filename
    
    # Convert to PyArrow Table
    table = pa.Table.from_pandas(df)
    
    # Write parquet file
    pq.write_table(
        table,
        file_path,
        compression=compression,
        use_dictionary=True,  # Efficient for repeated values
        write_statistics=True  # Enable predicate pushdown
    )
    
    print(f"Wrote {len(rows)} rows to {file_path}")
    return str(file_path)


def main():
    parser = argparse.ArgumentParser(
        description='Write metrics to partitioned Parquet files'
    )
    parser.add_argument('--input', required=True, help='Input JSON metrics file')
    parser.add_argument('--base-dir', required=True, help='Base directory for parquet storage')
    parser.add_argument('--metric-type', required=True,
                       choices=['optical', 'interface_stats', 'pic_detail'],
                       help='Type of metrics')
    parser.add_argument('--device', required=True, help='Device hostname')
    parser.add_argument('--no-device-partition', action='store_true',
                       help='Do not partition by device (only by date)')
    parser.add_argument('--compression', default='snappy',
                       choices=['snappy', 'gzip', 'brotli', 'none'],
                       help='Compression algorithm')
    
    args = parser.parse_args()
    
    # Read input JSON
    try:
        with open(args.input, 'r') as f:
            data = json.load(f)
    except (IOError, json.JSONDecodeError) as e:
        print(f"Error reading input file: {e}", file=sys.stderr)
        sys.exit(1)
    
    # Write to parquet
    try:
        file_path = write_to_parquet(
            data,
            args.base_dir,
            args.metric_type,
            args.device,
            partition_by_device=not args.no_device_partition,
            compression=args.compression
        )
        
        if file_path:
            print(f"Successfully wrote parquet file: {file_path}")
        else:
            print("No data written", file=sys.stderr)
            sys.exit(1)
            
    except Exception as e:
        print(f"Error writing parquet file: {e}", file=sys.stderr)
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == '__main__':
    main()
