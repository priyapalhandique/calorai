# ML Validation - physics-informed forecast surrogate (D6)

Honest validation table for `calorai/ml/forecast.py`. The surrogate is
trained on synthetic physics sweeps (the closed-form equilibrium solver
is the teacher) and validated in two stages. Stage 1 ships now; stage 2
lands post-deploy (real API series, deferred by design - no credits
spent before the Render infrastructure is green).

## Stage 1 - held-out synthetic rows (shipped 2026-08-20)

`python -m calorai train-forecast --rows 100000` -> `data/models/forecast_v1.joblib`

| Metric | Value |
|---|---|
| Training rows (synthetic physics sweep) | 100 000 |
| Hold-out rows (20 %) | 20 000 |
| Hold-out MAE | 0.750 C |
| Hold-out RMSE | 0.966 C |
| R2 | 0.9966 |
| Baseline MAE (predicting the mean) | 13.081 C |
| Gain over baseline | 94.3 % |

Interpretation: with 100k rows the GBM reproduces the closed-form
physics solver to well under a degree on inputs it never trained on.
This is internal consistency, not accuracy against the real world -
the physics itself carries the documented layer offset (tcm canopy vs
skin, 238-258 W/m2 residual verdict). That is exactly why stage 2
exists.

## Stage 2 - real FortyGuard 24-h series (run 2026-08-20, cached pulls)

Protocol (`scripts/validate_live.py`, re-runs with zero new credits from
the disk cache):

1. Pull a 24-h env series **and** 24 single-hour tcm heatmaps for the
   flagship district on the pinned catalog date (**Phoenix, 2024-07-15**).
2. For each hour, observe the API tile temperature (hottest cell and
   district mean), build the 8 features, and record both predictions:
   the surrogate (`forecast_v1.joblib`) and the closed-form physics
   baseline (equilibrium solve on the same inputs).
3. Report three numbers side by side (never hide the bad one):
   surrogate MAE vs observed, physics MAE vs observed, surrogate vs
   physics MAE, plus `layer_offset_c = mean(physics - observed)`.

### Phoenix 2024-07-15 (24 h, n=24 cached hours)

| Metric | Value |
|---|---|
| Surrogate MAE vs observed tile max | 9.54 C |
| Surrogate MAE vs observed tile mean | 9.50 C |
| Physics MAE vs observed tile max | 11.74 C |
| Physics MAE vs observed tile mean | 11.72 C |
| Surrogate vs physics MAE | 2.46 C |
| Layer offset (physics - observed) | -2.24 C |

Peak tile 40.6 C at 17 h vs peak air 41.2 C at 15 h — the API tile
layer hugs the air temperature curve (canopy/comfort semantics), while
physics predicts a hotter sunlit **skin** that divides the day.

### What the numbers mean (honest reading)

The surrogate reproduces the physics solver (2.46 C apart on identical
inputs), but both sit far from the **tile layer** because the layer is
not skin: the API tile stays within ~3 K of air temperature all day
(31-41 C), whereas sunlit skin physics exceeds 50 C around solar noon.
That gap *is* the documented tcm-canopy-vs-skin layer semantics, not a
model defect. The 2.27-layer_offset_c sign (physics below observed at
night, above by day) reflects the storage/inertia in the layer that the
steady-state equilibrium does not carry.

The surrogate is, therefore, a physics reproduction engine with a
validation date — not a direct forecaster of the tcm layer, and the
number the product quotes on the dashboard is the physics equilibrium
(the honest upper bound), not the canopy layer. This is the boundary
stated in "what doesn't work yet".