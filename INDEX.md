# Junos Optical Telemetry Collection System

## 📋 Quick Navigation

| Document | Purpose | Audience |
|----------|---------|----------|
| **[README.md](README.md)** | Complete system documentation | All users |
| **[SUMMARY.md](SUMMARY.md)** | Quick overview and setup | New users |
| **[IMPLEMENTATION_GUIDE.md](IMPLEMENTATION_GUIDE.md)** | Step-by-step deployment | Implementers |
| **[ARCHITECTURE.md](ARCHITECTURE.md)** | System design and data flow | Architects/Developers |
| **[CHECKLIST.md](CHECKLIST.md)** | Pre-production validation | Operations |
| **[parsers/test_data/README.md](parsers/test_data/README.md)** | Testing documentation | Testers/Developers |

## 🚀 Quick Start

```bash
# 1. Install dependencies
pip install -r requirements.txt
ansible-galaxy collection install junipernetworks.junos

# 2. Run tests
cd parsers && python3 test_optics_diagnostics.py && cd ..

# 3. Run demo
./demo.sh

# 4. Execute playbook
ansible-playbook -i inventory.yml junos_telemetry.yml
```

## 📁 Project Structure

```
telemetry/
├── 📄 Configuration
│   ├── inventory.yml              # Device inventory
│   ├── rpc_commands.yml           # RPC commands config
│   ├── ansible.cfg                # Ansible settings
│   └── requirements.txt           # Python dependencies
│
├── 🎯 Execution
│   ├── junos_telemetry.yml        # Main playbook
│   └── demo.sh                    # Demo script
│
├── 🔧 Parsers
│   ├── optics_diagnostics.py      # Optical metrics parser
│   ├── template_parser.py         # Parser template
│   ├── test_optics_diagnostics.py # Test suite
│   └── test_data/                 # Test data and samples
│
├── 🔌 Scripts
│   └── push_to_prometheus.py      # Prometheus integration
│
├── 📊 Output (runtime)
│   └── output/                    # Generated files
│
└── 📚 Documentation
    ├── README.md                  # Main documentation
    ├── SUMMARY.md                 # Quick summary
    ├── IMPLEMENTATION_GUIDE.md    # Deployment guide
    ├── ARCHITECTURE.md            # System architecture
    ├── CHECKLIST.md               # Pre-flight checklist
    └── INDEX.md                   # This file
```

## 🎯 What It Does

1. **Connects** to Junos devices via NETCONF
2. **Executes** RPC commands to get optical interface diagnostics
3. **Parses** XML responses into structured JSON
4. **Extracts** per-interface thresholds and per-lane measurements
5. **Exports** to Prometheus for monitoring and analytics

## 📊 Data Output

### Interface Metrics (Thresholds)
- Temperature alarm/warn limits
- Voltage alarm/warn limits
- Power alarm/warn limits
- Bias current alarm/warn limits

### Lane Metrics (Measurements)
- RX power (mW and dBm)
- TX power (mW and dBm)
- TX bias current (mA)

## 🔑 Key Features

✅ **XML Namespace Handling** - Works with any Junos version  
✅ **Field Mapping System** - XPath to JSON field mappings  
✅ **Comprehensive Testing** - 8 test cases covering all scenarios  
✅ **Extensible Design** - Easy to add new RPC commands  
✅ **Metadata Support** - Inject custom fields  
✅ **Prometheus Ready** - Direct push to Pushgateway  
✅ **Production Ready** - Error handling, logging, documentation  

## 📖 Documentation Guide

### For First-Time Users
1. Start with **[SUMMARY.md](SUMMARY.md)** for overview
2. Follow **[IMPLEMENTATION_GUIDE.md](IMPLEMENTATION_GUIDE.md)** Phase 1
3. Run `./demo.sh` to see it in action
4. Read **[README.md](README.md)** for details

### For Implementers
1. Review **[IMPLEMENTATION_GUIDE.md](IMPLEMENTATION_GUIDE.md)** all phases
2. Complete **[CHECKLIST.md](CHECKLIST.md)** items
3. Understand **[ARCHITECTURE.md](ARCHITECTURE.md)**
4. Test with sample data first

### For Developers
1. Study **[ARCHITECTURE.md](ARCHITECTURE.md)** for design
2. Review `parsers/optics_diagnostics.py` code
3. Read **[parsers/test_data/README.md](parsers/test_data/README.md)**
4. Use `template_parser.py` for new parsers

### For Operators
1. Review **[README.md](README.md)** usage section
2. Complete **[CHECKLIST.md](CHECKLIST.md)**
3. Bookmark troubleshooting sections
4. Set up monitoring and alerts

## 🔬 Testing

```bash
# Run parser tests
cd parsers
python3 test_optics_diagnostics.py

# Run full demo
./demo.sh

# Test specific components
python3 parsers/optics_diagnostics.py --help
python3 scripts/push_to_prometheus.py --help
```

## 🛠️ Common Tasks

### Add a New Device
Edit `inventory.yml`:
```yaml
junos_devices:
  hosts:
    new-device:
      ansible_user: user
      ansible_password: pass
```

### Add a New RPC Command
1. Edit `rpc_commands.yml`
2. Create `parsers/new_parser.py`
3. Test with sample data
4. Run playbook

### Schedule Collection
```bash
# Cron (every 5 minutes)
*/5 * * * * cd /path/to/telemetry && ansible-playbook -i inventory.yml junos_telemetry.yml
```

### View Collected Data
```bash
# Raw XML
cat output/*_raw.xml

# Parsed JSON
cat output/*_metrics.json | python3 -m json.tool

# Prometheus metrics
curl http://localhost:9091/metrics | grep junos_optics
```

## 🐛 Troubleshooting

Quick diagnostics:

```bash
# Test device connectivity
ansible -i inventory.yml junos_devices -m ping

# Check NETCONF
ssh root@10.209.3.39 "show system services | match netconf"

# Validate parser
python3 parsers/optics_diagnostics.py \
  --input parsers/test_data/optics_rpc_response.xml \
  --output /tmp/test.json \
  --device test \
  --format json

# Check Prometheus
curl http://localhost:9091/metrics | grep junos
```

See **[README.md](README.md)** Troubleshooting section for detailed help.

## 📈 Metrics Reference

### Available Metrics

| Metric | Description | Labels |
|--------|-------------|--------|
| `junos_optics_rx_power_dbm` | Receive power in dBm | device, interface, lane |
| `junos_optics_rx_power_milliwatts` | Receive power in mW | device, interface, lane |
| `junos_optics_tx_power_dbm` | Transmit power in dBm | device, interface, lane |
| `junos_optics_tx_power_milliwatts` | Transmit power in mW | device, interface, lane |
| `junos_optics_tx_bias_current_milliamps` | TX bias current in mA | device, interface, lane |

### Example Queries

```promql
# Average RX power per interface
avg by (interface) (junos_optics_rx_power_dbm)

# Low power alerts
junos_optics_rx_power_dbm < -10

# High bias current
junos_optics_tx_bias_current_milliamps > 80

# Per-device summary
sum by (device) (junos_optics_rx_power_dbm)
```

## 🔐 Security

- Use Ansible Vault for credentials
- Restrict NETCONF access by IP
- Use service accounts, not root
- Enable TLS for Prometheus
- Regular credential rotation

See **[IMPLEMENTATION_GUIDE.md](IMPLEMENTATION_GUIDE.md)** Security section.

## 📞 Support

### Resources
- **Documentation**: See files listed above
- **Test Data**: `parsers/test_data/`
- **Demo**: `./demo.sh`
- **Logs**: `output/` directory

### Getting Help
1. Check the relevant documentation file
2. Review error messages in output
3. Run tests to validate setup
4. Check troubleshooting sections

## 🎓 Learning Path

### Beginner
1. Read **[SUMMARY.md](SUMMARY.md)**
2. Run `./demo.sh`
3. Review output files
4. Understand data flow

### Intermediate  
1. Read **[IMPLEMENTATION_GUIDE.md](IMPLEMENTATION_GUIDE.md)**
2. Deploy to test environment
3. Add a new device
4. Configure Prometheus

### Advanced
1. Study **[ARCHITECTURE.md](ARCHITECTURE.md)**
2. Create custom parser
3. Add new RPC commands
4. Extend metadata fields
5. Build custom dashboards

## ✅ Success Criteria

- [x] All tests pass (8/8)
- [x] Parser generates valid JSON
- [x] Sample data parses correctly
- [ ] Deployed to test environment
- [ ] Connected to real device
- [ ] Metrics in Prometheus
- [ ] Grafana dashboards created
- [ ] Scheduled collection running
- [ ] Team trained

## 📝 Version History

- **v1.0** - Initial release
  - Optical diagnostics parser
  - JSON output format
  - Prometheus integration
  - Comprehensive testing
  - Full documentation

## 🚦 Status

| Component | Status | Notes |
|-----------|--------|-------|
| Parser | ✅ Ready | All tests pass |
| Playbook | ✅ Ready | Tested with sample data |
| Tests | ✅ Complete | 8/8 passing |
| Documentation | ✅ Complete | All guides written |
| Demo | ✅ Working | Demonstrates all features |

## 📅 Recommended Timeline

- **Week 1**: Setup and testing (Phases 1-2)
- **Week 2**: Integration (Phase 3)
- **Week 3**: Visualization (Phase 4)
- **Week 4**: Production deployment (Phase 5)

## 🎯 Next Steps

1. Review **[CHECKLIST.md](CHECKLIST.md)**
2. Follow **[IMPLEMENTATION_GUIDE.md](IMPLEMENTATION_GUIDE.md)**
3. Start with test environment
4. Gradually add production devices
5. Build monitoring and alerts

---

**Need help?** Start with the document that matches your role:
- 👤 **User**: [README.md](README.md)
- 🔧 **Implementer**: [IMPLEMENTATION_GUIDE.md](IMPLEMENTATION_GUIDE.md)
- 🏗️ **Architect**: [ARCHITECTURE.md](ARCHITECTURE.md)
- ✅ **Operator**: [CHECKLIST.md](CHECKLIST.md)
