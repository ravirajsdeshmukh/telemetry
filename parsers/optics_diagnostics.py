#!/usr/bin/env python3
"""
Parser for Junos get-interface-optics-diagnostics-information RPC output.
Converts optical interface metrics to JSON format.
"""

import argparse
import xml.etree.ElementTree as ET
import sys
import json
import time
from typing import Dict, List, Optional


def strip_namespace(tag):
    """Remove namespace from XML tag."""
    return tag.split('}', 1)[1] if '}' in tag else tag


def findall_ns(element, tag):
    """Find all child elements with tag, ignoring namespace."""
    return [child for child in element if strip_namespace(child.tag) == tag]


def find_ns(element, tag):
    """Find first child element with tag, ignoring namespace."""
    result = findall_ns(element, tag)
    return result[0] if result else None


def findtext_ns(element, tag, default=None):
    """Find text of child element with tag, ignoring namespace."""
    child = find_ns(element, tag)
    return child.text if child is not None and child.text else default


def findall_recursive_ns(element, tag):
    """Find all descendant elements with tag, ignoring namespace."""
    results = []
    for child in element.iter():
        if strip_namespace(child.tag) == tag:
            results.append(child)
    return results


def extract_numeric_value(text: Optional[str]) -> Optional[float]:
    """Extract numeric value from text, handling units."""
    if not text:
        return None
    try:
        # Split on space and take the first part
        value = text.split()[0]
        return float(value)
    except (ValueError, IndexError, AttributeError):
        return None


def parse_interface_metrics(phys_interface: ET.Element, device: str, 
                            additional_metadata: Dict = None) -> Optional[Dict]:
    """
    Parse interface-level metrics (thresholds).
    
    Args:
        phys_interface: physical-interface XML element
        device: Device hostname/IP
        additional_metadata: Additional metadata to include in output
    
    Returns:
        Dictionary with interface metrics or None if not available
    """
    interface_name = findtext_ns(phys_interface, 'name', 'unknown')
    optics_diag = find_ns(phys_interface, 'optics-diagnostics')
    
    if optics_diag is None:
        return None
    
    # Check if diagnostics are not available
    if find_ns(optics_diag, 'optic-diagnostics-not-available') is not None:
        return None
    
    metrics = {
        'if_name': interface_name,
        'device': device,
        'timestamp': int(time.time() * 1000000)  # microseconds
    }
    
    # Temperature thresholds
    metrics['temperature_high_alarm'] = extract_numeric_value(
        findtext_ns(optics_diag, 'laser-temperature-high-alarm-threshold'))
    metrics['temperature_low_alarm'] = extract_numeric_value(
        findtext_ns(optics_diag, 'laser-temperature-low-alarm-threshold'))
    metrics['temperature_high_warn'] = extract_numeric_value(
        findtext_ns(optics_diag, 'laser-temperature-high-warn-threshold'))
    metrics['temperature_low_warn'] = extract_numeric_value(
        findtext_ns(optics_diag, 'laser-temperature-low-warn-threshold'))
    
    # Voltage thresholds
    metrics['voltage_high_alarm'] = extract_numeric_value(
        findtext_ns(optics_diag, 'module-voltage-high-alarm-threshold'))
    metrics['voltage_low_alarm'] = extract_numeric_value(
        findtext_ns(optics_diag, 'module-voltage-low-alarm-threshold'))
    metrics['voltage_high_warn'] = extract_numeric_value(
        findtext_ns(optics_diag, 'module-voltage-high-warn-threshold'))
    metrics['voltage_low_warn'] = extract_numeric_value(
        findtext_ns(optics_diag, 'module-voltage-low-warn-threshold'))
    
    # TX power thresholds
    metrics['tx_power_high_alarm'] = extract_numeric_value(
        findtext_ns(optics_diag, 'laser-tx-power-high-alarm-threshold-dbm'))
    metrics['tx_power_low_alarm'] = extract_numeric_value(
        findtext_ns(optics_diag, 'laser-tx-power-low-alarm-threshold-dbm'))
    metrics['tx_power_high_warn'] = extract_numeric_value(
        findtext_ns(optics_diag, 'laser-tx-power-high-warn-threshold-dbm'))
    metrics['tx_power_low_warn'] = extract_numeric_value(
        findtext_ns(optics_diag, 'laser-tx-power-low-warn-threshold-dbm'))
    
    # RX power thresholds
    metrics['rx_power_high_alarm'] = extract_numeric_value(
        findtext_ns(optics_diag, 'laser-rx-power-high-alarm-threshold-dbm'))
    metrics['rx_power_low_alarm'] = extract_numeric_value(
        findtext_ns(optics_diag, 'laser-rx-power-low-alarm-threshold-dbm'))
    metrics['rx_power_high_warn'] = extract_numeric_value(
        findtext_ns(optics_diag, 'laser-rx-power-high-warn-threshold-dbm'))
    metrics['rx_power_low_warn'] = extract_numeric_value(
        findtext_ns(optics_diag, 'laser-rx-power-low-warn-threshold-dbm'))
    
    # TX bias current thresholds
    metrics['tx_bias_high_alarm'] = extract_numeric_value(
        findtext_ns(optics_diag, 'laser-bias-current-high-alarm-threshold'))
    metrics['tx_bias_low_alarm'] = extract_numeric_value(
        findtext_ns(optics_diag, 'laser-bias-current-low-alarm-threshold'))
    metrics['tx_bias_high_warn'] = extract_numeric_value(
        findtext_ns(optics_diag, 'laser-bias-current-high-warn-threshold'))
    metrics['tx_bias_low_warn'] = extract_numeric_value(
        findtext_ns(optics_diag, 'laser-bias-current-low-warn-threshold'))
    
    # Current measured values
    # Temperature - extract from junos:celsius attribute
    temp_element = find_ns(optics_diag, 'module-temperature')
    if temp_element is not None:
        # Try to get from attribute first (most accurate)
        temp_celsius = temp_element.get('{http://xml.juniper.net/junos/26.2I20251216150948-vchintada-1/junos}celsius')
        if not temp_celsius:
            # Try without full namespace
            for attr_name in temp_element.attrib:
                if 'celsius' in attr_name.lower():
                    temp_celsius = temp_element.attrib[attr_name]
                    break
        metrics['temperature'] = extract_numeric_value(temp_celsius) if temp_celsius else None
    else:
        metrics['temperature'] = None
    
    # Voltage - extract from text content
    metrics['voltage'] = extract_numeric_value(
        findtext_ns(optics_diag, 'module-voltage'))
    
    # Add additional metadata if provided
    if additional_metadata:
        metrics.update(additional_metadata)
    
    return metrics


def parse_lane_metrics(phys_interface: ET.Element, device: str,
                       additional_metadata: Dict = None) -> List[Dict]:
    """
    Parse lane-level metrics.
    
    Args:
        phys_interface: physical-interface XML element
        device: Device hostname/IP
        additional_metadata: Additional metadata to include in output
    
    Returns:
        List of dictionaries with lane metrics
    """
    interface_name = findtext_ns(phys_interface, 'name', 'unknown')
    optics_diag = find_ns(phys_interface, 'optics-diagnostics')
    
    if optics_diag is None:
        return []
    
    # Check if diagnostics are not available
    if find_ns(optics_diag, 'optic-diagnostics-not-available') is not None:
        return []
    
    lane_metrics_list = []
    
    for lane in findall_recursive_ns(optics_diag, 'optics-diagnostics-lane-values'):
        lane_index = findtext_ns(lane, 'lane-index', '0')
        
        metrics = {
            'if_name': interface_name,
            'device': device,
            'lane': int(lane_index),
            'timestamp': int(time.time() * 1000000)  # microseconds
        }
        
        # RX power (mW)
        metrics['rx_power_mw'] = extract_numeric_value(
            findtext_ns(lane, 'laser-rx-optical-power'))
        
        # RX power (dBm)
        metrics['rx_power'] = extract_numeric_value(
            findtext_ns(lane, 'laser-rx-optical-power-dbm'))
        
        # TX power (mW)
        metrics['tx_power_mw'] = extract_numeric_value(
            findtext_ns(lane, 'laser-output-power'))
        
        # TX power (dBm)
        metrics['tx_power'] = extract_numeric_value(
            findtext_ns(lane, 'laser-output-power-dbm'))
        
        # TX bias current
        metrics['tx_bias'] = extract_numeric_value(
            findtext_ns(lane, 'laser-bias-current'))
        
        # Add additional metadata if provided
        if additional_metadata:
            metrics.update(additional_metadata)
        
        lane_metrics_list.append(metrics)
    
    return lane_metrics_list


def parse_optical_diagnostics(xml_content: str, device: str,
                              additional_metadata: Dict = None) -> Dict:
    """
    Parse optical diagnostics XML and convert to JSON format.
    
    Args:
        xml_content: XML string from RPC response
        device: Device hostname/IP
        additional_metadata: Additional metadata to include in output
    
    Returns:
        Dictionary with 'interfaces' and 'lanes' arrays
    """
    try:
        root = ET.fromstring(xml_content)
    except ET.ParseError as e:
        print(f"Error parsing XML: {e}", file=sys.stderr)
        return {'interfaces': [], 'lanes': []}
    
    interface_metrics = []
    lane_metrics = []
    
    # Find all physical interfaces (namespace-agnostic)
    for phys_interface in findall_recursive_ns(root, 'physical-interface'):
        # Parse interface-level metrics
        interface_data = parse_interface_metrics(phys_interface, device, additional_metadata)
        if interface_data:
            interface_metrics.append(interface_data)
        
        # Parse lane-level metrics
        lanes_data = parse_lane_metrics(phys_interface, device, additional_metadata)
        lane_metrics.extend(lanes_data)
    
    return {
        'interfaces': interface_metrics,
        'lanes': lane_metrics
    }


def main():
    parser = argparse.ArgumentParser(
        description='Parse Junos optical diagnostics to JSON format'
    )
    parser.add_argument('--input', required=True, help='Input XML file')
    parser.add_argument('--output', required=True, help='Output JSON metrics file')
    parser.add_argument('--device', required=True, help='Device hostname/IP')
    parser.add_argument('--metadata', type=str, help='Additional metadata as JSON string')
    parser.add_argument('--format', choices=['json', 'jsonl'], default='json',
                       help='Output format: json (single JSON object) or jsonl (JSON Lines)')
    
    args = parser.parse_args()
    
    # Parse additional metadata if provided
    additional_metadata = None
    if args.metadata:
        try:
            additional_metadata = json.loads(args.metadata)
        except json.JSONDecodeError as e:
            print(f"Error parsing metadata JSON: {e}", file=sys.stderr)
            sys.exit(1)
    
    # Read input XML
    try:
        with open(args.input, 'r') as f:
            xml_content = f.read()
    except IOError as e:
        print(f"Error reading input file: {e}", file=sys.stderr)
        sys.exit(1)
    
    # Parse and convert to metrics
    result = parse_optical_diagnostics(xml_content, args.device, additional_metadata)
    
    interface_count = len(result['interfaces'])
    lane_count = len(result['lanes'])
    
    if interface_count == 0 and lane_count == 0:
        print("Warning: No metrics generated", file=sys.stderr)
    
    # Write output
    try:
        with open(args.output, 'w') as f:
            if args.format == 'json':
                json.dump(result, f, indent=2)
            else:  # jsonl
                # Write each lane metric as a separate JSON line
                for lane_metric in result['lanes']:
                    f.write(json.dumps(lane_metric) + '\n')
        
        print(f"Generated {interface_count} interface metrics and {lane_count} lane metrics")
    except IOError as e:
        print(f"Error writing output file: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == '__main__':
    main()
