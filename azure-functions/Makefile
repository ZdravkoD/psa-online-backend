.PHONY: help start smoke-test

default: help

help: ## Show this help message
	@grep -E '^[a-zA-Z0-9_-]+:.*?## .*$$' $(MAKEFILE_LIST) | sort | awk 'BEGIN {FS = ":.*?## "}; {printf "\033[36m%-30s\033[0m %s\n", $$1, $$2}'

start: ## Start the Azure Functions
	@func host start

install: ## Install the Azure Functions
	@pip install -r requirements.txt

deploy-staging: ## Deploy the Azure Functions to staging
	@func azure functionapp publish psa-online-functions --slot staging

smoke-test: ## Run read-only smoke tests against a deployed Functions base URL
	@test -n "$(BASE_URL)" || (echo "BASE_URL is required, e.g. make smoke-test BASE_URL=https://.../api" && exit 1)
	@python smoke_test.py --base-url "$(BASE_URL)"
