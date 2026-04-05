#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[2]
SCRAPER_SRC = REPO_ROOT / "scraper" / "scraper"


def _load_distributor_config(path: Path) -> None:
    with path.open("r", encoding="utf-8") as handle:
        data = json.load(handle)

    if "phoenix" in data:
        os.environ["PHOENIX_CONFIG"] = json.dumps(data["phoenix"])
    if "sting" in data:
        os.environ["STING_CONFIG"] = json.dumps(data["sting"])


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Local scraper debug entrypoint without Azure Service Bus dependencies."
    )
    parser.add_argument(
        "--distributor-config-file",
        type=Path,
        help="Path to distributor-config.json. If omitted, PHOENIX_CONFIG/STING_CONFIG must already be set.",
    )

    subparsers = parser.add_subparsers(dest="command", required=True)

    login_parser = subparsers.add_parser("phoenix-login", help="Start Phoenix browser, login, and optionally open order flow.")
    login_parser.add_argument("--pharmacy-id", required=True)
    login_parser.add_argument("--skip-prepare", action="store_true", help="Stop after login.")
    login_parser.add_argument("--capture-network", action="store_true", help="Enable Chrome performance logs and print Phoenix network activity.")
    login_parser.add_argument("--network-output-file", type=Path, help="Optional JSON file path for captured network events.")

    sting_login_parser = subparsers.add_parser("sting-login", help="Start Sting browser, login, and optionally open order flow.")
    sting_login_parser.add_argument("--pharmacy-id", required=True)
    sting_login_parser.add_argument("--skip-prepare", action="store_true", help="Stop after login.")

    task_parser = subparsers.add_parser("task", help="Run TaskHandler locally with a synthetic task payload.")
    task_parser.add_argument("--pharmacy-id", required=True)
    task_parser.add_argument(
        "--distributor",
        dest="distributors",
        action="append",
        choices=["phoenix", "sting"],
        required=True,
        help="Repeat to include multiple distributors.",
    )
    task_parser.add_argument("--product", help="Single product name to debug.")
    task_parser.add_argument("--quantity", type=int, default=1, help="Quantity for --product. Defaults to 1.")
    task_parser.add_argument(
        "--input-json",
        type=Path,
        help="Path to JSON payload with shape {'rows': [{'product_name': ..., 'quantity': ...}]}",
    )
    task_parser.add_argument(
        "--task-type",
        choices=["start_over", "resume"],
        default="start_over",
    )
    task_parser.add_argument("--capture-network", action="store_true", help="Enable Chrome performance logs and print Phoenix network activity after the task.")
    task_parser.add_argument("--network-output-file", type=Path, help="Optional JSON file path for captured network events.")
    return parser


def _ensure_required_config(distributors: list[str]) -> None:
    missing = []
    if "phoenix" in distributors and not os.getenv("PHOENIX_CONFIG"):
        missing.append("PHOENIX_CONFIG")
    if "sting" in distributors and not os.getenv("STING_CONFIG"):
        missing.append("STING_CONFIG")

    if missing:
        raise SystemExit(
            "Missing distributor config: "
            + ", ".join(missing)
            + ". Export the env vars or pass --distributor-config-file."
        )


def _import_scraper_modules() -> dict[str, Any]:
    sys.path.insert(0, str(SCRAPER_SRC))

    from psa_logger.logger import setup_logging

    setup_logging()

    import task_handler.task_handler as task_handler_module
    from messaging.messaging import ScraperTaskItem
    from pharmacy_distributors.phoenix.phoenix_optimized import PhoenixPharmaOptimized
    from pharmacy_distributors.sting.sting import StingPharma

    return {
        "task_handler_module": task_handler_module,
        "ScraperTaskItem": ScraperTaskItem,
        "PhoenixPharmaOptimized": PhoenixPharmaOptimized,
        "StingPharma": StingPharma,
    }


def _run_phoenix_login(args: argparse.Namespace, modules: dict[str, Any]) -> int:
    _ensure_required_config(["phoenix"])
    scraper = modules["PhoenixPharmaOptimized"](args.pharmacy_id)
    try:
        scraper.login()
        if not args.skip_prepare:
            scraper.prepare_for_order()
        print(scraper.format_debug_context())
        if args.capture_network:
            _dump_network_activity(
                scraper=scraper,
                output_path=args.network_output_file,
                scraper_name="Phoenix",
            )
        return 0
    finally:
        try:
            scraper.finish()
        except Exception:
            pass


def _run_sting_login(args: argparse.Namespace, modules: dict[str, Any]) -> int:
    _ensure_required_config(["sting"])
    scraper = modules["StingPharma"](args.pharmacy_id)
    try:
        scraper.login()
        if not args.skip_prepare:
            scraper.prepare_for_order()
        print(scraper.format_debug_context())
        return 0
    finally:
        try:
            scraper.finish()
        except Exception:
            pass


def _build_local_task_payload(args: argparse.Namespace) -> dict[str, Any]:
    if args.input_json is not None:
        with args.input_json.open("r", encoding="utf-8") as handle:
            file_data = json.load(handle)
    elif args.product:
        file_data = {
            "rows": [
                {
                    "product_name": args.product,
                    "quantity": args.quantity,
                }
            ]
        }
    else:
        raise SystemExit("Pass either --input-json or --product.")

    now = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
    return {
        "id": "000000000000000000000001",
        "account_id": "000000000000000000000002",
        "file_name": args.input_json.name if args.input_json else "local-debug.json",
        "file_data": file_data,
        "file_type": "json_content",
        "pharmacy_id": args.pharmacy_id,
        "distributors": args.distributors,
        "task_type": args.task_type,
        "date_created": now,
        "date_updated": now,
        "status": {
            "status": "in progress",
            "message": "local debug",
            "progress": 0,
            "detailed_error_message": None,
        },
        "report": None,
        "image_urls": None,
    }


def _run_task(args: argparse.Namespace, modules: dict[str, Any]) -> int:
    _ensure_required_config(args.distributors)

    class LocalTaskUpdatePublisher:
        events: list[dict[str, Any]] = []

        def __init__(self):
            pass

        def publish_error(self, taskItem, message: str, detailed_error_message: str, progress: int, image_urls=None):
            event = {
                "type": "error",
                "message": message,
                "progress": progress,
                "detailed_error_message": detailed_error_message,
                "image_urls": image_urls,
                "task": taskItem.to_json(),
            }
            self.events.append(event)
            print(json.dumps(event, ensure_ascii=False, indent=2))

        def publish_success(self, taskItem, report: dict):
            event = {
                "type": "success",
                "message": "Задачата приключи успешно!",
                "report": report,
                "task": taskItem.to_json(),
            }
            self.events.append(event)
            print(json.dumps(event, ensure_ascii=False, indent=2))

        def publish_progress_update(self, taskItem, message: str, progress: int):
            event = {
                "type": "progress",
                "message": message,
                "progress": progress,
            }
            self.events.append(event)
            print(json.dumps(event, ensure_ascii=False, indent=2))

    class LocalAzureBlobClient:
        def upload_blob_to_log_container(self, *_args, **_kwargs):
            return None

        def upload_blob_to_output_container(self, *_args, **_kwargs):
            return None

    task_handler_module = modules["task_handler_module"]
    task_handler_module.TaskUpdatePublisher = LocalTaskUpdatePublisher
    task_handler_module.AzureBlobClient = LocalAzureBlobClient

    payload = _build_local_task_payload(args)
    task_item = modules["ScraperTaskItem"].from_dict(payload)
    handler = task_handler_module.TaskHandler(task_item)
    handler.handle_task()
    if args.capture_network:
        for scraper in handler.scrapers:
            if getattr(scraper, "get_name", lambda: "")() == "Phoenix":
                _dump_network_activity(
                    scraper=scraper,
                    output_path=args.network_output_file,
                    scraper_name="Phoenix",
                )
    return 0


def _decode_performance_log_entries(entries: list[dict[str, Any]], *, url_contains: str) -> list[dict[str, Any]]:
    events_by_request_id: dict[str, dict[str, Any]] = {}
    filtered_events: list[dict[str, Any]] = []

    for entry in entries:
        message = entry.get("message")
        if not message:
            continue
        try:
            payload = json.loads(message)["message"]
        except Exception:
            continue

        method = payload.get("method")
        params = payload.get("params", {})
        request_id = params.get("requestId")

        if method == "Network.requestWillBeSent":
            request = params.get("request", {})
            url = request.get("url", "")
            if url_contains not in url:
                continue
            event = {
                "requestId": request_id,
                "type": "request",
                "url": url,
                "httpMethod": request.get("method"),
                "postData": request.get("postData"),
                "resourceType": params.get("type"),
                "initiator": params.get("initiator"),
            }
            events_by_request_id[request_id] = event
            filtered_events.append(event)
        elif method == "Network.responseReceived":
            response = params.get("response", {})
            url = response.get("url", "")
            if url_contains not in url:
                continue
            request_event = events_by_request_id.get(request_id, {})
            event = {
                "requestId": request_id,
                "type": "response",
                "url": url,
                "status": response.get("status"),
                "mimeType": response.get("mimeType"),
                "resourceType": params.get("type"),
                "requestMethod": request_event.get("httpMethod"),
            }
            filtered_events.append(event)
        elif method == "Network.loadingFailed":
            if request_id not in events_by_request_id:
                continue
            event = {
                "requestId": request_id,
                "type": "loadingFailed",
                "url": events_by_request_id[request_id].get("url"),
                "errorText": params.get("errorText"),
                "canceled": params.get("canceled"),
            }
            filtered_events.append(event)

    return filtered_events


def _dump_network_activity(scraper: Any, output_path: Path | None, scraper_name: str) -> None:
    entries = scraper.get_performance_logs()
    network_events = _decode_performance_log_entries(entries, url_contains="phoenixpharma.bg")
    if output_path is not None:
        output_path.write_text(json.dumps(network_events, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"Wrote {len(network_events)} {scraper_name} network events to {output_path}")
        return

    print(json.dumps({
        "scraper": scraper_name,
        "network_events": network_events,
    }, ensure_ascii=False, indent=2))


def main() -> int:
    parser = _build_parser()
    args = parser.parse_args()

    if args.distributor_config_file:
        _load_distributor_config(args.distributor_config_file)
    if getattr(args, "capture_network", False):
        os.environ["CHROME_ENABLE_PERFORMANCE_LOGS"] = "1"

    modules = _import_scraper_modules()

    if args.command == "phoenix-login":
        return _run_phoenix_login(args, modules)
    if args.command == "sting-login":
        return _run_sting_login(args, modules)
    if args.command == "task":
        return _run_task(args, modules)

    raise SystemExit(f"Unknown command: {args.command}")


if __name__ == "__main__":
    raise SystemExit(main())
