# Running Bits Pay with Docker — a beginner's tutorial

This guide takes you from "I have never used Docker" to "the whole Bits Pay backend (infrastructure + services)
is running on my laptop". Every command is meant to be run from the `bitspay-core/` folder unless stated otherwise.

> **Status of the outputs below:** the commands come straight from `compose.yaml` and the `Makefile`.
> Output blocks marked *expected* show what you should roughly see; exact timings and IDs will differ on your machine.

---

## 1. What you are about to run

Bits Pay is a set of small Spring Boot **services**. They need shared **infrastructure** to work
(a database, a message broker, a cache, and so on). Docker lets you start all of it with a few commands,
without installing Postgres, Kafka, etc. on your machine.

```
                         ┌──────────────── your laptop (Docker) ────────────────┐
                         │                                                       │
  you (curl / browser) ─►│  SERVICES (Spring Boot, Java 25)                      │
                         │   ledger 8101 · transaction 8102 · wallet 8103        │
                         │   limits-risk 8105 · pricing 8106 · treasury 8107     │
                         │   admin 8115 · general-ledger 8116                    │
                         │          │                                            │
                         │          ▼                                            │
                         │  INFRASTRUCTURE                                       │
                         │   Postgres 5432      – one database, one schema/svc   │
                         │   Redis 6379         – cache + fast state             │
                         │   Kafka 19092        – events between services        │
                         │   Debezium 8083      – copies DB "outbox" rows→Kafka  │
                         │   TigerBeetle 3001   – the ledger engine (ledger-svc) │
                         │   RustFS 19100/19101 – S3-compatible file storage     │
                         │                                                       │
                         │  INIT JOBS (run once, then exit)                      │
                         │   kafka-init · connect-init · object-store-init       │
                         └───────────────────────────────────────────────────────┘
```

### Docker words in plain English

| Word | Meaning | In this project |
|---|---|---|
| **Image** | A read-only template (like an installer). | `postgres:18.6`, `bitspay/ledger-service:local` |
| **Container** | A running copy of an image (a tiny isolated process). | `bitspay-postgres-1`, `bitspay-ledger-service-1` |
| **Volume** | Disk storage that survives container restarts. | `pg-data`, `kafka-data`, `tb-data`, ... |
| **Network** | A private virtual network so containers can find each other by name. | `bitspay` (e.g. services reach the DB at `postgres:5432`) |
| **Port mapping** | `"8101:8101"` = host port : container port. Lets *you* reach a container. | `localhost:8101` -> ledger-service |
| **Dockerfile** | Recipe to build an image. | `docker/service.Dockerfile` |
| **Docker Compose** | A file (`compose.yaml`) describing many containers to start together. | This whole project |
| **Healthcheck** | A command Docker runs to know a container is *ready*, not just started. | e.g. `pg_isready` for Postgres |

---

## 2. Prerequisites

| Tool | Why | Check it |
|---|---|---|
| **Docker Desktop** (macOS/Windows) or Docker Engine + Compose plugin (Linux) | Runs the containers. Needs **Compose v2.24+**. | `docker --version` and `docker compose version` |
| **~10 GB of memory given to Docker** | The stack has ~15 containers; limits add up to about 8–9 GB. | Docker Desktop -> Settings -> Resources -> Memory |
| **JDK 25** | `make build` compiles each service's jar on your machine first (see "Why do I need Java?" below). | `java -version` -> should say 25 |
| **make** | Short commands (`make up`). | `make --version` |
| **curl** | To test the services. | `curl --version` |

**macOS tips**
- Install Docker Desktop, open it once, and wait until the whale icon says "running".
- Raise memory: Settings -> Resources -> Memory -> 10 GB (or more) -> *Apply & restart*.
- JDK 25 via Homebrew: `brew install --cask temurin@25` (or use SDKMAN: `sdk install java 25-tem`).
- `make` ships with Xcode command line tools: `xcode-select --install`.

**Windows:** use WSL2 and run everything inside the Linux shell. **Linux:** make sure your user is in the `docker` group.

### Why do I need Java if everything is in Docker?
`docker/service.Dockerfile` is a *runtime-only* image. It does **not** compile code. It copies a ready-made jar from
`services/<svc>/build/libs/`. So the order is: (1) build jars with Gradle on your machine, (2) package them into images.
`make build` does both for you. If you skip step 1 the image build fails because no jar exists.

---

## 3. Get oriented (2 minutes)

```
bitspay-core/
├── compose.yaml          ← the "master plan": every container, port, env var, startup order
├── Makefile              ← friendly shortcuts that call docker compose
├── .env.example          ← template for secrets/config (committed)
├── .env                  ← your local copy (git-ignored)
├── docker/               ← config files mounted into containers (DB init, Kafka topics, Debezium, ...)
│   └── service.Dockerfile
├── scripts/              ← helper scripts (build every service, contracts check)
└── services/<name>/      ← one Spring Boot project per service (own gradlew)
```

See all shortcuts any time:

```bash
make help
```

---

## 4. Configure: the `.env` file

All secrets and tunables live in `.env`. You do **not** have to create it by hand: `make build`, `make up`,
`make infra` and `make tools` copy `.env.example` to `.env` automatically if it is missing.

To do it yourself:

```bash
cp .env.example .env
```

What the variables are for (open `.env.example` to see the local-only default values and formats):

| Group | Variable names | Used for |
|---|---|---|
| Postgres | `PG_ADMIN_PASSWORD`, `PG_SERVICE_PASSWORD`, `PG_DEBEZIUM_PASSWORD` | Admin login, the password every `svc_*` role uses, Debezium's replication user |
| Object store | `S3_ACCESS_KEY`, `S3_SECRET_KEY` | RustFS credentials (also what services use) |
| Platform keys | `BITSPAY_PLATFORM_HMAC_KEY`, `LEDGER_JOURNAL_MAC_KEY` | Signing / integrity keys |
| Field encryption | `FIELD_CIPHER_KEY_LEDGER`, `_TRANSACTION`, `_WALLET`, `_LIMITS_RISK`, `_PRICING`, `_TREASURY`, `_ADMIN`, `_GENERAL_LEDGER` | One encryption key per service |
| Optional overrides | `POSTGRES_IMAGE`, `REDIS_IMAGE`, `KAFKA_IMAGE`, `DEBEZIUM_CONNECT_IMAGE`, `TIGERBEETLE_IMAGE`, `OBJECT_STORE_IMAGE`, `OBJECT_STORE_CLIENT_IMAGE`, `CURL_IMAGE`, `KAFKA_UI_IMAGE`, `KAFKA_CLUSTER_ID` | Pin/swap image versions |

Rules of thumb:
- `.env` is for **local development only**. Never commit it, never reuse its values elsewhere.
- If you edit `.env`, restart the affected containers: `docker compose up -d` (Compose re-creates what changed).
- If compose complains `variable is not set`, a name above is missing/empty in your `.env`.

---

## 5. The fast path (copy-paste)

```bash
cd bitspay-core

make build      # 1. compile every service (Gradle) + build Docker images   (slowest step: several minutes the 1st time)
make up         # 2. start infra -> init jobs -> services, wait until all healthy
make welcome    # 3. smoke-test each service
make status     # 4. full health report
```

### Step 1 — `make build`
Runs `./gradlew bootJar` in every service (3 at a time, `JOBS=3`), then `docker compose build`.
The first run downloads Gradle and dependencies, so be patient. Lower `JOBS` on a small machine:
`make build JOBS=1`.

*Expected end of output:* a series of `naming to docker.io/bitspay/<service>:local` lines and no errors.

### Step 2 — `make up`
Runs `docker compose up -d --wait --wait-timeout 600`:
- `-d` = detached (runs in the background, you get your terminal back)
- `--wait` = do not return until every container is healthy (or 10 minutes pass)

First start also **downloads** the infra images (Postgres, Kafka, ...), so allow several minutes.

*Expected end of output:* a table of containers all `Healthy`/`Started`, then a list of URLs.

### Step 3 — `make welcome`
Calls `GET /welcome` on every service.

```
  OK   ledger-service   http://localhost:8000/ledger/welcome
```

> See [section 11](#11-known-gaps-read-this-before-you-file-a-bug).

### Step 4 — `make status`
Shows container states, the Debezium connector status, Kafka topic drift check, and the welcome check.

### Low memory? Start less
```bash
make core                                  # ledger, transaction, wallet, limits-risk, pricing
make up svcs="ledger-service wallet-service"   # pick your own
```
Infra containers needed by those services start automatically (via `depends_on`).

---

## 6. What happens during `make up`

Compose starts things in dependency order, waiting for **healthchecks**:

```
1. postgres, redis, kafka, tigerbeetle, object-store      (infra; start in parallel)
      │ postgres first run executes docker/postgres/init/*  → creates roles + schemas svc_*, outbox tables, Debezium publication
2. kafka-init        (after kafka healthy)  → creates all topics + a <topic>.dlq for each; then exits 0
   object-store-init (after object-store healthy) → creates buckets; then exits 0
3. connect (Debezium) (after postgres healthy + kafka-init done)
   connect-init      (after connect healthy) → registers the outbox connector; then exits 0
4. services          (after the infra *they* need is healthy)
      ledger: postgres + kafka-init + tigerbeetle
      wallet: postgres + kafka-init + redis + object-store(+init)
      others: postgres + kafka-init (+ redis for transaction, limits-risk, admin)
```

Good to know:
- **Init jobs exit on purpose.** `kafka-init`, `connect-init`, `object-store-init` show `Exited (0)` in `docker compose ps -a`. That means success.
- **Services do not wait for each other.** They call each other lazily with timeouts, so start order between services does not matter.
- Each service runs **Flyway** at startup, which applies its database migration.
- A service has `start_period: 60s` — it may show "starting" for a minute before it turns healthy.

---

## 7. Verify everything works

### 7.1 Containers
```bash
make ps                        # = docker compose ps
docker compose ps -a           # also shows the finished init jobs
```
You want every long-running container `running (healthy)`.

### 7.2 Services
```bash
curl -s http://localhost:8101/welcome                                   # service API
curl -s http://localhost:9101/actuator/health/readiness                  # management port: {"status":"UP"}
```
Port pattern: API `81xx`, management `91xx` (ledger 8101/9101, transaction 8102/9102, wallet 8103/9103,
limits-risk 8105/9105, pricing 8106/9106, treasury 8107/9107, admin 8115/9115, general-ledger 8116/9116).

### 7.3 Database (each service sees only its own schema)
```bash
make psql svc=ledger-service        # opens psql as role svc_ledger
```
Inside psql: `\dt` lists tables (you should see `outbox` and `processed_event`, plus Flyway's history table);
`\q` quits.

Admin view, all schemas:
```bash
docker compose exec postgres psql -U bitspay_admin -d bitspay -c '\dn'
```

### 7.4 Kafka
```bash
make tools                    # starts Kafka UI
```
Open http://localhost:8089 -> cluster `bitspay` -> Topics (you should see many topics and their `.dlq` twins) and
Kafka Connect.

List topics from the command line:
```bash
docker compose exec kafka /opt/kafka/bin/kafka-topics.sh --bootstrap-server localhost:9092 --list
```

### 7.5 Debezium (outbox -> Kafka)
```bash
curl -s http://localhost:8083/connectors            # lists registered connectors
docker/debezium/status.sh                            # connector state (also part of `make status`)
```

### 7.6 Object store (S3)
Open the console http://localhost:19101 and log in with `S3_ACCESS_KEY` / `S3_SECRET_KEY` from your `.env`.
The S3 API is at http://localhost:19100.

### 7.7 Redis
```bash
docker compose exec redis redis-cli ping            # PONG
```

---

## 8. Everyday commands

| I want to... | Command |
|---|---|
| Follow logs of one service | `make logs svc=wallet-service` (Ctrl+C to stop following) |
| Follow all logs | `make logs` |
| See container states | `make ps` |
| Restart one container | `docker compose restart wallet-service` |
| Rebuild + restart one service after a code change | `make rebuild svc=wallet-service` |
| Stop everything, **keep** data | `make down` |
| Stop everything and **delete all data** (fresh DB/Kafka/TigerBeetle) | `make reset` |
| Start only infra (run a service from your IDE) | `make infra`, then `cd services/wallet-service && ./gradlew bootRun` |
| Run tests of one service | `make check svc=ledger-service` (integration tests use Testcontainers -> need Docker running) |
| Open a shell in a container | `docker compose exec wallet-service sh` |

### Develop in the IDE against Dockerised infra
```bash
make infra                                   # postgres, redis, kafka, connect, tigerbeetle, object store + init jobs
cd services/wallet-service
./gradlew bootRun                            # profile "local": other services are WireMock stubs on :8099
```
Defaults in each service point at `localhost` (Postgres 5432, Kafka **19092**, Redis 6379), matching the published ports.

### `make down` vs `make reset`
- `make down` removes containers but keeps **volumes**, so your database, topics and ledger data are still there next time.
- `make reset` also removes volumes (`down -v`). Use it when you want a clean slate or after a failed first start.
  **All local data is lost.**

---

## 9. The same thing without `make` (learn the real commands)

| `make` target | Underlying command |
|---|---|
| `make build` | `scripts/gradle-each.sh ALL bootJar` then `docker compose build` |
| `make up` | `docker compose up -d --wait --wait-timeout 600` |
| `make up svcs="a b"` | `docker compose up -d --wait --wait-timeout 600 a b` |
| `make infra` | `docker compose up -d --wait --wait-timeout 600 postgres redis kafka kafka-init connect connect-init tigerbeetle object-store object-store-init` |
| `make tools` | `docker compose --profile tools up -d kafka-ui` |
| `make ps` | `docker compose ps` |
| `make logs svc=x` | `docker compose logs -f x` |
| `make down` | `docker compose --profile tools --profile cdc down` |
| `make reset` | `docker compose --profile tools --profile cdc down -v` |
| `make rebuild svc=x` | `(cd services/x && ./gradlew bootJar)` then `docker compose up -d --build --wait x` |

Handy raw Docker commands:
```bash
docker ps                          # running containers (all projects)
docker images                      # images on your machine
docker volume ls                   # volumes (look for bitspay_*)
docker stats                       # live CPU/memory per container
docker compose config -q           # validate compose.yaml (prints nothing if OK)
docker system df                   # how much disk Docker uses
```

---

## 10. Troubleshooting

| Symptom | Likely cause | Fix |
|---|---|---|
| `Cannot connect to the Docker daemon` | Docker Desktop not running | Start Docker Desktop, wait for "running" |
| Containers die with **exit code 137** / `OOMKilled`; machine very slow | Docker has too little memory | Raise Docker memory to 10 GB+, or `make core` / start fewer services |
| `bind: address already in use` | Something on your machine uses 5432, 6379, 8083, 8101… | Stop the local Postgres/Redis (`brew services stop postgresql`), or find it: `lsof -i :5432` |
| Image build fails: no jar / `build/libs/*.jar` not found | Jars not built | Run `make build` (not just `docker compose build`) |
| `make build` fails with Java/toolchain error | Wrong or missing JDK | `java -version` must be 25; set `JAVA_HOME` |
| `variable is not set` / blank password | `.env` missing or incomplete | `cp .env.example .env` |
| A container is `unhealthy` / `make up` times out | Service failed to start | `docker compose logs --tail 100 <name>`; the first error is usually the cause |
| `tigerbeetle` unhealthy or restarts on Docker Desktop | It needs io_uring (`seccomp=unconfined`, `IPC_LOCK`), which some Docker Desktop/kernel combinations restrict | Update Docker Desktop; on Linux check kernel version; ledger-service depends on it so ledger won't start |
| Service starts but DB errors about existing tables/roles | Old volume from an earlier layout | `make reset`, then `make up` |
| `manifest unknown` / image not found | Pinned tag unavailable in your registry mirror | Override the image in `.env` (e.g. `POSTGRES_IMAGE=postgres:18`) |
| `no matching manifest for linux/arm64` (Apple Silicon) | An image is amd64-only | Add `platform: linux/amd64` for that service or use another tag; amd64 emulation is slower |
| Kafka topic missing | `kafka-init` failed | `docker compose logs kafka-init`; then `docker compose up kafka-init` |
| Debezium connector missing/failed | `connect-init` failed or Postgres not ready | `docker compose logs connect-init connect`; `docker/debezium/status.sh` |
| Everything is weird | Stale state | `make reset && make build && make up` |

Reading logs well: `docker compose logs --tail 200 -f <service>`. Spring Boot prints `Started ...Application in N seconds`
when it is ready; `Flyway` lines show migrations; ERROR lines near the end tell you why it crashed.

---

## 11. Known gaps (read this before you file a bug)

Found while preparing this tutorial by comparing `README.md`, `Makefile` and `compose.yaml`:

1. **Only 8 of the 12 services are in `compose.yaml`.** disbursement (8108), support (8109), compliance (8111)
   and finance-ops (8112) have code and specs but no compose entry, no Makefile entry. The README still says
   "12 services". `make up` starts 8.
2. ~~The edge proxy (port 8000) was not in `compose.yaml`.~~ Fixed: the `edge-proxy` service now runs nginx on
   port 8000. Run `make up` (or `docker compose up -d edge-proxy`) and `localhost:8000/<svc>/welcome` works.
3. **ClickHouse and `tb-cdc`** have config files only / are opt-in and are not part of the default stack.
4. **`make build` requires JDK 25 on the host.** A multi-stage Dockerfile (build the jar inside Docker) would let
   `docker compose up --build` work with only Docker installed. No `.dockerignore` exists either.
5. **Security mode is `trusted-headers`.** Services trust forwarded identity headers; there is no auth server.
   Calls other than `/welcome` and actuator need the correct headers (see each service's `docs/SPEC.md`).

---

## 12. Cheat sheet

```bash
# first time
make build && make up && make status

# daily
make up                      # start (data kept)
make ps                      # state
make logs svc=ledger-service # logs
make rebuild svc=ledger-service   # after code changes
make down                    # stop, keep data

# clean slate
make reset && make up

# low memory
make core

# infra only (IDE development)
make infra

# UIs
Kafka UI      http://localhost:8089        (make tools)
RustFS        http://localhost:19101
Debezium API  http://localhost:8083/connectors
```

| Port | What |
|---|---|
| 5432 | Postgres (`bitspay` db, user `bitspay_admin`) |
| 6379 | Redis |
| 19092 | Kafka (from your laptop; containers use `kafka:9092`) |
| 8083 | Debezium Connect |
| 3001 | TigerBeetle |
| 19100 / 19101 | Object store API / console |
| 8089 | Kafka UI (tools profile) |
| 81xx / 91xx | Service API / management (actuator) |

### Glossary
- **Outbox pattern:** a service writes events into its own `outbox` table in the same DB transaction as its data;
  Debezium reads that table and publishes to Kafka, so events are never lost.
- **KRaft:** Kafka's built-in coordination mode (no ZooKeeper).
- **DLQ:** dead-letter queue — `<topic>.dlq` holds messages that could not be processed.
- **Flyway:** applies versioned SQL migrations at service startup.
- **Actuator:** Spring Boot's built-in health/metrics endpoints (management port 91xx).
- **Healthy vs started:** *started* = process exists; *healthy* = its healthcheck passed.
