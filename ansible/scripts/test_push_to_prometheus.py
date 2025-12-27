#!/usr/bin/env python3
"""
Test suite for push_to_prometheus.py
"""

import unittest
import json
from push_to_prometheus import json_to_prometheus


class TestJsonToPrometheus(unittest.TestCase):
    """Test json_to_prometheus conversion function"""
    
    def test_interface_with_dom_metrics_no_lanes(self):
        """Test interface with DOM metrics directly on interface (no lanes)"""
        data = {
            "interfaces": [
                {
                    "if_name": "xe-0/0/6",
                    "device": "test-device",
                    "temperature": 39.0,
                    "voltage": 3.328,
                    "tx_bias": 5.392,
                    "tx_power_mw": 0.593,
                    "tx_power": -2.27,
                    "rx_power_mw": 0.6295,
                    "rx_power": -2.01,
                    "temperature_high_alarm": 90.0,
                    "tx_power_high_alarm": 3.01
                }
            ],
            "lanes": []
        }
        
        result = json_to_prometheus(data, "test_job", "test-device")
        
        # Verify interface-level DOM metrics are present WITHOUT lane label
        self.assertIn('tx_bias{device="test-device",interface="xe-0/0/6"} 5.392', result)
        self.assertIn('tx_power_mw{device="test-device",interface="xe-0/0/6"} 0.593', result)
        self.assertIn('tx_power{device="test-device",interface="xe-0/0/6"} -2.27', result)
        self.assertIn('rx_power_mw{device="test-device",interface="xe-0/0/6"} 0.6295', result)
        self.assertIn('rx_power{device="test-device",interface="xe-0/0/6"} -2.01', result)
        
        # Verify temperature and voltage are still present
        self.assertIn('temperature{device="test-device",interface="xe-0/0/6"} 39.0', result)
        self.assertIn('voltage{device="test-device",interface="xe-0/0/6"} 3.328', result)
        
        # Verify thresholds are present
        self.assertIn('temperature_high_alarm{device="test-device",interface="xe-0/0/6"} 90.0', result)
        self.assertIn('tx_power_high_alarm{device="test-device",interface="xe-0/0/6"} 3.01', result)
        
        # Verify NO lane label appears in any metric
        self.assertNotIn('lane=', result)
    
    def test_interface_with_null_dom_metrics_and_lanes(self):
        """Test interface with null DOM metrics but lanes have values"""
        data = {
            "interfaces": [
                {
                    "if_name": "xe-0/0/48:2",
                    "device": "test-device",
                    "temperature": 28.2,
                    "voltage": 3.319,
                    "tx_bias": None,
                    "tx_power_mw": None,
                    "tx_power": None,
                    "rx_power_mw": None,
                    "rx_power": None,
                    "temperature_high_alarm": 75.0
                }
            ],
            "lanes": [
                {
                    "if_name": "xe-0/0/48:2",
                    "device": "test-device",
                    "lane": 2,
                    "rx_power_mw": 0.789,
                    "rx_power": -1.03,
                    "tx_power_mw": 0.42,
                    "tx_power": -3.77,
                    "tx_bias": 6.335
                }
            ]
        }
        
        result = json_to_prometheus(data, "test_job", "test-device")
        
        # Verify interface-level metrics are present (but not DOM metrics since they're null)
        self.assertIn('temperature{device="test-device",interface="xe-0/0/48:2"} 28.2', result)
        self.assertIn('voltage{device="test-device",interface="xe-0/0/48:2"} 3.319', result)
        self.assertIn('temperature_high_alarm{device="test-device",interface="xe-0/0/48:2"} 75.0', result)
        
        # Verify lane-level metrics are present WITH lane label
        self.assertIn('tx_bias{device="test-device",interface="xe-0/0/48:2",lane="2"} 6.335', result)
        self.assertIn('tx_power_mw{device="test-device",interface="xe-0/0/48:2",lane="2"} 0.42', result)
        self.assertIn('tx_power{device="test-device",interface="xe-0/0/48:2",lane="2"} -3.77', result)
        self.assertIn('rx_power_mw{device="test-device",interface="xe-0/0/48:2",lane="2"} 0.789', result)
        self.assertIn('rx_power{device="test-device",interface="xe-0/0/48:2",lane="2"} -1.03', result)
        
        # Verify interface-level DOM metrics WITHOUT lane label are NOT present (since they're null)
        lines_without_lane = [line for line in result.split('\n') if 'lane=' not in line]
        interface_dom_metrics = [
            'tx_bias{device="test-device",interface="xe-0/0/48:2"}',
            'tx_power_mw{device="test-device",interface="xe-0/0/48:2"}',
            'tx_power{device="test-device",interface="xe-0/0/48:2"}',
            'rx_power_mw{device="test-device",interface="xe-0/0/48:2"}',
            'rx_power{device="test-device",interface="xe-0/0/48:2"}'
        ]
        for metric in interface_dom_metrics:
            for line in lines_without_lane:
                self.assertNotIn(metric, line)
    
    def test_mixed_interfaces(self):
        """Test mix of interfaces with and without lane data"""
        data = {
            "interfaces": [
                {
                    "if_name": "xe-0/0/6",
                    "device": "test-device",
                    "temperature": 39.0,
                    "voltage": 3.328,
                    "tx_bias": 5.392,
                    "tx_power": -2.27,
                    "rx_power": -2.01
                },
                {
                    "if_name": "xe-0/0/48:2",
                    "device": "test-device",
                    "temperature": 28.2,
                    "voltage": 3.319,
                    "tx_bias": None,
                    "tx_power": None,
                    "rx_power": None
                }
            ],
            "lanes": [
                {
                    "if_name": "xe-0/0/48:2",
                    "device": "test-device",
                    "lane": 2,
                    "tx_bias": 6.335,
                    "tx_power": -3.77,
                    "rx_power": -1.03
                }
            ]
        }
        
        result = json_to_prometheus(data, "test_job", "test-device")
        
        # Interface xe-0/0/6 should have DOM metrics WITHOUT lane label
        self.assertIn('tx_bias{device="test-device",interface="xe-0/0/6"} 5.392', result)
        self.assertIn('tx_power{device="test-device",interface="xe-0/0/6"} -2.27', result)
        self.assertIn('rx_power{device="test-device",interface="xe-0/0/6"} -2.01', result)
        
        # Interface xe-0/0/48:2 should only have lane-level metrics WITH lane label
        self.assertIn('tx_bias{device="test-device",interface="xe-0/0/48:2",lane="2"} 6.335', result)
        self.assertIn('tx_power{device="test-device",interface="xe-0/0/48:2",lane="2"} -3.77', result)
        self.assertIn('rx_power{device="test-device",interface="xe-0/0/48:2",lane="2"} -1.03', result)
        
        # Both interfaces should have temperature and voltage
        self.assertIn('temperature{device="test-device",interface="xe-0/0/6"} 39.0', result)
        self.assertIn('temperature{device="test-device",interface="xe-0/0/48:2"} 28.2', result)
    
    def test_all_thresholds(self):
        """Test that all threshold metrics are properly exported"""
        data = {
            "interfaces": [
                {
                    "if_name": "xe-0/0/1",
                    "device": "test-device",
                    "temperature_high_alarm": 90.0,
                    "temperature_low_alarm": -10.0,
                    "temperature_high_warn": 85.0,
                    "temperature_low_warn": -5.0,
                    "voltage_high_alarm": 3.63,
                    "voltage_low_alarm": 2.97,
                    "voltage_high_warn": 3.465,
                    "voltage_low_warn": 3.134,
                    "tx_power_high_alarm": 3.01,
                    "tx_power_low_alarm": -9.0,
                    "tx_power_high_warn": -1.02,
                    "tx_power_low_warn": -4.99,
                    "rx_power_high_alarm": 2.0,
                    "rx_power_low_alarm": -13.9,
                    "rx_power_high_warn": -1.0,
                    "rx_power_low_warn": -9.9,
                    "tx_bias_high_alarm": 10.5,
                    "tx_bias_low_alarm": 2.5,
                    "tx_bias_high_warn": 10.5,
                    "tx_bias_low_warn": 2.5
                }
            ],
            "lanes": []
        }
        
        result = json_to_prometheus(data, "test_job", "test-device")
        
        # Verify all threshold types are present
        threshold_types = [
            'temperature_high_alarm', 'temperature_low_alarm', 'temperature_high_warn', 'temperature_low_warn',
            'voltage_high_alarm', 'voltage_low_alarm', 'voltage_high_warn', 'voltage_low_warn',
            'tx_power_high_alarm', 'tx_power_low_alarm', 'tx_power_high_warn', 'tx_power_low_warn',
            'rx_power_high_alarm', 'rx_power_low_alarm', 'rx_power_high_warn', 'rx_power_low_warn',
            'tx_bias_high_alarm', 'tx_bias_low_alarm', 'tx_bias_high_warn', 'tx_bias_low_warn'
        ]
        
        for threshold in threshold_types:
            self.assertIn(f'{threshold}{{device="test-device",interface="xe-0/0/1"}}', result)
    
    def test_empty_data(self):
        """Test with empty interfaces and lanes"""
        data = {
            "interfaces": [],
            "lanes": []
        }
        
        result = json_to_prometheus(data, "test_job", "test-device")
        
        # Should only have trailing newline
        self.assertEqual(result, '\n')
    
    def test_multiple_lanes_same_interface(self):
        """Test interface with multiple lanes"""
        data = {
            "interfaces": [
                {
                    "if_name": "xe-0/0/48",
                    "device": "test-device",
                    "temperature": 28.0,
                    "voltage": 3.3,
                    "tx_bias": None,
                    "tx_power": None,
                    "rx_power": None
                }
            ],
            "lanes": [
                {
                    "if_name": "xe-0/0/48",
                    "device": "test-device",
                    "lane": 0,
                    "tx_bias": 6.1,
                    "tx_power": -3.5,
                    "rx_power": -1.2
                },
                {
                    "if_name": "xe-0/0/48",
                    "device": "test-device",
                    "lane": 1,
                    "tx_bias": 6.2,
                    "tx_power": -3.6,
                    "rx_power": -1.3
                },
                {
                    "if_name": "xe-0/0/48",
                    "device": "test-device",
                    "lane": 2,
                    "tx_bias": 6.3,
                    "tx_power": -3.7,
                    "rx_power": -1.4
                }
            ]
        }
        
        result = json_to_prometheus(data, "test_job", "test-device")
        
        # Verify all lanes are present with correct lane numbers
        self.assertIn('tx_bias{device="test-device",interface="xe-0/0/48",lane="0"} 6.1', result)
        self.assertIn('tx_bias{device="test-device",interface="xe-0/0/48",lane="1"} 6.2', result)
        self.assertIn('tx_bias{device="test-device",interface="xe-0/0/48",lane="2"} 6.3', result)
        
        self.assertIn('tx_power{device="test-device",interface="xe-0/0/48",lane="0"} -3.5', result)
        self.assertIn('tx_power{device="test-device",interface="xe-0/0/48",lane="1"} -3.6', result)
        self.assertIn('tx_power{device="test-device",interface="xe-0/0/48",lane="2"} -3.7', result)
        
        # Verify interface-level metrics are still present
        self.assertIn('temperature{device="test-device",interface="xe-0/0/48"} 28.0', result)
        self.assertIn('voltage{device="test-device",interface="xe-0/0/48"} 3.3', result)
    
    def test_real_world_data(self):
        """Test with actual data from dcf-onyx27-jun.englab.juniper.net"""
        data = {
            "interfaces": [
                {
                    "if_name": "xe-0/0/6",
                    "device": "dcf-onyx27-jun.englab.juniper.net",
                    "temperature": 39.0,
                    "voltage": 3.328,
                    "tx_bias": 5.392,
                    "tx_power_mw": 0.593,
                    "tx_power": -2.27,
                    "rx_power_mw": 0.6295,
                    "rx_power": -2.01,
                    "temperature_high_alarm": 90.0
                },
                {
                    "if_name": "xe-0/0/48:2",
                    "device": "dcf-onyx27-jun.englab.juniper.net",
                    "temperature": 28.2,
                    "voltage": 3.319,
                    "tx_bias": None,
                    "tx_power_mw": None,
                    "tx_power": None,
                    "rx_power_mw": None,
                    "rx_power": None
                }
            ],
            "lanes": [
                {
                    "if_name": "xe-0/0/48:2",
                    "device": "dcf-onyx27-jun.englab.juniper.net",
                    "lane": 2,
                    "rx_power_mw": 0.789,
                    "rx_power": -1.03,
                    "tx_power_mw": 0.42,
                    "tx_power": -3.77,
                    "tx_bias": 6.335
                }
            ]
        }
        
        result = json_to_prometheus(data, "junos_optics", "dcf-onyx27-jun.englab.juniper.net")
        
        # xe-0/0/6: Interface with DOM metrics directly (no lanes)
        self.assertIn('tx_bias{device="dcf-onyx27-jun.englab.juniper.net",interface="xe-0/0/6"} 5.392', result)
        self.assertIn('tx_power_mw{device="dcf-onyx27-jun.englab.juniper.net",interface="xe-0/0/6"} 0.593', result)
        self.assertIn('tx_power{device="dcf-onyx27-jun.englab.juniper.net",interface="xe-0/0/6"} -2.27', result)
        self.assertIn('rx_power_mw{device="dcf-onyx27-jun.englab.juniper.net",interface="xe-0/0/6"} 0.6295', result)
        self.assertIn('rx_power{device="dcf-onyx27-jun.englab.juniper.net",interface="xe-0/0/6"} -2.01', result)
        
        # xe-0/0/48:2: Interface with lane-level DOM metrics
        self.assertIn('tx_bias{device="dcf-onyx27-jun.englab.juniper.net",interface="xe-0/0/48:2",lane="2"} 6.335', result)
        self.assertIn('tx_power_mw{device="dcf-onyx27-jun.englab.juniper.net",interface="xe-0/0/48:2",lane="2"} 0.42', result)
        self.assertIn('rx_power_mw{device="dcf-onyx27-jun.englab.juniper.net",interface="xe-0/0/48:2",lane="2"} 0.789', result)
        
        # Verify both interfaces have temperature/voltage without lane label
        self.assertIn('temperature{device="dcf-onyx27-jun.englab.juniper.net",interface="xe-0/0/6"} 39.0', result)
        self.assertIn('temperature{device="dcf-onyx27-jun.englab.juniper.net",interface="xe-0/0/48:2"} 28.2', result)


if __name__ == '__main__':
    unittest.main()
