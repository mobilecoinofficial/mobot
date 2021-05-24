#!/bin/bash

set -e
set -o pipefail

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

if [[ -z "${VALUES}" ]]; then
  echo "VALUES required"
  exit 1
fi

if [[ -z "${TAGS}" ]]; then
  echo "TAGS required"
  exit 1
fi

if [[ -z "${CHART_RELEASE_NAME}" ]]; then
  echo "CHART_RELEASE_NAME required"
  exit 1
fi

# Parse Tag - grab the first tag - Format org/repo:tag,org/repo:tag
TAG=$(echo -n "${TAGS}" | head -1 | awk -F ':' '{print $2}')
echo "-- Found TAG: ${TAG}"

# replace image tag in values content.
echo "-- Generate values.yaml content"
echo "${VALUES}" | sed -e "s/%TAG%/$TAG/g" > ./values.yaml

# Get kubeconfig generation url
echo "-- Rancher: Get kubeconfig for ${RANCHER_CLUSTER} ${RANCHER_URL}"
auth_header="Authorization: Bearer ${RANCHER_TOKEN}"
kubeconfig_url=$(curl -sSLf -H "${auth_header}" "${RANCHER_URL}/v3/clusters/?name=${RANCHER_CLUSTER}" | jq -r .data[0].actions.generateKubeconfig)

# Write kubeconfig to default location
mkdir -p ~/.kube
curl -sSLf -H "${auth_header}" -X POST "${kubeconfig_url}" | jq -r .config > ~/.kube/config

# Helm upgrade
echo "-- Helm: install/upgrade chart ${CHART_PATH}"
helm upgrade ${CHART_RELEASE_NAME} ${CHART_PATH} --namespace ${RANCHER_CLUSTER_NAMESPACE} --install --atomic -f ./values.yaml
