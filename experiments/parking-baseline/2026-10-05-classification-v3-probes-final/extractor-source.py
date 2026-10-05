"""Direct discovery v2 plus complete per-fragment classification v3 candidate."""

import sys
from pathlib import Path

from two_stage import main

if __name__ == "__main__":
    main(
        use_v2=True,
        use_v3=True,
        replay_path=Path(sys.argv[3]) if len(sys.argv) > 3 else None,
    )
