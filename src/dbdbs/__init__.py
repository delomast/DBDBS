# src init file to make package submodule
# define package installation directory as global variable
#   to allow sqlite database creation and access across sessions
from pathlib import Path
PACKAGEDIR = Path(__file__).parent.absolute()
