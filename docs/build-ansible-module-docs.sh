#!/bin/bash
set -e

CWD=`pwd`
MODULES_OUTPUT="$CWD/integrations/ansible/modules/source"

# Cleanup old repo
if [ -d "napalm_ansible_repo" ]; then
    rm -rf napalm_ansible_repo
fi

git clone https://github.com/napalm-automation/napalm-ansible.git napalm_ansible_repo
cd napalm_ansible_repo

git checkout develop

uv pip install .
uv run pytest -c /dev/null
cp module_docs/* $MODULES_OUTPUT/

cd $CWD

