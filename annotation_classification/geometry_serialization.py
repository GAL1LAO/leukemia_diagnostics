"""Extract reusable level-0 rectangle geometry from DICOM ANN and CSV files.

All rectangle vertices use canonical ``(x, y)`` coordinate order. Display
adapters are responsible for converting to their required coordinate order.
"""

from __future__ import annotations

import csv
import json
from dataclasses import dataclass
from pathlib import Path

import numpy as np
import pydicom


@dataclass(frozen=True)
class DicomAnnotationRectangles:
    """Rectangle geometry and labels extracted from one DICOM ANN instance."""

    name: str
    rectangles_xy: list[np.ndarray]
    labels: list[str]
    code_meanings: list[str]
    source: str


@dataclass(frozen=True)
class QualityPassCropRectangles:
    """Quality-passing crop geometry and metadata extracted from a cells CSV."""

    rectangles_xy: list[np.ndarray]
    cell_ids: list[int]
    x_coordinates: list[int]
    y_coordinates: list[int]
    p_trash: list[float]
    crop_size: int


def _point_coordinate_dtype(dataset: pydicom.Dataset, keyword: str) -> np.dtype:
    item_size = 8 if keyword == "DoublePointCoordinatesData" else 4
    is_little_endian = dataset.file_meta.TransferSyntaxUID.is_little_endian
    byte_order = "<" if is_little_endian else ">"
    return np.dtype(f"{byte_order}f{item_size}")


def _code_meaning(group: pydicom.Dataset) -> str:
    sequence = getattr(group, "AnnotationPropertyTypeCodeSequence", [])
    if not sequence:
        return ""
    return str(getattr(sequence[0], "CodeMeaning", ""))


def load_dicom_annotation_rectangles(
    path: str | Path,
) -> DicomAnnotationRectangles:
    """Extract rectangles and labels from a 2-D DICOM ANN file.

    The returned rectangle vertices remain in DICOM's level-0 ``(x, y)``
    coordinate order and therefore have no dependency on a viewer library.
    """

    annotation_path = Path(path)
    dataset = pydicom.dcmread(annotation_path, force=True)
    coordinate_type = str(getattr(dataset, "AnnotationCoordinateType", ""))
    if coordinate_type != "2D":
        raise ValueError(
            f"{annotation_path.name} uses unsupported coordinate type "
            f"{coordinate_type!r}; expected '2D'."
        )

    rectangles_xy: list[np.ndarray] = []
    labels: list[str] = []
    code_meanings: list[str] = []

    for group in getattr(dataset, "AnnotationGroupSequence", []):
        graphic_type = str(getattr(group, "GraphicType", ""))
        if graphic_type != "RECTANGLE":
            raise ValueError(
                f"Annotation group {getattr(group, 'AnnotationGroupNumber', '?')} "
                f"uses unsupported GraphicType {graphic_type!r}."
            )

        coordinate_keyword = (
            "DoublePointCoordinatesData"
            if hasattr(group, "DoublePointCoordinatesData")
            else "PointCoordinatesData"
        )
        if not hasattr(group, coordinate_keyword):
            raise ValueError("A rectangle annotation group has no coordinate data.")

        number_of_annotations = int(group.NumberOfAnnotations)
        coordinates = np.frombuffer(
            getattr(group, coordinate_keyword),
            dtype=_point_coordinate_dtype(dataset, coordinate_keyword),
        )
        expected_values = number_of_annotations * 4 * 2
        if coordinates.size != expected_values:
            raise ValueError(
                f"Expected {expected_values} coordinate values for "
                f"{number_of_annotations} rectangles, found {coordinates.size}."
            )

        label = str(getattr(group, "AnnotationGroupLabel", "unlabelled"))
        meaning = _code_meaning(group)
        for points_xy in coordinates.reshape(number_of_annotations, 4, 2):
            rectangles_xy.append(points_xy.copy())
            labels.append(label)
            code_meanings.append(meaning)

    name = str(getattr(dataset, "SeriesDescription", annotation_path.stem))
    return DicomAnnotationRectangles(
        name=name,
        rectangles_xy=rectangles_xy,
        labels=labels,
        code_meanings=code_meanings,
        source=annotation_path.name,
    )


def _crop_size_from_profile(cells_csv_path: Path) -> int | None:
    stem = cells_csv_path.stem
    slide_stem = stem[: -len("_cells")] if stem.endswith("_cells") else stem
    profile_path = cells_csv_path.with_name(f"{slide_stem}_profile.json")
    if not profile_path.is_file():
        return None

    with profile_path.open(encoding="utf-8") as profile_file:
        profile = json.load(profile_file)
    value = profile.get("metadata", {}).get("cell_processing.read_patch_size_level0")
    if value is None:
        return None
    return int(value)


def load_quality_pass_crop_rectangles(
    path: str | Path,
    *,
    crop_size: int | None = None,
) -> QualityPassCropRectangles:
    """Extract level-0 crop rectangles for rows with ``quality_pass=true``."""

    cells_csv_path = Path(path)
    if not cells_csv_path.is_file():
        raise FileNotFoundError(f"Cells CSV does not exist: {cells_csv_path}")

    resolved_crop_size = (
        crop_size if crop_size is not None else _crop_size_from_profile(cells_csv_path)
    )
    if resolved_crop_size is None:
        raise ValueError(
            "Could not determine the level-0 crop size. Keep the pipeline's "
            "*_profile.json next to the cells CSV or provide crop_size."
        )
    if resolved_crop_size <= 0:
        raise ValueError("Crop size must be greater than zero.")

    rectangles_xy: list[np.ndarray] = []
    cell_ids: list[int] = []
    x_coordinates: list[int] = []
    y_coordinates: list[int] = []
    p_trash_values: list[float] = []
    half = resolved_crop_size // 2

    with cells_csv_path.open(newline="", encoding="utf-8") as csv_file:
        reader = csv.DictReader(csv_file)
        required_columns = {"cell_id", "x", "y", "quality_pass"}
        missing = required_columns.difference(reader.fieldnames or [])
        if missing:
            raise ValueError(
                f"{cells_csv_path.name} is missing required column(s): "
                f"{', '.join(sorted(missing))}."
            )

        for row_number, row in enumerate(reader, start=2):
            quality_pass = str(row["quality_pass"]).strip().casefold()
            if quality_pass in {"false", "0", "no"}:
                continue
            if quality_pass not in {"true", "1", "yes"}:
                raise ValueError(
                    f"Invalid quality_pass value {row['quality_pass']!r} at "
                    f"CSV row {row_number}."
                )

            cell_id = int(row["cell_id"])
            x = int(row["x"])
            y = int(row["y"])
            x0 = x - half
            y0 = y - half
            x1 = x0 + resolved_crop_size
            y1 = y0 + resolved_crop_size
            rectangles_xy.append(
                np.asarray(
                    [[x0, y0], [x1, y0], [x1, y1], [x0, y1]],
                    dtype=np.float32,
                )
            )
            cell_ids.append(cell_id)
            x_coordinates.append(x)
            y_coordinates.append(y)
            p_trash_values.append(float(row.get("p_trash") or "nan"))

    return QualityPassCropRectangles(
        rectangles_xy=rectangles_xy,
        cell_ids=cell_ids,
        x_coordinates=x_coordinates,
        y_coordinates=y_coordinates,
        p_trash=p_trash_values,
        crop_size=resolved_crop_size,
    )
