#!/usr/bin/env bash

REPO_BASE=$(git rev-parse --show-toplevel)
PRE_COMMIT="${REPO_BASE}/.git/hooks/pre-commit"
if [[ ! -f "${PRE_COMMIT}" ]]; then
  echo "Installing copyright check hook..."
  chmod a+x "${REPO_BASE}/scripts/pre-commit-check-copyright.sh"
  ln -s "${REPO_BASE}/scripts/pre-commit-check-copyright.sh" "${PRE_COMMIT}"
  echo "Hook installed!"
else
  echo "Copyright hook already installed!"
fi