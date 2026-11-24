# Automated PR review by Claude (B-025)

Every non-draft pull request is reviewed by a fresh Claude Code session in GitHub Actions
(`.github/workflows/claude-review.yml`, instructions in `.github/claude-review.md`). Claude reads
the diff, checks it against `CLAUDE.md`, posts one comment starting with
`## Claude review: PASS` or `## Claude review: FAIL`, and the job fails on `FAIL`. On `PASS` the job
turns on auto-merge, and GitHub merges the PR once all required checks are green. A new push to
the PR starts a new review; if that one fails, the required check blocks the merge again.

## One-time setup

1. **Credential** (Settings → Secrets and variables → Actions → New repository secret), one of:
   - `CLAUDE_CODE_OAUTH_TOKEN`: run `claude setup-token` locally (uses your Claude subscription), or
   - `ANTHROPIC_API_KEY`: an API key from console.anthropic.com (billed per use).
2. **Auto-merge:** Settings → General → Pull Requests → tick "Allow auto-merge".
3. **Branch protection** (Settings → Branches, or Rules → Rulesets, for `main`):
   require a pull request, and require the status checks `test` (CI) and `review` (Claude review)
   to pass. Without the required checks, auto-merge would merge immediately.

## Things to know

- **The review rules come from `main`.** The workflow reads `.github/claude-review.md` from the
  base branch, so a PR can't soften its own review. The workflow file itself, however, runs as it
  is in the PR, so Claude fails every PR that touches `.github/`; merge those yourself after a look.
- **Pushes merged this way don't trigger workflows.** GitHub doesn't start workflows for events
  caused by the `GITHUB_TOKEN`, so the `push: main` run of `ci.yml` is skipped for auto-merged PRs.
  The same tests already ran on the PR head, so this is acceptable; use a PAT for the merge step if
  you want it.
- **Fork PRs** get no secrets, so the review fails for them; that is intended for a personal repo.
- **Merging despite a FAIL:** fix the findings and push (a new review runs), or, as admin, merge
  by hand ("bypass rules").
