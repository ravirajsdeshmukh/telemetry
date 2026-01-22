# Semaphore Runner Setup Guide

This guide explains how to set up remote runners for Semaphore to enable distributed execution of Ansible playbooks.

## Overview

Semaphore runners are separate containers that connect to the Semaphore server to execute tasks. Each runner requires:
- A **unique private key** (different for each runner)
- A **registration token** (same for all runners, configured on Semaphore server)
- A **runner-specific encrypted token** (generated during setup)

## Prerequisites

- Semaphore server running with `SEMAPHORE_USE_REMOTE_RUNNER: 'true'`
- Docker and docker-compose installed
- OpenSSL for key generation

## Step-by-Step Setup

### Step 1: Generate Private Key

Each runner needs its own unique private key. Generate one for each runner:

```bash
# Navigate to infrastructure directory
cd /home/ubuntu/workspace/telemetry/infrastructure

# Create semaphore_runners directory if it doesn't exist
mkdir -p mounts/semaphore_runners

# Generate private key for runner1
openssl genrsa -out private_key.pem 2048

# Move to the shared mount location
mv private_key.pem mounts/semaphore_runners/runner1.key.pem

# Set proper permissions
chmod 600 mounts/semaphore_runners/runner1.key.pem
```

For additional runners (runner2, runner3, etc.), repeat with different filenames:
```bash
openssl genrsa -out private_key.pem 2048
mv private_key.pem mounts/semaphore_runners/runner2.key.pem
chmod 600 mounts/semaphore_runners/runner2.key.pem
```

### Step 2: Get Registration Token

The registration token is configured on the Semaphore server in [`infrastructure/docker-compose.yml`](infrastructure/docker-compose.yml):

```yaml
semaphore:
  environment:
    SEMAPHORE_RUNNER_REGISTRATION_TOKEN: runnertoken12345
```

This token (`runnertoken12345` in the example) is used during runner setup.

### Step 3: Run Runner Setup (One-Time Per Runner)

Enter the Semaphore container and run the interactive setup:

```bash
# Enter Semaphore container
docker exec -it semaphore sh

# Run runner setup
semaphore runner setup --config /etc/semaphore_runners/runner1-config.json
```

**Interactive prompts and responses:**

```
Semaphore server URL: http://10.221.80.101:3001

Do you want to store token in external file? (yes/no) (default no): no

Do you have runner's token? (yes/no) (default no): yes

Enter valid runner token: runnertoken12345

Do you have runner's private key file? (yes/no) (default no): yes

Enter path to the private key file: /etc/semaphore_runners/runner1.key.pem
```

**Expected output:**
```
Running: mkdir -p /etc/semaphore_runners..
Configuration written to /etc/semaphore_runners/runner1-config.json..
Loading config
Validating config
INFO[0042] Registering a new runner                     
Re-launch this program pointing to the configuration file

./semaphore runner start --config /etc/semaphore_runners/runner1-config.json

To run as daemon:

nohup ./semaphore runner start --config /etc/semaphore_runners/runner1-config.json &
```

Exit the container:
```bash
exit
```

### Step 4: Extract Encrypted Token

The setup command generates a config file with an encrypted token. Extract it:

```bash
# View the generated config
cat mounts/semaphore_runners/runner1-config.json

# Example output:
# {
#   "server": "http://10.221.80.101:3001",
#   "token": "mEuxxri3HNFgieqX3uXD5Lk2bovfHd5C9+k2MJ7uvUY=",
#   "private_key_file": "/etc/semaphore_runners/runner1.key.pem"
# }
```

Copy the **token** value (e.g., `mEuxxri3HNFgieqX3uXD5Lk2bovfHd5C9+k2MJ7uvUY=`).

### Step 5: Update docker-compose.yml

Update the runner configuration in [`infrastructure/docker-compose.yml`](infrastructure/docker-compose.yml):

```yaml
  semaphore-runner01:
    image: semaphoreui/runner:v2.16.47
    container_name: semaphore-runner01
    user: "1000:1000"
    environment:
      SEMAPHORE_WEB_ROOT: http://10.221.80.101:3001
      SEMAPHORE_RUNNER_TOKEN: mEuxxri3HNFgieqX3uXD5Lk2bovfHd5C9+k2MJ7uvUY=  # From config.json
      SEMAPHORE_RUNNER_PRIVATE_KEY_FILE: /etc/semaphore_runners/runner1.key.pem
      SEMAPHORE_RUNNER_NAME: semaphore-runner01
      SEMAPHORE_RUNNER_TAGS: xai,junos
      ANSIBLE_HOST_KEY_CHECKING: 'false'
    volumes:
      - ./mounts/semaphore_runners:/etc/semaphore_runners
      - /home/ubuntu/.ssh:/root/.ssh:ro
      - ../ansible:/ansible:ro
      - ./mounts/output:/output
      - ./mounts/raw_ml_data:/raw_ml_data
    networks:
      - monitoring
    restart: unless-stopped
    depends_on:
      - semaphore
```

**Important:** 
- `SEMAPHORE_RUNNER_TOKEN`: Use the encrypted token from `runner1-config.json`
- `SEMAPHORE_RUNNER_PRIVATE_KEY_FILE`: Path inside container to the private key
- `SEMAPHORE_RUNNER_NAME`: Unique name for this runner
- `SEMAPHORE_RUNNER_TAGS`: Tags for task targeting (e.g., `xai,junos` or `regression,junos`)

### Step 6: Start the Runner

```bash
cd /home/ubuntu/workspace/telemetry/infrastructure

# Start the runner
docker compose up -d semaphore-runner01

# Check logs
docker logs -f semaphore-runner01

# Expected output:
# Loading config
# Validating config
# No additional python dependencies to install
# Starting semaphore runner
# INFO[xxxx] Runner connected to server
# INFO[xxxx] Waiting for tasks...
```

### Step 7: Install Dependencies (First Time)

After the runner starts, install Ansible and Python dependencies:

```bash
# Enter runner container
docker exec -it semaphore-runner01 sh

# Install Python packages
pip3 install ansible junipernetworks.junos jxmlease lxml xmltodict \
     pandas pyarrow boto3 botocore prometheus_client

# Install Ansible collections
ansible-galaxy collection install junipernetworks.junos
ansible-galaxy collection install community.aws

# Verify installations
ansible --version
ansible-galaxy collection list | grep junos

# Exit container
exit
```

### Step 8: Verify Runner Registration

1. Open Semaphore UI: http://10.221.80.101:3001
2. Navigate to **Settings → Runners**
3. You should see `semaphore-runner01` listed with status **Active**

## Setting Up Additional Runners

To add more runners (e.g., for the regression group):

### Runner 2 Setup

```bash
# Step 1: Generate new private key
cd /home/ubuntu/workspace/telemetry/infrastructure
openssl genrsa -out private_key.pem 2048
mv private_key.pem mounts/semaphore_runners/runner2.key.pem
chmod 600 mounts/semaphore_runners/runner2.key.pem

# Step 2: Run setup in Semaphore container
docker exec -it semaphore sh
semaphore runner setup --config /etc/semaphore_runners/runner2-config.json
# Answer prompts:
# Server: http://10.221.80.101:3001
# External file: no
# Have token: yes
# Token: runnertoken12345
# Have private key: yes
# Private key path: /etc/semaphore_runners/runner2.key.pem
exit

# Step 3: Extract token from config
cat mounts/semaphore_runners/runner2-config.json | grep token
```

### Add to docker-compose.yml

```yaml
  semaphore-runner02:
    image: semaphoreui/runner:v2.16.47
    container_name: semaphore-runner02
    user: "1000:1000"
    environment:
      SEMAPHORE_WEB_ROOT: http://10.221.80.101:3001
      SEMAPHORE_RUNNER_TOKEN: <token_from_runner2-config.json>
      SEMAPHORE_RUNNER_PRIVATE_KEY_FILE: /etc/semaphore_runners/runner2.key.pem
      SEMAPHORE_RUNNER_NAME: semaphore-runner02
      SEMAPHORE_RUNNER_TAGS: regression,junos
      ANSIBLE_HOST_KEY_CHECKING: 'false'
    volumes:
      - ./mounts/semaphore_runners:/etc/semaphore_runners
      - /home/ubuntu/.ssh:/root/.ssh:ro
      - ../ansible:/ansible:ro
      - ./mounts/output:/output
      - ./mounts/raw_ml_data:/raw_ml_data
    networks:
      - monitoring
    restart: unless-stopped
    depends_on:
      - semaphore
```

Start the new runner:
```bash
docker compose up -d semaphore-runner02
docker logs -f semaphore-runner02
```

## Runner Configuration Summary

### File Structure

```
infrastructure/
├── docker-compose.yml                    # Runner container definitions
└── mounts/
    └── semaphore_runners/
        ├── runner1.key.pem               # Private key for runner1
        ├── runner1-config.json           # Generated config (contains encrypted token)
        ├── runner2.key.pem               # Private key for runner2
        └── runner2-config.json           # Generated config for runner2
```

### Environment Variables

| Variable | Description | Same for all runners? |
|----------|-------------|----------------------|
| `SEMAPHORE_WEB_ROOT` | Semaphore server URL | ✅ Yes |
| `SEMAPHORE_RUNNER_TOKEN` | Encrypted runner token | ❌ No - unique per runner |
| `SEMAPHORE_RUNNER_PRIVATE_KEY_FILE` | Path to private key | ❌ No - unique per runner |
| `SEMAPHORE_RUNNER_NAME` | Runner identifier | ❌ No - unique per runner |
| `SEMAPHORE_RUNNER_TAGS` | Tags for task routing | ❌ No - depends on runner purpose |

### Registration Token vs Runner Token

- **Registration Token** (`runnertoken12345`): 
  - Configured on Semaphore server
  - Used during initial setup
  - Same for all runners
  - Found in: [`docker-compose.yml`](infrastructure/docker-compose.yml) under `semaphore.environment.SEMAPHORE_RUNNER_REGISTRATION_TOKEN`

- **Runner Token** (`mEuxxri3HNFgieqX3uXD5Lk2bovfHd5C9+k2MJ7uvUY=`):
  - Generated during runner setup
  - Encrypted and unique per runner
  - Used for runtime authentication
  - Found in: `mounts/semaphore_runners/runnerX-config.json`

## Troubleshooting

### Runner not appearing in Semaphore UI

**Check runner logs:**
```bash
docker logs semaphore-runner01
```

**Common issues:**

1. **Wrong token**: Verify `SEMAPHORE_RUNNER_TOKEN` matches `runner1-config.json`
2. **Permission denied on private key**:
   ```bash
   chmod 600 mounts/semaphore_runners/runner1.key.pem
   ```
3. **Server not accessible**:
   ```bash
   docker exec semaphore-runner01 wget -O- http://10.221.80.101:3001/api/ping
   ```

### Runner crashes or restarts continuously

**Check if config file exists:**
```bash
ls -la mounts/semaphore_runners/
```

**Verify private key is readable:**
```bash
docker exec semaphore-runner01 cat /etc/semaphore_runners/runner1.key.pem
```

### Ansible playbook fails with "Module not found"

**Install missing dependencies:**
```bash
docker exec -it semaphore-runner01 sh
pip3 install <missing_package>
ansible-galaxy collection install <missing_collection>
exit
docker restart semaphore-runner01
```

### Permission errors accessing output/raw_ml_data

**Fix directory permissions:**
```bash
sudo chown -R 1000:1000 mounts/output mounts/raw_ml_data
chmod -R 775 mounts/output mounts/raw_ml_data
```

## Runner Pools and Task Assignment

Assign tasks to specific runners using tags in Semaphore task templates:

**XAI Collection Task:**
- Playbook: [`ansible/junos_telemetry.yml`](ansible/junos_telemetry.yml)
- CLI Args: `--limit xai`
- Runner tags: `xai`
- Will run on: `semaphore-runner01`

**Regression Collection Task:**
- Playbook: [`ansible/junos_telemetry.yml`](ansible/junos_telemetry.yml)
- CLI Args: `--limit regression`
- Runner tags: `regression`
- Will run on: `semaphore-runner02`

## Scaling Runners

To handle more devices, add more runners with the same process:

```bash
# For 4 regression runners:
for i in {2..5}; do
  openssl genrsa -out private_key.pem 2048
  mv private_key.pem mounts/semaphore_runners/runner${i}.key.pem
  chmod 600 mounts/semaphore_runners/runner${i}.key.pem
done

# Then run setup for each and add to docker-compose.yml
```

## Maintenance

### Update Runner Image

```bash
cd /home/ubuntu/workspace/telemetry/infrastructure

# Pull new image
docker pull semaphoreui/runner:latest

# Update docker-compose.yml image tag
# Then restart
docker compose up -d semaphore-runner01
```

### Regenerate Runner Token

If a runner token is compromised:

1. Generate new private key
2. Delete old config file: `rm mounts/semaphore_runners/runner1-config.json`
3. Re-run setup process (Step 3)
4. Update `SEMAPHORE_RUNNER_TOKEN` in docker-compose.yml
5. Restart runner

## Security Best Practices

1. ✅ **Protect private keys**: Ensure `*.key.pem` files have `600` permissions
2. ✅ **Rotate keys**: Regenerate private keys every 90 days
3. ✅ **Unique keys**: Never share private keys between runners
4. ✅ **Secure vault password**: Mount vault password as read-only
5. ✅ **Network isolation**: Use Docker networks to isolate runners
6. ✅ **Audit logs**: Monitor runner activity in Semaphore UI

## References

- [Semaphore Documentation](https://docs.ansible-semaphore.com/)
- [Semaphore Runners Guide](https://docs.ansible-semaphore.com/administration-guide/runners)
- Main project README: [README.md](../README.md)
- Semaphore server setup: [SEMAPHORE_SETUP.md](SEMAPHORE_SETUP.md)
- Ansible Vault setup: [ANSIBLE_VAULT_SETUP.md](ANSIBLE_VAULT_SETUP.md)
