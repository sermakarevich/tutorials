# Notebooks

Chapter notebooks live in the tutorial folder (`../../NN_<slug>.ipynb`), not here.
Every notebook starts with the same setup cell, which walks up to the folder that
holds `pyproject.toml` (this `project/`) and imports the shared package:

```python
import sys
from pathlib import Path

here = Path.cwd()
ROOT = next(d for d in [here, *here.parents, here / "project"] if (d / "pyproject.toml").exists() and (d / "src" / "openmetadata_tutorial").exists())
sys.path.insert(0, str(ROOT / "src"))

from openmetadata_tutorial import nb
ROOT = nb.setup()
```

Execute a chapter notebook (from `project/`): `just nb 06_lineage`.
