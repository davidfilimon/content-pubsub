# python -m venv .venv
source .venv/bin/activate
# pip install -e .
# python -m pubsub.demo
python -m pubsub.evaluation --subscriptions 10000 --duration 180 --publisher-rate 25 --compare --no-sleep
