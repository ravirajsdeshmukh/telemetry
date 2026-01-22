#!/usr/bin/env python3
"""
Parser for Juniper interface FEC statistics.

Extracts FEC (Forward Error Correction) statistics from get-interface-information RPC output
for ML training to predict optical transceiver degradation.

CLI Equivalent: show interfaces
RPC: <get-interface-information/>

Key Metrics Collected:
1. FEC Corrected Codeword Count (fec_ccw)
2. FEC Uncorrected Codeword Count (fec_nccw) - Target variable for degradation prediction
3. FEC Corrected Error Rate (fec_ccw_error_rate)
4. FEC Uncorrected Error Rate (fec_nccw_error_rate)
5. Pre-FEC BER (pre_fec_ber) - Bit Error Rate
6. FEC Histogram bins 0-15 (histogram_bin_N) - Error distribution pattern

Note: Uses standard 'show interfaces' RPC (not extensive) to minimize compute impact.
"""

import sys
import json
import argparse
import time
from typing import Dict, List, Any, Optional
import xml.etree.ElementTree as ET


def extract_numeric_value(text: str) -> Optional[float]:
    """
    Extract numeric value from text, handling scientific notation and commas.
    
    Args:
        text: Text containing a numeric value
        
    Returns:
        Numeric value as float, or None if extraction fails
        
    Examples:
        "123" -> 123.0
        "1.5e-10" -> 1.5e-10
        "1,234" -> 1234.0
    """
    if not text:
        return None
    
    try:
        # Remove commas from numbers like "1,234"
        cleaned = text.strip().replace(',', '')
        return float(cleaned)
    except (ValueError, AttributeError):
        return None


def parse_speed(speed_text: str) -> Optional[int]:
    """
    Parse speed string to bits per second.
    
    Args:
        speed_text: Speed string (e.g., "400Gbps", "100Gbps", "10Gbps")
        
    Returns:
        Speed in bits per second as integer, or None if parsing fails
        
    Examples:
        "400Gbps" -> 400000000000
        "100Gbps" -> 100000000000
        "10Gbps" -> 10000000000
    """
    if not speed_text:
        return None
    
    speed_text = speed_text.strip().lower()
    
    # Extract numeric part and unit
    multipliers = {
        'gbps': 1_000_000_000,
        'mbps': 1_000_000,
        'kbps': 1_000,
        'bps': 1
    }
    
    for unit, multiplier in multipliers.items():
        if speed_text.endswith(unit):
            try:
                value = float(speed_text[:-len(unit)])
                return int(value * multiplier)
            except ValueError:
                return None
    
    return None


def parse_interface_statistics(xml_content: str, device: str, interface_filter: List[str] = None) -> Dict[str, Any]:
    """
    Parse interface FEC statistics from Junos get-interface-information XML output.
    
    Extracts 6 key metrics for ML training:
    1. FEC Corrected Codeword Count (fec_ccw)
    2. FEC Uncorrected Codeword Count (fec_nccw) - Target variable for degradation
    3. FEC Corrected Error Rate (fec_ccw_error_rate)
    4. FEC Uncorrected Error Rate (fec_nccw_error_rate)
    5. Pre-FEC BER (pre_fec_ber)
    6. FEC Histogram bins 0-15 (histogram_bin_N with live + harvest errors)
    
    Args:
        xml_content: XML string from get-interface-information RPC
        device: Device hostname or IP address
        interface_filter: Optional list of interface names to include
        
    Returns:
        Dictionary with 'interfaces' key containing list of interface statistics
    """
    try:
        root = ET.fromstring(xml_content)
    except ET.ParseError as e:
        print(f"Error parsing XML: {e}", file=sys.stderr)
        return {'interfaces': []}
    
    # Remove namespaces for easier parsing
    # Strip namespace from all tags
    for elem in root.iter():
        if '}' in elem.tag:
            elem.tag = elem.tag.split('}', 1)[1]
    
    # Find all physical interfaces
    interfaces = root.findall('.//physical-interface')
    
    results = []
    
    for interface in interfaces:
        interface_data = {}
        
        # Basic interface information
        name_elem = interface.find('name')
        if name_elem is not None and name_elem.text:
            interface_name = name_elem.text.strip()
            interface_data['if_name'] = interface_name
        else:
            continue  # Skip interfaces without a name
        
        # Apply interface filter if provided
        if interface_filter is not None and interface_name not in interface_filter:
            continue
        
        # Add device and timestamp
        interface_data['device'] = device
        interface_data['timestamp'] = int(time.time())
        interface_data['collection_time'] = time.strftime('%Y-%m-%d %H:%M:%S')
        
        # Admin and operational status (optional, for context)
        admin_status = interface.find('admin-status')
        if admin_status is not None and admin_status.text:
            interface_data['admin_status'] = admin_status.text.strip()
        
        oper_status = interface.find('oper-status')
        if oper_status is not None and oper_status.text:
            interface_data['oper_status'] = oper_status.text.strip()
        
        # Interface speed (optional, for normalization)
        speed = interface.find('speed')
        if speed is not None and speed.text:
            speed_bps = parse_speed(speed.text)
            if speed_bps is not None:
                interface_data['speed_bps'] = speed_bps
        
        # Traffic statistics (optional, for correlation with errors)
        traffic_stats = interface.find('traffic-statistics')
        if traffic_stats is not None:
            input_bps = traffic_stats.find('input-bps')
            if input_bps is not None and input_bps.text:
                interface_data['input_bps'] = extract_numeric_value(input_bps.text)
            
            input_pps = traffic_stats.find('input-pps')
            if input_pps is not None and input_pps.text:
                interface_data['input_pps'] = extract_numeric_value(input_pps.text)
            
            output_bps = traffic_stats.find('output-bps')
            if output_bps is not None and output_bps.text:
                interface_data['output_bps'] = extract_numeric_value(output_bps.text)
            
            output_pps = traffic_stats.find('output-pps')
            if output_pps is not None and output_pps.text:
                interface_data['output_pps'] = extract_numeric_value(output_pps.text)
        
        # === KEY METRICS FOR ML ===
        
        # 1-5: FEC statistics from ethernet-fec-statistics
        fec_stats = interface.find('ethernet-fec-statistics')
        if fec_stats is not None:
            # 1. FEC Corrected Codewords (cumulative counter)
            fec_ccw = fec_stats.find('fec_ccw_count')
            if fec_ccw is not None and fec_ccw.text:
                interface_data['fec_ccw'] = extract_numeric_value(fec_ccw.text)
            
            # 2. FEC Uncorrected Codewords (cumulative counter) - TARGET VARIABLE
            fec_nccw = fec_stats.find('fec_nccw_count')
            if fec_nccw is not None and fec_nccw.text:
                interface_data['fec_nccw'] = extract_numeric_value(fec_nccw.text)
            
            # 3. FEC Corrected Error Rate
            fec_ccw_rate = fec_stats.find('fec_ccw_error_rate')
            if fec_ccw_rate is not None and fec_ccw_rate.text:
                interface_data['fec_ccw_error_rate'] = extract_numeric_value(fec_ccw_rate.text)
            
            # 4. FEC Uncorrected Error Rate
            fec_nccw_rate = fec_stats.find('fec_nccw_error_rate')
            if fec_nccw_rate is not None and fec_nccw_rate.text:
                interface_data['fec_nccw_error_rate'] = extract_numeric_value(fec_nccw_rate.text)
            
            # 5. Pre-FEC BER (Bit Error Rate) in scientific notation
            pre_fec_ber = fec_stats.find('pre-fec-ber')
            if pre_fec_ber is not None and pre_fec_ber.text:
                interface_data['pre_fec_ber'] = extract_numeric_value(pre_fec_ber.text)
        
        # 6. FEC Histogram - error distribution across bins 0-15
        # Each bin represents number of symbol errors in a codeword
        # Critical for understanding error patterns and predicting degradation
        fec_histogram = interface.findall('ethernet-fechistogram-statistics')
        if fec_histogram:
            for bin_data in fec_histogram:
                bin_num = bin_data.find('bin-num')
                if bin_num is not None and bin_num.text:
                    bin_index = extract_numeric_value(bin_num.text)
                    if bin_index is not None:
                        bin_index = int(bin_index)
                        
                        # Live errors (current/recent errors)
                        sym_live = bin_data.find('sym-live-err')
                        live_err = 0
                        if sym_live is not None and sym_live.text:
                            live_err = extract_numeric_value(sym_live.text) or 0
                        
                        # Harvest errors (historical cumulative errors)
                        sym_harvest = bin_data.find('sym-harvest-err')
                        harvest_err = 0
                        if sym_harvest is not None and sym_harvest.text:
                            harvest_err = extract_numeric_value(sym_harvest.text) or 0
                        
                        # Store total (live + harvest) for ML features
                        interface_data[f'histogram_bin_{bin_index}'] = live_err + harvest_err
                        # Also store individual components for detailed analysis
                        interface_data[f'histogram_bin_{bin_index}_live'] = live_err
                        interface_data[f'histogram_bin_{bin_index}_harvest'] = harvest_err
        
        # Only include interfaces with FEC data (optical interfaces)
        if 'fec_ccw' in interface_data or 'fec_nccw' in interface_data:
            results.append(interface_data)
    
    return {'interfaces': results}


def main():
    """Main entry point for the parser."""
    parser = argparse.ArgumentParser(
        description='Parse Junos interface FEC statistics for ML training'
    )
    parser.add_argument('--input', required=True, help='Input XML file from get-interface-information RPC')
    parser.add_argument('--output', required=True, help='Output JSON file for FEC statistics')
    parser.add_argument('--device', required=True, help='Device hostname or IP address')
    parser.add_argument('--interfaces', type=str, 
                       help='Comma-separated list of interface names to filter (e.g., "et-0/0/0,et-0/0/1")')
    
    args = parser.parse_args()
    
    # Parse interface filter if provided
    interface_filter = None
    if args.interfaces:
        interface_filter = [iface.strip() for iface in args.interfaces.split(',')]
        print(f"Filtering for interfaces: {', '.join(interface_filter)}")
    
    # Read input XML
    try:
        with open(args.input, 'r') as f:
            xml_content = f.read()
    except IOError as e:
        print(f"Error reading input file {args.input}: {e}", file=sys.stderr)
        sys.exit(1)
    
    # Parse interface statistics
    result = parse_interface_statistics(xml_content, args.device, interface_filter)
    
    interface_count = len(result['interfaces'])
    
    if interface_count == 0:
        print("Warning: No interfaces with FEC data found", file=sys.stderr)
    else:
        print(f"Successfully extracted FEC statistics for {interface_count} interface(s)")
        
        # Print summary of metrics found
        if result['interfaces']:
            sample = result['interfaces'][0]
            metrics_found = []
            if 'fec_ccw' in sample:
                metrics_found.append('FEC corrected errors')
            if 'fec_nccw' in sample:
                metrics_found.append('FEC uncorrected errors')
            if 'fec_ccw_error_rate' in sample:
                metrics_found.append('FEC error rates')
            if 'pre_fec_ber' in sample:
                metrics_found.append('Pre-FEC BER')
            histogram_bins = [k for k in sample.keys() if k.startswith('histogram_bin_') and not k.endswith(('_live', '_harvest'))]
            if histogram_bins:
                metrics_found.append(f'FEC histogram ({len(histogram_bins)} bins)')
            
            if metrics_found:
                print(f"Metrics collected: {', '.join(metrics_found)}")
    
    # Write output JSON
    try:
        with open(args.output, 'w') as f:
            json.dump(result, f, indent=2)
        print(f"Output written to {args.output}")
    except IOError as e:
        print(f"Error writing output file {args.output}: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == '__main__':
    main()
