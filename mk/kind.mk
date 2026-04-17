CLUSTER_NAME ?= estategap
DOCKER_REGISTRY ?= localhost:5001
KIND_CONFIG ?= tests/kind/cluster.yaml
NAMESPACE ?= estategap-system
KIND_IMAGE_TAG ?= $(TAG)
KIND_BUILD_TARGETS := api-gateway ws-server scrape-orchestrator proxy-manager alert-engine alert-dispatcher spider-workers pipeline ml ai-chat frontend
INGRESS_NGINX_MANIFEST ?= https://raw.githubusercontent.com/kubernetes/ingress-nginx/main/deploy/static/provider/kind/deploy.yaml
LOCAL_PATH_PROVISIONER_MANIFEST ?= https://raw.githubusercontent.com/rancher/local-path-provisioner/v0.0.30/deploy/local-path-storage.yaml
TRAEFIK_CRD_MANIFEST ?= https://raw.githubusercontent.com/traefik/traefik/v3.1/docs/content/reference/dynamic-configuration/kubernetes-crd-definition-v1.yml
SEALED_SECRETS_CRD_MANIFEST ?= https://github.com/bitnami-labs/sealed-secrets/releases/download/v0.27.3/controller-crds.yaml

.PHONY: kind-up kind-down kind-build kind-load kind-deploy kind-seed kind-test kind-logs kind-shell kind-reset helm-lint helm-test helm-conformance helm-template helm-upgrade-test kind-prereqs

kind-up:
	@set -e; \
	if ! docker inspect kind-registry >/dev/null 2>&1; then \
		docker run -d --restart=always -p 5001:5000 --name kind-registry registry:2 >/dev/null; \
	elif [ "$$(docker inspect -f '{{.State.Running}}' kind-registry)" != "true" ]; then \
		docker start kind-registry >/dev/null; \
	fi; \
	kind create cluster --config $(KIND_CONFIG) --name $(CLUSTER_NAME); \
	docker network connect kind kind-registry 2>/dev/null || true; \
	kubectl apply -f tests/kind/registry-configmap.yaml; \
	kubectl apply -f $(LOCAL_PATH_PROVISIONER_MANIFEST); \
	kubectl wait --namespace local-path-storage --for=condition=available deployment/local-path-provisioner --timeout=90s; \
	kubectl apply -f $(TRAEFIK_CRD_MANIFEST); \
	kubectl apply -f $(SEALED_SECRETS_CRD_MANIFEST); \
	kubectl apply -f $(INGRESS_NGINX_MANIFEST); \
	kubectl wait --namespace ingress-nginx --for=condition=ready pod --selector=app.kubernetes.io/component=controller --timeout=120s

kind-down:
	@bash tests/kind/cleanup.sh; \
	docker rm -f kind-registry >/dev/null 2>&1 || true

kind-build:
	@set -e; \
	mkdir -p .make-cache; \
	changed=""; \
	pending="$$(mktemp)"; \
	for target in $(KIND_BUILD_TARGETS); do \
		case "$$target" in \
			frontend) dir="frontend" ;; \
			ws-server) dir="services/ws-server" ;; \
			ml) dir="services/ml" ;; \
			*) dir="services/$$target" ;; \
		esac; \
		current="$$( { \
			find "$$dir" -type f ! -path '*/.venv/*' ! -path '*/__pycache__/*' ! -path '*/.mypy_cache/*' ! -path '*/.pytest_cache/*' ! -path '*/.ruff_cache/*' | sort; \
			find libs -type f 2>/dev/null | sort; \
			find proto -type f 2>/dev/null | sort; \
			[ -f go.work ] && printf '%s\n' go.work || true; \
			[ -f go.work.sum ] && printf '%s\n' go.work.sum || true; \
		} | while read -r path; do sha256sum "$$path"; done | sha256sum | awk '{print $$1}' )"; \
		if [ ! -f ".make-cache/$$target.digest" ] || [ "$$(cat ".make-cache/$$target.digest")" != "$$current" ]; then \
			changed="$$changed $$target"; \
			printf '%s %s\n' "$$target" "$$current" >> "$$pending"; \
		fi; \
	done; \
	if [ -n "$$changed" ]; then \
		docker buildx bake --load -f docker-bake.hcl $$changed; \
		while read -r target digest; do \
			printf '%s\n' "$$digest" > ".make-cache/$$target.digest"; \
		done < "$$pending"; \
	else \
		echo "All kind images are up to date"; \
	fi; \
	rm -f "$$pending"

kind-load:
	@set -e; \
	for image in $(KIND_BUILD_TARGETS); do \
		docker push $(DOCKER_REGISTRY)/$$image:$(KIND_IMAGE_TAG); \
	done

kind-deploy:
	@set -e; \
	helm dependency update helm/estategap; \
	helm upgrade --install estategap helm/estategap \
		-f helm/estategap/values.yaml \
		-f helm/estategap/values-test.yaml \
		--namespace $(NAMESPACE) \
		--create-namespace \
		--wait \
		--timeout 5m; \
	bash tests/kind/port-forward.sh

kind-seed:
	@kubectl wait --for=condition=ready pod -l cnpg.io/cluster=estategap-postgres -n $(NAMESPACE) --timeout=2m && \
		uv run --project tests/fixtures python tests/fixtures/load.py

kind-test:
	@bash tests/helm/install-test.sh && bash tests/helm/schema-test.sh

kind-logs:
	@set -e; \
	if [ -n "$(SERVICE)" ]; then \
		kubectl logs -f -A -l app.kubernetes.io/component=$(SERVICE) --all-containers=true --prefix --max-log-requests=20; \
	elif command -v stern >/dev/null 2>&1; then \
		stern -A .; \
	else \
		kubectl logs -f -A --selector app.kubernetes.io/instance=estategap --all-containers=true --prefix --max-log-requests=20; \
	fi

kind-shell:
	@set -e; \
	if [ -z "$(SERVICE)" ]; then \
		echo "SERVICE is required, e.g. make kind-shell SERVICE=api-gateway"; \
		exit 1; \
	fi; \
	namespace="$$(kubectl get deployment $(SERVICE) -A --no-headers 2>/dev/null | awk 'NR==1 {print $$1}')"; \
	if [ -z "$$namespace" ]; then \
		echo "Deployment $(SERVICE) was not found in the cluster"; \
		exit 1; \
	fi; \
	kubectl exec -it -n "$$namespace" deploy/$(SERVICE) -- /bin/sh

kind-reset:
	@set -e; \
	$(MAKE) kind-down; \
	$(MAKE) kind-up; \
	$(MAKE) kind-build; \
	$(MAKE) kind-load; \
	$(MAKE) kind-deploy; \
	$(MAKE) kind-seed

helm-lint:
	@set -e; \
	helm lint --strict helm/estategap -f helm/estategap/values.yaml; \
	helm lint --strict helm/estategap -f helm/estategap/values.yaml -f helm/estategap/values-staging.yaml; \
	helm lint --strict helm/estategap -f helm/estategap/values.yaml -f helm/estategap/values-production.yaml; \
	helm lint --strict helm/estategap -f helm/estategap/values.yaml -f helm/estategap/values-test.yaml

helm-test:
	@helm unittest helm/estategap --file 'tests/*.yaml'

helm-conformance:
	@helm template estategap helm/estategap -f helm/estategap/values.yaml -f helm/estategap/values-test.yaml | \
		uv run --project tests/fixtures python tests/helm/conformance.py

helm-template:
	@set -e; \
	helm template estategap helm/estategap -f helm/estategap/values.yaml | kubectl apply --dry-run=client -f -; \
	helm template estategap helm/estategap -f helm/estategap/values.yaml -f helm/estategap/values-staging.yaml | kubectl apply --dry-run=client -f -; \
	helm template estategap helm/estategap -f helm/estategap/values.yaml -f helm/estategap/values-production.yaml | kubectl apply --dry-run=client -f -; \
	helm template estategap helm/estategap -f helm/estategap/values.yaml -f helm/estategap/values-test.yaml | kubectl apply --dry-run=client -f -

helm-upgrade-test:
	@bash tests/helm/upgrade-test.sh

# `make kind-prereqs` validates the local toolchain before kind/helm workflows run.
# Required tools:
#   - Docker 24+ with Buildx enabled
#   - kind 0.24+
#   - kubectl 1.30+
#   - Helm 3.14+
#   - helm-unittest plugin (auto-installed when missing)
kind-prereqs:
	@set -e; \
	for tool in kind kubectl helm docker; do \
		if ! command -v "$$tool" >/dev/null 2>&1; then \
			echo "$$tool is required. Install $$tool and rerun make kind-prereqs."; \
			exit 1; \
		fi; \
	done; \
	if ! docker buildx version >/dev/null 2>&1; then \
		echo "docker buildx is required. Install Docker Buildx and rerun make kind-prereqs."; \
		exit 1; \
	fi; \
	if ! helm plugin list 2>/dev/null | grep -q unittest; then \
		helm plugin install https://github.com/helm-unittest/helm-unittest; \
	fi
