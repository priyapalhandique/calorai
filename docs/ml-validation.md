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

## Stage 2 - real FortyGuard 24-h series (pending, post-deploy)

Protocol (already implemented in `calorai/ml/forecast.py:validate_vs_real`):

1. Pull one real 24-h env series for the flagship district
   (Maryvale/Phoenix, pinned 2024-07-15; ~1-4.5k credits).
2. For each hour, build the 8 FEATURES from the series + district
   params, observe the API tile temperature.
3. Report three numbers side by side (never hide the bad one):
   - surrogate MAE vs observed (does the ML reproduce the API?)
   - physics MAE vs observed (the closed-form baseline)
   - surrogate vs physics MAE (do the two models agree?)
   - layer_offset_c = mean(physics - observed), the documented
     canopy-vs-skin semantics offset.

The table lands here the day the pull runs. Until then, the surrogate
is advertised as "physics reproduction engine with a documented
validation date", not as an API forecaster.