# FALCON database image: PostgreSQL 17 + pgvector (AI similarity) + PostGIS (geo queries)
#
# Start FROM the official pgvector image (PostgreSQL 17 on a current Debian release)...
FROM pgvector/pgvector:pg17

# ...and ADD PostGIS from PostgreSQL's own package repository, which the base image already
# knows. (We used to start from postgis/postgis:17-3.5; its Debian release reached end of
# life, the package server dropped it, and the image could no longer be built. CI caught it.)
RUN apt-get update \
    && apt-get install -y --no-install-recommends postgresql-17-postgis-3 \
    && rm -rf /var/lib/apt/lists/*
