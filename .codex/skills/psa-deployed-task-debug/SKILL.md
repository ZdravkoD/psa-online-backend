---
name: psa-deployed-task-debug
description: Use when debugging a deployed PSA task from a task-progress URL or task ID, especially Phoenix or Sting failures in Azure. Resolves the live task from Azure Functions, downloads screenshots and the input file, previews the workbook, and guides Azure Container Instance or Azure Functions log collection.
---

# PSA Deployed Task Debug

Use this skill when the issue happened in the deployed environment and the user gives a `task-progress` URL or a task ID.

## What to do first

Run the helper script from the repo root:

```bash
cd /Users/zdravkodonev/projects/psa-online-backend
scraper/.venv/bin/python .codex/skills/psa-deployed-task-debug/scripts/debug_task.py \
  "https://black-wave-0302cc703.5.azurestaticapps.net/task-progress/6a05f7474f1632d5fc097b8a"
```

The script:
- extracts the task ID
- tries the likely Functions API bases
- downloads the task JSON
- downloads screenshots
- downloads the input file through the Functions `input-file` endpoint when the raw blob URL is not public
- previews the first rows of the workbook when possible
- checks `az account show` and triggers `az login --scope https://management.core.windows.net//.default` when the Azure session is expired
- prints the exact Azure commands to run next

Artifacts are stored under `/private/tmp/psa-deployed-task-debug/<task-id>/`.

If the script reports that the Azure session is expired but the current run is non-interactive, rerun it in a normal terminal session so `az login` can complete.

## After the script finishes

1. Read the task summary and `detailed_error_message`.
2. Open any downloaded screenshots with `view_image`.
3. Inspect the input workbook preview to see whether the failure might be data-specific.
4. If the error is clearly browser-flow related, inspect the likely scraper files the script reports.
5. If deployed-only behavior is still unclear, collect Azure logs next.

## Azure log workflow

The helper script already checks Azure auth first. If you need to do it manually, start with:

```bash
az account show
```

If Azure says interactive authentication is needed, run:

```bash
az login --scope https://management.core.windows.net//.default
```

Then prefer container logs first, because Phoenix and Sting browser failures usually happen in the scraper container:

```bash
az container show --name scraper-container --resource-group psa -o json
az container logs --name scraper-container --resource-group psa
```

Use Azure Functions logs when the task never reached the scraper cleanly, the task document looks wrong, or file download/task creation paths look suspicious:

- staging slot:
```bash
az webapp log tail --name psa-online-functions --resource-group psa --slot staging
```

- production slot:
```bash
az webapp log tail --name psa-online-functions --resource-group psa
```

`az webapp log tail` is interactive. Run it in a normal terminal, stop it after you have the relevant lines, then summarize the findings.

## Repo-specific facts

- The task document comes from `GET /api/task/{taskId}` in [function_app.py](/Users/zdravkodonev/projects/psa-online-backend/azure-functions/function_app.py).
- Input files can be fetched from `GET /api/input-file/{filename}` in the same file.
- Scraper errors upload screenshots to the `output-files` blob container and log files to the `log-files` container.
- The task document stores `image_urls` but does not store the uploaded log blob URL, so Azure logs are often needed.
- For Phoenix login/bootstrap failures, check [phoenix.py](/Users/zdravkodonev/projects/psa-online-backend/scraper/scraper/pharmacy_distributors/phoenix/phoenix.py) and [browser_common.py](/Users/zdravkodonev/projects/psa-online-backend/scraper/scraper/pharmacy_distributors/common/browser_common.py).

## When to switch to local repro

If the deployed task shows a scraper flow failure and the input file is not the root cause, switch to the local scraper debug skill to reproduce the same flow against Phoenix or Sting with the same pharmacy/distributor.

Read [references/resource-map.md](./references/resource-map.md) only when you need the exact deployed resource names, endpoints, or code-path mapping.
