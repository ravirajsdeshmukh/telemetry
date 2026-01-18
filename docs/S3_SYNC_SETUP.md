# S3 Data Lake Sync Setup

## Overview
The telemetry collection playbook automatically syncs the `raw_ml_data` directory to S3 (s3://amzn-ds-s3-rrd/datalake) after each collection run, preserving the directory structure for long-term storage and ML training.

## Directory Structure Preserved
```
s3://amzn-ds-s3-rrd/datalake/
├── dt=2026-01-16/
│   ├── hr=22/
│   │   ├── intf-dom/
│   │   │   └── interface_dom_20260116_223050.parquet
│   │   ├── lane-dom/
│   │   │   └── lane_dom_20260116_223050.parquet
│   │   └── intf-counters/
│   │       └── interface_counters_20260116_223050.parquet
│   └── hr=23/
│       └── ...
└── dt=2026-01-17/
    └── ...
```

## AWS Credentials Configuration

### Recommended: Ansible Vault (Production)

AWS credentials are stored in encrypted vault files at `group_vars/all/vault.yml`:

1. Create the encrypted vault:
```bash
cd ansible

# Create temporary file with credentials
cat > /tmp/vault_aws_temp.yml <<EOF
---
vault_aws_access_key_id: "YOUR_ACCESS_KEY_ID"
vault_aws_secret_access_key: "YOUR_SECRET_ACCESS_KEY"
vault_aws_session_token: "YOUR_SESSION_TOKEN"  # Optional, for STS credentials
EOF

# Encrypt and save
ansible-vault encrypt /tmp/vault_aws_temp.yml \
  --vault-password-file vault/vault_password \
  --output group_vars/all/vault.yml

# Clean up
rm /tmp/vault_aws_temp.yml
chmod 600 group_vars/all/vault.yml
```

2. Create variable references:
```bash
cat > group_vars/all/vars.yml <<EOF
---
# AWS S3 credentials for datalake sync
aws_access_key_id: "{{ vault_aws_access_key_id }}"
aws_secret_access_key: "{{ vault_aws_secret_access_key }}"
aws_session_token: "{{ vault_aws_session_token }}"
EOF
```

3. Run playbook:
```bash
ansible-playbook junos_telemetry.yml \
  -i inventory.yml \
  --vault-password-file vault/vault_password
```

The credentials are automatically decrypted and used by the S3 sync task.

### Alternative: Environment Variables (Docker/Semaphore)

For containerized environments, set credentials as environment variables:

```yaml
# docker-compose.yml or Semaphore task environment
environment:
  - AWS_ACCESS_KEY_ID=your_access_key_id
  - AWS_SECRET_ACCESS_KEY=your_secret_access_key
  - AWS_SESSION_TOKEN=your_session_token  # Optional
```

Then update the playbook S3 sync task to read from environment:
```yaml
environment:
  AWS_ACCESS_KEY_ID: "{{ lookup('env', 'AWS_ACCESS_KEY_ID') | default(aws_access_key_id, true) }}"
  AWS_SECRET_ACCESS_KEY: "{{ lookup('env', 'AWS_SECRET_ACCESS_KEY') | default(aws_secret_access_key, true) }}"
  AWS_SESSION_TOKEN: "{{ lookup('env', 'AWS_SESSION_TOKEN') | default(aws_session_token, true) }}"
```

## S3 Sync Task Details

The sync task is configured in `junos_telemetry.yml` (second play):

```yaml
- name: Sync raw_ml_data to S3 datalake
  community.aws.s3_sync:
    bucket: amzn-ds-s3-rrd
    file_root: "{{ raw_ml_data_dir }}"
    key_prefix: datalake/
    region: us-east-1
  environment:
    AWS_ACCESS_KEY_ID: "{{ aws_access_key_id }}"
    AWS_SECRET_ACCESS_KEY: "{{ aws_secret_access_key }}"
    AWS_SESSION_TOKEN: "{{ aws_session_token | default('') }}"
  register: s3_sync_result
  ignore_errors: yes
  when: aws_access_key_id is defined and aws_secret_access_key is defined
```

**Key Features:**
- **Module**: `community.aws.s3_sync` (requires community.aws >= 6.0.0)
- **Bucket**: `amzn-ds-s3-rrd`
- **Key Prefix**: `datalake/`
- **Region**: `us-east-1`
- **When**: Runs only if AWS credentials are defined (skipped otherwise)
- **Timing**: Runs after hourly Parquet files are created
- **Session Token**: Supports temporary STS credentials

## Required IAM Permissions

The AWS access key must have the following S3 permissions:
```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Action": [
        "s3:PutObject",
        "s3:GetObject",
        "s3:ListBucket",
        "s3:DeleteObject"
      ],
      "Resource": [
        "arn:aws:s3:::amzn-ds-s3-rrd/datalake/*",
        "arn:aws:s3:::amzn-ds-s3-rrd"
      ]
    }
  ]
}
```

## Installation Requirements

### Python Packages
```bash
pip install boto3>=1.26.0 botocore>=1.29.0
```

### Ansible Collections
```bash
ansible-galaxy collection install community.aws
# Or use requirements.yml:
ansible-galaxy collection install -r requirements.yml
```

The `requirements.yml` file should contain:
```yaml
collections:
  - name: junipernetworks.junos
    version: ">=5.0.0"
  - name: community.aws
    version: ">=6.0.0"
```

## Manual S3 Sync

To manually trigger S3 sync without collecting new telemetry:

```bash
cd ansible

# Sync existing data
ansible-playbook junos_telemetry.yml \
  -i inventory.yml \
  --vault-password-file vault/vault_password \
  --tags s3_sync
```

Or create a dedicated sync playbook `sync_to_s3.yml`:
```yaml
---
- name: Sync raw_ml_data to S3
  hosts: localhost
  connection: local
  gather_facts: no
  
  vars:
    raw_ml_data_dir: "{{ '/raw_ml_data' if playbook_dir == '/ansible' else '../raw_ml_data' }}"
  
  tasks:
    - name: Sync raw_ml_data to S3 datalake
      community.aws.s3_sync:
        bucket: amzn-ds-s3-rrd
        file_root: "{{ raw_ml_data_dir }}"
        key_prefix: datalake/
        region: us-east-1
      environment:
        AWS_ACCESS_KEY_ID: "{{ aws_access_key_id }}"
        AWS_SECRET_ACCESS_KEY: "{{ aws_secret_access_key }}"
        AWS_SESSION_TOKEN: "{{ aws_session_token | default('') }}"
      register: s3_sync_result

    - name: Display sync result
      debug:
        msg: "{{ s3_sync_result }}"
```

Run with:
```bash
ansible-playbook sync_to_s3.yml --vault-password-file vault/vault_password
```

## Scheduling Periodic Syncs

### Option 1: Semaphore Scheduled Tasks (Recommended)

1. In Semaphore UI, create a new Task Template
2. Set playbook: `junos_telemetry.yml`
3. Set inventory: `inventory.yml` or `junos_devices_semaphore.yaml`
4. Add environment variable: `ANSIBLE_VAULT_PASSWORD_FILE=/ansible/vault/vault_password`
5. Set schedule: `*/5 * * * *` (every 5 minutes)
6. Semaphore will automatically run collection and sync to S3

See [SEMAPHORE_SETUP.md](SEMAPHORE_SETUP.md) for detailed Semaphore configuration.

### Option 2: Cron Job
```bash
# Add to crontab: sync every 5 minutes
*/5 * * * * cd /home/ubuntu/workspace/telemetry/ansible && /home/ubuntu/venv310/bin/ansible-playbook junos_telemetry.yml -i inventory.yml --vault-password-file vault/vault_password >> /var/log/telemetry_cron.log 2>&1
```

## Monitoring S3 Sync

Check sync results in playbook output:
```
TASK [Display S3 sync result] *************
ok: [localhost] => {
    "msg": {
        "changed": true,
        "msg": "Uploaded 15 files to s3://amzn-ds-s3-rrd/datalake/"
    }
}
```

List files in S3:
```bash
aws s3 ls s3://amzn-ds-s3-rrd/datalake/ --recursive | head -20
```

## Cost Considerations
- **S3 Standard Storage**: ~$0.023/GB/month
- **PUT Requests**: $0.005 per 1,000 requests
- **Data Transfer OUT**: Free within same region

For a typical setup collecting 5 devices every 5 minutes:
- ~300 files/hour = 7,200 files/day
- ~1-2 MB per file = 7-14 GB/day
- Monthly storage: ~210-420 GB = ~$5-10/month

## Troubleshooting

### Error: "couldn't resolve module/action 'aws_s3_sync'"
- Install community.aws collection: `ansible-galaxy collection install community.aws`

### Error: "No module named 'boto3'"
- Install boto3: `pip install boto3 botocore`

### Error: "Access Denied"
- Check IAM permissions for the access key
- Verify bucket name and region are correct

### Error: "Invalid security token"
- AWS credentials may be expired or incorrect
- Regenerate access key in IAM console

## Data Lake Query Examples

Once data is in S3, you can query with AWS Athena:

```sql
-- Create external table
CREATE EXTERNAL TABLE junos_interface_counters (
  device STRING,
  interface_name STRING,
  fec_ccw BIGINT,
  fec_nccw BIGINT,
  collection_timestamp TIMESTAMP
)
PARTITIONED BY (dt STRING, hr STRING, metric_type STRING)
STORED AS PARQUET
LOCATION 's3://amzn-ds-s3-rrd/datalake/';

-- Add partitions
MSCK REPAIR TABLE junos_interface_counters;

-- Query FEC errors for specific device
SELECT 
  interface_name,
  fec_ccw,
  fec_nccw,
  collection_timestamp
FROM junos_interface_counters
WHERE dt = '2026-01-17'
  AND device = 'xai-qfx5240-01.englab.juniper.net'
  AND metric_type = 'intf-counters'
ORDER BY collection_timestamp DESC
LIMIT 100;
```

## Retention Policy

Consider implementing lifecycle policies to manage costs:

```xml
<LifecycleConfiguration>
  <Rule>
    <Id>Archive old telemetry data</Id>
    <Prefix>datalake/</Prefix>
    <Status>Enabled</Status>
    <Transition>
      <Days>30</Days>
      <StorageClass>INTELLIGENT_TIERING</StorageClass>
    </Transition>
    <Transition>
      <Days>90</Days>
      <StorageClass>GLACIER</StorageClass>
    </Transition>
    <Expiration>
      <Days>365</Days>
    </Expiration>
  </Rule>
</LifecycleConfiguration>
```

This policy:
- Keeps data in Standard storage for 30 days
- Moves to Intelligent Tiering after 30 days
- Archives to Glacier after 90 days
- Deletes data after 1 year
