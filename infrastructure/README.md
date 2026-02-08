# Infrastructure Management

This directory contains the infrastructure for the telemetry collection system, including Docker containers for Semaphore orchestration, Prometheus monitoring, and distributed runners.

## Quick Start

```bash
# Deploy control plane
./deploy.sh deploy control

# Deploy all runners
./deploy.sh deploy all-runners

# Check status
./deploy.sh status

# View health
./deploy.sh health
```

Or using Makefile:
```bash
make deploy-all
make status
make health
```

## Architecture

### VM Topology
```
┌─────────────────────────────────────────────────────────┐
│ VM1: 10.221.80.101                                      │
│ ├─ Control Plane                                        │
│ │  ├─ Semaphore UI (port 3001)                         │
│ │  ├─ PostgreSQL                                        │
│ │  ├─ Prometheus (port 9090)                           │
│ │  ├─ Grafana (port 3000)                              │
│ │  └─ Pushgateway (port 9091)                          │
│ └─ Runner01 (Shard1: XAI, Regression1)                 │
└─────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────┐
│ VM2: 10.161.38.200                                      │
│ ├─ Runner02 (Shard2: Regression2)                      │
│ └─ Runner03 (Shard3: GPU Fabric)                       │
└─────────────────────────────────────────────────────────┘
```

### Runner to Shard Mapping
| Runner | Shard | Inventory File | Tags | Devices |
|--------|-------|----------------|------|---------|
| runner01 | shard1 | inventory-shard1.yaml | `shard1,xai,regression1` | XAI, Regression1 |
| runner02 | shard2 | inventory-shard2.yaml | `shard2,regression2` | Regression2 |
| runner03 | shard3 | inventory-shard3.yaml | `shard3,gpu-fabric` | GPU Fabric Cluster |

## Files

### Core Files
- **docker-compose.yml** - Service definitions with profiles
- **prometheus.yml** - Prometheus configuration
- **deployment-config.yml** - Central topology configuration
- **deploy.sh** - Deployment automation script
- **Makefile** - Quick deployment commands

### Environment Files
- **env-files/.env** - Environment variables for all services

### Documentation
- **DEPLOYMENT_GUIDE.md** - Complete deployment guide
- **README.md** - This file

### Directories
- **mounts/** - Persistent data and shared volumes
  - `prometheus_data/` - Prometheus time-series database
  - `grafana_data/` - Grafana dashboards and config
  - `postgres_data/` - Semaphore database
  - `semaphore_runners/` - Runner keys and configs
  - `output/` - Temporary output from playbook runs
  - `raw_ml_data/` - ML training data (Parquet files)

## Docker Compose Profiles

Services are organized by profiles for targeted deployment:

| Profile | Services | Location |
|---------|----------|----------|
| `control` | semaphore, postgres, prometheus, grafana, pushgateway | VM1 |
| `runner01` | semaphore-runner01 | VM1 |
| `runner02` | semaphore-runner02 | VM2 |
| `runner03` | semaphore-runner03 | VM2 |
| `all-runners` | All runners | Multiple VMs |
| `all` | Everything | All VMs |

## Usage Examples

### Using deploy.sh (Recommended)

```bash
# Deploy control plane
./deploy.sh deploy control

# Deploy specific runner
./deploy.sh deploy runner01
./deploy.sh deploy runner02

# Deploy all runners
./deploy.sh deploy all-runners

# Deploy everything
./deploy.sh deploy all

# Check status
./deploy.sh status

# Health check
./deploy.sh health

# View logs
./deploy.sh logs control
./deploy.sh logs runner01

# Restart services
./deploy.sh deploy runner02 restart

# Stop services
./deploy.sh deploy all-runners down
```

### Using Makefile

```bash
# Deploy
make deploy-control
make deploy-runner01
make deploy-all

# Monitor
make status
make health

# Logs
make logs-control
make logs-runner01

# Management
make restart-runner01
make stop-all
```

### Using Docker Compose Directly

```bash
# On VM1
cd /home/ubuntu/workspace/telemetry/infrastructure

# Start control plane
docker compose --profile control up -d

# Start runner01
docker compose --profile runner01 up -d

# View status
docker compose --profile control ps

# View logs
docker compose --profile control logs -f semaphore

# On VM2
ssh ubuntu@10.161.38.200
cd /home/ubuntu/workspace/telemetry/infrastructure

# Start all runners on this VM
docker compose --profile all-runners up -d
```

## Initial Setup

### 1. Setup SSH Access
Ensure SSH keys are configured for remote deployment:
```bash
ssh-copy-id ubuntu@10.221.80.101
ssh-copy-id ubuntu@10.161.38.200
```

### 2. Deploy Control Plane
```bash
./deploy.sh deploy control
```

### 3. Setup Runner Keys
For each runner that needs setup:
```bash
# Generate private key (if not exists)
openssl genrsa -out mounts/semaphore_runners/runner3.key.pem 2048
chmod 600 mounts/semaphore_runners/runner3.key.pem

# Run runner setup (interactive)
docker exec -it semaphore-runner03 sh
semaphore runner setup --config /etc/semaphore_runners/runner3-config.json
# Follow prompts
```

### 4. Deploy Runners
```bash
./deploy.sh deploy all-runners
```

### 5. Configure Semaphore UI
1. Access http://10.221.80.101:3001
2. Login with admin credentials
3. Create project and repositories
4. Configure inventories (shard1, shard2, shard3)
5. Create task templates with runner tags
6. Schedule tasks

## Monitoring

### Web Interfaces
- **Semaphore UI**: http://10.221.80.101:3001
- **Prometheus**: http://10.221.80.101:9090
- **Grafana**: http://10.221.80.101:3000
- **Pushgateway**: http://10.221.80.101:9091

### Check Runner Status
```bash
# View runner logs
./deploy.sh logs runner01

# Check if runner is registered in Semaphore UI
# Navigate to: Semaphore UI → Runners
```

### Monitor Data Output
```bash
# Check output files
ls -lh mounts/output/

# Check Parquet files
ls -lh mounts/raw_ml_data/dt=*/hr=*/
```

## Troubleshooting

### Services Won't Start
```bash
# Check logs
./deploy.sh logs control semaphore

# Check if ports are in use
sudo netstat -tlnp | grep -E '(3001|9090|3000|9091)'

# Restart services
./deploy.sh deploy control restart
```

### Runner Not Connecting
```bash
# Check runner logs
./deploy.sh logs runner01

# Verify runner token
docker exec -it semaphore-runner01 cat /etc/semaphore_runners/runner1-config.json

# Restart runner
./deploy.sh deploy runner01 restart
```

### SSH Connection Issues
```bash
# Test SSH connectivity
ssh ubuntu@10.221.80.101 "echo OK"
ssh ubuntu@10.161.38.200 "echo OK"

# Check SSH keys
ssh-add -l
```

### Volume Permission Issues
```bash
# Fix permissions
sudo chown -R $(id -u):$(id -g) mounts/
chmod -R 755 mounts/
```

## Backup and Recovery

### Backup
```bash
# Backup all persistent data
tar -czf backup-$(date +%Y%m%d).tar.gz \
    mounts/postgres_data/ \
    mounts/grafana_data/ \
    mounts/prometheus_data/ \
    mounts/semaphore_runners/
```

### Restore
```bash
# Stop services
./deploy.sh deploy all down

# Restore data
tar -xzf backup-YYYYMMDD.tar.gz

# Restart services
./deploy.sh deploy all
```

## Scaling

### Add New Runner

1. Update `docker-compose.yml`:
```yaml
semaphore-runner04:
  # ... similar to runner03
```

2. Update `deployment-config.yml` with new runner details

3. Update `deploy.sh` to include new runner target

4. Generate keys and deploy:
```bash
openssl genrsa -out mounts/semaphore_runners/runner4.key.pem 2048
chmod 600 mounts/semaphore_runners/runner4.key.pem
./deploy.sh deploy runner04
```

### Move Runner to Different VM

1. Update VM host in `deployment-config.yml`
2. Update `SEMAPHORE_WEB_ROOT` in docker-compose.yml
3. Redeploy: `./deploy.sh deploy runner02`

## Best Practices

1. ✅ Use deployment script for consistency
2. ✅ Check status before and after deployments
3. ✅ Monitor logs when troubleshooting
4. ✅ Use specific profiles to avoid unnecessary restarts
5. ✅ Tag runners correctly in Semaphore for proper routing
6. ✅ Keep .env files secure
7. ✅ Document changes to configuration files
8. ✅ Test on one runner before deploying to all
9. ✅ Backup data regularly
10. ✅ Use health checks to verify deployments

## References

- [DEPLOYMENT_GUIDE.md](DEPLOYMENT_GUIDE.md) - Detailed deployment guide
- [../docs/SEMAPHORE_SETUP.md](../docs/SEMAPHORE_SETUP.md) - Semaphore setup
- [../docs/SEMAPHORE_RUNNER_SETUP.md](../docs/SEMAPHORE_RUNNER_SETUP.md) - Runner setup
- [Docker Compose Documentation](https://docs.docker.com/compose/)
- [Semaphore Documentation](https://docs.ansible-semaphore.com/)
