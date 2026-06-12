# A/B Test Guide — smart-suggest

Step-by-step guide to running, monitoring, and interpreting recommendation A/B tests.

---

## 1. Setting Up a Test

### Step 1 — Run a power analysis first

Before creating the test, calculate how many users you need:

```python
from significance import sample_size_needed

n = sample_size_needed(
    baseline=0.12,   # current CTR
    mde=0.02,        # minimum lift you care about (+2pp)
    alpha=0.05,      # significance level
    power=0.80,      # 80% chance of detecting the effect if real
)
print(f"Need {n:,} users per variant before analysing results")
```

**Do not launch the test unless you can realistically collect this many users.** An under-powered test that returns "not significant" is uninformative.

### Step 2 — Create the test

```bash
curl -X POST http://localhost:8000/ab_tests \
  -H "Content-Type: application/json" \
  -d '{"name": "rec-strategy-v1-vs-v2", "control": "v1", "treatment": "v2"}'
```

Response includes `id` — save it. All subsequent calls use this ID.

### Step 3 — Assign users to variants

On each recommendation request, call the assignments endpoint first:

```bash
curl "http://localhost:8000/ab_tests/1/assignments?user_id=42"
# → {"variant": "A", ...}
```

Then serve the corresponding strategy:
- Variant A → `GET /recommendations/v1?user_id=42`
- Variant B → `GET /recommendations/v2?user_id=42`

### Step 4 — Log events

Log every impression, click, and purchase back to the test:

```bash
# impression
curl -X POST http://localhost:8000/interactions \
  -d '{"user_id": 42, "item_id": 7, "action": "view"}'
```

For A/B-tagged events, use the logger directly in application code:
```python
from ab_testing.logger import log_impression, log_click, log_purchase

log_impression(db, user_id=42, item_id=7, test_id=1, variant=Variant.A)
```

---

## 2. How Long to Run the Test

### Minimum duration rules

1. **Hit the pre-calculated sample size** — never stop early because p < 0.05 appeared (peeking bias).
2. **Run for at least two full weeks** — captures day-of-week effects and outlasts the novelty effect.
3. **Check guardrail metrics daily** — stop immediately if error rates or page load time degrades.

### Novelty effect
Users tend to engage more with *anything new*. Run the test long enough for the initial curiosity spike to flatten (typically 3–5 days).

```
Day 1-5:  Inflated CTR for variant B (novelty)
Day 6-14: CTR stabilises — this is the true signal
```

---

## 3. Interpreting Results

### Check the metrics

```bash
curl http://localhost:8000/ab_tests/1/results
```

Look at the `lift` section:
```json
{
  "lift": {
    "ctr_absolute": 0.032,
    "ctr_relative_pct": 26.7,
    "conversion_rate_absolute": 0.018,
    "conversion_rate_relative_pct": 22.5
  }
}
```

### Get the full statistical analysis

```bash
curl http://localhost:8000/ab_tests/1/statistical_analysis
```

This returns:
- **p-value** from chi-square test (CTR and conversion rate)
- **95% Wilson CI** for each variant's metric
- **Cohen's h** effect size (negligible / small / medium / large)
- **Practical verdict** (worth_shipping / stat_sig_but_small_effect / promising_but_underpowered / no_effect)
- **Human-readable conclusion** sentence

### Reading the verdict

| Verdict | Meaning | Action |
|---|---|---|
| `worth_shipping` | Stat significant + meaningful effect | Ship variant B |
| `stat_sig_but_small_effect` | Real but tiny difference | Defer — not worth the engineering cost |
| `promising_but_underpowered` | Looks good, p not there yet | Run longer |
| `no_effect` | No evidence of difference | End test, keep variant A |

---

## 4. Common Mistakes

### Peeking (most common)
**Problem:** Checking p-values every day and stopping when p < 0.05.  
**Effect:** False positive rate rises from 5% to ~40%.  
**Fix:** Pre-commit to a sample size. Do not look at primary metric until you reach it.

### Underpowered tests
**Problem:** Running a test with 200 users when you need 4,000.  
**Effect:** "Not significant" result is meaningless — you simply couldn't detect the effect.  
**Fix:** Always run `sample_size_needed()` before launch.

### Multiple comparisons
**Problem:** Testing CTR, conversion rate, revenue, and diversity simultaneously.  
**Effect:** With 4 metrics at α=0.05, expected false positive rate is ~19%.  
**Fix:** Pick one primary metric before launch. Use Bonferroni correction (α/4 = 0.0125) for secondary metrics.

### Novelty effect
**Problem:** Stopping after 3 days when variant B looks great.  
**Effect:** Users clicked more because it was new, not because it's better.  
**Fix:** Minimum 2-week run; compare day 1–3 CTR against day 10–14.

### Ignoring practical significance
**Problem:** Shipping because p = 0.001.  
**Effect:** A 0.1pp CTR lift is statistically significant at n=1M but has zero business impact.  
**Fix:** Check Cohen's h. A "negligible" effect is not worth shipping.

### Leakage between variants
**Problem:** A user in variant A somehow receives variant B recommendations.  
**Effect:** Both groups contain mix of treatments, diluting the signal.  
**Fix:** Audit that `assign_variant` is called before every recommendation request; assert deterministic hash matches stored assignment.

---

## 5. Stopping the Test

When you reach your target sample size AND have run for at least 2 weeks:

1. Check that guardrail metrics (error rate, latency) are within bounds.
2. Read the `statistical_analysis` verdict.
3. If `worth_shipping`: deploy variant B globally.
4. Update the test status:
   ```python
   test.status = TestStatus.COMPLETED
   db.commit()
   ```
5. Document results in your team's experiment log — what worked, what didn't, and why.
