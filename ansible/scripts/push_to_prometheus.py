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
    
    # Process interface-level metrics (thresholds)
    for interface in data.get('interfaces', []):
        if_name = interface.get('if_name', 'unknown')
        device = interface.get('device', instance)
        
        # Base labels for interface metrics (no lane)
        base_labels = f'device="{device}",interface="{if_name}"'
        
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
    
    # Process lane-level metrics (measurements)
    for lane in data.get('lanes', []):
        if_name = lane.get('if_name', 'unknown')
        lane_num = lane.get('lane', 0)
        device = lane.get('device', instance)
        
        # Base labels for lane metrics (includes lane)
        base_labels = f'device="{device}",interface="{if_name}",lane="{lane_num}"'
        
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
