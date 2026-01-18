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

## AWS Access Key Configuration

### Option 1: Environment Variables (Recommended for Docker)
Set AWS credentials as environment variables in docker-compose.yml:

```yaml
semaphore:
  environment:
    - AWS_ACCESS_KEY_ID=your_access_key_id
    - AWS_SECRET_ACCESS_KEY=your_secret_access_key
```

### Option 2: Ansible Vault (Recommended for Host)
1. Create an encrypted vault file:
```bash
cd /home/ubuntu/workspace/telemetry/ansible
ansible-vault create group_vars/all/vault.yml
```

2. Add your AWS credentials:
```yaml
aws_access_key_id: AKIAIOSFODNN7EXAMPLE
aws_secret_access_key: wJalrXUtnFEMI/K7MDENG/bPxRfiCYEXAMPLEKEY
```

3. Reference in playbook (already configured):
```yaml
aws_access_key: "{{ aws_access_key_id }}"
aws_secret_key: "{{ aws_secret_access_key }}"
```

4. Run playbook with vault:
```bash
ansible-playbook junos_telemetry.yml --ask-vault-pass
```

### Option 3: Pass as Extra Variables
```bash
ansible-playbook junos_telemetry.yml \
  -e "aws_access_key_id=AKIAIOSFODNN7EXAMPLE" \
  -e "aws_secret_access_key=wJalrXUtnFEMI/K7MDENG/bPxRfiCYEXAMPLEKEY"
```

### Option 4: Use AWS Instance Profile (IAM Role)
If running on an EC2 instance with an IAM role that has S3 permissions, remove the aws_access_key and aws_secret_key parameters from the task. The module will automatically use the instance profile credentials.

## S3 Sync Task Details

The sync task is configured in `junos_telemetry.yml`:
- **Module**: `community.aws.s3_sync`
- **Bucket**: `amzn-ds-s3-rrd`
- **Key Prefix**: `datalake/`
- **Region**: `us-east-1`
- **When**: Runs after hourly Parquet files are created

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

### On Host
```bash
pip install boto3 botocore
ansible-galaxy collection install community.aws
```

### In Docker Container
Already configured. If needed:
```bash
docker exec semaphore pip3 install boto3 botocore
docker exec semaphore ansible-galaxy collection install community.aws
```

## Manual Sync
To manually sync without running the full playbook:

```bash
# From host
cd /home/ubuntu/workspace/telemetry/ansible
ansible-playbook -i localhost, -c local sync_to_s3.yml

# From Docker container
docker exec -w /ansible semaphore ansible-playbook sync_to_s3.yml
```

Create `sync_to_s3.yml`:
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
        aws_access_key: "{{ aws_access_key_id }}"
        aws_secret_key: "{{ aws_secret_access_key }}"
        region: "us-east-1"
      environment:
        AWS_ACCESS_KEY_ID: "{{ aws_access_key_id }}"
        AWS_SECRET_ACCESS_KEY: "{{ aws_secret_access_key }}"
```

## Scheduling Periodic Syncs

### Option 1: Semaphore Scheduled Tasks
1. In Semaphore UI, create a new Template
2. Set playbook: `junos_telemetry.yml`
3. Add Schedule: every 5 minutes
4. Semaphore will automatically run the playbook and sync to S3

### Option 2: Cron Job
```bash
# Add to crontab: sync every hour at minute 5
5 * * * * cd /home/ubuntu/workspace/telemetry/ansible && /home/ubuntu/venv310/bin/ansible-playbook junos_telemetry.yml --vault-password-file ~/.vault_pass
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
