#!/usr/bin/env bash
set -euo pipefail

script_dir="$(cd "$(dirname "$0")" && pwd)"
readonly script_dir

IRIS_INSTANCE="${IRIS_INSTANCE:-IRIS}"
FHIR_CONFIG_PATH="${FHIR_CONFIG_PATH:-${script_dir}/fhir_config.json}"
BOOTSTRAP_CLASS_PATH="${BOOTSTRAP_CLASS_PATH:-${script_dir}/MedSentinelInstaller.cls}"
export BOOTSTRAP_CLASS_PATH

json_default() {
  local key="$1"
  local fallback="$2"
  if [[ ! -f "${FHIR_CONFIG_PATH}" ]]; then
    printf '%s' "${fallback}"
    return
  fi

  local line
  line="$(grep -E "\"${key}\"[[:space:]]*:" "${FHIR_CONFIG_PATH}" | head -n 1 || true)"
  if [[ -z "${line}" ]]; then
    printf '%s' "${fallback}"
    return
  fi

  local value
  value="$(printf '%s' "${line}" | sed -E 's/.*:[[:space:]]*"?([^",}]+)"?.*/\1/')"
  if [[ -z "${value}" ]]; then
    printf '%s' "${fallback}"
    return
  fi
  printf '%s' "${value}"
}

export MEDSENT_NAMESPACE="${MEDSENT_NAMESPACE:-${IRIS_NAMESPACE:-$(json_default namespace MEDSENT)}}"
export MEDSENT_APP_USER="${MEDSENT_APP_USER:-${IRIS_USER:-$(json_default appUser medsent_app)}}"
export MEDSENT_APP_PASSWORD="${MEDSENT_APP_PASSWORD:-${IRIS_PASSWORD:-changeme}}"
export MEDSENT_SERVER_NAME="${MEDSENT_SERVER_NAME:-$(json_default serverName MedSentinelFHIR)}"
export MEDSENT_FHIR_PATH="${MEDSENT_FHIR_PATH:-$(json_default endpointPath /fhir/r4)}"
export MEDSENT_FHIR_VERSION="${MEDSENT_FHIR_VERSION:-$(json_default fhirVersion R4)}"
export MEDSENT_FHIR_METADATA_PACKAGE="${MEDSENT_FHIR_METADATA_PACKAGE:-$(json_default metadataPackage hl7.fhir.r4.core@4.0.1)}"
export MEDSENT_FHIR_STRATEGY_CLASS="${MEDSENT_FHIR_STRATEGY_CLASS:-$(json_default strategyClass HS.FHIRServer.Storage.Json.InteractionsStrategy)}"
export MEDSENT_WALLET_COLLECTION="${MEDSENT_WALLET_COLLECTION:-$(json_default walletCollection MedSentinel)}"
export MEDSENT_SERVICE_ROLE="${MEDSENT_SERVICE_ROLE:-MedSentinel_Service}"

echo "Initializing InterSystems IRIS for MedSentinel"
echo "  instance: ${IRIS_INSTANCE}"
echo "  namespace: ${MEDSENT_NAMESPACE}"
echo "  fhir path: ${MEDSENT_FHIR_PATH}"
echo "  fhir version: ${MEDSENT_FHIR_VERSION}"
echo "  app user: ${MEDSENT_APP_USER}"
echo "  wallet collection: ${MEDSENT_WALLET_COLLECTION}"

if [[ ! -f "${BOOTSTRAP_CLASS_PATH}" ]]; then
  echo "Bootstrap class not found at ${BOOTSTRAP_CLASS_PATH}" >&2
  exit 1
fi

for attempt in $(seq 1 30); do
  if printf 'halt\n' | iris session "${IRIS_INSTANCE}" -U %SYS >/dev/null 2>&1; then
    break
  fi
  if [[ "${attempt}" -eq 30 ]]; then
    echo "IRIS did not become ready in time for bootstrap" >&2
    exit 1
  fi
  sleep 2
done

if ! iris session "${IRIS_INSTANCE}" -U %SYS <<'EOF'
set classPath=$system.Util.GetEnviron("BOOTSTRAP_CLASS_PATH")
if classPath="" write !,"[MedSentinel] BOOTSTRAP_CLASS_PATH is not set",! halt 1
set sc=$SYSTEM.OBJ.Load(classPath,"ck")
if $SYSTEM.Status.IsError(sc) write !,"[MedSentinel] Unable to load bootstrap class from ",classPath,! do $SYSTEM.Status.DisplayError(sc) halt 1
do ##class(MedSentinel.Installer).Main()
halt 0
EOF
then
  echo "MedSentinel IRIS bootstrap failed" >&2
  exit 1
fi

echo "MedSentinel IRIS bootstrap complete"
