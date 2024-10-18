.PHONY: help docker-build docker-run docker-stop start

default: help

help: ## Show this help message
	@grep -E '^[a-zA-Z0-9_-]+:.*?## .*$$' $(MAKEFILE_LIST) | sort | awk 'BEGIN {FS = ":.*?## "}; {printf "\033[36m%-30s\033[0m %s\n", $$1, $$2}'

docker-build: ## Build the docker image
	docker build -t scraper .

docker-run: ## Run the docker container
	docker run --rm --name scraper scraper

docker-stop: ## Stop the docker container
	docker stop scraper
	docker rm scraper

docker-build-for-aci: ## Build the docker image for Azure Container Instances
	docker build -t scraper-aci . --platform amd64

docker-tag: ## Tag the docker image
	docker tag scraper-aci kfzzdravko/psa-online-scraper

docker-push: ## Push the docker image
	docker push kfzzdravko/psa-online-scraper

start: ## Run the scraper
	python scraper/main.py
