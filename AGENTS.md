# Automated Contributors

This repository is developed collaboratively by the owner and AI agents via [Paperclip](https://paperclip.ing).

## Bot Accounts & Agent Identity

| GitHub Account | Email Used in Commits | Role | Access Mechanism |
|---|---|---|---|
| TzuhekBareket | cto@paperclip.ing | Paperclip platform service account | GitHub token stored in Paperclip |

**Note:** `TzuhekBareket` is the GitHub account registered to the Paperclip platform's `cto@paperclip.ing` email address. When Paperclip agents author commits, GitHub resolves the commit email to this account and shows it as the author. The actual push is performed using the repository owner's GitHub token stored in Paperclip.

## Push Mechanism

Paperclip agents do not have independent GitHub credentials. All pushes to this repository are made using the repository owner's GitHub Personal Access Token, stored securely in Paperclip. The token owner (`5drei1`) is always the push actor.

## Active Agents

| Agent | Role | Paperclip Email |
|---|---|---|
| CTO Agent | Technical lead — architecture, code review, delegation | cto@paperclip.ing |

## Token & Security Policy

- The GitHub token used by Paperclip should have **only `repo` scope** (and `workflow` if GitHub Actions are used).
- A **dedicated token** for Paperclip is recommended — separate from personal tokens used for other tools.
- The token should be rotated periodically (every 90 days recommended).
- All code pushed by agents is reviewed in the PR history. Direct pushes to `main` require explicit owner approval.

## Branch Protection

Branch protection is enabled on `main`:
- Pull Requests required for all changes
- Direct pushes to `main` are restricted
- Force pushes and branch deletion are disabled

See [GitHub Branch Settings](https://github.com/5drei1/lex-retriever/settings/branches) to review or update protection rules.
