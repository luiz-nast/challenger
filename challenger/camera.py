"""Câmera: diz se é humano olhando. Tudo na memória; nenhum quadro vai para disco.

| Leitura    | Conta? | Por quê                                  |
|------------|--------|------------------------------------------|
| voce       | sim    | rosto na imagem                          |
| tapada     | sim    | imagem escura ou quase uniforme: burla   |
| erro       | sim    | câmera desligada, ocupada ou sem OpenCV  |
| vazia      | não    | imagem normal sem rosto: agente sozinho  |

Antes da primeira decisão o estado é "desconhecido", que conta (falha fechada).
"""

from __future__ import annotations

import logging
import time
from pathlib import Path

log = logging.getLogger("challenger")
MODEL = Path(__file__).with_name("face_detection_yunet_2023mar.onnx")
COUNTS = {"voce", "tapada", "erro", "desconhecido"}  # só "vazia" não conta
LABELS = {"voce": "você", "tapada": "câmera tapada", "erro": "sem câmera", "vazia": "sala vazia",
          "desconhecido": "olhando…", "repouso": "câmera em repouso"}
WARMUP_SECONDS = 2.0  # a exposição automática começa escura (medido: ~1,5 s)
IDLE_CLOSE_SECONDS = 10
RETRY_SECONDS = 5


def classify(frame, faces: int, dark_mean: float = 35, dark_std: float = 10) -> str:
    """Leitura de um quadro (array numpy) já passado pelo detector de rosto."""
    if frame is None:
        return "erro"
    if faces:
        return "voce"
    gray = frame.mean(axis=2) if frame.ndim == 3 else frame
    return "tapada" if gray.mean() < dark_mean or gray.std() < dark_std else "vazia"


class Smoother:
    """O estado só muda depois de `n` leituras seguidas iguais: evita oscilar."""

    def __init__(self, n: int = 3) -> None:
        self.n, self.state, self._last, self._run = max(1, n), "desconhecido", None, 0

    def push(self, reading: str) -> str:
        self._run = self._run + 1 if reading == self._last else 1
        self._last = reading
        if self._run >= self.n:
            self.state = reading
        return self.state

    def reset(self) -> None:
        self.state, self._last, self._run = "desconhecido", None, 0


class Camera:
    """Câmera de verdade (OpenCV, V4L2). Abre quando alguém pede leitura e fecha sozinha
    `IDLE_CLOSE_SECONDS` depois do último pedido."""

    def __init__(self, cfg: dict | None = None, device: int = 0) -> None:
        cfg = cfg or {}
        self.dark_mean, self.dark_std = cfg.get("dark_mean", 35), cfg.get("dark_std", 10)
        self.face_score = cfg.get("face_score", 0.6)
        self.smoother = Smoother(cfg.get("smoothing", 3))
        self.device, self._cap, self._detector = device, None, None
        self._opened_at = self._last_use = self._failed_at = 0.0

    @property
    def is_open(self) -> bool:
        return self._cap is not None

    def _open(self) -> bool:
        if time.monotonic() - self._failed_at < RETRY_SECONDS:
            return False
        try:
            import cv2

            cap = cv2.VideoCapture(self.device, cv2.CAP_V4L2)
            if not cap.isOpened():
                raise OSError("câmera não abriu")
            cap.set(cv2.CAP_PROP_FRAME_WIDTH, 320)
            cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 240)
            cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)  # sem quadro velho na fila
            size = (int(cap.get(cv2.CAP_PROP_FRAME_WIDTH)), int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT)))
            self._detector = cv2.FaceDetectorYN.create(str(MODEL), "", size, self.face_score, 0.3, 50)
        except Exception as e:  # noqa: BLE001 - sem OpenCV, sem câmera, câmera ocupada: tudo é "erro"
            log.warning("Câmera indisponível: %s", e)
            self._failed_at = time.monotonic()
            return False
        self._cap, self._opened_at = cap, time.monotonic()
        log.info("Câmera ligada")
        return True

    def read(self) -> str | None:
        """Leitura crua agora: voce/tapada/vazia/erro, ou None no aquecimento."""
        if not self._cap and not self._open():
            return "erro"
        ok, frame = self._cap.read()
        if not ok:
            self.close()
            self._failed_at = time.monotonic()
            return "erro"
        if time.monotonic() - self._opened_at < WARMUP_SECONDS:
            return None
        if frame.shape[1::-1] != tuple(self._detector.getInputSize()):
            self._detector.setInputSize(frame.shape[1::-1])
        faces = self._detector.detect(frame)[1]
        return classify(frame, 0 if faces is None else len(faces), self.dark_mean, self.dark_std)

    def sample(self) -> str:
        """Estado suavizado para quem está contando; liga a câmera se preciso."""
        self._last_use = time.monotonic()
        reading = self.read()
        return self.smoother.state if reading is None else self.smoother.push(reading)

    def idle(self) -> None:
        """Ninguém precisa da câmera agora: fecha depois de `IDLE_CLOSE_SECONDS`."""
        if self._cap and time.monotonic() - self._last_use > IDLE_CLOSE_SECONDS:
            self.close()

    def close(self) -> None:
        if self._cap:
            self._cap.release()
            log.info("Câmera desligada")
        self._cap = None
        self.smoother.reset()
