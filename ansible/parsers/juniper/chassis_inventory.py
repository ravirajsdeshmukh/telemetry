#!/usr/bin/env python3
"""
Parser for Junos get-chassis-inventory RPC output.
Extracts device serial number and transceiver metadata.

CLI Equivalent: show chassis hardware
RPC: <get-chassis-inventory/>
"""

import argparse
import xml.etree.ElementTree as ET
import sys
import json
import re
from typing import Dict, Optional
import os

# Add parent directory to path for imports
# sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from parsers.common.xml_utils import strip_namespace, findtext_ns, findall_ns, findall_recursive_ns
from parsers.common.interface_mapping import parse_juniper_interface_name, extract_fpc_pic_port


def parse_chassis_inventory(xml_content: str, device: str, platform_hint: Optional[str] = None) -> Dict:
    """
    Parse chassis inventory XML to extract device serial and identify FPC/PIC structure.
    
    NOTE: This parser ONLY extracts FPC/PIC information for interface naming.
    All transceiver metadata (vendor, part_number, serial_number, media_type, fiber_type, wavelength)
    MUST come from PIC detail command (show chassis pic fpc-slot X pic-slot Y).
    
    Args:
        xml_content: XML string from get-chassis-inventory RPC response
        device: Device hostname/IP
        platform_hint: Optional platform identifier for interface name mapping
    
    Returns:
        Dictionary with:
        - device: Device identifier
        - origin_name: Device serial number
        - transceivers: Dict mapping interface names (for structure only, no metadata)
    """
    try:
        root = ET.fromstring(xml_content)
    except ET.ParseError as e:
        print(f"Error parsing XML: {e}", file=sys.stderr)
        return {'device': device, 'origin_name': None, 'transceivers': {}}
    
    result = {
        'device': device,
        'origin_name': None,  # Device serial number
        'transceivers': {}     # Interface name -> transceiver metadata
    }
    
    # Find chassis element to get device serial number
    for chassis in findall_recursive_ns(root, 'chassis'):
        serial_number = findtext_ns(chassis, 'serial-number')
        if serial_number:
            result['origin_name'] = serial_number
            break
    
    # Find all FPC modules
    for fpc_elem in findall_recursive_ns(root, 'chassis-module'):
        module_name = findtext_ns(fpc_elem, 'name', '')
        
        # Skip if not an FPC
        if not module_name.startswith('FPC'):
            continue
        
        # Extract FPC number
        fpc_info = extract_fpc_pic_port(module_name)
        if not fpc_info or fpc_info['type'] != 'fpc':
            continue
        fpc_num = fpc_info['number']
        
        # Find all PICs within this FPC
        for pic_elem in findall_ns(fpc_elem, 'chassis-sub-module'):
            pic_name = findtext_ns(pic_elem, 'name', '')
            
            # Skip if not a PIC
            if not pic_name.startswith('PIC'):
                continue
            
            # Extract PIC number
            pic_info = extract_fpc_pic_port(pic_name)
            if not pic_info or pic_info['type'] != 'pic':
                continue
            pic_num = pic_info['number']
            
            # Find all transceivers (Xcvr) within this PIC
            for xcvr_elem in findall_ns(pic_elem, 'chassis-sub-sub-module'):
                xcvr_name = findtext_ns(xcvr_elem, 'name', '')
                
                # Skip if not a transceiver
                if not xcvr_name.startswith('Xcvr'):
                    continue
                
                # Extract Xcvr number
                xcvr_info = extract_fpc_pic_port(xcvr_name)
                if not xcvr_info or xcvr_info['type'] != 'port':
                    continue
                xcvr_num = xcvr_info['number']
                
                # Map to interface name
                interface_name = parse_juniper_interface_name(
                    fpc_num, pic_num, xcvr_num, platform_hint
                )
                
                # Only track that this interface exists (no metadata)
                # All transceiver metadata comes from PIC detail command
                if interface_name:
                    result['transceivers'][interface_name] = {}
    
    return result


def main():
    parser = argparse.ArgumentParser(
        description='Parse Junos chassis inventory to JSON format'
    )
    parser.add_argument('--input', required=True, help='Input XML file')
    parser.add_argument('--output', required=True, help='Output JSON file')
    parser.add_argument('--device', required=True, help='Device hostname/IP')
    parser.add_argument('--platform', help='Platform hint for interface mapping (e.g., qfx5240)')
    parser.add_argument('--format', default='json', choices=['json'],
                        help='Output format (only json supported)')
    
    args = parser.parse_args()
    
    # Read input XML
    try:
        with open(args.input, 'r') as f:
            xml_content = f.read()
    except IOError as e:
        print(f"Error reading input file: {e}", file=sys.stderr)
        sys.exit(1)
    
    # Parse chassis inventory
    result = parse_chassis_inventory(xml_content, args.device, args.platform)
    
    # Write output
    try:
        with open(args.output, 'w') as f:
            json.dump(result, f, indent=2)
        
        transceiver_count = len(result['transceivers'])
        origin_name = result.get('origin_name', 'Not found')
        print(f"Extracted {transceiver_count} transceiver(s), device serial: {origin_name}")
    except IOError as e:
        print(f"Error writing output file: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == '__main__':
    main()
