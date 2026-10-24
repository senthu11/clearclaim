"""Check required imports without reading credentials or making network calls."""
import importlib

for name in ("streamlit", "pymupdf", "pandas", "pydantic", "onnxruntime", "sklearn", "xxhash", "langchain_openai"):
    try:
        importlib.import_module(name)
        print(f"{name}: OK")
    except Exception as error:
        print(f"{name}: {type(error).__name__}: {error}")
