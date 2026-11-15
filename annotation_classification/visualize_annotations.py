"""Interactive, zoomable visualization of DICOM ANN annotations on a WSI.

The WSI is exposed to napari as a lazy Dask pyramid. Only image tiles needed
for the current view are decoded; the level-0 image is never loaded in full.
"""

from __future__ import annotations

import argparse
import colorsys
import hashlib
import threading
from collections.abc import Sequence
from pathlib import Path
from typing import TYPE_CHECKING, Any

import numpy as np
from wsidicom import WsiDicom

if __package__:
    from .geometry_serialization import (
        load_dicom_annotation_rectangles,
        load_quality_pass_crop_rectangles,
    )
else:
    from geometry_serialization import (
        load_dicom_annotation_rectangles,
        load_quality_pass_crop_rectangles,
    )

if TYPE_CHECKING:
    import napari


REPO_ROOT = Path(__file__).resolve().parents[1]
PATIENT_DIR = (
    REPO_ROOT
    / "_data"
    / "bonemarrowwsi_pediatricleukemia"
    / "A6BBC91AE73DD21C0533F735470A9CD0"
)
DEFAULT_WSI_DIR = PATIENT_DIR / "MS"
DEFAULT_ANNOTATION_DIR = PATIENT_DIR / "ANN"


class _WsiLevelArray:
    """Minimal array interface used by Dask to read one WSI pyramid level."""

    def __init__(
        self,
        slide: WsiDicom,
        level: int,
        width: int,
        height: int,
        read_lock: threading.Lock,
    ) -> None:
        self._slide = slide
        self._level = level
        self._read_lock = read_lock
        self.shape = (height, width, 3)
        self.ndim = 3
        self.dtype = np.dtype(np.uint8)

    def __getitem__(self, key: tuple[slice, slice, slice]) -> np.ndarray:
        if not isinstance(key, tuple) or len(key) != 3:
            raise IndexError("The WSI array expects (row, column, channel) slices.")

        row_slice, column_slice, channel_slice = key
        if not all(isinstance(item, slice) for item in key):
            raise IndexError("Only slice-based WSI reads are supported.")

        y_start, y_stop, y_step = row_slice.indices(self.shape[0])
        x_start, x_stop, x_step = column_slice.indices(self.shape[1])
        if y_stop <= y_start or x_stop <= x_start:
            return np.empty((0, 0, 3), dtype=self.dtype)[..., channel_slice]

        with self._read_lock:
            image = self._slide.read_region(
                (x_start, y_start),
                self._level,
                (x_stop - x_start, y_stop - y_start),
                threads=4,
                as_array=True,
            )

        array = np.asarray(image, dtype=self.dtype)
        return array[::y_step, ::x_step, channel_slice]


def _label_color(label: str) -> tuple[float, float, float, float]:
    """Return a stable, high-contrast color for an annotation label."""

    digest = hashlib.sha256(label.encode("utf-8")).digest()
    hue = int.from_bytes(digest[:2], "big") / 65535
    red, green, blue = colorsys.hsv_to_rgb(hue, 0.85, 1.0)
    return red, green, blue, 1.0


def _to_napari_rectangles(
    rectangles_xy: Sequence[np.ndarray],
) -> list[np.ndarray]:
    """Convert canonical ``(x, y)`` vertices to napari ``(row, column)``."""

    return [rectangle[:, ::-1].copy() for rectangle in rectangles_xy]


def _open_wsi(wsi_path: str | Path) -> WsiDicom:
    path = Path(wsi_path)
    if path.is_dir():
        files = sorted(path.glob("*.dcm"))
        if not files:
            raise FileNotFoundError(f"No DICOM files found in {path}.")
        return WsiDicom.open(files)
    if not path.is_file():
        raise FileNotFoundError(f"WSI path does not exist: {path}")
    return WsiDicom.open(path)


def build_lazy_wsi_pyramid(
    slide: WsiDicom,
    *,
    chunk_size: int = 1024,
) -> list[Any]:
    """Create lazy Dask arrays for every available WSI pyramid level."""

    try:
        import dask.array as da
    except ImportError as exc:
        raise RuntimeError(
            "The interactive viewer dependencies are missing. Run "
            "`.\\.venv\\Scripts\\python.exe -m uv sync --extra viewer`."
        ) from exc

    read_lock = threading.Lock()
    pyramid: list[Any] = []
    for level in slide.levels:
        array = _WsiLevelArray(
            slide=slide,
            level=int(level.level),
            width=int(level.size.width),
            height=int(level.size.height),
            read_lock=read_lock,
        )
        pyramid.append(
            da.from_array(
                array,
                chunks=(chunk_size, chunk_size, 3),
                asarray=False,
                fancy=False,
                name=f"wsidicom-{id(slide)}-level-{level.level}",
            )
        )
    return pyramid


def _annotation_files(annotation_path: str | Path) -> list[Path]:
    path = Path(annotation_path)
    if path.is_file():
        return [path]
    if not path.is_dir():
        raise FileNotFoundError(f"Annotation path does not exist: {path}")
    files = sorted(path.glob("*.dcm"))
    if not files:
        raise FileNotFoundError(f"No DICOM ANN files found in {path}.")
    return files


def create_annotation_viewer(
    wsi_path: str | Path = DEFAULT_WSI_DIR,
    annotation_path: str | Path = DEFAULT_ANNOTATION_DIR,
    cells_csv_path: str | Path | None = None,
    *,
    crop_size: int | None = None,
) -> tuple[napari.Viewer, WsiDicom]:
    """Build a napari viewer with a lazy WSI and toggleable ANN layers.

    The caller owns the returned ``WsiDicom`` object and should close it after
    the napari event loop exits. Use :func:`view_annotations` for the common
    blocking interface that handles this automatically.
    """

    try:
        import napari
    except ImportError as exc:
        raise RuntimeError(
            "The interactive viewer dependencies are missing. Run "
            "`.\\.venv\\Scripts\\python.exe -m uv sync --extra viewer`."
        ) from exc

    slide = _open_wsi(wsi_path)
    try:
        pyramid = build_lazy_wsi_pyramid(slide)
        viewer = napari.Viewer(title="WSI annotation viewer")
        viewer.add_image(
            pyramid,
            name="Whole-slide image",
            multiscale=True,
            rgb=True,
        )

        roi_layers: list[Any] = []
        for annotation_file in _annotation_files(annotation_path):
            annotations = load_dicom_annotation_rectangles(annotation_file)
            rectangles = _to_napari_rectangles(annotations.rectangles_xy)
            if not rectangles:
                continue

            is_consensus = "consensus" in annotations.name.lower()
            is_roi = "region" in annotations.name.lower()

            if is_roi:
                for index, rectangle in enumerate(rectangles, start=1):
                    layer = viewer.add_shapes(
                        [rectangle],
                        shape_type="rectangle",
                        name=f"Monolayer ROI {index}",
                        properties={
                            "label": [annotations.labels[index - 1]],
                            "code_meaning": [annotations.code_meanings[index - 1]],
                            "source": [annotations.source],
                        },
                        edge_color="yellow",
                        edge_width=20,
                        face_color="transparent",
                    )
                    roi_layers.append(layer)
                continue

            viewer.add_shapes(
                rectangles,
                shape_type="rectangle",
                name=annotations.name,
                properties={
                    "label": annotations.labels,
                    "code_meaning": annotations.code_meanings,
                    "source": [annotations.source] * len(annotations.labels),
                },
                edge_color=[_label_color(label) for label in annotations.labels],
                edge_width=3,
                face_color="transparent",
                text={
                    "string": "{label}",
                    "size": 10,
                    "color": "white",
                    "visible": False,
                },
                visible=is_consensus or is_roi,
            )

        if cells_csv_path is not None:
            crops = load_quality_pass_crop_rectangles(
                cells_csv_path,
                crop_size=crop_size,
            )
            rectangles = _to_napari_rectangles(crops.rectangles_xy)
            if rectangles:
                viewer.add_shapes(
                    rectangles,
                    shape_type="rectangle",
                    name="Quality-passing crop regions",
                    properties={
                        "cell_id": crops.cell_ids,
                        "x": crops.x_coordinates,
                        "y": crops.y_coordinates,
                        "p_trash": crops.p_trash,
                        "quality_pass": [True] * len(rectangles),
                        "crop_size": [crops.crop_size] * len(rectangles),
                    },
                    edge_color="black",
                    edge_width=10,
                    face_color="transparent",
                )

        viewer.reset_view()
        if roi_layers:
            roi_state = {"index": 0}

            def focus_roi(index: int) -> None:
                roi_state["index"] = index % len(roi_layers)
                viewer.reset_view(
                    layers=[roi_layers[roi_state["index"]]],
                    margin=0.2,
                )

            def focus_next_roi(_viewer: napari.Viewer) -> None:
                focus_roi(roi_state["index"] + 1)

            def show_overview(_viewer: napari.Viewer) -> None:
                viewer.reset_view()

            viewer.bind_key("n", focus_next_roi, overwrite=True)
            viewer.bind_key("o", show_overview, overwrite=True)
            focus_roi(0)

        return viewer, slide
    except Exception:
        slide.close()
        raise


def view_annotations(
    wsi_path: str | Path = DEFAULT_WSI_DIR,
    annotation_path: str | Path = DEFAULT_ANNOTATION_DIR,
    cells_csv_path: str | Path | None = None,
    *,
    crop_size: int | None = None,
) -> None:
    """Open the interactive WSI viewer and close resources on exit.

    ``cells_csv_path`` is optional. When it is omitted, the WSI and DICOM ANN
    layers are shown normally, without the quality-passing crop overlay.
    """

    try:
        import napari
    except ImportError as exc:
        raise RuntimeError(
            "The interactive viewer dependencies are missing. Run "
            "`.\\.venv\\Scripts\\python.exe -m uv sync --extra viewer`."
        ) from exc

    _, slide = create_annotation_viewer(
        wsi_path,
        annotation_path,
        cells_csv_path,
        crop_size=crop_size,
    )
    try:
        napari.run()
    finally:
        slide.close()


def _parse_args(arguments: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="View DICOM ANN annotations on a zoomable whole-slide image."
    )
    parser.add_argument(
        "--wsi",
        type=Path,
        default=DEFAULT_WSI_DIR,
        help="WSI DICOM file or directory (default: the configured A6BBC MS folder).",
    )
    parser.add_argument(
        "--annotations",
        type=Path,
        default=DEFAULT_ANNOTATION_DIR,
        help="DICOM ANN file or directory (default: the configured A6BBC ANN folder).",
    )
    parser.add_argument(
        "--cells-csv",
        type=Path,
        help=(
            "Optional pipeline cells CSV. Rows with quality_pass=True are shown "
            "as thick black crop rectangles."
        ),
    )
    parser.add_argument(
        "--crop-size",
        type=int,
        help=(
            "Level-0 crop size in pixels. By default it is read from the "
            "companion *_profile.json file."
        ),
    )
    return parser.parse_args(arguments)


if __name__ == "__main__":
    args = _parse_args()
    view_annotations(
        args.wsi,
        args.annotations,
        args.cells_csv,
        crop_size=args.crop_size,
    )
