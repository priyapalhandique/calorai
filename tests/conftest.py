"""Force the mock data source for the whole test suite.

resolve_source(None) prefers live whenever a FORTYGUARD_API_KEY is
present (e.g. a local .env). Tests must be deterministic, offline and
zero-credit, so every test pins the mock source here, before any
calorai import.
"""

import os

os.environ["CALORAI_DATA_SOURCE"] = "mock"