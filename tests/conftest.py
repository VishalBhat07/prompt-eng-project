"""Keep the default test environment deterministic and dependency-light.

The full semantic mode loads a sentence-transformers model (and numpy). The
Windows demo environment is intentionally installed without those heavy
dependencies, so tests default to the heuristic layer unless a test explicitly
sets ``CTG_SEMANTIC_MODE=full``.
"""

import os

os.environ.setdefault("CTG_SEMANTIC_MODE", "heuristic")
