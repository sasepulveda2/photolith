import cv2
import numpy as np
from PyQt5.QtCore import Qt
from PyQt5.QtGui import QImage, QPixmap
from PyQt5.QtWidgets import QApplication, QLabel, QVBoxLayout, QWidget


class ProjectionWindow(QWidget):
    def __init__(self, parent_simulator=None):
        super().__init__(None)
        self.parent_simulator = parent_simulator
        self.setWindowTitle("Proyección")
        self.setWindowFlags(
            Qt.Window | Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint
        )
        self.setStyleSheet("background-color: black;")

        self.original_image = None
        self.brightness_factor = 1.0
        self.invert_intensity = False
        self.binary_mode = True  # Proyección binaria para litografía (0/1 estricto)
        self.binary_threshold = 50.0  # Umbral 0-100 para conversión binaria
        self.screen_geometry = None

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        self.image_label = QLabel()
        self.image_label.setAlignment(Qt.AlignCenter)
        self.image_label.setScaledContents(False)

        self.show_black_screen()

        layout.addWidget(self.image_label)
        self.setLayout(layout)
        self.setFocusPolicy(Qt.StrongFocus)

    # ─── Private helpers ─────────────────────────────────────────────────────

    @staticmethod
    def _to_grayscale_uint8(arr: np.ndarray) -> np.ndarray:
        """Convert any array (float/uint8, 2-D/3-D) to a 2-D uint8 grayscale array."""
        if arr.ndim == 3:
            arr = np.mean(arr, axis=2)
        if arr.dtype in (np.float32, np.float64):
            arr = (arr * 255.0 if arr.max() <= 1.0 else arr).astype(np.uint8)
        else:
            arr = arr.astype(np.uint8)
        return arr

    @staticmethod
    def _numpy_to_qimage(arr: np.ndarray) -> QImage:
        """Convert a contiguous uint8 array (2-D grayscale or 3-D RGB) to a QImage."""
        arr = np.ascontiguousarray(arr)
        if arr.ndim == 2:
            h, w = arr.shape
            return QImage(arr.data, w, h, w, QImage.Format_Grayscale8).copy()
        if arr.ndim == 3 and arr.shape[2] == 3:
            h, w, c = arr.shape
            return QImage(arr.data, w, h, w * c, QImage.Format_RGB888).copy()
        # Fallback: collapse to grayscale
        gray = np.ascontiguousarray(np.mean(arr, axis=-1).astype(np.uint8))
        h, w = gray.shape
        return QImage(gray.data, w, h, w, QImage.Format_Grayscale8).copy()

    def _numpy_to_pixmap(self, arr: np.ndarray, flip: bool = True) -> QPixmap:
        """Convert a numpy array to a QPixmap.

        Args:
            arr:  Any numeric array accepted by _to_grayscale_uint8.
            flip: If True, flip vertically to correct Qt's top-down coordinate system.
        """
        gray = self._to_grayscale_uint8(arr)
        if flip:
            gray = np.flipud(gray)
        return QPixmap.fromImage(self._numpy_to_qimage(gray))

    # ─── Public API ──────────────────────────────────────────────────────────

    def show_black_screen(self):
        """Display a fully black screen on the projection window."""
        if self.screen_geometry:
            width = self.screen_geometry.width()
            height = self.screen_geometry.height()
        else:
            width, height = 800, 600

        pixmap = QPixmap(width, height)
        pixmap.fill(Qt.black)
        self.image_label.setPixmap(pixmap)
        self.original_image = None

    def update_segment(self, segment_image):
        """Update the projection with an image segment.

        The segment is scaled to fill the maximum available screen space
        (object-fit: contain) while preserving its aspect ratio.

        Args:
            segment_image: numpy array of the segment (already processed with effects).
        """
        if segment_image is None:
            if self.parent_simulator:
                self.parent_simulator.log_to_console(
                    "❌ ERROR: segment_image es None", "ERROR"
                )
            return

        if self.screen_geometry is None:
            if self.parent_simulator:
                self.parent_simulator.log_to_console(
                    "❌ ERROR: screen_geometry es None", "ERROR"
                )
            return

        segment_gray = self._to_grayscale_uint8(segment_image)
        screen_width = self.screen_geometry.width()
        screen_height = self.screen_geometry.height()
        segment_height, segment_width = segment_gray.shape[:2]

        if segment_width == 0 or segment_height == 0:
            return

        # Scale to fit screen while preserving aspect ratio (object-fit: contain)
        scale_factor = min(screen_width / segment_width, screen_height / segment_height)
        new_width = int(segment_width * scale_factor)
        new_height = int(segment_height * scale_factor)

        segment_scaled = cv2.resize(
            segment_gray, (new_width, new_height), interpolation=cv2.INTER_NEAREST
        )

        # Place the scaled segment centered on a black canvas matching the screen size
        canvas = np.zeros((screen_height, screen_width), dtype=np.uint8)
        x_offset = (screen_width - new_width) // 2
        y_offset = (screen_height - new_height) // 2
        canvas[y_offset : y_offset + new_height, x_offset : x_offset + new_width] = (
            segment_scaled
        )

        # CRITICAL: DO NOT flip vertically, this was causing images to appear inverted.
        canvas = np.ascontiguousarray(canvas)

        self.image_label.setPixmap(QPixmap.fromImage(self._numpy_to_qimage(canvas)))
        self.image_label.update()
        self.update()
        QApplication.processEvents()

        if self.parent_simulator:
            self.parent_simulator.log_to_console(
                f"🖥️ PROYECTANDO EN PANTALLA SECUNDARIA:\n"
                f"  • Chunk original: {segment_width}×{segment_height} px\n"
                f"  • Escalado a: {new_width}×{new_height} px (factor {scale_factor:.2f}×)\n"
                f"  • Monitor: {screen_width}×{screen_height} px\n"
                f"  • Posición: centrado ({x_offset}, {y_offset})\n"
                f"  • Valores canvas: min={canvas.min()}, max={canvas.max()}",
                "SUCCESS",
            )

    def update_image(self, image_array):
        if image_array is None:
            self.show_black_screen()
            return

        self.original_image = np.array(image_array, dtype=np.float64, copy=True)
        self._apply_brightness_and_display()

    def set_brightness(self, brightness_percent):
        self.brightness_factor = brightness_percent / 100.0
        self._apply_brightness_and_display()

    def set_inversion(self, enabled: bool) -> None:
        self.invert_intensity = bool(enabled)
        self._apply_brightness_and_display()

    def set_binary_mode(self, enabled: bool) -> None:
        """Enable/disable strict binary mode (0/1) for lithography."""
        self.binary_mode = bool(enabled)
        self._apply_brightness_and_display()

    def set_binary_threshold(self, threshold: float) -> None:
        """Set the threshold for binary conversion (0-100).

        Values >= threshold → white (255 / On)
        Values <  threshold → black (0   / Off)
        Automatically inverted when invert_intensity is active.
        """
        self.binary_threshold = float(np.clip(threshold, 0.0, 100.0))
        self._apply_brightness_and_display()

    # ─── Private display logic ───────────────────────────────────────────────

    def _apply_brightness_and_display(self):
        """Process and display the image with strict binary conversion for lithography.

        Binary mode: each pixel is 0 (Black/Off) or 255 (White/On).
        Intermediate grayscale values are not allowed in lithographic projection.
        """
        if self.original_image is None:
            return

        image = np.nan_to_num(self.original_image, nan=0.0)
        min_val = float(image.min()) if image.size else 0.0
        max_val = float(image.max()) if image.size else 0.0

        if max_val > min_val:
            normalized = (image - min_val) / (max_val - min_val)
        else:
            normalized = np.zeros_like(image, dtype=np.float64)

        if self.invert_intensity:
            normalized = 1.0 - normalized

        adjusted = np.clip(normalized * self.brightness_factor, 0.0, 1.0)

        if self.binary_mode:
            # Strict binary conversion for lithography
            pixel_data = np.where(
                adjusted * 100.0 >= self.binary_threshold, 255, 0
            ).astype(np.uint8)
        else:
            # Grayscale mode (not recommended for lithography)
            pixel_data = (adjusted * 255.0).round().astype(np.uint8)

        pixmap = self._numpy_to_pixmap(pixel_data, flip=False)

        if self.parent_simulator:
            self.image_label.setPixmap(self._apply_scale(pixmap))
        else:
            self.image_label.setPixmap(pixmap)

    def _apply_scale(self, pixmap):
        if not self.parent_simulator or not self.screen_geometry:
            return pixmap

        # La regla de escala ya se genera del tamaño exacto del monitor, no debe escalarse
        if getattr(self.parent_simulator, "_ruler_scale_view_active", False):
            return pixmap

        scale_mode = self.parent_simulator.scale_mode
        scale_percentage = self.parent_simulator.scale_percentage

        if scale_mode == "automatic":
            scaled_pixmap = pixmap.scaled(
                self.screen_geometry.width(),
                self.screen_geometry.height(),
                Qt.KeepAspectRatio,
                Qt.SmoothTransformation,
            )
        else:
            scale_factor = scale_percentage / 100.0
            scaled_pixmap = pixmap.scaled(
                int(pixmap.width() * scale_factor),
                int(pixmap.height() * scale_factor),
                Qt.KeepAspectRatio,
                Qt.SmoothTransformation,
            )

        if self.parent_simulator:
            self.parent_simulator.update_projection_stats(
                pixmap.width(),
                pixmap.height(),
                scaled_pixmap.width(),
                scaled_pixmap.height(),
            )

        return scaled_pixmap

    # ─── Qt event handlers ───────────────────────────────────────────────────

    def keyPressEvent(self, event):
        if event.key() == Qt.Key_Escape:
            self.close()
        super().keyPressEvent(event)

    def closeEvent(self, event):
        if self.parent_simulator is not None:
            self.parent_simulator.on_projection_closed()
        super().closeEvent(event)

    def show_on_secondary_monitor(self):
        screens = QApplication.screens()
        secondary_screen = screens[1] if len(screens) > 1 else screens[0]
        self.screen_geometry = secondary_screen.geometry()
        self.setGeometry(self.screen_geometry)
        self.showFullScreen()
        self._apply_brightness_and_display()
