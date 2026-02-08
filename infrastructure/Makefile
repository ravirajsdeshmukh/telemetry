# Makefile for centralized deployment management
# All logic delegated to deploy.sh script which uses deployment-config.yml

DEPLOY_SCRIPT := ./deploy.sh

.PHONY: help deploy-control deploy-runner01 deploy-runner02 deploy-runner03 deploy-runner04 deploy-runner05 deploy-runners deploy-all status health logs-control logs-runner01 logs-runner02 logs-runner03 logs-runner04 logs-runner05 stop-control stop-runner01 stop-runner02 stop-runner03 stop-runner04 stop-runner05 stop-runners stop-all restart-control restart-runner01 restart-runner02 restart-runner03 restart-runner04 restart-runner05 cleanup-vm1 cleanup-vm2

help:
	@$(DEPLOY_SCRIPT) help

# Deployment targets
deploy-control:
	@$(DEPLOY_SCRIPT) deploy control

deploy-runner01:
	@$(DEPLOY_SCRIPT) deploy runner01

deploy-runner02:
	@$(DEPLOY_SCRIPT) deploy runner02

deploy-runner03:
	@$(DEPLOY_SCRIPT) deploy runner03

deploy-runner04:
	@$(DEPLOY_SCRIPT) deploy runner04

deploy-runner05:
	@$(DEPLOY_SCRIPT) deploy runner05

deploy-runners:
	@$(DEPLOY_SCRIPT) deploy all-runners

deploy-all:
	@$(DEPLOY_SCRIPT) deploy all

# Status and monitoring
status:
	@$(DEPLOY_SCRIPT) status

health:
	@$(DEPLOY_SCRIPT) health

# Logs
logs-control:
	@$(DEPLOY_SCRIPT) logs control

logs-runner01:
	@$(DEPLOY_SCRIPT) logs runner01

logs-runner02:
	@$(DEPLOY_SCRIPT) logs runner02

logs-runner03:
	@$(DEPLOY_SCRIPT) logs runner03

logs-runner04:
	@$(DEPLOY_SCRIPT) logs runner04

logs-runner05:
	@$(DEPLOY_SCRIPT) logs runner05

# Cleanup targets
cleanup-vm1:
	@$(DEPLOY_SCRIPT) cleanup 10.221.80.101

cleanup-vm2:
	@$(DEPLOY_SCRIPT) cleanup 10.87.94.51

# Stop targets
stop-control:
	@$(DEPLOY_SCRIPT) deploy control down

stop-runner01:
	@$(DEPLOY_SCRIPT) deploy runner01 down

stop-runner02:
	@$(DEPLOY_SCRIPT) deploy runner02 down

stop-runner03:
	@$(DEPLOY_SCRIPT) deploy runner03 down

stop-runner04:
	@$(DEPLOY_SCRIPT) deploy runner04 down

stop-runner05:
	@$(DEPLOY_SCRIPT) deploy runner05 down

stop-runners:
	@$(DEPLOY_SCRIPT) deploy all-runners down

stop-all:
	@$(DEPLOY_SCRIPT) deploy all down

# Restart targets
restart-control:
	@$(DEPLOY_SCRIPT) deploy control restart

restart-runner01:
	@$(DEPLOY_SCRIPT) deploy runner01 restart

restart-runner02:
	@$(DEPLOY_SCRIPT) deploy runner02 restart

restart-runner03:
	@$(DEPLOY_SCRIPT) deploy runner03 restart

restart-runner04:
	@$(DEPLOY_SCRIPT) deploy runner04 restart

restart-runner05:
	@$(DEPLOY_SCRIPT) deploy runner05 restart