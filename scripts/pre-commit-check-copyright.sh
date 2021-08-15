#!/usr/bin/env bash

echo "Running pre-commit hook"
COPYRIGHT_TEXT="# Copyright (c) 2021 MobileCoin. All rights reserved."

git diff --cached --name-status | while read flag file; do
    echo "File: ${file}"
    EXTENSION=$([[ "$file" = *.* ]] && echo ".${file##*.}" || echo '')
    echo "Extension: ${EXTENSION}"
    if [[ "${EXTENSION}" == ".py" && ! $(head -1 "${file}" | grep -q "${COPYRIGHT_TEXT}") ]]; then
        echo "ERROR: Missing MobileCoin Copyright in file: ${file}" >&2
        exit 1
    fi
done