#!/usr/bin/env python3
"""
Push metrics to Prometheus Pushgateway.
Supports both JSON and Prometheus line protocol formats.
"""

import argparse
import requests
import sys
import json


def json_to_prometheus(data: dict, job: str, instance: str) -> str:
    """
    Convert JSON metrics to Prometheus line protocol.
    
    Args:
        data: Dictionary with 'interfaces' and 'lanes' arrays
        job: Job label
        instance: Instance label
    
    Returns:
        Prometheus line protocol string
    """
    lines = []
    
    # Process interface-level metrics (thresholds and FEC statistics)
    for interface in data.get('interfaces', []):
        # Get interface name (uniform 'if_name' across all metric types)
        if_name = interface.get('if_name', 'unknown')
        
        # Build base labels with metadata
        labels = [
            f'interface="{if_name}"'
        ]
        
        # Add device-level metadata
        if interface.get('origin_hostname'):
            labels.append(f'origin_hostname="{interface["origin_hostname"]}"')
        if interface.get('device_profile'):
            labels.append(f'device_profile="{interface["device_profile"]}"')
        if interface.get('origin_name'):
            labels.append(f'origin_name="{interface["origin_name"]}"')
        
        # Add transceiver metadata
        if interface.get('vendor'):
            labels.append(f'vendor="{interface["vendor"]}"')
        if interface.get('part_number'):
            labels.append(f'part_number="{interface["part_number"]}"')
        if interface.get('serial_number'):
            labels.append(f'serial_number="{interface["serial_number"]}"')
        if interface.get('media_type'):
            labels.append(f'media_type="{interface["media_type"]}"')
        if interface.get('cable_type'):
            labels.append(f'cable_type="{interface["cable_type"]}"')
        if interface.get('wavelength'):
            labels.append(f'wavelength="{interface["wavelength"]}"')
        if interface.get('fiber_type'):
            labels.append(f'fiber_type="{interface["fiber_type"]}"')
        
        base_labels = ','.join(labels)
        
        # Temperature thresholds
        if interface.get('temperature_high_alarm') is not None:
            lines.append(f'temperature_high_alarm{{{base_labels}}} {interface["temperature_high_alarm"]}')
        if interface.get('temperature_low_alarm') is not None:
            lines.append(f'temperature_low_alarm{{{base_labels}}} {interface["temperature_low_alarm"]}')
        if interface.get('temperature_high_warn') is not None:
            lines.append(f'temperature_high_warn{{{base_labels}}} {interface["temperature_high_warn"]}')
        if interface.get('temperature_low_warn') is not None:
            lines.append(f'temperature_low_warn{{{base_labels}}} {interface["temperature_low_warn"]}')
        
        # Voltage thresholds
        if interface.get('voltage_high_alarm') is not None:
            lines.append(f'voltage_high_alarm{{{base_labels}}} {interface["voltage_high_alarm"]}')
        if interface.get('voltage_low_alarm') is not None:
            lines.append(f'voltage_low_alarm{{{base_labels}}} {interface["voltage_low_alarm"]}')
        if interface.get('voltage_high_warn') is not None:
            lines.append(f'voltage_high_warn{{{base_labels}}} {interface["voltage_high_warn"]}')
        if interface.get('voltage_low_warn') is not None:
            lines.append(f'voltage_low_warn{{{base_labels}}} {interface["voltage_low_warn"]}')
        
        # TX power thresholds
        if interface.get('tx_power_high_alarm') is not None:
            lines.append(f'tx_power_high_alarm{{{base_labels}}} {interface["tx_power_high_alarm"]}')
        if interface.get('tx_power_low_alarm') is not None:
            lines.append(f'tx_power_low_alarm{{{base_labels}}} {interface["tx_power_low_alarm"]}')
        if interface.get('tx_power_high_warn') is not None:
            lines.append(f'tx_power_high_warn{{{base_labels}}} {interface["tx_power_high_warn"]}')
        if interface.get('tx_power_low_warn') is not None:
            lines.append(f'tx_power_low_warn{{{base_labels}}} {interface["tx_power_low_warn"]}')
        
        # RX power thresholds
        if interface.get('rx_power_high_alarm') is not None:
            lines.append(f'rx_power_high_alarm{{{base_labels}}} {interface["rx_power_high_alarm"]}')
        if interface.get('rx_power_low_alarm') is not None:
            lines.append(f'rx_power_low_alarm{{{base_labels}}} {interface["rx_power_low_alarm"]}')
        if interface.get('rx_power_high_warn') is not None:
            lines.append(f'rx_power_high_warn{{{base_labels}}} {interface["rx_power_high_warn"]}')
        if interface.get('rx_power_low_warn') is not None:
            lines.append(f'rx_power_low_warn{{{base_labels}}} {interface["rx_power_low_warn"]}')
        
        # TX bias current thresholds
        if interface.get('tx_bias_high_alarm') is not None:
            lines.append(f'tx_bias_high_alarm{{{base_labels}}} {interface["tx_bias_high_alarm"]}')
        if interface.get('tx_bias_low_alarm') is not None:
            lines.append(f'tx_bias_low_alarm{{{base_labels}}} {interface["tx_bias_low_alarm"]}')
        if interface.get('tx_bias_high_warn') is not None:
            lines.append(f'tx_bias_high_warn{{{base_labels}}} {interface["tx_bias_high_warn"]}')
        if interface.get('tx_bias_low_warn') is not None:
            lines.append(f'tx_bias_low_warn{{{base_labels}}} {interface["tx_bias_low_warn"]}')
        
        # Current measured values (always at interface level)
        if interface.get('temperature') is not None:
            lines.append(f'temperature{{{base_labels}}} {interface["temperature"]}')
        if interface.get('voltage') is not None:
            lines.append(f'voltage{{{base_labels}}} {interface["voltage"]}')
        
        # DOM metrics at interface level (for interfaces without lanes)
        if interface.get('tx_bias') is not None:
            lines.append(f'tx_bias{{{base_labels}}} {interface["tx_bias"]}')
        if interface.get('tx_power_mw') is not None:
            lines.append(f'tx_power_mw{{{base_labels}}} {interface["tx_power_mw"]}')
        if interface.get('tx_power') is not None:
            lines.append(f'tx_power{{{base_labels}}} {interface["tx_power"]}')
        if interface.get('rx_power_mw') is not None:
            lines.append(f'rx_power_mw{{{base_labels}}} {interface["rx_power_mw"]}')
        if interface.get('rx_power') is not None:
            lines.append(f'rx_power{{{base_labels}}} {interface["rx_power"]}')
        
        # Interface statistics (admin/oper status, traffic, speed)
        if interface.get('admin_status') is not None:
            # Convert status to numeric (0=down, 1=up)
            admin_value = 1 if interface['admin_status'] == 'up' else 0
            lines.append(f'interface_admin_status{{{base_labels}}} {admin_value}')
        if interface.get('oper_status') is not None:
            oper_value = 1 if interface['oper_status'] == 'up' else 0
            lines.append(f'interface_oper_status{{{base_labels}}} {oper_value}')
        if interface.get('speed_bps') is not None:
            lines.append(f'interface_speed_bps{{{base_labels}}} {interface["speed_bps"]}')
        if interface.get('input_bps') is not None:
            lines.append(f'interface_input_bps{{{base_labels}}} {interface["input_bps"]}')
        if interface.get('input_pps') is not None:
            lines.append(f'interface_input_pps{{{base_labels}}} {interface["input_pps"]}')
        if interface.get('output_bps') is not None:
            lines.append(f'interface_output_bps{{{base_labels}}} {interface["output_bps"]}')
        if interface.get('output_pps') is not None:
            lines.append(f'interface_output_pps{{{base_labels}}} {interface["output_pps"]}')
        
        # FEC statistics (Forward Error Correction)
        if interface.get('fec_ccw') is not None:
            lines.append(f'interface_fec_ccw{{{base_labels}}} {interface["fec_ccw"]}')
        if interface.get('fec_nccw') is not None:
            lines.append(f'interface_fec_nccw{{{base_labels}}} {interface["fec_nccw"]}')
        if interface.get('fec_ccw_error_rate') is not None:
            lines.append(f'interface_fec_ccw_error_rate{{{base_labels}}} {interface["fec_ccw_error_rate"]}')
        if interface.get('fec_nccw_error_rate') is not None:
            lines.append(f'interface_fec_nccw_error_rate{{{base_labels}}} {interface["fec_nccw_error_rate"]}')
        if interface.get('pre_fec_ber') is not None:
            lines.append(f'interface_pre_fec_ber{{{base_labels}}} {interface["pre_fec_ber"]}')
        
        # FEC histogram bins (if present)
        for i in range(16):
            bin_key = f'histogram_bin_{i}'
            if interface.get(bin_key) is not None:
                lines.append(f'interface_fec_histogram_bin_{i}{{{base_labels}}} {interface[bin_key]}')
    
    # Process lane-level metrics (measurements)
    for lane in data.get('lanes', []):
        if_name = lane.get('if_name', 'unknown')
        lane_num = lane.get('lane', 0)
        
        # Build base labels with metadata (includes lane)
        labels = [
            f'interface="{if_name}"',
            f'lane="{lane_num}"'
        ]
        
        # Add device-level metadata
        if lane.get('origin_hostname'):
            labels.append(f'origin_hostname="{lane["origin_hostname"]}"')
        if lane.get('device_profile'):
            labels.append(f'device_profile="{lane["device_profile"]}"')
        if lane.get('origin_name'):
            labels.append(f'origin_name="{lane["origin_name"]}"')
        
        # Add transceiver metadata
        if lane.get('vendor'):
            labels.append(f'vendor="{lane["vendor"]}"')
        if lane.get('part_number'):
            labels.append(f'part_number="{lane["part_number"]}"')
        if lane.get('serial_number'):
            labels.append(f'serial_number="{lane["serial_number"]}"')
        if lane.get('media_type'):
            labels.append(f'media_type="{lane["media_type"]}"')
        if lane.get('cable_type'):
            labels.append(f'cable_type="{lane["cable_type"]}"')
        if lane.get('wavelength'):
            labels.append(f'wavelength="{lane["wavelength"]}"')
        if lane.get('fiber_type'):
            labels.append(f'fiber_type="{lane["fiber_type"]}"')
        
        base_labels = ','.join(labels)
        
        # RX power metrics
        if lane.get('rx_power_mw') is not None:
            lines.append(f'rx_power_mw{{{base_labels}}} {lane["rx_power_mw"]}')
        if lane.get('rx_power') is not None:
            lines.append(f'rx_power{{{base_labels}}} {lane["rx_power"]}')
        
        # TX power metrics
        if lane.get('tx_power_mw') is not None:
            lines.append(f'tx_power_mw{{{base_labels}}} {lane["tx_power_mw"]}')
        if lane.get('tx_power') is not None:
            lines.append(f'tx_power{{{base_labels}}} {lane["tx_power"]}')
        
        # TX bias current
        if lane.get('tx_bias') is not None:
            lines.append(f'tx_bias{{{base_labels}}} {lane["tx_bias"]}')
    
    # Prometheus format requires trailing newline
    return '\n'.join(lines) + '\n'


def push_metrics(pushgateway_url: str, job: str, instance: str, 
                metrics_file: str, format_type: str = 'prom') -> bool:
    """
    Push metrics to Prometheus Pushgateway.
    
    Args:
        pushgateway_url: URL of the Pushgateway (e.g., http://localhost:9091)
        job: Job label for the metrics
        instance: Instance label (typically device hostname/IP)
        metrics_file: Path to file containing metrics
        format_type: Format of metrics file ('json' or 'prom')
    
    Returns:
        True if successful, False otherwise
    """
    try:
        with open(metrics_file, 'r') as f:
            if format_type == 'json':
                data = json.load(f)
                metrics_data = json_to_prometheus(data, job, instance)
            else:
                metrics_data = f.read()
    except (IOError, json.JSONDecodeError) as e:
        print(f"Error reading metrics file: {e}", file=sys.stderr)
        return False
    
    if not metrics_data.strip():
        print("Warning: No metrics to push", file=sys.stderr)
        return True
    
    # Construct the pushgateway URL with job and instance labels
    url = f"{pushgateway_url}/metrics/job/{job}/instance/{instance}"
    
    try:
        response = requests.post(
            url,
            data=metrics_data.encode('utf-8'),
            headers={'Content-Type': 'text/plain; charset=utf-8'},
            timeout=10
        )
        response.raise_for_status()
        print(f"Successfully pushed metrics to {url}")
        return True
    except requests.exceptions.RequestException as e:
        print(f"Error pushing metrics to Pushgateway: {e}", file=sys.stderr)
        return False


def main():
    parser = argparse.ArgumentParser(
        description='Push metrics to Prometheus Pushgateway'
    )
    parser.add_argument('--pushgateway', required=True, 
                        help='Pushgateway URL (e.g., http://localhost:9091)')
    parser.add_argument('--job', required=True, 
                        help='Job label for the metrics')
    parser.add_argument('--instance', required=True, 
                        help='Instance label (device hostname/IP)')
    parser.add_argument('--metrics-file', required=True, 
                        help='File containing metrics')
    parser.add_argument('--format', choices=['json', 'prom'], default='prom',
                        help='Format of metrics file (json or prom)')
    
    args = parser.parse_args()
    
    success = push_metrics(
        args.pushgateway,
        args.job,
        args.instance,
        args.metrics_file,
        args.format
    )
    
    sys.exit(0 if success else 1)


if __name__ == '__main__':
    main()
