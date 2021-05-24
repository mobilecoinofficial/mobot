#!/bin/bash

set -e

if [[ -z "${RANCHER_TOKEN}" ]]; then
  echo "RANCHER_TOKEN required"
  exit 1
fi

if [[ -z "${RANCHER_URL}" ]]; then
  echo "RANCHER_URL required"
  exit 1
fi

if [[ -z "${RANCHER_CLUSTER}" ]]; then
  echo "RANCHER_CLUSTER required"
  exit 1
fi

if [[ -z "${RANCHER_CLUSTER_NAMESPACE}" ]]; then
  echo "RANCHER_CLUSTER_NAMESPACE required"
  exit 1
fi

if [[ -z "${CHART_PATH}" ]]; then
  echo "CHART_PATH required"
  exit 1
fi

if [[ -z "${VALUES_PATH}" ]]; then
  echo "VALUES_PATH required"
  exit 1
fi

if [[ -z "${CHART_RELEASE_NAME}" ]]; then
  echo "CHART_RELEASE_NAME required"
  exit 1
fi

auth_header="Authorization: Bearer ${RANCHER_TOKEN}"

echo "-- Rancher: Get kubeconfig for ${RANCHER_CLUSTER} ${RANCHER_URL}"

# Get kubeconfig generation url
kubeconfig_url=$(curl -sSL -H "${auth_header}" "${RANCHER_URL}/v3/clusters/?name=${RANCHER_CLUSTER}" | jq -r .data[0].actions.generateKubeconfig)

# Write kubeconfig to default location
mkdir -p ~/.kube
curl -sSL -H "${auth_header}" -X POST "${kubeconfig_url}" | jq -r .config > ~/.kube/config

echo "-- Helm: install/upgrade chart ${CHART_PATH}

helm upgrade ${CHART_RELEASE_NAME} ${CHART_PATH} --namespace ${RANCHER_CLUSTER_NAMESPACE} --install --atomic -f ./values.yaml
