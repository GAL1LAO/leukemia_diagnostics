# End-to-End_AI_for_Bone_Marrow_Smear_Based_Leukemia_Diagnostics
Project with Helmholz and TUM as a part of the Computational Method for Single Cell Biology

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

## Code quality

Install the development tools in the virtual environment:

```powershell
.\.venv\Scripts\python.exe -m pip install -r requirements-dev.txt
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
fresh clone, install the development tools and register the hooks once:

```powershell
.\.venv\Scripts\python.exe -m pip install -r requirements-dev.txt
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
