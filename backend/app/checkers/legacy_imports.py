import importlib.util
from functools import lru_cache
from pathlib import Path
from types import ModuleType


REPO_ROOT = Path(__file__).resolve().parents[3]


@lru_cache(maxsize=8)
def load_legacy_module(filename: str) -> ModuleType:
    module_path = REPO_ROOT / filename
    spec = importlib.util.spec_from_file_location(module_path.stem, module_path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"无法加载旧脚本: {module_path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module
