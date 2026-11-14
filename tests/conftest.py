import os

from hypothesis import settings

# HYPOTHESIS_PROFILE=ci (set in GitHub Actions) tries more random cases than a local run.
settings.register_profile("dev", max_examples=100)
settings.register_profile("ci", max_examples=1000)
settings.load_profile(os.environ.get("HYPOTHESIS_PROFILE", "dev"))
