---
title: Releasing - PyPI, MCP Registry and GitHub Releases from a tag
description: One-time setup for PyPI trusted publishing, GitHub Pages and the MCP Registry, and the steps to release a new version of yfinance-agent-mcp from a git tag.
---

# Releasing

Pushing a tag `vX.Y.Z` runs `.github/workflows/release.yml`, which:

1. checks that the tag matches the version in `pyproject.toml`, `server.json` and the plugin
   files (`scripts/set_version.py --check-tag`), and takes the release notes from that
   version's section in `CHANGELOG.md` (`scripts/release_notes.py`). If either step fails,
   nothing is published;
2. builds the sdist and wheel with `uv build` and checks that the wheel runs with `uvx`;
3. creates [PEP 740](https://peps.python.org/pep-0740/) attestations;
4. publishes to PyPI with trusted publishing (no token);
5. publishes `server.json` to the [MCP Registry](https://registry.modelcontextprotocol.io/)
   as `io.github.n-kostadinov/yfinance-agent-mcp`, logging in with GitHub OIDC;
6. creates a GitHub Release with the changelog section and the package files.

## One-time setup

These steps need the maintainer's accounts and are done once.

### PyPI trusted publisher

On [PyPI](https://pypi.org/manage/account/publishing/), add a **pending publisher**:

| Field | Value |
|---|---|
| PyPI project name | `yfinance-agent-mcp` |
| Owner | `n-kostadinov` |
| Repository name | `yfinance-agent-mcp` |
| Workflow name | `release.yml` |
| Environment name | `pypi` |

### GitHub repository

- **Environment:** create an environment named `pypi` (Settings → Environments). Adding
  yourself as a required reviewer makes every release wait for your approval.
- **Pages:** Settings → Pages → Source: **GitHub Actions**.
- **Metadata:** description, homepage and topics, for example:

    ```bash
    gh repo edit n-kostadinov/yfinance-agent-mcp \
      --description "Read-only Yahoo Finance MCP server for AI trading-research agents (yfinance)" \
      --homepage https://n-kostadinov.github.io/yfinance-agent-mcp/ \
      --add-topic mcp --add-topic mcp-server --add-topic model-context-protocol \
      --add-topic yfinance --add-topic yahoo-finance --add-topic stock-market \
      --add-topic market-data --add-topic trading --add-topic ai-agents --add-topic llm \
      --add-topic claude --add-topic python --add-topic finance --add-topic uv \
      --add-topic stocks --add-topic stock-data --add-topic financial-data \
      --add-topic claude-code --add-topic mcp-tools --add-topic agentic-ai
    ```

- **Social preview:** upload an image under Settings → General → Social preview (a page card
  from `site/assets/images/social/index.png` works).

### MCP Registry

Nothing to register up front. The workflow logs in with GitHub OIDC, which proves ownership
of the `io.github.n-kostadinov/` namespace, and the registry checks the
`<!-- mcp-name: ... -->` marker in the README published on PyPI.

## Automatic releases

`.github/workflows/yfinance-update.yml` runs every day at 05:41 UTC and on demand
(Actions → **yfinance update** → **Run workflow**). It releases a new patch version whenever
yfinance publishes a release this project can adopt:

1. `scripts/update_yfinance.py check` reads yfinance's releases from PyPI and picks the
   newest one that is final (no pre-releases), has files, is not yanked, is newer than the
   current `yfinance>=` floor and below the `<2` cap, and has been out for at least 3 days,
   so a broken or compromised upload has time to be pulled.
2. `scripts/update_yfinance.py apply X` bumps the patch version in every versioned file,
   raises the requirement to `yfinance>=X,<2` and re-locks `uv.lock`, and moves the
   `[Unreleased]` entries into a new CHANGELOG section with a "Require yfinance X or later"
   entry. The result is committed to a branch `automation/yfinance-X`.
3. The whole `ci.yml` and the live tests (`live.yml`) run against that commit.
4. If both pass, the workflow fast-forwards `main` to the tested commit, pushes the tag
   `vX.Y.Z`, starts the **Release** workflow on the tag and the **Docs** workflow on `main`,
   and deletes the branch. It starts them itself because a tag pushed with `GITHUB_TOKEN`
   triggers no workflow.

When something fails, nothing reaches `main` or PyPI: the run turns red, GitHub emails you,
the branch stays for inspection, and the next day's run starts over. If `main` moved while
the tests ran, the fast-forward is refused and the next run rebuilds on the new `main`.

A yfinance release at or above the cap (a new major version) is never adopted: the workflow
opens one issue for it instead, so you can check the changes, raise the cap and release by
hand.

A manual run has two options:

| Option | Effect |
|---|---|
| `dry_run` | Prepare and test the update, then delete the branch and release nothing. |
| `live_tests` | Clear it to release without the live tests, for example while Yahoo throttles GitHub's runners. |

A run on any branch other than `main` never releases. To see the whole flow without
releasing, lower the floor on a scratch branch (`uv add "yfinance>=1.7.0,<2" --no-sync`) and
start a dry run on it.

Things to know:

- GitHub turns off scheduled workflows in a public repository after 60 days without
  activity, after an email warning. Turn it back on with
  `gh workflow enable yfinance-update.yml`.
- Dependabot ignores yfinance, so updates come only from this workflow.
- If you protect `main` later, let `github-actions[bot]` bypass the rule, or the
  fast-forward fails.
- Adding a required reviewer to the `pypi` environment makes each automatic release wait
  for one click.

## Release a version

1. Bump the version everywhere it appears:

    ```bash
    uv run python scripts/set_version.py --bump patch    # or minor, major
    ```

2. In `CHANGELOG.md`, rename `[Unreleased]` to the new version with today's date, add an
   empty `[Unreleased]` above it, and update the links at the bottom.
3. Check and commit:

    ```bash
    uv run python scripts/set_version.py --check
    uv run python scripts/release_notes.py 0.1.1    # prints the release notes
    uv run pytest --cov
    git commit -am "Release 0.1.1"
    ```

4. Tag and push:

    ```bash
    git tag v0.1.1
    git push origin main v0.1.1
    ```

5. Watch the **Release** workflow, then verify:

    ```bash
    uvx yfinance-agent-mcp@0.1.1 --version
    ```

    and search the registry for `yfinance-agent-mcp`.
