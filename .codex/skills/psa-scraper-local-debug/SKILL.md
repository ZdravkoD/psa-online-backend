---
name: psa-scraper-local-debug
description: Use when debugging the Selenium scraper worker in this repository, especially Phoenix or Sting browser startup/login failures. Covers the fastest local entrypoints, required config, and the helper script for running Phoenix login or a full TaskHandler flow locally without Azure Service Bus.
---

# PSA Scraper Local Debug

Use this skill when the task is to reproduce or debug the scraper locally.

## What to use

Prefer the helper script:

```bash
cd /Users/zdravkodonev/projects/psa-online-backend
scraper/.venv/bin/python scraper/scripts/run_local_debug.py --help
```

It supports:
- `phoenix-login`: narrow browser/login bootstrap debug
- `sting-login`: same for Sting
- `task`: full local `TaskHandler` run with a synthetic task payload and no Azure Service Bus dependency

## Required config

The scraper does not have checked-in local config files. It expects distributor credentials from either:
- env vars `PHOENIX_CONFIG` and/or `STING_CONFIG`
- `--distributor-config-file <path>` pointing to a local JSON file shaped like `distributor-config.json`

The helper script loads that file and exports the expected env vars before importing scraper modules.

Selenium note:
- ChromeDriver binds a localhost port during startup.
- Inside the Codex sandbox this fails with `PermissionError: [Errno 1] Operation not permitted` from Selenium's `free_port()`.
- So real browser repros must be run in a normal terminal session, or via an escalated command, not inside the restricted sandbox.

Minimal config shape:

```json
{
  "phoenix": [
    { "id": "tolstoy", "username": "...", "password": "..." }
  ],
  "sting": [
    { "id": "tolstoy", "username": "...", "password": "..." }
  ]
}
```

## Fastest workflows

### 1. Reproduce Phoenix browser startup failure

Use this first when Phoenix dies before meaningful actions appear in the debug context.

```bash
cd /Users/zdravkodonev/projects/psa-online-backend
scraper/.venv/bin/python scraper/scripts/run_local_debug.py \
  --distributor-config-file /absolute/path/to/distributor-config.json \
  phoenix-login \
  --pharmacy-id tolstoy \
  --skip-prepare
```

What this does:
- starts only the Phoenix scraper
- runs `login()`
- skips product/order flow if `--skip-prepare` is set
- prints `format_debug_context()` to stdout

If the failure still shows `Current action: browser initialized` with `data:,`, the problem is below the Phoenix DOM layer and is likely browser startup or first navigation.

### 2. Reproduce a full local task

Use this when the bug might be in `TaskHandler`, product lookup, or cart logic.

Single product:

```bash
cd /Users/zdravkodonev/projects/psa-online-backend
scraper/.venv/bin/python scraper/scripts/run_local_debug.py \
  --distributor-config-file /absolute/path/to/distributor-config.json \
  task \
  --pharmacy-id tolstoy \
  --distributor phoenix \
  --product "нурофен 200 мг" \
  --quantity 1
```

JSON rows file:

```bash
cd /Users/zdravkodonev/projects/psa-online-backend
scraper/.venv/bin/python scraper/scripts/run_local_debug.py \
  --distributor-config-file /absolute/path/to/distributor-config.json \
  task \
  --pharmacy-id tolstoy \
  --distributor phoenix \
  --input-json /absolute/path/to/local-task.json
```

Expected JSON input:

```json
{
  "rows": [
    { "product_name": "нурофен 200 мг", "quantity": 1 }
  ]
}
```

This path monkeypatches:
- `TaskUpdatePublisher` to print progress/success/error locally
- `AzureBlobClient` to no-op, so local failures do not depend on Azure blob upload

## Important repo facts

- The normal worker entrypoint is [main.py](/Users/zdravkodonev/projects/psa-online-backend/scraper/scraper/main.py), but it depends on Azure Service Bus and is not the fastest way to debug.
- The `scraper/Makefile` `start` target runs the real worker loop, not a focused local repro.
- Phoenix and Sting share the same browser bootstrap in [browser_common.py](/Users/zdravkodonev/projects/psa-online-backend/scraper/scraper/pharmacy_distributors/common/browser_common.py). If Phoenix fails before navigation, compare with `sting-login` to decide whether the issue is flow-specific or environment-level.

## Useful next checks

If `phoenix-login` still lands on `data:,`:
- inspect the current Chrome flags in [utils.py](/Users/zdravkodonev/projects/psa-online-backend/scraper/scraper/pharmacy_distributors/common/utils.py)
- compare `phoenix-login` vs `sting-login`
- if both fail, treat it as browser/runtime regression
- if only Phoenix fails, focus on `dummy_page` -> cookie bootstrap -> login page in [phoenix.py](/Users/zdravkodonev/projects/psa-online-backend/scraper/scraper/pharmacy_distributors/phoenix/phoenix.py)
