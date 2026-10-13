"""Bundle only Windows x64 TkDND, for the Tcl version of the build runtime."""

from pathlib import Path
from PyInstaller.utils.hooks import get_package_paths
import tkinter

package = Path(get_package_paths("tkinterdnd2")[1])
platform = "win-x64-tcl9" if int(tkinter.TclVersion) >= 9 else "win-x64"
datas = [(str(package / "tkdnd" / platform), "tkinterdnd2/tkdnd/" + platform)]
