#!/usr/bin/env sh
# FALCON backup: the database AND the original evidence files, taken together.
#   ./deploy/backup.sh                 → backups/falcon-YYYY-MM-DD_HHMM/
# Run it daily (cron: 0 2 * * * cd /opt/falcon && ./deploy/backup.sh) and copy backups/
# somewhere else. A backup on the same disk is not a backup.
set -eu

COMPOSE="docker compose -f docker-compose.prod.yml --env-file deploy/.env.production"
STAMP=$(date +%Y-%m-%d_%H%M)
OUT="backups/falcon-$STAMP"
mkdir -p "$OUT"

# 1. Database: a consistent snapshot even while FALCON is in use (custom format, compressed).
$COMPOSE exec -T db sh -c 'pg_dump -U "$POSTGRES_USER" -d "$POSTGRES_DB" -Fc' > "$OUT/database.dump"

# 2. Evidence originals, read-only from the volume.
docker run --rm -v falcon-prod_evidence:/data:ro -v "$(pwd)/$OUT:/backup" alpine \
  tar czf /backup/evidence.tar.gz -C /data .

# 3. Fingerprints, so a restore can be checked.
( cd "$OUT" && sha256sum database.dump evidence.tar.gz > SHA256SUMS )
echo "Backup written to $OUT"

# Restore (into an empty installation):
#   $COMPOSE exec -T db sh -c 'pg_restore -U "$POSTGRES_USER" -d "$POSTGRES_DB" --clean' < database.dump
#   docker run --rm -v falcon-prod_evidence:/data -v "$PWD:/backup" alpine tar xzf /backup/evidence.tar.gz -C /data
