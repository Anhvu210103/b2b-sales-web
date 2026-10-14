#!/usr/bin/env bash
# Run on your own computer with Docker and DATABASE_URL set securely.
set -euo pipefail
umask 077
: "${DATABASE_URL:?Set the native PostgreSQL connection URL locally; do not paste it into chat}"
backup_dir="${1:-./backups}"
mkdir -p "$backup_dir"
server_version_num="$(docker run --rm -e DATABASE_URL postgres:18-alpine sh -c 'exec psql "$DATABASE_URL" -tAc "SHOW server_version_num"')"
[[ "$server_version_num" =~ ^[0-9]+$ ]] || { echo 'Cannot identify PostgreSQL version' >&2; exit 1; }
postgres_major="$((server_version_num / 10000))"
postgres_client_image="postgres:${postgres_major}-alpine"
backup_file="$backup_dir/chatask-pg${postgres_major}-$(date -u +%Y%m%dT%H%M%SZ).dump"
backup_tmp="$(mktemp "$backup_dir/.backup-XXXXXX")"
trap 'rm -f "$backup_tmp"' EXIT
docker run --rm -e DATABASE_URL "$postgres_client_image" sh -c 'exec pg_dump "$DATABASE_URL" --format=custom --no-owner --no-acl' > "$backup_tmp"
test -s "$backup_tmp"
docker run --rm -i "$postgres_client_image" pg_restore --list < "$backup_tmp" >/dev/null
mv "$backup_tmp" "$backup_file"
echo "Backup saved: $backup_file"
