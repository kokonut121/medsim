#!/usr/bin/env bash
set -euo pipefail

script_dir="$(cd "$(dirname "$0")" && pwd)"
readonly script_dir
repo_root="$(cd "${script_dir}/.." && pwd)"
readonly repo_root

cd "${repo_root}"

docker compose up -d iris
docker compose exec iris /docker-entrypoint-initdb.d/init.sh

grant_output="$(docker compose exec -T iris iris session "${IRIS_INSTANCE:-IRIS}" -U %SYS <<'EOF'
set serviceRole=$system.Util.GetEnviron("MEDSENT_SERVICE_ROLE")
if serviceRole="" set serviceRole="MedSentinel_Service"
kill props
set props("Resources")="MedSentinel_Data:RWU,MedSentinel_Wallet_Use:U,MedSentinel_Wallet_Edit:W,MedSentinel_FHIR_Use:U,MedSentinel_FHIR_Edit:W,"_$CHAR(37)_"Native_GlobalAccess:U"
set sc=##class(Security.Roles).Modify(serviceRole,.props)
if $SYSTEM.Status.IsError(sc) write !,"[MedSentinel] Unable to grant native global access to "_serviceRole,!
if $SYSTEM.Status.IsError(sc) do $SYSTEM.Status.DisplayError(sc)
if $SYSTEM.Status.IsError(sc) halt
write !,"[MedSentinel] Granted "_$CHAR(37)_"Native_GlobalAccess to "_serviceRole,!
halt
EOF
)"

printf '%s\n' "${grant_output}"

if [[ "${grant_output}" != *"[MedSentinel] Granted %Native_GlobalAccess"* ]]; then
  echo "MedSentinel IRIS native-global bootstrap failed" >&2
  exit 1
fi
