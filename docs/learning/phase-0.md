# Phase 0 — Project Setup

## The big picture

```
 C:\falcon
   ├─① Git          time machine for code
   ├─② Folders      a place for everything
   ├─③ Secrets      .env (private) vs .env.example (public)
   ├─④ Docker       run PostgreSQL without installing it
   └─⑤ Verify       database answers, with PostGIS + pgvector
```

## ① Git

```
 commit 1 ──► commit 2 ──► commit 3
                  ▲             │
                  └── go back ──┘
```

- `.gitignore` — files Git must never save (secrets, node_modules, caches, uploaded evidence).
- `.gitattributes` — forces LF line endings. Windows uses `\r\n`, Linux uses `\n`;
  a script with `\r\n` crashes inside a Linux container.

## ③ Secrets

```
 .env.example (committed)  ── copy ──►  .env (ignored)
 "which settings exist"                 "the real values"
```

Rule: code never contains secrets; it reads them from the environment.

## ④ Docker

```
 Dockerfile ──build──► IMAGE ──run──► CONTAINER ──saves to──► VOLUME
 "recipe"              "mold"         "the cake"              "the fridge"
```

- A container can be deleted and recreated at any time; the **volume** keeps the data.
- `docker-compose.yml` describes all services; `docker compose up -d` starts them.
- On Windows, Docker runs Linux containers inside **WSL 2** (a real Linux kernel).

Our database image = `postgis/postgis:17-3.5` + the `pgvector` package.
First-run SQL (`infra/postgres/init/`) enables three extensions:

| Extension | Superpower | FALCON use |
|---|---|---|
| postgis | geo distance | location correlation |
| vector | similarity search | duplicate / similar evidence |
| pg_trgm | fuzzy text | global search on IDs |

## Decisions made in this phase

| Decision | Why |
|---|---|
| Port **5433**, not 5432 | a local PostgreSQL already uses 5432 on this machine |
| Bind to **127.0.0.1** | the database is reachable only from this computer, not the network |
| **No MinIO** | its free edition was archived in 2026 and images were removed from Docker Hub. Dev uses local disk behind a `StorageService` interface; cloud storage later. |
| Healthcheck in compose | other services can wait until the DB is really ready |

## Recall questions

1. What's the difference between an image, a container and a volume?
2. If you run `docker compose down`, is your data lost? Why or why not?
3. Why is `.env` in `.gitignore` but `.env.example` is not?
4. Why did we bind the port to `127.0.0.1` instead of just `5433:5432`?
5. Why would a shell script with Windows line endings fail inside a container?
