# Troubleshooting

When you run:

```bash
make start
```

and you get a similar error:

```
❯ make start                                                                                                                                                                                         ─╯
Found Python version 3.8.19 (python3).

Azure Functions Core Tools
Core Tools Version:       4.0.5907 Commit hash: N/A +807e89766a92b14fd07b9f0bc2bea1d8777ab209 (64-bit)
Function Runtime Version: 4.834.3.22875

Skipping 'AZURE_CLIENT_ID' from local settings as it's already defined in current environment variables.
Skipping 'AZURE_CLIENT_SECRET' from local settings as it's already defined in current environment variables.
[2024-09-09T02:43:28.823Z] Failed to initialize worker provider for: /opt/homebrew/Cellar/azure-functions-core-tools@4/4.0.5907/workers/python
[2024-09-09T02:43:28.823Z] Microsoft.Azure.WebJobs.Script: File DefaultWorkerPath: /opt/homebrew/Cellar/azure-functions-core-tools@4/4.0.5907/workers/python/3.8/OSX/Arm64/worker.py does not exist.
[2024-09-09T02:43:29.129Z] Failed to initialize worker provider for: /opt/homebrew/Cellar/azure-functions-core-tools@4/4.0.5907/workers/python
[2024-09-09T02:43:29.129Z] Microsoft.Azure.WebJobs.Script: File DefaultWorkerPath: /opt/homebrew/Cellar/azure-functions-core-tools@4/4.0.5907/workers/python/3.8/OSX/Arm64/worker.py does not exist.
[2024-09-09T02:43:29.314Z] A host error has occurred during startup operation '5e184598-939e-4ab7-9d29-78a79cc8d4f1'.
[2024-09-09T02:43:29.314Z] Microsoft.Azure.WebJobs.Script: WorkerConfig for runtime: python not found.
[2024-09-09T02:43:29.320Z] Failed to stop host instance 'd3509165-bacc-4a7d-8b85-bb055549a8a0'.
[2024-09-09T02:43:29.320Z] Microsoft.Azure.WebJobs.Host: The host has not yet started.
Value cannot be null. (Parameter 'provider')
[2024-09-09T02:43:29.346Z] Host startup operation has been canceled
make: *** [start] Error 1
```

Then you just need to copy the OSX/X64 folder to OSX/Arm64 like so:

```
❯ cp -r /opt/homebrew/Cellar/azure-functions-core-tools@4/4.0.5907/workers/python/3.8/OSX/X64 /opt/homebrew/Cellar/azure-functions-core-tools@4/4.0.5907/workers/python/3.8/OSX/Arm64
```

This is a bug coming from the brew package for azure-functions that is not yet resolved.

