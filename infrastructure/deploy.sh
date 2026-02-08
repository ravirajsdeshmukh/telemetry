#!/bin/bash
# Central deployment script for managing all Docker containers across VMs
# Usage: ./deploy.sh <command> [arguments]
# Configuration: deployment-config.yml (SINGLE SOURCE OF TRUTH)

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
CONFIG_FILE="${SCRIPT_DIR}/deployment-config.yml"

# Check if yq is installed
if ! command -v yq &> /dev/null; then
    echo "ERROR: yq is required but not installed."
    echo "Install with: sudo snap install yq"
    exit 1
fi

# Verify config file exists
if [ ! -f "$CONFIG_FILE" ]; then
    echo "ERROR: Configuration file not found: $CONFIG_FILE"
    exit 1
fi

# Logging functions
log_info() {
    echo "[INFO] $1"
}

log_warn() {
    echo "[WARN] $1"
}

log_error() {
    echo "[ERROR] $1"
}

log_section() {
    echo ""
    echo "==== $1 ===="
}

# Get VM host for a given target from config
get_vm_host() {
    local target=$1
    
    case $target in
        control)
            yq eval '.deployment.control_plane.vm_host' "$CONFIG_FILE"
            ;;
        runner01|runner02|runner03|runner04|runner05)
            local runner_name="semaphore-$target"
            yq eval ".deployment.runners[] | select(.name == \"$runner_name\") | .vm_host" "$CONFIG_FILE"
            ;;
        *)
            echo ""
            ;;
    esac
}

# Get SSH user for a given VM host
get_ssh_user() {
    local vm_host=$1
    local user=$(yq eval ".vm_details[] | select(.host == \"$vm_host\") | .user" "$CONFIG_FILE")
    echo "${user:-ubuntu}"
}

# Get base path for a given VM host
get_base_path() {
    local vm_host=$1
    local base_path=$(yq eval ".vm_details[] | select(.host == \"$vm_host\") | .base_path" "$CONFIG_FILE")
    echo "${base_path:-/home/ubuntu}"
}

# Get profile for a target, these profiles map to docker-compose profiles
get_profile() {
    local target=$1
    
    case $target in
        control)
            yq eval '.deployment.control_plane.compose_profile' "$CONFIG_FILE"
            ;;
        runner01|runner02|runner03|runner04|runner05)
            local runner_name="semaphore-$target"
            yq eval ".deployment.runners[] | select(.name == \"$runner_name\") | .compose_profile" "$CONFIG_FILE"
            ;;
        *)
            echo "$target"
            ;;
    esac
}

# Check if running on VM or needs SSH
is_local_vm() {
    local target_vm=$1
    local current_ip=$(hostname -I | awk '{print $1}')
    
    if [ "$target_vm" == "localhost" ] || [ "$target_vm" == "$current_ip" ]; then
        return 0
    else
        return 1
    fi
}

# Cleanup function for remote VM
cleanup_vm() {
    local vm_host=$1
    local ssh_user=$(get_ssh_user "$vm_host")
    local remote_base=$(get_base_path "$vm_host")
    
    log_section "Cleanup: $vm_host"
    
    if is_local_vm "$vm_host"; then
        log_warn "Cleanup not needed for local VM"
        return
    fi
    
    log_info "Cleaning up $vm_host..."
    ssh "$ssh_user@$vm_host" "rm -rf $remote_base/workspace/telemetry"
    log_info "Cleanup complete for $vm_host"
}

# Deploy to specific VM
deploy_to_vm() {
    local vm_host=$1
    local profile=$2
    local compose_cmd=$3
    local ssh_user=$(get_ssh_user "$vm_host")
    
    log_info "Deploying profile '$profile' to VM $vm_host (user: $ssh_user)"
    
    if is_local_vm "$vm_host"; then
        # Local deployment
        log_info "Local deployment detected"
        local local_base="$(cd "$SCRIPT_DIR/.." && pwd)"
        export TELEMETRY_BASE="$local_base"
        export CLUSTER_NAME=$(yq eval '.cluster_name' "$CONFIG_FILE")
        export RUNNER_NAME="${CLUSTER_NAME}-${profile}"
        cd "$SCRIPT_DIR"
        docker compose --env-file env-files/.env --profile "$profile" $compose_cmd
    else
        # Remote deployment via SSH
        log_info "Remote deployment via SSH to $ssh_user@$vm_host"
        
        # Get remote base path from config
        local remote_base=$(get_base_path "$vm_host")
        
        # Create directory structure on remote VM
        log_info "Ensuring remote directory exists..."
        ssh "$ssh_user@$vm_host" "mkdir -p $remote_base/workspace/telemetry/infrastructure/mounts/semaphore_runners && \
            mkdir -p $remote_base/workspace/telemetry/infrastructure/mounts/output && \
            mkdir -p $remote_base/workspace/telemetry/infrastructure/mounts/raw_ml_data && \
            mkdir -p $remote_base/workspace/telemetry/infrastructure/env-files && \
            mkdir -p $remote_base/workspace/telemetry/ansible && \
            chmod 777 $remote_base/workspace/telemetry/infrastructure/mounts/output && \
            chmod 777 $remote_base/workspace/telemetry/infrastructure/mounts/raw_ml_data"
        
        # Copy only essential files for this deployment
        log_info "Copying deployment files to $vm_host..."
        
        # Copy docker-compose.yml
        scp "$SCRIPT_DIR/docker-compose.yml" "$ssh_user@$vm_host:$remote_base/workspace/telemetry/infrastructure/"
        
        # Copy .env file
        scp "$SCRIPT_DIR/env-files/.env" "$ssh_user@$vm_host:$remote_base/workspace/telemetry/infrastructure/env-files/"
        
        # Copy ansible requirements.txt
        scp "$SCRIPT_DIR/../ansible/requirements.txt" "$ssh_user@$vm_host:$remote_base/workspace/telemetry/ansible/"
        
        # Copy runner-specific private key if this is a runner deployment
        if [[ "$profile" =~ ^runner[0-9]+$ ]]; then
            # This line extracts the runner number from the profile name
            # ${variable//pattern/replacement} is used to remove 'runner' prefix
            local runner_num=${profile//runner/}
            local key_file="runner${runner_num}.key.pem"
            if [ -f "$SCRIPT_DIR/mounts/semaphore_runners/$key_file" ]; then
                log_info "Copying $key_file to $vm_host..."
                scp "$SCRIPT_DIR/mounts/semaphore_runners/$key_file" "$ssh_user@$vm_host:$remote_base/workspace/telemetry/infrastructure/mounts/semaphore_runners/"
            else
                log_error "Missing private key file for runner $runner_num: $key_file"
                exit 1                
            fi
            
            local config_file="runner${runner_num}-config.json"
            if [ -f "$SCRIPT_DIR/mounts/semaphore_runners/$config_file" ]; then
                log_info "Copying $config_file to $vm_host..."
                scp "$SCRIPT_DIR/mounts/semaphore_runners/$config_file" "$ssh_user@$vm_host:$remote_base/workspace/telemetry/infrastructure/mounts/semaphore_runners/"
            else
                log_error "Missing config file for runner $runner_num: $config_file"
                exit 1
            fi
        elif [ "$profile" == "control" ]; then
            # For control plane, copy prometheus.yml and all runner keys (needed for registration)
            log_info "Copying control plane files to $vm_host..."
            scp "$SCRIPT_DIR/prometheus.yml" "$ssh_user@$vm_host:$remote_base/workspace/telemetry/infrastructure/" 2>/dev/null || true
            
            # Copy all runner keys and configs for control plane (needed for runner registration)
            if [ -d "$SCRIPT_DIR/mounts/semaphore_runners" ]; then
                scp "$SCRIPT_DIR/mounts/semaphore_runners/"* "$ssh_user@$vm_host:$remote_base/workspace/telemetry/infrastructure/mounts/semaphore_runners/" 2>/dev/null || true
            fi
        fi
        
        # Execute deployment on remote VM with environment variables
        log_info "Executing deployment on $vm_host..."
        local cluster_name=$(yq eval '.cluster_name' "$CONFIG_FILE")
        ssh "$ssh_user@$vm_host" "cd $remote_base/workspace/telemetry/infrastructure && \
            TELEMETRY_BASE=$remote_base/workspace/telemetry \
            CLUSTER_NAME=$cluster_name \
            RUNNER_NAME=${cluster_name}-${profile} \
            docker compose --env-file env-files/.env --profile $profile $compose_cmd"
    fi
}

# Main deployment function
deploy() {
    local target=$1
    local action=${2:-up -d}
    
    log_section "Deployment: $target"
    
    case $target in
        control|runner01|runner02|runner03|runner04|runner05|runner06|runner07|runner08|runner09|runner10)
            local vm_host=$(get_vm_host "$target")
            local profile=$(get_profile "$target")
            local description=$(yq eval ".deployment.runners[] | select(.compose_profile == \"$profile\") | .description" "$CONFIG_FILE" 2>/dev/null || echo "")
            
            if [ "$target" == "control" ]; then
                description=$(yq eval '.deployment.control_plane.description' "$CONFIG_FILE")
                log_info "Deploying control plane: $description"
            else
                log_info "Deploying $target: $description"
            fi
            
            if [ -z "$vm_host" ]; then
                log_error "Could not find VM host for target: $target"
                exit 1
            fi
            
            deploy_to_vm "$vm_host" "$profile" "$action"
            ;;
        all-runners)
            log_info "Deploying all runners..."
            local runner_count=$(yq eval '.deployment.runners | length' "$CONFIG_FILE")
            
            for ((i=0; i<$runner_count; i++)); do
                local runner_name=$(yq eval ".deployment.runners[$i].name" "$CONFIG_FILE")
                local runner_target=$(echo "$runner_name" | sed 's/semaphore-//')
                local vm_host=$(yq eval ".deployment.runners[$i].vm_host" "$CONFIG_FILE")
                local profile=$(yq eval ".deployment.runners[$i].compose_profile" "$CONFIG_FILE")
                
                log_info "Deploying $runner_name on $vm_host..."
                deploy_to_vm "$vm_host" "$profile" "$action"
            done
            ;;
        all)
            log_info "Deploying everything (control + all runners)..."
            
            # Deploy control plane first
            local control_vm=$(get_vm_host "control")
            deploy_to_vm "$control_vm" "control" "$action"
            sleep 5  # Give control plane time to start
            
            # Deploy all runners
            deploy "all-runners" "$action"
            ;;
        *)
            log_error "Unknown target: $target"
            echo ""
            echo "Usage: $0 deploy {control|runner01|runner02|runner03|runner04|runner05|all-runners|all} [docker-compose-args]"
            echo ""
            
            # Show available targets from config
            echo "Targets (from deployment-config.yml):"
            local control_vm=$(yq eval '.deployment.control_plane.vm_host' "$CONFIG_FILE")
            echo "  control      - Control plane (VM: $control_vm)"
            
            local runner_count=$(yq eval '.deployment.runners | length' "$CONFIG_FILE")
            for ((i=0; i<$runner_count; i++)); do
                local runner_name=$(yq eval ".deployment.runners[$i].name" "$CONFIG_FILE")
                local runner_vm=$(yq eval ".deployment.runners[$i].vm_host" "$CONFIG_FILE")
                local runner_desc=$(yq eval ".deployment.runners[$i].description" "$CONFIG_FILE")
                local runner_target=$(echo "$runner_name" | sed 's/semaphore-//')
                echo "  $runner_target     - $runner_desc (VM: $runner_vm)"
            done
            
            echo "  all-runners  - All runners"
            echo "  all          - Everything"
            echo ""
            echo "Examples:"
            echo "  $0 deploy control up -d          # Start control plane"
            echo "  $0 deploy runner01 restart       # Restart runner01"
            echo "  $0 deploy all-runners down       # Stop all runners"
            echo "  $0 status                        # Check status"
            exit 1
            ;;
    esac
    
    log_info "✓ Deployment complete for $target"
}

# Status check across all VMs
status() {
    log_section "Status Check Across All VMs"
    
    # Get unique VM hosts
    local control_vm=$(yq eval '.deployment.control_plane.vm_host' "$CONFIG_FILE")
    local control_user=$(get_ssh_user "$control_vm")
    local control_path=$(get_base_path "$control_vm")
    
    echo ""
    echo "=== Control Plane ($control_vm) ==="
    if ssh -o ConnectTimeout=5 "$control_user@$control_vm" "cd $control_path/workspace/telemetry/infrastructure && docker compose --profile control ps" 2>/dev/null; then
        :
    else
        log_warn "Could not connect to $control_vm"
    fi
    
    # Check each runner
    local runner_count=$(yq eval '.deployment.runners | length' "$CONFIG_FILE")
    local checked_vms=()
    
    for ((i=0; i<$runner_count; i++)); do
        local runner_name=$(yq eval ".deployment.runners[$i].name" "$CONFIG_FILE")
        local runner_vm=$(yq eval ".deployment.runners[$i].vm_host" "$CONFIG_FILE")
        local runner_profile=$(yq eval ".deployment.runners[$i].compose_profile" "$CONFIG_FILE")
        local runner_user=$(get_ssh_user "$runner_vm")
        local runner_path=$(get_base_path "$runner_vm")
        
        # Skip if we've already checked this VM with all-runners profile
        if [[ " ${checked_vms[@]} " =~ " ${runner_vm} " ]]; then
            continue
        fi
        
        echo ""
        echo "=== $runner_name ($runner_vm) ==="
        if ssh -o ConnectTimeout=5 "$runner_user@$runner_vm" "cd $runner_path/workspace/telemetry/infrastructure && docker compose --profile $runner_profile ps" 2>/dev/null; then
            :
        else
            log_warn "Could not connect to $runner_vm"
        fi
        
        checked_vms+=("$runner_vm")
    done
}

# Health check
health() {
    log_section "Health Check"
    
    local control_vm=$(yq eval '.deployment.control_plane.vm_host' "$CONFIG_FILE")
    
    log_info "Checking Semaphore UI ($control_vm:3001)..."
    if curl -s -o /dev/null -w "%{http_code}" http://$control_vm:3001 | grep -q "200\|301\|302"; then
        log_info "✓ Semaphore UI is accessible"
    else
        log_warn "✗ Semaphore UI is not accessible"
    fi
    
    log_info "Checking Prometheus ($control_vm:9090)..."
    if curl -s -o /dev/null -w "%{http_code}" http://$control_vm:9090/-/healthy | grep -q "200"; then
        log_info "✓ Prometheus is healthy"
    else
        log_warn "✗ Prometheus is not healthy"
    fi
    
    log_info "Checking Grafana ($control_vm:3000)..."
    if curl -s -o /dev/null -w "%{http_code}" http://$control_vm:3000 | grep -q "200\|302"; then
        log_info "✓ Grafana is accessible"
    else
        log_warn "✗ Grafana is not accessible"
    fi
}

# Logs from specific service
logs() {
    local target=$1
    local service=${2:-}
    
    local vm_host=$(get_vm_host "$target")
    local profile=$(get_profile "$target")
    local ssh_user=$(get_ssh_user "$vm_host")
    local remote_path=$(get_base_path "$vm_host")
    
    if [ -z "$vm_host" ]; then
        log_error "Unknown target: $target"
        echo "Usage: $0 logs {control|runner01|runner02|runner03|runner04|runner05} [service-name]"
        exit 1
    fi
    
    if is_local_vm "$vm_host"; then
        cd "$SCRIPT_DIR"
        docker compose --profile "$profile" logs -f $service
    else
        ssh "$ssh_user@$vm_host" "cd $remote_path/workspace/telemetry/infrastructure && docker compose --profile $profile logs -f $service"
    fi
}

# Show help
show_help() {
    local control_vm=$(yq eval '.deployment.control_plane.vm_host' "$CONFIG_FILE")
    local runner_count=$(yq eval '.deployment.runners | length' "$CONFIG_FILE")
    
    cat << EOF
Central Deployment Manager
Manage Docker containers across multiple VMs

Configuration: deployment-config.yml (SINGLE SOURCE OF TRUTH)

Usage:
  $0 <command> [arguments]

Commands:
  deploy <target> [action]  Deploy to specific target
  status                    Check status of all deployments
  health                    Run health checks on services
  logs <target> [service]   View logs from specific target
  help                      Show this help

Deployment Targets:
  control      - Semaphore UI, Prometheus, Grafana, Postgres
  runner01     - Shard 1 runner (XAI, Regression1)
  runner02     - Shard 2 runner (Regression2)
  runner03     - Shard 3 runner (GPU Fabric)
  all-runners  - All runners
  all          - Everything

Common Examples:
  $0 deploy control               # Deploy control plane
  $0 deploy all-runners           # Deploy all runners
  $0 deploy all                   # Deploy everything
  $0 deploy runner01 restart      # Restart runner01
  $0 deploy all-runners down      # Stop all runners
  $0 cleanup 10.87.94.51          # Clean up remote VM
  $0 status                       # Check status
  $0 health                       # Health check
  $0 logs control semaphore       # View Semaphore logs
  $0 logs runner01                # View runner01 logs

VM Topology (from deployment-config.yml):
  $control_vm   - Control plane
EOF

    for ((i=0; i<$runner_count; i++)); do
        local runner_name=$(yq eval ".deployment.runners[$i].name" "$CONFIG_FILE")
        local runner_vm=$(yq eval ".deployment.runners[$i].vm_host" "$CONFIG_FILE")
        local runner_shard=$(yq eval ".deployment.runners[$i].inventory_shard" "$CONFIG_FILE")
        echo "  $runner_vm   - $runner_name ($runner_shard)"
    done
    
    cat << EOF

Configuration Files:
  deployment-config.yml - Central configuration (ALL VMs and runners defined here)
  docker-compose.yml    - Service definitions
  .env.vm*             - VM-specific environment variables

EOF
}

# Main script entry point
case ${1:-help} in
    deploy)
        shift
        deploy "$@"
        ;;
    cleanup)
        shift
        if [ -z "$1" ]; then
            log_error "VM host required for cleanup"
            echo "Usage: $0 cleanup <vm_host>"
            echo "Example: $0 cleanup 10.87.94.51"
            exit 1
        fi
        cleanup_vm "$1"
        ;;
    status)
        status
        ;;
    health)
        health
        ;;
    logs)
        shift
        logs "$@"
        ;;
    help|--help|-h)
        show_help
        ;;
    *)
        log_error "Unknown command: $1"
        echo ""
        show_help
        exit 1
        ;;
esac
