# Contributing to BankPulse Social Split

This repository develops BankPulse Social Split as a portfolio application with executable business guarantees. Contributions should preserve the complete Social Split story: confirmed business state, durable facts, recoverable analytics, live Grafana rendering and a release gate based on business correctness.

Changes to the broader [BankPulse platform](https://github.com/VillaforTech/bankpulse) follow its own pull-request workflow. Keep contributions and verification evidence traceable to the repository where they were made.

## Workflow

1. Create a focused branch from the current `main`.
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
- Documentation describes observed behavior and credits contributions through their commits and reviews.

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

Preserve authorship accurately. The application was implemented by Roberto Villafuerte with Codex assistance; adaptations in the shared repository receive credit through their own commits, reviews and merged pull requests.

Keep reproducible verification evidence in `docs/business-verification.md` so another developer can run, inspect and challenge the results.
