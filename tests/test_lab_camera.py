import unittest

from app.cameras.lab_camera import LabCameraConfig, LabCamera


class LabCameraTests(unittest.TestCase):
    def test_lab_camera_config_has_correct_defaults(self):
        config = LabCameraConfig(name="lab")
        self.assertEqual(config.role, "laboratory")
        self.assertEqual(config.width, 1280)
        self.assertEqual(config.height, 720)

    def test_lab_camera_container_can_be_created(self):
        camera = LabCamera(LabCameraConfig(name="lab", url="http://example.com/lab"))
        self.assertEqual(camera.name, "lab")
        self.assertEqual(camera.config.role, "laboratory")


if __name__ == "__main__":
    unittest.main()
