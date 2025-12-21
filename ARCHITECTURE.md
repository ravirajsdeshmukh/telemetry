# System Architecture and Data Flow

## High-Level Architecture

```
┌─────────────────┐
│  Junos Device   │
│  10.209.3.39    │
│   (NETCONF)     │
└────────┬────────┘
         │
         │ RPC Request
         │ <get-interface-optics-diagnostics-information>
         │
         ▼
┌─────────────────────────────────────────────────────────┐
│              Ansible Playbook                           │
│  (junos_telemetry.yml)                                  │
│                                                         │
│  1. Connect via NETCONF                                │
│  2. Execute RPC from rpc_commands.yml                  │
│  3. Save raw XML to output/                            │
│  4. Call parser script                                 │
│  5. Push to Prometheus (optional)                      │
└────────┬───────────────────────────────────────────────┘
         │
         │ XML Response
         │
         ▼
┌─────────────────────────────────────────────────────────┐
│         Parser (optics_diagnostics.py)                  │
│                                                         │
│  Input:  Raw XML                                       │
│  Process:                                              │
│    • Parse with namespace handling                     │
│    • Extract interface thresholds                      │
│    • Extract lane measurements                         │
│    • Apply field mappings                              │
│  Output: JSON {interfaces: [], lanes: []}             │
└────────┬───────────────────────────────────────────────┘
         │
         │ JSON Data
         │
         ▼
┌─────────────────────────────────────────────────────────┐
│     Push Script (push_to_prometheus.py)                 │
│                                                         │
│  1. Read JSON file                                     │
│  2. Convert to Prometheus line protocol               │
│  3. POST to Pushgateway                               │
└────────┬───────────────────────────────────────────────┘
         │
         │ Prometheus Metrics
         │
         ▼
┌─────────────────┐      ┌─────────────────┐
│  Pushgateway    │──────│   Prometheus    │
│  :9091          │      │   :9090         │
└─────────────────┘      └────────┬────────┘
                                  │
                                  │ Scrape
                                  │
                                  ▼
                         ┌─────────────────┐
                         │    Grafana      │
                         │    :3000        │
                         │  (Dashboards)   │
                         └─────────────────┘
```

## Data Transformation Flow

```
XML (NETCONF Response)
  │
  ├─ <physical-interface>
  │    ├─ <name>et-0/0/32</name>
  │    └─ <optics-diagnostics>
  │         ├─ <laser-temperature-high-alarm-threshold>90</...>
  │         └─ <optics-diagnostics-lane-values>
  │              ├─ <lane-index>0</lane-index>
  │              ├─ <laser-rx-optical-power>0.591</...>
  │              └─ <laser-output-power-dbm>-2.32</...>
  │
  ▼
JSON (Structured Data)
  │
  ├─ interfaces: [
  │    {
  │      "if_name": "et-0/0/32",
  │      "temperature_high_alarm": 90.0,
  │      "voltage_high_alarm": 3.63,
  │      ...
  │    }
  │  ]
  │
  └─ lanes: [
       {
         "if_name": "et-0/0/32",
         "lane": 0,
         "rx_power_mw": 0.591,
         "rx_power": -2.28,
         "tx_power": -2.32,
         "tx_bias": 6.157
       }
     ]
  │
  ▼
Prometheus Line Protocol
  │
  junos_optics_rx_power_dbm{device="10.209.3.39",interface="et-0/0/32",lane="0"} -2.28
  junos_optics_tx_power_dbm{device="10.209.3.39",interface="et-0/0/32",lane="0"} -2.32
  junos_optics_tx_bias_current_milliamps{device="10.209.3.39",interface="et-0/0/32",lane="0"} 6.157
  │
  ▼
Time Series Database (Prometheus)
  │
  └─ Stored with timestamps, indexed by labels
```

## Field Mapping Process

```
XML Path (from meta files)          →  JSON Field Name
────────────────────────────────────────────────────────

Interface Level (Thresholds):
  laser-temperature-high-alarm      →  temperature_high_alarm
  module-voltage-high-alarm         →  voltage_high_alarm
  laser-tx-power-high-alarm-dbm     →  tx_power_high_alarm
  laser-rx-power-high-alarm-dbm     →  rx_power_high_alarm
  laser-bias-current-high-alarm     →  tx_bias_high_alarm

Lane Level (Measurements):
  lane-index                        →  lane
  laser-rx-optical-power            →  rx_power_mw
  laser-rx-optical-power-dbm        →  rx_power
  laser-output-power                →  tx_power_mw
  laser-output-power-dbm            →  tx_power
  laser-bias-current                →  tx_bias
```

## Execution Flow

```
1. ansible-playbook junos_telemetry.yml
   │
   ├─ Load inventory.yml (device credentials)
   ├─ Load rpc_commands.yml (commands to execute)
   │
   ├─ For each device in junos_devices:
   │    │
   │    ├─ Establish NETCONF connection
   │    │
   │    ├─ For each RPC command:
   │    │    │
   │    │    ├─ Execute RPC via junos_rpc module
   │    │    ├─ Save raw XML → output/{device}_{command}_raw.xml
   │    │    │
   │    │    ├─ Run parser script:
   │    │    │    python3 parsers/{parser}.py \
   │    │    │      --input output/{device}_{command}_raw.xml \
   │    │    │      --output output/{device}_{command}_metrics.json \
   │    │    │      --device {device} \
   │    │    │      --format json
   │    │    │
   │    │    └─ If prometheus_pushgateway defined:
   │    │         python3 scripts/push_to_prometheus.py \
   │    │           --pushgateway {url} \
   │    │           --job junos_telemetry \
   │    │           --instance {device} \
   │    │           --metrics-file output/{device}_{command}_metrics.json \
   │    │           --format json
   │    │
   │    └─ Close NETCONF connection
   │
   └─ Playbook complete
```

## File Organization

```
telemetry/
│
├── Configuration Files
│   ├── inventory.yml          # Device list & credentials
│   ├── rpc_commands.yml       # RPC commands & parsers mapping
│   └── ansible.cfg            # Ansible settings
│
├── Execution Layer
│   ├── junos_telemetry.yml    # Main playbook
│   └── demo.sh                # Test/demo script
│
├── Processing Layer
│   └── parsers/
│       ├── optics_diagnostics.py    # Optical metrics parser
│       ├── template_parser.py       # Template for new parsers
│       └── test_optics_diagnostics.py  # Test suite
│
├── Integration Layer
│   └── scripts/
│       └── push_to_prometheus.py    # Prometheus integration
│
├── Test Data
│   └── parsers/test_data/
│       ├── optics_rpc_response.xml  # Sample XML
│       ├── optics_lane_rpc_prom.json  # Expected output
│       ├── interface-mapping.meta   # Interface field mappings
│       └── lane-mapping.meta        # Lane field mappings
│
├── Runtime Output (created during execution)
│   └── output/
│       ├── {device}_{command}_raw.xml
│       └── {device}_{command}_metrics.json
│
└── Documentation
    ├── README.md              # Complete documentation
    ├── SUMMARY.md             # Quick summary
    └── IMPLEMENTATION_GUIDE.md  # Step-by-step guide
```

## Parser Internal Architecture

```
optics_diagnostics.py
│
├── Namespace Handling Functions
│   ├── strip_namespace()      # Remove XML namespace
│   ├── findall_ns()          # Find elements ignoring NS
│   ├── find_ns()             # Find single element
│   ├── findtext_ns()         # Get text ignoring NS
│   └── findall_recursive_ns()  # Recursive search
│
├── Data Extraction
│   ├── extract_numeric_value()  # Parse numbers with units
│   ├── parse_interface_metrics()  # Extract thresholds
│   └── parse_lane_metrics()    # Extract measurements
│
├── Main Processing
│   └── parse_optical_diagnostics()
│        │
│        ├─ Parse XML
│        ├─ Find all physical interfaces
│        │
│        ├─ For each interface:
│        │    ├─ Extract interface metrics
│        │    └─ Extract lane metrics
│        │
│        └─ Return {interfaces: [], lanes: []}
│
└── CLI Interface
    └── main()
         ├─ Parse arguments
         ├─ Read input XML
         ├─ Call parse_optical_diagnostics()
         └─ Write JSON output
```

## Prometheus Push Architecture

```
push_to_prometheus.py
│
├── JSON to Prometheus Conversion
│   └── json_to_prometheus()
│        │
│        ├─ Read lanes array from JSON
│        │
│        └─ For each lane:
│             ├─ Build label set
│             │   {job, instance, device, interface, lane}
│             │
│             └─ Generate metric lines:
│                  junos_optics_{metric}{{labels}} value
│
├── Push Logic
│   └── push_metrics()
│        │
│        ├─ Read metrics file
│        ├─ Convert JSON to Prometheus format
│        │
│        └─ POST to Pushgateway
│             URL: {pushgateway}/metrics/job/{job}/instance/{instance}
│             Body: Prometheus line protocol
│
└── CLI Interface
    └── main()
```

## Extension Points

```
Adding New RPC Commands:
1. Edit rpc_commands.yml
   └─ Add new command with parser name

2. Create parsers/{parser_name}.py
   └─ Based on template_parser.py
   └─ Implement parse_rpc_output()

3. Create test data
   └─ parsers/test_data/{command}_response.xml
   └─ parsers/test_data/{command}_mapping.meta

4. Create tests
   └─ parsers/test_{parser_name}.py

5. Run playbook
   └─ Automatically processes new command
```
