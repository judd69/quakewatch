"""QuakeWatch — run as ``python3 -m quakewatch``."""

from .cli import main

if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except BrokenPipeError:
        # Piped output closed early (e.g. `| head`) — not an error.
        try:
            import sys as _sys

            _sys.stdout.close()
        except Exception:
            pass
        raise SystemExit(0)
