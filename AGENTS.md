# PSA Online Backend: Codex working rules

## Investigate before proposing a fix

- Start from the user's reported task, the current repository state, and the available task/deployment evidence. Inspect relevant logs, screenshots, task data, and code paths before naming a root cause or proposing a code change.
- Treat a timeout as an observation, not a diagnosis. Capture and inspect the current URL, page/source text, screenshot, browser logs, and last completed action before changing waits or selectors.
- Distinguish application failures from local runtime, network, authentication, and sandbox restrictions. Quote the actual error that supports the distinction; do not apply a generic sandbox explanation when the observed failure says something else.
- If evidence is incomplete, collect the next useful evidence yourself with available tools. Do not stop at a proposed diagnostic step when the user has already authorized the investigation and the tool is available.

## Phoenix account and pharmacy identity

- Phoenix credentials authenticate the shared Phoenix account. A pharmacy ID selects the pharmacy/location to use after login; it is not a separate username/password identity.
- Do not infer that each pharmacy requires separate credentials. Check the configured account and selected pharmacy ID independently, and report which one failed.
- Keep credentials and credential-bearing config out of logs, screenshots, command output, commits, and replies. Refer to the configured credential source without printing its contents.

## Azure CLI and deployment

- Use Azure CLI, Azure Functions Core Tools, Make targets, and Git CLI for operational work. Do not use editor UI clicks for git push, deployment, or verification when a CLI path exists.
- Preserve the user's normal Azure CLI profile at `~/.azure`. Do not switch to a temporary `AZURE_CONFIG_DIR` as a workaround when the user asks to use their existing Azure login.
- Run `az account show` in the intended execution environment before Azure operations. If the default profile is inaccessible, identify the exact permission/environment error and use the supported local/host execution path when available; do not claim the user must change settings unless that is an actual prerequisite.
- Before deployment, confirm target environment/slot and use this repository's documented manual-test account (Tolstoy). Never silently substitute production for staging or vice versa.
- After a deploy, verify the deployment result and the deployed behavior through an appropriate smoke check or task run, then inspect relevant runtime logs. A successful local test, successful publish command, or green static checks alone do not prove the deployed issue is fixed.
- State separately what was verified locally, what was deployed, and what was verified against the live target. Do not say “fixed” without evidence for the claim.

## Continue through the authorized task

- When the user authorizes an operational step, carry it through using the available CLI/tools and report the concrete result. Ask only for information or access that is genuinely missing; do not send the user to perform a step the current tools can perform.
- If a real access boundary blocks progress, say which command failed and why, preserve the exact useful error, and offer the shortest supported way to unblock it. Do not present speculative UI/settings instructions as fact.

