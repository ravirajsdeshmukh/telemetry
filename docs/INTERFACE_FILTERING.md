# Interface Filtering

## Overview

The telemetry collection system supports filtering to monitor only specific interfaces. This is useful when you want to:
- Reduce metric volume for large deployments
- Monitor only critical interfaces
- Test with specific interfaces before full rollout
- Focus on interfaces with known issues

## Configuration Methods

### Method 1: Command Line (Recommended for Testing)

Pass the `interface_filter` variable when running the playbook:

```bash
# Single interface
ansible-playbook -i inventory.yml junos_telemetry.yml \
  -e 'interface_filter="et-0/0/32"'

# Multiple interfaces (comma-separated)
ansible-playbook -i inventory.yml junos_telemetry.yml \
  -e 'interface_filter="et-0/0/32,et-0/0/33,et-0/0/48"'
```

### Method 2: Playbook Variables (Recommended for Production)

Edit the `junos_telemetry.yml` file and set the `interface_filter` variable:

```yaml
vars:
  netconf_port: 830
  output_dir: "./output"
  prometheus_pushgateway: "http://localhost:9091"
  rpc_config_file: "rpc_commands.yml"
  interface_filter: "et-0/0/32,et-0/0/33"  # Comma-separated list
```

### Method 3: Inventory Variables (Per-Device Filtering)

**This is the recommended method for production environments with different monitoring needs per device.**

For device-specific filtering, add the `interface_filter` variable to each device in your inventory. Device-specific filters take precedence over the global filter.

```yaml
junos_devices:
  hosts:
    10.209.3.39:
      ansible_user: root
      ansible_password: yourpassword
      interface_filter: "et-0/0/32,et-0/0/48"  # Only these interfaces for this device
    
    10.83.6.222:
      ansible_user: root
      ansible_password: yourpassword
      interface_filter: "et-0/0/10,et-0/0/20"  # Different interfaces for this device
    
    192.168.1.1:
      ansible_user: root
      ansible_password: yourpassword
      # No interface_filter set - uses global filter or monitors all interfaces
```

**Precedence Order:**
1. **Device-specific filter** (in inventory.yml) - Highest priority
2. **Global filter** (in junos_telemetry.yml vars or command line) - Medium priority  
3. **No filter** - Default, monitors all interfaces

## Default Behavior

If `interface_filter` is:
- **Not set**: All interfaces are monitored (default)
- **Empty string** (`""`): All interfaces are monitored
- **Set with values**: Only specified interfaces are monitored

## Direct Parser Usage

You can also use the interface filter directly with the parser script:

```bash
# Filter for specific interfaces
python3 parsers/optics_diagnostics.py \
  --input raw_output.xml \
  --output metrics.json \
  --device 10.209.3.39 \
  --interfaces "et-0/0/32,et-0/0/33"

# Process all interfaces (omit --interfaces)
python3 parsers/optics_diagnostics.py \
  --input raw_output.xml \
  --output metrics.json \
  --device 10.209.3.39
```

## Validation

To verify which interfaces are being monitored:

```bash
# Check the JSON output
cat output/DEVICE_optics_diagnostics_metrics.json | jq '.interfaces[].if_name'

# Check the playbook output for filtering message
# You should see: "Filtering for interfaces: et-0/0/32,et-0/0/33"
```

## Use Cases

### 1. Testing New Deployment
Monitor a single interface to validate the setup:
```bash
ansible-playbook -i inventory.yml junos_telemetry.yml \
  -e 'interface_filter="et-0/0/32"'
```

### 2. Critical Interfaces Only
Configure permanent monitoring for business-critical interfaces:
```yaml
# In junos_telemetry.yml
vars:
  interface_filter: "et-0/0/32,et-0/0/33,et-0/0/48,et-0/0/49"
```

### 3. Troubleshooting Specific Links
Temporarily focus on problematic interfaces:
```bash
ansible-playbook -i inventory.yml junos_telemetry.yml \
  -e 'interface_filter="et-0/0/15"' \
  --limit problematic-device
```

### 4. Different Interfaces Per Device

Use inventory variables for device-specific filtering (recommended for production):

```yaml
# inventory.yml
junos_devices:
  hosts:
    core-router-1:
      ansible_user: root
      ansible_password: yourpassword
      interface_filter: "et-0/0/0,et-0/0/1"  # Core uplinks only
    
    edge-router-1:
      ansible_user: root
      ansible_password: yourpassword
      interface_filter: "et-0/0/32,et-0/0/33"  # Customer-facing ports
    
    access-switch-1:
      ansible_user: root
      ansible_password: yourpassword
      # No filter - monitor all interfaces on this device
```

Run with:
```bash
ansible-playbook -i inventory.yml junos_telemetry.yml
```

Each device will use its own interface filter automatically.

### 5. Mixed Global and Per-Device Filtering

Set a global default and override for specific devices:

```yaml
# junos_telemetry.yml
vars:
  interface_filter: "et-0/0/0,et-0/0/1"  # Default for most devices

# inventory.yml
junos_devices:
  hosts:
    router-1:
      # Uses global filter: et-0/0/0,et-0/0/1
    
    router-2:
      interface_filter: "et-0/0/48,et-0/0/49"  # Overrides global filter
    
    router-3:
      interface_filter: ""  # Empty string = monitor all interfaces
```

## Performance Considerations

- **Reduced Processing Time**: Filtering interfaces reduces XML parsing time
- **Lower Metric Volume**: Fewer metrics sent to Prometheus
- **Faster Queries**: Less data in time series database
- **Storage Savings**: Reduced storage requirements in Prometheus

## Example Output

With `interface_filter="et-0/0/32"`, the playbook output shows:

```
TASK [Display parsing results] *************************************************
ok: [10.209.3.39] => (item=optics_diagnostics) => 
    msg: 'Parsed optics_diagnostics: [''Filtering for interfaces: et-0/0/32'', 
          ''Generated 1 interface metrics and 1 lane metrics'']'
```

Without filtering:

```
TASK [Display parsing results] *************************************************
ok: [10.209.3.39] => (item=optics_diagnostics) => 
    msg: 'Parsed optics_diagnostics: [''Generated 62 interface metrics and 62 lane metrics'']'
```
