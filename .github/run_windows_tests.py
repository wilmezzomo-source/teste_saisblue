"""Isolated CI diagnostics. No company credentials or data exist in this runner."""
import os
from pathlib import Path
import sys
import unittest

suite=unittest.defaultTestLoader.discover('.')
result=unittest.TextTestRunner(verbosity=2).run(suite)
for test,trace in result.failures+result.errors:
    safe=trace[-10000:].replace('%','%25').replace('\r','%0D').replace('\n','%0A')
    print('::error title='+test.id()+'::'+safe,flush=True)
summary=os.environ.get('GITHUB_STEP_SUMMARY')
if summary:
    Path(summary).write_text(f'Windows updater: {result.testsRun} tests; {len(result.failures)} failures; {len(result.errors)} errors.\n',encoding='utf-8')
sys.exit(0 if result.wasSuccessful() else 1)
