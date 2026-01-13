#!/usr/bin/env python3
"""
Merge metadata from system_information and chassis_inventory into optics_diagnostics metrics.
Combines device-level metadata (hostname, model, serial) and transceiver metadata
(vendor, part number, serial number, fiber type) with optical diagnostics data.
"""

import argparse
import json
import sys
from typing import Dict, Optional
import os

# Add parent directory to path for imports
# sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from parsers.common.interface_mapping import parse_interface_base_name


def merge_metadata(system_info: Dict, chassis_inv: Dict, optics_metrics: Dict, pic_detail: Optional[Dict] = None) -> Dict:
    """
    Merge device and transceiver metadata into optics metrics.
    
    Args:
        system_info: System information (hostname, model, OS)
        chassis_inv: Chassis inventory (device serial, transceiver metadata)
        optics_metrics: Optics diagnostics metrics
        pic_detail: Optional PIC detail (detailed vendor information from get-pic-detail)
    
    Returns:
        Updated optics metrics with merged metadata
    """
    # Extract system-level metadata
    origin_hostname = system_info.get('origin_hostname')
    device_profile = system_info.get('device_profile')
    origin_name = chassis_inv.get('origin_name')  # Device serial number
    transceivers = chassis_inv.get('transceivers', {})
    
    # Get PIC detail transceivers (higher priority for vendor info)
    pic_transceivers = pic_detail.get('transceivers', {}) if pic_detail else {}
    
    # Update interface metrics
    for interface in optics_metrics.get('interfaces', []):
        if_name = interface.get('if_name')
        
        # Add device-level metadata
        if origin_hostname:
            interface['origin_hostname'] = origin_hostname
        if device_profile:
            interface['device_profile'] = device_profile
        if origin_name:
            interface['origin_name'] = origin_name
        
        # Add transceiver metadata
        # Extract base interface name (remove :N suffix for channelized interfaces)
        base_if_name = parse_interface_base_name(if_name) if if_name else None
        
        if base_if_name:
            # First, try chassis inventory for basic metadata
            if base_if_name in transceivers:
                xcvr_data = transceivers[base_if_name]
                if xcvr_data.get('part_number'):
                    interface['part_number'] = xcvr_data['part_number']
                if xcvr_data.get('serial_number'):
                    interface['serial_number'] = xcvr_data['serial_number']
                # Use chassis data as fallback for vendor and media_type
                if xcvr_data.get('vendor'):
                    interface['vendor'] = xcvr_data['vendor']
                if xcvr_data.get('media_type'):
                    interface['media_type'] = xcvr_data['media_type']
                if xcvr_data.get('fiber_type'):
                    interface['fiber_type'] = xcvr_data['fiber_type']
            
            # Then, override with PIC detail data if available (more detailed)
            if base_if_name in pic_transceivers:
                pic_data = pic_transceivers[base_if_name]
                # PIC detail has priority for vendor info
                if pic_data.get('vendor'):
                    interface['vendor'] = pic_data['vendor']
                if pic_data.get('part_number'):
                    interface['part_number'] = pic_data['part_number']
                if pic_data.get('cable_type'):
                    interface['cable_type'] = pic_data['cable_type']
                if pic_data.get('media_type'):
                    interface['media_type'] = pic_data['media_type']
                if pic_data.get('wavelength'):
                    interface['wavelength'] = pic_data['wavelength']
                if pic_data.get('fiber_type'):
                    interface['fiber_type'] = pic_data['fiber_type']
                if pic_data.get('firmware_version'):
                    interface['firmware_version'] = pic_data['firmware_version']
    
    # Update lane metrics
    for lane in optics_metrics.get('lanes', []):
        if_name = lane.get('if_name')
        
        # Add device-level metadata
        if origin_hostname:
            lane['origin_hostname'] = origin_hostname
        if device_profile:
            lane['device_profile'] = device_profile
        if origin_name:
            lane['origin_name'] = origin_name
        
        # Add transceiver metadata
        base_if_name = parse_interface_base_name(if_name) if if_name else None
        
        if base_if_name:
            # First, try chassis inventory for basic metadata
            if base_if_name in transceivers:
                xcvr_data = transceivers[base_if_name]
                if xcvr_data.get('part_number'):
                    lane['part_number'] = xcvr_data['part_number']
                if xcvr_data.get('serial_number'):
                    lane['serial_number'] = xcvr_data['serial_number']
                # Use chassis data as fallback
                if xcvr_data.get('vendor'):
                    lane['vendor'] = xcvr_data['vendor']
                if xcvr_data.get('media_type'):
                    lane['media_type'] = xcvr_data['media_type']
                if xcvr_data.get('fiber_type'):
                    lane['fiber_type'] = xcvr_data['fiber_type']
            
            # Then, override with PIC detail data if available (more detailed)
            if base_if_name in pic_transceivers:
                pic_data = pic_transceivers[base_if_name]
                # PIC detail has priority for vendor info
                if pic_data.get('vendor'):
                    lane['vendor'] = pic_data['vendor']
                if pic_data.get('part_number'):
                    lane['part_number'] = pic_data['part_number']
                if pic_data.get('cable_type'):
                    lane['cable_type'] = pic_data['cable_type']
                if pic_data.get('media_type'):
                    lane['media_type'] = pic_data['media_type']
                if pic_data.get('wavelength'):
                    lane['wavelength'] = pic_data['wavelength']
                if pic_data.get('fiber_type'):
                    lane['fiber_type'] = pic_data['fiber_type']
                if pic_data.get('firmware_version'):
                    lane['firmware_version'] = pic_data['firmware_version']
    
    return optics_metrics


def main():
    parser = argparse.ArgumentParser(
        description='Merge metadata from system info and chassis inventory into optics metrics'
    )
    parser.add_argument('--system-info', required=True, help='System information JSON file')
    parser.add_argument('--chassis-inventory', required=True, help='Chassis inventory JSON file')
    parser.add_argument('--pic-detail', help='PIC detail JSON file (optional, for detailed vendor info)')
    parser.add_argument('--optics-metrics', required=True, help='Optics diagnostics metrics JSON file')
    parser.add_argument('--output', required=True, help='Output JSON file')
    
    args = parser.parse_args()
    
    # Load system information
    try:
        with open(args.system_info, 'r') as f:
            system_info = json.load(f)
    except (IOError, json.JSONDecodeError) as e:
        print(f"Warning: Error loading system information: {e}", file=sys.stderr)
        system_info = {}
    
    # Load chassis inventory
    try:
        with open(args.chassis_inventory, 'r') as f:
            chassis_inv = json.load(f)
    except (IOError, json.JSONDecodeError) as e:
        print(f"Warning: Error loading chassis inventory: {e}", file=sys.stderr)
        chassis_inv = {}
    
    # Load PIC detail (optional)
    pic_detail = None
    if args.pic_detail:
        try:
            with open(args.pic_detail, 'r') as f:
                pic_detail = json.load(f)
        except (IOError, json.JSONDecodeError) as e:
            print(f"Warning: Error loading PIC detail: {e}", file=sys.stderr)
            pic_detail = None
    
    # Load optics metrics
    try:
        with open(args.optics_metrics, 'r') as f:
            optics_metrics = json.load(f)
    except (IOError, json.JSONDecodeError) as e:
        print(f"Error loading optics metrics: {e}", file=sys.stderr)
        sys.exit(1)
    
    # Merge metadata
    merged_metrics = merge_metadata(system_info, chassis_inv, optics_metrics, pic_detail)
    
    # Write output
    try:
        with open(args.output, 'w') as f:
            json.dump(merged_metrics, f, indent=2)
        
        interface_count = len(merged_metrics.get('interfaces', []))
        lane_count = len(merged_metrics.get('lanes', []))
        print(f"Merged metadata into {interface_count} interface(s) and {lane_count} lane(s)")
    except IOError as e:
        print(f"Error writing output file: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == '__main__':
    main()
