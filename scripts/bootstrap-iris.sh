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
if serviceRole="" set serviceRole="MedSim_Service"
kill props
set props("Resources")="MedSim_Data:RWU,MedSim_Wallet_Use:U,MedSim_Wallet_Edit:W,MedSim_FHIR_Use:U,MedSim_FHIR_Edit:W,"_$CHAR(37)_"Native_GlobalAccess:U"
set sc=##class(Security.Roles).Modify(serviceRole,.props)
if $SYSTEM.Status.IsError(sc) write !,"[MedSim] Unable to grant native global access to "_serviceRole,!
if $SYSTEM.Status.IsError(sc) do $SYSTEM.Status.DisplayError(sc)
if $SYSTEM.Status.IsError(sc) halt
write !,"[MedSim] Granted "_$CHAR(37)_"Native_GlobalAccess to "_serviceRole,!
halt
EOF
)"

printf '%s\n' "${grant_output}"

if [[ "${grant_output}" != *"[MedSim] Granted %Native_GlobalAccess"* ]]; then
  echo "MedSim IRIS native-global bootstrap failed" >&2
  exit 1
fi
