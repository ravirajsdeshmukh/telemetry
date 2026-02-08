# System Architecture and Data Flow

## High-Level Architecture

```
┌─────────────────────────────────────────────────────────────────────┐
│                        Junos Devices (Sharded)                      │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐              │
│  │  Shard 1     │  │  Shard 2     │  │  Shard 3     │              │
│  │  (XAI, QFX)  │  │ (Regression) │  │ (Production) │              │
│  │   NETCONF    │  │   NETCONF    │  │   NETCONF    │              │
│  └──────┬───────┘  └──────┬───────┘  └──────┬───────┘              │
└─────────┼──────────────────┼──────────────────┼────────────────────┘
          │                  │                  │
          │  RPC Requests    │                  │
          │  - get-system-information           │
          │  - get-chassis-inventory            │
          │  - get-interface-optics-diagnostics │
          │  - get-interface-information        │
          │  - get-pic-detail                   │
          │                  │                  │
          ▼                  ▼                  ▼
┌─────────────────────────────────────────────────────────────────────┐
│         Semaphore Orchestration (3 Parallel Runners)                │
│  ┌──────────────────────────────────────────────────────────────┐   │
│  │              Ansible Playbook (junos_telemetry.yml)          │   │
│  │                                                              │   │
│  │  1. Initialize run timestamp (for partitioning)             │   │
│  │  2. Connect via NETCONF to devices                          │   │
│  │  3. Execute RPC commands from rpc_commands.yml              │   │
│  │  4. Save raw XML to /tmp/semaphore/output/                  │   │
│  │  5. Parse XML → JSON metrics                                │   │
│  │  6. Collect PIC details for transceiver metadata            │   │
│  │  7. Merge metadata (system + chassis + PIC + optics)        │   │
│  │  8. Write to Parquet files (per-device)                     │   │
│  │  9. Push to Prometheus (optional)                           │   │
│  │  10. Aggregate hourly Parquet files (per runner)            │   │
│  │  11. Sync to S3 data lake (AWS)                             │   │
│  └──────────────────────────────────────────────────────────────┘   │
└─────────┬───────────────────────────────────────────────────────────┘
          │
          │ XML → JSON → Parquet
          │
          ▼
┌─────────────────────────────────────────────────────────────────────┐
│                     Parser Pipeline (Python)                        │
│  ┌────────────────────────────────────────────────────────────┐     │
│  │ parsers/juniper/                                           │     │
│  │  ├─ system_information.py  → hostname, model, OS version   │     │
│  │  ├─ chassis_inventory.py   → serial, transceiver metadata  │     │
│  │  ├─ optics_diagnostics.py  → power, temp, bias, thresholds│     │
│  │  └─ interface_statistics.py→ FEC errors, BER, histogram   │     │
│  ├────────────────────────────────────────────────────────────┤     │
│  │ parsers/common/                                            │     │
│  │  ├─ xml_utils.py          → Namespace-aware XML parsing    │     │
│  │  ├─ fiber_detection.py     → Fiber type classification     │     │
│  │  └─ interface_mapping.py   → Interface name normalization  │     │
│  └────────────────────────────────────────────────────────────┘     │
└─────────┬───────────────────────────────────────────────────────────┘
          │
          │ JSON Metrics
          │
          ▼
┌─────────────────────────────────────────────────────────────────────┐
│                   Data Storage & Export Layer                       │
│  ┌────────────────────────────────────────────────────────────┐     │
│  │ scripts/                                                   │     │
│  │  ├─ merge_metadata.py      → Combine system/chassis/PIC   │     │
│  │  ├─ write_to_parquet.py    → Per-device Parquet files     │     │
│  │  ├─ write_hourly_parquet.py→ Hourly aggregation + S3 sync │     │
│  │  ├─ collect_pic_details.py → Transceiver details via RPC  │     │
│  │  └─ push_to_prometheus.py  → Pushgateway integration      │     │
│  └────────────────────────────────────────────────────────────┘     │
└─────────┬─────────────────────────────────────┬─────────────────────┘
          │                                     │
          │ Parquet Files                       │ Prometheus Metrics
          │                                     │
          ▼                                     ▼
┌─────────────────────────────┐     ┌─────────────────┐
│    AWS S3 Data Lake         │     │  Pushgateway    │
│  s3://amzn-ds-s3-rrd/       │     │  :9091          │
│         datalake/           │     └────────┬────────┘
│  dt=YYYY-MM-DD/             │              │
│    hr=HH/                   │              │ Scrape
│      intf-dom/              │              ▼
│      lane-dom/              │     ┌─────────────────┐
│      intf-counters/         │     │   Prometheus    │
│                             │     │   :9090         │
│  • Hive-partitioned format  │     └────────┬────────┘
│  • Snappy compression       │              │
│  • ML training ready        │              ▼
└─────────────────────────────┘     ┌─────────────────┐
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
  │         ├─ <module-temperature>45.5</...>
  │         ├─ <module-voltage>3.28</...>
  │         └─ <optics-diagnostics-lane-values>
  │              ├─ <lane-index>0</lane-index>
  │              ├─ <laser-rx-optical-power>0.591</...>
  │              ├─ <laser-output-power-dbm>-2.32</...>
  │              ├─ <laser-bias-current>6.157</...>
  │              └─ ...
  │
  ▼
JSON (Structured Data - Multiple Files)
  │
  ├─ system_information_metrics.json
  │    {
  │      "hostname": "dcf-glen8-evo.englab.juniper.net",
  │      "model": "qfx5220-32cd",
  │      "version": "22.4R3.25",
  │      "serial_number": "...",
  │      "timestamp": 1737238450
  │    }
  │
  ├─ chassis_inventory_metrics.json
  │    {
  │      "serial_number": "...",
  │      "transceivers": {
  │        "et-0/0/32": {
  │          "vendor": "Juniper Networks Inc",
  │          "part_number": "740-102562",
  │          "serial_number": "..."
  │        }
  │      }
  │    }
  │
  ├─ pic_detail_metrics.json
  │    {
  │      "et-0/0/32": {
  │        "vendor": "Juniper Networks Inc",
  │        "part_number": "740-102562",
  │        "wavelength": "1310nm",
  │        "fiber_type": "SM",
  │        "cable_type": "100GBASE-LR4",
  │        "fpc": 0, "pic": 0, "port": 32
  │      }
  │    }
  │
  ├─ optics_diagnostics_metrics.json (merged with metadata)
  │    {
  │      "interfaces": [...],
  │      "lanes": [
  │        {
  │          "if_name": "et-0/0/32",
  │          "device": "dcf-glen8-evo.englab.juniper.net",
  │          "lane": 0,
  │          "rx_power_mw": 0.591,
  │          "rx_power": -2.28,
  │          "tx_power_mw": 0.585,
  │          "tx_power": -2.32,
  │          "tx_bias": 6.157,
  │          "temperature": 45.5,
  │          "voltage": 3.28,
  │          // Merged metadata:
  │          "hostname": "dcf-glen8-evo.englab.juniper.net",
  │          "model": "qfx5220-32cd",
  │          "vendor": "Juniper Networks Inc",
  │          "part_number": "740-102562",
  │          "wavelength": "1310nm",
  │          "fiber_type": "SM",
  │          "cable_type": "100GBASE-LR4"
  │        }
  │      ]
  │    }
  │
  └─ interface_statistics_metrics.json
       {
         "et-0/0/32": {
           "if_name": "et-0/0/32",
           "device": "dcf-glen8-evo.englab.juniper.net",
           "admin_status": "up",
           "oper_status": "up",
           "speed_bps": 100000000000,
           "fec_ccw": 123456789,
           "fec_nccw": 0,
           "fec_ccw_rate": 0.0,
           "fec_nccw_rate": 0.0,
           "pre_fec_ber": "1.23e-10",
           "histogram_bin_0": 1000,
           "histogram_bin_1": 500,
           ... (bins 0-15)
         }
       }
  │
  ▼
Parquet Files (Hive-Partitioned for ML)
  │
  raw_ml_data/
    dt=2026-02-03/
      hr=15/
        ├─ intf-dom/
        │    interface_dom_20260203_153045.parquet
        │    ├─ if_name, device, hostname, model
        │    ├─ temperature, voltage, status
        │    ├─ vendor, part_number, wavelength, fiber_type
        │    └─ timestamp, run_timestamp, runner_name
        │
        ├─ lane-dom/
        │    lane_dom_20260203_153045.parquet
        │    ├─ if_name, lane, device, hostname
        │    ├─ rx_power, tx_power, tx_bias, temperature
        │    ├─ vendor, part_number, wavelength, fiber_type
        │    └─ timestamp, run_timestamp, runner_name
        │
        └─ intf-counters/
             interface_counters_20260203_153045.parquet
             ├─ if_name, device, hostname
             ├─ fec_ccw, fec_nccw, fec_ccw_rate, fec_nccw_rate
             ├─ pre_fec_ber, histogram_bin_0..15
             ├─ admin_status, oper_status, speed_bps
             └─ timestamp, run_timestamp, runner_name
  │
  ▼
Prometheus Line Protocol (Optional Export)
  │
  junos_optics_rx_power_dbm{device="dcf-glen8-evo.englab.juniper.net",interface="et-0/0/32",lane="0"} -2.28
  junos_optics_tx_power_dbm{device="dcf-glen8-evo.englab.juniper.net",interface="et-0/0/32",lane="0"} -2.32
  junos_optics_tx_bias_current_milliamps{device="dcf-glen8-evo.englab.juniper.net",interface="et-0/0/32",lane="0"} 6.157
  junos_optics_temperature_celsius{device="dcf-glen8-evo.englab.juniper.net",interface="et-0/0/32"} 45.5
  junos_interface_fec_ccw_rate{device="dcf-glen8-evo.englab.juniper.net",interface="et-0/0/32"} 0.0
  junos_interface_fec_nccw_rate{device="dcf-glen8-evo.englab.juniper.net",interface="et-0/0/32"} 0.0
  junos_interface_pre_fec_ber{device="dcf-glen8-evo.englab.juniper.net",interface="et-0/0/32"} 1.23e-10
  │
  ▼
Time Series Database (Prometheus)
  │
  └─ Stored with timestamps, indexed by labels
  └─ Scraped by Grafana for visualization
```

## Field Mapping Process

```
XML Path (from meta files)          →  JSON Field Name
────────────────────────────────────────────────────────

Interface Level (Thresholds & Current Values):
  laser-temperature-high-alarm      →  temperature_high_alarm
  module-temperature                →  temperature
  module-voltage                    →  voltage
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

Interface Statistics (FEC & Counters):
  fec-ccw                           →  fec_ccw (corrected codewords)
  fec-nccw                          →  fec_nccw (uncorrected codewords)
  fec-ccw-rate                      →  fec_ccw_rate
  fec-nccw-rate                     →  fec_nccw_rate
  pre-fec-ber                       →  pre_fec_ber
  histogram-bin-N                   →  histogram_bin_N (0-15)

Metadata Fields (from merge_metadata.py):
  System Info:
    hostname, model, version, serial_number
  
  Chassis/PIC Detail:
    vendor, part_number, serial_number (transceiver)
    wavelength, fiber_type, cable_type
    fpc, pic, port (hardware location)
```

## Execution Flow

```
1. Semaphore Runner (via docker-compose.yml)
   │
   ├─ Initialize run timestamp
   │    └─ Set dt=YYYY-MM-DD, hr=HH for partitioning
   │
   ├─ ansible-playbook junos_telemetry.yml -i inventory-shardN.yaml
   │
   ├─ Load inventory (shard-based for parallel execution)
   │    ├─ inventory-shard1.yaml: XAI devices (RMA testing)
   │    ├─ inventory-shard2.yaml: Regression lab devices
   │    └─ inventory-shard3.yaml: Production devices
   │
   ├─ Load rpc_commands.yml (4 RPC commands + parsers)
   │    ├─ system_information     → juniper/system_information
   │    ├─ chassis_inventory      → juniper/chassis_inventory
   │    ├─ optics_diagnostics     → juniper/optics_diagnostics
   │    └─ interface_statistics   → juniper/interface_statistics
   │
   ├─ For each device in shard:
   │    │
   │    ├─ Establish NETCONF connection
   │    │
   │    ├─ Execute RPC commands:
   │    │    ├─ get-system-information
   │    │    ├─ get-chassis-inventory
   │    │    ├─ get-interface-optics-diagnostics-information
   │    │    └─ get-interface-information (with interface filter)
   │    │
   │    ├─ Save raw XML → /tmp/semaphore/output/{device}_{command}_raw.xml
   │    │
   │    ├─ Parse each RPC output:
   │    │    ├─ Run parsers/juniper/{parser}.py
   │    │    │    --input {raw_xml}
   │    │    │    --output {metrics_json}
   │    │    │    --device {hostname}
   │    │    │    [--interfaces "et-0/0/32,et-0/0/33" if filter set]
   │    │    │
   │    │    └─ Output: {device}_{command}_metrics.json
   │    │
   │    ├─ Collect PIC details (transceiver metadata):
   │    │    └─ scripts/collect_pic_details.py
   │    │         --chassis-xml {chassis_raw.xml}
   │    │         --output {pic_detail_metrics.json}
   │    │
   │    ├─ Merge metadata:
   │    │    └─ parsers/juniper/merge_metadata.py
   │    │         --system-info {system_info.json}
   │    │         --chassis-inventory {chassis.json}
   │    │         --pic-detail {pic_detail.json}
   │    │         --optics-metrics {optics.json}
   │    │         → Enriched optics_diagnostics_metrics.json
   │    │
   │    ├─ Write per-device Parquet files (optional, deprecated):
   │    │    └─ scripts/write_to_parquet.py
   │    │         --input {metrics.json}
   │    │         --base-dir /tmp/semaphore/output/ml_data
   │    │         --metric-type {optical|interface_stats|pic_detail}
   │    │
   │    └─ Push to Prometheus Pushgateway (optional):
   │         └─ scripts/push_to_prometheus.py
   │              --pushgateway http://pushgateway:9091
   │              --job junos_telemetry
   │              --instance {device}
   │              --metrics-file {metrics.json}
   │              --format json
   │
   └─ Aggregate hourly Parquet files (second play, localhost):
        │
        ├─ scripts/write_hourly_parquet.py
        │    --metrics-dir /tmp/semaphore/output
        │    --base-dir /tmp/semaphore/raw_ml_data
        │    --runner-name $SEMAPHORE_RUNNER_NAME
        │    --partition-dir dt=YYYY-MM-DD/hr=HH
        │    --run-timestamp {unix_timestamp}
        │    --compression snappy
        │    │
        │    └─ Output:
        │         raw_ml_data/dt=YYYY-MM-DD/hr=HH/
        │           ├─ intf-dom/interface_dom_{timestamp}.parquet
        │           ├─ lane-dom/lane_dom_{timestamp}.parquet
        │           └─ intf-counters/interface_counters_{timestamp}.parquet
        │
        └─ Sync to S3 data lake:
             └─ community.aws.s3_sync
                  --bucket amzn-ds-s3-rrd
                  --file-root raw_ml_data/dt=YYYY-MM-DD/hr=HH/
                  --key-prefix datalake/dt=YYYY-MM-DD/hr=HH/
                  └─ Uploads all hourly Parquet files to S3
```

## File Organization

```
telemetry/
│
├── Configuration Files
│   ├── ansible/
│   │   ├── inventory-shard1.yaml      # XAI + Regression1 devices
│   │   ├── inventory-shard2.yaml      # Regression2 devices
│   │   ├── inventory-shard3.yaml      # Regression3 devices
│   │   ├── inventory.yml              # Legacy/local testing
│   │   ├── rpc_commands.yml           # RPC commands & parsers mapping
│   │   ├── ansible.cfg                # Ansible settings
│   │   ├── requirements.txt           # Python dependencies
│   │   ├── requirements.yml           # Ansible collection dependencies
│   │   └── group_vars/
│   │       ├── all/                   # AWS credentials (encrypted)
│   │       │   ├── vars.yml           # Variable references
│   │       │   └── vault.yml          # Encrypted AWS credentials
│   │       ├── xai/                   # XAI device credentials
│   │       ├── regression/            # Regression lab credentials
│   │       └── junos/                 # Production device credentials
│   └── infrastructure/
│       ├── docker-compose.yml         # Semaphore, Prometheus, Grafana
│       ├── deployment-config.yml      # VM topology & runner mapping
│       ├── deploy.sh                  # Centralized deployment script
│       ├── Makefile                   # Deployment shortcuts
│       ├── prometheus.yml             # Prometheus configuration
│       ├── env-files/
│       │   └── .env                   # Environment variables
│       └── mounts/                    # Docker volume mounts
│           ├── semaphore_runners/     # Runner certificates
│           ├── postgres_data/         # PostgreSQL data
│           ├── prometheus_data/       # Prometheus TSDB
│           ├── grafana_data/          # Grafana dashboards
│           ├── output/                # Temporary JSON/XML
│           └── raw_ml_data/           # Parquet files
│
├── Execution Layer
│   ├── ansible/
│   │   ├── junos_telemetry.yml        # Main playbook (2 plays)
│   │   └── demo.sh                    # Local test script
│
├── Processing Layer
│   ├── ansible/parsers/
│   │   ├── common/                    # Shared utilities
│   │   │   ├── xml_utils.py           # Namespace-aware XML parsing
│   │   │   ├── fiber_detection.py     # Fiber type classification
│   │   │   └── interface_mapping.py   # Interface normalization
│   │   ├── juniper/                   # Juniper-specific parsers
│   │   │   ├── system_information.py  # System metadata parser
│   │   │   ├── chassis_inventory.py   # Hardware inventory parser
│   │   │   ├── optics_diagnostics.py  # Optical metrics parser
│   │   │   ├── interface_statistics.py# Interface counters parser
│   │   │   └── merge_metadata.py      # Metadata merger
│   │   ├── template_parser.py         # Template for new parsers
│   │   └── test_data/                 # Sample data for testing
│
├── Integration & Export Layer
│   ├── ansible/scripts/
│   │   ├── collect_pic_details.py     # Collect transceiver details
│   │   ├── merge_metadata.py          # Merge system/chassis/PIC data
│   │   ├── write_to_parquet.py        # Per-device Parquet writer
│   │   ├── write_hourly_parquet.py    # Hourly aggregation + S3 sync
│   │   └── push_to_prometheus.py      # Prometheus integration
│
├── Runtime Output (created during execution)
│   ├── /tmp/semaphore/output/         # Temporary JSON/XML files
│   │   ├── {device}_system_information_raw.xml
│   │   ├── {device}_system_information_metrics.json
│   │   ├── {device}_chassis_inventory_raw.xml
│   │   ├── {device}_chassis_inventory_metrics.json
│   │   ├── {device}_optics_diagnostics_raw.xml
│   │   ├── {device}_optics_diagnostics_metrics.json
│   │   ├── {device}_interface_statistics_raw.xml
│   │   ├── {device}_interface_statistics_metrics.json
│   │   ├── {device}_pic_detail_metrics.json
│   │   └── ml_data/                   # Per-device Parquet (deprecated)
│   │
│   └── /tmp/semaphore/raw_ml_data/    # Hourly aggregated Parquet
│       └── dt=YYYY-MM-DD/
│           └── hr=HH/
│               ├── intf-dom/          # Interface-level DOM metrics
│               │   └── interface_dom_{timestamp}.parquet
│               ├── lane-dom/          # Lane-level DOM metrics
│               │   └── lane_dom_{timestamp}.parquet
│               └── intf-counters/     # Interface traffic counters
│                   └── interface_counters_{timestamp}.parquet
│
├── Cloud Storage
│   └── s3://amzn-ds-s3-rrd/datalake/ # AWS S3 data lake
│       └── dt=YYYY-MM-DD/hr=HH/       # Same structure as raw_ml_data
│
├── Analysis
│   └── analysis/
│       ├── telemetry_eda.ipynb        # Exploratory Data Analysis
│       └── csv_output/                # Analysis results
│
└── Documentation
    ├── README.md                      # Complete documentation
    ├── ARCHITECTURE.md                # This file
    ├── SUMMARY.md                     # Quick summary
    ├── IMPLEMENTATION_GUIDE.md        # Step-by-step guide
    ├── CHECKLIST.md                   # Implementation checklist
    ├── infrastructure/
    │   ├── DEPLOYMENT_GUIDE.md        # Deployment procedures
    │   └── README.md                  # Infrastructure overview
    └── docs/
        ├── ANSIBLE_VAULT_SETUP.md     # Credential management
        ├── S3_SYNC_SETUP.md           # AWS S3 data lake sync
        ├── SEMAPHORE_SETUP.md         # Semaphore orchestration
        ├── SEMAPHORE_RUNNER_SETUP.md  # Runner configuration
        ├── INTERFACE_FILTERING.md     # Interface filtering
        └── ML_DATA_COLLECTION.md      # ML data format and usage
```

## Infrastructure Deployment Architecture

### Overview

The infrastructure deployment system uses a centralized configuration approach with:
- **docker-compose.yml**: Service definitions with profiles for control plane and runners
- **deployment-config.yml**: Single source of truth for VM topology and runner mappings
- **deploy.sh**: Automated deployment script with SSH-based remote deployment
- **env-files/.env**: Consolidated environment variables for all services

### Multi-VM Deployment Topology

```
┌─────────────────────────────────────────────────────────────────────┐
│                      Local Development Machine                      │
│  ┌───────────────────────────────────────────────────────────────┐  │
│  │ telemetry/infrastructure/                                     │  │
│  │  ├── deploy.sh               (Deployment orchestration)       │  │
│  │  ├── deployment-config.yml   (VM topology config)            │  │
│  │  ├── docker-compose.yml      (Service definitions)           │  │
│  │  ├── env-files/.env          (Environment variables)         │  │
│  │  └── Makefile                (Deployment shortcuts)          │  │
│  └───────────────────────────────────────────────────────────────┘  │
│           │                                │                         │
│           │ SSH + rsync                    │ SSH + rsync             │
│           ▼                                ▼                         │
└───────────┼────────────────────────────────┼─────────────────────────┘
            │                                │
┌───────────▼──────────────────┐   ┌────────▼──────────────────────────┐
│ VM1: 10.221.80.101          │   │ VM2: 10.87.94.51                 │
│ User: ubuntu                 │   │ User: root                        │
│ Base: /home/ubuntu           │   │ Base: /root                       │
│                              │   │                                   │
│ ┌──────────────────────────┐ │   │ ┌──────────────────────────────┐ │
│ │   Control Plane          │ │   │ │   Remote Runners             │ │
│ │  (Profile: control)      │ │   │ │  (Profiles: runner02/03)     │ │
│ ├──────────────────────────┤ │   │ ├──────────────────────────────┤ │
│ │ • Semaphore UI (:3001)   │ │   │ │ • Semaphore Runner02         │ │
│ │ • PostgreSQL (:5432)     │ │   │ │   - Shard2: Regression2      │ │
│ │ • Prometheus (:9090)     │ │   │ │   - Tags: shard2,regression2 │ │
│ │ • Grafana (:3000)        │ │   │ │                              │ │
│ │ • Pushgateway (:9091)    │ │   │ │ • Semaphore Runner03         │ │
│ └──────────────────────────┘ │   │ │   - Shard3: GPU Fabric       │ │
│                              │   │ │   - Tags: shard3,gpu-fabric  │ │
│ ┌──────────────────────────┐ │   │ └──────────────────────────────┘ │
│ │   Local Runner           │ │   │                                   │
│ │  (Profile: runner01)     │ │   │ Docker Compose:                   │
│ ├──────────────────────────┤ │   │  docker compose --env-file        │
│ │ • Semaphore Runner01     │ │   │    env-files/.env                 │
│ │   - Shard1: XAI, Reg1    │ │   │    --profile runner02 up -d       │
│ │   - Tags: shard1,xai     │ │   │                                   │
│ └──────────────────────────┘ │   └───────────────────────────────────┘
│                              │
│ Docker Compose:              │
│  docker compose --env-file   │
│    env-files/.env            │
│    --profile control up -d   │
│    --profile runner01 up -d  │
└──────────────────────────────┘
```

### Deployment Flow

```
1. Local Machine
   └─ make deploy-runner02
       │
       ├─ Calls: ./deploy.sh deploy runner02
       │
       └─ deploy.sh execution:
           │
           ├─ Load deployment-config.yml
           │   └─ Read runner02 configuration:
           │        • vm_host: 10.87.94.51
           │        • user: root
           │        • base_path: /root
           │        • profile: runner02
           │
           ├─ Check if VM is remote
           │   └─ If remote (not 127.0.0.1/localhost):
           │
           ├─ Clean up old deployment
           │   └─ ssh root@10.87.94.51 "rm -rf /root/workspace/telemetry"
           │
           ├─ Create directories
           │   └─ ssh root@10.87.94.51 "mkdir -p /root/workspace/telemetry/..."
           │
           ├─ Sync infrastructure files
           │   └─ rsync -avz infrastructure/ root@10.87.94.51:/root/workspace/telemetry/infrastructure/
           │        • Includes: docker-compose.yml, env-files/, mounts/semaphore_runners/
           │        • Excludes: Large data dirs (raw_ml_data/, output/, postgres_data/)
           │
           ├─ Sync ansible requirements
           │   └─ rsync -avz ansible/requirements.txt root@10.87.94.51:/root/workspace/telemetry/ansible/
           │
           ├─ Execute remote deployment
           │   └─ ssh root@10.87.94.51 "
           │        export TELEMETRY_BASE=/root/workspace/telemetry
           │        export CLUSTER_NAME=telemetry-prod
           │        export RUNNER_NAME=telemetry-prod-runner02
           │        cd /root/workspace/telemetry/infrastructure
           │        docker compose --env-file env-files/.env --profile runner02 up -d
           │      "
           │
           └─ Report completion

2. Remote VM (10.87.94.51)
   │
   ├─ Docker Compose reads:
   │   ├─ env-files/.env (via --env-file flag)
   │   │    • RUNNER02_TOKEN=<encrypted_token>
   │   │    • RUNNER02_WEB_ROOT=http://10.221.80.101:3001
   │   └─ docker-compose.yml
   │        • Environment substitution: ${RUNNER02_TOKEN}
   │        • Profile: runner02
   │
   ├─ Start semaphore-runner02 container:
   │   ├─ Image: semaphoreui/runner:v2.16.47
   │   ├─ Environment:
   │   │    • SEMAPHORE_WEB_ROOT=http://10.221.80.101:3001
   │   │    • SEMAPHORE_RUNNER_TOKEN=<from_env>
   │   │    • SEMAPHORE_RUNNER_NAME=telemetry-prod-runner02
   │   ├─ Volumes:
   │   │    • Ansible requirements.txt
   │   │    • Runner certificates (runner2.key.pem)
   │   │    • Output directories
   │   └─ Connect to control plane
   │
   └─ Runner registers with Semaphore UI and enters ready state
```

> **Note**: For detailed configuration file structure and setup instructions, see [DEPLOYMENT_GUIDE.md](infrastructure/DEPLOYMENT_GUIDE.md#setting-up-deployment-configyml).

### Deploy Script Architecture

**deploy.sh** - Core Functions

```bash
# Query functions (use yq to read deployment-config.yml)
get_vm_host($target)           # Get VM IP for target (control/runner01/etc)
get_ssh_user($vm_host)         # Get SSH username for VM
get_base_path($vm_host)        # Get base directory path on VM
get_profile($target)           # Get docker-compose profile for target
is_local_vm($vm_host)          # Check if deployment is local or remote

# Deployment function
deploy_to_vm($vm_host, $profile, $compose_cmd)
  ├─ If local (127.0.0.1/localhost):
  │   └─ Run docker compose locally with --env-file flag
  │
  └─ If remote:
      ├─ Clean old files: rm -rf $base_path/workspace/telemetry
      ├─ Create directories: mkdir -p ...
      ├─ Sync infrastructure: rsync infrastructure/ to remote
      ├─ Sync ansible requirements: rsync ansible/requirements.txt
      └─ Execute remotely:
           ssh $user@$vm_host "
             export TELEMETRY_BASE=$base_path/workspace/telemetry
             export CLUSTER_NAME=$(yq .cluster_name config)
             export RUNNER_NAME=${CLUSTER_NAME}-${profile}
             cd $base_path/workspace/telemetry/infrastructure
             docker compose --env-file env-files/.env --profile $profile $compose_cmd
           "

# Main entry point
deploy($target, $action)       # Routes to deploy_to_vm with appropriate params

# Utility functions
logs($target)                  # View container logs
status()                       # Show deployment status across all VMs
health()                       # Health check for all services
```

### Key Design Decisions

1. **Single .env file**: Consolidated all environment variables into one file instead of VM-specific files
   - Simplifies management
   - Uses `--env-file` flag for variable substitution
   - No `env_file` directive in docker-compose.yml (only explicit `environment` mappings)

2. **Clean deployment**: Removes entire telemetry directory before each deployment
   - Prevents stale files
   - Ensures clean state
   - Faster than selective sync

3. **Selective rsync**: Excludes large data directories
   - Syncs code, config, and certificates
   - Excludes: raw_ml_data/, output/, postgres_data/, prometheus_data/, grafana_data/
   - Keeps certificate files: mounts/semaphore_runners/*.pem

4. **Environment variable passing**: Three-layer approach
   - Shell exports: TELEMETRY_BASE, CLUSTER_NAME, RUNNER_NAME
   - .env file: RUNNER*_TOKEN, RUNNER*_WEB_ROOT, SEMAPHORE_WEB_ROOT, PROMETHEUS_PUSHGATEWAY
   - docker-compose.yml: Environment substitution with ${VARIABLE}
   - Runners inherit PROMETHEUS_PUSHGATEWAY for Ansible playbook access

5. **Profile-based deployment**: Uses docker-compose profiles for service grouping
   - control: Control plane services
   - runner01/02/03: Individual runners
   - all-runners: All runners together
   - all: Everything

### Runner Registration Process

```
1. Generate Private Key
   └─ openssl genrsa -out infrastructure/mounts/semaphore_runners/runner2.key.pem 2048

2. Enter Control Plane Container
   └─ docker exec -it semaphore bash

3. Run Registration Command
   └─ semaphore runner setup --config /etc/semaphore_runners/runner2-config.json
       ├─ Prompts:
       │   • Semaphore server URL: http://10.221.80.101:3001
       │   • Store token in external file: no
       │   • Have runner token: yes
       │   • Runner token: runnertoken12345 (from .env RUNNER_TOKEN)
       │   • Have private key: yes
       │   • Private key path: /etc/semaphore_runners/runner2.key.pem
       │
       └─ Output:
           • Configuration written to runner2-config.json
           • Generates encrypted token (RUNNER02_TOKEN)

4. Update .env File
   └─ Add generated token:
       RUNNER02_TOKEN=<encrypted_token_from_config>

5. Deploy Runner
   └─ make deploy-runner02
       └─ Runner connects to control plane and enters ready state

6. Verify in UI
   └─ Semaphore UI → Settings → Runners
       └─ Runner appears as "Connected"
```

## Parser Internal Architecture

```
Common Utilities (parsers/common/)
│
├── xml_utils.py
│   ├── strip_namespace()           # Remove XML namespace prefixes
│   ├── findall_ns()                # Find elements ignoring namespace
│   ├── find_ns()                   # Find single element
│   ├── findtext_ns()               # Get text ignoring namespace
│   └── findall_recursive_ns()      # Recursive search
│
├── fiber_detection.py
│   ├── detect_fiber_type()         # Classify fiber from metadata
│   │    ├─ Parse wavelength (850nm, 1310nm, 1550nm)
│   │    ├─ Parse cable_type (SR4, LR4, ER4, ZR)
│   │    └─ Return: SM (single-mode), MM (multi-mode), or Unknown
│   └── get_wavelength()            # Extract wavelength from part number
│
└── interface_mapping.py
    ├── map_interface_name()        # Normalize interface names
    │    ├─ et-0/0/32:0 → et-0/0/32
    │    ├─ xe-0/0/0 → xe-0/0/0
    │    └─ Handle port:channel notation
    └── parse_interface_location()  # Extract FPC/PIC/port numbers

Juniper Parsers (parsers/juniper/)
│
├── system_information.py
│   └── parse_system_information()
│        ├─ Extract: hostname, model, version
│        ├─ Extract: serial_number
│        └─ Return: {hostname, model, version, serial_number, timestamp}
│
├── chassis_inventory.py
│   └── parse_chassis_inventory()
│        ├─ Find all <chassis-module> entries
│        ├─ For each transceiver (name starts with "Xcvr"):
│        │    ├─ Extract interface name
│        │    ├─ Extract vendor, part_number, serial_number
│        │    └─ Build transceivers dict
│        └─ Return: {serial_number, transceivers{if_name: {...}}}
│
├── optics_diagnostics.py
│   └── parse_optical_diagnostics()
│        ├─ Parse XML with namespace handling
│        ├─ Find all physical interfaces
│        ├─ For each interface:
│        │    ├─ Extract interface-level metrics:
│        │    │    • temperature, voltage, status
│        │    │    • alarm/warning thresholds
│        │    ├─ Extract lane metrics:
│        │    │    • For each lane: rx_power, tx_power, tx_bias
│        │    │    • Apply numeric value extraction
│        │    └─ Apply interface filtering (if specified)
│        └─ Return: {interfaces: [...], lanes: [...]}
│
├── interface_statistics.py
│   └── parse_interface_statistics()
│        ├─ Find all physical interfaces
│        ├─ For each interface:
│        │    ├─ Extract basic info: admin_status, oper_status, speed
│        │    ├─ Extract FEC counters:
│        │    │    • fec_ccw, fec_nccw (cumulative)
│        │    │    • fec_ccw_rate, fec_nccw_rate (from device)
│        │    ├─ Extract FEC histogram (bins 0-15):
│        │    │    • histogram_bin_N (live + harvest)
│        │    │    • histogram_bin_N_live, histogram_bin_N_harvest
│        │    ├─ Extract pre-FEC BER
│        │    ├─ Extract traffic stats: input_bps, output_bps, etc.
│        │    └─ Apply interface filtering (if specified)
│        └─ Return: {if_name: {metrics}, ...}
│
└── merge_metadata.py
     └── merge_metadata()
          ├─ Load system_info.json
          ├─ Load chassis_inventory.json
          ├─ Load pic_detail.json (if available)
          ├─ Load optics_diagnostics.json
          ├─ For each interface in optics data:
          │    ├─ Add system metadata: hostname, model, version
          │    ├─ Add chassis metadata: device_serial
          │    ├─ Add transceiver metadata:
          │    │    • vendor, part_number, serial_number
          │    │    • wavelength, fiber_type, cable_type
          │    │    • fpc, pic, port
          │    └─ Normalize interface names
          └─ Write enriched optics_diagnostics_metrics.json

Scripts (ansible/scripts/)
│
├── collect_pic_details.py
│   └── collect_pic_details()
│        ├─ Parse chassis_inventory XML for FPC/PIC slots
│        ├─ For each FPC/PIC with transceivers:
│        │    ├─ Connect via NETCONF
│        │    ├─ Execute: show chassis pic fpc-slot X pic-slot Y
│        │    ├─ Parse transceiver details:
│        │    │    • vendor, part_number, serial_number
│        │    │    • wavelength, cable_type
│        │    └─ Apply fiber type detection
│        └─ Return: {if_name: {vendor, part_number, ...}}
│
├── write_to_parquet.py (deprecated - per-device files)
│   └── write_metrics_to_parquet()
│        ├─ Load metrics JSON
│        ├─ Convert to pandas DataFrame
│        ├─ Partition by: dt=YYYY-MM-DD/device=hostname/
│        └─ Write Parquet with pyarrow compression
│
├── write_hourly_parquet.py
│   └── write_hourly_parquet()
│        ├─ Scan /tmp/semaphore/output/ for all JSON files
│        ├─ Aggregate by metric type:
│        │    ├─ intf-dom: interface-level DOM metrics
│        │    ├─ lane-dom: lane-level DOM metrics
│        │    └─ intf-counters: interface statistics
│        ├─ Add metadata:
│        │    • run_timestamp (unix timestamp)
│        │    • runner_name (Semaphore runner ID)
│        │    • timestamp (collection time)
│        ├─ Write to partition: dt=YYYY-MM-DD/hr=HH/
│        └─ Snappy compression for efficient storage
│
└── push_to_prometheus.py
     └── push_metrics_to_prometheus()
          ├─ Load JSON metrics
          ├─ Convert to Prometheus line protocol:
          │    ├─ Build label set: {job, instance, device, interface, lane}
          │    ├─ Generate metric lines for each measurement
          │    └─ Format: junos_{metric}{{labels}} value
          └─ POST to Pushgateway at /metrics/job/{job}/instance/{instance}
```

## Prometheus Push Architecture

```
push_to_prometheus.py
│
├── JSON to Prometheus Conversion
│   └── json_to_prometheus()
│        │
│        ├─ Read JSON metrics file
│        │    ├─ optics_diagnostics: {interfaces: [...], lanes: [...]}
│        │    └─ interface_statistics: {if_name: {...}, ...}
│        │
│        ├─ For optics lanes:
│        │    ├─ Build label set
│        │    │   {job, instance, device, interface, lane}
│        │    │
│        │    └─ Generate metric lines:
│        │         junos_optics_rx_power_dbm{{labels}} value
│        │         junos_optics_tx_power_dbm{{labels}} value
│        │         junos_optics_tx_bias_current_milliamps{{labels}} value
│        │         junos_optics_temperature_celsius{{labels}} value
│        │
│        └─ For interface statistics:
│             ├─ Build label set
│             │   {job, instance, device, interface}
│             │
│             └─ Generate metric lines:
│                  junos_interface_fec_ccw{{labels}} value
│                  junos_interface_fec_nccw{{labels}} value
│                  junos_interface_fec_ccw_rate{{labels}} value
│                  junos_interface_fec_nccw_rate{{labels}} value
│                  junos_interface_pre_fec_ber{{labels}} value
│                  junos_interface_histogram_bin_N{{labels}} value
│
├── Push Logic
│   └── push_metrics()
│        │
│        ├─ Read metrics file
│        ├─ Convert JSON to Prometheus format
│        │
│        └─ POST to Pushgateway
│             URL: {pushgateway}/metrics/job/{job}/instance/{instance}
│             Body: Prometheus line protocol (plain text)
│             Headers: Content-Type: text/plain
│
└── CLI Interface
    └── main()
         ├─ Parse arguments
         │    --pushgateway: Pushgateway URL
         │    --job: Job label
         │    --instance: Instance label
         │    --metrics-file: JSON file to push
         │    --format: json (fixed)
         │
         └─ Call push_metrics()
```

## Extension Points

```
Adding New RPC Commands:

1. Edit rpc_commands.yml
   └─ Add new command with parser name:
      - name: my_new_command
        rpc: get-my-new-rpc
        parser: juniper/my_new_parser
        description: "Collect new metrics"

2. Create parsers/juniper/my_new_parser.py
   └─ Based on template_parser.py or existing parsers
   └─ Implement parse function:
        def parse_my_new_rpc(xml_content, device=None, interfaces=None):
            # Parse XML using common/xml_utils.py
            # Extract metrics
            # Return structured JSON
            return {"metrics": [...]}

3. (Optional) Create test data
   └─ parsers/test_data/my_new_command_response.xml
   └─ parsers/test_data/my_new_command_expected.json

4. (Optional) Update write_hourly_parquet.py
   └─ Add new metric type if needed for ML data lake

5. Run playbook
   └─ Automatically processes new command for all devices
   └─ Creates {device}_my_new_command_raw.xml
   └─ Creates {device}_my_new_command_metrics.json
   └─ Pushes to Prometheus (if enabled)

Adding New Devices:

1. Add to inventory file (shard-based)
   └─ inventory-shard1.yaml / shard2 / shard3
   └─ Specify credentials in group_vars/{group}/vault.yml

2. (Optional) Set device-specific variables
   └─ interface_filter: "et-0/0/32,et-0/0/33"
   └─ hardware_model: "qfx5220-32cd"

3. Run playbook with shard inventory
   └─ ansible-playbook junos_telemetry.yml -i inventory-shardN.yaml

Adding New Parsers for Different Vendors:

1. Create vendor directory
   └─ parsers/{vendor}/

2. Create parser scripts
   └─ parsers/{vendor}/parser_name.py

3. Update rpc_commands.yml
   └─ parser: {vendor}/parser_name

4. (Optional) Create vendor-specific utilities
   └─ parsers/{vendor}/common/
        ├─ xml_utils.py
        └─ field_mappings.py

Extending ML Data Collection:

1. Add new metrics to existing parsers
   └─ Update parse functions in parsers/juniper/

2. Update merge_metadata.py
   └─ Add new metadata fields to merge

3. Update write_hourly_parquet.py
   └─ Add new columns to DataFrames
   └─ Create new metric types if needed

4. Update S3 sync configuration
   └─ Ensure new partition paths are synced

Semaphore Parallel Execution:

1. Shard devices across inventories
   └─ inventory-shard1.yaml: 20 devices
   └─ inventory-shard2.yaml: 20 devices
   └─ inventory-shard3.yaml: 20 devices

2. Configure Semaphore tasks
   └─ Task 1: Run with inventory-shard1.yaml
   └─ Task 2: Run with inventory-shard2.yaml
   └─ Task 3: Run with inventory-shard3.yaml

3. Configure Semaphore runners
   └─ 3 parallel runners (one per shard)
   └─ Set SEMAPHORE_RUNNER_NAME env variable

4. Hourly aggregation
   └─ Each runner writes to separate partition
   └─ runner_name field tracks source runner
   └─ Single S3 sync uploads all runner data
```

## ML Data Pipeline Architecture

```
Collection → Aggregation → Storage → Analysis

┌─────────────────────────────────────────────────────────────────┐
│ Step 1: Per-Device Collection (Ansible Play 1)                 │
│                                                                 │
│ For each device in shard:                                      │
│   ├─ Collect RPC data via NETCONF                             │
│   ├─ Parse to JSON metrics                                    │
│   └─ Write to /tmp/semaphore/output/{device}_{metric}.json    │
└─────────────────────────────────────────────────────────────────┘
                            ↓
┌─────────────────────────────────────────────────────────────────┐
│ Step 2: Hourly Aggregation (Ansible Play 2)                    │
│                                                                 │
│ write_hourly_parquet.py:                                        │
│   ├─ Scan all JSON files in /tmp/semaphore/output/            │
│   ├─ Combine into 3 DataFrames:                               │
│   │    ├─ intf-dom: Interface-level DOM metrics               │
│   │    ├─ lane-dom: Lane-level DOM metrics                    │
│   │    └─ intf-counters: Interface statistics & FEC           │
│   ├─ Add metadata:                                             │
│   │    ├─ run_timestamp (Unix timestamp of collection)        │
│   │    ├─ runner_name (Semaphore runner ID)                   │
│   │    └─ timestamp (Per-device collection time)              │
│   └─ Write to raw_ml_data/dt=YYYY-MM-DD/hr=HH/                │
│        ├─ intf-dom/interface_dom_{timestamp}.parquet          │
│        ├─ lane-dom/lane_dom_{timestamp}.parquet               │
│        └─ intf-counters/interface_counters_{timestamp}.parquet│
│   Compression: Snappy (efficient for analytics)               │
└─────────────────────────────────────────────────────────────────┘
                            ↓
┌─────────────────────────────────────────────────────────────────┐
│ Step 3: S3 Data Lake Sync (Ansible Play 2)                     │
│                                                                 │
│ community.aws.s3_sync:                                          │
│   ├─ Source: raw_ml_data/dt=YYYY-MM-DD/hr=HH/                 │
│   ├─ Destination: s3://amzn-ds-s3-rrd/datalake/               │
│   ├─ Preserves Hive partitioning (dt=, hr=)                   │
│   └─ Credentials from group_vars/all/vault.yml                │
└─────────────────────────────────────────────────────────────────┘
                            ↓
┌─────────────────────────────────────────────────────────────────┐
│ Step 4: ML Analysis (analysis/telemetry_eda.ipynb)             │
│                                                                 │
│ Read Parquet files with Pandas/PyArrow:                        │
│   ├─ Load specific partitions (dt=, hr=)                      │
│   ├─ Query with predicate pushdown                            │
│   ├─ Join across metric types:                                │
│   │    • Correlate FEC errors with optical power              │
│   │    • Analyze temperature vs. error rates                  │
│   │    • Track transceiver degradation over time              │
│   └─ Train ML models for predictive maintenance               │
└─────────────────────────────────────────────────────────────────┘
```

### Parquet Schema Details

**intf-dom/** (Interface-level DOM metrics)
```
Columns:
  - if_name (string): Interface name (e.g., "et-0/0/32")
  - device (string): Device IP or hostname
  - hostname (string): Device FQDN
  - model (string): Device model (e.g., "qfx5220-32cd")
  - temperature (float): Module temperature (°C)
  - voltage (float): Module voltage (V)
  - status (string): Operational status (OK, Warning, Alarm)
  - vendor (string): Transceiver vendor
  - part_number (string): Transceiver part number
  - serial_number (string): Transceiver serial
  - wavelength (string): Wavelength (e.g., "1310nm")
  - fiber_type (string): Fiber type (SM, MM)
  - cable_type (string): Cable type (e.g., "100GBASE-LR4")
  - temperature_high_alarm (float): High temp threshold
  - voltage_high_alarm (float): High voltage threshold
  - timestamp (int64): Collection timestamp (Unix)
  - run_timestamp (int64): Playbook run timestamp
  - runner_name (string): Semaphore runner ID

Partitions: dt=YYYY-MM-DD/hr=HH/
```

**lane-dom/** (Lane-level DOM metrics)
```
Columns:
  - if_name (string): Interface name
  - lane (int): Lane number (0-7)
  - device (string): Device IP/hostname
  - hostname (string): Device FQDN
  - model (string): Device model
  - rx_power (float): RX power (dBm)
  - rx_power_mw (float): RX power (mW)
  - tx_power (float): TX power (dBm)
  - tx_power_mw (float): TX power (mW)
  - tx_bias (float): Laser bias current (mA)
  - temperature (float): Module temperature (°C)
  - voltage (float): Module voltage (V)
  - vendor (string): Transceiver vendor
  - part_number (string): Transceiver part number
  - wavelength (string): Wavelength
  - fiber_type (string): Fiber type
  - cable_type (string): Cable type
  - timestamp (int64): Collection timestamp
  - run_timestamp (int64): Playbook run timestamp
  - runner_name (string): Semaphore runner ID

Partitions: dt=YYYY-MM-DD/hr=HH/
```

**intf-counters/** (Interface statistics & FEC)
```
Columns:
  - if_name (string): Interface name
  - device (string): Device IP/hostname
  - hostname (string): Device FQDN
  - model (string): Device model
  - admin_status (string): Admin status (up, down)
  - oper_status (string): Operational status
  - speed_bps (int64): Interface speed (bps)
  - fec_ccw (int64): FEC corrected codewords (cumulative)
  - fec_nccw (int64): FEC uncorrected codewords (cumulative)
  - fec_ccw_rate (float): Corrected error rate (/s)
  - fec_nccw_rate (float): Uncorrected error rate (/s)
  - pre_fec_ber (string): Pre-FEC BER (scientific notation)
  - histogram_bin_0..15 (int64): FEC histogram bins
  - histogram_bin_0..15_live (int64): Live FEC errors
  - histogram_bin_0..15_harvest (int64): Harvest FEC errors
  - input_bps (int64): Input traffic rate
  - output_bps (int64): Output traffic rate
  - input_pps (int64): Input packet rate
  - output_pps (int64): Output packet rate
  - timestamp (int64): Collection timestamp
  - run_timestamp (int64): Playbook run timestamp
  - runner_name (string): Semaphore runner ID

Partitions: dt=YYYY-MM-DD/hr=HH/
```

### ML Use Cases

**1. Transceiver Degradation Prediction**
- **Target**: `fec_nccw_rate` (uncorrected errors)
- **Features**: 
  - FEC metrics: `fec_ccw_rate`, `histogram_bin_*`, `pre_fec_ber`
  - Optical power: `rx_power`, `tx_power`
  - Environmental: `temperature`, `tx_bias`
  - Metadata: `vendor`, `part_number`, `cable_type`, `fiber_type`
- **Model**: Time-series forecasting (LSTM, Prophet, XGBoost)

**2. Anomaly Detection**
- **Input**: All DOM metrics + FEC counters
- **Method**: Isolation Forest, Autoencoder
- **Output**: Anomaly score per interface

**3. Failure Prediction**
- **Target**: Binary (will fail in next N hours)
- **Features**: Rate of change in FEC errors, optical power drift
- **Model**: Gradient boosting (XGBoost, LightGBM)

**4. RMA Correlation Analysis**
- **XAI Shard**: Devices under RMA testing
- **Compare**: Pre-RMA vs. post-RMA metrics
- **Identify**: Common failure patterns

### Data Lake Query Examples

**Pandas/PyArrow:**
```python
import pandas as pd

# Read single hour
df = pd.read_parquet('s3://amzn-ds-s3-rrd/datalake/dt=2026-02-03/hr=15/lane-dom/')

# Read date range with predicate pushdown
df = pd.read_parquet(
    's3://amzn-ds-s3-rrd/datalake/',
    filters=[('dt', '>=', '2026-02-01'), ('dt', '<=', '2026-02-03')]
)

# Join interface counters with lane DOM
counters = pd.read_parquet('.../intf-counters/')
lanes = pd.read_parquet('.../lane-dom/')
joined = counters.merge(lanes, on=['if_name', 'device', 'timestamp'])
```

**AWS Athena:**
```sql
CREATE EXTERNAL TABLE lane_dom (
  if_name STRING,
  lane INT,
  device STRING,
  rx_power DOUBLE,
  tx_power DOUBLE,
  ...
)
PARTITIONED BY (dt STRING, hr STRING)
STORED AS PARQUET
LOCATION 's3://amzn-ds-s3-rrd/datalake/';

-- Query specific partition
SELECT * FROM lane_dom
WHERE dt = '2026-02-03' AND hr = '15'
  AND fec_nccw_rate > 0;
```
