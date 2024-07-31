.PHONY: help docker-build docker-run docker-stop

VENV_PYTHON := .venv/bin/python3.12

default: help

help: ## Show this help message
	@grep -E '^[a-zA-Z0-9_-]+:.*?## .*$$' $(MAKEFILE_LIST) | sort | awk 'BEGIN {FS = ":.*?## "}; {printf "\033[36m%-30s\033[0m %s\n", $$1, $$2}'

start-azure-functions: ## Start Azure Functions
	@pushd azure-functions && make start && popd > /dev/null

start-scraper: ## Start scraper
	@(cd scraper && $(MAKE) -f Makefile start)

python-test:
	@$(VENV_PYTHON) --version