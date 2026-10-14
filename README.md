# bitspay-core

Bits Pay core backend: 12 services in one repo, built from **Service Specs v6**. Each service is a standalone
Spring Boot + Gradle project (kernel K9). The whole system runs locally with one `compose.yaml`.

## Quick start

Prerequisites: Docker (Compose v2.24+, about 10 GB of memory for Docker), JDK 25, make, curl.

```bash
make build      # ./gradlew bootJar in every service, then docker compose build
make up         # infra + init jobs + 12 services, waits until healthy
make welcome    # GET /welcome on every service (direct + edge proxy)
make status     # containers, Debezium connector, Kafka topic drift, welcome
make down       # stop (keep data)  ·  make reset = stop + delete volumes
```

Use `make up svcs="ledger-service wallet-service"` or `make core` on machines with less memory.
Use `make infra` for infrastructure only, when you run a service from the IDE.

New to Docker? Follow the step-by-step guide: [docs/DOCKER-TUTORIAL.md](docs/DOCKER-TUTORIAL.md).

## Services

| # | Service | Ports (API / mgmt) | Schema | Modules | Welcome (edge) |
|---|---|---|---|---|---|
| 01 | ledger-service | 8101 / 9101 | `svc_ledger` | — | http://localhost:8000/ledger/welcome |
| 02 | transaction-service | 8102 / 9102 | `svc_transaction` | — | http://localhost:8000/transaction/welcome |
| 03 | wallet-service | 8103 / 9103 | `svc_wallet` | wallet,partner | http://localhost:8000/wallet/welcome |
| 05 | limits-risk-service | 8105 / 9105 | `svc_limits_risk` | — | http://localhost:8000/limits-risk/welcome |
| 06 | pricing-service | 8106 / 9106 | `svc_pricing` | pricing,campaign | http://localhost:8000/pricing/welcome |
| 07 | treasury-service | 8107 / 9107 | `svc_treasury` | — | http://localhost:8000/treasury/welcome |
| 08 | disbursement-service | 8108 / 9108 | `svc_disbursement` | — | http://localhost:8000/disbursement/welcome |
| 09 | support-service | 8109 / 9109 | `svc_support` | — | http://localhost:8000/support/welcome |
| 11 | compliance-service | 8111 / 9111 | `svc_compliance` | — | http://localhost:8000/compliance/welcome |
| 12 | finance-ops-service | 8112 / 9112 | `svc_finance_ops` | reconciliation,reporting | http://localhost:8000/finance-ops/welcome |
| 15 | admin-service | 8115 / 9115 | `svc_admin` | governance,notification | http://localhost:8000/admin/welcome |
| 16 | general-ledger-service | 8116 / 9116 | `svc_general_ledger` | — | http://localhost:8000/general-ledger/welcome |

Each service also answers directly on its API port, for example `curl http://localhost:8101/welcome`.

## Layout

```
compose.yaml            infra → init jobs → services → tools (profile "tools")
docker/                 Postgres init (schemas, roles, outbox, publication), Kafka topics, Debezium,
                        TigerBeetle, ClickHouse, object store, nginx edge proxy, service.Dockerfile
docs/global/            kernel: GLOBAL-CONVENTIONS, CONTRACT-MODEL, CHANGE-PROCESS, schemas, generated/, tools/
services/<svc>/         standalone Gradle project
  CLAUDE.md             agent instructions (from the pack, paths adjusted)
  docs/                 the v6 pack: SPEC.md, contracts/, changes/, stubs/, fixtures/, PROGRESS.md
  src/                  Spring Boot app; GET /welcome; Flyway V1 = outbox + processed_event (kernel K8.2)
                        layered packages (kernel K9): controller · dto · service · repository (Spring Data JPA) ·
                        entity · mapper · exception · client · messaging · config — checked by ArchitectureTest
scripts/                gradle-each.sh (task in N services) · contracts.sh (contracts.py on this layout)
```

## Working on one service

```bash
cd services/wallet-service
./gradlew check                       # unit (*Test, incl. ArchUnit) + integration (*IT, Testcontainers) + coverage gate
./gradlew bootRun                     # profile local: other services = WireMock on :8099
make rebuild svc=wallet-service       # (repo root) new jar + image, restart in the stack
```

Contracts: `scripts/contracts.sh check wallet-service` (needs Python 3.9+ and PyYAML).

## Notes

- Kafka topics come from `docs/global/generated/topics.json`, plus a `<topic>.dlq` for each one. Auto-create is off.
- `tb-cdc` (TigerBeetle → RabbitMQ) is opt-in until ledger WP-2 verifies its flags: `docker compose --profile cdc up -d tb-cdc`.
- `.env` is local-only and git-ignored. Image tags can be overridden there.
