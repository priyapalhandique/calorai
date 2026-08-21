# calorai Concept Summary

## Problem

Extreme urban heat is no longer only a weather issue. It is an infrastructure,
labor, health, and budget problem. Cities can already see where heat is
concentrated, but the hard operational question is what to do next: add shade,
raise albedo, adjust work-rest schedules, activate misting, or prioritize a
capital retrofit. A heatmap alone does not answer that question.

## User

calorai is built for city heat officers, resilience planners, real-estate asset
managers, and outdoor-work operators who need a defensible, fast audit for one
district or site. The demo focuses on a simple judging story: one district, one
heat problem, three interventions, with every number traceable.

## FortyGuard Usage

The project starts from the FortyGuard Temperature API. `POST /v1/heatmap`
provides tile-level temperature layers; `POST /v1/env_params` provides the
environmental series used for apparent temperature, wet bulb, humidity, cloud,
precipitation, and solar assumptions; premium satellite and street-view
segmentation caches provide land-cover evidence; and the usage endpoints support
credit monitoring. The code wraps these calls behind a cache-first data layer so
the public demo can run in mock mode without a key while live runs remain
auditable.

On top of the API, calorai runs a physics-first audit: Stefan-Boltzmann
radiation, Brutsaert sky emissivity, Oke street-canyon trapping, Newtonian
convection, thermal inertia, latent cooling, WBGT, facade solar load, retrofit
economics, productivity loss, equity distribution, synoptic risk, and a
wind-aware misting responder. The agentic layer turns a natural-language request
into a tool plan, executes deterministic tools, and returns a trace so the
answer is inspectable rather than a black box.

## Measured Result

For Phoenix on the catalog-proven live date `2024-07-15 14:00`, FortyGuard
returned 2,891 cells with a 39.57-39.76 C tile range. The audit found solar
absorption contributed about 96-97% of the positive heat load, WBGT reached
28.5 C in the high band, and the top intervention was cool roofs with a modeled
cooling effect of -13.0 C. The vulnerability block rated Phoenix 84/100,
critical. A 24-hour cached validation run showed the ML surrogate stayed close
to the closed-form physics engine while both remained separated from the tcm
tile layer, which the project documents honestly as a canopy/comfort-layer
versus sunlit-skin-temperature boundary.

The result is a judge-openable web audit and natural-language heat agent that
does not just color a map. It explains the physics, ranks actions, exports a
PDF/GeoJSON/CSV evidence package, and states the limits of what is known.
