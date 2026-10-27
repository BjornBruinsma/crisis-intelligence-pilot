# One World. One People. — autonomous news pilot 0.1

This pilot is intentionally AI-first: no human editorial queue is required.

## Pipeline

1. `scripts/owop_collect.py` gathers recent candidate-news metadata from multilingual Google News RSS searches and GDELT DOC 2.0.
2. `scripts/owop_editorial.py` clusters near-duplicate same-day headlines and sends up to 80 candidate groups to three AI editorial roles:
   - Good News Editor
   - Sceptic / Fact Checker
   - OWOP Editor
3. A final AI editor combines the panel judgements and chooses `publish`, `reserve`, or `reject`.
4. `scripts/owop_build.py` renders the published stories to `/site/owop/index.html`.
5. The existing GitHub Pages deployment publishes the whole `/site` directory, so OWOP is available under `/owop/` without replacing the CRISIS dashboard.

## Editorial rule

OWOP is not a generic feel-good feed. A publishable story should show something that appears to have actually improved, recovered, been restored, protected, solved, discovered, made safer, reduced, opened, or concretely helped people. Mere plans, PR, partisan messaging, celebrity fluff, shopping promotions, and tragedy-with-a-tiny-positive-angle should score low.

Current automatic thresholds:

- 75–100 + final-editor publish decision: publish
- 60–74 + non-reject decision: reserve
- below 60 or explicit reject: reject

The pilot stores panel reviews and reserve/rejected items in `site/owop/data/editorial.json` so the decision logic can be audited later.

## Required GitHub secret

Add repository secret `OPENAI_API_KEY` under **Settings → Secrets and variables → Actions**. Do not commit the key to the repository.

If the secret is absent, collection and the website build still succeed; the OWOP page reports that the AI editorial board is awaiting configuration.

Optional environment variable: `OWOP_MODEL` (workflow default: `gpt-6-luna`).

## Important pilot limitation

Version 0.1 judges headlines and source metadata, not full article text. It deliberately penalizes certainty and is not yet a fact-verification engine. Full-source retrieval, primary-source verification, event-level semantic clustering, geographical balancing, and richer translations are next-stage upgrades after observing live runs.
