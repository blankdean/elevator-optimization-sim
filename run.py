"""Run the source directly, with numbered menus or command-line options."""

import sys
from pathlib import Path

if __name__ == "__main__":
    sys.path.insert(0, str(Path(__file__).resolve().parent / "src"))
    from elevator_sim.cli import interactive_args, main

    args = sys.argv[1:]
    if not args and sys.stdin.isatty():
        args = interactive_args()
    raise SystemExit(main(args))
