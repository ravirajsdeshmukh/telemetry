#!/usr/bin/env python3
"""
Parser for Junos get-system-information RPC output.
Extracts hostname, model, and OS information.

CLI Equivalent: show system information
RPC: <get-system-information/>
"""

import argparse
import xml.etree.ElementTree as ET
import sys
import json
from typing import Dict
import os

# Add parent directory to path for imports
# sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from parsers.common.xml_utils import strip_namespace, findtext_ns


def parse_system_information(xml_content: str, device: str) -> Dict:
    """
    Parse system information XML and extract device metadata.
    
    Args:
        xml_content: XML string from get-system-information RPC response
        device: Device hostname/IP
    
    Returns:
        Dictionary with system information containing:
        - origin_hostname: Device hostname
        - device_profile: Formatted as "Juniper_{model}"
        - hardware_model: Raw hardware model
        - os_name: Operating system name
        - os_version: Operating system version
    """
    try:
        root = ET.fromstring(xml_content)
    except ET.ParseError as e:
        print(f"Error parsing XML: {e}", file=sys.stderr)
        return {'device': device}
    
    # Find system-information element
    sys_info = None
    for elem in root.iter():
        if strip_namespace(elem.tag) == 'system-information':
            sys_info = elem
            break
    
    if sys_info is None:
        print("Warning: No system-information element found", file=sys.stderr)
        return {'device': device}
    
    result = {
        'device': device,
        'origin_hostname': findtext_ns(sys_info, 'host-name', device),
        'hardware_model': findtext_ns(sys_info, 'hardware-model'),
        'os_name': findtext_ns(sys_info, 'os-name'),
        'os_version': findtext_ns(sys_info, 'os-version'),
    }
    
    # Format device_profile as "Juniper_{model}"
    if result['hardware_model']:
        result['device_profile'] = f"Juniper_{result['hardware_model']}"
    else:
        result['device_profile'] = None
    
    return result


def main():
    parser = argparse.ArgumentParser(
        description='Parse Junos system information to JSON format'
    )
    parser.add_argument('--input', required=True, help='Input XML file')
    parser.add_argument('--output', required=True, help='Output JSON file')
    parser.add_argument('--device', required=True, help='Device hostname/IP')
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
    
    # Parse system information
    result = parse_system_information(xml_content, args.device)
    
    # Write output
    try:
        with open(args.output, 'w') as f:
            json.dump(result, f, indent=2)
        
        hostname = result.get('origin_hostname', 'unknown')
        model = result.get('device_profile', 'unknown')
        print(f"Extracted system information: {hostname} ({model})")
    except IOError as e:
        print(f"Error writing output file: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == '__main__':
    main()
