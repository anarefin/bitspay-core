# Bits Pay — bitspay-core (Service Specs v6). `make help` lists the targets.
SHELL    := /bin/bash
COMPOSE  := docker compose
JOBS     ?= 3
SERVICES := ledger-service transaction-service wallet-service limits-risk-service pricing-service treasury-service admin-service general-ledger-service
CORE     := ledger-service transaction-service wallet-service limits-risk-service pricing-service
INFRA    := postgres redis kafka kafka-init connect connect-init tigerbeetle object-store object-store-init
# service:apiPort:edgePrefix
ENDPOINTS := ledger-service:8101:ledger transaction-service:8102:transaction wallet-service:8103:wallet limits-risk-service:8105:limits-risk pricing-service:8106:pricing treasury-service:8107:treasury admin-service:8115:admin general-ledger-service:8116:general-ledger
svc  ?=
svcs ?=
args ?=
schema = svc_$(subst -,_,$(patsubst %-service,%,$(svc)))

.DEFAULT_GOAL := help
.PHONY: help build up core infra down reset ps logs status welcome rebuild psql check check-all gradle tools contracts-check verify urls

help: ## List targets
	@grep -hE '^[a-zA-Z_-]+:.*?## ' $(MAKEFILE_LIST) | awk -F':.*?## ' '{printf "  \033[36m%-16s\033[0m %s\n", $$1, $$2}'

.env:
	cp .env.example .env
	@echo "Created .env from .env.example (local-only values)"

build: .env ## bootJar in every service (host JDK 25), then docker compose build
	JOBS=$(JOBS) scripts/gradle-each.sh ALL bootJar
	$(COMPOSE) build $(svcs)

up: .env ## Start the stack (or only svcs="a-service b-service") and wait until healthy
	$(COMPOSE) up -d --wait --wait-timeout 600 $(svcs)
	@$(MAKE) --no-print-directory urls

core: ## Start the core set: ledger-service transaction-service wallet-service limits-risk-service pricing-service
	@$(MAKE) --no-print-directory up svcs="$(CORE)"

infra: .env ## Start infrastructure only (for bootRun / IDE work)
	$(COMPOSE) up -d --wait --wait-timeout 600 $(INFRA)

down: ## Stop the stack (keep data)
	$(COMPOSE) --profile tools --profile cdc down

reset: ## Stop and delete all volumes (fresh Postgres/TB/Kafka)
	$(COMPOSE) --profile tools --profile cdc down -v

ps: ## Container states
	$(COMPOSE) ps

logs: ## Follow logs: make logs svc=wallet-service
	$(COMPOSE) logs -f $(svc)

status: ## Containers, Debezium connector, topic drift, /welcome of every service
	@$(COMPOSE) ps
	@echo; docker/debezium/status.sh || true
	@echo; $(COMPOSE) exec -T kafka bash /bitspay/kafka/verify-topics.sh || true
	@echo; $(MAKE) --no-print-directory welcome || true

welcome: ## GET /welcome on every service, direct and through the edge proxy
	@rc=0; for e in $(ENDPOINTS); do s=$${e%%:*}; r=$${e#*:}; p=$${r%%:*}; x=$${r#*:}; \
	  if curl -fsS -m 3 "http://localhost:$$p/welcome" >/dev/null && curl -fsS -m 3 "http://localhost:8000/$$x/welcome" >/dev/null; \
	  then printf "  \033[32mOK\033[0m   %-24s http://localhost:8000/%s/welcome\n" "$$s" "$$x"; \
	  else printf "  \033[31mDOWN\033[0m %-24s http://localhost:%s/welcome\n" "$$s" "$$p"; rc=1; fi; done; exit $$rc

rebuild: ## Rebuild one service jar + image and restart it: make rebuild svc=wallet-service
	@test -n "$(svc)" || (echo "usage: make rebuild svc=<service>" && exit 1)
	cd services/$(svc) && ./gradlew --console=plain bootJar
	$(COMPOSE) up -d --build --wait $(svc)

psql: ## psql as the service's own role (sees only its schema): make psql svc=ledger-service
	@test -n "$(svc)" || (echo "usage: make psql svc=<service>" && exit 1)
	$(COMPOSE) exec postgres sh -c 'PGPASSWORD="$$PG_SERVICE_PASSWORD" psql -h 127.0.0.1 -U $(schema) -d bitspay'

check: ## ./gradlew check in one service: make check svc=ledger-service
	@test -n "$(svc)" || (echo "usage: make check svc=<service>" && exit 1)
	cd services/$(svc) && ./gradlew check

check-all: ## ./gradlew check in every service
	JOBS=$(JOBS) scripts/gradle-each.sh ALL check

gradle: ## Any Gradle command in one service: make gradle svc=x args="test --tests '*Foo*'"
	cd services/$(svc) && ./gradlew $(args)

tools: .env ## Kafka UI :8089
	$(COMPOSE) --profile tools up -d kafka-ui

contracts-check: ## Validate every pack's contracts (needs PyYAML)
	scripts/contracts.sh check

verify: contracts-check ## Repo-level checks (contracts)

urls:
	@echo "Edge proxy  http://localhost:8000/<svc-short>/welcome   ·   Kafka UI http://localhost:8089 (make tools)"
	@for e in $(ENDPOINTS); do s=$${e%%:*}; r=$${e#*:}; p=$${r%%:*}; x=$${r#*:}; \
	  printf "  %-24s http://localhost:%s/welcome   http://localhost:8000/%s/welcome\n" "$$s" "$$p" "$$x"; done
