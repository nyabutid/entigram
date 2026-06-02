from pathlib import Path
import os
from typing import Optional

def find_project_root(start_path: str = ".") -> Optional[Path]:
    """
    Searches upwards from the start_path to find a directory containing a .etg folder.
    Returns the absolute Path of the project root, or None if not found.
    """
    current = Path(start_path).expanduser().resolve()
    
    # Search up to the filesystem root
    while current.parent != current:
        if (current / ".etg").exists():
            return current
        current = current.parent
        
    return None
