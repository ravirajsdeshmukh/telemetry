# Ansible Semaphore Setup Guide

## ✅ Installation Complete

Semaphore has been successfully added to your Docker Compose stack and is running!

## Access Semaphore

**URL:** http://your-server-ip:3001

**Default Credentials:**
- Username: `admin` or `admin@localhost`
- Password: `changeme`

## Initial Configuration Steps

### Step 1: Login
1. Open http://your-server-ip:3001 in your browser
2. Login with credentials above
3. Change your password (recommended)

### Step 2: Install Ansible Dependencies in Container

The Semaphore container needs Ansible and Python dependencies:

```bash
# Enter the container
docker exec -it semaphore sh

# Install Ansible and dependencies
apk add --no-cache ansible python3 py3-pip openssh-client sshpass git

# Install Python libraries
pip3 install junos-eznc jxmlease requests lxml netaddr ncclient

# Exit container
exit
```

Or restart the container after creating a custom Dockerfile (see Alternative Setup below).

### Step 3: Create a Project

1. Click **New Project** button
2. Fill in:
   - **Name**: `Junos Telemetry`
   - Click **Create**

### Step 4: Add Key Store (Credentials)

1. In your project, go to **Key Store** → **New Key**
2. Fill in:
   - **Name**: `Junos Root Credentials`
   - **Type**: `Login with password`
   - **Login**: `root`
   - **Password**: `Empe1mpls` (or your actual password)
3. Click **Create**

### Step 5: Create Inventory

1. Go to **Inventory** → **New Inventory**
2. Fill in:
   - **Name**: `Junos Devices`
   - **Type**: `File`
   - **Inventory** (paste content from your inventory.yml):
     ```yaml
     all:
       children:
         junos_devices:
           hosts:
             10.209.3.39:
               ansible_user: root
               ansible_password: Empe1mpls
               ansible_network_os: junipernetworks.junos.junos
               ansible_connection: netconf
               interface_filter: "et-0/0/32"
             10.83.6.222:
               ansible_user: root
               ansible_password: fasetup123
               ansible_network_os: junipernetworks.junos.junos
               ansible_connection: netconf
     ```
3. Click **Create**

### Step 6: Create Repository

1. Go to **Repositories** → **New Repository**
2. Fill in:
   - **Name**: `Telemetry Local`
   - **URL**: `/ansible` (this is the mounted project directory)
   - **Branch**: (leave empty for local filesystem)
   - **Access Key**: None
3. Click **Create**

### Step 7: Create Environment

1. Go to **Environment** → **New Environment**
2. Fill in:
   - **Name**: `Production`
   - **Variables** (JSON format):
     ```json
     {
       "prometheus_pushgateway": "http://pushgateway:9091",
       "output_dir": "/tmp/telemetry_output"
     }
     ```
   - **Extra Variables** (optional):
     ```json
     {
       "ansible_python_interpreter": "/usr/bin/python3"
     }
     ```
3. Click **Create**

### Step 8: Create Task Template

1. Go to **Task Templates** → **New Template**
2. Fill in:
   - **Name**: `Collect Junos Optics Metrics`
   - **Playbook Filename**: `junos_telemetry.yml`
   - **Inventory**: Select `Junos Devices`
   - **Repository**: Select `Telemetry Local`
   - **Environment**: Select `Production`
   - **Start Version**: (leave empty)
   - **Allow CLI Args in Task**: ✅ (optional)
   - **Survey Variables**: (leave empty)
3. Click **Create**

### Step 9: Test Manual Run

1. Go to your newly created Task Template
2. Click the **Run** button (play icon)
3. Watch the live output
4. Verify metrics are collected successfully

### Step 10: Create Schedule (Every 10 Minutes)

1. In your Task Template, click **Schedules** tab
2. Click **New Schedule**
3. Fill in:
   - **Name**: `Every 10 Minutes`
   - **Cron Expression**: `*/10 * * * *`
   - **Repository Ref**: (leave empty)
   - **Active**: ✅ Check this box
4. Click **Create**

## Cron Expression Examples

Change the schedule by editing the cron expression:

- **Every 10 minutes**: `*/10 * * * *`
- **Every 5 minutes**: `*/5 * * * *`
- **Every 15 minutes**: `*/15 * * * *`
- **Every 30 minutes**: `*/30 * * * *`
- **Every hour**: `0 * * * *`
- **Every 2 hours**: `0 */2 * * *`
- **Business hours only (9-5, every 10 min)**: `*/10 9-17 * * 1-5`
- **Every 10 min, weekdays only**: `*/10 * * * 1-5`

## Monitoring

### View Task History
- Go to **Tasks** tab to see all execution history
- Click on any task to see detailed logs
- Filter by status: Success ✅ / Failed ❌ / Running 🔵

### View Next Scheduled Run
- Go to your Task Template → **Schedules** tab
- See "Last Run" and "Next Run" times

### Check Logs
```bash
# View Semaphore logs
docker compose logs -f semaphore

# View all container logs
docker compose logs -f
```

## Troubleshooting

### Issue: Can't connect to Junos devices

**Solution 1:** Use host network mode

Edit docker-compose.yml:
```yaml
  semaphore:
    network_mode: host
    # Comment out or remove:
    # ports:
    #   - "3001:3000"
    # networks:
    #   - monitoring
```

Then restart:
```bash
docker compose down
docker compose up -d
```

Access Semaphore at: http://localhost:3000 (note: port 3000, not 3001)

**Solution 2:** Test connectivity
```bash
# Enter container
docker exec -it semaphore sh

# Test network access
ping 10.209.3.39
nc -zv 10.209.3.39 830

# Test from host
telnet 10.209.3.39 830
```

### Issue: Ansible modules not found

```bash
# Enter container
docker exec -it semaphore sh

# Install Ansible collection
ansible-galaxy collection install junipernetworks.junos

# Verify installation
ansible-galaxy collection list
```

### Issue: Python import errors

```bash
# Enter container and install missing packages
docker exec -it semaphore sh
pip3 install junos-eznc ncclient lxml jxmlease requests
```

### Issue: Permission denied accessing /ansible

Check the volume mount and permissions:
```bash
ls -la /home/ubuntu/workspace/telemetry/
docker exec -it semaphore ls -la /ansible
```

## Alternative: Custom Dockerfile with Pre-installed Dependencies

Create `Dockerfile.semaphore`:

```dockerfile
FROM semaphoreui/semaphore:latest

USER root

# Install system dependencies
RUN apk add --no-cache \
    ansible \
    python3 \
    py3-pip \
    openssh-client \
    sshpass \
    git \
    build-base \
    python3-dev \
    libxml2-dev \
    libxslt-dev

# Install Python packages
RUN pip3 install --no-cache-dir \
    junos-eznc \
    jxmlease \
    ncclient \
    lxml \
    requests \
    netaddr

# Install Ansible collections
RUN ansible-galaxy collection install junipernetworks.junos

# Set working directory
WORKDIR /ansible

USER semaphore
```

Update docker-compose.yml:
```yaml
  semaphore:
    build:
      context: .
      dockerfile: Dockerfile.semaphore
    # ... rest of config
```

Build and run:
```bash
docker compose build semaphore
docker compose up -d semaphore
```

## API Usage (Optional)

Semaphore has a REST API for automation:

```bash
# Get API token
TOKEN=$(curl -s -X POST http://localhost:3001/api/auth/login \
  -H "Content-Type: application/json" \
  -d '{"auth":"admin","password":"changeme"}' | jq -r .token)

# List projects
curl -H "Authorization: Bearer $TOKEN" \
  http://localhost:3001/api/projects

# Run task manually via API
curl -X POST -H "Authorization: Bearer $TOKEN" \
  http://localhost:3001/api/project/1/templates/1/tasks

# Update schedule interval
curl -X PUT -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"cron_format":"*/15 * * * *"}' \
  http://localhost:3001/api/project/1/schedules/1
```

## URLs Reference

- **Semaphore UI**: http://your-server-ip:3001
- **Prometheus**: http://your-server-ip:9090
- **Grafana**: http://your-server-ip:3000
- **Pushgateway**: http://your-server-ip:9091

## Docker Commands

```bash
# View all containers
docker compose ps

# View Semaphore logs
docker compose logs -f semaphore

# Restart Semaphore
docker compose restart semaphore

# Stop all services
docker compose down

# Start all services
docker compose up -d

# Rebuild and restart Semaphore
docker compose up -d --build semaphore

# Enter Semaphore container
docker exec -it semaphore sh

# Remove and recreate
docker compose down
docker compose up -d
```

## Backup

```bash
# Backup Semaphore configuration and database
tar -czf semaphore_backup_$(date +%Y%m%d).tar.gz semaphore_data/

# Restore
tar -xzf semaphore_backup_YYYYMMDD.tar.gz
```

## Next Steps

1. ✅ Login to Semaphore Web UI
2. ✅ Install Ansible dependencies in container
3. ✅ Configure Project, Inventory, Repository, Environment
4. ✅ Create Task Template
5. ✅ Test manual run
6. ✅ Create schedule for every 10 minutes
7. Monitor task executions in the **Tasks** tab
8. Set up notifications (optional)
9. Create Grafana dashboards for collected metrics

## Support

- Semaphore Documentation: https://docs.ansible-semaphore.com/
- GitHub: https://github.com/ansible-semaphore/semaphore
- Community: https://github.com/ansible-semaphore/semaphore/discussions
