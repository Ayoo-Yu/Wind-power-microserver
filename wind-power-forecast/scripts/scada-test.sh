#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPOSITORY_ROOT="$(cd "${SCRIPT_DIR}/../.." && pwd)"
COMPOSE_FILE="${REPOSITORY_ROOT}/compose.scada-test.yaml"
BASE_IMAGE_ARCHIVE="${REPOSITORY_ROOT}/wind-power-forecast/04_scada_simulator.tar"
ACTION="${1:-status}"
SCENARIO="${2:-normal}"

compose() {
  docker compose -p wind-power-scada-test -f "${COMPOSE_FILE}" "$@"
}

ensure_base_image() {
  if docker image inspect wind-power-scada-simulator:v1 >/dev/null 2>&1; then
    return
  fi
  if [[ ! -f "${BASE_IMAGE_ARCHIVE}" ]]; then
    echo "缺少基础镜像和离线镜像包: ${BASE_IMAGE_ARCHIVE}" >&2
    exit 1
  fi
  docker load -i "${BASE_IMAGE_ARCHIVE}"
}

start_core() {
  ensure_base_image
  mkdir -p "${REPOSITORY_ROOT}/simulation/scada-test/artifacts"
  compose up -d --build scada-simulator fault-proxy
  echo "C104 测试入口: 127.0.0.1:${SCADA_TEST_C104_PORT:-12404}"
  echo "仿真器控制接口: http://127.0.0.1:${SCADA_TEST_SIMULATOR_CONTROL_PORT:-18082}"
  echo "故障代理控制接口: http://127.0.0.1:${SCADA_TEST_PROXY_CONTROL_PORT:-18081}"
}

case "${ACTION}" in
  up)
    start_core
    ;;
  up-infra)
    start_core
    compose --profile infra up -d --wait --wait-timeout 120 test-kingbase test-redis
    ;;
  down)
    compose --profile acceptance --profile infra down --remove-orphans
    ;;
  status)
    compose --profile acceptance --profile infra ps
    ;;
  test)
    start_core
    compose --profile acceptance up -d mock-ingress worker-harness
    set +e
    compose --profile acceptance run --rm acceptance-runner
    test_exit=$?
    set -e
    compose --profile acceptance stop worker-harness mock-ingress >/dev/null
    compose --profile acceptance rm -f worker-harness mock-ingress >/dev/null
    exit "${test_exit}"
    ;;
  scenario)
    curl --fail --silent --show-error \
      -H 'Content-Type: application/json' \
      -d "{\"name\":\"${SCENARIO}\"}" \
      "http://127.0.0.1:${SCADA_TEST_SIMULATOR_CONTROL_PORT:-18082}/scenario"
    echo
    ;;
  reset)
    curl --fail --silent --show-error -H 'Content-Type: application/json' -d '{}' \
      "http://127.0.0.1:${SCADA_TEST_PROXY_CONTROL_PORT:-18081}/reset" >/dev/null
    curl --fail --silent --show-error -H 'Content-Type: application/json' -d '{"name":"normal"}' \
      "http://127.0.0.1:${SCADA_TEST_SIMULATOR_CONTROL_PORT:-18082}/scenario" >/dev/null
    echo "已恢复正常场景并清除网络故障。"
    ;;
  logs)
    compose logs --follow --tail 200 scada-simulator fault-proxy
    ;;
  *)
    echo "用法: $0 {up|up-infra|down|status|test|scenario|reset|logs} [scenario]" >&2
    exit 2
    ;;
esac
