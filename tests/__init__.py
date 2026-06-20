import os
import tempfile
from pathlib import Path


os.environ.setdefault("ENTIGRAM_REGISTRY_OFFLINE", "1")
os.environ.setdefault(
    "ENTIGRAM_REGISTRY_CACHE_DIR",
    str(Path(tempfile.gettempdir()) / "entigram-test-registry-cache"),
)
