import tempfile
import unittest
from pathlib import Path

from tools.prepare_labcoat_dataset import prepare_dataset


class PrepareLabcoatDatasetTests(unittest.TestCase):
    def _create_dataset(self, root: Path) -> None:
        root.mkdir(parents=True)
        (root / "data.yaml").write_text(
            "nc: 2\n"
            "names: ['person_with_labcoat', 'person_without_labcoat']\n",
            encoding="utf-8",
        )
        for split in ("train", "valid", "test"):
            (root / split / "images").mkdir(parents=True)
            (root / split / "labels").mkdir(parents=True)
            (root / split / "images" / "sample.rf.hash.jpg").write_bytes(b"image")
            (root / split / "labels" / "sample.rf.hash.txt").write_text(
                "0 0.1 0.2 0.4 0.2 0.4 0.8 0.1 0.8\n",
                encoding="utf-8",
            )

    def test_converts_segmentation_polygon_to_detection_box(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            source = root / "source"
            destination = root / "prepared"
            self._create_dataset(source)

            summary = prepare_dataset(source, destination)

            self.assertEqual(summary, {"train": 1, "valid": 1, "test": 1})
            label = (
                destination / "train" / "labels" / "sample.rf.hash.txt"
            ).read_text(encoding="utf-8")
            self.assertEqual(label, "0 0.25 0.5 0.3 0.6\n")
            self.assertTrue(
                (
                    destination
                    / "train"
                    / "images"
                    / "sample.rf.hash.jpg"
                ).is_file()
            )
            self.assertIn(
                "names: ['person_with_labcoat', 'person_without_labcoat']",
                (destination / "data.yaml").read_text(encoding="utf-8"),
            )
            self.assertIn(
                f"path: {destination.resolve().as_posix()}",
                (destination / "data.yaml").read_text(encoding="utf-8"),
            )

    def test_preserves_empty_labels_for_negative_images(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            source = root / "source"
            destination = root / "prepared"
            self._create_dataset(source)
            (source / "test" / "labels" / "sample.rf.hash.txt").write_text(
                "", encoding="utf-8"
            )

            prepare_dataset(source, destination)

            self.assertEqual(
                (
                    destination / "test" / "labels" / "sample.rf.hash.txt"
                ).read_text(
                    encoding="utf-8"
                ),
                "",
            )

    def test_rejects_mismatched_classes(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            source = root / "source"
            destination = root / "prepared"
            self._create_dataset(source)
            (source / "data.yaml").write_text(
                "nc: 2\nnames: ['person', 'lab_coat']\n",
                encoding="utf-8",
            )

            with self.assertRaisesRegex(ValueError, "Classes inesperadas"):
                prepare_dataset(source, destination)
            self.assertFalse(destination.exists())

    def test_rejects_label_coordinates_outside_normalized_range(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            source = root / "source"
            destination = root / "prepared"
            self._create_dataset(source)
            (source / "train" / "labels" / "sample.rf.hash.txt").write_text(
                "0 0.1 0.2 1.4 0.2 0.4 0.8 0.1 0.8\n",
                encoding="utf-8",
            )

            with self.assertRaisesRegex(ValueError, "Coordenadas inválidas"):
                prepare_dataset(source, destination)
            self.assertFalse(destination.exists())

    def test_rejects_non_finite_coordinates(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            source = root / "source"
            destination = root / "prepared"
            self._create_dataset(source)
            (source / "train" / "labels" / "sample.rf.hash.txt").write_text(
                "0 0.1 0.2 nan 0.2 0.4 0.8 0.1 0.8\n",
                encoding="utf-8",
            )

            with self.assertRaisesRegex(ValueError, "Coordenadas inválidas"):
                prepare_dataset(source, destination)
            self.assertFalse(destination.exists())

    def test_does_not_overwrite_existing_destination(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            source = root / "source"
            destination = root / "prepared"
            self._create_dataset(source)
            destination.mkdir()

            with self.assertRaises(FileExistsError):
                prepare_dataset(source, destination)


if __name__ == "__main__":
    unittest.main()
