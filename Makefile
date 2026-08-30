# DisasterMesh Sentinel task runner.
# Targets whose subproject does not exist yet fail with a clear message
# rather than pretending to succeed. See docs/DEVELOPMENT_STATUS.md.

.DEFAULT_GOAL := help
PY ?= python3

define require_dir
	@test -d $(1) || { echo "BLOCKED: $(1) is not scaffolded yet. See docs/DEVELOPMENT_STATUS.md"; exit 1; }
endef

.PHONY: help
help: ## List available targets
	@grep -hE '^[a-zA-Z_-]+:.*?## ' $(MAKEFILE_LIST) \
		| awk 'BEGIN{FS=":.*?## "}{printf "  %-20s %s\n", $$1, $$2}'

.PHONY: status
status: ## Show which subprojects exist
	@for d in protocol backend ai-service dashboard android-app; do \
		if [ -d $$d ]; then echo "  present  $$d"; else echo "  missing  $$d"; fi; done

.PHONY: fmt
fmt: ## Format Python sources
	ruff format .

.PHONY: lint
lint: ## Lint Python sources
	ruff check .

.PHONY: test-protocol
test-protocol: ## Run DMBP protocol tests
	$(call require_dir,protocol)
	$(PY) -m pytest protocol -q

.PHONY: test-backend
test-backend: ## Run backend tests
	$(call require_dir,backend)
	$(PY) -m pytest backend -q

.PHONY: test-ai
test-ai: ## Run AI service tests (mock adapters)
	$(call require_dir,ai-service)
	$(PY) -m pytest ai-service -q

.PHONY: test
test: test-protocol test-backend test-ai ## Run all Python tests

.PHONY: run-backend
run-backend: ## Start the backend API
	$(call require_dir,backend)
	$(PY) -m uvicorn backend.app.main:app --reload --port 8000

.PHONY: run-ai
run-ai: ## Start the AI service in mock mode
	$(call require_dir,ai-service)
	DMS_AI_MODE=mock $(PY) -m uvicorn app.main:app --reload --port 8001 --app-dir ai-service

.PHONY: run-dashboard
run-dashboard: ## Start the dashboard dev server
	$(call require_dir,dashboard)
	cd dashboard && npm run dev

.PHONY: build-dashboard
build-dashboard: ## Build the dashboard
	$(call require_dir,dashboard)
	cd dashboard && npm run build

.PHONY: apk
apk: ## Build the Android debug APK (BLOCKED: no Gradle wrapper, no ANDROID_HOME)
	$(call require_dir,android-app)
	@test -x android-app/gradlew || { echo "BLOCKED: no Gradle wrapper. See docs/LOCAL_DEVELOPMENT.md"; exit 1; }
	cd android-app && ./gradlew assembleDebug
