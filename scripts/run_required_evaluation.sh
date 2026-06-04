#!/usr/bin/env bash
set -euo pipefail
python -m pubsub.evaluation --subscriptions 10000 --duration 180 --publisher-rate 25 --compare
