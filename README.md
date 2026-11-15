# End-to-End_AI_for_Bone_Marrow_Smear_Based_Leukemia_Diagnostics
Project with Helmholz and TUM as a part of the Computational Method for Single Cell Biology

## Setup

The project requires Python 3.11 or newer and uses `uv` to create the virtual
environment and install dependencies. The `wsi2sc` pipeline is included as a Git
submodule and installed in editable mode from `third_party/wsi2sc`. You need
GitHub access to that repository before initializing the submodule.

For a fresh clone, include all submodules:

```powershell
git clone --recurse-submodules https://github.com/GAL1LAO/leukemia_diagnostics.git
Set-Location leukemia_diagnostics
```

If the repository is already cloned, initialize or update the submodule instead:

```powershell
git submodule update --init --recursive
```

Install `uv`, then create `.venv` and synchronize all project, third-party, and
development dependencies declared in `pyproject.toml`:

```powershell
py -m pip install uv
py -m uv sync --locked
```

Verify that the third-party package is available:

```powershell
.\.venv\Scripts\python.exe -c "import wsi2sc; print(wsi2sc.__version__)"
```

To run the project notebooks in VS Code, open a notebook and select the Python
interpreter under `.venv` as its kernel.

[`notebooks/wsi2sc_core_functions.ipynb`](notebooks/wsi2sc_core_functions.ipynb)
documents the submodule's core configuration, reader, sampling, factory, and
pipeline APIs with guarded examples for the local DICOM slide.

After changing `pyproject.toml` or updating the submodule, regenerate and apply
the lockfile with `py -m uv lock` followed by `py -m uv sync`. Commit the updated
`uv.lock` whenever dependency resolution changes.

## Downloading the data

The DICOM data is not stored in this repository. Download the image and
annotation series from the original **Bone Marrow WSI – Pediatric Leukemia**
dataset using the identifiers below, and place the series under
`_data/bonemarrowwsi_pediatricleukemia/A6BBC91AE73DD21C0533F735470A9CD0/`.

| Identifier | Value |
| --- | --- |
| Patient ID | `A6BBC91AE73DD21C0533F735470A9CD0` |
| StudyInstanceUID | `1.2.826.0.1.3680043.8.498.59505406792209197618128317514282530941` |
| WSI SeriesInstanceUID | `1.2.826.0.1.3680043.8.498.63168619527270722340105054684865144558` |
| Consensus annotation SeriesInstanceUID | `1.2.826.0.1.3680043.10.511.3.14336815145959892627830061814418131` |
| Annotation session 0 SeriesInstanceUID | `1.2.826.0.1.3680043.10.511.3.79470360671595439788727812397221468` |
| Annotation session 1 SeriesInstanceUID | `1.2.826.0.1.3680043.10.511.3.80443019300040425367918921699554272` |
| Annotation session 3 SeriesInstanceUID | `1.2.826.0.1.3680043.10.511.3.24193110408419274872952557978659298` |
| Annotation session 4 SeriesInstanceUID | `1.2.826.0.1.3680043.10.511.3.95468493484132104867495199664240499` |
| Monolayer ROI SeriesInstanceUID | `1.2.826.0.1.3680043.10.511.3.86657604656478666358399584064332136` |

The SeriesInstanceUID values are the preferred identifiers for retrieving the
exact image and annotation series; the Patient ID alone may refer to multiple
studies or slides.

## Interactive annotation viewer

Install the optional viewer dependencies:

```powershell
.\.venv\Scripts\python.exe -m uv sync --extra viewer
```

Then open the WSI with its DICOM ANN overlays:

```powershell
.\.venv\Scripts\python.exe annotation_classification\visualize_annotations.py
```

The viewer reads image tiles lazily as you pan and zoom and initially focuses on
the first monolayer ROI. Press `N` to move to the next ROI and `O` to return to
the whole-slide overview. Consensus cell labels and both ROI outlines are
visible initially. Individual annotation sessions are loaded as hidden layers
and can be shown from napari's layer list. Use the mouse wheel to zoom and drag
the canvas to pan. Select an annotation layer and enable its text control to
display the cell-type labels. Pass `--wsi` and `--annotations` to view a
different DICOM WSI directory and ANN file or directory. DICOM ANN files contain
vector coordinates rather than image pixels and should not be opened as image
layers directly.

To overlay the quality-passing crop regions from a pipeline run as thick black
rectangles, pass its cells CSV:

```powershell
.\.venv\Scripts\python.exe annotation_classification\visualize_annotations.py `
    --cells-csv outputs\wsi2sc\MS_cells.csv
```

The crop size is read from the adjacent `MS_profile.json`. If the profile is not
available, provide the level-0 size explicitly, for example `--crop-size 192`.

## Code quality

The setup procedure installs the development tools into `.venv`. To synchronize
them again, run:

```powershell
py -m uv sync --locked
```

Run the same checks used in CI:

```powershell
.\.venv\Scripts\python.exe -m ruff check .
.\.venv\Scripts\python.exe -m ruff format --check .
```

Apply safe lint fixes and formatting:

```powershell
.\.venv\Scripts\python.exe -m ruff check --fix .
.\.venv\Scripts\python.exe -m ruff format .
```

### Git hooks

The hook configuration is stored in `.pre-commit-config.yaml`, but Git hooks
themselves are local and are not included when cloning the repository. After a
fresh clone and `py -m uv sync --locked`, register the hooks once:

```powershell
.\.venv\Scripts\python.exe -m pre_commit install
```

Verify the installation by running every hook against the repository:

```powershell
.\.venv\Scripts\python.exe -m pre_commit run --all-files
```

The hooks now run automatically on `git commit`. They fix lint issues and format
staged Python files. If a hook changes a file, review it, stage it again with
`git add`, and repeat the commit. To remove the local hooks, run:

```powershell
.\.venv\Scripts\python.exe -m pre_commit uninstall
```

GitHub Actions independently checks every push and pull request without modifying
files.
