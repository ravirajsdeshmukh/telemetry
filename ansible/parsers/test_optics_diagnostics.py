#!/usr/bin/env python3
"""
Test suite for optics_diagnostics parser.
"""

import unittest
import json
import os
import sys
from pathlib import Path

# Add parent directory to path to import the parser
sys.path.insert(0, str(Path(__file__).parent))

from optics_diagnostics import (
    parse_optical_diagnostics,
    parse_interface_metrics,
    parse_lane_metrics,
    extract_numeric_value,
    findall_recursive_ns,
    findtext_ns
)
import xml.etree.ElementTree as ET


class TestOpticsDiagnosticsParser(unittest.TestCase):
    """Test cases for optical diagnostics parser."""
    
    @classmethod
    def setUpClass(cls):
        """Load test data."""
        test_data_dir = Path(__file__).parent / 'test_data'
        
        # Load sample XML
        xml_file = test_data_dir / 'optics_rpc_response.xml'
        if xml_file.exists():
            with open(xml_file, 'r') as f:
                cls.sample_xml = f.read()
        else:
            cls.sample_xml = None
        
        # Load sample expected output
        json_file = test_data_dir / 'optics_lane_rpc_prom.json'
        if json_file.exists():
            with open(json_file, 'r') as f:
                cls.expected_lane_sample = json.load(f)
        else:
            cls.expected_lane_sample = None
    
    def test_extract_numeric_value(self):
        """Test numeric value extraction."""
        # Test with unit
        self.assertEqual(extract_numeric_value("34 degrees C / 93 degrees F"), 34.0)
        self.assertEqual(extract_numeric_value("3.347"), 3.347)
        self.assertEqual(extract_numeric_value("-2.28"), -2.28)
        
        # Test with None
        self.assertIsNone(extract_numeric_value(None))
        
        # Test with invalid input
        self.assertIsNone(extract_numeric_value("Not supported"))
    
    def test_parse_full_xml(self):
        """Test parsing complete XML response."""
        if not self.sample_xml:
            self.skipTest("Sample XML file not found")
        
        result = parse_optical_diagnostics(self.sample_xml, "10.209.3.39")
        
        # Verify structure
        self.assertIn('interfaces', result)
        self.assertIn('lanes', result)
        self.assertIsInstance(result['interfaces'], list)
        self.assertIsInstance(result['lanes'], list)
        
        # Should have at least one interface with data (et-0/0/32)
        self.assertGreater(len(result['interfaces']), 0)
        self.assertGreater(len(result['lanes']), 0)
        
        print(f"\nParsed {len(result['interfaces'])} interfaces and {len(result['lanes'])} lanes")
    
    def test_interface_metrics_parsing(self):
        """Test parsing interface-level metrics (thresholds)."""
        if not self.sample_xml:
            self.skipTest("Sample XML file not found")
        
        root = ET.fromstring(self.sample_xml)
        # Find et-0/0/32 which has data
        phys_interface = None
        for pi in findall_recursive_ns(root, 'physical-interface'):
            if findtext_ns(pi, 'name') == 'et-0/0/32':
                phys_interface = pi
                break
        
        self.assertIsNotNone(phys_interface, "et-0/0/32 interface not found")
        
        metrics = parse_interface_metrics(phys_interface, "10.209.3.39")
        
        # Verify basic structure
        self.assertIsNotNone(metrics)
        self.assertEqual(metrics['if_name'], 'et-0/0/32')
        self.assertEqual(metrics['device'], '10.209.3.39')
        
        # Verify temperature thresholds
        self.assertEqual(metrics['temperature_high_alarm'], 90.0)
        self.assertEqual(metrics['temperature_low_alarm'], -10.0)
        self.assertEqual(metrics['temperature_high_warn'], 85.0)
        self.assertEqual(metrics['temperature_low_warn'], -5.0)
        
        # Verify voltage thresholds
        self.assertEqual(metrics['voltage_high_alarm'], 3.63)
        self.assertEqual(metrics['voltage_low_alarm'], 2.97)
        self.assertEqual(metrics['voltage_high_warn'], 3.464)
        self.assertEqual(metrics['voltage_low_warn'], 3.134)
        
        # Verify TX power thresholds
        self.assertEqual(metrics['tx_power_high_alarm'], 0.00)
        self.assertEqual(metrics['tx_power_low_alarm'], -5.99)
        self.assertEqual(metrics['tx_power_high_warn'], -1.00)
        self.assertEqual(metrics['tx_power_low_warn'], -5.00)
        
        # Verify RX power thresholds
        self.assertEqual(metrics['rx_power_high_alarm'], 2.00)
        self.assertEqual(metrics['rx_power_low_alarm'], -13.90)
        self.assertEqual(metrics['rx_power_high_warn'], -1.00)
        self.assertEqual(metrics['rx_power_low_warn'], -9.90)
        
        # Verify TX bias current thresholds
        self.assertEqual(metrics['tx_bias_high_alarm'], 13.0)
        self.assertEqual(metrics['tx_bias_low_alarm'], 4.0)
        self.assertEqual(metrics['tx_bias_high_warn'], 12.5)
        self.assertEqual(metrics['tx_bias_low_warn'], 5.0)
        
        print("\nInterface metrics:", json.dumps(metrics, indent=2))
    
    def test_lane_metrics_parsing(self):
        """Test parsing lane-level metrics."""
        if not self.sample_xml:
            self.skipTest("Sample XML file not found")
        
        root = ET.fromstring(self.sample_xml)
        # Find et-0/0/32 which has data
        phys_interface = None
        for pi in findall_recursive_ns(root, 'physical-interface'):
            if findtext_ns(pi, 'name') == 'et-0/0/32':
                phys_interface = pi
                break
        
        self.assertIsNotNone(phys_interface, "et-0/0/32 interface not found")
        
        lane_metrics = parse_lane_metrics(phys_interface, "10.209.3.39")
        
        # Should have exactly one lane
        self.assertEqual(len(lane_metrics), 1)
        
        lane = lane_metrics[0]
        
        # Verify basic structure
        self.assertEqual(lane['if_name'], 'et-0/0/32')
        self.assertEqual(lane['device'], '10.209.3.39')
        self.assertEqual(lane['lane'], 0)
        
        # Verify metrics match expected values from XML
        self.assertEqual(lane['rx_power_mw'], 0.591)
        self.assertEqual(lane['rx_power'], -2.28)
        self.assertEqual(lane['tx_power_mw'], 0.585)
        self.assertEqual(lane['tx_power'], -2.32)
        self.assertEqual(lane['tx_bias'], 6.157)
        
        # Compare with expected sample (if available)
        if self.expected_lane_sample:
            self.assertEqual(lane['rx_power_mw'], self.expected_lane_sample['rx_power_mw'])
            self.assertEqual(lane['rx_power'], self.expected_lane_sample['rx_power'])
            self.assertEqual(lane['tx_power_mw'], self.expected_lane_sample['tx_power_mw'])
            self.assertEqual(lane['tx_power'], self.expected_lane_sample['tx_power'])
            self.assertEqual(lane['tx_bias'], self.expected_lane_sample['tx_bias'])
        
        print("\nLane metrics:", json.dumps(lane, indent=2))
    
    def test_not_supported_interfaces(self):
        """Test handling of interfaces with no diagnostics."""
        if not self.sample_xml:
            self.skipTest("Sample XML file not found")
        
        root = ET.fromstring(self.sample_xml)
        # Find et-0/0/0:0 which has "Not supported"
        phys_interface = None
        for pi in findall_recursive_ns(root, 'physical-interface'):
            if findtext_ns(pi, 'name') == 'et-0/0/0:0':
                phys_interface = pi
                break
        
        self.assertIsNotNone(phys_interface, "et-0/0/0:0 interface not found")
        
        # Should return None for interface metrics
        interface_metrics = parse_interface_metrics(phys_interface, "10.209.3.39")
        self.assertIsNone(interface_metrics)
        
        # Should return empty list for lane metrics
        lane_metrics = parse_lane_metrics(phys_interface, "10.209.3.39")
        self.assertEqual(lane_metrics, [])
    
    def test_with_additional_metadata(self):
        """Test parsing with additional metadata."""
        if not self.sample_xml:
            self.skipTest("Sample XML file not found")
        
        metadata = {
            'origin_hostname': '5d2-qfx1-leaf2',
            'blueprint_label': 'HW-BP',
            'probe_label': 'Optical Transceivers',
            'stage_name': 'Lane Stats'
        }
        
        result = parse_optical_diagnostics(self.sample_xml, "10.209.3.39", metadata)
        
        # Verify metadata is included in lane metrics
        if result['lanes']:
            lane = result['lanes'][0]
            self.assertEqual(lane['origin_hostname'], '5d2-qfx1-leaf2')
            self.assertEqual(lane['blueprint_label'], 'HW-BP')
            self.assertEqual(lane['probe_label'], 'Optical Transceivers')
            self.assertEqual(lane['stage_name'], 'Lane Stats')
    
    def test_json_output_format(self):
        """Test that output can be serialized to JSON."""
        if not self.sample_xml:
            self.skipTest("Sample XML file not found")
        
        result = parse_optical_diagnostics(self.sample_xml, "10.209.3.39")
        
        # Should be able to serialize to JSON without errors
        json_str = json.dumps(result, indent=2)
        self.assertIsNotNone(json_str)
        
        # Should be able to deserialize back
        deserialized = json.loads(json_str)
        self.assertEqual(len(deserialized['interfaces']), len(result['interfaces']))
        self.assertEqual(len(deserialized['lanes']), len(result['lanes']))
    
    def test_field_mappings(self):
        """Verify all required fields from mapping files are present."""
        if not self.sample_xml:
            self.skipTest("Sample XML file not found")
        
        result = parse_optical_diagnostics(self.sample_xml, "10.209.3.39")
        
        # Required lane fields from lane-mapping.meta
        required_lane_fields = [
            'if_name', 'lane', 'rx_power_mw', 'rx_power',
            'tx_power_mw', 'tx_power', 'tx_bias'
        ]
        
        if result['lanes']:
            lane = result['lanes'][0]
            for field in required_lane_fields:
                self.assertIn(field, lane, f"Missing required lane field: {field}")
        
        # Required interface fields from interface-mapping.meta
        required_interface_fields = [
            'if_name', 'temperature_high_alarm', 'temperature_low_alarm',
            'temperature_high_warn', 'temperature_low_warn',
            'voltage_high_alarm', 'voltage_low_alarm',
            'voltage_high_warn', 'voltage_low_warn',
            'tx_power_high_alarm', 'tx_power_low_alarm',
            'tx_power_high_warn', 'tx_power_low_warn',
            'rx_power_high_alarm', 'rx_power_low_alarm',
            'rx_power_high_warn', 'rx_power_low_warn',
            'tx_bias_high_alarm', 'tx_bias_low_alarm',
            'tx_bias_high_warn', 'tx_bias_low_warn'
        ]
        
        if result['interfaces']:
            interface = result['interfaces'][0]
            for field in required_interface_fields:
                self.assertIn(field, interface, f"Missing required interface field: {field}")


def run_tests():
    """Run all tests and print results."""
    # Create test suite
    loader = unittest.TestLoader()
    suite = loader.loadTestsFromTestCase(TestOpticsDiagnosticsParser)
    
    # Run tests with verbose output
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)
    
    # Return exit code
    return 0 if result.wasSuccessful() else 1


if __name__ == '__main__':
    sys.exit(run_tests())
