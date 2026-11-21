"""Câmera falsa: a tabela do PROMPT (rosto, tapada, erro, sala vazia) e a suavização."""

import sys
import unittest
from unittest import mock

import numpy as np

from challenger import camera
from challenger.camera import COUNTS, Camera, Smoother, classify

rng = np.random.default_rng(7)
ROOM = rng.integers(0, 255, (240, 320, 3), dtype=np.uint8)  # sala iluminada, com textura
BLACK = np.zeros((240, 320, 3), dtype=np.uint8)  # lente tapada
DIM = np.full((240, 320, 3), 20, dtype=np.uint8)  # muito escura
FLAT = np.full((240, 320, 3), 128, dtype=np.uint8)  # dedo/papel na frente: uniforme


class ClassifyTest(unittest.TestCase):
    def test_table(self):
        self.assertEqual(classify(ROOM, faces=1), "voce")
        self.assertEqual(classify(ROOM, faces=0), "vazia")
        self.assertEqual(classify(BLACK, faces=0), "tapada")
        self.assertEqual(classify(DIM, faces=0), "tapada")
        self.assertEqual(classify(FLAT, faces=0), "tapada")
        self.assertEqual(classify(None, faces=0), "erro")
        self.assertEqual(classify(DIM, faces=1), "voce")  # rosto vence o escuro

    def test_what_counts(self):
        self.assertEqual({s for s in ("voce", "tapada", "erro", "vazia", "desconhecido") if s in COUNTS},
                         {"voce", "tapada", "erro", "desconhecido"})

    def test_thresholds_are_configurable(self):
        self.assertEqual(classify(DIM, 0, dark_mean=10, dark_std=0), "vazia")
        self.assertEqual(classify(ROOM, 0, dark_mean=200), "tapada")


class SmootherTest(unittest.TestCase):
    def test_starts_unknown_and_counts(self):
        self.assertIn(Smoother(3).state, COUNTS)

    def test_changes_only_after_n_equal_readings(self):
        s = Smoother(3)
        self.assertEqual([s.push(r) for r in ("vazia", "vazia", "vazia")], ["desconhecido", "desconhecido", "vazia"])
        self.assertEqual([s.push(r) for r in ("voce", "voce", "voce")], ["vazia", "vazia", "voce"])

    def test_flicker_does_not_flip(self):
        s = Smoother(3)
        for _ in range(3):
            s.push("voce")
        for r in ("vazia", "voce", "vazia", "vazia", "voce", "vazia", "tapada", "vazia", "vazia"):
            self.assertEqual(s.push(r), "voce", r)
        self.assertEqual(s.push("vazia"), "vazia")

    def test_reset(self):
        s = Smoother(1)
        s.push("vazia")
        s.reset()
        self.assertEqual(s.state, "desconhecido")


class FakeCap:
    def __init__(self, frames, opened=True):
        self.frames, self.opened, self.released = list(frames), opened, False

    def isOpened(self):
        return self.opened

    def set(self, *_):
        return True

    def get(self, prop):
        return {3: 320, 4: 240}.get(prop, 0)

    def grab(self):
        return True

    def read(self):
        return (True, self.frames.pop(0)) if self.frames else (False, None)

    def release(self):
        self.released = True


class FakeDetector:
    def __init__(self, faces):
        self.faces = faces

    def getInputSize(self):
        return (320, 240)

    def setInputSize(self, size):
        pass

    def detect(self, frame):
        return 1, (np.zeros((self.faces, 15)) if self.faces else None)


def fake_cv2(cap, faces=0):
    return mock.Mock(VideoCapture=lambda *a: cap, CAP_V4L2=200, CAP_PROP_FRAME_WIDTH=3, CAP_PROP_FRAME_HEIGHT=4,
                     CAP_PROP_BUFFERSIZE=38, FaceDetectorYN=mock.Mock(create=lambda *a: FakeDetector(faces)))


class CameraTest(unittest.TestCase):
    def setUp(self):
        patcher = mock.patch.object(camera, "WARMUP_SECONDS", 0)
        patcher.start()
        self.addCleanup(patcher.stop)

    def sample(self, cv2, n=3):
        cam = Camera({"smoothing": 3})
        with mock.patch.dict(sys.modules, {"cv2": cv2}):
            states = [cam.sample() for _ in range(n)]
        return cam, states

    def test_face_counts(self):
        cam, states = self.sample(fake_cv2(FakeCap([ROOM] * 3), faces=1))
        self.assertEqual(states[-1], "voce")
        # nenhum quadro fica guardado no objeto depois da leitura
        self.assertFalse([v for v in vars(cam).values() if isinstance(v, np.ndarray)])

    def test_empty_room_does_not_count(self):
        _, states = self.sample(fake_cv2(FakeCap([ROOM] * 3)))
        self.assertEqual(states[-1], "vazia")
        self.assertNotIn("vazia", COUNTS)

    def test_covered_counts(self):
        _, states = self.sample(fake_cv2(FakeCap([BLACK] * 3)))
        self.assertEqual(states[-1], "tapada")

    def test_camera_off_or_busy_counts(self):
        _, states = self.sample(fake_cv2(FakeCap([], opened=False)))
        self.assertEqual(states, ["desconhecido", "desconhecido", "erro"])

    def test_no_opencv_counts(self):
        cam = Camera()
        with mock.patch.dict(sys.modules, {"cv2": None}):  # import cv2 falha
            states = [cam.sample() for _ in range(3)]
        self.assertEqual(states[-1], "erro")

    def test_camera_stops_mid_way_counts(self):
        cap = FakeCap([ROOM] * 3)
        cam, states = self.sample(fake_cv2(cap), n=3)
        self.assertEqual(states[-1], "vazia")
        with mock.patch.object(camera, "RETRY_SECONDS", 0), mock.patch.dict(sys.modules, {"cv2": fake_cv2(FakeCap([], opened=False))}):
            states = [cam.sample() for _ in range(3)]  # quadros acabaram: câmera caiu
        self.assertTrue(cap.released)
        self.assertEqual(states[-1], "erro")

    def test_error_with_camera_open_counts_and_turns_it_off(self):
        """Detector que quebra com a câmera já aberta: "erro" (conta) e a câmera desliga."""
        class Broken(FakeDetector):
            def detect(self, frame):
                raise RuntimeError("cv2.error")

        cap = FakeCap([ROOM] * 5)
        cv2 = fake_cv2(cap)
        cv2.FaceDetectorYN = mock.Mock(create=lambda *a: Broken(0))
        cam, states = self.sample(cv2, n=3)
        self.assertEqual(states[-1], "erro")
        self.assertIn(states[-1], COUNTS)
        self.assertTrue(cap.released)
        self.assertFalse(cam.is_open)

    def test_real_missing_device_is_error(self):
        """Câmera de verdade num dispositivo que não existe: erro, que conta."""
        cam = Camera({"smoothing": 1}, device=97)
        self.assertEqual(cam.sample(), "erro")
        cam.close()

    def test_closes_after_idle_and_forgets_state(self):
        cap = FakeCap([ROOM] * 3)
        cam, _ = self.sample(fake_cv2(cap))
        with mock.patch.object(camera, "IDLE_CLOSE_SECONDS", -1):
            cam.idle()
        self.assertTrue(cap.released)
        self.assertFalse(cam.is_open)
        self.assertEqual(cam.smoother.state, "desconhecido")

    def test_warmup_frames_are_ignored(self):
        with mock.patch.object(camera, "WARMUP_SECONDS", 60):
            _, states = self.sample(fake_cv2(FakeCap([ROOM] * 5)), n=5)
        self.assertEqual(set(states), {"desconhecido"})


if __name__ == "__main__":
    unittest.main()
