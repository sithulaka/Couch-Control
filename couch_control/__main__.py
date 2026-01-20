#!/usr/bin/env python3
"""
Allow running the module directly: python -m couch_control
"""

from .cli import main

if __name__ == "__main__":
    exit(main())
