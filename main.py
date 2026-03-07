"""PyInstaller entry point — avoids relative-import issues."""
import sys
from couch_control.cli import main

if __name__ == '__main__':
    sys.exit(main())
