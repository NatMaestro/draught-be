#!/usr/bin/env bash
# Render build — run from `draught-be` (set as Root Directory on the service).
set -o errexit -o pipefail

pip install --upgrade pip
pip install -r requirements.txt
python manage.py collectstatic --no-input
python manage.py migrate --no-input
