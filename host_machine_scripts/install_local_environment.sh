#!/usr/bin/env bash

function install_local_env() {
  PROJECT_VERSION=$(grep python_version ../Pipfile | awk '{ print $3 }')

  brew update
  brew install pyenv
  CFLAGS="-I$(brew --prefix openssl)/include -I$(brew --prefix bzip2)/include -I$(brew --prefix readline)/include -I$(xcrun --show-sdk-path)/usr/include" LDFLAGS="-L$(brew --prefix openssl)/lib -L$(
    brew -
    -prefix readline
  )/lib -L$(brew --prefix zlib)/lib -L$(brew --prefix bzip2)/lib" pyenv install 3.9.5
}

install_local_env