#!/usr/bin/env python3
"""
Generic parser template for Junos RPC commands.
Copy this file and customize for different RPC outputs.
"""

import argparse
import xml.etree.ElementTree as ET
import sys
from typing import List


def parse_rpc_output(xml_content: str, device: str) -> List[str]:
    """
    Parse RPC XML output and convert to Prometheus metrics.
    
    Args:
        xml_content: XML string from RPC response
        device: Device hostname/IP
    
    Returns:
        List of Prometheus metric lines
    """
    metrics = []
    
    try:
        root = ET.fromstring(xml_content)
    except ET.ParseError as e:
        print(f"Error parsing XML: {e}", file=sys.stderr)
        return []
    
    # TODO: Customize this section based on your RPC output structure
    # Example:
    # for element in root.findall('.//your-element'):
    #     name = element.findtext('name', 'unknown')
    #     value = element.findtext('value', '0')
    #     
    #     labels = f'device="{device}",element_name="{name}"'
    #     metrics.append(f'junos_custom_metric{{{labels}}} {value}')
    
    return metrics


def main():
    parser = argparse.ArgumentParser(
        description='Parse Junos RPC output to Prometheus format'
    )
    parser.add_argument('--input', required=True, help='Input XML file')
    parser.add_argument('--output', required=True, help='Output Prometheus metrics file')
    parser.add_argument('--device', required=True, help='Device hostname/IP')
    
    args = parser.parse_args()
    
    # Read input XML
    try:
        with open(args.input, 'r') as f:
            xml_content = f.read()
    except IOError as e:
        print(f"Error reading input file: {e}", file=sys.stderr)
        sys.exit(1)
    
    # Parse and convert to metrics
    metrics = parse_rpc_output(xml_content, args.device)
    
    if not metrics:
        print("Warning: No metrics generated", file=sys.stderr)
    
    # Write output
    try:
        with open(args.output, 'w') as f:
            f.write('\n'.join(metrics))
            if metrics:
                f.write('\n')
        print(f"Generated {len(metrics)} metrics")
    except IOError as e:
        print(f"Error writing output file: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == '__main__':
    main()
