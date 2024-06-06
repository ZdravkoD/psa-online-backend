.PHONY: help docker-build docker-run docker-stop

default: help

help: ## Show this help message
	@grep -E '^[a-zA-Z0-9_-]+:.*?## .*$$' $(MAKEFILE_LIST) | sort | awk 'BEGIN {FS = ":.*?## "}; {printf "\033[36m%-30s\033[0m %s\n", $$1, $$2}'

install-shared-lib: ## Install shared library in venv
	@python shared_lib/setup.py install
