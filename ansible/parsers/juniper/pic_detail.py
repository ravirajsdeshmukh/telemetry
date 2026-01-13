#!/usr/bin/env python3
"""
Parser for Junos get-pic-detail RPC output.
Extracts detailed transceiver vendor information including fiber mode, cable type, and wavelength.

CLI Equivalent: show pic fpc-slot {fpc} pic-slot {pic}
RPC: <get-pic-detail><fpc-slot>{fpc}</fpc-slot><pic-slot>{pic}</pic-slot></get-pic-detail>
"""

import argparse
import xml.etree.ElementTree as ET
import sys
import json
from typing import Dict, Optional
import os
from lxml import etree as lxml_etree

from parsers.common.xml_utils import strip_namespace, findtext_ns, findall_ns, findall_recursive_ns
from parsers.common.interface_mapping import parse_juniper_interface_name


def parse_fiber_mode(fiber_mode: Optional[str]) -> Optional[str]:
    """
    Convert fiber-mode from PIC detail to standardized fiber_type.
    
    Args:
        fiber_mode: Fiber mode from XML (e.g., "Multi Mode", "Single Mode", "n/a")
    
    Returns:
        Standardized fiber type or None
    """
    if not fiber_mode or fiber_mode.lower() in ['n/a', 'na', 'none', '']:
        return None
    
    fiber_mode_lower = fiber_mode.lower()
    if 'multi' in fiber_mode_lower or 'mm' in fiber_mode_lower:
        return 'FIBER_TYPE_MULTI_MODE'
    elif 'single' in fiber_mode_lower or 'sm' in fiber_mode_lower:
        return 'FIBER_TYPE_SINGLE_MODE'
    
    return None


def parse_pic_detail(xml_content, device: str, fpc: int, pic: int, 
                     platform_hint: Optional[str] = None) -> Dict:
    """
    Parse PIC detail XML and extract transceiver metadata.
    
    Args:
        xml_content: XML string or lxml element from get-pic-detail RPC response
        device: Device hostname/IP
        fpc: FPC slot number
        pic: PIC slot number
        platform_hint: Optional platform identifier for interface name mapping
    
    Returns:
        Dictionary with:
        - device: Device identifier
        - fpc: FPC slot
        - pic: PIC slot
        - transceivers: Dict mapping interface names to detailed transceiver metadata
    """
    try:
        # Convert lxml element to string if needed
        if hasattr(xml_content, 'tag'):  # It's an lxml or ET element
            try:
                from lxml import etree as lxml_etree
                if isinstance(xml_content, lxml_etree._Element):
                    xml_content = lxml_etree.tostring(xml_content, encoding='unicode')
            except (ImportError, AttributeError):
                pass
        
        # Now parse as string
        if isinstance(xml_content, str):
            root = ET.fromstring(xml_content)
        else:
            # Last resort, try to use it directly
            root = xml_content
    except (ET.ParseError, Exception) as e:
        print(f"Error parsing XML: {e}", file=sys.stderr)
        return {'device': device, 'fpc': fpc, 'pic': pic, 'transceivers': {}}
    
    result = {
        'device': device,
        'fpc': fpc,
        'pic': pic,
        'transceivers': {}  # Interface name -> transceiver metadata
    }
    
    # Find all port elements
    for port_elem in findall_recursive_ns(root, 'port'):
        port_number = findtext_ns(port_elem, 'port-number')
        if not port_number:
            continue
        
        # Build interface name
        interface_name = parse_juniper_interface_name(
            str(fpc), str(pic), port_number, platform_hint
        )
        
        if not interface_name:
            continue
        
        # Extract transceiver metadata
        cable_type = findtext_ns(port_elem, 'cable-type')
        fiber_mode = findtext_ns(port_elem, 'fiber-mode')
        vendor_name = findtext_ns(port_elem, 'sfp-vendor-name')
        vendor_pno = findtext_ns(port_elem, 'sfp-vendor-pno')
        wavelength = findtext_ns(port_elem, 'wavelength')
        vendor_fw = findtext_ns(port_elem, 'sfp-vendor-fw-ver')
        jnpr_ver = findtext_ns(port_elem, 'sfp-jnpr-ver')
        
        # Build transceiver metadata dictionary
        transceiver = {}
        
        if vendor_name and vendor_name.lower() not in ['n/a', 'na', 'none', '']:
            transceiver['vendor'] = vendor_name
        
        if vendor_pno and vendor_pno.lower() not in ['n/a', 'na', 'none', '']:
            transceiver['part_number'] = vendor_pno
        
        if cable_type and cable_type.lower() not in ['n/a', 'na', 'none', '']:
            transceiver['cable_type'] = cable_type
            # Also use as media_type if not already set
            if 'media_type' not in transceiver:
                transceiver['media_type'] = cable_type
        
        if wavelength and wavelength.lower() not in ['n/a', 'na', 'none', '']:
            transceiver['wavelength'] = wavelength
        
        # Convert fiber_mode to standardized fiber_type
        fiber_type = parse_fiber_mode(fiber_mode)
        if fiber_type:
            transceiver['fiber_type'] = fiber_type
        
        # Store firmware versions if available
        if vendor_fw and vendor_fw.lower() not in ['n/a', 'na', 'none', '', '0.0']:
            transceiver['firmware_version'] = vendor_fw
        
        if jnpr_ver and jnpr_ver.lower() not in ['n/a', 'na', 'none', '']:
            transceiver['juniper_version'] = jnpr_ver
        
        # Only add if we have at least some metadata
        if transceiver:
            result['transceivers'][interface_name] = transceiver
    
    return result


def extract_fpc_pic_slots(chassis_xml: str) -> list:
    """
    Extract FPC and PIC slots from chassis hardware output.
    
    Args:
        chassis_xml: XML string from get-chassis-inventory RPC response
    
    Returns:
        List of (fpc, pic) tuples
    """
    try:
        root = ET.fromstring(chassis_xml)
    except ET.ParseError as e:
        print(f"Error parsing chassis XML: {e}", file=sys.stderr)
        return []
    
    slots = []
    
    # Find all chassis modules (FPCs)
    for module in findall_recursive_ns(root, 'chassis-module'):
        module_name = findtext_ns(module, 'name', '')
        
        # Check if this is an FPC
        if 'FPC' in module_name:
            # Extract FPC number
            import re
            fpc_match = re.search(r'FPC\s+(\d+)', module_name, re.IGNORECASE)
            if not fpc_match:
                continue
            fpc_num = int(fpc_match.group(1))
            
            # Find all sub-modules (PICs)
            for sub_module in findall_ns(module, 'chassis-sub-module'):
                sub_name = findtext_ns(sub_module, 'name', '')
                
                if 'PIC' in sub_name:
                    # Extract PIC number
                    pic_match = re.search(r'PIC\s+(\d+)', sub_name, re.IGNORECASE)
                    if pic_match:
                        pic_num = int(pic_match.group(1))
                        slots.append((fpc_num, pic_num))
    
    return slots


def main():
    parser = argparse.ArgumentParser(
        description='Parse Junos get-pic-detail RPC output for transceiver metadata'
    )
    parser.add_argument('--input', required=True,
                        help='Path to XML file from get-pic-detail RPC')
    parser.add_argument('--output', required=True,
                        help='Path to output JSON file')
    parser.add_argument('--device', required=True,
                        help='Device hostname or IP')
    parser.add_argument('--fpc', type=int, required=True,
                        help='FPC slot number')
    parser.add_argument('--pic', type=int, required=True,
                        help='PIC slot number')
    parser.add_argument('--platform', 
                        help='Platform hint for interface naming (e.g., qfx5240)')
    parser.add_argument('--chassis-xml',
                        help='Path to chassis inventory XML to auto-discover FPC/PIC slots')
    
    args = parser.parse_args()
    
    # If chassis-xml provided, extract all FPC/PIC slots
    if args.chassis_xml:
        with open(args.chassis_xml, 'r') as f:
            chassis_xml = f.read()
        slots = extract_fpc_pic_slots(chassis_xml)
        print(f"Discovered FPC/PIC slots: {slots}", file=sys.stderr)
    
    # Read input XML
    try:
        with open(args.input, 'r') as f:
            xml_content = f.read()
    except IOError as e:
        print(f"Error reading input file: {e}", file=sys.stderr)
        sys.exit(1)
    
    # Parse XML
    result = parse_pic_detail(
        xml_content, 
        args.device, 
        args.fpc, 
        args.pic,
        args.platform
    )
    
    # Write output JSON
    try:
        with open(args.output, 'w') as f:
            json.dump(result, f, indent=2)
        
        transceiver_count = len(result['transceivers'])
        print(f"Extracted {transceiver_count} transceiver(s) from FPC {args.fpc} PIC {args.pic}")
        
    except IOError as e:
        print(f"Error writing output file: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == '__main__':
    main()
