.PHONY: help lint site

help: ## Show this help message
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST)

lint: ## Check the syntax of each playbook
	ansible-playbook ansible/playbooks/site.yaml --syntax-check

site: ## Apply the site playbook
	ansible-playbook ansible/playbooks/site.yaml
