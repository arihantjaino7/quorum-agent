# Model bake-off: debrief2

3 runs per model and role, temperature 0, draft prompts, scored against `seed/expected_debrief2.json`.
Normalizer: corrections found + digression removed + key content kept. Extractor: decisions, Rahul attribution,
tasks (found, ISO due date, raw phrase). The extractor is given the raw debrief, not the normalizer's output.

`model@low` = reasoning effort low. Rate-limit waits (free tier) are excluded from the time column.

| Role | Model | Avg score | Worst run | Avg time | Failed runs | Rate-limit waits | What it missed (any run) |
|---|---|---|---|---|---|---|---|
| normalizer | `openai/gpt-oss-120b` | 9.0/10 | 9/10 | 6.6s | 0 | 17s | correction self_correction:December 1st |
| normalizer | `openai/gpt-oss-120b@low` | 9.7/10 | 9/10 | 2.7s | 0 | 26s | dropped 'stripe' |
| normalizer | `openai/gpt-oss-20b` | 0.0/0 | 0/0 | 0.0s | 3 | 10s | FAILED: normalizer: no valid output after 3 attempts (invalid output: Error code: 400 |
| normalizer | `openai/gpt-oss-20b@low` | 8.0/10 | 7/10 | 2.7s | 0 | 39s | correction date_resolution:Monday; correction date_resolution:next Wednesday; correction self_correction:December 1st |
| normalizer | `qwen/qwen3.8-27b` | 10.0/10 | 10/10 | 1.4s | 0 | 52s | nothing |
| extractor | `openai/gpt-oss-120b` | 13.0/13 | 13/13 | 4.2s | 0 | 10s | nothing |
| extractor | `openai/gpt-oss-120b@low` | 13.0/13 | 13/13 | 2.4s | 0 | 53s | nothing |
| extractor | `openai/gpt-oss-20b` | 8.7/13 | 0/13 | 2.3s | 1 | 0s | FAILED: extractor: no valid output after 3 attempts (invalid output: Error code: 400 |
| extractor | `openai/gpt-oss-20b@low` | 11.7/13 | 11/13 | 1.2s | 0 | 48s | task Ananya/onboarding: due (2026-11-02); task Ananya/onboarding: due (2026-11-08); task Priya/investor update: due (2026-11-06); task Rahul/Play Store: due (2026-11-06) |
| extractor | `qwen/qwen3.8-27b` | 13.0/13 | 13/13 | 1.7s | 0 | 30s | nothing |
