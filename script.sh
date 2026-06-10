#!/usr/bin/env zsh

echo
echo "================ DEMO SISTEM PUB/SUB ================"
python -m pubsub.demo

echo
echo "================ EVALUARE 10.000 SUBSCRIPTII ================"
python -m pubsub.evaluation \
  --subscriptions 10000 \
  --duration 180 \
  --publisher-rate 25 \
  --compare \
  --no-sleep
