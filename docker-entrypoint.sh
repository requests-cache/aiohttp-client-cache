#!/bin/sh

set -e

. /venv/bin/activate

exec gunicorn -c gunicorn-cfg.py server:app
