#!/usr/bin/env python3
"""
Collect PIC details for all FPC/PIC slots on a Junos device.
Uses chassis inventory to discover slots, then queries each one.
"""

import argparse
import json
import sys
from ncclient import manager
from parsers.juniper.pic_detail import parse_pic_detail, extract_fpc_pic_slots
from parsers.juniper.chassis_inventory import parse_chassis_inventory
from lxml import etree


def collect_pic_details(host: str, username: str, password: str, port: int, 
                        chassis_xml: str, platform_hint: str = None) -> dict:
    """
    Collect PIC details for all FPC/PIC slots.
    
    Args:
        host: Device hostname/IP
        username: NETCONF username
        password: NETCONF password
        port: NETCONF port
        chassis_xml: Chassis inventory XML to discover FPC/PIC slots
        platform_hint: Optional platform hint for interface naming
    
    Returns:
        Combined dictionary with all transceiver metadata
    """
    # Extract FPC/PIC slots from chassis inventory
    slots = extract_fpc_pic_slots(chassis_xml)
    
    if not slots:
        print("No FPC/PIC slots found in chassis inventory", file=sys.stderr)
        return {'device': host, 'transceivers': {}}
    
    print(f"Discovered {len(slots)} FPC/PIC slot(s): {slots}", file=sys.stderr)
    
    # Connect to device
    try:
        with manager.connect(
            host=host,
            port=port,
            username=username,
            password=password,
            hostkey_verify=False,
            device_params={'name': 'junos'},
            timeout=30
        ) as conn:
            
            all_transceivers = {}
            
            # Query each FPC/PIC
            for fpc, pic in slots:
                rpc_str = f'''
                <get-pic-detail>
                    <fpc-slot>{fpc}</fpc-slot>
                    <pic-slot>{pic}</pic-slot>
                </get-pic-detail>
                '''
                
                try:
                    rpc_elem = etree.fromstring(rpc_str)
                    response = conn.rpc(rpc_elem)
                    
                    # Convert NCElement to string - tostring is a property that returns bytes
                    xml_bytes = response.tostring
                    xml_str = xml_bytes.decode('utf-8') if isinstance(xml_bytes, bytes) else xml_bytes
                    
                    # Parse the response
                    result = parse_pic_detail(xml_str, host, fpc, pic, platform_hint)
                    
                    # Merge transceivers
                    all_transceivers.update(result['transceivers'])
                    
                    print(f"FPC {fpc} PIC {pic}: {len(result['transceivers'])} transceiver(s)", 
                          file=sys.stderr)
                    
                except Exception as e:
                    print(f"Error querying FPC {fpc} PIC {pic}: {e}", file=sys.stderr)
                    continue
            
            return {
                'device': host,
                'transceivers': all_transceivers
            }
            
    except Exception as e:
        print(f"Error connecting to device: {e}", file=sys.stderr)
        return {'device': host, 'transceivers': {}}


def main():
    parser = argparse.ArgumentParser(
        description='Collect PIC details from all FPC/PIC slots'
    )
    parser.add_argument('--host', required=True,
                        help='Device hostname or IP')
    parser.add_argument('--username', default='root',
                        help='NETCONF username')
    parser.add_argument('--password', required=True,
                        help='NETCONF password')
    parser.add_argument('--port', type=int, default=830,
                        help='NETCONF port')
    parser.add_argument('--chassis-xml', required=True,
                        help='Path to chassis inventory XML file')
    parser.add_argument('--output', required=True,
                        help='Path to output JSON file')
    parser.add_argument('--platform',
                        help='Platform hint for interface naming')
    
    args = parser.parse_args()
    
    # Read chassis XML
    try:
        with open(args.chassis_xml, 'r') as f:
            chassis_xml = f.read()
    except IOError as e:
        print(f"Error reading chassis XML: {e}", file=sys.stderr)
        sys.exit(1)
    
    # Collect PIC details
    result = collect_pic_details(
        args.host,
        args.username,
        args.password,
        args.port,
        chassis_xml,
        args.platform
    )
    
    # Write output
    try:
        with open(args.output, 'w') as f:
            json.dump(result, f, indent=2)
        
        print(f"Collected {len(result['transceivers'])} total transceiver(s)")
        
    except IOError as e:
        print(f"Error writing output: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == '__main__':
    main()
