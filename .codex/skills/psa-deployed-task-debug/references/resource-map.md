# Resource Map

## Public task inspection

- Frontend task page: `https://<static-app-host>/task-progress/<task-id>`
- Likely task API candidates:
  - `https://<static-app-host>/api/task/<task-id>`
  - `https://psa-online-functions-staging.azurewebsites.net/api/task/<task-id>`
  - `https://psa-online-functions.azurewebsites.net/api/task/<task-id>`

The helper script tries those in order and uses the first `200` response.

## Azure resources

- Resource group: `psa`
- Azure Functions app: `psa-online-functions`
- Azure Functions staging slot: `staging`
- Scraper container group/container: `scraper-container`
- Blob containers:
  - `input-files`
  - `output-files`
  - `log-files`

## Relevant APIs

- `GET /api/task/{taskId}`
  - returns task document with `status`, `detailed_error_message`, `image_urls`, `file_data`, `distributors`, `pharmacy_id`
- `GET /api/input-file/{filename}`
  - returns the original uploaded input file bytes

## Code-path mapping

- Task creation and input-file download:
  - [azure-functions/function_app.py](/Users/zdravkodonev/projects/psa-online-backend/azure-functions/function_app.py)
- Task orchestration and error upload:
  - [scraper/scraper/task_handler/task_handler.py](/Users/zdravkodonev/projects/psa-online-backend/scraper/scraper/task_handler/task_handler.py)
- Task update publishing:
  - [scraper/scraper/task_handler/task_update_publisher.py](/Users/zdravkodonev/projects/psa-online-backend/scraper/scraper/task_handler/task_update_publisher.py)
- Blob helper:
  - [scraper/scraper/files/azure_blob_client.py](/Users/zdravkodonev/projects/psa-online-backend/scraper/scraper/files/azure_blob_client.py)
- Phoenix login/bootstrap:
  - [scraper/scraper/pharmacy_distributors/phoenix/phoenix.py](/Users/zdravkodonev/projects/psa-online-backend/scraper/scraper/pharmacy_distributors/phoenix/phoenix.py)
- Shared browser state/debug context:
  - [scraper/scraper/pharmacy_distributors/common/browser_common.py](/Users/zdravkodonev/projects/psa-online-backend/scraper/scraper/pharmacy_distributors/common/browser_common.py)

## Important caveats

- The raw `file_data` blob URL may not be public. If it fails, use `GET /api/input-file/{blob_name}`.
- The task document stores screenshot URLs, but not the uploaded worker log blob URL.
- Current CI workflows target the same `scraper-container` resource name in the `psa` resource group, so correlate container logs with the task timestamp before drawing conclusions.
