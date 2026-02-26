#!/bin/bash
cd /home/kavia/workspace/code-generation/nhai-tender-automation-platform-326951/nhai_aiqps_backend
source venv/bin/activate
flake8 .
LINT_EXIT_CODE=$?
if [ $LINT_EXIT_CODE -ne 0 ]; then
  exit 1
fi

