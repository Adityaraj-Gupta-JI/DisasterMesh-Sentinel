# DisasterMesh Sentinel task runner.
# Every target below has been run on this machine; those that cannot run here say so
# and exit non-zero rather than pretending to pass. See docs/DEVELOPMENT_STATUS.md.

.DEFAULT_GOAL := help
PY ?= python3
ROOT := $(shell pwd)

define require_dir
	@test -d $(1) || { echo "BLOCKED: $(1) is not present."; exit 1; }
endef

.PHONY: help
help: ## List available targets
	@grep -hE '^[a-zA-Z_-]+:.*?## ' $(MAKEFILE_LIST) \
		| awk 'BEGIN{FS=":.*?## "}{printf "  \033[1m%-22s\033[0m %s\n", $$1, $$2}'

.PHONY: status
status: ## Show which subprojects exist
	@for d in protocol backend ai-service dashboard android-app; do \
		if [ -d $$d ]; then echo "  present  $$d"; else echo "  missing  $$d"; fi; done

# ----------------------------------------------------------------------- tests

.PHONY: test
test: test-protocol test-backend test-ai ## Run every runnable test suite (Python)

.PHONY: test-protocol
test-protocol: ## Core: domain, DMBP, crypto, sync, files, AI rules, e2e, fuzz
	$(call require_dir,protocol)
	cd protocol && $(PY) -m pytest

.PHONY: test-backend
test-backend: ## Gateway API tests
	$(call require_dir,backend)
	cd backend && $(PY) -m pytest

.PHONY: test-ai
test-ai: ## AI service tests (mock adapters)
	$(call require_dir,ai-service)
	cd ai-service && $(PY) -m pytest tests -q

.PHONY: test-dashboard
test-dashboard: ## Dashboard unit tests (requires npm install)
	$(call require_dir,dashboard)
	cd dashboard && npm run test

.PHONY: test-all
test-all: test test-dashboard ## Python suites plus the dashboard

.PHONY: test-android
test-android: ## Android unit tests
	$(call require_dir,android-app)
	cd android-app && ./gradlew testDebugUnitTest

# ------------------------------------------------------------------ run / demo

.PHONY: demo
demo: ## Run the full offline demo (reporter -> relay -> coordinator -> dispatch)
	$(PY) scripts/demo.py

.PHONY: multihop
multihop: ## Simulate multi-hop delivery over a chain (see --help for topologies)
	$(PY) scripts/multihop_demo.py --topology chain --nodes 6

.PHONY: demo-hindi
demo-hindi: ## Run the demo with a Hindi report
	$(PY) scripts/demo.py --language hi

.PHONY: demo-tamil
demo-tamil: ## Run the demo with a Tamil report
	$(PY) scripts/demo.py --language ta

.PHONY: simulate
simulate: ## Run all ten simulator scenarios and write JSON + CSV reports
	$(PY) scripts/run_simulator.py

.PHONY: fixtures
fixtures: ## Regenerate test fixtures from the live pipeline
	$(PY) scripts/make_fixtures.py

.PHONY: contract
contract: ## Regenerate the cross-language priority contract (review the diff!)
	$(PY) scripts/make_priority_contract.py
	@echo ""
	@echo "The diff is the review: a changed expected score must be justified."

.PHONY: parity
parity: ## Check the Python and Kotlin priority engines have not drifted
	cd protocol && $(PY) -m pytest tests/test_engine_parity.py tests/test_priority_contract.py -q

.PHONY: reset-demo
reset-demo: ## Wipe the gateway database and reseed simulated resources
	$(PY) scripts/reset_demo_data.py

.PHONY: run-backend
run-backend: ## Start the gateway API on :8000
	$(call require_dir,backend)
	cd backend && PYTHONPATH=$(ROOT)/protocol:. $(PY) -m uvicorn app.main:app --reload --port 8000

.PHONY: run-ai
run-ai: ## Start the AI service on :8001 in mock mode
	$(call require_dir,ai-service)
	cd ai-service && DMS_AI_MODE=mock PYTHONPATH=$(ROOT)/protocol:. \
		$(PY) -m uvicorn app.main:app --reload --port 8001

.PHONY: run-dashboard
run-dashboard: ## Start the dashboard dev server on :5173
	$(call require_dir,dashboard)
	cd dashboard && npm run dev

.PHONY: build-dashboard
build-dashboard: ## Type-check and build the dashboard
	$(call require_dir,dashboard)
	cd dashboard && npm run build

.PHONY: apk
apk: ## Build the Android debug APK
	$(call require_dir,android-app)
	cd android-app && ./gradlew assembleDebug


# ----------------------------------------------------------------- quality

.PHONY: fmt
fmt: ## Format Python sources
	ruff format protocol backend ai-service scripts

.PHONY: lint
lint: ## Lint Python sources
	ruff check protocol backend ai-service scripts

.PHONY: typecheck
typecheck: ## Type-check the dashboard
	cd dashboard && npx tsc --noEmit

.PHONY: verify
verify: lint test test-dashboard simulate demo ## Everything that can be verified here
	@echo ""
	@echo "All runnable checks passed. Android remains unbuilt — see docs/KNOWN_LIMITATIONS.md."
