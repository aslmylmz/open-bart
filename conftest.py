"""Make the repo root and ``app/`` importable under pytest.

The repo root puts ``import scoring`` on the path; ``app/`` puts the sidecar
package (``import sidecar``) on the path without it being a pip-installed package.
"""

import os
import sys

_ROOT = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, _ROOT)
sys.path.insert(0, os.path.join(_ROOT, "app"))
