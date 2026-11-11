from __future__ import annotations

import argparse
import ast
import re
import shutil
from math import isfinite
from pathlib import Path
from typing import Dict, List, Tuple


EXPECTED_CLASSES = ("person_with_labcoat", "person_without_labcoat")
IMAGE_EXTENSIONS = {".bmp", ".jpeg", ".jpg", ".png", ".webp"}
SPLITS = ("train", "valid", "test")


def _read_dataset_classes(dataset_yaml: Path) -> Tuple[str, ...]:
    content = dataset_yaml.read_text(encoding="utf-8")
    class_match = re.search(r"(?m)^names:\s*(\[[^\r\n]*\])\s*$", content)
    if class_match is None:
        raise ValueError(f"Não foi possível ler a lista de classes: {dataset_yaml}")
    classes = ast.literal_eval(class_match.group(1))
    if not isinstance(classes, list) or not all(
        isinstance(name, str) for name in classes
    ):
        raise ValueError("A lista 'names' do dataset precisa conter nomes de classe.")
    if tuple(classes) != EXPECTED_CLASSES:
        raise ValueError(
            "Classes inesperadas. Esperado, nesta ordem: "
            + ", ".join(EXPECTED_CLASSES)
        )
    return tuple(classes)


def _image_files(directory: Path) -> Dict[Path, Path]:
    files = {}
    for image in directory.rglob("*"):
        if not image.is_file() or image.suffix.lower() not in IMAGE_EXTENSIONS:
            continue
        key = image.relative_to(directory).with_suffix("")
        if key in files:
            raise ValueError(f"Mais de uma imagem corresponde ao rótulo {key}.")
        files[key] = image
    return files


def _label_files(directory: Path) -> Dict[Path, Path]:
    files = {}
    for label in directory.rglob("*.txt"):
        if not label.is_file():
            continue
        key = label.relative_to(directory).with_suffix("")
        if key in files:
            raise ValueError(f"Mais de um rótulo corresponde à imagem {key}.")
        files[key] = label
    return files


def _format_number(value: float) -> str:
    return f"{value:.8f}".rstrip("0").rstrip(".") or "0"


def _convert_label_file(label_path: Path, label_name: str) -> str:
    converted: List[str] = []
    for line_number, raw_line in enumerate(
        label_path.read_text(encoding="utf-8").splitlines(), start=1
    ):
        if not raw_line.strip():
            continue
        parts = raw_line.split()
        try:
            class_id = int(parts[0])
            coordinates = [float(value) for value in parts[1:]]
        except (ValueError, IndexError) as exc:
            raise ValueError(
                f"Rótulo inválido em {label_name}:{line_number}"
            ) from exc

        if class_id not in (0, 1):
            raise ValueError(
                f"Classe fora do intervalo 0..1 em {label_name}:{line_number}"
            )
        if len(coordinates) < 4 or any(
            not isfinite(value) or value < 0.0 or value > 1.0
            for value in coordinates
        ):
            raise ValueError(
                f"Coordenadas inválidas em {label_name}:{line_number}"
            )

        if len(coordinates) == 4:
            center_x, center_y, width, height = coordinates
            if width <= 0.0 or height <= 0.0:
                raise ValueError(
                    f"Caixa sem área em {label_name}:{line_number}"
                )
        else:
            if len(coordinates) < 6 or len(coordinates) % 2:
                raise ValueError(
                    f"Polígono inválido em {label_name}:{line_number}"
                )
            x_coordinates = coordinates[0::2]
            y_coordinates = coordinates[1::2]
            left, right = min(x_coordinates), max(x_coordinates)
            top, bottom = min(y_coordinates), max(y_coordinates)
            width, height = right - left, bottom - top
            if width <= 0.0 or height <= 0.0:
                raise ValueError(
                    f"Polígono sem área em {label_name}:{line_number}"
                )
            center_x = (left + right) / 2.0
            center_y = (top + bottom) / 2.0

        converted.append(
            " ".join(
                (
                    str(class_id),
                    _format_number(center_x),
                    _format_number(center_y),
                    _format_number(width),
                    _format_number(height),
                )
            )
        )
    return "\n".join(converted) + ("\n" if converted else "")


def prepare_dataset(source: Path, destination: Path) -> Dict[str, int]:
    source = source.resolve()
    destination = destination.resolve()
    if destination.exists():
        raise FileExistsError(
            f"Destino já existe; escolha um diretório novo: {destination}"
        )
    _read_dataset_classes(source / "data.yaml")

    prepared_splits: Dict[str, List[Tuple[Path, Path, str]]] = {}
    summary: Dict[str, int] = {}
    for split in SPLITS:
        split_root = source / split
        images = _image_files(split_root / "images")
        labels = _label_files(split_root / "labels")
        if not images:
            raise ValueError(f"Nenhuma imagem encontrada na divisão '{split}'.")
        if set(images) != set(labels):
            missing_labels = sorted(set(images) - set(labels))
            orphan_labels = sorted(set(labels) - set(images))
            raise ValueError(
                f"Imagens/rótulos não correspondem em '{split}': "
                f"{len(missing_labels)} sem rótulo, {len(orphan_labels)} órfãos."
            )

        prepared: List[Tuple[Path, Path, str]] = []
        for relative_path, image_path in images.items():
            label_path = labels[relative_path]
            converted_label = _convert_label_file(
                label_path, str(label_path.relative_to(source))
            )
            prepared.append((relative_path, image_path, converted_label))
        prepared_splits[split] = prepared
        summary[split] = len(prepared)

    destination.mkdir(parents=True)
    for split, files in prepared_splits.items():
        for relative_path, image_path, converted_label in files:
            output_image = destination / split / "images" / relative_path
            output_image = output_image.with_name(
                output_image.name + image_path.suffix.lower()
            )
            output_label = destination / split / "labels" / relative_path.with_name(
                relative_path.name + ".txt"
            )
            output_image.parent.mkdir(parents=True, exist_ok=True)
            output_label.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(image_path, output_image)
            output_label.write_text(converted_label, encoding="utf-8")

    yaml_content = (
        f"path: {destination.as_posix()}\n"
        "train: train/images\n"
        "val: valid/images\n"
        "test: test/images\n\n"
        "nc: 2\n"
        "names: ['person_with_labcoat', 'person_without_labcoat']\n"
    )
    (destination / "data.yaml").write_text(yaml_content, encoding="utf-8")
    return summary


def main() -> None:
    repository_root = Path(__file__).resolve().parents[1]
    parser = argparse.ArgumentParser(
        description="Converte polígonos do dataset de jaleco em caixas YOLO."
    )
    parser.add_argument(
        "--source",
        type=Path,
        default=repository_root / "Lab Coat Detection 3.v12i.yolov8",
        help="Diretório do dataset Roboflow original.",
    )
    parser.add_argument(
        "--destination",
        type=Path,
        default=repository_root / "training" / "generated" / "labcoat-detection",
        help="Novo diretório para o dataset YOLO de detecção.",
    )
    args = parser.parse_args()
    try:
        summary = prepare_dataset(args.source, args.destination)
    except (FileExistsError, FileNotFoundError, ValueError) as exc:
        parser.error(str(exc))

    print(f"Dataset de detecção preparado em: {args.destination.resolve()}")
    for split, count in summary.items():
        print(f"  {split}: {count} imagens")


if __name__ == "__main__":
    main()
