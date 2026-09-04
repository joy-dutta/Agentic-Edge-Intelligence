# GitHub Project Files

This folder contains the files GitHub uses to maintain the repository. They do not change the traffic-control experiment itself.

| File or folder | What it does |
|---|---|
| `CODEOWNERS` | Identifies the repository owner for review requests. |
| `CONTRIBUTING.md` | Explains how to propose a focused, reproducible change. |
| `SECURITY.md` | Explains how to report a vulnerability privately and how credentials are handled. |
| `dependabot.yml` | Asks GitHub to propose dependency updates. Updates are reviewed rather than accepted automatically because the experiment uses frozen versions. |
| `pull_request_template.md` | Reminds contributors to describe scientific, data, cost, and reproducibility effects. |
| `ISSUE_TEMPLATE/` | Provides the structured bug-report form and issue-menu settings. |
| `workflows/ci.yml` | Runs the offline test, integrity, documentation, result, and container checks on pushes and pull requests. It receives no API key and makes no billable call. |

To reproduce the same checks locally, run the commands in [the contributing guide](CONTRIBUTING.md). A green CI badge on the [root README](../README.md) means the latest commit passed these automated checks.
