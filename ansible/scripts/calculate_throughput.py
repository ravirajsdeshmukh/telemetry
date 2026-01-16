#!/usr/bin/env python3
"""
Calculate throughput deltas by comparing current and previous counter values.
Stores state for delta calculations between collection intervals.
"""

import argparse
import json
import sys
import os
from datetime import datetime
from typing import Dict, Optional
from pathlib import Path


class ThroughputCalculator:
    """
    Calculate throughput by tracking counter deltas over time.
    """
    
    def __init__(self, state_dir: str):
        """
        Initialize calculator with state directory.
        
        Args:
            state_dir: Directory to store previous counter states
        """
        self.state_dir = Path(state_dir)
        self.state_dir.mkdir(parents=True, exist_ok=True)
    
    def _get_state_file(self, device: str, interface: str) -> Path:
        """Get path to state file for device/interface."""
        # Sanitize interface name for filename
        safe_interface = interface.replace('/', '_').replace(':', '_')
        return self.state_dir / f"{device}_{safe_interface}.json"
    
    def _load_previous_state(self, device: str, interface: str) -> Optional[Dict]:
        """Load previous counter state."""
        state_file = self._get_state_file(device, interface)
        
        if not state_file.exists():
            return None
        
        try:
            with open(state_file, 'r') as f:
                return json.load(f)
        except (IOError, json.JSONDecodeError):
            return None
    
    def _save_current_state(self, device: str, interface: str, state: Dict):
        """Save current counter state."""
        state_file = self._get_state_file(device, interface)
        
        try:
            with open(state_file, 'w') as f:
                json.dump(state, f, indent=2)
        except IOError as e:
            print(f"Warning: Could not save state: {e}", file=sys.stderr)
    
    def calculate_throughput(self, interface_data: Dict) -> Dict:
        """
        Calculate throughput deltas for interface.
        
        Args:
            interface_data: Current interface metrics
        
        Returns:
            Interface data with added throughput delta fields
        """
        device = interface_data.get('device')
        if_name = interface_data.get('if_name')
        current_timestamp = interface_data.get('timestamp')
        
        # Load previous state
        prev_state = self._load_previous_state(device, if_name)
        
        # Prepare current state to save
        current_state = {
            'timestamp': current_timestamp,
            'collection_time': interface_data.get('collection_time'),
            # Note: Junos doesn't provide byte counters in traffic-statistics brief mode
            # We'll use the instantaneous rates as proxies
            'rx_bps': interface_data.get('rx_bps'),
            'tx_bps': interface_data.get('tx_bps'),
            'rx_pps': interface_data.get('rx_pps'),
            'tx_pps': interface_data.get('tx_pps'),
            # FEC counters for delta calculation
            'fec_ccw_count': interface_data.get('fec_ccw_count'),
            'fec_nccw_count': interface_data.get('fec_nccw_count'),
        }
        
        # Calculate deltas if we have previous state
        if prev_state and prev_state.get('timestamp'):
            time_delta_sec = (current_timestamp - prev_state['timestamp']) / 1_000_000
            
            if time_delta_sec > 0:
                # Calculate FEC error deltas (most important for ML)
                if (current_state.get('fec_ccw_count') is not None and 
                    prev_state.get('fec_ccw_count') is not None):
                    fec_ccw_delta = current_state['fec_ccw_count'] - prev_state['fec_ccw_count']
                    interface_data['fec_ccw_delta'] = fec_ccw_delta
                    interface_data['fec_ccw_rate'] = fec_ccw_delta / time_delta_sec
                
                if (current_state.get('fec_nccw_count') is not None and 
                    prev_state.get('fec_nccw_count') is not None):
                    fec_nccw_delta = current_state['fec_nccw_count'] - prev_state['fec_nccw_count']
                    interface_data['fec_nccw_delta'] = fec_nccw_delta
                    interface_data['fec_nccw_rate'] = fec_nccw_delta / time_delta_sec
                
                # Store time delta for reference
                interface_data['collection_interval_sec'] = time_delta_sec
        else:
            # First collection - no deltas available
            interface_data['fec_ccw_delta'] = None
            interface_data['fec_nccw_delta'] = None
            interface_data['fec_ccw_rate'] = None
            interface_data['fec_nccw_rate'] = None
            interface_data['collection_interval_sec'] = None
        
        # Save current state for next collection
        self._save_current_state(device, if_name, current_state)
        
        return interface_data


def process_metrics(input_file: str, output_file: str, state_dir: str):
    """
    Process metrics file and add throughput calculations.
    
    Args:
        input_file: Input JSON metrics file
        output_file: Output JSON file with added throughput metrics
        state_dir: Directory for state storage
    """
    # Load input metrics
    try:
        with open(input_file, 'r') as f:
            data = json.load(f)
    except (IOError, json.JSONDecodeError) as e:
        print(f"Error reading input file: {e}", file=sys.stderr)
        sys.exit(1)
    
    # Initialize calculator
    calculator = ThroughputCalculator(state_dir)
    
    # Process each interface
    if 'interfaces' in data:
        for i, interface in enumerate(data['interfaces']):
            data['interfaces'][i] = calculator.calculate_throughput(interface)
    
    # Write output
    try:
        with open(output_file, 'w') as f:
            json.dump(data, f, indent=2)
        
        interface_count = len(data.get('interfaces', []))
        print(f"Processed {interface_count} interfaces with throughput calculations")
    except IOError as e:
        print(f"Error writing output file: {e}", file=sys.stderr)
        sys.exit(1)


def main():
    parser = argparse.ArgumentParser(
        description='Calculate throughput deltas for interface metrics'
    )
    parser.add_argument('--input', required=True, help='Input JSON metrics file')
    parser.add_argument('--output', required=True, help='Output JSON file with throughput')
    parser.add_argument('--state-dir', required=True, help='Directory for state storage')
    
    args = parser.parse_args()
    
    process_metrics(args.input, args.output, args.state_dir)


if __name__ == '__main__':
    main()
