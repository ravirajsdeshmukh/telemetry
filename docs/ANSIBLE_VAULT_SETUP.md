# Ansible Vault Credential Management

## Overview
Device credentials are now stored in an encrypted Ansible Vault file instead of plaintext in the inventory. This provides better security for production environments.

## Structure

```
ansible/
├── inventory.yml                              # Production device inventory
├── junos_devices_semaphore.yaml                # Semaphore inventory (xai, regression)
├── vault/
│   └── vault_password                          # Vault decryption password (DO NOT COMMIT)
└── group_vars/
    ├── all/                                    # Variables for ALL hosts
    │   ├── vault.yml                           # Encrypted AWS credentials
    │   └── vars.yml                            # AWS variable references
    ├── junos/                                  # Production device credentials
    │   ├── vault.yml                           # Encrypted device credentials
    │   └── vars.yml                            # Connection settings
    ├── xai/                                    # XAI RMA device credentials
    │   ├── vault.yml                           # Encrypted credentials
    │   └── vars.yml                            # Connection settings
    └── regression/                             # Regression lab credentials
        ├── vault.yml                           # Encrypted credentials
        └── vars.yml                            # Connection settings
```

## File Contents

### 1. vault.yml (Encrypted)

**Device Credentials** (e.g., `group_vars/junos/vault.yml`):
```yaml
---
vault_junos_username: root
vault_junos_password: Embe1mpls
```

**AWS Credentials** (`group_vars/all/vault.yml`):
```yaml
---
vault_aws_access_key_id: "AKIAIOSFODNN7EXAMPLE"
vault_aws_secret_access_key: "wJalrXUtnFEMI/K7MDENG/bPxRfiCYEXAMPLEKEY"
vault_aws_session_token: "IQoJb3JpZ2luX2VjE..."  # Optional, for STS credentials
```

### 2. vars.yml (Plain text)

**Device Connection Settings** (e.g., `group_vars/junos/vars.yml`):
```yaml
---
ansible_user: "{{ vault_junos_username }}"
ansible_password: "{{ vault_junos_password }}"
ansible_network_os: junipernetworks.junos.junos
ansible_connection: netconf
ansible_ssh_common_args: '-o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null -o PreferredAuthentications=password'
ansible_port: 22
```

**AWS Credentials** (`group_vars/all/vars.yml`):
```yaml
---
aws_access_key_id: "{{ vault_aws_access_key_id }}"
aws_secret_access_key: "{{ vault_aws_secret_access_key }}"
aws_session_token: "{{ vault_aws_session_token }}"
```

### 3. Inventory Files

**inventory.yml** - Production devices:
```yaml
---
all:
  children:
    junos:
      hosts:
        device1.example.com:
          interface_filter: "et-0/0/32"
        device2.example.com:
          interface_filter: "et-0/0/0"
```

**junos_devices_semaphore.yaml** - Grouped by function:
```yaml
---
all:
  children:
    junos_devices:
      children:
        xai:  # XAI RMA devices
          hosts:
            xai-qfx5240-01.englab.juniper.net:
              interface_filter: "et-0/0/11:0,et-0/0/9:0"
        regression:  # Lab test devices
          hosts:
            garnet-qfx5240-a.englab.juniper.net:
```

Credentials are automatically loaded from `group_vars/{group_name}/vault.yml`.

## Managing Credentials

### View Encrypted Vault
```bash
ansible-vault view group_vars/junos/vault.yml --vault-password-file vault/vault_password
```

### Edit Encrypted Vault
```bash
ansible-vault edit group_vars/junos/vault.yml --vault-password-file vault/vault_password
```

### Create New Vault
```bash
# Create temporary file with credentials
cat > /tmp/vault_temp.yml <<EOF
---
vault_junos_username: root
vault_junos_password: YourPassword
EOF

# Encrypt and save
ansible-vault encrypt /tmp/vault_temp.yml \
  --vault-password-file vault/vault_password \
  --output group_vars/junos/vault.yml

# Clean up
rm /tmp/vault_temp.yml
```

### Change Vault Password
```bash
ansible-vault rekey group_vars/junos/vault.yml --vault-password-file vault/vault_password
```

## Adding Device Groups with Different Credentials

If you have devices with different credentials, create separate groups:

### 1. Create new vault file
```bash
mkdir -p group_vars/my_new_group

# Create credentials
cat > /tmp/vault_newgroup.yml <<EOF
---
vault_newgroup_username: admin
vault_newgroup_password: DifferentPassword
EOF

ansible-vault encrypt /tmp/vault_newgroup.yml \
  --vault-password-file vault/vault_password \
  --output group_vars/my_new_group/vault.yml
  
rm /tmp/vault_newgroup.yml
chmod 600 group_vars/my_new_group/vault.yml
```

### 2. Create vars.yml for the group
```bash
cat > group_vars/my_new_group/vars.yml <<EOF
---
ansible_user: "{{ vault_newgroup_username }}"
ansible_password: "{{ vault_newgroup_password }}"
ansible_network_os: junipernetworks.junos.junos
ansible_connection: netconf
ansible_ssh_common_args: '-o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null -o PreferredAuthentications=password'
ansible_port: 22
EOF
```

### 3. Update inventory
```yaml
all:
  children:
    junos_devices:
      children:
        my_new_group:
          hosts:
            newdevice.example.com:
              interface_filter: "et-0/0/0"
```

## AWS Credentials Management

AWS credentials for S3 sync are stored in `group_vars/all/vault.yml` so they're available to all hosts.

### Create AWS Vault
```bash
mkdir -p group_vars/all

# Create temporary file
cat > /tmp/vault_aws_temp.yml <<EOF
---
vault_aws_access_key_id: "YOUR_ACCESS_KEY"
vault_aws_secret_access_key: "YOUR_SECRET_KEY"
vault_aws_session_token: "YOUR_SESSION_TOKEN"  # Optional, for STS credentials
EOF

# Encrypt
ansible-vault encrypt /tmp/vault_aws_temp.yml \
  --vault-password-file vault/vault_password \
  --output group_vars/all/vault.yml

rm /tmp/vault_aws_temp.yml
chmod 600 group_vars/all/vault.yml
```

### Create vars.yml for AWS
```bash
cat > group_vars/all/vars.yml <<EOF
---
# AWS S3 credentials for datalake sync
aws_access_key_id: "{{ vault_aws_access_key_id }}"
aws_secret_access_key: "{{ vault_aws_secret_access_key }}"
aws_session_token: "{{ vault_aws_session_token }}"
EOF
```

These credentials are now automatically available to the S3 sync task in the playbook.

## Running Playbooks with Vault

### Option 1: Using vault password file (Recommended for automation)
```bash
ansible-playbook junos_telemetry.yml \
  -i inventory.yml \
  --vault-password-file vault/vault_password
```

### Option 2: Interactive password prompt
```bash
ansible-playbook junos_telemetry.yml \
  -i inventory.yml \
  --ask-vault-pass
```

### Option 3: With specific device group
```bash
ansible-playbook junos_telemetry.yml \
  -i junos_devices_semaphore.yaml \
  --vault-password-file vault/vault_password \
  --limit xai
```

## Security Best Practices

### 1. Protect the vault password file
```bash
chmod 600 vault/vault_password
```

### 2. Add to .gitignore
```bash
echo "vault/vault_password" >> .gitignore
echo "*.vault_password" >> .gitignore
echo "group_vars/*/vault.yml" >> .gitignore
```

### 3. Never commit plaintext credentials
- Always encrypt sensitive data before committing
- Use `git diff` to verify no credentials are exposed
- Review all vault files before committing

### 4. Rotate credentials regularly
```bash
# Update vault with new password
ansible-vault edit group_vars/junos/vault.yml --vault-password-file vault/vault_password
```

### 5. Use different vault passwords for different environments
```bash
# Production
ansible-playbook playbook.yml --vault-password-file vault/vault_password_prod

# Development
ansible-playbook playbook.yml --vault-password-file vault/vault_password_dev
```

### 6. Set proper file permissions
```bash
# All vault files should be readable only by owner
chmod 600 group_vars/*/vault.yml
chmod 600 vault/vault_password
```

## Troubleshooting

### Error: "Vault password not found"
```bash
# Verify vault password file exists
ls -la .vault_password

# Create if missing (must contain the correct password)
echo "your_vault_password" > .vault_password
chmod 600 .vault_password
```

### Error: "ERROR! Attempting to decrypt but no vault secrets found"
```bash
# File may not be encrypted - encrypt it
ansible-vault encrypt group_vars/junos_devices/vault.yml --vault-password-file .vault_password
```

### Verify vault is working
```bash
# Test inventory resolution
ansible-inventory --list --vault-password-file .vault_password

# Test connectivity
ansible junos_devices -m ping --vault-password-file .vault_password
```

### Variables not resolving
Variables are resolved at runtime, not in `ansible-inventory --list`. To verify:
```bash
ansible junos_devices -m debug -a "var=ansible_user" --vault-password-file .vault_password
```

## Semaphore Integration

When using Semaphore UI, configure the vault password:

1. Go to Environment → Secrets
2. Add new secret: `ANSIBLE_VAULT_PASSWORD`
3. In Project settings, set Environment Variables:
   ```
   ANSIBLE_VAULT_PASSWORD_FILE=/tmp/vault_pass
   ```
4. In Task Template, add a pre-task:
   ```bash
   echo "$ANSIBLE_VAULT_PASSWORD" > /tmp/vault_pass
   chmod 600 /tmp/vault_pass
   ```

## Migration from Plaintext to Vault

If migrating existing inventory:

1. Extract unique credential sets
2. Create vault files for each credential group
3. Organize inventory by credential groups
4. Update playbooks to use `--vault-password-file`
5. Test thoroughly before removing plaintext credentials
6. Update documentation and CI/CD pipelines

## Benefits

✅ **Security**: Credentials encrypted at rest
✅ **Organization**: Group devices by credential sets
✅ **Auditability**: Track credential changes via git
✅ **Scalability**: Easy to add new device groups
✅ **Compliance**: Meet security audit requirements
✅ **Automation**: Works with CI/CD pipelines
