# FALCON database image
# Start FROM the official PostGIS image (PostgreSQL 17 + PostGIS 3.5 = geo queries)
FROM postgis/postgis:17-3.5

# ...and ADD pgvector (AI similarity search). The base image already knows the
# PostgreSQL apt repository, so installing the extension is one package.
RUN apt-get update \
    && apt-get install -y --no-install-recommends postgresql-17-pgvector \
    && rm -rf /var/lib/apt/lists/*
