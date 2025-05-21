.PHONY: check-py

check-py: ## Run code quality tools.
	: 🚀 installing uv deps
	uv sync
	: 🚀 Linting code: Running pre-commit
	uv run pre-commit run -a
	@$(MAKE) typecheck
	: 🚀 Checking for obsolete dependencies: Running deptry
	uv run deptry .

.PHONY: check
check: check-py 

typecheck: ## just the typechecks
	: 🚀 Static type checking: Running mypy
	uv run mypy

.PHONY: test-py
test-py: ## Test the code with pytest
	uv run pytest ./gohumanloop --cov --cov-config=pyproject.toml --cov-report=xml --junitxml=junit.xml

.PHONY: test
test: test-py

.PHONY: build
build: clean-build ## Build wheel file using uv
	: 🚀 Creating wheel file
	uv build

.PHONY: clean-build
clean-build: ## clean build artifacts
	@rm -rf dist

.PHONY: publish-py
publish-py: ## publish a release to pypi. with UV_PUBLISH_TOKEN
	: 🚀 Publishing.
	uv publish

.PHONY: publish
publish: publish-py

.PHONY: publish-ts
publish-ts: build-ts
	npm -C humanlayer-ts publish

.PHONY: build-and-publish
build-and-publish: build publish ## Build and publish.

.PHONY: githooks
githooks:
	:
	: 🚀 Installing pre-push hook
	:
	echo 'make check test' > .git/hooks/pre-push
	chmod +x .git/hooks/pre-push

.PHONY: help
help:
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | awk 'BEGIN {FS = ":.*?## "}; {printf "\033[36m%-20s\033[0m %s\n", $$1, $$2}'

.DEFAULT_GOAL := help
