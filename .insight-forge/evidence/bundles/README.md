# Evidence bundles

One YAML file per crystallized entry. Schema:

```yaml
entry_id: H01
target_layer: heuristic
crystallized_via: verbal-affirmation
created_at: 2026-05-05T12:34:56+00:00
from_staging: O03
sessions: [aaaa1111]
evidence:
  - kind: trigger
    role: user
    quote: "Always use pnpm not npm"
  - kind: verbal-affirmation
    role: user
    quote: "yes parfait, on part sur pnpm"
counter_evidence:
  text: "Doesn't apply when …"
  source: deterministic-template
promotion_gate:
  passed: true
  reason: "User affirmation phrase"
```
