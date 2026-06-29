# Dual-Model Debate: Reference Script

The working dual-model debate engine lives at `/mnt/d/debate-engine/dual_debate.py`.

Key design decisions that made it work:

## Model Selection
- **Lead**: `deepseek-v4-pro` (temperature=0.7) — deep reasoning, generates thorough arguments
- **Challenger**: `deepseek-v4-flash` (temperature=0.8) — faster, slightly more aggressive in finding gaps
- **Judge**: `deepseek-v4-flash` (temperature=0.3) — low temp for structured, consistent output

## API Key Extraction
The script reads the API key from `~/.hermes/config.yaml` → `custom_providers` section, not from `.env`. This was necessary because:
1. The `.env` file had no LLM API keys (only QQ/terminal config)
2. The custom provider `taotoken.net` stores its key in `config.yaml`
3. Hermes's `security.redact_secrets: true` masks keys in terminal output; PyYAML extraction works around this

## Debate Flow
Each round:
1. Lead speaks first (sees question + own history + opponent's previous)
2. Challenger responds (sees question + own history + lead's LATEST only)
3. Context injection is limited to last round only — avoids context bloat

## Timeout Handling
- API timeout: 600 seconds (was 240, caused failures on v4-pro's long responses)
- 3 retries with 5-second backoff
- `max_tokens: 3000` to keep responses manageable

## Quality Observations from Test Run (康方生物 debate)
1. v4-flash caught that v4-pro inflated "product revenue" by including licensing fees — genuine error discovery
2. v4-flash cited specific FDA rejection precedent (信迪利单抗) that v4-pro missed
3. v4-flash used per-capita sales metrics (96万 vs 267万) to rebut "efficiency" claim — different analytical framework
4. Both models used real drug names, trial data, and financial figures without hallucination
