#!/usr/bin/env bash
set -euo pipefail

script_dir="$(cd "$(dirname "$0")" && pwd)"
readonly script_dir
repo_root="$(cd "${script_dir}/.." && pwd)"
readonly repo_root

cd "${repo_root}"

docker compose up -d iris
docker compose exec iris /docker-entrypoint-initdb.d/init.sh
