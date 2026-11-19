"""Allow ``python -m py_annotate``."""

from .gui import main

# (guarded: a process that renders pages imports the main module again)
if __name__ == "__main__":
    raise SystemExit(main())
