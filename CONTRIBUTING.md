# Contributing to the BankPulse reference

This repository maintains an executable integration baseline for the team-owned BankPulse product. Contributions should preserve the complete Social Split story: confirmed business state, durable facts, recoverable analytics, live Grafana rendering and a release gate based on business correctness.

The shared product work belongs in [BANKPULSE-V2.1-LAB2](https://github.com/VillaforTech/bankpulse). Use this repository to improve the reference, reproducibility or engineering documentation. Do not use a reference commit to claim another contributor completed a shared issue.

## Workflow

1. Create a focused branch from the current `main` or the reviewed reference branch.
2. Describe the product behavior, failure mode or documentation gap being changed.
3. Add or update the smallest meaningful verification.
4. Record commands and observed results in the pull request.
5. Request review only after all required checks pass.

Use conventional prefixes such as `feat/`, `fix/`, `docs/` and `chore/`. Keep generated artifacts limited to intentional evidence and never commit local secrets.

## Definition of done

- Aggregate and outbox writes remain transactional.
- Event identity and aggregate revision survive retries and replay.
- Analytics commits only after its state is durable.
- Coverage and freshness report uncertainty instead of inventing history.
- Browser tests measure a correlated Grafana render, including losses and errors.
- Recovery tests retain state across broker interruption and service restart.
- Failed, skipped or cancelled required checks cannot produce a green release gate.
- Documentation describes observed behavior and distinguishes the reference from team contributions.

## Validation

```bash
bash scripts/unit-test.sh
bash scripts/projection-test.sh
bash scripts/business-test.sh
python3 scripts/resilience_test.py
npm ci
npx playwright install --with-deps chromium
npm run browser-test
```

Run the full suite for runtime changes. For documentation-only changes, verify links, commands, formatting and the rendered GitHub structure, then state that runtime behavior was unchanged.

## Security and attribution

Use only synthetic accounts and amounts. Never commit `.env`, tokens, institutional credentials or real personal and financial data. Do not publish a Codespace or local database port to make a demo easier.

Preserve authorship accurately. The reference was implemented by Roberto Villafuerte with Codex assistance; adaptations in the shared repository receive credit through their own commits, reviews and merged pull requests.

Course-specific evidence remains in `docs/deber-01.md`, but the repository should read first as an engineering reference that another developer can run, inspect and challenge.
