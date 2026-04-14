# Quality Gates

This repository now uses a layered assurance model:

- Local hooks: `pre-commit` and `pre-push` via `.pre-commit-config.yaml`
- PR gates: `.github/workflows/pr-gates.yml` plus `.github/workflows/codeql.yml`
- Nightly deep assurance: `.github/workflows/nightly-deep-assurance.yml`
- Release gates: `.github/workflows/release-gates.yml`

## Required PR Checks

Configure branch protection to require these checks:

- `lint_and_type`
- `unit_and_integration_tests`
- `coverage_gate`
- `security_sast`
- `supply_chain`
- `secrets`
- `container_and_iac`
- `build_and_package`
- `docs_and_contracts`
- `codeql`

## Branch Protection Policy

Apply these GitHub settings to `main`:

- Require pull requests before merging
- Require 2 approvals
- Require review from code owners
- Dismiss stale approvals when new commits are pushed
- Require status checks to pass before merging
- Require branches to be up to date before merging
- Enable merge queue
- Disable force-push
- Disable branch deletion

## Ownership And Automation

- `CODEOWNERS` is defined in `.github/CODEOWNERS`
- Dependabot is defined in `.github/dependabot.yml`
- Use `merge_group` triggers so merge queue evaluates the same gate set as pull requests

## Coverage Policy

The enforced package-level coverage threshold currently targets the maintained enduser surfaces:

- `codewiki/src/enduser/*`
- `codewiki/cli/commands/enduser.py`
- `codewiki/run_web_app.py`

Diff coverage is enforced at `90%` for changed lines.

Expand the package-level coverage include list as legacy modules gain stable tests.

## Release Provenance

Release builds now generate and upload:

- Built distributions
- An SPDX SBOM
- A GitHub build provenance attestation

Tag protection and release permissions still need to be enforced in GitHub repository settings.
