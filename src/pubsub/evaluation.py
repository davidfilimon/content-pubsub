from __future__ import annotations

import argparse
import json
import random
import statistics
import time
from pathlib import Path
from typing import Dict, List

from .overlay import BrokerOverlay
from .protobuf_codec import serialize_publication
from .publisher import PublisherNode
from .subscriber import SubscriberNode
from .theme_adapter import generate_theme_subscriptions


def percentile(values: List[float], p: float) -> float:
    if not values:
        return 0.0
    ordered = sorted(values)
    index = int(round((len(ordered) - 1) * p))
    return ordered[index]


def build_overlay(
    subscriptions: int, equality_ratio: float, seed: int
) -> BrokerOverlay:
    random.seed(seed)
    overlay = BrokerOverlay(["broker-1", "broker-2", "broker-3"])
    subscribers = [SubscriberNode(f"subscriber-{i}") for i in range(1, 4)]
    for subscriber in subscribers:
        overlay.add_subscriber(subscriber)

    generated_subscriptions = generate_theme_subscriptions(
        count=subscriptions,
        subscriber_ids=[subscriber.subscriber_id for subscriber in subscribers],
        equality_ratio=equality_ratio,
        num_threads=4,
    )

    for subscription in generated_subscriptions:
        entry_broker = random.choice(overlay.broker_ids)
        overlay.register_subscription(entry_broker, subscription)

    return overlay


def run_single_evaluation(
    subscriptions: int,
    duration: float,
    publisher_rate: float,
    equality_ratio: float,
    seed: int,
    sleep_realtime: bool,
    failure_demo: bool,
) -> Dict[str, object]:
    overlay = build_overlay(subscriptions, equality_ratio, seed)
    publishers = [PublisherNode("publisher-a"), PublisherNode("publisher-b")]
    total_publications_target = max(1, int(duration * publisher_rate))

    start = time.perf_counter()
    successful_publications = 0
    total_notifications = 0
    replica_notifications = 0
    published = 0
    failure_triggered = False
    recovery_triggered = False
    generated_publication_lines = []

    for idx in range(total_publications_target):
        now_elapsed = time.perf_counter() - start

        if (
            failure_demo
            and not failure_triggered
            and idx >= total_publications_target // 3
        ):
            overlay.fail_broker("broker-2")
            failure_triggered = True
        if (
            failure_demo
            and not recovery_triggered
            and idx >= (2 * total_publications_target) // 3
        ):
            overlay.recover_broker("broker-2")
            recovery_triggered = True

        publisher = random.choice(publishers)
        entry = random.choice(overlay.broker_ids)

        publication = publisher.generate_publication()
        generated_publication_lines.append(
            f"{idx + 1};source={publication.source};entry={entry};"
            f"{publication.as_theme_text()}\n"
        )

        payload = serialize_publication(publication)
        result = overlay.publish_binary(entry, payload)
        published += 1
        total_notifications += result.delivered_notifications
        replica_notifications += result.matched_on_replicas
        if result.delivered_notifications > 0:
            successful_publications += 1

        if sleep_realtime and publisher_rate > 0:
            expected_elapsed = (idx + 1) / publisher_rate
            remaining = expected_elapsed - (time.perf_counter() - start)
            if remaining > 0:
                time.sleep(remaining)

    elapsed = time.perf_counter() - start

    pub_file = (
        Path("results") / f"generated_publications_eq_{int(equality_ratio * 100)}.txt"
    )
    pub_file.parent.mkdir(parents=True, exist_ok=True)
    pub_file.write_text("".join(generated_publication_lines), encoding="utf-8")

    deliveries = list(overlay.all_deliveries())
    latencies = [delivery.latency_ms for delivery in deliveries]
    mean_latency = statistics.fmean(latencies) if latencies else 0.0
    median_latency = statistics.median(latencies) if latencies else 0.0

    matching_rate = 0.0
    if published > 0 and subscriptions > 0:
        matching_rate = total_notifications / (published * subscriptions)

    return {
        "subscriptions": subscriptions,
        "duration_configured_seconds": duration,
        "elapsed_real_seconds": elapsed,
        "publisher_rate_per_second": publisher_rate,
        "equality_ratio_on_company_field": equality_ratio,
        "published_publications": published,
        "successful_publications": successful_publications,
        "total_delivered_notifications": total_notifications,
        "mean_delivery_latency_ms": mean_latency,
        "median_delivery_latency_ms": median_latency,
        "p95_delivery_latency_ms": percentile(latencies, 0.95),
        "matching_rate": matching_rate,
        "matching_rate_percent": matching_rate * 100.0,
        "broker_loads": overlay.broker_loads(),
        "deliveries_by_subscriber": overlay.subscriber_delivery_counts(),
        "failure_demo": failure_demo,
        "failure_triggered": failure_triggered,
        "recovery_triggered": recovery_triggered,
        "replica_notifications": replica_notifications,
    }


def render_report(results: List[Dict[str, object]]) -> str:
    lines: List[str] = []
    lines.append("# Raport de evaluare - sistem publish/subscribe content-based")
    lines.append("")
    lines.append("## Configuratie")
    lines.append("")
    lines.append(
        "Sistemul evaluat foloseste 2 publisheri, 3 brokeri in overlay de tip ring si 3 subscriberi. Subscriptiile sunt distribuite printr-un mecanism Balanced Rendezvous Routing: cheia de rutare este derivata din continutul subscriptiei, iar alegerea brokerului tine cont de balansarea subscriptiilor aceluiasi subscriber si de incarcarea globala a brokerilor."
    )
    lines.append("")
    lines.append(
        "Publicatiile sunt serializate binar in format Protocol Buffers wire format pentru legatura publisher -> broker. Dupa intrarea in overlay, publicatia este propagata prin brokeri, iar fiecare broker face matching doar pe subscriptiile locale/replicate."
    )
    lines.append("")
    lines.append("## Rezultate")
    lines.append("")
    lines.append(
        "| Egalitate pe campul `company` | Publicatii emise | Publicatii livrate cu succes | Notificari livrate | Latenta medie [ms] | Latenta p95 [ms] | Rata matching |"
    )
    lines.append("|---:|---:|---:|---:|---:|---:|---:|")
    for result in results:
        lines.append(
            "| "
            f"{float(result['equality_ratio_on_company_field']) * 100:.0f}% | "
            f"{int(result['published_publications'])} | "
            f"{int(result['successful_publications'])} | "
            f"{int(result['total_delivered_notifications'])} | "
            f"{float(result['mean_delivery_latency_ms']):.4f} | "
            f"{float(result['p95_delivery_latency_ms']):.4f} | "
            f"{float(result['matching_rate_percent']):.4f}% |"
        )

    lines.append("")
    lines.append("## Interpretare")
    lines.append("")
    lines.append(
        "Cazul cu 100% operator de egalitate pe campul `company` este mai selectiv: o publicatie se potriveste doar cu subscriptiile care cer exact aceeasi valoare. In cazul cu aproximativ 25% egalitate, restul subscriptiilor folosesc `!=`, ceea ce este mai putin selectiv si mareste rata de matching. Latenta ramane mica deoarece filtrarea este impartita intre brokeri, iar fiecare broker verifica numai subscriptiile proprii, nu o baza centralizata unica."
    )
    lines.append("")
    lines.append("## Toleranta la caderi")
    lines.append("")
    lines.append(
        "Fiecare subscriptie este stocata pe un broker primar si replicata pe urmatorul broker viu din ring. Daca un broker cade, publicatiile evita nodul indisponibil, iar brokerii vecini pot folosi copiile replicate pentru a livra notificari. Subscriberii au deduplicare pe perechea `(publication_id, subscription_id)`, deci aceeasi notificare nu este livrata de doua ori."
    )
    lines.append("")
    lines.append("## Limitari")
    lines.append("")
    lines.append(
        "Implementarea este o simulare intr-un singur proces pentru a putea fi rulata usor la prezentare. Arhitectura este separata pe noduri logice, deci poate fi extinsa ulterior la procese reale/TCP/UDP fara schimbarea modelului de rutare si matching."
    )
    lines.append("")
    return "\n".join(lines)


def save_outputs(results: List[Dict[str, object]], output_dir: Path) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)
    timestamp = time.strftime("%Y%m%d_%H%M%S")
    json_path = output_dir / f"evaluation_{timestamp}.json"
    report_path = output_dir / f"evaluation_report_{timestamp}.md"

    json_path.write_text(
        json.dumps(results, indent=2, ensure_ascii=False), encoding="utf-8"
    )
    report_path.write_text(render_report(results), encoding="utf-8")

    print(f"Saved JSON results: {json_path}")
    print(f"Saved Markdown report: {report_path}")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Evaluate content-based pub/sub overlay."
    )
    parser.add_argument("--subscriptions", type=int, default=10_000)
    parser.add_argument(
        "--duration",
        type=float,
        default=180.0,
        help="Feed interval in seconds. Use 180 for the required 3 minutes.",
    )
    parser.add_argument(
        "--publisher-rate", type=float, default=25.0, help="Publications per second."
    )
    parser.add_argument(
        "--equality-ratio",
        type=float,
        default=1.0,
        help="Run one scenario with this equality ratio.",
    )
    parser.add_argument(
        "--compare",
        action="store_true",
        help="Run both 100%% and 25%% equality scenarios.",
    )
    parser.add_argument("--seed", type=int, default=2026)
    parser.add_argument(
        "--no-sleep",
        action="store_true",
        help="Accelerated mode: process the configured feed without real-time waiting.",
    )
    parser.add_argument(
        "--failure-demo",
        action="store_true",
        help="Stop broker-2 during the run and recover it later.",
    )
    parser.add_argument("--output-dir", type=Path, default=Path("results"))
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    ratios = [1.0, 0.25] if args.compare else [args.equality_ratio]
    results: List[Dict[str, object]] = []

    for offset, ratio in enumerate(ratios):
        print(
            f"Running evaluation: subscriptions={args.subscriptions}, duration={args.duration}s, rate={args.publisher_rate}/s, equality={ratio:.2f}"
        )
        result = run_single_evaluation(
            subscriptions=args.subscriptions,
            duration=args.duration,
            publisher_rate=args.publisher_rate,
            equality_ratio=ratio,
            seed=args.seed + offset,
            sleep_realtime=not args.no_sleep,
            failure_demo=args.failure_demo,
        )
        results.append(result)
        print(json.dumps(result, indent=2, ensure_ascii=False))

    save_outputs(results, args.output_dir)


if __name__ == "__main__":
    main()
