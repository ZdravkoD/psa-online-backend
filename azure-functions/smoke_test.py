#!/usr/bin/env python3
"""
Read-only smoke tests for the deployed Azure Functions app.

The checks in this script only call GET endpoints and avoid any operation that
creates, updates, or deletes application state.
"""

from __future__ import annotations

import argparse
import json
import sys
import urllib.error
import urllib.parse
import urllib.request
from typing import Any


DEFAULT_TIMEOUT_SECONDS = 15


def normalize_base_url(base_url: str) -> str:
    return base_url.rstrip("/")


def build_url(base_url: str, path: str, query: dict[str, str] | None = None) -> str:
    url = f"{normalize_base_url(base_url)}/{path.lstrip('/')}"
    if query:
        url = f"{url}?{urllib.parse.urlencode(query)}"
    return url


def request_json(
    *,
    base_url: str,
    path: str,
    expected_status: int,
    timeout: int,
    query: dict[str, str] | None = None,
) -> Any:
    url = build_url(base_url, path, query=query)
    request = urllib.request.Request(url, method="GET")

    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            body = response.read().decode("utf-8")
            status_code = response.getcode()
    except urllib.error.HTTPError as err:
        body = err.read().decode("utf-8", errors="replace")
        status_code = err.code
    except urllib.error.URLError as err:
        raise AssertionError(f"{url} request failed: {err.reason}") from err

    if status_code != expected_status:
        raise AssertionError(
            f"{url} returned {status_code}, expected {expected_status}. Body: {body[:500]}"
        )

    if expected_status >= 400:
        return body

    try:
        return json.loads(body)
    except json.JSONDecodeError as err:
        raise AssertionError(f"{url} did not return valid JSON. Body: {body[:500]}") from err


def assert_list_payload(name: str, payload: Any) -> None:
    if not isinstance(payload, list):
        raise AssertionError(f"{name} returned {type(payload).__name__}, expected list")


def assert_products_payload(payload: Any) -> None:
    if not isinstance(payload, dict):
        raise AssertionError(f"products returned {type(payload).__name__}, expected object")
    if "items" not in payload:
        raise AssertionError("products response is missing 'items'")
    if not isinstance(payload["items"], list):
        raise AssertionError("products.items is not a list")


def run_smoke_tests(base_url: str, timeout: int) -> None:
    checks = [
        ("GET pharmacies", "pharmacies", 200, None, assert_list_payload),
        ("GET distributors", "distributors", 200, None, assert_list_payload),
        ("GET products", "products", 200, {"limit": "1"}, assert_products_payload),
        ("GET task invalid id", "task/not-a-valid-object-id", 400, None, None),
        ("GET product invalid id", "product/not-a-valid-object-id", 400, None, None),
    ]

    for name, path, expected_status, query, validator in checks:
        payload = request_json(
            base_url=base_url,
            path=path,
            expected_status=expected_status,
            timeout=timeout,
            query=query,
        )
        if validator is assert_list_payload:
            validator(name, payload)
        elif validator is not None:
            validator(payload)
        print(f"PASS {name}")


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run read-only Azure Functions smoke tests.")
    parser.add_argument(
        "--base-url",
        required=True,
        help="Function app base URL, for example https://psa-online-functions.azurewebsites.net/api",
    )
    parser.add_argument(
        "--timeout",
        type=int,
        default=DEFAULT_TIMEOUT_SECONDS,
        help=f"Request timeout in seconds. Default: {DEFAULT_TIMEOUT_SECONDS}",
    )
    return parser.parse_args(argv)


def main(argv: list[str]) -> int:
    args = parse_args(argv)
    try:
        run_smoke_tests(base_url=args.base_url, timeout=args.timeout)
    except AssertionError as err:
        print(f"FAIL {err}", file=sys.stderr)
        return 1

    print("Smoke tests passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
