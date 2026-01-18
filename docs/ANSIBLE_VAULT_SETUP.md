# Ansible Vault Credential Management

## Overview
Device credentials are now stored in an encrypted Ansible Vault file instead of plaintext in the inventory. This provides better security for production environments.

## Structure

```
ansible/
├── inventory.yml                              # Device inventory (no credentials)
├── .vault_password                           # Vault password file (DO NOT COMMIT)
└── group_vars/
    └── junos_devices/
        ├── vault.yml                         # Encrypted credentials
        └── vars.yml                          # Variable references
```

## File Contents

### 1. vault.yml (Encrypted)
Contains actual credentials:
```yaml
---
vault_junos_username: root
vault_junos_password: Embe1mpls
```

### 2. vars.yml (Plain text)
References vault variables:
```yaml
---
ansible_user: "{{ vault_junos_username }}"
ansible_password: "{{ vault_junos_password }}"
ansible_network_os: junipernetworks.junos.junos
ansible_connection: netconf
ansible_ssh_common_args: '-o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null -o PreferredAuthentications=password'
ansible_port: 22
```

### 3. inventory.yml (No credentials)
Organized by credential groups:
```yaml
---
all:
  children:
    junos_devices:
      children:
        junos_standard_auth:  # Group for devices with same credentials
          hosts:
            device1.example.com:
              interface_filter: "et-0/0/32"
            device2.example.com:
              interface_filter: "et-0/0/0"
```

## Managing Credentials

### View Encrypted Vault
```bash
ansible-vault view group_vars/junos_devices/vault.yml --vault-password-file .vault_password
```

### Edit Encrypted Vault
```bash
ansible-vault edit group_vars/junos_devices/vault.yml --vault-password-file .vault_password
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
ansible-vault encrypt /tmp/vault_temp.yml --vault-password-file .vault_password --output group_vars/junos_devices/vault.yml

# Clean up
rm /tmp/vault_temp.yml
```

### Change Vault Password
```bash
ansible-vault rekey group_vars/junos_devices/vault.yml --vault-password-file .vault_password
```

## Adding Device Groups with Different Credentials

If you have devices with different credentials, create separate groups:

### 1. Create new vault file
```bash
mkdir -p group_vars/junos_alternate_auth

# Create credentials
cat > /tmp/vault_alt.yml <<EOF
---
vault_junos_alt_username: admin
vault_junos_alt_password: DifferentPassword
EOF

ansible-vault encrypt /tmp/vault_alt.yml --vault-password-file .vault_password --output group_vars/junos_alternate_auth/vault.yml
rm /tmp/vault_alt.yml
```

### 2. Create vars.yml for the group
```bash
cat > group_vars/junos_alternate_auth/vars.yml <<EOF
---
ansible_user: "{{ vault_junos_alt_username }}"
ansible_password: "{{ vault_junos_alt_password }}"
ansible_network_os: junipernetworks.junos.junos
ansible_connection: netconf
ansible_ssh_common_args: '-o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null -o PreferredAuthentications=password'
ansible_port: 22
EOF
```

### 3. Update inventory.yml
```yaml
all:
  children:
    junos_devices:
      children:
        junos_standard_auth:
          hosts:
            device1.example.com:
        junos_alternate_auth:
          hosts:
            device2.example.com:
```

## Running Playbooks with Vault

### Option 1: Using vault password file (Recommended for automation)
```bash
ansible-playbook junos_telemetry.yml --vault-password-file .vault_password
```

### Option 2: Interactive password prompt
```bash
ansible-playbook junos_telemetry.yml --ask-vault-pass
```

### Option 3: With AWS credentials
```bash
ansible-playbook junos_telemetry.yml \
  --vault-password-file .vault_password \
  -e "aws_access_key_id=YOUR_KEY" \
  -e "aws_secret_access_key=YOUR_SECRET" \
  -e "aws_session_token=YOUR_TOKEN"
```

## Security Best Practices

### 1. Protect the vault password file
```bash
chmod 600 .vault_password
```

### 2. Add to .gitignore
```bash
echo ".vault_password" >> .gitignore
echo "*.vault_password" >> .gitignore
```

### 3. Never commit plaintext credentials
- Always encrypt sensitive data before committing
- Use `git diff` to verify no credentials are exposed

### 4. Rotate credentials regularly
```bash
# Update vault with new password
ansible-vault edit group_vars/junos_devices/vault.yml --vault-password-file .vault_password
```

### 5. Use different vault passwords for different environments
```bash
# Production
ansible-playbook playbook.yml --vault-password-file .vault_password_prod

# Development
ansible-playbook playbook.yml --vault-password-file .vault_password_dev
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
