.DEFAULT_GOAL := help

-include config.mk

PYTHON ?= python3

.PHONY: help setup install mqtt preview proxy run run-sim run-mock test

help:
	@echo ""
	@echo "\033[2mSetup\033[0m"
	@echo "  \033[36msetup\033[0m        Install Python deps (uv required)"
	@echo "  \033[36minstall\033[0m      Install with all optional deps (mujoco, onnx, torch)"
	@echo ""
	@echo "\033[2mDev\033[0m"
	@echo "  \033[36mmqtt\033[0m         Start local Mosquitto broker (optional. Cloud broker used by default)"
	@echo "  \033[36mpreview\033[0m      Serve dashboard at http://localhost:8080"
	@echo "  \033[36mproxy\033[0m        Start local Claude proxy (personal account, port 7337)"
	@echo ""
	@echo "\033[2mRun\033[0m"
	@echo "  \033[36mrun\033[0m          Run policy on real robot   (requires CONFIG=configs/go2.yaml)"
	@echo "  \033[36mrun-sim\033[0m      Run policy in MuJoCo sim   (requires CONFIG=configs/go2_sim.yaml)"
	@echo "  \033[36mrun-mock\033[0m     Run policy with mock robot  (no hardware)"
	@echo ""
	@echo "\033[2mTest\033[0m"
	@echo "  \033[36mtest\033[0m         Run test suite"
	@echo ""

setup:
	uv sync

install:
	uv sync --extra all

mqtt:
	@echo "Local MQTT broker: mqtt://localhost:1883"
	@echo "Local WebSocket:   ws://localhost:9001"
	@echo ""
	docker compose -f docker/docker-compose.yml up mqtt

preview:
	@printf "\n\033[1;36m  Dashboard: http://localhost:8080\033[0m\n\n"
	$(PYTHON) -m http.server 8080 --directory dashboard

proxy:
	@printf "\n\033[1;36m  Claude proxy: http://127.0.0.1:7337\033[0m\n\n"
	node local-proxy.js

run:
	@test -n "$(CONFIG)" || (echo "Error: set CONFIG= e.g. make run CONFIG=configs/go2.yaml"; exit 1)
	$(PYTHON) runner.py --config $(CONFIG)

run-sim:
	@test -n "$(CONFIG)" || (echo "Error: set CONFIG= e.g. make run-sim CONFIG=configs/go2_sim.yaml"; exit 1)
	$(PYTHON) runner.py --config $(CONFIG) --sim

run-mock:
	$(PYTHON) runner.py --config configs/mock.yaml --mock

test:
	$(PYTHON) -m pytest
