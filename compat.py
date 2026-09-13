"""Python-version compatibility shims. Import this BEFORE anything that needs
one of these patches -- it has no other side effects, so importing it multiple
times (arkana_v2.py, setup_check.py, ...) is safe and cheap.
"""

import importlib.util
import pkgutil

if not hasattr(pkgutil, "find_loader"):
    # pytesseract 0.3.10/0.3.13 both do `from pkgutil import find_loader`,
    # removed in Python 3.13+. Without this, `import pytesseract` crashes.
    pkgutil.find_loader = lambda name: importlib.util.find_spec(name)
