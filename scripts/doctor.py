"""Local-only dependency diagnostics; never prints environment variables or keys."""
import importlib
import sys

MODULES = ('streamlit', 'xxhash', 'langgraph', 'langsmith', 'pymupdf', 'PIL', 'pandas',
           'sklearn', 'rapidocr_onnxruntime', 'openpyxl', 'cryptography.fernet', 'reportlab')

def check():
    failures = []
    for name in MODULES:
        try:
            importlib.import_module(name)
            print('OK  ' + name)
        except Exception as error:
            failures.append(name)
            print('FAIL ' + name + ' (' + type(error).__name__ + ')')
    if failures:
        print('Repair the Python 3.12 environment with: python -m pip install -r requirements.windows-py312.lock.txt')
        print('For an xxhash Application Control error use the pinned official 3.6.0 wheel. Do not disable system policy.')
    return not failures

if __name__ == '__main__':
    sys.exit(0 if check() else 1)
