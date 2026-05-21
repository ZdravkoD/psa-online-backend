#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path
from types import SimpleNamespace
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
        "--input-file",
        type=Path,
        help="Path to a local Excel file. Uses the same ExcelWorker path as production.",
    )
    task_parser.add_argument(
        "--task-type",
        choices=["start_over", "resume"],
        default="start_over",
    )
    task_parser.add_argument(
        "--cleanup-after",
        action="store_true",
        help="Attempt to clear the created cart/order after the run.",
    )
    task_parser.add_argument("--capture-network", action="store_true", help="Enable Chrome performance logs and print Phoenix network activity after the task.")
    task_parser.add_argument("--network-output-file", type=Path, help="Optional JSON file path for captured network events.")

    stress_parser = subparsers.add_parser(
        "stress-test",
        help="Run a full order independently against each distributor and clean up after each run.",
    )
    stress_parser.add_argument("--pharmacy-id", required=True)
    stress_parser.add_argument(
        "--distributor",
        dest="distributors",
        action="append",
        choices=["phoenix", "sting"],
        required=True,
        help="Repeat to run the same order against multiple distributors independently.",
    )
    stress_parser.add_argument(
        "--input-file",
        type=Path,
        required=True,
        help="Path to a local Excel file for the full-order run.",
    )
    stress_parser.add_argument(
        "--iterations",
        type=int,
        default=1,
        help="How many times to rerun each distributor flow. Defaults to 1.",
    )
    stress_parser.add_argument(
        "--keep-orders",
        action="store_true",
        help="Do not clear the created cart/order after each iteration.",
    )
    stress_parser.add_argument(
        "--stop-on-failure",
        action="store_true",
        help="Stop after the first failed iteration.",
    )
    stress_parser.add_argument("--capture-network", action="store_true", help="Enable Chrome performance logs and print Phoenix network activity after each run.")
    stress_parser.add_argument("--network-output-file", type=Path, help="Optional JSON file path for captured Phoenix network events.")
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

    import files.excel_worker as excel_worker_module
    import task_handler.task_handler as task_handler_module
    from messaging.messaging import ScraperTaskItem
    from pharmacy_distributors.phoenix.phoenix_optimized import PhoenixPharmaOptimized
    from pharmacy_distributors.sting.sting import StingPharma

    return {
        "excel_worker_module": excel_worker_module,
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
    input_file = getattr(args, "input_file", None)

    if args.input_json is not None and input_file is not None:
        raise SystemExit("Pass either --input-json or --input-file, not both.")

    if args.input_json is not None:
        with args.input_json.open("r", encoding="utf-8") as handle:
            file_data = json.load(handle)
        file_name = args.input_json.name
        file_type = "json_content"
    elif input_file is not None:
        file_data = f"https://local.test/input-files/{input_file.name}"
        file_name = input_file.name
        file_type = "blob_storage_url"
    elif args.product:
        file_data = {
            "rows": [
                {
                    "product_name": args.product,
                    "quantity": args.quantity,
                }
            ]
        }
        file_name = "local-debug.json"
        file_type = "json_content"
    else:
        raise SystemExit("Pass one of --input-file, --input-json, or --product.")

    now = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
    return {
        "id": "000000000000000000000001",
        "account_id": "000000000000000000000002",
        "file_name": file_name,
        "file_data": file_data,
        "file_type": file_type,
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


def _cleanup_scraper_state(scraper: Any) -> str:
    if hasattr(scraper, "clear_order_items"):
        scraper.clear_order_items()
        return "cleared Phoenix order items"
    if hasattr(scraper, "clearCart"):
        scraper.clearCart()
        return "cleared Sting cart"
    raise ValueError(f"No cleanup hook is implemented for scraper '{getattr(scraper, 'name', type(scraper).__name__)}'")


def _verify_cleanup_state(scraper: Any) -> str:
    if hasattr(scraper, "verify_cleanup_state"):
        if scraper.verify_cleanup_state():
            return f"verified {getattr(scraper, 'get_name', lambda: type(scraper).__name__)()} cleanup state"
        raise ValueError(f"{getattr(scraper, 'get_name', lambda: type(scraper).__name__)()}: cleanup verification failed")
    raise ValueError(f"No cleanup verification hook is implemented for scraper '{getattr(scraper, 'name', type(scraper).__name__)}'")


def _patch_local_blob_clients(modules: dict[str, Any], local_azure_blob_client: type) -> None:
    modules["task_handler_module"].AzureBlobClient = local_azure_blob_client
    modules["excel_worker_module"].AzureBlobClient = local_azure_blob_client


def _patch_local_cosmos_client(modules: dict[str, Any], local_cosmos_client: type) -> None:
    modules["task_handler_module"].CosmosDbClient = local_cosmos_client


def _run_task(args: argparse.Namespace, modules: dict[str, Any]) -> int:
    _ensure_required_config(args.distributors)
    input_file = getattr(args, "input_file", None)
    input_file_bytes = input_file.read_bytes() if input_file is not None else None

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
        def download_blob_from_input_container(self, blob_name: str):
            if input_file is None or input_file_bytes is None:
                raise FileNotFoundError(f"No local input file is configured for blob '{blob_name}'")
            if blob_name != input_file.name:
                raise FileNotFoundError(f"Unexpected local blob request '{blob_name}', expected '{input_file.name}'")
            return input_file_bytes

        def upload_blob_to_log_container(self, *_args, **_kwargs):
            return None

        def upload_blob_to_output_container(self, *_args, **_kwargs):
            return None

    class LocalCosmosDbClient:
        _collections: dict[str, list[dict[str, Any]]] = {}
        _next_id = 1

        def read_items(
            self,
            collection_name: str,
            filter: dict[str, Any] | None = None,
            projection: dict[str, Any] | None = None,
            sort: dict[str, Any] | None = None,
            skip: int | None = 0,
            limit: int | None = 0,
        ) -> list[dict[str, Any]]:
            del sort
            items = [item.copy() for item in self._collections.get(collection_name, [])]

            if filter and "original_product_name" in filter:
                original_product_name_filter = filter["original_product_name"]
                if isinstance(original_product_name_filter, dict) and "$in" in original_product_name_filter:
                    allowed_names = set(original_product_name_filter["$in"])
                    items = [
                        item for item in items
                        if item.get("original_product_name") in allowed_names
                    ]

            if projection:
                projected_items = []
                for item in items:
                    projected_item = {
                        key: value for key, value in item.items()
                        if key == "id" or projection.get(key)
                    }
                    projected_items.append(projected_item)
                items = projected_items

            if skip:
                items = items[skip:]
            if limit:
                items = items[:limit]
            return items

        def create_item(self, collection_name: str, document: dict[str, Any]) -> str:
            item_id = str(self._next_id)
            type(self)._next_id += 1
            stored_document = document.copy()
            stored_document["id"] = item_id
            self._collections.setdefault(collection_name, []).append(stored_document)
            return item_id

        def update_item(self, collection_name: str, item_id: str, document: dict[str, Any]) -> int:
            for item in self._collections.get(collection_name, []):
                if item.get("id") == item_id:
                    item.update(document)
                    return 1
            return 0

    task_handler_module = modules["task_handler_module"]
    task_handler_module.TaskUpdatePublisher = LocalTaskUpdatePublisher
    _patch_local_blob_clients(modules, LocalAzureBlobClient)
    if not os.getenv("AZURE_COSMOS_DB_CONNECTION_STRING"):
        _patch_local_cosmos_client(modules, LocalCosmosDbClient)

    LocalTaskUpdatePublisher.events = []
    payload = _build_local_task_payload(args)
    task_item = modules["ScraperTaskItem"].from_dict(payload)
    handler = task_handler_module.TaskHandler(task_item)
    cleanup_errors: list[str] = []

    try:
        handler.handle_task()
        if args.capture_network:
            for scraper in handler.scrapers:
                if getattr(scraper, "get_name", lambda: "")() == "Phoenix":
                    _dump_network_activity(
                        scraper=scraper,
                        output_path=args.network_output_file,
                        scraper_name="Phoenix",
                    )
        if getattr(args, "cleanup_after", False):
            for scraper in handler.scrapers:
                try:
                    cleanup_result = _cleanup_scraper_state(scraper)
                    print(json.dumps({
                        "type": "cleanup",
                        "scraper": getattr(scraper, "get_name", lambda: type(scraper).__name__)(),
                        "result": cleanup_result,
                    }, ensure_ascii=False, indent=2))
                    verification_result = _verify_cleanup_state(scraper)
                    print(json.dumps({
                        "type": "cleanup_verification",
                        "scraper": getattr(scraper, "get_name", lambda: type(scraper).__name__)(),
                        "result": verification_result,
                    }, ensure_ascii=False, indent=2))
                except Exception as exc:
                    cleanup_errors.append(
                        f"{getattr(scraper, 'get_name', lambda: type(scraper).__name__)()}: {exc}"
                    )
    finally:
        for scraper in getattr(handler, "scrapers", []):
            try:
                scraper.finish()
            except Exception:
                pass

    if cleanup_errors:
        for cleanup_error in cleanup_errors:
            print(json.dumps({
                "type": "cleanup_error",
                "message": cleanup_error,
            }, ensure_ascii=False, indent=2))

    task_failed = any(event.get("type") == "error" for event in LocalTaskUpdatePublisher.events)
    return 1 if task_failed or cleanup_errors else 0


def _run_stress_test(args: argparse.Namespace, modules: dict[str, Any]) -> int:
    if args.iterations < 1:
        raise SystemExit("--iterations must be at least 1.")

    overall_exit_code = 0
    summaries: list[dict[str, Any]] = []

    for distributor in args.distributors:
        for iteration in range(1, args.iterations + 1):
            print(json.dumps({
                "type": "stress_test_start",
                "distributor": distributor,
                "iteration": iteration,
                "iterations": args.iterations,
                "input_file": str(args.input_file),
            }, ensure_ascii=False, indent=2))

            task_args = SimpleNamespace(
                command="task",
                pharmacy_id=args.pharmacy_id,
                distributors=[distributor],
                product=None,
                quantity=1,
                input_json=None,
                input_file=args.input_file,
                task_type="start_over",
                cleanup_after=not args.keep_orders,
                capture_network=args.capture_network,
                network_output_file=args.network_output_file,
            )
            exit_code = _run_task(task_args, modules)
            status = "passed" if exit_code == 0 else "failed"
            summaries.append({
                "distributor": distributor,
                "iteration": iteration,
                "status": status,
            })
            overall_exit_code = max(overall_exit_code, exit_code)

            print(json.dumps({
                "type": "stress_test_result",
                "distributor": distributor,
                "iteration": iteration,
                "status": status,
            }, ensure_ascii=False, indent=2))

            if exit_code != 0 and args.stop_on_failure:
                print(json.dumps({
                    "type": "stress_test_summary",
                    "results": summaries,
                }, ensure_ascii=False, indent=2))
                return overall_exit_code

    print(json.dumps({
        "type": "stress_test_summary",
        "results": summaries,
    }, ensure_ascii=False, indent=2))
    return overall_exit_code


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
    if args.command == "stress-test":
        return _run_stress_test(args, modules)

    raise SystemExit(f"Unknown command: {args.command}")


if __name__ == "__main__":
    raise SystemExit(main())
