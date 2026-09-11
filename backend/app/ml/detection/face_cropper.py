"""ArcFace 112×112 face cropper built on SCRFD detections."""

from __future__ import annotations

import uuid
from typing import TYPE_CHECKING

import cv2
import numpy as np

from app.ml.detection.types import DetectedFace, FaceCrop
from app.ml.face_preprocess import estimate_norm, norm_crop, preprocess

if TYPE_CHECKING:
    from app.ml.detection.scrfd import SCRFDDetector


class FaceCropper:
    """Crop and align detected faces to 112×112 ArcFace template."""

    OUTPUT_SIZE = 112
    ARCFACE_TEMPLATE = np.array(
        [
            [38.2946, 51.6963],
            [73.5318, 51.5014],
            [56.0252, 71.7366],
            [41.5493, 92.3655],
            [70.7299, 92.2041],
        ],
        dtype=np.float32,
    )

    def __init__(self, detector: SCRFDDetector | None = None) -> None:
        """Create a cropper optionally bound to a shared SCRFD detector."""
        self._detector = detector

    def crop_all(
        self,
        image_bgr: np.ndarray,
        detected_faces: list[DetectedFace],
        source_photo_id: uuid.UUID | None = None,
    ) -> list[FaceCrop]:
        """Crop and align all detected faces.

        Args:
            image_bgr: Source BGR image.
            detected_faces: Faces from ``SCRFDDetector.detect``.
            source_photo_id: Optional originating photo UUID.

        Returns:
            Aligned 112×112 crops for each detection.
        """
        crops: list[FaceCrop] = []
        for face in detected_faces:
            crop = self._crop_single(image_bgr, face, source_photo_id=source_photo_id)
            if crop is not None:
                crops.append(crop)
        return crops

    def crop_primary(
        self,
        image_bgr: np.ndarray,
        detected_faces: list[DetectedFace],
        source_photo_id: uuid.UUID | None = None,
    ) -> FaceCrop | None:
        """Return the single face whose nose landmark is closest to image center.

        Matches pix-workers ``get_all_face_crops(..., get_faces=1)`` behaviour
        used for guest selfie matching.

        Args:
            image_bgr: Source BGR image.
            detected_faces: Faces from ``SCRFDDetector.detect``.
            source_photo_id: Optional originating photo UUID.

        Returns:
            Primary aligned crop, or ``None`` when no faces are provided.
        """
        primary = self.select_primary(image_bgr, detected_faces)
        if primary is None:
            return None
        return self._crop_single(image_bgr, primary, source_photo_id=source_photo_id)

    def select_primary(
        self,
        image_bgr: np.ndarray,
        detected_faces: list[DetectedFace],
    ) -> DetectedFace | None:
        """Choose the face whose nose (or bbox centre) is closest to image centre.

        Args:
            image_bgr: Source BGR image.
            detected_faces: Faces from ``SCRFDDetector.detect``.

        Returns:
            The primary detection, or ``None`` when ``detected_faces`` is empty.
        """
        if not detected_faces:
            return None

        image_center = (image_bgr.shape[1] / 2.0, image_bgr.shape[0] / 2.0)
        best_face = detected_faces[0]
        best_distance = float("inf")
        for face in detected_faces:
            if face.landmarks.shape == (5, 2) and np.any(face.landmarks):
                nose_x, nose_y = face.landmarks[2]
                distance = float(
                    ((nose_x - image_center[0]) ** 2 + (nose_y - image_center[1]) ** 2) ** 0.5
                )
            else:
                x, y, width, height = face.bbox_pixel
                center_x = x + width / 2.0
                center_y = y + height / 2.0
                distance = float(
                    ((center_x - image_center[0]) ** 2 + (center_y - image_center[1]) ** 2) ** 0.5
                )
            if distance < best_distance:
                best_distance = distance
                best_face = face
        return best_face

    def detect_and_crop_all(
        self,
        image_bgr: np.ndarray,
        source_photo_id: uuid.UUID | None = None,
    ) -> list[FaceCrop]:
        """Detect all faces and return aligned crops (upload pipeline path)."""
        if self._detector is None:
            raise ValueError("FaceCropper requires a SCRFDDetector for detect_and_crop_all().")
        faces = self._detector.detect(image_bgr)
        return self.crop_all(image_bgr, faces, source_photo_id=source_photo_id)

    def detect_and_crop_primary(
        self,
        image_bgr: np.ndarray,
        source_photo_id: uuid.UUID | None = None,
    ) -> FaceCrop | None:
        """Detect faces and return the primary selfie crop."""
        if self._detector is None:
            raise ValueError("FaceCropper requires a SCRFDDetector for detect_and_crop_primary().")
        faces = self._detector.detect(image_bgr)
        return self.crop_primary(image_bgr, faces, source_photo_id=source_photo_id)

    def _crop_single(
        self,
        image_bgr: np.ndarray,
        face: DetectedFace,
        source_photo_id: uuid.UUID | None,
    ) -> FaceCrop | None:
        """Align one face or fall back to bbox crop when landmarks are missing."""
        alignment_matrix: np.ndarray | None = None
        if face.landmarks.shape == (5, 2) and np.any(face.landmarks):
            alignment_matrix = estimate_norm(face.landmarks, image_size=self.OUTPUT_SIZE)
            aligned_face = norm_crop(image_bgr, face.landmarks, image_size=self.OUTPUT_SIZE)
        else:
            x, y, width, height = face.bbox_pixel
            x1, y1 = int(x), int(y)
            x2, y2 = int(x + width), int(y + height)
            bbox_xyxy = np.array([x1, y1, x2, y2], dtype=np.int32)
            aligned_face = preprocess(
                image_bgr,
                bbox=bbox_xyxy,
                image_size=(self.OUTPUT_SIZE, self.OUTPUT_SIZE),
            )

        if aligned_face.shape[:2] != (self.OUTPUT_SIZE, self.OUTPUT_SIZE):
            aligned_face = cv2.resize(aligned_face, (self.OUTPUT_SIZE, self.OUTPUT_SIZE))

        return FaceCrop(
            aligned_face=aligned_face.astype(np.uint8, copy=False),
            source_detection=face,
            alignment_matrix=alignment_matrix,
            source_photo_id=source_photo_id,
        )
