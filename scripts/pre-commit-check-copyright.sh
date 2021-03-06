#!/usr/bin/env bash

echo "Running pre-commit hook to check copyright on python files"
COPYRIGHT_TEXT="Copyright (c) 2021 MobileCoin. All rights reserved."
IGNORE="src/manage.py"

git diff --cached --name-status | while read flag file; do
    if [[ ! -f "${file}" ]]; then
      continue;
    fi
    if [[ "${flag}" == 'D' ]]; then
      continue;
    fi
    if [[ "${file}" == "${IGNORE}" ]]; then
      continue
    fi
    
    EXTENSION=$([[ "$file" = *.* ]] && echo ".${file##*.}" || echo '')
    if [[ "${file}" == 'src/manage.py' ]]; then
	continue;
    fi
    if [[ "${EXTENSION}" == ".py" ]]; then
      if [[ $(grep "${COPYRIGHT_TEXT}" "${file}") == '' ]]; then
        echo "ERROR: Missing MobileCoin Copyright in file: ${file}" >&2
        exit 1
      fi
    fi
done
