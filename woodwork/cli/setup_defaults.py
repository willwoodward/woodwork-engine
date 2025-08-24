import shutil
from pathlib import Path

from woodwork.utils import get_package_directory

def copy_prompts():
    shutil.copytree(Path(get_package_directory()) / "config" / "prompts", Path(".woodwork") / "prompts" / "defaults", dirs_exist_ok=True)
