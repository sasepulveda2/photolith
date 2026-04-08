import numpy as np
from PyQt5.QtCore import Qt
from PyQt5.QtGui import QImage, QPixmap
from PyQt5.QtWidgets import QApplication, QLabel, QVBoxLayout, QWidget


class ProjectionWindow(QWidget):
    def __init__(self, image_array, parent_simulator=None):
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

        layout = QVBoxLayout()
        layout.setContentsMargins(0, 0, 0, 0)

        self.image_label = QLabel()
        self.image_label.setAlignment(Qt.AlignCenter)
        self.image_label.setScaledContents(False)

        # NO actualizar con la imagen inicial - mantener negro
        # self.update_image(image_array)
        # En su lugar, mostrar pantalla negra
        self.show_black_screen()

        layout.addWidget(self.image_label)
        self.setLayout(layout)

        self.setFocusPolicy(Qt.StrongFocus)

    def show_black_screen(self):
        """Muestra una pantalla completamente negra en la proyección."""
        # Usar el tamaño completo de la pantalla si está disponible
        if self.screen_geometry:
            width = self.screen_geometry.width()
            height = self.screen_geometry.height()
        else:
            width, height = 800, 600

        # Crear una imagen negra del tamaño de la pantalla
        black_image = np.zeros((height, width), dtype=np.uint8)
        black_image = np.ascontiguousarray(black_image)

        # Convertir a QPixmap y mostrar
        bytes_per_line = width
        q_image = QImage(
            black_image.tobytes(),
            width,
            height,
            bytes_per_line,
            QImage.Format_Grayscale8,
        )
        pixmap = QPixmap.fromImage(q_image)

        self.image_label.setPixmap(pixmap)
        self.original_image = None  # No hay imagen cargada

    def update_segment(self, segment_image):
        """
        Actualiza la proyección con un segmento de imagen.
        El segmento se escala para ocupar el MÁXIMO espacio posible en pantalla (object-fit: contain),
        manteniendo su relación de aspecto.

        Args:
            segment_image: numpy array del segmento (ya procesado con efectos)
        """
        if segment_image is None:
            if hasattr(self, "parent_simulator") and self.parent_simulator:
                self.parent_simulator.log_to_console(
                    "❌ ERROR: segment_image es None", "ERROR"
                )
            return

        if self.screen_geometry is None:
            if hasattr(self, "parent_simulator") and self.parent_simulator:
                self.parent_simulator.log_to_console(
                    "❌ ERROR: screen_geometry es None", "ERROR"
                )
            return

        if len(segment_image.shape) == 3:
            segment_gray = np.mean(segment_image, axis=2)
        else:
            segment_gray = segment_image.copy()

        # Normalizar a rango 0-255 para uint8
        # Si los valores están en rango 0-1 (float), multiplicar por 255
        if segment_gray.dtype == np.float64 or segment_gray.dtype == np.float32:
            if segment_gray.max() <= 1.0:
                segment_gray = (segment_gray * 255).astype(np.uint8)
            else:
                segment_gray = segment_gray.astype(np.uint8)
        else:
            segment_gray = segment_gray.astype(np.uint8)

        # Obtener dimensiones del monitor (resolución fija)
        screen_width = self.screen_geometry.width()
        screen_height = self.screen_geometry.height()

        # Obtener dimensiones del segmento
        segment_height, segment_width = segment_gray.shape[:2]

        if segment_width == 0 or segment_height == 0:
            return

        # Calcular factor de escala para "object-fit: contain"
        scale_x = screen_width / segment_width
        scale_y = screen_height / segment_height
        scale_factor = min(scale_x, scale_y)

        # Nuevas dimensiones escaladas
        new_width = int(segment_width * scale_factor)
        new_height = int(segment_height * scale_factor)

        # Escalar imagen
        import cv2

        segment_scaled = cv2.resize(
            segment_gray, (new_width, new_height), interpolation=cv2.INTER_NEAREST
        )

        # Crear canvas negro del tamaño del monitor
        canvas = np.zeros((screen_height, screen_width), dtype=np.uint8)

        # Calcular posición para centrar
        x_offset = (screen_width - new_width) // 2
        y_offset = (screen_height - new_height) // 2

        # Copiar segmento escalado al centro del canvas
        canvas[y_offset : y_offset + new_height, x_offset : x_offset + new_width] = (
            segment_scaled
        )

        # CRÍTICO: Invertir verticalmente para corregir el sistema de coordenadas de Qt
        # Qt/QImage escanea de arriba hacia abajo, mientras que NumPy/OpenCV puede tener orden diferente
        # Esto evita que algunos chunks aparezcan invertidos o en espejo
        canvas = np.flipud(canvas)

        canvas = np.ascontiguousarray(canvas)

        # Convertir a QPixmap y mostrar
        bytes_per_line = screen_width
        q_image = QImage(
            canvas.tobytes(),
            screen_width,
            screen_height,
            bytes_per_line,
            QImage.Format_Grayscale8,
        )
        pixmap = QPixmap.fromImage(q_image)

        # Mostrar en tamaño completo del monitor
        self.image_label.setPixmap(pixmap)

        # FORZAR actualización de la ventana
        self.image_label.update()
        self.update()
        QApplication.processEvents()

        # Log de información
        if hasattr(self, "parent_simulator") and self.parent_simulator:
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

    def set_image(self, image_array):
        self.update_image(image_array)

    def set_brightness(self, brightness_percent):
        self.brightness_factor = brightness_percent / 100.0
        self._apply_brightness_and_display()

    def set_inversion(self, enabled: bool) -> None:
        self.invert_intensity = bool(enabled)
        self._apply_brightness_and_display()

    def set_binary_mode(self, enabled: bool) -> None:
        """Activa/desactiva el modo binario estricto (0/1) para litografía."""
        self.binary_mode = bool(enabled)
        self._apply_brightness_and_display()

    def set_binary_threshold(self, threshold: float) -> None:
        """
        Establece el umbral para conversión binaria (0-100).
        Valores >= threshold → blanco (1/On)
        Valores < threshold → negro (0/Off)
        Se invierte automáticamente si invert_intensity está activo.
        """
        self.binary_threshold = float(np.clip(threshold, 0.0, 100.0))
        self._apply_brightness_and_display()

    def _apply_brightness_and_display(self):
        """
        Procesa y muestra la imagen con conversión binaria estricta para litografía.
        Modo binario: cada píxel es 0 (Negro/Off) o 255 (Blanco/On).
        No se permiten escalas de grises intermedias en proyección litográfica.
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

        # Aplicar inversión de intensidad si está activada
        if self.invert_intensity:
            normalized = 1.0 - normalized

        # Aplicar brillo (antes de binarización)
        adjusted = np.clip(normalized * self.brightness_factor, 0.0, 1.0)

        if self.binary_mode:
            # ═══════════════════════════════════════════════════════════════════
            # CONVERSIÓN BINARIA ESTRICTA PARA LITOGRAFÍA
            # ═══════════════════════════════════════════════════════════════════
            # Convertir a porcentaje 0-100 para comparar con threshold
            intensity_percent = adjusted * 100.0

            # Binarización estricta: >= threshold → blanco (255), < threshold → negro (0)
            binary = np.where(
                intensity_percent >= self.binary_threshold, 255, 0
            ).astype(np.uint8)
            scaled = np.ascontiguousarray(binary)
        else:
            # Modo escala de grises (no recomendado para litografía)
            scaled = np.ascontiguousarray((adjusted * 255.0).round().astype(np.uint8))

        # CRÍTICO: Invertir verticalmente para corregir el sistema de coordenadas de Qt
        # Qt/QImage escanea de arriba hacia abajo con origen en (0,0) superior izquierda
        # NumPy/OpenCV puede tener un sistema de coordenadas diferente
        # Esto evita que la imagen completa aparezca invertida verticalmente
        scaled = np.flipud(scaled)
        scaled = np.ascontiguousarray(scaled)

        if scaled.ndim == 2:
            height, width = scaled.shape
            bytes_per_line = width
            q_image = QImage(
                scaled.tobytes(),
                width,
                height,
                bytes_per_line,
                QImage.Format_Grayscale8,
            )
        elif scaled.ndim == 3 and scaled.shape[2] == 3:
            height, width, channels = scaled.shape
            bytes_per_line = width * channels
            q_image = QImage(
                scaled.tobytes(),
                width,
                height,
                bytes_per_line,
                QImage.Format_RGB888,
            )
        else:
            gray = np.mean(scaled, axis=-1) if scaled.ndim > 2 else scaled
            gray = np.ascontiguousarray(gray.astype(np.uint8))
            height, width = gray.shape
            bytes_per_line = width
            q_image = QImage(
                gray.tobytes(),
                width,
                height,
                bytes_per_line,
                QImage.Format_Grayscale8,
            )

        pixmap = QPixmap.fromImage(q_image)

        if self.parent_simulator:
            scaled_pixmap = self._apply_scale(pixmap)
            self.image_label.setPixmap(scaled_pixmap)
        else:
            self.image_label.setPixmap(pixmap)

    def _apply_scale(self, pixmap):
        if not self.parent_simulator or not self.screen_geometry:
            return pixmap

        scale_mode = self.parent_simulator.scale_mode
        scale_percentage = self.parent_simulator.scale_percentage

        if scale_mode == "automatic":

            screen_width = self.screen_geometry.width()
            screen_height = self.screen_geometry.height()

            scaled_pixmap = pixmap.scaled(
                screen_width, screen_height, Qt.KeepAspectRatio, Qt.SmoothTransformation
            )
        else:
            original_width = pixmap.width()
            original_height = pixmap.height()

            scale_factor = scale_percentage / 100.0
            new_width = int(original_width * scale_factor)
            new_height = int(original_height * scale_factor)

            scaled_pixmap = pixmap.scaled(
                new_width, new_height, Qt.KeepAspectRatio, Qt.SmoothTransformation
            )

        if self.parent_simulator:
            self.parent_simulator.update_projection_stats(
                pixmap.width(),
                pixmap.height(),
                scaled_pixmap.width(),
                scaled_pixmap.height(),
            )

        return scaled_pixmap

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

        if len(screens) > 1:
            secondary_screen = screens[1]
        else:
            secondary_screen = screens[0]

        geometry = secondary_screen.geometry()
        self.screen_geometry = geometry

        self.setGeometry(geometry)
        self.showFullScreen()

        self._apply_brightness_and_display()
