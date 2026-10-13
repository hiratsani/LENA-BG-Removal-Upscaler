# LENA application source

The current Windows desktop app: background removal, Hair & Fur refinement, and 2× / 4× upscaling. Original LENA code is licensed under [MIT](../LICENSE).

## Run from source

Use **64-bit Python 3.12** from [python.org](https://www.python.org/downloads/windows/), including Tcl/Tk, on Windows 10 (1903 or newer) or Windows 11.

From the repository root, run in PowerShell:

```powershell
cd app
py -3.12 -m venv .venv
& ./.venv/Scripts/python.exe -m pip install -r requirements.txt
& ./.venv/Scripts/python.exe prepare_models.py
& ./.venv/Scripts/python.exe lena_app.py
```

Model preparation downloads approximately **73.4 MB** once: Basic removal, Hair & Fur, and SPAN upscaling. Each file must match its pinned SHA-256 and byte count before it is used. Better and Best can be downloaded from the app when needed. Model weights stay outside Git.

After setup, you can also double-click **Run LENA.cmd**. Preferences and optional models are stored in `%LOCALAPPDATA%\LENA`. Set `LENA_DATA_DIR` to a separate directory when developing or testing.

## Build

Install the build requirements in the same environment:

```powershell
& ./.venv/Scripts/python.exe -m pip install -r requirements-build.txt
./build_lena.ps1 -AppOnly
```

The portable app is written to `app/.build/dist/LENA/`.

For the Windows installer, install [Inno Setup 6](https://jrsoftware.org/isdl.php), then run:

```powershell
./build_lena.ps1
```

You can pass `-Compiler 'C:/path/to/ISCC.exe'` and `-InstallerName 'LENA-Setup'`. The installer is written to the repository's `Installer/` folder and installs to `%LOCALAPPDATA%\Programs\LENA`.

Builds require the three prepared offline models. The build checks them, regenerates third-party notices, and includes the UI assets, fonts and licenses.

## Tests

These regression tests use isolated temporary data and small mocked model fixtures; no model downloads are required:

```powershell
& ./.venv/Scripts/python.exe -m unittest discover -s tests -v
```

For a manual smoke check, launch LENA and verify background removal, 2× / 4× upscaling, PNG/JPG export, language/theme switching, and Settings. See [MODEL-GUIDE.md](MODEL-GUIDE.md) and [GPU-AUDIT.md](GPU-AUDIT.md) for the current inference policy.

## Source organization

- `lena_app.py`: application entry point and worker dispatch.
- `lena_custom.py`, `lena_design.py`, `lena_redesign.py`: current interface and panels.
- `lena_worker.py`, `lena_hair.py`, `lena_upscale.py`, `lena_refine.py`: inference and output processing.
- `lena_models.py`, `lena_downloads.py`, `assets/models.json`: model availability and verified downloads.
- `assets/`: the app's icons, fonts, loading frames and model manifest.
- `tests/`: regression checks for quality selection, caching, download integrity and refinement inputs.

Legacy app variants, local audit captures, generated builds and private development environments are not part of this source tree. Windows is the supported build target for this release.
