"""Public demo entry point. No provider credentials are needed."""
import os
import runpy
from pathlib import Path

os.environ['CLEARCLAIM_PUBLIC_DEMO'] = '1'
runpy.run_path(str(Path(__file__).with_name('app.py')), run_name='__main__')
