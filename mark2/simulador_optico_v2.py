"""
═══════════════════════════════════════════════════════════════════════════════
SIMULADOR DE LITOGRAFÍA ÓPTICA - SISTEMA DE SLICE Y PROYECCIÓN
═══════════════════════════════════════════════════════════════════════════════

SISTEMA DE SEGMENTACIÓN Y CORTES (SLICE):
-----------------------------------------
✓ UN ÚNICO CORTE ACTIVO: Solo existe un corte automático en todo momento
✓ CÁLCULO AUTOMÁTICO: El corte se calcula usando las coordenadas extremas del contenido
✓ CACHE DETERMINISTA: El mismo corte se reutiliza si no cambian:
    • La imagen (mismo objeto)
    • La posición de la imagen en el grid
    • La configuración del grid (segments_x, segments_y)
✓ NO SE PERMITEN CORTES SOBRE CORTES: El único corte válido identifica exactamente
  los chunks donde la imagen está presente
✓ ORDEN SECUENCIAL ESTRICTO: Los chunks se procesan uno a uno, en orden

VISUALIZACIÓN Y RENDERIZADO:
----------------------------
✓ CHUNKS SECUENCIALES: Los chunks se muestran uno a la vez, estrictamente en orden
✓ ESCALADO MÁXIMO: Cada chunk se renderiza al máximo tamaño posible que permita
  la pantalla (object-fit: contain)
✓ RESOLUCIÓN FIJA: Los píxeles de la pantalla son fijos, la adaptación ocurre
  dentro del chunk
✓ INVERSIÓN DISPONIBLE: Opción para invertir la imagen en el preview y proyección

CONSISTENCIA Y DETERMINISMO:
---------------------------
✓ CACHE INTELIGENTE: No se recalcula el corte si los datos no cambian
✓ LOGGING DETALLADO: Se registra cuando se usa cache vs. recálculo
✓ LIMPIEZA MANUAL: Opción en menú de preferencias para limpiar cache si es necesario

Fecha última actualización: 2025-11-25
═══════════════════════════════════════════════════════════════════════════════
"""

import sys
import cv2
import os
import json
import time
from scipy.ndimage import gaussian_filter

os.environ['OPENCV_VIDEOIO_PRIORITY_MSMF'] = '0'
os.environ['OPENCV_LOG_LEVEL'] = 'ERROR'
cv2.setLogLevel(0)

try:
    from pypylon import pylon
    BASLER_AVAILABLE = True
except ImportError:
    BASLER_AVAILABLE = False
    pylon = None
from PyQt5.QtWidgets import (
    QApplication,
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QPushButton,
    QLabel,
    QFileDialog,
    QSlider,
    QMessageBox,
    QTreeWidget,
    QTreeWidgetItem,
    QInputDialog,
    QMenu,
    QComboBox,
    QTreeWidgetItemIterator,
    QGraphicsOpacityEffect,
    QLineEdit,
    QScrollArea,
    QDialog,
    QRadioButton,
    QButtonGroup,
    QCheckBox,
    QToolButton,
    QFrame,
    QSizePolicy,
    QSpinBox,
    QDoubleSpinBox,
    QProgressBar,
    QTextEdit,
)
from PyQt5.QtCore import Qt, QPropertyAnimation, QEasingCurve, QSize, QTimer
from PyQt5.QtGui import QDragEnterEvent, QDropEvent, QIcon, QPixmap, QImage
from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg as FigureCanvas, NavigationToolbar2QT as NavigationToolbar
from matplotlib.figure import Figure
import numpy as np
import ctypes


class CollapsibleSection(QWidget):

    def __init__(self, title: str, parent=None, expanded: bool = True):
        super().__init__(parent)

        self.toggle_button = QToolButton(text=title)
        self.toggle_button.setCheckable(True)
        self.toggle_button.setChecked(expanded)
        self.toggle_button.setArrowType(Qt.DownArrow if expanded else Qt.RightArrow)
        self.toggle_button.setToolButtonStyle(Qt.ToolButtonTextBesideIcon)
        self.toggle_button.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        self.toggle_button.setObjectName("sectionTitle")
        self.toggle_button.setCursor(Qt.PointingHandCursor)

        self.content_area = QFrame()
        self.content_area.setFrameShape(QFrame.NoFrame)
        self.content_area.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        self.content_layout = QVBoxLayout()
        self.content_layout.setContentsMargins(0, 0, 0, 0)
        self.content_layout.setSpacing(0)
        self.content_area.setLayout(self.content_layout)
        self.content_area.setVisible(expanded)

        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(4)
        main_layout.addWidget(self.toggle_button)
        main_layout.addWidget(self.content_area)

        self.toggle_button.toggled.connect(self._on_toggled)

    def _on_toggled(self, checked: bool) -> None:
        self.toggle_button.setArrowType(Qt.DownArrow if checked else Qt.RightArrow)
        self.content_area.setVisible(checked)

    def setContentWidget(self, widget: QWidget) -> None:
        while self.content_layout.count():
            item = self.content_layout.takeAt(0)
            if item.widget():
                item.widget().setParent(None)
        self.content_layout.addWidget(widget)

    def set_collapsed(self, collapsed: bool) -> None:
        self.toggle_button.setChecked(not collapsed)

    def is_collapsed(self) -> bool:
        return not self.toggle_button.isChecked()


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
        q_image = QImage(black_image.tobytes(), width, height, bytes_per_line, QImage.Format_Grayscale8)
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
            if hasattr(self, 'parent_simulator') and self.parent_simulator:
                self.parent_simulator.log_to_console("❌ ERROR: segment_image es None", "ERROR")
            return
            
        if self.screen_geometry is None:
            if hasattr(self, 'parent_simulator') and self.parent_simulator:
                self.parent_simulator.log_to_console("❌ ERROR: screen_geometry es None", "ERROR")
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
        segment_scaled = cv2.resize(segment_gray, (new_width, new_height), interpolation=cv2.INTER_NEAREST)
        
        # Crear canvas negro del tamaño del monitor
        canvas = np.zeros((screen_height, screen_width), dtype=np.uint8)
        
        # Calcular posición para centrar
        x_offset = (screen_width - new_width) // 2
        y_offset = (screen_height - new_height) // 2
        
        # Copiar segmento escalado al centro del canvas
        canvas[y_offset:y_offset+new_height, 
               x_offset:x_offset+new_width] = segment_scaled
        
        # CRÍTICO: Invertir verticalmente para corregir el sistema de coordenadas de Qt
        # Qt/QImage escanea de arriba hacia abajo, mientras que NumPy/OpenCV puede tener orden diferente
        # Esto evita que algunos chunks aparezcan invertidos o en espejo
        canvas = np.flipud(canvas)
        
        canvas = np.ascontiguousarray(canvas)
        
        # Convertir a QPixmap y mostrar
        bytes_per_line = screen_width
        q_image = QImage(canvas.tobytes(), screen_width, screen_height, bytes_per_line, QImage.Format_Grayscale8)
        pixmap = QPixmap.fromImage(q_image)
        
        # Mostrar en tamaño completo del monitor
        self.image_label.setPixmap(pixmap)
        
        # FORZAR actualización de la ventana
        self.image_label.update()
        self.update()
        QApplication.processEvents()
        
        # Log de información
        if hasattr(self, 'parent_simulator') and self.parent_simulator:
            self.parent_simulator.log_to_console(
                f"🖥️ PROYECTANDO EN PANTALLA SECUNDARIA:\n"
                f"  • Chunk original: {segment_width}×{segment_height} px\n"
                f"  • Escalado a: {new_width}×{new_height} px (factor {scale_factor:.2f}×)\n"
                f"  • Monitor: {screen_width}×{screen_height} px\n"
                f"  • Posición: centrado ({x_offset}, {y_offset})\n"
                f"  • Valores canvas: min={canvas.min()}, max={canvas.max()}",
                "SUCCESS"
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
            binary = np.where(intensity_percent >= self.binary_threshold, 255, 0).astype(np.uint8)
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


class LithographySimulator(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Simulador Litografía Uandes V1.1")
        
        # Ajustar tamaño de ventana según pantalla disponible
        from PyQt5.QtWidgets import QDesktopWidget
        screen = QDesktopWidget().availableGeometry()
        # Usar 90% del ancho y 85% de la altura disponible (dejar margen para taskbar)
        width = min(1400, int(screen.width() * 0.9))
        height = min(900, int(screen.height() * 0.85))
        self.resize(width, height)
        self.setAcceptDrops(True)

        icon_path = os.path.join(os.path.dirname(__file__), "icono.ico")
        if os.path.exists(icon_path):
            self.setWindowIcon(QIcon(icon_path))

        self.set_dark_titlebar()

        # ═══════════════════════════════════════════════════════════════════════════
        # DEFINICIÓN DE UNIDADES Y PRECISIÓN PARA LITOGRAFÍA
        # ═══════════════════════════════════════════════════════════════════════════
        # Todas las coordenadas, movimientos y tiempos de exposición son manejados
        # en punto flotante (float) para máxima precisión en procesos litográficos.
        # 
        # Unidades utilizadas:
        #   - Coordenadas espaciales: píxeles (px) y unidades configurables (μm, mm, cm)
        #   - Tiempo de exposición: segundos (s) con precisión de microsegundos (μs)
        #   - Resolución: píxeles por unidad (px/μm, px/mm, etc.)
        #   - Intensidad: porcentaje normalizado (0.0 - 100.0%)
        #   - Brillo: porcentaje normalizado (0.0 - 100.0%)
        # ═══════════════════════════════════════════════════════════════════════════

        self.pattern = None
        self.sigma = 1.0
        self.cache_dir = "cache_photolith"
        self.config_file = os.path.join(self.cache_dir, "file_structure.json")
        self.dark_mode = True
        self.projector_active = False
        self.projection_window = None
        self.has_second_monitor = self.check_second_monitor()

        self.scale_mode = "automatic"
        self.scale_percentage = 100
        self.current_scale_info = {
            "original": (0, 0),
            "scaled": (0, 0),
            "percentage": 0,
        }

        self.inter_cycle_delay = 0
        self.final_brightness_mode = "zero"

        self.grid_view_active = False
        self.grid_config_file = os.path.join("cache_photolith", "grid_config.json")
        self.load_grid_config()
        
        self.apply_effects_to_grid = False

        self.calibration_view_active = False
        self.calibration_source = "camera"
        self.calibration_camera = None
        self.basler_camera = None
        self.basler_converter = None
        self.calibration_image = None
        self.calibration_grayscale = None
        self.calibration_intensity_data = None
        self.current_zone_grid = "4x4"
        
        self.basler_exposure = 10000.0
        self.basler_gain = 0.0
        self.basler_width = 640
        self.basler_height = 750
        self.basler_offset_x = 0
        self.basler_offset_y = 0
        self.basler_gamma = 1.0
        self.basler_black_level = 0
        
        self.calibration_threshold = 50.0
        self.attenuation_matrix = None
        self.attenuation_strength = 100.0
        self.attenuation_method = "normalized"
        self.apply_attenuation_to_grid = False
        
        self.calibration_flip_x = False
        self.calibration_flip_y = False
        
        self.calibration_file = os.path.join("cache_photolith", "calibration_matrix.npy")
        self.calibration_config_file = os.path.join("cache_photolith", "calibration_config.json")
        
        self.load_calibration_data()

        self.exposure_timer = QTimer()
        self.exposure_timer.timeout.connect(self.stop_timed_exposure)
        self.exposure_active = False
        self.exposure_start_time = 0.0
        self.exposure_duration = 0.0
        self.exposure_cycles_completed = 0
        self.exposure_target_brightness = 0.0
        
        self.current_projecting_segment = None

        self.countdown_timer = QTimer()
        self.countdown_timer.timeout.connect(self.update_countdown)
        self.countdown_timer.setInterval(100)

        self.inter_cycle_timer = QTimer()
        self.inter_cycle_timer.setSingleShot(True)
        self.inter_cycle_timer.timeout.connect(self.resume_next_cycle)

        self.frequency_mode = False
        self.frequency_timer = QTimer()
        self.frequency_timer.timeout.connect(self.stop_frequency_mode)
        self.frequency_start_time = 0.0
        self.frequency_duration = 0.0

        self.init_cache_system()

        main_layout = QVBoxLayout()
        control_layout = QHBoxLayout()

        self.load_button = QPushButton("📂 Cargar patrón")
        self.load_button.clicked.connect(self.load_pattern)

        self.toggle_view_button = QPushButton("📏 Vista Grid")
        self.toggle_view_button.clicked.connect(self.toggle_grid_view)

        self.calibration_button = QPushButton("🎯 Calibración")
        self.calibration_button.clicked.connect(self.toggle_calibration_view)

        self.preferences_button = QPushButton("⚙️ Preferencias")
        self.preferences_button.clicked.connect(self.show_preferences_menu)

        self.projector_button = QPushButton("🎬 Proyectar")
        self.projector_button.clicked.connect(self.toggle_projector)
        self.projector_button.setVisible(False)

        self.sigma_label = QLabel(f"Sigma (Desenfoque): {self.sigma:.1f}")
        self.sigma_slider = QSlider(Qt.Horizontal)
        self.sigma_slider.setMinimum(1)
        self.sigma_slider.setMaximum(30)
        self.sigma_slider.setValue(int(self.sigma))
        self.sigma_slider.valueChanged.connect(self.update_sigma)

        self.brightness = 100
        self.brightness_label = QLabel(f"Brillo Proyección: {self.brightness}%")
        self.brightness_slider = QSlider(Qt.Horizontal)
        self.brightness_slider.setMinimum(0)
        self.brightness_slider.setMaximum(100)
        self.brightness_slider.setValue(self.brightness)
        self.brightness_slider.valueChanged.connect(self.update_brightness)
        self.brightness_slider.setVisible(False)
        self.brightness_label.setVisible(False)

        self.invert_projection = False

        self.binary_threshold = 50.0
        self.binary_mode_enabled = False

        self.downscale_factor = 1.0
        self.sequence_running = False
        self.sequence_paused = False
        self.current_segment_index = 0
        self.total_segments = 0
        self.sequence_timer = None

        self.image_segments = []
        self.segments_x = 4
        self.segments_y = 4
        self.show_segments_overlay = False
        self.segmentation_mode = 0
        
        self._pattern_load_id = None
        self._last_segmentation_pattern_id = None
        self._last_segmentation_bounds = None
        self._last_segmentation_grid_config = None
        self._last_image_position = None
        
        self.image_rotation = 0
        self.image_mirror_h = False
        self.image_mirror_v = False

        self.save_button = QPushButton("💾 Guardar imagen")
        self.save_button.clicked.connect(self.save_image)

        self.format_combo = QComboBox()
        self.format_combo.addItems(["PNG", "JPG", "BMP", "TIFF"])

        self.show_projection_image = True
        
        self.exposure_button = QPushButton("▶️ Iniciar Exposición")

        control_layout.addWidget(self.load_button)
        control_layout.addWidget(self.toggle_view_button)
        control_layout.addWidget(self.calibration_button)
        control_layout.addWidget(self.preferences_button)
        control_layout.addWidget(self.projector_button)
        control_layout.addWidget(self.sigma_label)
        control_layout.addWidget(self.sigma_slider)
        control_layout.addWidget(self.brightness_label)
        control_layout.addWidget(self.brightness_slider)
        # control_layout.addWidget(self.invert_button)
        control_layout.addWidget(self.save_button)
        control_layout.addWidget(QLabel("Formato:"))
        control_layout.addWidget(self.format_combo)

        self.figure = Figure(facecolor="#121212")
        self.canvas = FigureCanvas(self.figure)
        
        self.canvas.mpl_connect('button_press_event', self.on_mouse_press)
        self.canvas.mpl_connect('button_release_event', self.on_mouse_release)
        self.canvas.mpl_connect('motion_notify_event', self.on_mouse_move)
        self.canvas.mpl_connect('scroll_event', self.on_mouse_scroll)
        
        self.panning = False
        self.pan_start_pos = None

        self.info_layout = QVBoxLayout()
        self.info_layout.setSpacing(12)

        self.stats_section = CollapsibleSection("📊 DATA", self, expanded=True)
        stats_content = QWidget()
        stats_content.setObjectName("statsContainer")
        stats_layout = QVBoxLayout(stats_content)
        stats_layout.setContentsMargins(12, 12, 12, 12)
        stats_layout.setSpacing(8)

        self.resolution_label = QLabel("Resolución: -")
        self.resolution_label.setObjectName("statLabel")
        self.min_label = QLabel("Intensidad mínima: -")
        self.min_label.setObjectName("statLabel")
        self.avg_label = QLabel("Intensidad promedio: -")
        self.avg_label.setObjectName("statLabel")
        self.max_label = QLabel("Intensidad máxima: -")
        self.max_label.setObjectName("statLabel")

        self.scale_info_label = QLabel("Escala proyección: -")
        self.scale_info_label.setObjectName("statLabel")
        self.scale_info_label.setVisible(False)
        
        self.projected_resolution_label = QLabel("Resolución proyectada: -")
        self.projected_resolution_label.setObjectName("statLabel")
        self.projected_resolution_label.setVisible(False)
        
        self.monitor_resolution_label = QLabel("Monitor proyección: -")
        self.monitor_resolution_label.setObjectName("statLabel")

        self.calibration_status_label = QLabel("Calibración: Inactiva")
        self.calibration_status_label.setObjectName("statLabel")
        if hasattr(self, 'apply_attenuation_to_grid'):
             self.calibration_status_label.setText(f"Calibración: {'✓ Activa' if self.apply_attenuation_to_grid else 'Inactiva'}")

        stats_layout.addWidget(self.resolution_label)
        stats_layout.addWidget(self.min_label)
        stats_layout.addWidget(self.avg_label)
        stats_layout.addWidget(self.max_label)
        stats_layout.addWidget(self.scale_info_label)
        stats_layout.addWidget(self.projected_resolution_label)
        stats_layout.addWidget(self.monitor_resolution_label)
        stats_layout.addWidget(self.calibration_status_label)

        self.stats_section.setContentWidget(stats_content)
        self.info_layout.addWidget(self.stats_section)

        # ═══════════════════════════════════════════════════════════════════════════
        # SECCIÓN BINARIO (NUEVA)
        # ═══════════════════════════════════════════════════════════════════════════
        self.binary_section = CollapsibleSection("⚫⚪ BINARIO", self, expanded=True)
        binary_content = QWidget()
        binary_content.setObjectName("statsContainer")
        binary_layout = QVBoxLayout(binary_content)
        binary_layout.setContentsMargins(12, 12, 12, 12)
        binary_layout.setSpacing(12)

        # Checkbox Activar Modo Binario
        self.binary_mode_check = QCheckBox("Activar Modo Binario (0/1)")
        self.binary_mode_check.setChecked(self.binary_mode_enabled)
        self.binary_mode_check.stateChanged.connect(self.toggle_binary_mode)
        self.binary_mode_check.setObjectName("statLabel")
        binary_layout.addWidget(self.binary_mode_check)

        # Label de estado
        self.binary_status_label = QLabel(f"Estado: {'✓ Activo' if self.binary_mode_enabled else '✗ Inactivo'}")
        self.binary_status_label.setObjectName("statLabel")
        binary_layout.addWidget(self.binary_status_label)

        # Checkbox Invertir Color
        self.invert_check = QCheckBox("Invertir Color (Negativo)")
        self.invert_check.setChecked(self.invert_projection)
        self.invert_check.stateChanged.connect(self.toggle_intensity_inversion)
        self.invert_check.setObjectName("statLabel")
        binary_layout.addWidget(self.invert_check)

        # Threshold Control
        threshold_label = QLabel("Umbral (Threshold):")
        threshold_label.setObjectName("statLabel")
        binary_layout.addWidget(threshold_label)

        threshold_layout = QHBoxLayout()
        self.binary_threshold_slider = QSlider(Qt.Horizontal)
        self.binary_threshold_slider.setMinimum(0)
        self.binary_threshold_slider.setMaximum(100)
        self.binary_threshold_slider.setValue(int(self.binary_threshold))
        self.binary_threshold_slider.valueChanged.connect(self.update_binary_threshold_from_slider)
        
        self.binary_threshold_input = QLineEdit(str(self.binary_threshold))
        self.binary_threshold_input.setMaximumWidth(50)
        self.binary_threshold_input.returnPressed.connect(self.update_binary_threshold_from_input)
        
        threshold_layout.addWidget(self.binary_threshold_slider)
        threshold_layout.addWidget(self.binary_threshold_input)
        threshold_layout.addWidget(QLabel("%"))
        binary_layout.addLayout(threshold_layout)

        self.binary_section.setContentWidget(binary_content)
        self.info_layout.addWidget(self.binary_section)

        self.check_second_monitor()

        self.grid_stats_section = CollapsibleSection("📏 ESTADÍSTICAS GRID", self, expanded=False)
        grid_stats_content = QWidget()
        grid_stats_content.setObjectName("statsContainer")
        grid_stats_layout = QVBoxLayout(grid_stats_content)
        grid_stats_layout.setContentsMargins(12, 12, 12, 12)
        grid_stats_layout.setSpacing(8)

        self.grid_dimensions_label = QLabel("Dimensiones: -")
        self.grid_dimensions_label.setObjectName("statLabel")
        self.grid_cells_x_label = QLabel("Celdas X: -")
        self.grid_cells_x_label.setObjectName("statLabel")
        self.grid_cells_y_label = QLabel("Celdas Y: -")
        self.grid_cells_y_label.setObjectName("statLabel")
        self.grid_cell_size_label = QLabel("Tamaño celda: -")
        self.grid_cell_size_label.setObjectName("statLabel")
        self.grid_pixels_label = QLabel("Píxeles/celda: -")
        self.grid_pixels_label.setObjectName("statLabel")
        self.grid_resolution_label = QLabel("Resolución: -")
        self.grid_resolution_label.setObjectName("statLabel")
        self.grid_pixel_size_label = QLabel("Tamaño píxel: -")
        self.grid_pixel_size_label.setObjectName("statLabel")
        self.grid_total_cells_label = QLabel("Total celdas: -")
        self.grid_total_cells_label.setObjectName("statLabel")
        self.grid_color_label = QLabel("Color: -")
        self.grid_color_label.setObjectName("statLabel")

        grid_stats_layout.addWidget(self.grid_dimensions_label)
        grid_stats_layout.addWidget(self.grid_cells_x_label)
        grid_stats_layout.addWidget(self.grid_cells_y_label)
        grid_stats_layout.addWidget(self.grid_cell_size_label)
        grid_stats_layout.addWidget(self.grid_pixels_label)
        grid_stats_layout.addWidget(self.grid_resolution_label)
        grid_stats_layout.addWidget(self.grid_pixel_size_label)
        grid_stats_layout.addWidget(self.grid_total_cells_label)
        grid_stats_layout.addWidget(self.grid_color_label)

        self.grid_stats_section.setContentWidget(grid_stats_content)
        self.grid_stats_section.setVisible(False)
        self.info_layout.addWidget(self.grid_stats_section)

        # ═══════════════════════════════════════════════════════════════════════════
        # SECCIÓN CONTROLES CÁMARA BASLER (PANEL LATERAL DERECHO)
        # ═══════════════════════════════════════════════════════════════════════════
        self.basler_sidebar_section = CollapsibleSection("🎥 CÁMARA BASLER", self, expanded=True)
        basler_sidebar_content = QWidget()
        basler_sidebar_content.setObjectName("statsContainer")
        basler_sidebar_layout = QVBoxLayout(basler_sidebar_content)
        basler_sidebar_layout.setContentsMargins(12, 12, 12, 12)
        basler_sidebar_layout.setSpacing(12)
        
        # Control de Exposición
        exp_label = QLabel("⏱️ Exposición (μs):")
        exp_label.setStyleSheet("font-weight: bold; font-size: 11px;")
        basler_sidebar_layout.addWidget(exp_label)
        
        exp_layout = QHBoxLayout()
        self.basler_sidebar_exposure_slider = QSlider(Qt.Horizontal)
        self.basler_sidebar_exposure_slider.setMinimum(100)  # 100 μs mínimo
        self.basler_sidebar_exposure_slider.setMaximum(1000000)  # 1 segundo máximo
        self.basler_sidebar_exposure_slider.setValue(10000)  # 10ms por defecto
        self.basler_sidebar_exposure_slider.valueChanged.connect(self.update_basler_exposure_from_slider)
        self.basler_sidebar_exposure_input = QLineEdit("10000")
        self.basler_sidebar_exposure_input.setMaximumWidth(70)
        self.basler_sidebar_exposure_input.returnPressed.connect(self.update_basler_exposure_from_input)
        exp_layout.addWidget(self.basler_sidebar_exposure_slider, stretch=1)
        exp_layout.addWidget(self.basler_sidebar_exposure_input)
        exp_unit_label = QLabel("μs")
        exp_unit_label.setStyleSheet("font-size: 10px;")
        exp_layout.addWidget(exp_unit_label)
        basler_sidebar_layout.addLayout(exp_layout)
        
        # Control de Ganancia
        gain_label = QLabel("📊 Ganancia (dB):")
        gain_label.setStyleSheet("font-weight: bold; font-size: 11px;")
        basler_sidebar_layout.addWidget(gain_label)
        
        gain_layout = QHBoxLayout()
        self.basler_sidebar_gain_slider = QSlider(Qt.Horizontal)
        self.basler_sidebar_gain_slider.setMinimum(0)
        self.basler_sidebar_gain_slider.setMaximum(240)  # 24.0 dB máximo (x10 para precisión)
        self.basler_sidebar_gain_slider.setValue(0)
        self.basler_sidebar_gain_slider.valueChanged.connect(self.update_basler_gain_from_slider)
        self.basler_sidebar_gain_input = QLineEdit("0.0")
        self.basler_sidebar_gain_input.setMaximumWidth(70)
        self.basler_sidebar_gain_input.returnPressed.connect(self.update_basler_gain_from_input)
        gain_layout.addWidget(self.basler_sidebar_gain_slider, stretch=1)
        gain_layout.addWidget(self.basler_sidebar_gain_input)
        gain_unit_label = QLabel("dB")
        gain_unit_label.setStyleSheet("font-size: 10px;")
        gain_layout.addWidget(gain_unit_label)
        basler_sidebar_layout.addLayout(gain_layout)
        
        # Control de Gamma
        gamma_label = QLabel("🔆 Gamma:")
        gamma_label.setStyleSheet("font-weight: bold; font-size: 11px;")
        basler_sidebar_layout.addWidget(gamma_label)
        
        gamma_layout = QHBoxLayout()
        self.basler_sidebar_gamma_slider = QSlider(Qt.Horizontal)
        self.basler_sidebar_gamma_slider.setMinimum(10)  # 0.1 (x10)
        self.basler_sidebar_gamma_slider.setMaximum(40)  # 4.0 (x10)
        self.basler_sidebar_gamma_slider.setValue(10)  # 1.0 por defecto
        self.basler_sidebar_gamma_slider.valueChanged.connect(self.update_basler_gamma_from_slider)
        self.basler_sidebar_gamma_input = QLineEdit("1.0")
        self.basler_sidebar_gamma_input.setMaximumWidth(70)
        self.basler_sidebar_gamma_input.returnPressed.connect(self.update_basler_gamma_from_input)
        gamma_layout.addWidget(self.basler_sidebar_gamma_slider, stretch=1)
        gamma_layout.addWidget(self.basler_sidebar_gamma_input)
        basler_sidebar_layout.addLayout(gamma_layout)
        
        # Control de Black Level
        black_label = QLabel("⬛ Nivel de Negro:")
        black_label.setStyleSheet("font-weight: bold; font-size: 11px;")
        basler_sidebar_layout.addWidget(black_label)
        
        black_layout = QHBoxLayout()
        self.basler_sidebar_black_slider = QSlider(Qt.Horizontal)
        self.basler_sidebar_black_slider.setMinimum(0)
        self.basler_sidebar_black_slider.setMaximum(255)
        self.basler_sidebar_black_slider.setValue(0)
        self.basler_sidebar_black_slider.valueChanged.connect(self.update_basler_black_from_slider)
        self.basler_sidebar_black_input = QLineEdit("0")
        self.basler_sidebar_black_input.setMaximumWidth(70)
        self.basler_sidebar_black_input.returnPressed.connect(self.update_basler_black_from_input)
        black_layout.addWidget(self.basler_sidebar_black_slider, stretch=1)
        black_layout.addWidget(self.basler_sidebar_black_input)
        basler_sidebar_layout.addLayout(black_layout)
        
        # Separador
        basler_sidebar_layout.addSpacing(8)
        
        # Botón para aplicar cambios
        apply_sidebar_basler_btn = QPushButton("✓ Aplicar Configuración")
        apply_sidebar_basler_btn.setObjectName("modernButton")
        apply_sidebar_basler_btn.setMinimumHeight(32)
        apply_sidebar_basler_btn.clicked.connect(self.apply_basler_settings)
        basler_sidebar_layout.addWidget(apply_sidebar_basler_btn)
        
        # Botón para resetear a valores por defecto
        reset_sidebar_basler_btn = QPushButton("↺ Valores por Defecto")
        reset_sidebar_basler_btn.setObjectName("modernButton")
        reset_sidebar_basler_btn.setMinimumHeight(32)
        reset_sidebar_basler_btn.clicked.connect(self.reset_basler_settings)
        basler_sidebar_layout.addWidget(reset_sidebar_basler_btn)
        
        self.basler_sidebar_section.setContentWidget(basler_sidebar_content)
        self.basler_sidebar_section.setVisible(False)  # Oculto por defecto
        self.info_layout.addWidget(self.basler_sidebar_section)

        self.image_coords_section = CollapsibleSection("🖼️ IMAGEN EN GRID", self, expanded=False)
        image_coords_content = QWidget()
        image_coords_content.setObjectName("statsContainer")
        image_coords_layout = QVBoxLayout(image_coords_content)
        image_coords_layout.setContentsMargins(12, 12, 12, 12)
        image_coords_layout.setSpacing(8)

        drag_mode_layout = QHBoxLayout()
        drag_mode_label = QLabel("Modo:")
        drag_mode_label.setObjectName("statLabel")
        self.drag_mode_combo = QComboBox()
        self.drag_mode_combo.addItems(["Fixed (Chunks)", "Free (Píxel)"])
        self.drag_mode_combo.setCurrentIndex(0)
        self.drag_mode_combo.currentIndexChanged.connect(self.change_drag_mode)
        drag_mode_layout.addWidget(drag_mode_label)
        drag_mode_layout.addWidget(self.drag_mode_combo)
        image_coords_layout.addLayout(drag_mode_layout)

        self.coord_top_left_label = QLabel("🔺 Superior Izq: -")
        self.coord_top_left_label.setObjectName("statLabel")
        self.coord_top_right_label = QLabel("🔺 Superior Der: -")
        self.coord_top_right_label.setObjectName("statLabel")
        self.coord_bottom_left_label = QLabel("🔻 Inferior Izq: -")
        self.coord_bottom_left_label.setObjectName("statLabel")
        self.coord_bottom_right_label = QLabel("🔻 Inferior Der: -")
        self.coord_bottom_right_label.setObjectName("statLabel")

        image_coords_layout.addWidget(self.coord_top_left_label)
        image_coords_layout.addWidget(self.coord_top_right_label)
        image_coords_layout.addWidget(self.coord_bottom_left_label)
        image_coords_layout.addWidget(self.coord_bottom_right_label)

        self.record_button = QPushButton("⏺️ Grabar Movimiento")
        self.record_button.clicked.connect(self.toggle_recording)
        self.record_button.setObjectName("modernButton")
        self.record_button.setMinimumHeight(35)
        image_coords_layout.addWidget(self.record_button)

        self.play_button = QPushButton("▶️ Reproducir")
        self.play_button.clicked.connect(self.play_movement)
        self.play_button.setEnabled(False)
        image_coords_layout.addWidget(self.play_button)

        self.recorded_positions_label = QLabel("Posiciones grabadas: 0")
        self.recorded_positions_label.setObjectName("statLabel")
        image_coords_layout.addWidget(self.recorded_positions_label)

        self.image_coords_section.setContentWidget(image_coords_content)
        self.image_coords_section.setVisible(False)
        self.info_layout.addWidget(self.image_coords_section)

        self.grid_config_section = CollapsibleSection("📏 CONFIGURACIÓN GRID", self, expanded=False)
        grid_config_content = QWidget()
        grid_config_content.setObjectName("statsContainer")
        grid_config_layout = QVBoxLayout(grid_config_content)
        grid_config_layout.setContentsMargins(12, 12, 12, 12)
        grid_config_layout.setSpacing(8)

        width_layout = QHBoxLayout()
        width_label = QLabel("Ancho (W):")
        width_label.setObjectName("statLabel")
        self.grid_width_input = QLineEdit()
        self.grid_width_input.setText(str(self.grid_width))
        self.grid_width_input.setMaximumWidth(80)
        width_layout.addWidget(width_label)
        width_layout.addWidget(self.grid_width_input)
        width_layout.addStretch()
        grid_config_layout.addLayout(width_layout)

        height_layout = QHBoxLayout()
        height_label = QLabel("Alto (H):")
        height_label.setObjectName("statLabel")
        self.grid_height_input = QLineEdit()
        self.grid_height_input.setText(str(self.grid_height))
        self.grid_height_input.setMaximumWidth(80)
        height_layout.addWidget(height_label)
        height_layout.addWidget(self.grid_height_input)
        height_layout.addStretch()
        grid_config_layout.addLayout(height_layout)

        cell_layout = QHBoxLayout()
        cell_label = QLabel("Tamaño celda:")
        cell_label.setObjectName("statLabel")
        self.grid_cell_input = QLineEdit()
        self.grid_cell_input.setText(str(self.grid_cell_size))
        self.grid_cell_input.setMaximumWidth(80)
        cell_layout.addWidget(cell_label)
        cell_layout.addWidget(self.grid_cell_input)
        cell_layout.addStretch()
        grid_config_layout.addLayout(cell_layout)

        pixels_layout = QHBoxLayout()
        pixels_label = QLabel("Píxeles/celda:")
        pixels_label.setObjectName("statLabel")
        self.grid_pixels_input = QLineEdit()
        self.grid_pixels_input.setText(str(self.grid_pixels_per_cell))
        self.grid_pixels_input.setMaximumWidth(80)
        pixels_layout.addWidget(pixels_label)
        pixels_layout.addWidget(self.grid_pixels_input)
        pixels_layout.addStretch()
        grid_config_layout.addLayout(pixels_layout)

        unit_layout = QHBoxLayout()
        unit_label = QLabel("Unidad:")
        unit_label.setObjectName("statLabel")
        self.grid_unit_combo = QComboBox()
        self.grid_unit_combo.addItems(["nm", "µm", "mm", "cm", "m"])
        self.grid_unit_combo.setCurrentText(self.grid_unit)
        self.grid_unit_combo.setMaximumWidth(80)
        unit_layout.addWidget(unit_label)
        unit_layout.addWidget(self.grid_unit_combo)
        unit_layout.addStretch()
        grid_config_layout.addLayout(unit_layout)

        self.show_pixel_grid_checkbox = QCheckBox("🔍 Mostrar Grid de Píxeles")
        self.show_pixel_grid_checkbox.setChecked(self.show_pixel_grid)
        self.show_pixel_grid_checkbox.stateChanged.connect(self.toggle_pixel_grid)
        self.show_pixel_grid_checkbox.setObjectName("statLabel")
        grid_config_layout.addWidget(self.show_pixel_grid_checkbox)

        self.generate_grid_button = QPushButton("🎨 Generar Grid")
        self.generate_grid_button.clicked.connect(self.generate_grid)
        self.generate_grid_button.setObjectName("modernButton")
        self.generate_grid_button.setMinimumHeight(40)
        grid_config_layout.addWidget(self.generate_grid_button)

        self.grid_status_label = QLabel("Estado: No generado")
        self.grid_status_label.setObjectName("statLabel")
        grid_config_layout.addWidget(self.grid_status_label)

        self.grid_config_section.setContentWidget(grid_config_content)
        self.grid_config_section.setVisible(False)
        self.info_layout.addWidget(self.grid_config_section)

        # ═══════════════════════════════════════════════════════════════════════════
        # SECCIÓN SEGMENTACIÓN DE IMAGEN (PRE-PROCESAMIENTO LITOGRÁFICO)
        # ═══════════════════════════════════════════════════════════════════════════
        self.segmentation_section = CollapsibleSection("✂️ SEGMENTACIÓN DE IMAGEN", self, expanded=False)
        segmentation_content = QWidget()
        segmentation_content.setObjectName("statsContainer")
        segmentation_layout = QVBoxLayout(segmentation_content)
        segmentation_layout.setContentsMargins(12, 12, 12, 12)
        segmentation_layout.setSpacing(10)

        # Descripción
        seg_desc = QLabel("División de la imagen en segmentos/subcampos para exposición secuencial en stepper litográfico")
        seg_desc.setWordWrap(True)
        seg_desc.setStyleSheet("font-size: 10px; color: #888888;")
        segmentation_layout.addWidget(seg_desc)

        # Modo de segmentación
        seg_mode_layout = QHBoxLayout()
        seg_mode_label = QLabel("Modo:")
        seg_mode_label.setObjectName("statLabel")
        self.segmentation_mode_combo = QComboBox()
        self.segmentation_mode_combo.addItems([
            "Automático (usar grid)",
            "Manual (especificar)",
            "Por tamaño de campo",
            "Imagen Completa (sin slice)"
        ])
        self.segmentation_mode_combo.currentIndexChanged.connect(self.update_segmentation_mode)
        seg_mode_layout.addWidget(seg_mode_label)
        seg_mode_layout.addWidget(self.segmentation_mode_combo)
        segmentation_layout.addLayout(seg_mode_layout)

        # ═══════════════════════════════════════════════════════════════════════════
        # TRANSFORMACIONES DE IMAGEN (ROTACIÓN, ESPEJO, ETC.)
        # ═══════════════════════════════════════════════════════════════════════════
        transform_label = QLabel("🔄 Transformaciones:")
        transform_label.setObjectName("statLabel")
        transform_label.setStyleSheet("font-weight: bold; margin-top: 10px;")
        segmentation_layout.addWidget(transform_label)

        # Rotación con slider
        rotation_layout = QVBoxLayout()
        rotation_label_layout = QHBoxLayout()
        rotation_label = QLabel("Rotación:")
        rotation_label.setObjectName("statLabel")
        self.rotation_value_label = QLabel("0°")
        self.rotation_value_label.setObjectName("statLabel")
        self.rotation_value_label.setStyleSheet("font-weight: bold;")
        rotation_label_layout.addWidget(rotation_label)
        rotation_label_layout.addWidget(self.rotation_value_label)
        rotation_label_layout.addStretch()
        rotation_layout.addLayout(rotation_label_layout)
        
        self.rotation_slider = QSlider(Qt.Horizontal)
        self.rotation_slider.setMinimum(0)
        self.rotation_slider.setMaximum(360)
        self.rotation_slider.setValue(0)
        self.rotation_slider.setTickPosition(QSlider.TicksBelow)
        self.rotation_slider.setTickInterval(45)
        self.rotation_slider.setToolTip("Rotar imagen en sentido horario (0-360°)")
        self.rotation_slider.valueChanged.connect(self.update_image_transform)
        rotation_layout.addWidget(self.rotation_slider)
        
        segmentation_layout.addLayout(rotation_layout)

        # Espejos
        mirror_layout = QHBoxLayout()
        self.mirror_horizontal_checkbox = QCheckBox("↔️ Espejo Horizontal")
        self.mirror_horizontal_checkbox.setObjectName("statLabel")
        self.mirror_horizontal_checkbox.stateChanged.connect(self.update_image_transform)
        mirror_layout.addWidget(self.mirror_horizontal_checkbox)
        segmentation_layout.addLayout(mirror_layout)

        mirror_v_layout = QHBoxLayout()
        self.mirror_vertical_checkbox = QCheckBox("↕️ Espejo Vertical")
        self.mirror_vertical_checkbox.setObjectName("statLabel")
        self.mirror_vertical_checkbox.stateChanged.connect(self.update_image_transform)
        mirror_v_layout.addWidget(self.mirror_vertical_checkbox)
        segmentation_layout.addLayout(mirror_v_layout)

        # Configuración manual de segmentos
        self.manual_segments_widget = QWidget()
        manual_seg_layout = QVBoxLayout(self.manual_segments_widget)
        manual_seg_layout.setContentsMargins(0, 5, 0, 0)
        manual_seg_layout.setSpacing(6)

        segments_x_layout = QHBoxLayout()
        segments_x_label = QLabel("Segmentos X:")
        segments_x_label.setObjectName("statLabel")
        self.segments_x_spin = QSpinBox()
        self.segments_x_spin.setMinimum(1)
        self.segments_x_spin.setMaximum(100)
        self.segments_x_spin.setValue(4)
        self.segments_x_spin.valueChanged.connect(self.update_segmentation_preview)
        segments_x_layout.addWidget(segments_x_label)
        segments_x_layout.addWidget(self.segments_x_spin)
        segments_x_layout.addStretch()
        manual_seg_layout.addLayout(segments_x_layout)

        segments_y_layout = QHBoxLayout()
        segments_y_label = QLabel("Segmentos Y:")
        segments_y_label.setObjectName("statLabel")
        self.segments_y_spin = QSpinBox()
        self.segments_y_spin.setMinimum(1)
        self.segments_y_spin.setMaximum(100)
        self.segments_y_spin.setValue(4)
        self.segments_y_spin.valueChanged.connect(self.update_segmentation_preview)
        segments_y_layout.addWidget(segments_y_label)
        segments_y_layout.addWidget(self.segments_y_spin)
        segments_y_layout.addStretch()
        manual_seg_layout.addLayout(segments_y_layout)

        self.manual_segments_widget.setVisible(False)
        segmentation_layout.addWidget(self.manual_segments_widget)

        # Información de segmentación
        self.segment_info_label = QLabel("Total de segmentos: -")
        self.segment_info_label.setObjectName("statLabel")
        self.segment_info_label.setStyleSheet("font-size: 10px; font-weight: bold;")
        segmentation_layout.addWidget(self.segment_info_label)

        self.segment_size_label = QLabel("Tamaño por segmento: -")
        self.segment_size_label.setObjectName("statLabel")
        self.segment_size_label.setStyleSheet("font-size: 10px;")
        segmentation_layout.addWidget(self.segment_size_label)

        self.segment_overlap_label = QLabel("Solapamiento: 0%")
        self.segment_overlap_label.setObjectName("statLabel")
        self.segment_overlap_label.setStyleSheet("font-size: 10px;")
        segmentation_layout.addWidget(self.segment_overlap_label)

        # Botón para aplicar segmentación
        self.apply_segmentation_button = QPushButton("✂️ Aplicar Segmentación")
        self.apply_segmentation_button.setObjectName("modernButton")
        self.apply_segmentation_button.clicked.connect(self.apply_image_segmentation)
        self.apply_segmentation_button.setToolTip("Divide la imagen según la configuración de segmentos")
        segmentation_layout.addWidget(self.apply_segmentation_button)

        # Checkbox para mostrar overlay de segmentos
        self.show_segments_overlay_checkbox = QCheckBox("Mostrar overlay de segmentos en grid")
        self.show_segments_overlay_checkbox.setChecked(False)
        self.show_segments_overlay_checkbox.setObjectName("statLabel")
        self.show_segments_overlay_checkbox.stateChanged.connect(self.toggle_segments_overlay)
        segmentation_layout.addWidget(self.show_segments_overlay_checkbox)

        self.segmentation_section.setContentWidget(segmentation_content)
        self.segmentation_section.setVisible(False)
        self.info_layout.addWidget(self.segmentation_section)

        self.info_layout.addSpacing(20)

        tabs_layout = QHBoxLayout()
        self.exposure_tab_button = QPushButton("⏱️ EXPOSICIÓN")
        self.exposure_tab_button.setCheckable(True)
        self.exposure_tab_button.setChecked(True)
        self.exposure_tab_button.clicked.connect(self.show_exposure_section)
        self.exposure_tab_button.setObjectName("tabButton")

        self.frequency_tab_button = QPushButton(" FRECUENCIA")
        self.frequency_tab_button.setCheckable(True)
        self.frequency_tab_button.clicked.connect(self.show_frequency_section)
        self.frequency_tab_button.setObjectName("tabButton")

        tabs_layout.addWidget(self.exposure_tab_button)
        tabs_layout.addWidget(self.frequency_tab_button)
        self.info_layout.addLayout(tabs_layout)

        self.exposure_section = CollapsibleSection("⏱️ EXPOSICIÓN", self, expanded=True)
        exposure_content = QWidget()
        exposure_content.setObjectName("statsContainer")
        exposure_layout = QVBoxLayout(exposure_content)
        exposure_layout.setContentsMargins(12, 12, 12, 12)
        exposure_layout.setSpacing(8)

        time_layout = QHBoxLayout()
        time_label = QLabel("Tiempo (segundos):")
        time_label.setObjectName("statLabel")
        self.exposure_time_input = QLineEdit()
        self.exposure_time_input.setText("10")
        self.exposure_time_input.setPlaceholderText("Ej: 5")
        self.exposure_time_input.setMaximumWidth(80)
        time_layout.addWidget(time_label)
        time_layout.addWidget(self.exposure_time_input)
        time_layout.addStretch()

        intensity_layout = QHBoxLayout()
        intensity_label = QLabel("Intensidad (%):")
        intensity_label.setObjectName("statLabel")
        self.exposure_intensity_input = QLineEdit()
        self.exposure_intensity_input.setText("100")
        self.exposure_intensity_input.setPlaceholderText("0-100")
        self.exposure_intensity_input.setMaximumWidth(80)
        intensity_layout.addWidget(intensity_label)
        intensity_layout.addWidget(self.exposure_intensity_input)
        intensity_layout.addStretch()

        freq_layout = QHBoxLayout()
        freq_label = QLabel("Ciclos:")
        freq_label.setObjectName("statLabel")
        self.exposure_cycles_input = QLineEdit()
        self.exposure_cycles_input.setText("1")
        self.exposure_cycles_input.setPlaceholderText("Ej: 3")
        self.exposure_cycles_input.setMaximumWidth(80)
        freq_layout.addWidget(freq_label)
        freq_layout.addWidget(self.exposure_cycles_input)
        freq_layout.addStretch()

        # Botón para proyectar imagen manualmente
        self.project_image_button = QPushButton("🖼️ Proyectar Imagen Completa")
        self.project_image_button.clicked.connect(self.project_full_image)
        self.project_image_button.setVisible(False)
        self.project_image_button.setToolTip("Proyecta la imagen completa en el monitor secundario")
        
        self.exposure_button = QPushButton("▶️ Iniciar Exposición")
        self.exposure_button.clicked.connect(self.start_timed_exposure)
        self.exposure_button.setVisible(False)

        self.stop_exposure_button = QPushButton("⏹️ Detener")
        self.stop_exposure_button.clicked.connect(self.force_stop_exposure)
        self.stop_exposure_button.setVisible(False)

        self.exposure_status_label = QLabel("Estado: Inactivo")
        self.exposure_status_label.setObjectName("statLabel")

        exposure_layout.addLayout(time_layout)
        exposure_layout.addLayout(intensity_layout)
        exposure_layout.addLayout(freq_layout)
        exposure_layout.addWidget(self.project_image_button)
        exposure_layout.addWidget(self.exposure_button)
        exposure_layout.addWidget(self.stop_exposure_button)
        exposure_layout.addWidget(self.exposure_status_label)

        self.exposure_section.setContentWidget(exposure_content)
        self.info_layout.addWidget(self.exposure_section)

        self.frequency_section = CollapsibleSection(" FRECUENCIA", self, expanded=False)
        frequency_content = QWidget()
        frequency_content.setObjectName("statsContainer")
        frequency_main_layout = QVBoxLayout(frequency_content)
        frequency_main_layout.setContentsMargins(12, 12, 12, 12)
        frequency_main_layout.setSpacing(8)

        frequency_input_layout = QHBoxLayout()
        frequency_value_label = QLabel("Frecuencia:")
        frequency_value_label.setObjectName("statLabel")
        self.frequency_value_input = QLineEdit()
        self.frequency_value_input.setText("1")
        self.frequency_value_input.setPlaceholderText("Ej: 2.5")
        self.frequency_value_input.setMaximumWidth(80)

        self.frequency_unit_combo = QComboBox()
        self.frequency_unit_combo.addItems(["Hz", "kHz", "MHz"])
        self.frequency_unit_combo.setMaximumWidth(80)

        frequency_input_layout.addWidget(frequency_value_label)
        frequency_input_layout.addWidget(self.frequency_value_input)
        frequency_input_layout.addWidget(self.frequency_unit_combo)
        frequency_input_layout.addStretch()

        duration_layout = QHBoxLayout()
        duration_label = QLabel("Duración (segundos):")
        duration_label.setObjectName("statLabel")
        self.frequency_duration_input = QLineEdit()
        self.frequency_duration_input.setText("60")
        self.frequency_duration_input.setPlaceholderText("0 = infinito")
        self.frequency_duration_input.setMaximumWidth(80)
        duration_layout.addWidget(duration_label)
        duration_layout.addWidget(self.frequency_duration_input)
        duration_layout.addStretch()

        self.frequency_button = QPushButton("🌊 Iniciar Modo Frecuencia")
        self.frequency_button.clicked.connect(self.start_frequency_mode)
        self.frequency_button.setVisible(False)

        self.stop_frequency_button = QPushButton("⏹️ Detener Frecuencia")
        self.stop_frequency_button.clicked.connect(self.force_stop_frequency)
        self.stop_frequency_button.setVisible(False)

        self.frequency_status_label = QLabel("Estado: Inactivo")
        self.frequency_status_label.setObjectName("statLabel")

        frequency_main_layout.addLayout(frequency_input_layout)
        frequency_main_layout.addLayout(duration_layout)
        frequency_main_layout.addWidget(self.frequency_button)
        frequency_main_layout.addWidget(self.stop_frequency_button)
        frequency_main_layout.addWidget(self.frequency_status_label)

        self.frequency_section.setContentWidget(frequency_content)
        self.frequency_section.setVisible(False)
        self.info_layout.addWidget(self.frequency_section)

        # ═══════════════════════════════════════════════════════════════════════════
        # SECCIÓN CONTROL DE PROYECCIÓN Y STEPPER
        # ═══════════════════════════════════════════════════════════════════════════
        self.projection_control_section = CollapsibleSection("🎬 CONTROL DE PROYECCIÓN", self, expanded=False)
        projection_control_content = QWidget()
        projection_control_content.setObjectName("statsContainer")
        projection_control_layout = QVBoxLayout(projection_control_content)
        projection_control_layout.setContentsMargins(12, 12, 12, 12)
        projection_control_layout.setSpacing(10)

        # ─── Downscaling de Imagen ───
        downscale_group = QWidget()
        downscale_layout = QVBoxLayout(downscale_group)
        downscale_layout.setContentsMargins(0, 0, 0, 0)
        downscale_layout.setSpacing(6)
        
        downscale_title = QLabel("📐 Factor de Reducción (Downscaling)")
        downscale_title.setStyleSheet("font-weight: bold; font-size: 11px;")
        downscale_layout.addWidget(downscale_title)
        
        downscale_desc = QLabel("Reduce la imagen proyectada para lograr la resolución final deseada en el sustrato (típico de steppers)")
        downscale_desc.setWordWrap(True)
        downscale_desc.setStyleSheet("font-size: 10px; color: #888888;")
        downscale_layout.addWidget(downscale_desc)
        
        # Control de factor de downscaling
        downscale_control_layout = QHBoxLayout()
        downscale_label = QLabel("Factor:")
        downscale_label.setObjectName("statLabel")
        
        self.downscale_factor_spin = QDoubleSpinBox()
        self.downscale_factor_spin.setMinimum(0.1)
        self.downscale_factor_spin.setMaximum(10.0)
        self.downscale_factor_spin.setValue(1.0)
        self.downscale_factor_spin.setSingleStep(0.1)
        self.downscale_factor_spin.setDecimals(2)
        self.downscale_factor_spin.setSuffix("x")
        self.downscale_factor_spin.setToolTip("Factor de reducción: <1 reduce tamaño, >1 aumenta tamaño")
        self.downscale_factor_spin.valueChanged.connect(self.update_downscale_factor)
        
        downscale_control_layout.addWidget(downscale_label)
        downscale_control_layout.addWidget(self.downscale_factor_spin)
        downscale_control_layout.addStretch()
        downscale_layout.addLayout(downscale_control_layout)
        
        # Información de resolución resultante
        self.downscale_info_label = QLabel("Resolución resultante: -")
        self.downscale_info_label.setObjectName("statLabel")
        self.downscale_info_label.setStyleSheet("font-size: 10px;")
        downscale_layout.addWidget(self.downscale_info_label)
        
        projection_control_layout.addWidget(downscale_group)
        projection_control_layout.addSpacing(15)
        
        # ─── Consola de Secuencias ───
        sequence_group = QWidget()
        sequence_layout = QVBoxLayout(sequence_group)
        sequence_layout.setContentsMargins(0, 0, 0, 0)
        sequence_layout.setSpacing(6)
        
        sequence_title = QLabel("🎮 Consola de Secuencias")
        sequence_title.setStyleSheet("font-weight: bold; font-size: 11px;")
        sequence_layout.addWidget(sequence_title)
        
        sequence_desc = QLabel("Gestión de secuencias de movimiento (stage/platina) y activación de proyección (shutter)")
        sequence_desc.setWordWrap(True)
        sequence_desc.setStyleSheet("font-size: 10px; color: #888888;")
        sequence_layout.addWidget(sequence_desc)
        
        # Estado de secuencia actual
        self.sequence_status_label = QLabel("Estado: ⏸️ Inactivo")
        self.sequence_status_label.setObjectName("statLabel")
        sequence_layout.addWidget(self.sequence_status_label)
        
        # Información de segmento actual
        segment_info_layout = QHBoxLayout()
        self.current_segment_label = QLabel("Segmento: 0/0")
        self.current_segment_label.setObjectName("statLabel")
        self.segment_progress_bar = QProgressBar()
        self.segment_progress_bar.setMaximum(100)
        self.segment_progress_bar.setValue(0)
        self.segment_progress_bar.setMaximumHeight(15)
        segment_info_layout.addWidget(self.current_segment_label)
        segment_info_layout.addWidget(self.segment_progress_bar, stretch=1)
        sequence_layout.addLayout(segment_info_layout)
        
        # Botones de control de secuencia
        sequence_buttons_layout = QHBoxLayout()
        
        self.sequence_start_button = QPushButton("▶️ Iniciar")
        self.sequence_start_button.setObjectName("modernButton")
        self.sequence_start_button.clicked.connect(self.start_sequence)
        self.sequence_start_button.setToolTip("Inicia la secuencia de proyección con los segmentos del grid")
        
        self.sequence_pause_button = QPushButton("⏸️ Pausar")
        self.sequence_pause_button.setObjectName("modernButton")
        self.sequence_pause_button.clicked.connect(self.pause_sequence)
        self.sequence_pause_button.setEnabled(False)
        
        self.sequence_stop_button = QPushButton("⏹️ Detener")
        self.sequence_stop_button.setObjectName("modernButton")
        self.sequence_stop_button.clicked.connect(self.stop_sequence)
        self.sequence_stop_button.setEnabled(False)
        
        sequence_buttons_layout.addWidget(self.sequence_start_button)
        sequence_buttons_layout.addWidget(self.sequence_pause_button)
        sequence_buttons_layout.addWidget(self.sequence_stop_button)
        sequence_layout.addLayout(sequence_buttons_layout)
        
        # Opciones de secuencia
        sequence_options_layout = QVBoxLayout()
        
        self.auto_shutter_checkbox = QCheckBox("Shutter automático por segmento")
        self.auto_shutter_checkbox.setChecked(True)
        self.auto_shutter_checkbox.setObjectName("statLabel")
        self.auto_shutter_checkbox.setToolTip("Activa/desactiva la proyección automáticamente en cada segmento")
        sequence_options_layout.addWidget(self.auto_shutter_checkbox)
        
        self.auto_movement_checkbox = QCheckBox("Movimiento automático de stage")
        self.auto_movement_checkbox.setChecked(True)
        self.auto_movement_checkbox.setObjectName("statLabel")
        self.auto_movement_checkbox.setToolTip("Mueve la platina automáticamente entre segmentos")
        sequence_options_layout.addWidget(self.auto_movement_checkbox)
        
        sequence_layout.addLayout(sequence_options_layout)
        
        # Tiempo de exposición (imagen visible)
        exposure_time_layout = QHBoxLayout()
        exposure_time_label = QLabel("⏱️ Tiempo de exposición:")
        exposure_time_label.setObjectName("statLabel")
        self.exposure_time_spin = QDoubleSpinBox()
        self.exposure_time_spin.setMinimum(0.001)  # Mínimo 1ms
        self.exposure_time_spin.setMaximum(60.0)   # Máximo 60 segundos
        self.exposure_time_spin.setValue(0.5)
        self.exposure_time_spin.setSingleStep(0.1)
        self.exposure_time_spin.setDecimals(3)
        self.exposure_time_spin.setSuffix(" s")
        self.exposure_time_spin.setToolTip("Tiempo que se muestra cada segmento (exposición)")
        exposure_time_layout.addWidget(exposure_time_label)
        exposure_time_layout.addWidget(self.exposure_time_spin)
        exposure_time_layout.addStretch()
        sequence_layout.addLayout(exposure_time_layout)
        
        # Tiempo de movimiento (pantalla negra)
        movement_time_layout = QHBoxLayout()
        movement_time_label = QLabel("🚀 Tiempo de movimiento:")
        movement_time_label.setObjectName("statLabel")
        self.movement_time_spin = QDoubleSpinBox()
        self.movement_time_spin.setMinimum(0.0)    # Puede ser 0 si no hay movimiento
        self.movement_time_spin.setMaximum(60.0)   # Máximo 60 segundos
        self.movement_time_spin.setValue(0.2)
        self.movement_time_spin.setSingleStep(0.1)
        self.movement_time_spin.setDecimals(3)
        self.movement_time_spin.setSuffix(" s")
        self.movement_time_spin.setToolTip("Tiempo para mover stage entre segmentos (pantalla negra)")
        movement_time_layout.addWidget(movement_time_label)
        movement_time_layout.addWidget(self.movement_time_spin)
        movement_time_layout.addStretch()
        sequence_layout.addLayout(movement_time_layout)
        
        projection_control_layout.addWidget(sequence_group)
        
        self.projection_control_section.setContentWidget(projection_control_content)
        self.projection_control_section.setVisible(False)
        self.info_layout.addWidget(self.projection_control_section)

        # ═══════════════════════════════════════════════════════════════════════════
        # SECCIÓN MONITOREO DE CALIBRACIÓN Y EFECTOS EN TIEMPO REAL
        # ═══════════════════════════════════════════════════════════════════════════
        self.calibration_monitor_section = CollapsibleSection("🔍 MONITOREO DE CALIBRACIÓN", self, expanded=True)
        calibration_monitor_content = QWidget()
        calibration_monitor_content.setObjectName("statsContainer")
        calibration_monitor_layout = QVBoxLayout(calibration_monitor_content)
        calibration_monitor_layout.setContentsMargins(12, 12, 12, 12)
        calibration_monitor_layout.setSpacing(8)

        monitor_desc = QLabel("Estado en tiempo real de efectos aplicados a la proyección")
        monitor_desc.setWordWrap(True)
        monitor_desc.setStyleSheet("font-size: 10px; color: #888888;")
        calibration_monitor_layout.addWidget(monitor_desc)

        # ─── Estado de Calibración ───
        calib_status_title = QLabel("📊 Estado de Calibración:")
        calib_status_title.setStyleSheet("font-weight: bold; font-size: 10px; margin-top: 5px;")
        calibration_monitor_layout.addWidget(calib_status_title)
        
        self.calib_status_label = QLabel("❌ Sin calibración cargada")
        self.calib_status_label.setObjectName("statLabel")
        self.calib_status_label.setStyleSheet("font-size: 10px; color: #FF6B6B;")
        calibration_monitor_layout.addWidget(self.calib_status_label)
        
        self.calib_apply_status_label = QLabel("⚪ Aplicación: Inactiva")
        self.calib_apply_status_label.setObjectName("statLabel")
        self.calib_apply_status_label.setStyleSheet("font-size: 10px;")
        calibration_monitor_layout.addWidget(self.calib_apply_status_label)

        # ─── Parámetros de Atenuación ───
        atten_title = QLabel("🔧 Parámetros de Atenuación:")
        atten_title.setStyleSheet("font-weight: bold; font-size: 10px; margin-top: 8px;")
        calibration_monitor_layout.addWidget(atten_title)
        
        self.atten_threshold_label = QLabel("• Threshold: -")
        self.atten_threshold_label.setObjectName("statLabel")
        self.atten_threshold_label.setStyleSheet("font-size: 10px;")
        calibration_monitor_layout.addWidget(self.atten_threshold_label)
        
        self.atten_min_label = QLabel("• Valor mínimo: -")
        self.atten_min_label.setObjectName("statLabel")
        self.atten_min_label.setStyleSheet("font-size: 10px;")
        calibration_monitor_layout.addWidget(self.atten_min_label)
        
        self.atten_max_label = QLabel("• Valor máximo: -")
        self.atten_max_label.setObjectName("statLabel")
        self.atten_max_label.setStyleSheet("font-size: 10px;")
        calibration_monitor_layout.addWidget(self.atten_max_label)

        # ─── Efectos Activos ───
        effects_title = QLabel("⚡ Efectos Activos:")
        effects_title.setStyleSheet("font-weight: bold; font-size: 10px; margin-top: 8px;")
        calibration_monitor_layout.addWidget(effects_title)
        
        self.effect_sigma_label = QLabel("• Sigma (Blur): -")
        self.effect_sigma_label.setObjectName("statLabel")
        self.effect_sigma_label.setStyleSheet("font-size: 10px;")
        calibration_monitor_layout.addWidget(self.effect_sigma_label)
        
        self.effect_downscale_label = QLabel("• Downscaling: -")
        self.effect_downscale_label.setObjectName("statLabel")
        self.effect_downscale_label.setStyleSheet("font-size: 10px;")
        calibration_monitor_layout.addWidget(self.effect_downscale_label)
        
        self.effect_brightness_label = QLabel("• Brillo: -")
        self.effect_brightness_label.setObjectName("statLabel")
        self.effect_brightness_label.setStyleSheet("font-size: 10px;")
        calibration_monitor_layout.addWidget(self.effect_brightness_label)
        
        self.effect_binary_label = QLabel("• Modo Binario: -")
        self.effect_binary_label.setObjectName("statLabel")
        self.effect_binary_label.setStyleSheet("font-size: 10px;")
        calibration_monitor_layout.addWidget(self.effect_binary_label)
        
        self.effect_invert_label = QLabel("• Inversión: -")
        self.effect_invert_label.setObjectName("statLabel")
        self.effect_invert_label.setStyleSheet("font-size: 10px;")
        calibration_monitor_layout.addWidget(self.effect_invert_label)

        # ─── Última Proyección ───
        projection_title = QLabel("🖥️ Última Proyección:")
        projection_title.setStyleSheet("font-weight: bold; font-size: 10px; margin-top: 8px;")
        calibration_monitor_layout.addWidget(projection_title)
        
        self.last_projection_size_label = QLabel("• Tamaño: -")
        self.last_projection_size_label.setObjectName("statLabel")
        self.last_projection_size_label.setStyleSheet("font-size: 10px;")
        calibration_monitor_layout.addWidget(self.last_projection_size_label)
        
        self.last_projection_values_label = QLabel("• Valores: -")
        self.last_projection_values_label.setObjectName("statLabel")
        self.last_projection_values_label.setStyleSheet("font-size: 10px;")
        calibration_monitor_layout.addWidget(self.last_projection_values_label)

        # ─── Preview de Calibración (Antes/Después) ───
        preview_title = QLabel("🔬 Preview Calibración:")
        preview_title.setStyleSheet("font-weight: bold; font-size: 10px; margin-top: 8px;")
        calibration_monitor_layout.addWidget(preview_title)
        
        # Canvas para mostrar antes/después (using global imports from lines 89-90)
        self.calib_preview_figure = Figure(figsize=(3, 2), dpi=80)
        self.calib_preview_canvas = FigureCanvas(self.calib_preview_figure)
        self.calib_preview_canvas.setMinimumHeight(150)
        self.calib_preview_canvas.setMaximumHeight(200)
        calibration_monitor_layout.addWidget(self.calib_preview_canvas)
        
        # Slider para ajustar strength en tiempo real
        strength_layout = QHBoxLayout()
        strength_label = QLabel("Intensidad:")
        strength_label.setObjectName("statLabel")
        strength_label.setStyleSheet("font-size: 10px;")
        
        self.calib_preview_strength_slider = QSlider(Qt.Horizontal)
        self.calib_preview_strength_slider.setMinimum(0)
        self.calib_preview_strength_slider.setMaximum(100)
        self.calib_preview_strength_slider.setValue(100)
        self.calib_preview_strength_slider.setToolTip("Ajusta la intensidad de la calibración en el preview")
        self.calib_preview_strength_slider.valueChanged.connect(self.update_calibration_preview)
        
        self.calib_preview_strength_value = QLabel("100%")
        self.calib_preview_strength_value.setObjectName("statLabel")
        self.calib_preview_strength_value.setStyleSheet("font-size: 10px; min-width: 35px;")
        
        strength_layout.addWidget(strength_label)
        strength_layout.addWidget(self.calib_preview_strength_slider)
        strength_layout.addWidget(self.calib_preview_strength_value)
        calibration_monitor_layout.addLayout(strength_layout)
        
        # Botones de control de preview
        preview_buttons_layout = QHBoxLayout()
        
        self.calib_show_before_btn = QPushButton("👁️ Ver Original")
        self.calib_show_before_btn.setObjectName("modernButton")
        self.calib_show_before_btn.clicked.connect(lambda: self.update_calibration_preview(show_mode='before'))
        self.calib_show_before_btn.setToolTip("Muestra la imagen sin calibración")
        
        self.calib_show_after_btn = QPushButton("✨ Ver Calibrado")
        self.calib_show_after_btn.setObjectName("modernButton")
        self.calib_show_after_btn.clicked.connect(lambda: self.update_calibration_preview(show_mode='after'))
        self.calib_show_after_btn.setToolTip("Muestra la imagen con calibración aplicada")
        
        preview_buttons_layout.addWidget(self.calib_show_before_btn)
        preview_buttons_layout.addWidget(self.calib_show_after_btn)
        calibration_monitor_layout.addLayout(preview_buttons_layout)
        
        # ─── Controles de Orientación de Matriz ───
        flip_title = QLabel("🔄 Orientación de Matriz:")
        flip_title.setStyleSheet("font-weight: bold; font-size: 10px; margin-top: 8px;")
        calibration_monitor_layout.addWidget(flip_title)
        
        flip_controls_layout = QHBoxLayout()
        
        self.calib_flip_x_checkbox = QCheckBox("↔️ Invertir X")
        self.calib_flip_x_checkbox.setObjectName("modernCheckbox")
        self.calib_flip_x_checkbox.setToolTip("Invierte la matriz de calibración horizontalmente (eje X)")
        self.calib_flip_x_checkbox.setChecked(self.calibration_flip_x)
        self.calib_flip_x_checkbox.stateChanged.connect(self.toggle_calibration_flip_x)
        
        self.calib_flip_y_checkbox = QCheckBox("↕️ Invertir Y")
        self.calib_flip_y_checkbox.setObjectName("modernCheckbox")
        self.calib_flip_y_checkbox.setToolTip("Invierte la matriz de calibración verticalmente (eje Y)")
        self.calib_flip_y_checkbox.setChecked(self.calibration_flip_y)
        self.calib_flip_y_checkbox.stateChanged.connect(self.toggle_calibration_flip_y)
        
        flip_controls_layout.addWidget(self.calib_flip_x_checkbox)
        flip_controls_layout.addWidget(self.calib_flip_y_checkbox)
        calibration_monitor_layout.addLayout(flip_controls_layout)

        # Botón para actualizar manualmente
        update_monitor_btn = QPushButton("🔄 Actualizar Monitor")
        update_monitor_btn.setObjectName("modernButton")
        update_monitor_btn.clicked.connect(self.update_calibration_monitor)
        update_monitor_btn.setToolTip("Actualiza la información del monitor de calibración")
        calibration_monitor_layout.addWidget(update_monitor_btn)

        self.calibration_monitor_section.setContentWidget(calibration_monitor_content)
        self.info_layout.addWidget(self.calibration_monitor_section)

        self.info_layout.addSpacing(20)

        files_title = QLabel("📁 ARCHIVOS")
        files_title.setObjectName("sectionTitle")
        self.info_layout.addWidget(files_title)

        self.file_tree = QTreeWidget()
        self.file_tree.setHeaderLabel("")
        self.file_tree.setHeaderHidden(True)
        self.file_tree.setContextMenuPolicy(Qt.CustomContextMenu)
        self.file_tree.customContextMenuRequested.connect(self.show_context_menu)
        self.file_tree.itemDoubleClicked.connect(self.load_from_tree)
        self.file_tree.setIconSize(QSize(56, 56))
        self.file_tree.setMinimumWidth(280)
        self.file_tree.setMinimumHeight(400)
        self.file_tree.setObjectName("fileTree")
        self.update_file_tree()

        self.info_layout.addWidget(self.file_tree, stretch=1)

        info_widget = QWidget()
        info_widget.setLayout(self.info_layout)

        scroll_area = QScrollArea()
        scroll_area.setWidget(info_widget)
        scroll_area.setWidgetResizable(True)
        scroll_area.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        scroll_area.setMinimumWidth(420)
        scroll_area.setMaximumWidth(550)


        self.canvas_with_toolbar = QVBoxLayout()
        self.toolbar = NavigationToolbar(self.canvas, self)
        self.customize_toolbar()
        self.toolbar.setVisible(False)  # Oculta por defecto, solo visible en modo grid
        self.canvas_with_toolbar.addWidget(self.toolbar)
        self.canvas_with_toolbar.addWidget(self.canvas)
        
        # Variables para manejo de imagen en grid (precisión float para litografía)
        self.image_on_grid = None
        self.image_position = [0.0, 0.0]  # float: posición en píxeles del grid [x, y]
        self.drag_mode = "fixed"  # "free" o "fixed"
        self.dragging_image = False
        self.drag_start_pos = None  # float: [x, y] en unidades del grid
        
        #variables para grabación de movimientos
        self.recording = False
        self.recorded_positions = []
        self.playback_active = False
        self.playback_timer = QTimer()
        self.playback_timer.timeout.connect(self.playback_step)
        self.playback_index = 0

        canvas_layout = QHBoxLayout()
        canvas_layout.addLayout(self.canvas_with_toolbar, stretch=3)
        canvas_layout.addWidget(scroll_area, stretch=1)

        # ═══════════════════════════════════════════════════════════════════════════
        # MINI CONSOLA DE SISTEMA
        # ═══════════════════════════════════════════════════════════════════════════
        console_section = CollapsibleSection("📋 Consola del Sistema", expanded=False)
        console_content = QWidget()
        console_layout = QVBoxLayout(console_content)
        console_layout.setContentsMargins(5, 5, 5, 5)
        
        # Crear mini consola de texto
        self.system_console = QTextEdit()
        self.system_console.setReadOnly(True)
        self.system_console.setMaximumHeight(150)
        self.system_console.setPlaceholderText("Los mensajes del sistema aparecerán aquí...")
        
        # Botón para limpiar consola
        clear_console_btn = QPushButton("🗑️ Limpiar Consola")
        clear_console_btn.clicked.connect(self.clear_console)
        
        console_layout.addWidget(self.system_console)
        console_layout.addWidget(clear_console_btn)
        console_section.setContentWidget(console_content)

        main_layout.addLayout(control_layout)
        main_layout.addLayout(canvas_layout)
        main_layout.addWidget(console_section)
        self.setLayout(main_layout)

        self.apply_theme()
        
        app = QApplication.instance()
        app.screenAdded.connect(self.on_screen_changed)
        app.screenRemoved.connect(self.on_screen_changed)
        for screen in app.screens():
            screen.geometryChanged.connect(self.on_screen_changed)

    def set_dark_titlebar(self):
        try:
            if sys.platform == "win32":
                hwnd = int(self.winId())

                DWMWA_USE_IMMERSIVE_DARK_MODE = 20

                value = ctypes.c_int(1)

                ctypes.windll.dwmapi.DwmSetWindowAttribute(
                    hwnd,
                    DWMWA_USE_IMMERSIVE_DARK_MODE,
                    ctypes.byref(value),
                    ctypes.sizeof(value),
                )
        except Exception as e:
            print(f"No se pudo aplicar barra de título oscura: {e}")

    def customize_toolbar(self):
        """Personaliza la toolbar de matplotlib, eliminando botones innecesarios"""
        # Obtener todas las acciones
        actions = self.toolbar.actions()
        
        # Nombres de las acciones a eliminar
        actions_to_remove = ['Save', 'Subplots', 'Customize']
        
        for action in actions:
            # Eliminar acciones no deseadas
            if action.text() in actions_to_remove:
                self.toolbar.removeAction(action)
        
        # Actualizar tooltips para hacerlos más descriptivos
        for action in self.toolbar.actions():
            if action.text() == 'Home':
                action.setToolTip('🏠 Vista inicial')
            elif action.text() == 'Back':
                action.setToolTip('◀ Retroceder vista')
            elif action.text() == 'Forward':
                action.setToolTip('▶ Avanzar vista')
            elif action.text() == 'Pan':
                action.setToolTip('✋ Mover/Zoom (Click: mover, Arrastrar: zoom)')

    def showEvent(self, event):
        super().showEvent(event)
        self.set_dark_titlebar()

    def closeEvent(self, event):
        if self.projection_window is not None:
            self.projection_window.close()
            self.projection_window = None
        super().closeEvent(event)

    def check_second_monitor(self):
        """
        Detecta el monitor secundario y gestiona dinámicamente la interfaz de proyección.
        Los campos de resolución se deshabilitan/ocultan si no hay monitor externo detectado.
        """
        screens = QApplication.screens()
        has_second = len(screens) > 1
        
        # Gestionar visibilidad y estado de campos relacionados con proyección
        if hasattr(self, 'monitor_resolution_label'):
            if has_second:
                # Monitor secundario detectado - mostrar información con indicador verde
                secondary = screens[1]
                geometry = secondary.geometry()
                self.monitor_resolution_label.setText(
                    f"✓ Monitor proyección: {geometry.width()}x{geometry.height()}"
                )
                self.monitor_resolution_label.setStyleSheet(
                    "color: #00FF00;" if self.dark_mode else "color: #008800;"
                )
                self.monitor_resolution_label.setVisible(True)
                
                # Habilitar el botón de proyección
                if hasattr(self, 'projector_button'):
                    self.projector_button.setEnabled(True)
                    self.projector_button.setToolTip("Activar/desactivar proyección en monitor secundario")
            else:
                # Sin monitor secundario - mostrar advertencia clara
                self.monitor_resolution_label.setText("⚠️ Monitor externo no detectado")
                self.monitor_resolution_label.setStyleSheet(
                    "color: #FF6B6B; font-weight: bold;"
                )
                self.monitor_resolution_label.setVisible(True)
                
                # Deshabilitar el botón de proyección si no hay proyección activa
                if hasattr(self, 'projector_button'):
                    if not self.projector_active:
                        self.projector_button.setEnabled(False)
                        self.projector_button.setToolTip(
                            "⚠️ Conecte un monitor secundario para usar la proyección"
                        )
        
        # Gestionar campos de resolución proyectada
        if hasattr(self, 'projected_resolution_label'):
            if has_second and self.projector_active:
                # Mostrar solo si hay monitor Y proyección activa
                self.projected_resolution_label.setVisible(True)
            else:
                # Ocultar si no hay monitor o no hay proyección
                self.projected_resolution_label.setVisible(False)
        
        # Gestionar escala de proyección
        if hasattr(self, 'scale_info_label'):
            if has_second and self.projector_active:
                self.scale_info_label.setVisible(True)
            else:
                self.scale_info_label.setVisible(False)
        
        return has_second

    def _update_projection_resolution_fields(self, show):
        """
        Gestiona dinámicamente la visibilidad de los campos de resolución de proyección.
        
        Args:
            show (bool): True para mostrar los campos, False para ocultarlos
        """
        # Campo de resolución proyectada
        if hasattr(self, 'projected_resolution_label'):
            self.projected_resolution_label.setVisible(show)
        
        # Campo de escala de proyección
        if hasattr(self, 'scale_info_label'):
            self.scale_info_label.setVisible(show)
        
        # Si se ocultan, limpiar valores para evitar confusión
        if not show:
            if hasattr(self, 'projected_resolution_label'):
                self.projected_resolution_label.setText("Resolución proyectada: -")
            if hasattr(self, 'scale_info_label'):
                self.scale_info_label.setText("Escala proyección: -")

    def on_screen_changed(self):
        """
        Se llama cuando cambia la configuración de monitores.
        Actualiza dinámicamente la interfaz según disponibilidad del monitor.
        """
        has_monitor = self.check_second_monitor()
        
        # Si hay una proyección activa, actualizar su geometría
        if self.projection_window and self.projection_window.isVisible():
            screens = QApplication.screens()
            if len(screens) > 1:
                secondary_screen = screens[1]
            else:
                # Si se desconectó el monitor secundario durante la proyección
                if has_monitor:
                    secondary_screen = screens[0]
                else:
                    # Cerrar proyección si se perdió el monitor
                    QMessageBox.warning(
                        self,
                        "Monitor desconectado",
                        "El monitor secundario se desconectó.\n\n"
                        "La proyección se cerrará automáticamente."
                    )
                    self.projector_active = False
                    self.projection_window.close()
                    self.projection_window = None
                    self.update_projector_button()
                    return
            
            geometry = secondary_screen.geometry()
            self.projection_window.screen_geometry = geometry
            self.projection_window.setGeometry(geometry)

    def show_exposure_section(self):
        self.exposure_section.setVisible(True)
        self.exposure_section.set_collapsed(False)
        self.frequency_section.setVisible(False)
        self.exposure_tab_button.setChecked(True)
        self.frequency_tab_button.setChecked(False)

    def show_frequency_section(self):
        self.exposure_section.setVisible(False)
        self.frequency_section.setVisible(True)
        self.frequency_section.set_collapsed(False)
        self.exposure_tab_button.setChecked(False)
        self.frequency_tab_button.setChecked(True)

    def toggle_grid_view(self):
        self.grid_view_active = not self.grid_view_active
        
        if self.grid_view_active:
            # Asegurar que la vista de calibración esté oculta
            if self.calibration_view_active:
                self.hide_calibration_interface()
                self.calibration_view_active = False
                self.calibration_button.setText("🎯 Calibración")

            self.toggle_view_button.setText("🖼️ Vista Imagen")
            self.grid_config_section.setVisible(True)
            self.grid_config_section.set_collapsed(False)
            self.grid_stats_section.setVisible(True)
            self.grid_stats_section.set_collapsed(False)
            self.segmentation_section.setVisible(True)  # Mostrar segmentación en modo grid
            self.segmentation_section.set_collapsed(False)
            self.projection_control_section.setVisible(True)  # Mostrar control de proyección en modo grid
            self.projection_control_section.set_collapsed(False)
            self.toolbar.setVisible(True)  # Mostrar toolbar en modo grid
            
            # Preparar imagen para el grid si existe un patrón cargado
            if self.pattern is not None:
                # Aplicar efectos si la opción está activada
                if self.apply_effects_to_grid:
                    self.image_on_grid = self.apply_grid_effects(self.pattern.copy())
                else:
                    self.image_on_grid = self.pattern.copy()
                self.image_position = [0, 0]
                self.image_coords_section.setVisible(True)
                self.image_coords_section.set_collapsed(False)
                self.update_image_coordinates()
            else:
                self.image_on_grid = None
                self.image_coords_section.setVisible(False)
            
            if hasattr(self, 'grid_generated') and self.grid_generated:
                self.generate_grid_button.setText("💾 Guardar Nuevo Tamaño")
                self.display_grid()
            else:
                self.generate_grid_button.setText("🎨 Generar Grid")
                self.grid_stats_section.setVisible(False)
                if hasattr(self, 'ax'):
                    self.canvas.figure.clear()
                    self.ax = self.canvas.figure.add_subplot(111)
                    self.ax.set_facecolor("#1E1E1E" if self.dark_mode else "#FFFFFF")
                    self.ax.text(0.5, 0.5, 'Presione "Generar Grid" para visualizar',
                                ha='center', va='center', fontsize=14,
                                color='#E0E0E0' if self.dark_mode else '#000000')
                    self.ax.set_xlim(0, 1)
                    self.ax.set_ylim(0, 1)
                    self.ax.axis('off')
                    self.canvas.draw()
        else:
            self.toggle_view_button.setText("📏 Vista Grid")
            self.grid_config_section.setVisible(False)
            self.grid_stats_section.setVisible(False)
            self.image_coords_section.setVisible(False)
            self.segmentation_section.setVisible(False)  # Ocultar segmentación en modo normal
            self.projection_control_section.setVisible(False)  # Ocultar control de proyección en modo normal
            self.toolbar.setVisible(False)  # Ocultar toolbar en modo normal
            
            if self.pattern is not None:
                self.simulate_optics()
            else:
                if hasattr(self, 'ax'):
                    self.canvas.figure.clear()
                    self.ax = self.canvas.figure.add_subplot(111)
                    self.ax.set_facecolor("#1E1E1E" if self.dark_mode else "#FFFFFF")
                    self.ax.text(0.5, 0.5, 'Cargue un patrón para comenzar',
                                ha='center', va='center', fontsize=14,
                                color='#E0E0E0' if self.dark_mode else '#000000')
                    self.ax.set_xlim(0, 1)
                    self.ax.set_ylim(0, 1)
                    self.ax.axis('off')
                    self.canvas.draw()

        # NO actualizar proyector automáticamente al cargar imagen
        # Solo se mostrará cuando se proyecten segmentos individuales
        # if self.projector_active and self.projection_window is not None:
        #     current_image = self._get_projection_image()
        #     if current_image is not None:
        #         self.projection_window.update_image(current_image)

        self._refresh_invert_button_state()

    def toggle_calibration_view(self):
        """Alterna entre vista normal y vista de calibración."""
        self.calibration_view_active = not self.calibration_view_active
        
        if self.calibration_view_active:
            # Desactivar vista grid si está activa
            if self.grid_view_active:
                self.toggle_grid_view()
            
            self.calibration_button.setText("🖼️ Vista Normal")
            self.show_calibration_interface()
        else:
            self.calibration_button.setText("🎯 Calibración")
            self.hide_calibration_interface()
            
            # Volver a mostrar vista normal
            if self.pattern is not None:
                self.simulate_optics()
            else:
                if hasattr(self, 'ax'):
                    self.canvas.figure.clear()
                    self.ax = self.canvas.figure.add_subplot(111)
                    self.ax.set_facecolor("#1E1E1E" if self.dark_mode else "#FFFFFF")
                    self.ax.text(0.5, 0.5, 'Cargue un patrón para comenzar',
                                ha='center', va='center', fontsize=14,
                                color='#E0E0E0' if self.dark_mode else '#000000')
                    self.ax.set_xlim(0, 1)
                    self.ax.set_ylim(0, 1)
                    self.ax.axis('off')
                    self.canvas.draw()

    def show_calibration_interface(self):
        """Muestra la interfaz de calibración con pestañas."""
        self.canvas.setVisible(False)
        if hasattr(self, 'toolbar'):
            self.toolbar.setVisible(False)
        
        from PyQt5.QtWidgets import QTabWidget
        
        if not hasattr(self, 'calibration_widget'):
            self.calibration_widget = QWidget()
            self.calibration_widget.setParent(self)
            calib_layout = QVBoxLayout(self.calibration_widget)
            
            title = QLabel("🎯 CALIBRACIÓN DE IMAGEN Y UNIFORMIDAD")
            title.setObjectName("sectionTitle")
            title.setAlignment(Qt.AlignCenter)
            calib_layout.addWidget(title)
            
            # Pestañas
            self.calibration_tabs = QTabWidget()
            self.calibration_tabs.setObjectName("calibrationTabs")

            self.calibration_tabs.setStyleSheet("""
                QTabWidget::pane {
                    background-color: #1E1E1E;
                    border: none;
                }
                QTabWidget > QWidget {
                    background-color: #1E1E1E;
                }
            """ if self.dark_mode else """
                QTabWidget::pane {
                    background-color: #FFFFFF;
                    border: none;
                }
                QTabWidget > QWidget {
                    background-color: #FFFFFF;
                }
            """)
            
            # ════════════════════════════════════════════════════════════
            # PESTAÑA Fuente de Imagen
            # ════════════════════════════════════════════════════════════
            source_tab_container = QWidget()
            source_tab_container.setAutoFillBackground(False)
            source_tab_container.setStyleSheet("background-color: transparent;")
            source_tab_scroll = QScrollArea()
            source_tab_scroll.setWidgetResizable(True)
            source_tab_scroll.setFrameShape(QFrame.NoFrame)
            source_tab_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAsNeeded)
            source_tab_scroll.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)
            source_tab_scroll.setStyleSheet("QScrollArea { background-color: transparent; border: none; }")
            
            source_tab = QWidget()
            source_tab.setAutoFillBackground(False)
            source_tab.setStyleSheet("background-color: transparent;")
            source_layout = QVBoxLayout(source_tab)
            source_layout.setContentsMargins(20, 20, 20, 20)
            source_layout.setSpacing(15)
            
            # Establecer tamaño mínimo cómodo
            source_tab.setMinimumWidth(750)
            
            # Título de la sección
            source_title = QLabel("📷 Selección de Fuente de Imagen")
            source_title.setStyleSheet("font-size: 14px; font-weight: bold; margin-bottom: 10px; color: #03DAC6;")
            source_layout.addWidget(source_title)
            
            source_desc = QLabel("Seleccione la fuente de imagen para realizar la calibración:")
            source_desc.setWordWrap(True)
            source_desc.setStyleSheet("color: #B0B0B0;")
            source_layout.addWidget(source_desc)
            
            source_layout.addSpacing(10)
            
            # Grupo de radio buttons para selección de fuente
            self.source_button_group = QButtonGroup()
            
            # Cámara en vivo
            self.camera_radio = QRadioButton("📹 Cámara en Vivo")
            self.camera_radio.setChecked(True)
            self.source_button_group.addButton(self.camera_radio, 0)
            source_layout.addWidget(self.camera_radio)
            
            camera_info = QLabel("   • Captura imágenes en tiempo real desde la cámara conectada")
            camera_info.setStyleSheet("font-size: 11px; color: #888888; margin-left: 20px;")
            camera_info.setWordWrap(True)
            source_layout.addWidget(camera_info)
            
            # Selector de cámara
            camera_selector_layout = QHBoxLayout()
            camera_selector_layout.setContentsMargins(40, 5, 0, 5)
            camera_label = QLabel("Cámara:")
            camera_label.setStyleSheet("color: #B0B0B0;")
            self.camera_combo = QComboBox()
            self.refresh_cameras_button = QPushButton("🔄")
            self.refresh_cameras_button.setMaximumWidth(40)
            self.refresh_cameras_button.clicked.connect(self.refresh_available_cameras)
            camera_selector_layout.addWidget(camera_label)
            camera_selector_layout.addWidget(self.camera_combo, stretch=1)
            camera_selector_layout.addWidget(self.refresh_cameras_button)
            source_layout.addLayout(camera_selector_layout)
            
            # Botón para iniciar/detener cámara
            camera_control_layout = QHBoxLayout()
            camera_control_layout.setContentsMargins(40, 5, 0, 10)
            self.start_camera_button = QPushButton("▶️ Iniciar Cámara")
            self.start_camera_button.clicked.connect(self.toggle_camera_capture)
            camera_control_layout.addWidget(self.start_camera_button)
            camera_control_layout.addStretch()
            source_layout.addLayout(camera_control_layout)
            
            source_layout.addSpacing(10)
            
            # Cámara Basler (si está disponible)
            if BASLER_AVAILABLE:
                self.basler_radio = QRadioButton("🎥 Cámara Basler aCA640-750um")
                self.source_button_group.addButton(self.basler_radio, 1)
                source_layout.addWidget(self.basler_radio)
                
                basler_info = QLabel("   • Cámara industrial con controles avanzados de exposición y ganancia")
                basler_info.setStyleSheet("font-size: 11px; color: #888888; margin-left: 20px;")
                basler_info.setWordWrap(True)
                source_layout.addWidget(basler_info)
                
                # Botón para iniciar/detener cámara Basler
                basler_control_layout = QHBoxLayout()
                basler_control_layout.setContentsMargins(40, 5, 0, 10)
                self.start_basler_button = QPushButton("▶️ Iniciar Cámara Basler")
                self.start_basler_button.clicked.connect(self.toggle_basler_capture)
                basler_control_layout.addWidget(self.start_basler_button)
                basler_control_layout.addStretch()
                source_layout.addLayout(basler_control_layout)
                
                # Panel de controles Basler (colapsable)
                self.basler_controls_section = CollapsibleSection("⚙️ Controles Avanzados Basler", expanded=False)
                basler_controls_content = QWidget()
                basler_controls_layout = QVBoxLayout(basler_controls_content)
                basler_controls_layout.setContentsMargins(10, 10, 10, 10)
                basler_controls_layout.setSpacing(12)
                
                # Control de Exposición
                exp_label = QLabel("⏱️ Exposición (μs):")
                exp_label.setStyleSheet("font-weight: bold;")
                basler_controls_layout.addWidget(exp_label)
                
                exp_layout = QHBoxLayout()
                self.basler_exposure_slider = QSlider(Qt.Horizontal)
                self.basler_exposure_slider.setMinimum(100)  # 100 μs mínimo
                self.basler_exposure_slider.setMaximum(1000000)  # 1 segundo máximo
                self.basler_exposure_slider.setValue(10000)  # 10ms por defecto
                self.basler_exposure_slider.valueChanged.connect(self.update_basler_exposure_from_slider)
                self.basler_exposure_input = QLineEdit("10000")
                self.basler_exposure_input.setMaximumWidth(80)
                self.basler_exposure_input.returnPressed.connect(self.update_basler_exposure_from_input)
                exp_layout.addWidget(self.basler_exposure_slider, stretch=1)
                exp_layout.addWidget(self.basler_exposure_input)
                exp_layout.addWidget(QLabel("μs"))
                basler_controls_layout.addLayout(exp_layout)
                
                # Control de Ganancia
                gain_label = QLabel("📊 Ganancia (dB):")
                gain_label.setStyleSheet("font-weight: bold;")
                basler_controls_layout.addWidget(gain_label)
                
                gain_layout = QHBoxLayout()
                self.basler_gain_slider = QSlider(Qt.Horizontal)
                self.basler_gain_slider.setMinimum(0)
                self.basler_gain_slider.setMaximum(240)  # 24.0 dB máximo (x10 para precisión)
                self.basler_gain_slider.setValue(0)
                self.basler_gain_slider.valueChanged.connect(self.update_basler_gain_from_slider)
                self.basler_gain_input = QLineEdit("0.0")
                self.basler_gain_input.setMaximumWidth(80)
                self.basler_gain_input.returnPressed.connect(self.update_basler_gain_from_input)
                gain_layout.addWidget(self.basler_gain_slider, stretch=1)
                gain_layout.addWidget(self.basler_gain_input)
                gain_layout.addWidget(QLabel("dB"))
                basler_controls_layout.addLayout(gain_layout)
                
                # Control de Gamma
                gamma_label = QLabel("🔆 Gamma:")
                gamma_label.setStyleSheet("font-weight: bold;")
                basler_controls_layout.addWidget(gamma_label)
                
                gamma_layout = QHBoxLayout()
                self.basler_gamma_slider = QSlider(Qt.Horizontal)
                self.basler_gamma_slider.setMinimum(10)  # 0.1 (x10)
                self.basler_gamma_slider.setMaximum(40)  # 4.0 (x10)
                self.basler_gamma_slider.setValue(10)  # 1.0 por defecto
                self.basler_gamma_slider.valueChanged.connect(self.update_basler_gamma_from_slider)
                self.basler_gamma_input = QLineEdit("1.0")
                self.basler_gamma_input.setMaximumWidth(80)
                self.basler_gamma_input.returnPressed.connect(self.update_basler_gamma_from_input)
                gamma_layout.addWidget(self.basler_gamma_slider, stretch=1)
                gamma_layout.addWidget(self.basler_gamma_input)
                basler_controls_layout.addLayout(gamma_layout)
                
                # Control de Black Level
                black_label = QLabel("⬛ Nivel de Negro:")
                black_label.setStyleSheet("font-weight: bold;")
                basler_controls_layout.addWidget(black_label)
                
                black_layout = QHBoxLayout()
                self.basler_black_slider = QSlider(Qt.Horizontal)
                self.basler_black_slider.setMinimum(0)
                self.basler_black_slider.setMaximum(255)
                self.basler_black_slider.setValue(0)
                self.basler_black_slider.valueChanged.connect(self.update_basler_black_from_slider)
                self.basler_black_input = QLineEdit("0")
                self.basler_black_input.setMaximumWidth(80)
                self.basler_black_input.returnPressed.connect(self.update_basler_black_from_input)
                black_layout.addWidget(self.basler_black_slider, stretch=1)
                black_layout.addWidget(self.basler_black_input)
                basler_controls_layout.addLayout(black_layout)
                
                # Botón para aplicar cambios
                apply_basler_btn = QPushButton("✓ Aplicar Configuración")
                apply_basler_btn.clicked.connect(self.apply_basler_settings)
                basler_controls_layout.addWidget(apply_basler_btn)
                
                # Botón para resetear a valores por defecto
                reset_basler_btn = QPushButton("↺ Valores por Defecto")
                reset_basler_btn.clicked.connect(self.reset_basler_settings)
                basler_controls_layout.addWidget(reset_basler_btn)
                
                self.basler_controls_section.setContentWidget(basler_controls_content)
                source_layout.addWidget(self.basler_controls_section)
                
                source_layout.addSpacing(10)
            else:
                self.basler_radio = None
                # Mostrar mensaje de que Basler no está disponible
                basler_unavailable = QLabel("ℹ️ Cámara Basler no disponible (pypylon no instalado)")
                basler_unavailable.setStyleSheet("font-size: 11px; color: #666666; font-style: italic;")
                source_layout.addWidget(basler_unavailable)
                source_layout.addSpacing(10)

            self.image_radio = QRadioButton("🖼️ Imagen Estática")
            self.source_button_group.addButton(self.image_radio, 2 if BASLER_AVAILABLE else 1)
            source_layout.addWidget(self.image_radio)
            
            image_info = QLabel("   • Carga una imagen preexistente desde el disco")
            image_info.setStyleSheet("font-size: 11px; color: #888888; margin-left: 20px;")
            image_info.setWordWrap(True)
            source_layout.addWidget(image_info)
            
            # Botón para cargar imagen
            image_loader_layout = QHBoxLayout()
            image_loader_layout.setContentsMargins(40, 5, 0, 5)
            self.load_calib_image_button = QPushButton("📂 Cargar Imagen...")
            self.load_calib_image_button.clicked.connect(self.load_calibration_image)
            image_loader_layout.addWidget(self.load_calib_image_button)
            image_loader_layout.addStretch()
            source_layout.addLayout(image_loader_layout)
            
            # Label para mostrar imagen cargada
            self.calib_image_status = QLabel("   Sin imagen cargada")
            self.calib_image_status.setStyleSheet("font-size: 11px; color: #666666; margin-left: 40px;")
            source_layout.addWidget(self.calib_image_status)
            
            source_layout.addSpacing(20)
            
            # Vista previa
            preview_label = QLabel("👁️ Vista Previa:")
            preview_label.setStyleSheet("font-size: 13px; font-weight: bold; color: #E0E0E0;")
            source_layout.addWidget(preview_label)
            
            # Canvas para vista previa de calibración
            self.calib_preview_figure = Figure(facecolor="#121212" if self.dark_mode else "#FFFFFF")
            self.calib_preview_canvas = FigureCanvas(self.calib_preview_figure)
            self.calib_preview_canvas.setMinimumHeight(300)
            self.calib_preview_ax = self.calib_preview_figure.add_subplot(111)
            self.calib_preview_ax.set_facecolor("#1E1E1E" if self.dark_mode else "#F5F5F5")
            self.calib_preview_ax.text(0.5, 0.5, 'Seleccione una fuente para comenzar',
                        ha='center', va='center', fontsize=12,
                        color='#E0E0E0' if self.dark_mode else '#000000')
            self.calib_preview_ax.axis('off')
            self.calib_preview_canvas.draw()
            source_layout.addWidget(self.calib_preview_canvas, stretch=1)
            
            source_layout.addStretch()
            
            # Conectar cambios de fuente
            self.source_button_group.buttonClicked.connect(self.on_calibration_source_changed)
            
            # Agregar contenido al scroll y scroll al tab
            source_tab_scroll.setWidget(source_tab)
            source_tab_container_layout = QVBoxLayout(source_tab_container)
            source_tab_container_layout.setContentsMargins(0, 0, 0, 0)
            source_tab_container_layout.addWidget(source_tab_scroll)
            
            self.calibration_tabs.addTab(source_tab_container, "1️⃣ Fuente de Imagen")
            
            # ════════════════════════════════════════════════════════════
            # PESTAÑA 2: Análisis y Visualización del Brillo
            # ════════════════════════════════════════════════════════════
            analysis_tab = QWidget()
            analysis_tab.setAutoFillBackground(False)
            analysis_tab.setStyleSheet("background-color: transparent;")
            analysis_layout = QVBoxLayout(analysis_tab)
            analysis_layout.setContentsMargins(20, 20, 20, 20)
            analysis_layout.setSpacing(15)
            
            # Título de la sección
            analysis_title = QLabel("📊 Análisis y Visualización del Brillo")
            analysis_title.setStyleSheet("font-size: 14px; font-weight: bold; margin-bottom: 10px; color: #03DAC6;")
            analysis_layout.addWidget(analysis_title)
            
            analysis_desc = QLabel("Análisis de intensidad y uniformidad de la imagen capturada:")
            analysis_desc.setWordWrap(True)
            analysis_desc.setStyleSheet("color: #B0B0B0;")
            analysis_layout.addWidget(analysis_desc)
            
            analysis_layout.addSpacing(10)
            
            # ─────────────────────────────────────────────────────────
            # Visualización en Escala de Grises
            # ─────────────────────────────────────────────────────────
            grayscale_group = QWidget()
            grayscale_group.setObjectName("statsContainer")
            grayscale_layout = QVBoxLayout(grayscale_group)
            grayscale_layout.setContentsMargins(10, 10, 10, 10)
            
            gray_title = QLabel("🎞️ Visualización en Escala de Grises")
            gray_title.setStyleSheet("font-size: 13px; font-weight: bold; color: #E0E0E0;")
            grayscale_layout.addWidget(gray_title)
            
            gray_desc = QLabel("Vista de la imagen en escala de grises para análisis de intensidad:")
            gray_desc.setWordWrap(True)
            gray_desc.setStyleSheet("font-size: 11px; color: #888888;")
            grayscale_layout.addWidget(gray_desc)
            
            # Botones de control
            gray_controls = QHBoxLayout()
            self.show_grayscale_button = QPushButton("👁️ Mostrar Escala de Grises")
            self.show_grayscale_button.clicked.connect(self.show_grayscale_fullscreen)
            self.show_grayscale_button.setEnabled(False)  # Habilitado solo cuando hay imagen
            gray_controls.addWidget(self.show_grayscale_button)
            
            # Botón de inversión (espejo)
            self.mirror_preview_button = QPushButton("↔️ Espejo")
            self.mirror_preview_button.setCheckable(True)
            self.mirror_preview_button.clicked.connect(self.toggle_mirror_preview)
            self.mirror_preview_button.setEnabled(False)
            gray_controls.addWidget(self.mirror_preview_button)
            
            gray_controls.addStretch()
            grayscale_layout.addLayout(gray_controls)
            
            # Canvas para vista previa en escala de grises
            self.gray_preview_figure = Figure(facecolor="#121212" if self.dark_mode else "#FFFFFF")
            self.gray_preview_canvas = FigureCanvas(self.gray_preview_figure)
            self.gray_preview_canvas.setMinimumHeight(250)
            self.gray_preview_ax = self.gray_preview_figure.add_subplot(111)
            self.gray_preview_ax.set_facecolor("#1E1E1E" if self.dark_mode else "#F5F5F5")
            self.gray_preview_ax.text(0.5, 0.5, 'Capture o cargue una imagen en la pestaña anterior',
                        ha='center', va='center', fontsize=11,
                        color='#E0E0E0' if self.dark_mode else '#000000')
            self.gray_preview_ax.axis('off')
            self.gray_preview_canvas.draw()
            grayscale_layout.addWidget(self.gray_preview_canvas)
            
            analysis_layout.addWidget(grayscale_group)
            
            analysis_layout.addSpacing(10)
            
            # ─────────────────────────────────────────────────────────
            # Mapeo de Intensidad de Píxeles
            # ─────────────────────────────────────────────────────────
            intensity_group = QWidget()
            intensity_group.setObjectName("statsContainer")
            intensity_layout = QVBoxLayout(intensity_group)
            intensity_layout.setContentsMargins(10, 10, 10, 10)
            
            intensity_title = QLabel("📊 Análisis de Intensidad")
            intensity_title.setStyleSheet("font-size: 13px; font-weight: bold; color: #E0E0E0;")
            intensity_layout.addWidget(intensity_title)
            
            
            intensity_desc = QLabel("Análisis zonal de brillo/atenuación con mapa de calor:")
            intensity_desc.setWordWrap(True)
            intensity_desc.setStyleSheet("font-size: 11px; color: #888888;")
            intensity_layout.addWidget(intensity_desc)
            
            # Controles de análisis zonal
            zone_controls_layout = QHBoxLayout()
            
            zone_label = QLabel("División de Zonas:")
            zone_label.setStyleSheet("color: #B0B0B0;")
            zone_controls_layout.addWidget(zone_label)
            
            self.zone_grid_combo = QComboBox()
            self.zone_grid_combo.addItems(["3x3 (9 zonas)", "4x4 (16 zonas)", "5x5 (25 zonas)", 
                                           "8x8 (64 zonas)", "Píxel a Píxel"])
            self.zone_grid_combo.setCurrentIndex(1)  # 4x4 por defecto
            self.zone_grid_combo.currentIndexChanged.connect(self.update_intensity_analysis)
            zone_controls_layout.addWidget(self.zone_grid_combo)
            
            zone_controls_layout.addSpacing(20)
            
            self.analyze_intensity_button = QPushButton("🔍 Analizar Intensidad")
            self.analyze_intensity_button.clicked.connect(self.analyze_brightness_zones)
            self.analyze_intensity_button.setEnabled(False)
            zone_controls_layout.addWidget(self.analyze_intensity_button)
            
            zone_controls_layout.addStretch()
            intensity_layout.addLayout(zone_controls_layout)
            
            # Opciones de visualización
            viz_options = QHBoxLayout()
            
            self.show_percentages_check = QCheckBox("Mostrar Porcentajes")
            self.show_percentages_check.setChecked(True)
            self.show_percentages_check.stateChanged.connect(self.update_intensity_analysis)
            viz_options.addWidget(self.show_percentages_check)
            
            self.show_heatmap_check = QCheckBox("Mapa de Calor")
            self.show_heatmap_check.setChecked(True)
            self.show_heatmap_check.stateChanged.connect(self.update_intensity_analysis)
            viz_options.addWidget(self.show_heatmap_check)
            
            viz_options.addStretch()
            intensity_layout.addLayout(viz_options)
            
            # Canvas para mapa de intensidad
            self.intensity_map_figure = Figure(facecolor="#121212" if self.dark_mode else "#FFFFFF")
            self.intensity_map_canvas = FigureCanvas(self.intensity_map_figure)
            self.intensity_map_canvas.setMinimumHeight(300)
            self.intensity_map_ax = self.intensity_map_figure.add_subplot(111)
            self.intensity_map_ax.set_facecolor("#1E1E1E" if self.dark_mode else "#F5F5F5")
            self.intensity_map_ax.text(0.5, 0.5, 'Presione "Analizar Intensidad" para comenzar',
                        ha='center', va='center', fontsize=11,
                        color='#E0E0E0' if self.dark_mode else '#000000')
            self.intensity_map_ax.axis('off')
            self.intensity_map_canvas.draw()
            intensity_layout.addWidget(self.intensity_map_canvas)
            
            # Estadísticas de uniformidad
            stats_layout = QHBoxLayout()
            
            self.brightness_avg_label = QLabel("Promedio: ---%")
            self.brightness_avg_label.setObjectName("statLabel")
            stats_layout.addWidget(self.brightness_avg_label)
            
            self.brightness_min_label = QLabel("Mínimo: ---%")
            self.brightness_min_label.setObjectName("statLabel")
            stats_layout.addWidget(self.brightness_min_label)
            
            self.brightness_max_label = QLabel("Máximo: ---%")
            self.brightness_max_label.setObjectName("statLabel")
            stats_layout.addWidget(self.brightness_max_label)
            
            self.brightness_std_label = QLabel("Desv. Est.: ---%")
            self.brightness_std_label.setObjectName("statLabel")
            stats_layout.addWidget(self.brightness_std_label)
            
            stats_layout.addStretch()
            intensity_layout.addLayout(stats_layout)
            
            # Indicador de uniformidad
            uniformity_layout = QHBoxLayout()
            uniformity_label = QLabel("Uniformidad:")
            uniformity_label.setStyleSheet("font-weight: bold;")
            uniformity_layout.addWidget(uniformity_label)
            
            self.uniformity_indicator = QLabel("--- %")
            self.uniformity_indicator.setStyleSheet("font-size: 16px; font-weight: bold; color: #888888;")
            uniformity_layout.addWidget(self.uniformity_indicator)
            
            self.uniformity_status = QLabel("Sin datos")
            self.uniformity_status.setStyleSheet("font-size: 11px; color: #888888;")
            uniformity_layout.addWidget(self.uniformity_status)
            
            uniformity_layout.addStretch()
            intensity_layout.addLayout(uniformity_layout)
            
            analysis_layout.addWidget(intensity_group)
            
            analysis_layout.addStretch()
            
            self.calibration_tabs.addTab(analysis_tab, "2️⃣ Análisis de Brillo")
            

            adjustment_tab = QWidget()
            adjustment_tab.setAutoFillBackground(False)
            adjustment_tab.setStyleSheet("background-color: transparent;")
            adjustment_layout = QVBoxLayout(adjustment_tab)
            adjustment_layout.setContentsMargins(20, 20, 20, 20)
            adjustment_layout.setSpacing(15)
            
            adjustment_title = QLabel("🔧 Herramientas de Ajuste de Calibración")
            adjustment_title.setStyleSheet("font-size: 14px; font-weight: bold; margin-bottom: 10px; color: #03DAC6;")
            adjustment_layout.addWidget(adjustment_title)
            
            adjustment_desc = QLabel("Ajuste del umbral y generación de matriz de atenuación:")
            adjustment_desc.setWordWrap(True)
            adjustment_desc.setStyleSheet("color: #B0B0B0;")
            adjustment_layout.addWidget(adjustment_desc)
            
            adjustment_layout.addSpacing(10)
            
            # ─────────────────────────────────────────────────────────
            # Control de Umbral (Threshold)
            # ─────────────────────────────────────────────────────────
            threshold_group = QWidget()
            threshold_group.setObjectName("statsContainer")
            threshold_layout = QVBoxLayout(threshold_group)
            threshold_layout.setContentsMargins(10, 10, 10, 10)
            
            threshold_title = QLabel("⚖️ Control de Umbral Binario")
            threshold_title.setStyleSheet("font-size: 13px; font-weight: bold; color: #E0E0E0;")
            threshold_layout.addWidget(threshold_title)
            
            threshold_desc = QLabel("Ajuste del punto de corte para conversión binaria de la imagen:")
            threshold_desc.setWordWrap(True)
            threshold_desc.setStyleSheet("font-size: 11px; color: #888888;")
            threshold_layout.addWidget(threshold_desc)
            
            # Control de umbral con slider e input
            threshold_controls = QHBoxLayout()
            
            threshold_label = QLabel("Umbral de Intensidad:")
            threshold_label.setStyleSheet("color: #B0B0B0;")
            threshold_controls.addWidget(threshold_label)
            
            self.calib_threshold_slider = QSlider(Qt.Horizontal)
            self.calib_threshold_slider.setMinimum(0)
            self.calib_threshold_slider.setMaximum(100)
            self.calib_threshold_slider.setValue(int(self.calibration_threshold))
            self.calib_threshold_slider.setMinimumWidth(200)
            self.calib_threshold_slider.valueChanged.connect(self.update_calibration_threshold_from_slider)
            self.calib_threshold_slider.sliderReleased.connect(self.save_calibration_data)
            threshold_controls.addWidget(self.calib_threshold_slider)
            
            self.calib_threshold_input = QLineEdit()
            self.calib_threshold_input.setText(f"{self.calibration_threshold:.1f}")
            self.calib_threshold_input.setMaximumWidth(60)
            self.calib_threshold_input.setPlaceholderText("0-100")
            self.calib_threshold_input.editingFinished.connect(self.update_calibration_threshold_from_input)
            self.calib_threshold_input.editingFinished.connect(self.save_calibration_data)
            threshold_controls.addWidget(self.calib_threshold_input)
            
            threshold_unit_label = QLabel("%")
            threshold_unit_label.setStyleSheet("color: #B0B0B0;")
            threshold_controls.addWidget(threshold_unit_label)
            
            threshold_controls.addStretch()
            threshold_layout.addLayout(threshold_controls)
            
            threshold_info = QLabel("• El umbral determina el punto de corte para conversión binaria\n"
                                   "• Intensidad ≥ umbral → 100% (Blanco/Expuesto)\n"
                                   "• Intensidad < umbral → 0% (Negro/No expuesto)")
            threshold_info.setWordWrap(True)
            threshold_info.setStyleSheet("font-size: 10px; color: #888888; margin-left: 10px;")
            threshold_layout.addWidget(threshold_info)
            
            preview_threshold_layout = QHBoxLayout()
            self.preview_threshold_button = QPushButton("👁️ Previsualizar Conversión")
            self.preview_threshold_button.clicked.connect(self.preview_threshold_conversion)
            self.preview_threshold_button.setEnabled(False)
            preview_threshold_layout.addWidget(self.preview_threshold_button)
            preview_threshold_layout.addStretch()
            threshold_layout.addLayout(preview_threshold_layout)
            self.threshold_preview_figure = Figure(facecolor="#121212" if self.dark_mode else "#FFFFFF")
            self.threshold_preview_canvas = FigureCanvas(self.threshold_preview_figure)
            self.threshold_preview_canvas.setMinimumHeight(250)
            self.threshold_preview_ax = self.threshold_preview_figure.add_subplot(111)
            self.threshold_preview_ax.set_facecolor("#1E1E1E" if self.dark_mode else "#F5F5F5")
            self.threshold_preview_ax.text(0.5, 0.5, 'Capture/cargue una imagen y presione "Previsualizar"',
                        ha='center', va='center', fontsize=11,
                        color='#E0E0E0' if self.dark_mode else '#000000')
            self.threshold_preview_ax.axis('off')
            self.threshold_preview_canvas.draw()
            threshold_layout.addWidget(self.threshold_preview_canvas)
            
            # Estadísticas de la conversión
            threshold_stats = QHBoxLayout()
            self.threshold_white_label = QLabel("Píxeles Blancos: ---%")
            self.threshold_white_label.setObjectName("statLabel")
            threshold_stats.addWidget(self.threshold_white_label)
            
            self.threshold_black_label = QLabel("Píxeles Negros: ---%")
            self.threshold_black_label.setObjectName("statLabel")
            threshold_stats.addWidget(self.threshold_black_label)
            
            threshold_stats.addStretch()
            threshold_layout.addLayout(threshold_stats)
            
            adjustment_layout.addWidget(threshold_group)
            
            adjustment_layout.addSpacing(10)
            
            # ─────────────────────────────────────────────────────────
            # Matriz de Compensación de Uniformidad
            # ─────────────────────────────────────────────────────────
            attenuation_group = QWidget()
            attenuation_group.setObjectName("statsContainer")
            attenuation_layout = QVBoxLayout(attenuation_group)
            attenuation_layout.setContentsMargins(10, 10, 10, 10)
            
            atten_title = QLabel("🎛️ Matriz de Compensación de Uniformidad")
            atten_title.setStyleSheet("font-size: 13px; font-weight: bold; color: #E0E0E0;")
            attenuation_layout.addWidget(atten_title)
            
            atten_desc = QLabel("Corrección automática de variaciones de brillo en la proyección:")
            atten_desc.setWordWrap(True)
            atten_desc.setStyleSheet("font-size: 11px; color: #888888;")
            attenuation_layout.addWidget(atten_desc)
            
            # Controles de generación de matriz
            matrix_gen_layout = QHBoxLayout()
            
            self.generate_attenuation_button = QPushButton("🎯 Generar Matriz de Atenuación")
            self.generate_attenuation_button.clicked.connect(self.generate_attenuation_matrix)
            self.generate_attenuation_button.setEnabled(False)
            matrix_gen_layout.addWidget(self.generate_attenuation_button)
            
            matrix_gen_layout.addSpacing(20)
            
            self.apply_attenuation_check = QCheckBox("Aplicar a Grid de Proyección")
            self.apply_attenuation_check.setEnabled(False)
            self.apply_attenuation_check.stateChanged.connect(self.toggle_attenuation_application)
            matrix_gen_layout.addWidget(self.apply_attenuation_check)
            
            matrix_gen_layout.addStretch()
            attenuation_layout.addLayout(matrix_gen_layout)
            
            # Método de compensación
            method_layout = QHBoxLayout()
            method_label = QLabel("Método de Compensación:")
            method_label.setStyleSheet("color: #B0B0B0;")
            method_layout.addWidget(method_label)
            
            self.attenuation_method_combo = QComboBox()
            self.attenuation_method_combo.addItems([
                "Inversión Normalizada (Recomendado)",
                "Inversión Simple",
                "Ecualizador Adaptativo",
                "Compensación Proporcional"
            ])
            self.attenuation_method_combo.currentIndexChanged.connect(self.update_attenuation_preview)
            self.attenuation_method_combo.currentIndexChanged.connect(self.save_calibration_data)
            method_layout.addWidget(self.attenuation_method_combo)
            
            method_layout.addStretch()
            attenuation_layout.addLayout(method_layout)
            
            # Intensidad de corrección
            intensity_layout = QHBoxLayout()
            intensity_label = QLabel("Intensidad de Corrección:")
            intensity_label.setStyleSheet("color: #B0B0B0;")
            intensity_layout.addWidget(intensity_label)
            
            self.attenuation_strength_slider = QSlider(Qt.Horizontal)
            self.attenuation_strength_slider.setMinimum(0)
            self.attenuation_strength_slider.setMaximum(100)
            self.attenuation_strength_slider.setValue(int(self.attenuation_strength))
            self.attenuation_strength_slider.setMinimumWidth(150)
            self.attenuation_strength_slider.valueChanged.connect(self.update_attenuation_preview)
            self.attenuation_strength_slider.sliderReleased.connect(self.save_calibration_data)
            intensity_layout.addWidget(self.attenuation_strength_slider)
            
            self.attenuation_strength_label = QLabel(f"{self.attenuation_strength}%")
            self.attenuation_strength_label.setStyleSheet("color: #B0B0B0;")
            intensity_layout.addWidget(self.attenuation_strength_label)
            
            intensity_layout.addStretch()
            attenuation_layout.addLayout(intensity_layout)
            
            # Botones de acción
            action_layout = QHBoxLayout()
            
            self.preview_attenuation_button = QPushButton("👁️ Previsualizar Corrección")
            self.preview_attenuation_button.clicked.connect(self.preview_attenuation_effect)
            self.preview_attenuation_button.setEnabled(False)
            action_layout.addWidget(self.preview_attenuation_button)
            
            self.save_attenuation_button = QPushButton("💾 Guardar Matriz")
            self.save_attenuation_button.clicked.connect(self.save_attenuation_matrix)
            self.save_attenuation_button.setEnabled(False)
            action_layout.addWidget(self.save_attenuation_button)
            
            self.load_attenuation_button = QPushButton("📂 Cargar Matriz")
            self.load_attenuation_button.clicked.connect(self.load_attenuation_matrix)
            action_layout.addWidget(self.load_attenuation_button)
            
            action_layout.addStretch()
            attenuation_layout.addLayout(action_layout)
            
            # Canvas para visualización de matriz de atenuación
            self.attenuation_figure = Figure(facecolor="#121212" if self.dark_mode else "#FFFFFF")
            self.attenuation_canvas = FigureCanvas(self.attenuation_figure)
            self.attenuation_canvas.setMinimumHeight(300)
            self.attenuation_ax = self.attenuation_figure.add_subplot(111)
            self.attenuation_ax.set_facecolor("#1E1E1E" if self.dark_mode else "#F5F5F5")
            self.attenuation_ax.text(0.5, 0.5, 'Genere la matriz para visualizar',
                        ha='center', va='center', fontsize=11,
                        color='#E0E0E0' if self.dark_mode else '#000000')
            self.attenuation_ax.axis('off')
            self.attenuation_canvas.draw()
            attenuation_layout.addWidget(self.attenuation_canvas)
            
            # Información de la matriz
            matrix_info_layout = QHBoxLayout()
            self.matrix_status_label = QLabel("Estado: Sin matriz generada")
            self.matrix_status_label.setObjectName("statLabel")
            matrix_info_layout.addWidget(self.matrix_status_label)
            
            self.matrix_range_label = QLabel("Rango: ---")
            self.matrix_range_label.setObjectName("statLabel")
            matrix_info_layout.addWidget(self.matrix_range_label)
            
            matrix_info_layout.addStretch()
            attenuation_layout.addLayout(matrix_info_layout)
            
            adjustment_layout.addWidget(attenuation_group)
            
            adjustment_layout.addStretch()
            
            self.calibration_tabs.addTab(adjustment_tab, "3️⃣ Ajustes y Matriz")
            
            # Crear scroll area para las pestañas de calibración
            calibration_scroll = QScrollArea()
            calibration_scroll.setWidget(self.calibration_tabs)
            calibration_scroll.setWidgetResizable(True)
            calibration_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAsNeeded)
            calibration_scroll.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)
            calibration_scroll.setFrameShape(QFrame.NoFrame)
            
            # Establecer tamaño mínimo cómodo para el área de calibración
            calibration_scroll.setMinimumWidth(800)
            calibration_scroll.setMinimumHeight(600)
            
            calib_layout.addWidget(calibration_scroll)
            
            # Agregar el widget al layout del canvas
            self.canvas_with_toolbar.addWidget(self.calibration_widget)
            self.calibration_widget.setVisible(False)  # Oculto por defecto
        
        # Mostrar widget de calibración y ocultar canvas
        self.canvas.setVisible(False)
        self.toolbar.setVisible(False)
        self.calibration_widget.setVisible(True)
        
        # Actualizar lista de cámaras disponibles
        self.refresh_available_cameras()

    def hide_calibration_interface(self):
        """Oculta la interfaz de calibración."""
        if hasattr(self, 'calibration_widget'):
            self.calibration_widget.setVisible(False)
        
        # Mostrar el canvas normal
        self.canvas.setVisible(True)
        if hasattr(self, 'toolbar'):
            self.toolbar.setVisible(self.grid_view_active)  # Solo mostrar si estamos en modo grid
        
        # Detener cámaras si están activas
        if self.calibration_camera is not None:
            self.stop_camera_capture()
        if BASLER_AVAILABLE and self.basler_camera is not None:
            self.stop_basler_capture()

    def refresh_available_cameras(self):
        """Detecta y lista las cámaras disponibles."""
        self.camera_combo.clear()
        
        # Intentar detectar cámaras (solo 0-2 para evitar errores)
        # Usar CAP_DSHOW en Windows para detección más rápida y silenciosa
        available_cameras = []
        
        # Suprimir temporalmente warnings de OpenCV durante detección
        import warnings
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            for i in range(3):  # Reducido a 3 para evitar búsquedas innecesarias
                try:
                    # Usar DirectShow en Windows para evitar errores de obsensor
                    cap = cv2.VideoCapture(i, cv2.CAP_DSHOW)
                    if cap.isOpened():
                        # Verificar que realmente puede leer frames
                        ret, _ = cap.read()
                        if ret:
                            available_cameras.append(i)
                    cap.release()
                except Exception:
                    pass  # Ignorar errores silenciosamente
        
        if available_cameras:
            for cam_id in available_cameras:
                self.camera_combo.addItem(f"Cámara {cam_id}", cam_id)
            self.log_to_console(f"{len(available_cameras)} cámara(s) detectada(s)", "SUCCESS")
        else:
            self.camera_combo.addItem("No se detectaron cámaras", -1)
            self.log_to_console("No se detectaron cámaras conectadas", "INFO")

    def toggle_camera_capture(self):
        """Inicia o detiene la captura de cámara."""
        if self.calibration_camera is None:
            self.start_camera_capture()
        else:
            self.stop_camera_capture()

    def start_camera_capture(self):
        """Inicia la captura desde la cámara seleccionada."""
        camera_id = self.camera_combo.currentData()
        
        if camera_id == -1:
            QMessageBox.warning(self, "Error", "No hay cámaras disponibles")
            return
        
        # Usar DirectShow en Windows para evitar errores de obsensor
        try:
            self.calibration_camera = cv2.VideoCapture(camera_id, cv2.CAP_DSHOW)
        except Exception:
            self.calibration_camera = cv2.VideoCapture(camera_id)
        
        if not self.calibration_camera.isOpened():
            QMessageBox.warning(self, "Error", f"No se pudo abrir la cámara {camera_id}")
            self.calibration_camera = None
            return
        
        # Cambiar botón
        self.start_camera_button.setText("⏹️ Detener Cámara")
        
        # Iniciar timer para actualizar frames
        if not hasattr(self, 'camera_timer'):
            self.camera_timer = QTimer()
            self.camera_timer.timeout.connect(self.update_camera_frame)
        
        self.camera_timer.start(33)  # ~30 FPS

    def stop_camera_capture(self):
        """Detiene la captura de cámara."""
        if hasattr(self, 'camera_timer'):
            self.camera_timer.stop()
        
        if self.calibration_camera is not None:
            self.calibration_camera.release()
            self.calibration_camera = None
        
        self.start_camera_button.setText("▶️ Iniciar Cámara")

    def update_camera_frame(self):
        """Actualiza el frame de la cámara en la vista previa."""
        if self.calibration_camera is None:
            return
        
        ret, frame = self.calibration_camera.read()
        
        if ret:
            # Convertir de BGR a RGB
            frame_rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            
            # Guardar como imagen de calibración actual
            self.calibration_image = frame_rgb
            
            # Generar versión en escala de grises
            self.calibration_grayscale = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
            
            # Actualizar vista previa en pestaña 1
            self.calib_preview_ax.clear()
            self.calib_preview_ax.imshow(frame_rgb)
            self.calib_preview_ax.axis('off')
            self.calib_preview_canvas.draw_idle()
            
            # Actualizar vista de escala de grises en pestaña 2
            if hasattr(self, 'gray_preview_ax'):
                self.update_grayscale_preview()
            
            # Habilitar botones de análisis
            if hasattr(self, 'show_grayscale_button'):
                self.show_grayscale_button.setEnabled(True)
                self.mirror_preview_button.setEnabled(True)
                self.analyze_intensity_button.setEnabled(True)
                self.preview_threshold_button.setEnabled(True)
                self.generate_attenuation_button.setEnabled(True)

    # ═══════════════════════════════════════════════════════════════════════════
    # FUNCIONES DE CONTROL DE CÁMARA BASLER
    # ═══════════════════════════════════════════════════════════════════════════
    
    def toggle_basler_capture(self):
        """Inicia o detiene la captura de cámara Basler."""
        if self.basler_camera is None:
            self.start_basler_capture()
        else:
            self.stop_basler_capture()
    
    def start_basler_capture(self):
        """Inicia la captura desde la cámara Basler."""
        if not BASLER_AVAILABLE:
            QMessageBox.warning(self, "Error", "pypylon no está instalado")
            return
        
        try:
            # Buscar cámaras Basler disponibles
            tlFactory = pylon.TlFactory.GetInstance()
            devices = tlFactory.EnumerateDevices()
            
            if len(devices) == 0:
                QMessageBox.warning(self, "Error", "No se encontraron cámaras Basler conectadas")
                self.log_to_console("No se encontraron cámaras Basler", "WARNING")
                return
            
            # Conectar a la primera cámara
            self.basler_camera = pylon.InstantCamera(tlFactory.CreateFirstDevice())
            self.basler_camera.Open()
            
            # Log de conexión
            device_info = self.basler_camera.GetDeviceInfo()
            self.log_to_console(f"Cámara Basler conectada: {device_info.GetModelName()} (S/N: {device_info.GetSerialNumber()})", "SUCCESS")
            
            # Configurar cámara
            self.apply_basler_settings()
            
            # Configurar convertidor de imagen
            self.basler_converter = pylon.ImageFormatConverter()
            self.basler_converter.OutputPixelFormat = pylon.PixelType_BGR8packed
            self.basler_converter.OutputBitAlignment = pylon.OutputBitAlignment_MsbAligned
            
            # Iniciar captura
            self.basler_camera.StartGrabbing(pylon.GrabStrategy_LatestImageOnly)
            
            # Crear timer para actualizar frames
            if not hasattr(self, 'basler_timer'):
                self.basler_timer = QTimer()
                self.basler_timer.timeout.connect(self.update_basler_frame)
            
            self.basler_timer.start(33)  # ~30 FPS
            self.start_basler_button.setText("⏸️ Detener Cámara Basler")
            
            # Mostrar controles en sidebar si existen
            if hasattr(self, 'basler_sidebar_section'):
                self.basler_sidebar_section.setVisible(True)
            
            self.log_to_console("Captura Basler iniciada", "INFO")
            
        except Exception as e:
            QMessageBox.critical(self, "Error", f"No se pudo iniciar cámara Basler: {str(e)}")
            self.log_to_console(f"Error al iniciar Basler: {str(e)}", "ERROR")
            if self.basler_camera is not None:
                try:
                    self.basler_camera.Close()
                except:
                    pass
                self.basler_camera = None
    
    def stop_basler_capture(self):
        """Detiene la captura de cámara Basler."""
        try:
            if hasattr(self, 'basler_timer'):
                self.basler_timer.stop()
            
            if self.basler_camera is not None:
                if self.basler_camera.IsGrabbing():
                    self.basler_camera.StopGrabbing()
                self.basler_camera.Close()
                self.basler_camera = None
                self.log_to_console("Cámara Basler desconectada", "INFO")
            
            # Ocultar controles en sidebar si existen
            if hasattr(self, 'basler_sidebar_section'):
                self.basler_sidebar_section.setVisible(False)
            
            self.start_basler_button.setText("▶️ Iniciar Cámara Basler")
            
        except Exception as e:
            self.log_to_console(f"Error al detener Basler: {str(e)}", "WARNING")
    
    def update_basler_frame(self):
        """Actualiza el frame de la cámara Basler en la vista previa."""
        if self.basler_camera is None or not self.basler_camera.IsGrabbing():
            return
        
        try:
            # Capturar imagen
            grabResult = self.basler_camera.RetrieveResult(100, pylon.TimeoutHandling_Return)
            
            if grabResult.GrabSucceeded():
                # Convertir imagen
                image = self.basler_converter.Convert(grabResult)
                frame = image.GetArray()
                
                # Convertir de BGR a RGB para visualización
                frame_rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
                
                # Guardar como imagen de calibración actual
                self.calibration_image = frame_rgb
                
                # Generar versión en escala de grises
                self.calibration_grayscale = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
                
                # Actualizar vista previa en pestaña 1
                self.calib_preview_ax.clear()
                self.calib_preview_ax.imshow(frame_rgb)
                self.calib_preview_ax.axis('off')
                self.calib_preview_ax.set_title(f"Basler - Exp: {self.basler_exposure/1000:.1f}ms | Gain: {self.basler_gain:.1f}dB", 
                                               fontsize=10, color='#00FF00' if self.dark_mode else '#008800')
                self.calib_preview_canvas.draw_idle()
                
                # Actualizar vista de escala de grises en pestaña 2
                if hasattr(self, 'gray_preview_ax'):
                    self.update_grayscale_preview()
                
                # Habilitar botones de análisis
                if hasattr(self, 'show_grayscale_button'):
                    self.show_grayscale_button.setEnabled(True)
                    self.mirror_preview_button.setEnabled(True)
                    self.analyze_intensity_button.setEnabled(True)
                    self.preview_threshold_button.setEnabled(True)
                    self.generate_attenuation_button.setEnabled(True)
            
            grabResult.Release()
            
        except Exception as e:
            self.log_to_console(f"Error en captura Basler: {str(e)}", "WARNING")
    
    def apply_basler_settings(self):
        """Aplica la configuración actual a la cámara Basler."""
        if self.basler_camera is None or not self.basler_camera.IsOpen():
            return
        
        try:
            # Configurar exposición
            try:
                self.basler_camera.ExposureTime.SetValue(self.basler_exposure)
                self.log_to_console(f"Exposición Basler: {self.basler_exposure/1000:.1f}ms", "INFO")
            except Exception as e:
                self.log_to_console(f"No se pudo configurar exposición: {str(e)}", "WARNING")
            
            # Configurar ganancia
            try:
                self.basler_camera.Gain.SetValue(self.basler_gain)
                self.log_to_console(f"Ganancia Basler: {self.basler_gain:.1f}dB", "INFO")
            except Exception as e:
                self.log_to_console(f"No se pudo configurar ganancia: {str(e)}", "WARNING")
            
            # Configurar gamma (si está disponible)
            try:
                if hasattr(self.basler_camera, 'Gamma'):
                    self.basler_camera.Gamma.SetValue(self.basler_gamma)
                    self.log_to_console(f"Gamma Basler: {self.basler_gamma:.2f}", "INFO")
            except Exception as e:
                pass
            
            # Configurar black level (si está disponible)
            try:
                if hasattr(self.basler_camera, 'BlackLevel'):
                    self.basler_camera.BlackLevel.SetValue(self.basler_black_level)
                    self.log_to_console(f"Black Level Basler: {self.basler_black_level}", "INFO")
            except Exception as e:
                pass
                
        except Exception as e:
            self.log_to_console(f"Error al aplicar configuración Basler: {str(e)}", "ERROR")
    
    def reset_basler_settings(self):
        """Resetea los controles Basler a valores por defecto."""
        self.basler_exposure = 10000.0
        self.basler_gain = 0.0
        self.basler_gamma = 1.0
        self.basler_black_level = 0
        
        # Actualizar UI en calibración (si existen)
        if hasattr(self, 'basler_exposure_slider'):
            self.basler_exposure_slider.setValue(10000)
            self.basler_exposure_input.setText("10000")
            self.basler_gain_slider.setValue(0)
            self.basler_gain_input.setText("0.0")
            self.basler_gamma_slider.setValue(10)
            self.basler_gamma_input.setText("1.0")
            self.basler_black_slider.setValue(0)
            self.basler_black_input.setText("0")
        
        # Actualizar UI en sidebar (si existen)
        if hasattr(self, 'basler_sidebar_exposure_slider'):
            self.basler_sidebar_exposure_slider.setValue(10000)
            self.basler_sidebar_exposure_input.setText("10000")
            self.basler_sidebar_gain_slider.setValue(0)
            self.basler_sidebar_gain_input.setText("0.0")
            self.basler_sidebar_gamma_slider.setValue(10)
            self.basler_sidebar_gamma_input.setText("1.0")
            self.basler_sidebar_black_slider.setValue(0)
            self.basler_sidebar_black_input.setText("0")
        
        # Aplicar a cámara si está activa
        if self.basler_camera is not None:
            self.apply_basler_settings()
        
        self.log_to_console("Configuración Basler reseteada a valores por defecto", "INFO")
    
    def update_basler_exposure_from_slider(self):
        """Actualiza exposición desde el slider."""
        # Determinar qué slider se usó
        sender = self.sender()
        if hasattr(self, 'basler_exposure_slider') and sender == self.basler_exposure_slider:
            self.basler_exposure = float(self.basler_exposure_slider.value())
            self.basler_exposure_input.setText(f"{int(self.basler_exposure)}")
            # Sincronizar con sidebar
            if hasattr(self, 'basler_sidebar_exposure_slider'):
                self.basler_sidebar_exposure_slider.blockSignals(True)
                self.basler_sidebar_exposure_slider.setValue(int(self.basler_exposure))
                self.basler_sidebar_exposure_input.setText(f"{int(self.basler_exposure)}")
                self.basler_sidebar_exposure_slider.blockSignals(False)
        elif hasattr(self, 'basler_sidebar_exposure_slider') and sender == self.basler_sidebar_exposure_slider:
            self.basler_exposure = float(self.basler_sidebar_exposure_slider.value())
            self.basler_sidebar_exposure_input.setText(f"{int(self.basler_exposure)}")
            # Sincronizar con calibración
            if hasattr(self, 'basler_exposure_slider'):
                self.basler_exposure_slider.blockSignals(True)
                self.basler_exposure_slider.setValue(int(self.basler_exposure))
                self.basler_exposure_input.setText(f"{int(self.basler_exposure)}")
                self.basler_exposure_slider.blockSignals(False)
        
        if self.basler_camera is not None and self.basler_camera.IsGrabbing():
            try:
                self.basler_camera.ExposureTime.SetValue(self.basler_exposure)
            except:
                pass
    
    def update_basler_exposure_from_input(self):
        """Actualiza exposición desde el campo de texto."""
        sender = self.sender()
        try:
            if hasattr(self, 'basler_exposure_input') and sender == self.basler_exposure_input:
                value = float(self.basler_exposure_input.text())
                value = max(100, min(1000000, value))
                self.basler_exposure = value
                self.basler_exposure_slider.setValue(int(value))
                # Sincronizar con sidebar
                if hasattr(self, 'basler_sidebar_exposure_slider'):
                    self.basler_sidebar_exposure_slider.blockSignals(True)
                    self.basler_sidebar_exposure_slider.setValue(int(value))
                    self.basler_sidebar_exposure_input.setText(f"{int(value)}")
                    self.basler_sidebar_exposure_slider.blockSignals(False)
            elif hasattr(self, 'basler_sidebar_exposure_input') and sender == self.basler_sidebar_exposure_input:
                value = float(self.basler_sidebar_exposure_input.text())
                value = max(100, min(1000000, value))
                self.basler_exposure = value
                self.basler_sidebar_exposure_slider.setValue(int(value))
                # Sincronizar con calibración
                if hasattr(self, 'basler_exposure_slider'):
                    self.basler_exposure_slider.blockSignals(True)
                    self.basler_exposure_slider.setValue(int(value))
                    self.basler_exposure_input.setText(f"{int(value)}")
                    self.basler_exposure_slider.blockSignals(False)
            
            if self.basler_camera is not None and self.basler_camera.IsGrabbing():
                self.basler_camera.ExposureTime.SetValue(self.basler_exposure)
        except ValueError:
            if hasattr(self, 'basler_exposure_input') and sender == self.basler_exposure_input:
                self.basler_exposure_input.setText(f"{int(self.basler_exposure)}")
            elif hasattr(self, 'basler_sidebar_exposure_input') and sender == self.basler_sidebar_exposure_input:
                self.basler_sidebar_exposure_input.setText(f"{int(self.basler_exposure)}")
    
    def update_basler_gain_from_slider(self):
        """Actualiza ganancia desde el slider."""
        sender = self.sender()
        if hasattr(self, 'basler_gain_slider') and sender == self.basler_gain_slider:
            self.basler_gain = float(self.basler_gain_slider.value()) / 10.0
            self.basler_gain_input.setText(f"{self.basler_gain:.1f}")
            # Sincronizar con sidebar
            if hasattr(self, 'basler_sidebar_gain_slider'):
                self.basler_sidebar_gain_slider.blockSignals(True)
                self.basler_sidebar_gain_slider.setValue(int(self.basler_gain * 10))
                self.basler_sidebar_gain_input.setText(f"{self.basler_gain:.1f}")
                self.basler_sidebar_gain_slider.blockSignals(False)
        elif hasattr(self, 'basler_sidebar_gain_slider') and sender == self.basler_sidebar_gain_slider:
            self.basler_gain = float(self.basler_sidebar_gain_slider.value()) / 10.0
            self.basler_sidebar_gain_input.setText(f"{self.basler_gain:.1f}")
            # Sincronizar con calibración
            if hasattr(self, 'basler_gain_slider'):
                self.basler_gain_slider.blockSignals(True)
                self.basler_gain_slider.setValue(int(self.basler_gain * 10))
                self.basler_gain_input.setText(f"{self.basler_gain:.1f}")
                self.basler_gain_slider.blockSignals(False)
        
        if self.basler_camera is not None and self.basler_camera.IsGrabbing():
            try:
                self.basler_camera.Gain.SetValue(self.basler_gain)
            except:
                pass
    
    def update_basler_gain_from_input(self):
        """Actualiza ganancia desde el campo de texto."""
        sender = self.sender()
        try:
            if hasattr(self, 'basler_gain_input') and sender == self.basler_gain_input:
                value = float(self.basler_gain_input.text())
                value = max(0, min(24.0, value))
                self.basler_gain = value
                self.basler_gain_slider.setValue(int(value * 10))
                # Sincronizar con sidebar
                if hasattr(self, 'basler_sidebar_gain_slider'):
                    self.basler_sidebar_gain_slider.blockSignals(True)
                    self.basler_sidebar_gain_slider.setValue(int(value * 10))
                    self.basler_sidebar_gain_input.setText(f"{value:.1f}")
                    self.basler_sidebar_gain_slider.blockSignals(False)
            elif hasattr(self, 'basler_sidebar_gain_input') and sender == self.basler_sidebar_gain_input:
                value = float(self.basler_sidebar_gain_input.text())
                value = max(0, min(24.0, value))
                self.basler_gain = value
                self.basler_sidebar_gain_slider.setValue(int(value * 10))
                # Sincronizar con calibración
                if hasattr(self, 'basler_gain_slider'):
                    self.basler_gain_slider.blockSignals(True)
                    self.basler_gain_slider.setValue(int(value * 10))
                    self.basler_gain_input.setText(f"{value:.1f}")
                    self.basler_gain_slider.blockSignals(False)
            
            if self.basler_camera is not None and self.basler_camera.IsGrabbing():
                self.basler_camera.Gain.SetValue(self.basler_gain)
        except ValueError:
            if hasattr(self, 'basler_gain_input') and sender == self.basler_gain_input:
                self.basler_gain_input.setText(f"{self.basler_gain:.1f}")
            elif hasattr(self, 'basler_sidebar_gain_input') and sender == self.basler_sidebar_gain_input:
                self.basler_sidebar_gain_input.setText(f"{self.basler_gain:.1f}")
    
    def update_basler_gamma_from_slider(self):
        """Actualiza gamma desde el slider."""
        sender = self.sender()
        if hasattr(self, 'basler_gamma_slider') and sender == self.basler_gamma_slider:
            self.basler_gamma = float(self.basler_gamma_slider.value()) / 10.0
            self.basler_gamma_input.setText(f"{self.basler_gamma:.1f}")
            # Sincronizar con sidebar
            if hasattr(self, 'basler_sidebar_gamma_slider'):
                self.basler_sidebar_gamma_slider.blockSignals(True)
                self.basler_sidebar_gamma_slider.setValue(int(self.basler_gamma * 10))
                self.basler_sidebar_gamma_input.setText(f"{self.basler_gamma:.1f}")
                self.basler_sidebar_gamma_slider.blockSignals(False)
        elif hasattr(self, 'basler_sidebar_gamma_slider') and sender == self.basler_sidebar_gamma_slider:
            self.basler_gamma = float(self.basler_sidebar_gamma_slider.value()) / 10.0
            self.basler_sidebar_gamma_input.setText(f"{self.basler_gamma:.1f}")
            # Sincronizar con calibración
            if hasattr(self, 'basler_gamma_slider'):
                self.basler_gamma_slider.blockSignals(True)
                self.basler_gamma_slider.setValue(int(self.basler_gamma * 10))
                self.basler_gamma_input.setText(f"{self.basler_gamma:.1f}")
                self.basler_gamma_slider.blockSignals(False)
        
        if self.basler_camera is not None and self.basler_camera.IsGrabbing():
            try:
                if hasattr(self.basler_camera, 'Gamma'):
                    self.basler_camera.Gamma.SetValue(self.basler_gamma)
            except:
                pass
    
    def update_basler_gamma_from_input(self):
        """Actualiza gamma desde el campo de texto."""
        sender = self.sender()
        try:
            if hasattr(self, 'basler_gamma_input') and sender == self.basler_gamma_input:
                value = float(self.basler_gamma_input.text())
                value = max(0.1, min(4.0, value))
                self.basler_gamma = value
                self.basler_gamma_slider.setValue(int(value * 10))
                # Sincronizar con sidebar
                if hasattr(self, 'basler_sidebar_gamma_slider'):
                    self.basler_sidebar_gamma_slider.blockSignals(True)
                    self.basler_sidebar_gamma_slider.setValue(int(value * 10))
                    self.basler_sidebar_gamma_input.setText(f"{value:.1f}")
                    self.basler_sidebar_gamma_slider.blockSignals(False)
            elif hasattr(self, 'basler_sidebar_gamma_input') and sender == self.basler_sidebar_gamma_input:
                value = float(self.basler_sidebar_gamma_input.text())
                value = max(0.1, min(4.0, value))
                self.basler_gamma = value
                self.basler_sidebar_gamma_slider.setValue(int(value * 10))
                # Sincronizar con calibración
                if hasattr(self, 'basler_gamma_slider'):
                    self.basler_gamma_slider.blockSignals(True)
                    self.basler_gamma_slider.setValue(int(value * 10))
                    self.basler_gamma_input.setText(f"{value:.1f}")
                    self.basler_gamma_slider.blockSignals(False)
            
            if self.basler_camera is not None and self.basler_camera.IsGrabbing():
                if hasattr(self.basler_camera, 'Gamma'):
                    self.basler_camera.Gamma.SetValue(self.basler_gamma)
        except ValueError:
            if hasattr(self, 'basler_gamma_input') and sender == self.basler_gamma_input:
                self.basler_gamma_input.setText(f"{self.basler_gamma:.1f}")
            elif hasattr(self, 'basler_sidebar_gamma_input') and sender == self.basler_sidebar_gamma_input:
                self.basler_sidebar_gamma_input.setText(f"{self.basler_gamma:.1f}")
    
    def update_basler_black_from_slider(self):
        """Actualiza black level desde el slider."""
        sender = self.sender()
        if hasattr(self, 'basler_black_slider') and sender == self.basler_black_slider:
            self.basler_black_level = self.basler_black_slider.value()
            self.basler_black_input.setText(f"{self.basler_black_level}")
            # Sincronizar con sidebar
            if hasattr(self, 'basler_sidebar_black_slider'):
                self.basler_sidebar_black_slider.blockSignals(True)
                self.basler_sidebar_black_slider.setValue(self.basler_black_level)
                self.basler_sidebar_black_input.setText(f"{self.basler_black_level}")
                self.basler_sidebar_black_slider.blockSignals(False)
        elif hasattr(self, 'basler_sidebar_black_slider') and sender == self.basler_sidebar_black_slider:
            self.basler_black_level = self.basler_sidebar_black_slider.value()
            self.basler_sidebar_black_input.setText(f"{self.basler_black_level}")
            # Sincronizar con calibración
            if hasattr(self, 'basler_black_slider'):
                self.basler_black_slider.blockSignals(True)
                self.basler_black_slider.setValue(self.basler_black_level)
                self.basler_black_input.setText(f"{self.basler_black_level}")
                self.basler_black_slider.blockSignals(False)
        
        if self.basler_camera is not None and self.basler_camera.IsGrabbing():
            try:
                if hasattr(self.basler_camera, 'BlackLevel'):
                    self.basler_camera.BlackLevel.SetValue(self.basler_black_level)
            except:
                pass
    
    def update_basler_black_from_input(self):
        """Actualiza black level desde el campo de texto."""
        sender = self.sender()
        try:
            if hasattr(self, 'basler_black_input') and sender == self.basler_black_input:
                value = int(self.basler_black_input.text())
                value = max(0, min(255, value))
                self.basler_black_level = value
                self.basler_black_slider.setValue(value)
                # Sincronizar con sidebar
                if hasattr(self, 'basler_sidebar_black_slider'):
                    self.basler_sidebar_black_slider.blockSignals(True)
                    self.basler_sidebar_black_slider.setValue(value)
                    self.basler_sidebar_black_input.setText(f"{value}")
                    self.basler_sidebar_black_slider.blockSignals(False)
            elif hasattr(self, 'basler_sidebar_black_input') and sender == self.basler_sidebar_black_input:
                value = int(self.basler_sidebar_black_input.text())
                value = max(0, min(255, value))
                self.basler_black_level = value
                self.basler_sidebar_black_slider.setValue(value)
                # Sincronizar con calibración
                if hasattr(self, 'basler_black_slider'):
                    self.basler_black_slider.blockSignals(True)
                    self.basler_black_slider.setValue(value)
                    self.basler_black_input.setText(f"{value}")
                    self.basler_black_slider.blockSignals(False)
            
            if self.basler_camera is not None and self.basler_camera.IsGrabbing():
                if hasattr(self.basler_camera, 'BlackLevel'):
                    self.basler_camera.BlackLevel.SetValue(self.basler_black_level)
        except ValueError:
            if hasattr(self, 'basler_black_input') and sender == self.basler_black_input:
                self.basler_black_input.setText(f"{self.basler_black_level}")
            elif hasattr(self, 'basler_sidebar_black_input') and sender == self.basler_sidebar_black_input:
                self.basler_sidebar_black_input.setText(f"{self.basler_black_level}")

    def load_calibration_image(self):
        """Carga una imagen estática para calibración."""
        file_path, _ = QFileDialog.getOpenFileName(
            self, "Cargar Imagen de Calibración", "", 
            "Images (*.png *.jpg *.jpeg *.bmp *.tif *.tiff)"
        )
        
        if file_path:
            try:
                # Cargar imagen
                img = cv2.imread(file_path)
                if img is None:
                    raise Exception("No se pudo leer la imagen")
                
                img_rgb = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)
                self.calibration_image = img_rgb
                
                # Generar versión en escala de grises
                self.calibration_grayscale = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
                
                # Actualizar status
                self.calib_image_status.setText(f"   ✓ {os.path.basename(file_path)}")
                self.calib_image_status.setStyleSheet("font-size: 11px; color: #00CC00; margin-left: 40px;")
                
                # Mostrar en vista previa pestaña 1
                self.calib_preview_ax.clear()
                self.calib_preview_ax.imshow(img_rgb)
                self.calib_preview_ax.axis('off')
                self.calib_preview_canvas.draw()
                
                # Actualizar vista de escala de grises en pestaña 2
                if hasattr(self, 'gray_preview_ax'):
                    self.update_grayscale_preview()
                
                # Habilitar botones de análisis
                if hasattr(self, 'show_grayscale_button'):
                    self.show_grayscale_button.setEnabled(True)
                    self.analyze_intensity_button.setEnabled(True)
                    self.preview_threshold_button.setEnabled(True)
                    self.generate_attenuation_button.setEnabled(True)
                
            except Exception as e:
                QMessageBox.warning(self, "Error", f"Error al cargar imagen:\n{str(e)}")

    def toggle_mirror_preview(self):
        """Alterna el modo espejo en la vista previa."""
        self.update_grayscale_preview()

    def update_grayscale_preview(self):
        """Actualiza la vista previa en escala de grises."""
        if self.calibration_grayscale is None:
            return
        
        # Aplicar espejo si está activo
        display_image = self.calibration_grayscale.copy()
        if hasattr(self, 'mirror_preview_button') and self.mirror_preview_button.isChecked():
            display_image = cv2.flip(display_image, 1)
        
        self.gray_preview_ax.clear()
        self.gray_preview_ax.imshow(display_image, cmap='gray', vmin=0, vmax=255)
        self.gray_preview_ax.set_title('Vista en Escala de Grises', 
                                       color='#E0E0E0' if self.dark_mode else '#000000',
                                       fontsize=11)
        self.gray_preview_ax.axis('off')
        self.gray_preview_canvas.draw()
    
    def show_grayscale_fullscreen(self):
        """Muestra la imagen en escala de grises en pantalla completa."""
        if self.calibration_grayscale is None:
            QMessageBox.warning(self, "Advertencia", "No hay imagen disponible para mostrar")
            return
        
        # Crear ventana de proyección para escala de grises
        from PyQt5.QtWidgets import QDialog
        from PyQt5.QtCore import Qt
        
        fullscreen_dialog = QDialog(self)
        fullscreen_dialog.setWindowTitle("Visualización en Escala de Grises - Calibración")
        fullscreen_dialog.setWindowFlags(Qt.Window | Qt.WindowMaximizeButtonHint | Qt.WindowCloseButtonHint)
        
        layout = QVBoxLayout(fullscreen_dialog)
        layout.setContentsMargins(0, 0, 0, 0)
        
        # Canvas para mostrar escala de grises
        fig = Figure(facecolor='black')
        canvas = FigureCanvas(fig)
        ax = fig.add_subplot(111)
        ax.set_facecolor('black')
        
        # Mostrar imagen en escala de grises
        ax.imshow(self.calibration_grayscale, cmap='gray', vmin=0, vmax=255)
        ax.axis('off')
        fig.tight_layout(pad=0)
        canvas.draw()
        
        layout.addWidget(canvas)
        
        # Mostrar en pantalla completa o maximizado
        fullscreen_dialog.showMaximized()
        fullscreen_dialog.exec_()
    
    def analyze_brightness_zones(self):
        """Analiza las zonas de brillo de la imagen."""
        if self.calibration_grayscale is None:
            QMessageBox.warning(self, "Advertencia", "No hay imagen disponible para analizar")
            return
        
        # Obtener configuración de zonas
        zone_text = self.zone_grid_combo.currentText()
        
        if "Píxel a Píxel" in zone_text:
            self.analyze_pixel_by_pixel()
        else:
            # Extraer dimensiones del grid (ej: "4x4" de "4x4 (16 zonas)")
            grid_size = zone_text.split()[0]  # "4x4"
            rows, cols = map(int, grid_size.split('x'))
            self.analyze_zone_grid(rows, cols)
    
    def analyze_zone_grid(self, rows, cols):
        """Analiza la imagen dividida en una cuadrícula de zonas."""
        gray = self.calibration_grayscale
        h, w = gray.shape
        
        zone_h = h // rows
        zone_w = w // cols
        
        # Matriz para almacenar intensidades promedio de cada zona
        intensity_matrix = np.zeros((rows, cols))
        
        for i in range(rows):
            for j in range(cols):
                y_start = i * zone_h
                y_end = (i + 1) * zone_h if i < rows - 1 else h
                x_start = j * zone_w
                x_end = (j + 1) * zone_w if j < cols - 1 else w
                
                zone = gray[y_start:y_end, x_start:x_end]
                intensity_matrix[i, j] = np.mean(zone)
        
        # Convertir a porcentajes (0-100%)
        intensity_percentages = (intensity_matrix / 255.0) * 100.0
        
        # Guardar datos
        self.calibration_intensity_data = {
            'type': 'grid',
            'rows': rows,
            'cols': cols,
            'intensities': intensity_percentages,
            'raw_matrix': intensity_matrix
        }
        
        # Actualizar visualización
        self.update_intensity_analysis()
        
        # Calcular y mostrar estadísticas
        self.update_brightness_statistics(intensity_percentages)
    
    def analyze_pixel_by_pixel(self):
        """Analiza cada píxel individualmente."""
        gray = self.calibration_grayscale
        
        # Convertir a porcentajes
        intensity_percentages = (gray.astype(float) / 255.0) * 100.0
        
        # Guardar datos
        self.calibration_intensity_data = {
            'type': 'pixel',
            'intensities': intensity_percentages,
            'raw_matrix': gray
        }
        
        # Actualizar visualización
        self.update_intensity_analysis()
        
        # Calcular y mostrar estadísticas
        self.update_brightness_statistics(intensity_percentages)
    
    def update_intensity_analysis(self):
        """Actualiza la visualización del análisis de intensidad."""
        if self.calibration_intensity_data is None:
            return
        
        data = self.calibration_intensity_data
        intensities = data['intensities']
        
        self.intensity_map_figure.clear()
        self.intensity_map_ax = self.intensity_map_figure.add_subplot(111)
        
        show_heatmap = self.show_heatmap_check.isChecked()
        show_percentages = self.show_percentages_check.isChecked()
        
        if show_heatmap:
            im = self.intensity_map_ax.imshow(intensities, cmap='hot', vmin=0, vmax=100, 
                                              interpolation='nearest' if data['type'] == 'grid' else 'bilinear')
            cbar = self.intensity_map_figure.colorbar(im, ax=self.intensity_map_ax, 
                                                      orientation='vertical', pad=0.02)
            cbar.set_label('Intensidad (%)', rotation=270, labelpad=20,
                          color='#E0E0E0' if self.dark_mode else '#000000')
            cbar.ax.tick_params(colors='#E0E0E0' if self.dark_mode else '#000000')
        else:
            self.intensity_map_ax.imshow(intensities, cmap='gray', vmin=0, vmax=100)
        
        if show_percentages and data['type'] == 'grid':
            rows, cols = data['rows'], data['cols']
            
            for i in range(rows):
                for j in range(cols):
                    value = intensities[i, j]
                    
                    text_color = 'black' if value > 50 else 'white'
                    
                    self.intensity_map_ax.text(j, i, f'{value:.1f}%',
                                              ha='center', va='center',
                                              color=text_color, fontsize=8,
                                              weight='bold')
        
        self.intensity_map_ax.set_title('Mapa de Intensidad de Brillo',
                                       color='#E0E0E0' if self.dark_mode else '#000000',
                                       fontsize=12, pad=10)
        self.intensity_map_ax.axis('off')
        
        self.intensity_map_figure.tight_layout()
        self.intensity_map_canvas.draw()
    
    def update_brightness_statistics(self, intensities):
        """Actualiza las estadísticas de brillo y uniformidad."""
        avg = np.mean(intensities)
        min_val = np.min(intensities)
        max_val = np.max(intensities)
        std = np.std(intensities)
        
        # Actualizar labels
        self.brightness_avg_label.setText(f"Promedio: {avg:.1f}%")
        self.brightness_min_label.setText(f"Mínimo: {min_val:.1f}%")
        self.brightness_max_label.setText(f"Máximo: {max_val:.1f}%")
        self.brightness_std_label.setText(f"Desv. Est.: {std:.1f}%")
        
        # Calcular uniformidad (100% - coeficiente de variación)
        # Uniformidad alta = desviación baja
        if avg > 0:
            cv = (std / avg) * 100  # Coeficiente de variación
            uniformity = max(0, 100 - cv)
        else:
            uniformity = 0
        
        self.uniformity_indicator.setText(f"{uniformity:.1f}%")
        
        # Colorear según uniformidad
        if uniformity >= 90:
            color = "#00FF00"  
            status = "✓ Excelente"
        elif uniformity >= 75:
            color = "#88FF00"  
            status = "✓ Buena"
        elif uniformity >= 60:
            color = "#FFFF00"  
            status = "⚠ Aceptable"
        elif uniformity >= 40:
            color = "#FF8800" 
            status = "⚠ Baja"
        else:
            color = "#FF0000"  
            status = "✗ Muy Baja"
        
        self.uniformity_indicator.setStyleSheet(f"font-size: 16px; font-weight: bold; color: {color};")
        self.uniformity_status.setText(status)
        self.uniformity_status.setStyleSheet(f"font-size: 11px; color: {color};")

    def update_calibration_threshold_from_slider(self):
        """Actualiza el umbral de calibración desde el slider."""
        self.calibration_threshold = float(self.calib_threshold_slider.value())
        self.calib_threshold_input.setText(f"{self.calibration_threshold:.1f}")
    
    def update_calibration_threshold_from_input(self):
        """Actualiza el umbral de calibración desde el input."""
        try:
            value = float(self.calib_threshold_input.text())
            if 0 <= value <= 100:
                self.calibration_threshold = value
                self.calib_threshold_slider.setValue(int(round(value)))
            else:
                self.calib_threshold_input.setText(f"{self.calibration_threshold:.1f}")
        except ValueError:
            self.calib_threshold_input.setText(f"{self.calibration_threshold:.1f}")
    
    def preview_threshold_conversion(self):
        """Previsualiza la conversión binaria con el umbral actual."""
        if self.calibration_grayscale is None:
            QMessageBox.warning(self, "Advertencia", "No hay imagen disponible")
            return
        
        # Convertir a porcentajes
        intensity_percent = (self.calibration_grayscale.astype(float) / 255.0) * 100.0
        
        # Aplicar umbral
        binary_image = np.where(intensity_percent >= self.calibration_threshold, 255, 0).astype(np.uint8)
        
        # Calcular estadísticas
        total_pixels = binary_image.size
        white_pixels = np.sum(binary_image == 255)
        black_pixels = np.sum(binary_image == 0)
        
        white_percent = (white_pixels / total_pixels) * 100
        black_percent = (black_pixels / total_pixels) * 100
        
        # Actualizar labels
        self.threshold_white_label.setText(f"Píxeles Blancos: {white_percent:.1f}%")
        self.threshold_black_label.setText(f"Píxeles Negros: {black_percent:.1f}%")
        
        # Visualizar
        self.threshold_preview_ax.clear()
        self.threshold_preview_ax.imshow(binary_image, cmap='gray', vmin=0, vmax=255)
        self.threshold_preview_ax.set_title(f'Conversión Binaria (Umbral: {self.calibration_threshold:.1f}%)',
                                           color='#E0E0E0' if self.dark_mode else '#000000',
                                           fontsize=11)
        self.threshold_preview_ax.axis('off')
        self.threshold_preview_canvas.draw()

    def save_calibration_data(self, *args):
        """Guarda los datos de calibración en archivos."""
        try:
            import json
            import os
            
            cache_dir = "cache_photolith"
            if not os.path.exists(cache_dir):
                os.makedirs(cache_dir)
            
            if self.attenuation_matrix is not None:
                np.save(os.path.join(cache_dir, "calibration_matrix.npy"), self.attenuation_matrix)
            config = {
                "strength": self.attenuation_strength,
                "method_index": self.attenuation_method_combo.currentIndex(),
                "enabled": self.apply_attenuation_to_grid,
                "threshold": self.calibration_threshold,
                "flip_x": self.calibration_flip_x,
                "flip_y": self.calibration_flip_y
            }
            
            with open(os.path.join(cache_dir, "calibration_config.json"), 'w') as f:
                json.dump(config, f)
                
            self.log_to_console("Datos de calibración guardados correctamente", "INFO")
            
        except Exception as e:
            self.log_to_console(f"Error al guardar calibración: {str(e)}", "ERROR")

    def load_calibration_data(self):
        """Carga los datos de calibración guardados."""
        try:
            import json
            import os
            
            cache_dir = "cache_photolith"
            matrix_path = os.path.join(cache_dir, "calibration_matrix.npy")
            config_path = os.path.join(cache_dir, "calibration_config.json")
            
            if os.path.exists(matrix_path):
                self.attenuation_matrix = np.load(matrix_path)
                if hasattr(self, 'system_console'):
                    self.log_to_console("Matriz de calibración cargada", "INFO")
            if os.path.exists(config_path):
                with open(config_path, 'r') as f:
                    config = json.load(f)
                
                if "strength" in config:
                    self.attenuation_strength = config["strength"]
                    if hasattr(self, 'attenuation_strength_slider'):
                        self.attenuation_strength_slider.setValue(int(self.attenuation_strength))
                        self.attenuation_strength_label.setText(f"{self.attenuation_strength}%")
                
                if "method_index" in config:
                    if hasattr(self, 'attenuation_method_combo'):
                        self.attenuation_method_combo.setCurrentIndex(config["method_index"])
                
                if "enabled" in config:
                    self.apply_attenuation_to_grid = config["enabled"]
                    if hasattr(self, 'apply_attenuation_check'):
                        self.apply_attenuation_check.setChecked(self.apply_attenuation_to_grid)
                    # Actualizar label de estado
                    if hasattr(self, 'calibration_status_label'):
                        self.calibration_status_label.setText(f"Calibración: {'✓ Activa' if self.apply_attenuation_to_grid else 'Inactiva'}")
                
                if "threshold" in config:
                    self.calibration_threshold = config["threshold"]
                    if hasattr(self, 'calib_threshold_slider'):
                        self.calib_threshold_slider.setValue(int(self.calibration_threshold))
                        self.calib_threshold_input.setText(f"{self.calibration_threshold:.1f}")
                
                if "flip_x" in config:
                    self.calibration_flip_x = config["flip_x"]
                    if hasattr(self, 'calib_flip_x_checkbox'):
                        self.calib_flip_x_checkbox.setChecked(self.calibration_flip_x)
                
                if "flip_y" in config:
                    self.calibration_flip_y = config["flip_y"]
                    if hasattr(self, 'calib_flip_y_checkbox'):
                        self.calib_flip_y_checkbox.setChecked(self.calibration_flip_y)
                
                if hasattr(self, 'system_console'):
                    self.log_to_console("Configuración de calibración cargada", "INFO")
                
        except Exception as e:
            if hasattr(self, 'system_console'):
                self.log_to_console(f"Error al cargar calibración: {str(e)}", "ERROR")
            else:
                print(f"Error al cargar calibración: {str(e)}")
    
    def toggle_calibration_flip_x(self, state):
        """Activa/desactiva el flip horizontal de la matriz de calibración."""
        self.calibration_flip_x = bool(state)
        self.save_calibration_data()
        self.log_to_console(
            f"🔄 Flip X de calibración: {'✓ Activo' if self.calibration_flip_x else '✗ Inactivo'}",
            "INFO"
        )
        if hasattr(self, 'update_calibration_preview'):
            self.update_calibration_preview()
    
    def toggle_calibration_flip_y(self, state):
        """Activa/desactiva el flip vertical de la matriz de calibración."""
        self.calibration_flip_y = bool(state)
        self.save_calibration_data()
        self.log_to_console(
            f"🔄 Flip Y de calibración: {'✓ Activo' if self.calibration_flip_y else '✗ Inactivo'}",
            "INFO"
        )
        if hasattr(self, 'update_calibration_preview'):
            self.update_calibration_preview()
    
    def get_calibration_matrix_with_flips(self):
        """
        Obtiene la matriz de calibración con los flips aplicados según la configuración.
        
        Returns:
            numpy.ndarray: Matriz de calibración con flips aplicados, o None si no hay matriz
        """
        if self.attenuation_matrix is None:
            return None
        
        matrix = self.attenuation_matrix.copy()
        
        # Aplicar flip horizontal (eje X) si está activo
        if self.calibration_flip_x:
            matrix = np.fliplr(matrix)  # Flip left-right
        
        # Aplicar flip vertical (eje Y) si está activo
        if self.calibration_flip_y:
            matrix = np.flipud(matrix)  # Flip up-down
        
        return matrix
    
    def update_calibration_monitor(self):
        """
        Actualiza el monitor de calibración en tiempo real con el estado actual
        de todos los efectos y parámetros de calibración.
        """
        try:
            # ═══════════════════════════════════════════════════════════════════
            # ESTADO DE CALIBRACIÓN
            # ═══════════════════════════════════════════════════════════════════
            if hasattr(self, 'attenuation_matrix') and self.attenuation_matrix is not None:
                matrix_shape = self.attenuation_matrix.shape
                self.calib_status_label.setText(
                    f"✅ Calibración cargada ({matrix_shape[1]}×{matrix_shape[0]} px)"
                )
                self.calib_status_label.setStyleSheet("font-size: 10px; color: #51CF66;")
            else:
                self.calib_status_label.setText("❌ Sin calibración cargada")
                self.calib_status_label.setStyleSheet("font-size: 10px; color: #FF6B6B;")
            
            # Estado de aplicación
            if hasattr(self, 'apply_attenuation_to_grid') and self.apply_attenuation_to_grid:
                self.calib_apply_status_label.setText("✅ Aplicación: ACTIVA")
                self.calib_apply_status_label.setStyleSheet("font-size: 10px; color: #51CF66;")
            else:
                self.calib_apply_status_label.setText("⚪ Aplicación: Inactiva")
                self.calib_apply_status_label.setStyleSheet("font-size: 10px; color: #888888;")
            
            # ═══════════════════════════════════════════════════════════════════
            # PARÁMETROS DE ATENUACIÓN
            # ═══════════════════════════════════════════════════════════════════
            if hasattr(self, 'calibration_threshold'):
                self.atten_threshold_label.setText(f"• Threshold: {self.calibration_threshold:.1f}%")
            else:
                self.atten_threshold_label.setText("• Threshold: No configurado")
            
            if hasattr(self, 'attenuation_matrix') and self.attenuation_matrix is not None:
                min_val = self.attenuation_matrix.min()
                max_val = self.attenuation_matrix.max()
                self.atten_min_label.setText(f"• Valor mínimo: {min_val:.3f}")
                self.atten_max_label.setText(f"• Valor máximo: {max_val:.3f}")
            else:
                self.atten_min_label.setText("• Valor mínimo: -")
                self.atten_max_label.setText("• Valor máximo: -")
            
            # ═══════════════════════════════════════════════════════════════════
            # EFECTOS ACTIVOS
            # ═══════════════════════════════════════════════════════════════════
            if hasattr(self, 'sigma'):
                if self.sigma > 0:
                    self.effect_sigma_label.setText(f"• Sigma (Blur): ✅ {self.sigma:.2f}")
                    self.effect_sigma_label.setStyleSheet("font-size: 10px; color: #51CF66;")
                else:
                    self.effect_sigma_label.setText(f"• Sigma (Blur): ⚪ Desactivado")
                    self.effect_sigma_label.setStyleSheet("font-size: 10px; color: #888888;")
            
            if hasattr(self, 'downscale_factor'):
                if self.downscale_factor != 1.0:
                    self.effect_downscale_label.setText(f"• Downscaling: ✅ {self.downscale_factor:.2f}x")
                    self.effect_downscale_label.setStyleSheet("font-size: 10px; color: #51CF66;")
                else:
                    self.effect_downscale_label.setText(f"• Downscaling: ⚪ Sin reducción")
                    self.effect_downscale_label.setStyleSheet("font-size: 10px; color: #888888;")
            
            if hasattr(self, 'brightness'):
                if self.brightness != 100:
                    self.effect_brightness_label.setText(f"• Brillo: ✅ {self.brightness}%")
                    self.effect_brightness_label.setStyleSheet("font-size: 10px; color: #51CF66;")
                else:
                    self.effect_brightness_label.setText(f"• Brillo: ⚪ 100% (sin ajuste)")
                    self.effect_brightness_label.setStyleSheet("font-size: 10px; color: #888888;")
            
            if hasattr(self, 'binary_mode_enabled'):
                if self.binary_mode_enabled:
                    threshold = self.binary_threshold if hasattr(self, 'binary_threshold') else 50
                    self.effect_binary_label.setText(f"• Modo Binario: ✅ Activo (Th: {threshold:.0f})")
                    self.effect_binary_label.setStyleSheet("font-size: 10px; color: #51CF66;")
                else:
                    self.effect_binary_label.setText(f"• Modo Binario: ⚪ Desactivado")
                    self.effect_binary_label.setStyleSheet("font-size: 10px; color: #888888;")
            
            if hasattr(self, 'invert_projection'):
                if self.invert_projection:
                    self.effect_invert_label.setText(f"• Inversión: ✅ Activa")
                    self.effect_invert_label.setStyleSheet("font-size: 10px; color: #51CF66;")
                else:
                    self.effect_invert_label.setText(f"• Inversión: ⚪ Desactivada")
                    self.effect_invert_label.setStyleSheet("font-size: 10px; color: #888888;")
            
            self.log_to_console("✅ Monitor de calibración actualizado", "INFO")
            
        except Exception as e:
            self.log_to_console(f"❌ Error al actualizar monitor: {str(e)}", "ERROR")
    
    def update_calibration_preview(self, show_mode='split'):
        """
        Actualiza el preview de calibración mostrando antes/después.
        
        Args:
            show_mode: 'before', 'after', o 'split' (lado a lado)
        """
        try:
            if not hasattr(self, 'calib_preview_figure'):
                return
            
            # Actualizar valor del slider
            if hasattr(self, 'calib_preview_strength_slider'):
                strength = self.calib_preview_strength_slider.value()
                self.calib_preview_strength_value.setText(f"{strength}%")
            else:
                strength = 100
            
            self.calib_preview_figure.clear()
            
            # Verificar si hay imagen y calibración disponible
            if self.pattern is None:
                ax = self.calib_preview_figure.add_subplot(111)
                ax.text(0.5, 0.5, 'Cargue una imagen\npara ver preview', 
                       ha='center', va='center', fontsize=10, color='gray')
                ax.axis('off')
                self.calib_preview_canvas.draw()
                return
            
            if not hasattr(self, 'attenuation_matrix') or self.attenuation_matrix is None:
                ax = self.calib_preview_figure.add_subplot(111)
                ax.text(0.5, 0.5, 'Genere una matriz\nde calibración', 
                       ha='center', va='center', fontsize=10, color='gray')
                ax.axis('off')
                self.calib_preview_canvas.draw()
                return
            
            # Obtener región central de la imagen para preview (más rápido)
            h, w = self.pattern.shape[:2]
            center_h, center_w = h // 2, w // 2
            size = min(200, h // 2, w // 2)
            
            y1, y2 = center_h - size, center_h + size
            x1, x2 = center_w - size, center_w + size
            
            sample = self.pattern[y1:y2, x1:x2].copy()
            
            # Obtener matriz con flips aplicados
            calibration_matrix = self.get_calibration_matrix_with_flips()
            
            # Aplicar calibración con la intensidad del slider
            if sample.shape[:2] == calibration_matrix.shape[:2]:
                # Tamaños coinciden - aplicar directamente
                calibrated = sample.copy()
            else:
                # Redimensionar matriz al tamaño de la muestra
                import cv2
                matrix_resized = cv2.resize(
                    calibration_matrix[y1:y2, x1:x2],
                    (sample.shape[1], sample.shape[0]),
                    interpolation=cv2.INTER_LINEAR
                )
                calibrated = sample.copy()
            
            # Aplicar calibración con strength ajustable
            strength_factor = strength / 100.0
            if sample.shape[:2] == calibration_matrix.shape[:2]:
                matrix_to_use = calibration_matrix[y1:y2, x1:x2]
            else:
                matrix_to_use = matrix_resized
            
            adjusted_matrix = 1.0 + (matrix_to_use - 1.0) * strength_factor
            calibrated = np.clip(sample * adjusted_matrix, 0, 1.0)
            
            # Mostrar según el modo
            if show_mode == 'before':
                ax = self.calib_preview_figure.add_subplot(111)
                ax.imshow(sample, cmap='gray', vmin=0, vmax=1)
                ax.set_title('Original (Sin Calibración)', fontsize=9)
                ax.axis('off')
            elif show_mode == 'after':
                ax = self.calib_preview_figure.add_subplot(111)
                ax.imshow(calibrated, cmap='gray', vmin=0, vmax=1)
                ax.set_title(f'Calibrado ({strength}%)', fontsize=9)
                ax.axis('off')
            else:  # split
                ax1 = self.calib_preview_figure.add_subplot(121)
                ax1.imshow(sample, cmap='gray', vmin=0, vmax=1)
                ax1.set_title('Original', fontsize=8)
                ax1.axis('off')
                
                ax2 = self.calib_preview_figure.add_subplot(122)
                ax2.imshow(calibrated, cmap='gray', vmin=0, vmax=1)
                ax2.set_title(f'Calibrado {strength}%', fontsize=8)
                ax2.axis('off')
            
            self.calib_preview_figure.tight_layout(pad=0.5)
            self.calib_preview_canvas.draw()
            
        except Exception as e:
            self.log_to_console(f"❌ Error en preview de calibración: {str(e)}", "ERROR")
            import traceback
            traceback.print_exc()
    
    def generate_attenuation_matrix(self):
        """Genera la matriz de compensación basada en el análisis de intensidad."""
        if self.calibration_grayscale is None:
            QMessageBox.warning(self, "Advertencia", "No hay imagen disponible para generar matriz")
            return
        
        # Convertir a intensidades normalizadas (0-1)
        intensity = self.calibration_grayscale.astype(float) / 255.0
        
        # Obtener método seleccionado
        method_text = self.attenuation_method_combo.currentText()
        
        if "Inversión Normalizada" in method_text:
            # Método recomendado: inversión con normalización
            # Zonas oscuras reciben más corrección, zonas claras menos
            max_intensity = np.max(intensity)
            if max_intensity > 0:
                self.attenuation_matrix = max_intensity / (intensity + 0.01)  # +0.01 para evitar división por 0
                # Normalizar al rango [1, max_correction]
                self.attenuation_matrix = np.clip(self.attenuation_matrix, 1.0, 5.0)
            else:
                self.attenuation_matrix = np.ones_like(intensity)
                
        elif "Inversión Simple" in method_text:
            # Inversión directa
            self.attenuation_matrix = 1.0 / (intensity + 0.01)
            self.attenuation_matrix = np.clip(self.attenuation_matrix, 0.5, 2.0)
            
        elif "Ecualizador Adaptativo" in method_text:
            # Ecualización basada en desviación del promedio
            mean_intensity = np.mean(intensity)
            deviation = mean_intensity - intensity
            self.attenuation_matrix = 1.0 + (deviation * 2.0)
            self.attenuation_matrix = np.clip(self.attenuation_matrix, 0.5, 2.0)
            
        else:  # "Compensación Proporcional"
            # Corrección proporcional a la desviación
            target_intensity = np.percentile(intensity, 95)  # Usar percentil 95 como referencia
            self.attenuation_matrix = target_intensity / (intensity + 0.01)
            self.attenuation_matrix = np.clip(self.attenuation_matrix, 0.8, 1.5)
        
        # Habilitar controles
        self.apply_attenuation_check.setEnabled(True)
        self.preview_attenuation_button.setEnabled(True)
        self.save_attenuation_button.setEnabled(True)
        
        # Actualizar visualización
        self.update_attenuation_preview()
        
        # Actualizar estado
        matrix_min = np.min(self.attenuation_matrix)
        matrix_max = np.max(self.attenuation_matrix)
        self.matrix_status_label.setText(f"Estado: ✓ Matriz generada ({self.attenuation_matrix.shape[0]}×{self.attenuation_matrix.shape[1]})")
        self.matrix_range_label.setText(f"Rango: {matrix_min:.2f} - {matrix_max:.2f}")
        
        # Guardar calibración automáticamente
        self.save_calibration_data()
        
        # Actualizar monitor de calibración y preview
        if hasattr(self, 'update_calibration_monitor'):
            self.update_calibration_monitor()
        if hasattr(self, 'update_calibration_preview'):
            self.update_calibration_preview(show_mode='split')
        
        QMessageBox.information(self, "Éxito", 
                               f"Matriz de atenuación generada exitosamente.\n\n"
                               f"Dimensiones: {self.attenuation_matrix.shape[0]}×{self.attenuation_matrix.shape[1]}\n"
                               f"Rango de corrección: {matrix_min:.2f}x - {matrix_max:.2f}x")
    
    def update_attenuation_preview(self):
        """Actualiza la visualización de la matriz de atenuación."""
        if self.attenuation_matrix is None:
            return
        
        # Obtener intensidad de corrección
        strength = self.attenuation_strength_slider.value()
        self.attenuation_strength_label.setText(f"{strength}%")
        self.attenuation_strength = float(strength)
        
        # Obtener matriz con flips aplicados
        calibration_matrix = self.get_calibration_matrix_with_flips()
        
        # Aplicar intensidad (interpolar entre sin corrección [1.0] y corrección completa)
        strength_factor = strength / 100.0
        adjusted_matrix = 1.0 + (calibration_matrix - 1.0) * strength_factor
        
        # Limpiar figura completa para evitar colorbar duplicados
        self.attenuation_figure.clear()
        self.attenuation_ax = self.attenuation_figure.add_subplot(111)
        
        im = self.attenuation_ax.imshow(adjusted_matrix, cmap='viridis', 
                                        interpolation='bilinear')
        
        # Colorbar (solo una vez)
        cbar = self.attenuation_figure.colorbar(im, ax=self.attenuation_ax,
                                                orientation='vertical', pad=0.02)
        cbar.set_label('Factor de Corrección (×)', rotation=270, labelpad=20,
                      color='#E0E0E0' if self.dark_mode else '#000000')
        cbar.ax.tick_params(colors='#E0E0E0' if self.dark_mode else '#000000')
        
        self.attenuation_ax.set_title('Matriz de Compensación de Uniformidad',
                                     color='#E0E0E0' if self.dark_mode else '#000000',
                                     fontsize=12, pad=10)
        self.attenuation_ax.axis('off')
        
        self.attenuation_figure.tight_layout()
        self.attenuation_canvas.draw()
    
    def preview_attenuation_effect(self):
        """Previsualiza el efecto de la matriz de atenuación aplicada."""
        if self.attenuation_matrix is None or self.calibration_image is None:
            QMessageBox.warning(self, "Advertencia", 
                               "Necesita generar la matriz y tener una imagen cargada")
            return
        
        # Convertir imagen a escala de grises si es necesario
        if len(self.calibration_image.shape) == 3:
            gray = cv2.cvtColor(self.calibration_image, cv2.COLOR_RGB2GRAY)
        else:
            gray = self.calibration_image.copy()
        
        # Obtener matriz con flips aplicados
        calibration_matrix = self.get_calibration_matrix_with_flips()
        
        # Redimensionar matriz si es necesario
        if calibration_matrix.shape != gray.shape:
            from scipy.ndimage import zoom
            zoom_factors = (gray.shape[0] / calibration_matrix.shape[0],
                          gray.shape[1] / calibration_matrix.shape[1])
            attenuation_resized = zoom(calibration_matrix, zoom_factors, order=1)
        else:
            attenuation_resized = calibration_matrix
        
        # Aplicar matriz con intensidad ajustada
        strength_factor = self.attenuation_strength / 100.0
        adjusted_matrix = 1.0 + (attenuation_resized - 1.0) * strength_factor
        
        # Aplicar corrección
        corrected = gray.astype(float) * adjusted_matrix
        corrected = np.clip(corrected, 0, 255).astype(np.uint8)
        
        # Crear ventana de comparación
        comparison_dialog = QDialog(self)
        comparison_dialog.setWindowTitle("Comparación: Original vs Corregida")
        comparison_dialog.resize(1000, 500)
        
        layout = QVBoxLayout(comparison_dialog)
        
        # Canvas de comparación
        fig = Figure(facecolor='#121212' if self.dark_mode else '#FFFFFF')
        canvas = FigureCanvas(fig)
        
        # Subplot 1: Original
        ax1 = fig.add_subplot(1, 2, 1)
        ax1.imshow(gray, cmap='gray', vmin=0, vmax=255)
        ax1.set_title('Original', color='#E0E0E0' if self.dark_mode else '#000000')
        ax1.axis('off')
        
        # Subplot 2: Corregida
        ax2 = fig.add_subplot(1, 2, 2)
        ax2.imshow(corrected, cmap='gray', vmin=0, vmax=255)
        ax2.set_title('Con Matriz de Atenuación', color='#E0E0E0' if self.dark_mode else '#000000')
        ax2.axis('off')
        
        fig.tight_layout()
        canvas.draw()
        
        layout.addWidget(canvas)
        
        # Estadísticas
        stats_label = QLabel()
        orig_mean = np.mean(gray)
        corr_mean = np.mean(corrected)
        orig_std = np.std(gray)
        corr_std = np.std(corrected)
        
        stats_text = (f"<b>Estadísticas:</b><br>"
                     f"Original - Media: {orig_mean:.1f}, Desv.Est: {orig_std:.1f}<br>"
                     f"Corregida - Media: {corr_mean:.1f}, Desv.Est: {corr_std:.1f}<br>"
                     f"<b>Mejora en uniformidad: {((orig_std - corr_std) / orig_std * 100):.1f}%</b>")
        stats_label.setText(stats_text)
        layout.addWidget(stats_label)
        
        comparison_dialog.exec_()
    
    def toggle_attenuation_application(self, state):
        """Activa/desactiva la aplicación de la matriz al grid de proyección."""
        self.apply_attenuation_to_grid = bool(state)
        
        # Actualizar label de estado
        if hasattr(self, 'calibration_status_label'):
            self.calibration_status_label.setText(f"Calibración: {'✓ Activa' if self.apply_attenuation_to_grid else 'Inactiva'}")
        
        # Guardar estado
        self.save_calibration_data()
        
        if self.apply_attenuation_to_grid and self.attenuation_matrix is not None:
            QMessageBox.information(self, "Información",
                                   "La matriz de atenuación se aplicará automáticamente\n"
                                   "al grid de proyección para compensar la uniformidad.")
        
        # Actualizar grid si está activo
        if self.grid_view_active and hasattr(self, 'grid_generated') and self.grid_generated:
            self.display_grid()
        
        # Actualizar monitor de calibración y preview
        if hasattr(self, 'update_calibration_monitor'):
            self.update_calibration_monitor()
        if hasattr(self, 'update_calibration_preview'):
            self.update_calibration_preview(show_mode='split')
    
    def save_attenuation_matrix(self):
        """Guarda la matriz de atenuación en un archivo."""
        if self.attenuation_matrix is None:
            QMessageBox.warning(self, "Advertencia", "No hay matriz para guardar")
            return
        
        file_path, _ = QFileDialog.getSaveFileName(
            self, "Guardar Matriz de Atenuación", 
            "attenuation_matrix.npy",
            "NumPy Array (*.npy);;CSV File (*.csv)"
        )
        
        if file_path:
            try:
                if file_path.endswith('.npy'):
                    np.save(file_path, self.attenuation_matrix)
                else:
                    np.savetxt(file_path, self.attenuation_matrix, delimiter=',', fmt='%.6f')
                
                QMessageBox.information(self, "Éxito", 
                                       f"Matriz guardada exitosamente en:\n{file_path}")
            except Exception as e:
                QMessageBox.critical(self, "Error", f"Error al guardar matriz:\n{str(e)}")
    
    def load_attenuation_matrix(self):
        """Carga una matriz de atenuación desde un archivo."""
        file_path, _ = QFileDialog.getOpenFileName(
            self, "Cargar Matriz de Atenuación", "",
            "NumPy Array (*.npy);;CSV File (*.csv);;All Files (*)"
        )
        
        if file_path:
            try:
                if file_path.endswith('.npy'):
                    self.attenuation_matrix = np.load(file_path)
                else:
                    self.attenuation_matrix = np.loadtxt(file_path, delimiter=',')
                
                # Habilitar controles
                self.apply_attenuation_check.setEnabled(True)
                self.preview_attenuation_button.setEnabled(True)
                self.save_attenuation_button.setEnabled(True)
                
                # Actualizar visualización
                self.update_attenuation_preview()
                
                # Actualizar estado
                matrix_min = np.min(self.attenuation_matrix)
                matrix_max = np.max(self.attenuation_matrix)
                self.matrix_status_label.setText(f"Estado: ✓ Matriz cargada ({self.attenuation_matrix.shape[0]}×{self.attenuation_matrix.shape[1]})")
                self.matrix_range_label.setText(f"Rango: {matrix_min:.2f} - {matrix_max:.2f}")
                
                QMessageBox.information(self, "Éxito", 
                                       f"Matriz cargada exitosamente.\n\n"
                                       f"Dimensiones: {self.attenuation_matrix.shape[0]}×{self.attenuation_matrix.shape[1]}")
            except Exception as e:
                QMessageBox.critical(self, "Error", f"Error al cargar matriz:\n{str(e)}")

    def on_calibration_source_changed(self, button):
        """Maneja el cambio de fuente de calibración."""
        if button == self.camera_radio:
            self.calibration_source = "camera"
            # Habilitar controles de cámara OpenCV
            self.camera_combo.setEnabled(True)
            self.refresh_cameras_button.setEnabled(True)
            self.start_camera_button.setEnabled(True)
            self.load_calib_image_button.setEnabled(False)
            # Deshabilitar Basler si está activa
            if BASLER_AVAILABLE and self.basler_camera is not None:
                self.stop_basler_capture()
            if BASLER_AVAILABLE:
                self.start_basler_button.setEnabled(False)
        elif BASLER_AVAILABLE and button == self.basler_radio:
            self.calibration_source = "basler"
            # Habilitar controles de cámara Basler
            self.start_basler_button.setEnabled(True)
            self.load_calib_image_button.setEnabled(False)
            # Deshabilitar cámara OpenCV si está activa
            if self.calibration_camera is not None:
                self.stop_camera_capture()
            self.camera_combo.setEnabled(False)
            self.refresh_cameras_button.setEnabled(False)
            self.start_camera_button.setEnabled(False)
        else:
            self.calibration_source = "image"
            # Deshabilitar todas las cámaras y detener si están activas
            if self.calibration_camera is not None:
                self.stop_camera_capture()
            if BASLER_AVAILABLE and self.basler_camera is not None:
                self.stop_basler_capture()
            self.camera_combo.setEnabled(False)
            self.refresh_cameras_button.setEnabled(False)
            self.start_camera_button.setEnabled(False)
            if BASLER_AVAILABLE:
                self.start_basler_button.setEnabled(False)
            self.load_calib_image_button.setEnabled(True)

    def generate_grid(self):
        """
        Genera el grid de litografía con precisión float para todas las dimensiones.
        Unidades: μm, mm, cm (configurables), con resolución en px/unidad.
        """
        try:
            # Convertir a float para máxima precisión litográfica
            self.grid_width = float(self.grid_width_input.text())
            self.grid_height = float(self.grid_height_input.text())
            self.grid_cell_size = float(self.grid_cell_input.text())
            self.grid_pixels_per_cell = int(self.grid_pixels_input.text())
            self.grid_unit = self.grid_unit_combo.currentText()

            if self.grid_width <= 0 or self.grid_height <= 0 or self.grid_cell_size <= 0 or self.grid_pixels_per_cell <= 0:
                QMessageBox.warning(
                    self,
                    "Valores inválidos",
                    "Los valores deben ser mayores que cero."
                )
                return

            self.save_grid_config()
            self.grid_generated = True
            self.generate_grid_button.setText("💾 Guardar Nuevo Tamaño")
            self.display_grid()
            
            # Actualizar información de segmentación si está en modo automático
            if self.segmentation_mode == 0:
                self.update_segmentation_preview()

        except ValueError:
            QMessageBox.warning(
                self,
                "Error de entrada",
                "Por favor ingrese valores numéricos válidos."
            )
        except Exception as e:
            QMessageBox.critical(
                self,
                "Error",
                f"Error al generar el grid: {str(e)}"
            )

    def display_grid(self):
        try:
            import numpy as np

            cells_x = int(self.grid_width / self.grid_cell_size)
            cells_y = int(self.grid_height / self.grid_cell_size)

            self.canvas.figure.clear()
            self.ax = self.canvas.figure.add_subplot(111)
            self.ax.set_facecolor("#1E1E1E" if self.dark_mode else "#FFFFFF")

            for i in range(cells_x + 1):
                x_pos = i * self.grid_cell_size
                self.ax.axvline(x=x_pos, color=self.grid_color, linewidth=1, alpha=0.8)

            for i in range(cells_y + 1):
                y_pos = i * self.grid_cell_size
                self.ax.axhline(y=y_pos, color=self.grid_color, linewidth=1, alpha=0.8)

            # Dibujar grilla de píxeles si está activada
            if self.show_pixel_grid:
                self._draw_pixel_grid()

            self.ax.set_xlim(0, self.grid_width)
            self.ax.set_ylim(0, self.grid_height)
            
            # Conectar evento para redibujar grid de píxeles cuando se hace zoom/pan
            if self.show_pixel_grid:
                self.ax.callbacks.connect('xlim_changed', self._on_zoom_or_pan)
                self.ax.callbacks.connect('ylim_changed', self._on_zoom_or_pan)
            self.ax.set_aspect('equal')

            self.ax.set_xlabel(f'Ancho ({self.grid_unit})', 
                             color='#E0E0E0' if self.dark_mode else '#000000')
            self.ax.set_ylabel(f'Alto ({self.grid_unit})', 
                             color='#E0E0E0' if self.dark_mode else '#000000')
            self.ax.tick_params(colors='#E0E0E0' if self.dark_mode else '#000000')

            for spine in self.ax.spines.values():
                spine.set_edgecolor('#E0E0E0' if self.dark_mode else '#000000')

            # Superponer imagen si existe
            if self.image_on_grid is not None:
                self.overlay_image_on_grid()
            
            # Dibujar overlay de segmentos si está activo
            self.draw_segments_overlay()
            
            # Dibujar resaltado del chunk que se está proyectando actualmente
            self.draw_projecting_segment_highlight()

            self.canvas.draw()

            resolution = self.grid_pixels_per_cell / self.grid_cell_size
            pixel_size = self.grid_cell_size / self.grid_pixels_per_cell

            self.grid_dimensions_label.setText(f"Dimensiones: {self.grid_width} x {self.grid_height} {self.grid_unit}")
            self.grid_cells_x_label.setText(f"Celdas X: {cells_x}")
            self.grid_cells_y_label.setText(f"Celdas Y: {cells_y}")
            self.grid_cell_size_label.setText(f"Tamaño celda: {self.grid_cell_size} {self.grid_unit}")
            self.grid_pixels_label.setText(f"Píxeles/celda: {self.grid_pixels_per_cell} px")
            self.grid_resolution_label.setText(f"Resolución: {resolution:.2f} px/{self.grid_unit}")
            self.grid_pixel_size_label.setText(f"Tamaño píxel: {pixel_size:.4f} {self.grid_unit}/px")
            self.grid_total_cells_label.setText(f"Total celdas: {cells_x * cells_y}")
            self.grid_color_label.setText(f"Color: {self.grid_color}")

            self.grid_stats_section.setVisible(True)
            self.grid_stats_section.set_collapsed(False)
            self.grid_status_label.setText(f"✅ Grid: {cells_x}x{cells_y} celdas")

        except Exception as e:
            QMessageBox.critical(
                self,
                "Error",
                f"Error al mostrar el grid: {str(e)}"
            )

    def _draw_pixel_grid(self):
        """
        Dibuja el grid de píxeles basándose en la vista actual (zoom).
        Solo dibuja las líneas visibles en la vista actual para optimizar rendimiento.
        """
        if not hasattr(self, 'ax') or self.ax is None:
            return
        
        # Obtener límites visibles actuales
        xlim = self.ax.get_xlim()
        ylim = self.ax.get_ylim()
        
        pixel_step = self.grid_cell_size / self.grid_pixels_per_cell
        
        # Calcular número de líneas de píxeles en la región VISIBLE
        visible_width = xlim[1] - xlim[0]
        visible_height = ylim[1] - ylim[0]
        visible_pixel_lines_x = int(visible_width / pixel_step)
        visible_pixel_lines_y = int(visible_height / pixel_step)
        
        max_pixel_lines = 1000  # Límite para mantener rendimiento óptimo
        
        # Solo dibujar si el número de líneas es razonable
        if (visible_pixel_lines_x + visible_pixel_lines_y) <= max_pixel_lines:
            # Calcular índices de las líneas visibles
            start_x = int(xlim[0] / pixel_step)
            end_x = int(xlim[1] / pixel_step) + 1
            start_y = int(ylim[0] / pixel_step)
            end_y = int(ylim[1] / pixel_step) + 1
            
            # Dibujar líneas verticales de píxeles (solo las visibles)
            for i in range(start_x, end_x):
                x_pos = i * pixel_step
                # Verificar que está en el rango del grid y no es línea principal
                if 0 <= x_pos <= self.grid_width and x_pos % self.grid_cell_size != 0:
                    self.ax.axvline(x=x_pos, color=self.grid_pixel_color, 
                                  linewidth=0.5, alpha=0.5)
            
            # Dibujar líneas horizontales de píxeles (solo las visibles)
            for i in range(start_y, end_y):
                y_pos = i * pixel_step
                # Verificar que está en el rango del grid y no es línea principal
                if 0 <= y_pos <= self.grid_height and y_pos % self.grid_cell_size != 0:
                    self.ax.axhline(y=y_pos, color=self.grid_pixel_color, 
                                  linewidth=0.5, alpha=0.5)
    
    def _on_zoom_or_pan(self, event=None):
        """
        Callback que se ejecuta cuando se hace zoom o pan.
        Redibuja el grid de píxeles solo en la región visible.
        """
        if not self.show_pixel_grid or not hasattr(self, 'ax') or self.ax is None:
            return
        
        # Evitar recursión: desconectar temporalmente los callbacks
        if hasattr(self, '_updating_pixel_grid') and self._updating_pixel_grid:
            return
        
        self._updating_pixel_grid = True
        
        try:
            # Guardar límites actuales
            xlim = self.ax.get_xlim()
            ylim = self.ax.get_ylim()
            
            # Eliminar solo las líneas de píxeles (las delgadas)
            # Mantener las líneas principales del grid (las gruesas)
            lines_to_remove = []
            for line in self.ax.get_lines():
                if line.get_linewidth() < 1.0:  # Las líneas de píxeles son más delgadas
                    lines_to_remove.append(line)
            
            for line in lines_to_remove:
                line.remove()
            
            # Redibujar grid de píxeles en la región visible
            self._draw_pixel_grid()
            
            # Redibujar canvas (sin restaurar límites, ya están correctos)
            self.canvas.draw_idle()
        finally:
            self._updating_pixel_grid = False

    def toggle_pixel_grid(self, state):
        """Activa o desactiva la visualización de la grilla de píxeles"""
        try:
            self.show_pixel_grid = bool(state)
            self.save_grid_config()
            
            if self.grid_generated:
                self.display_grid()
        except Exception as e:
            QMessageBox.warning(
                self,
                "Error",
                f"Error al cambiar visibilidad de grid de píxeles: {str(e)}"
            )

    def change_drag_mode(self, index):
        """Cambia entre modo Fixed y Free para arrastrar la imagen"""
        self.drag_mode = "fixed" if index == 0 else "free"
        if self.image_on_grid is not None and self.drag_mode == "fixed":
            # Ajustar posición al chunk más cercano
            self.snap_to_optimal_chunks()

    def update_image_coordinates(self):
        """
        Actualiza las etiquetas de coordenadas de la imagen en el grid.
        Coordenadas en píxeles con precisión float para litografía de alta resolución.
        """
        if self.image_on_grid is None:
            self.coord_top_left_label.setText("🔺 Superior Izq: -")
            self.coord_top_right_label.setText("🔺 Superior Der: -")
            self.coord_bottom_left_label.setText("🔻 Inferior Izq: -")
            self.coord_bottom_right_label.setText("🔻 Inferior Der: -")
            return
        
        h, w = self.image_on_grid.shape[:2]
        x, y = self.image_position
        
        # Calcular coordenadas de las esquinas en píxeles del grid (precisión float)
        top_left = (x, y)
        top_right = (x + w - 1, y)
        bottom_left = (x, y + h - 1)
        bottom_right = (x + w - 1, y + h - 1)
        
        # Mostrar con precisión de 2 decimales para coordenadas sub-pixel
        self.coord_top_left_label.setText(f"🔺 Superior Izq: ({top_left[0]:.2f}, {top_left[1]:.2f})")
        self.coord_top_right_label.setText(f"🔺 Superior Der: ({top_right[0]:.2f}, {top_right[1]:.2f})")
        self.coord_bottom_left_label.setText(f"🔻 Inferior Izq: ({bottom_left[0]:.2f}, {bottom_left[1]:.2f})")
        self.coord_bottom_right_label.setText(f"🔻 Inferior Der: ({bottom_right[0]:.2f}, {bottom_right[1]:.2f})")

    def snap_to_optimal_chunks(self):
        """
        Ajusta la posición de la imagen para alinearla con los chunks del grid.
        Utiliza precisión float para permitir ajustes sub-pixel si es necesario.
        """
        if self.image_on_grid is None:
            return
        
        h, w = self.image_on_grid.shape[:2]
        chunk_size_px = float(self.grid_pixels_per_cell)  # float para precisión
        
        # Calcular cuántos chunks ocupa la imagen
        chunks_w = int(np.ceil(w / chunk_size_px))
        chunks_h = int(np.ceil(h / chunk_size_px))
        
        # Ajustar a la esquina del chunk más cercano (float para precisión)
        chunk_x = round(self.image_position[0] / chunk_size_px)
        chunk_y = round(self.image_position[1] / chunk_size_px)
        
        self.image_position = [float(chunk_x * chunk_size_px), float(chunk_y * chunk_size_px)]
        self.update_image_coordinates()
        self.display_grid()

    def apply_grid_effects(self, image):
        """Aplica los efectos de intensidad y desenfoque a la imagen para el grid"""
        if image is None:
            return None
        
        result = image.copy().astype(np.float64)
        
        # Aplicar desenfoque (sigma)
        if self.sigma > 0:
            result = gaussian_filter(result, sigma=self.sigma)
        
        # Aplicar intensidad (brightness) - mejorado para mayor visibilidad
        # Normalizar a 0-1 si es necesario
        if result.max() > 1.0:
            result = result / 255.0
        
        intensity_factor = self.brightness / 100.0
        result = result * intensity_factor
        
        # Volver a rango 0-255 para visualización
        result = (result * 255.0).clip(0, 255).astype(np.uint8)
        
        return result

    def overlay_image_on_grid(self):
        """
        Superpone la imagen cargada sobre el grid.
        
        NOTA: La calibración NO se aplica aquí porque:
        - Esta es solo una VISUALIZACIÓN en el grid
        - La calibración real se aplica a cada CHUNK durante la SEGMENTACIÓN
        - Cada chunk recibe su porción específica de la matriz de calibración
        """
        if self.image_on_grid is None:
            return
        
        # Aplicar transformaciones geométricas (rotación, espejos) y luego mostrar
        display_image = self.apply_image_transforms(self.image_on_grid)
        
        # NOTA: El downscaling NO se aplica aquí en la visualización del grid
        # Se aplica individualmente a cada CHUNK después de la segmentación
        # Esto mantiene la coherencia: la imagen en el grid muestra el tamaño original,
        # pero cada chunk proyectado tendrá el downscaling aplicado
        
        h, w = display_image.shape[:2]
        pixel_size = self.grid_cell_size / self.grid_pixels_per_cell
        
        # Convertir posición en píxeles a coordenadas del grid
        x_pos = self.image_position[0] * pixel_size
        y_pos = self.image_position[1] * pixel_size
        
        # Dimensiones de la imagen en unidades del grid
        img_width = w * pixel_size
        img_height = h * pixel_size
        
        # Mostrar la imagen en escala de grises o color según corresponda
        if len(display_image.shape) == 2:
            # Imagen en escala de grises
            self.ax.imshow(display_image, cmap='gray', 
                          extent=[x_pos, x_pos + img_width, 
                                 y_pos + img_height, y_pos],
                          alpha=0.7, interpolation='nearest')
        else:
            # Imagen a color
            self.ax.imshow(display_image, 
                          extent=[x_pos, x_pos + img_width, 
                                 y_pos + img_height, y_pos],
                          alpha=0.7, interpolation='nearest')

    def on_mouse_press(self, event):
        """Maneja el evento de presionar el mouse"""
        if not self.grid_view_active:
            return
        
        if not hasattr(self, 'ax') or self.ax is None:
            return
        
        if event.inaxes != self.ax:
            return
        
        # Botón central (2) = Pan de vista
        if event.button == 2:
            self.panning = True
            self.pan_start_pos = [event.xdata, event.ydata]
            self.canvas.setCursor(Qt.ClosedHandCursor)
            return
        
        # Botón izquierdo (1) = Mover imagen
        if event.button == 1 and self.image_on_grid is not None:
            # Verificar si el click está sobre la imagen
            pixel_size = self.grid_cell_size / self.grid_pixels_per_cell
            h, w = self.image_on_grid.shape[:2]
            
            x_pos = self.image_position[0] * pixel_size
            y_pos = self.image_position[1] * pixel_size
            img_width = w * pixel_size
            img_height = h * pixel_size
            
            if (x_pos <= event.xdata <= x_pos + img_width and 
                y_pos <= event.ydata <= y_pos + img_height):
                self.dragging_image = True
                self.drag_start_pos = [event.xdata, event.ydata]

    def on_mouse_release(self, event):
        """Maneja el evento de soltar el mouse"""
        # Terminar pan con botón central
        if event.button == 2 and self.panning:
            self.panning = False
            self.pan_start_pos = None
            self.canvas.setCursor(Qt.ArrowCursor)
            return
        
        # Terminar arrastre de imagen
        if self.dragging_image:
            self.dragging_image = False
            self.drag_start_pos = None
            
            if self.drag_mode == "fixed":
                self.snap_to_optimal_chunks()
            
            # Grabar posición si está grabando
            if self.recording:
                self.recorded_positions.append(tuple(self.image_position))
                self.recorded_positions_label.setText(f"Posiciones grabadas: {len(self.recorded_positions)}")

    def on_mouse_move(self, event):
        """
        Maneja el movimiento del mouse para pan de vista o arrastre de imagen.
        """
        if not hasattr(self, 'ax') or self.ax is None:
            return
        
        if event.inaxes != self.ax:
            return
        
        # Pan con botón central
        if self.panning and self.pan_start_pos is not None:
            dx = event.xdata - self.pan_start_pos[0]
            dy = event.ydata - self.pan_start_pos[1]
            
            # Obtener límites actuales
            xlim = self.ax.get_xlim()
            ylim = self.ax.get_ylim()
            
            # Aplicar desplazamiento
            self.ax.set_xlim(xlim[0] - dx, xlim[1] - dx)
            self.ax.set_ylim(ylim[0] - dy, ylim[1] - dy)
            
            # Redibujar
            self.canvas.draw_idle()
            return
        
        # Arrastre de imagen
        if not self.dragging_image:
            return
        
        if self.drag_start_pos is None:
            return
        
        pixel_size = float(self.grid_cell_size) / float(self.grid_pixels_per_cell)
        
        # Calcular el desplazamiento (float para precisión)
        dx = float(event.xdata - self.drag_start_pos[0])
        dy = float(event.ydata - self.drag_start_pos[1])
        
        # Convertir a píxeles del grid (mantener como float en modo libre)
        dx_px = dx / pixel_size
        dy_px = dy / pixel_size
        
        moved = False
        
        if self.drag_mode == "free":
            # Modo libre: movimiento continuo con precisión float (sub-pixel)
            if abs(dx_px) > 0.01 or abs(dy_px) > 0.01:  # Umbral mínimo para evitar ruido
                self.image_position[0] += dx_px
                self.image_position[1] += dy_px
                self.drag_start_pos = [event.xdata, event.ydata]
                moved = True
        else:
            # Modo fixed: movimiento por chunks completos (precisión int)
            chunk_size_px = float(self.grid_pixels_per_cell)
            if abs(dx_px) >= 1.0 or abs(dy_px) >= 1.0:
                chunks_x = int(dx_px // 1.0)
                chunks_y = int(dy_px // 1.0)
                self.image_position[0] += float(chunks_x)
                self.image_position[1] += float(chunks_y)
                self.drag_start_pos[0] += chunks_x * pixel_size
                self.drag_start_pos[1] += chunks_y * pixel_size
                moved = True
        
        if moved:
            self.update_image_coordinates()
            self.quick_redraw_image()

    def on_mouse_scroll(self, event):
        """
        Maneja el evento de scroll del mouse para hacer zoom.
        Scroll up = zoom in, Scroll down = zoom out
        """
        if not self.grid_view_active:
            return
        
        if not hasattr(self, 'ax') or self.ax is None:
            return
        
        if event.inaxes != self.ax:
            return
        
        # Factor de zoom
        zoom_factor = 1.2 if event.button == 'up' else 0.8
        
        # Obtener límites actuales
        xlim = self.ax.get_xlim()
        ylim = self.ax.get_ylim()
        
        # Calcular punto central del zoom (posición del mouse)
        xdata = event.xdata
        ydata = event.ydata
        
        # Calcular nuevos límites centrados en el cursor
        x_range = xlim[1] - xlim[0]
        y_range = ylim[1] - ylim[0]
        
        new_x_range = x_range / zoom_factor
        new_y_range = y_range / zoom_factor
        
        # Mantener el punto bajo el cursor fijo
        x_ratio = (xdata - xlim[0]) / x_range
        y_ratio = (ydata - ylim[0]) / y_range
        
        new_xlim = [
            xdata - new_x_range * x_ratio,
            xdata + new_x_range * (1 - x_ratio)
        ]
        new_ylim = [
            ydata - new_y_range * y_ratio,
            ydata + new_y_range * (1 - y_ratio)
        ]
        
        # Limitar el zoom para no alejarse demasiado
        grid_width = self.grid_width if hasattr(self, 'grid_width') else 100
        grid_height = self.grid_height if hasattr(self, 'grid_height') else 100
        
        # No permitir zoom out más allá de 1.5x el tamaño del grid
        if new_x_range > grid_width * 1.5 or new_y_range > grid_height * 1.5:
            return
        
        # No permitir zoom in más allá de 1 píxel
        if new_x_range < 1 or new_y_range < 1:
            return
        
        # Aplicar nuevos límites
        self.ax.set_xlim(new_xlim)
        self.ax.set_ylim(new_ylim)
        
        # Redibujar
        self.canvas.draw_idle()

    def quick_redraw_image(self):
        """Redibuja solo la imagen sin regenerar todo el grid para movimiento fluido"""
        if self.image_on_grid is None:
            return
        
        try:
            # Limpiar solo las imágenes superpuestas, manteniendo el grid
            for img in self.ax.images[:]:
                img.remove()
            
            # Superponer la imagen en la nueva posición
            self.overlay_image_on_grid()
            
            # Redibujar solo el canvas (más rápido que display_grid completo)
            self.canvas.draw_idle()
            
            # NO actualizar proyección automáticamente - solo mostrar segmentos individuales
            # if self.projector_active and self.projection_window is not None and self.grid_view_active:
            #     self.projection_window.set_image(self.image_on_grid)
        except:
            # Si falla, usar el método completo
            self.display_grid()

    def toggle_recording(self):
        """Inicia o detiene la grabación de posiciones"""
        if not self.recording:
            # Iniciar grabación
            self.recording = True
            self.recorded_positions = []
            self.record_button.setText("⏹️ Detener Grabación")
            self.record_button.setStyleSheet("background-color: #FF4444;")
            QMessageBox.information(
                self,
                "Grabación iniciada",
                "Mueve la imagen por el grid.\nCada posición se guardará automáticamente."
            )
        else:
            # Detener grabación
            self.recording = False
            self.record_button.setText("⏺️ Grabar Movimiento")
            self.record_button.setStyleSheet("")
            self.play_button.setEnabled(len(self.recorded_positions) > 0)
            QMessageBox.information(
                self,
                "Grabación finalizada",
                f"Se grabaron {len(self.recorded_positions)} posiciones.\n"
                f"Presiona '▶️ Reproducir' para ver el movimiento."
            )

    def play_movement(self):
        """Reproduce el movimiento grabado"""
        if len(self.recorded_positions) == 0:
            return
        
        if self.playback_active:
            # Detener reproducción
            self.playback_active = False
            self.playback_timer.stop()
            self.play_button.setText("▶️ Reproducir")
            self.record_button.setEnabled(True)
            self.drag_mode_combo.setEnabled(True)
        else:
            # Iniciar reproducción
            self.playback_active = True
            self.playback_index = 0
            self.play_button.setText("⏸️ Pausar")
            self.record_button.setEnabled(False)
            self.drag_mode_combo.setEnabled(False)
            # 100ms entre cada posición (10 fps)
            self.playback_timer.start(100)

    def playback_step(self):
        """Ejecuta un paso de la reproducción"""
        if self.playback_index >= len(self.recorded_positions):
            # Finalizar reproducción
            self.playback_active = False
            self.playback_timer.stop()
            self.play_button.setText("▶️ Reproducir")
            self.record_button.setEnabled(True)
            self.drag_mode_combo.setEnabled(True)
            return
        
        # Mover a la siguiente posición
        self.image_position = list(self.recorded_positions[self.playback_index])
        self.update_image_coordinates()
        self.quick_redraw_image()
        self.playback_index += 1

    def create_input_dialog(self, title, label, text=""):
        dialog = QInputDialog(self)
        dialog.setWindowTitle(title)
        dialog.setLabelText(label)
        dialog.setTextValue(text)
        dialog.setWindowFlags(dialog.windowFlags() & ~Qt.WindowContextHelpButtonHint)

        if self.dark_mode and sys.platform == "win32":
            try:
                hwnd = int(dialog.winId())
                DWMWA_USE_IMMERSIVE_DARK_MODE = 20
                value = ctypes.c_int(1)
                ctypes.windll.dwmapi.DwmSetWindowAttribute(
                    hwnd,
                    DWMWA_USE_IMMERSIVE_DARK_MODE,
                    ctypes.byref(value),
                    ctypes.sizeof(value),
                )
            except:
                pass

        return dialog

    def init_cache_system(self):
        if not os.path.exists(self.cache_dir):
            os.makedirs(self.cache_dir)

        if not os.path.exists(self.config_file):
            with open(self.config_file, "w") as f:
                json.dump({"folders": {}}, f)

    def load_grid_config(self):
        default_config = {
            "width": 10,
            "height": 10,
            "cell_size": 1,
            "pixels_per_cell": 100,
            "unit": "mm",
            "color": "#00FF00",
            "pixel_grid_color": "#FF00FF",
            "show_pixel_grid": False,
            "apply_effects_to_grid": False,
            "binary_mode_enabled": False,
            "binary_threshold": 50.0,
            "invert_projection": False
        }
        
        self.grid_generated = False
        
        if os.path.exists(self.grid_config_file):
            try:
                with open(self.grid_config_file, "r") as f:
                    config = json.load(f)
                    self.grid_width = config.get("width", default_config["width"])
                    self.grid_height = config.get("height", default_config["height"])
                    self.grid_cell_size = config.get("cell_size", default_config["cell_size"])
                    self.grid_pixels_per_cell = config.get("pixels_per_cell", default_config["pixels_per_cell"])
                    self.grid_unit = config.get("unit", default_config["unit"])
                    self.grid_color = config.get("color", default_config["color"])
                    self.grid_pixel_color = config.get("pixel_grid_color", default_config["pixel_grid_color"])
                    self.show_pixel_grid = config.get("show_pixel_grid", default_config["show_pixel_grid"])
                    self.apply_effects_to_grid = config.get("apply_effects_to_grid", default_config["apply_effects_to_grid"])
                    
                    # Cargar configuración binaria
                    self.binary_mode_enabled = config.get("binary_mode_enabled", default_config["binary_mode_enabled"])
                    self.binary_threshold = config.get("binary_threshold", default_config["binary_threshold"])
                    self.invert_projection = config.get("invert_projection", default_config["invert_projection"])
                    
                    self.grid_generated = True
            except:
                self.grid_width = default_config["width"]
                self.grid_height = default_config["height"]
                self.grid_cell_size = default_config["cell_size"]
                self.grid_pixels_per_cell = default_config["pixels_per_cell"]
                self.grid_unit = default_config["unit"]
                self.grid_color = default_config["color"]
                self.grid_pixel_color = default_config["pixel_grid_color"]
                self.show_pixel_grid = default_config["show_pixel_grid"]
                self.apply_effects_to_grid = default_config["apply_effects_to_grid"]
                
                # Cargar defaults binarios
                self.binary_mode_enabled = default_config["binary_mode_enabled"]
                self.binary_threshold = default_config["binary_threshold"]
                self.invert_projection = default_config["invert_projection"]
        else:
            self.grid_width = default_config["width"]
            self.grid_height = default_config["height"]
            self.grid_cell_size = default_config["cell_size"]
            self.grid_pixels_per_cell = default_config["pixels_per_cell"]
            self.grid_unit = default_config["unit"]
            self.grid_color = default_config["color"]
            self.grid_pixel_color = default_config["pixel_grid_color"]
            self.show_pixel_grid = default_config["show_pixel_grid"]
            self.apply_effects_to_grid = default_config["apply_effects_to_grid"]
            
            # Cargar defaults binarios
            self.binary_mode_enabled = default_config["binary_mode_enabled"]
            self.binary_threshold = default_config["binary_threshold"]
            self.invert_projection = default_config["invert_projection"]

    def save_grid_config(self):
        config = {
            "width": self.grid_width,
            "height": self.grid_height,
            "cell_size": self.grid_cell_size,
            "pixels_per_cell": self.grid_pixels_per_cell,
            "unit": self.grid_unit,
            "color": self.grid_color,
            "pixel_grid_color": self.grid_pixel_color,
            "show_pixel_grid": self.show_pixel_grid,
            "apply_effects_to_grid": self.apply_effects_to_grid,
            "binary_mode_enabled": self.binary_mode_enabled,
            "binary_threshold": self.binary_threshold,
            "invert_projection": self.invert_projection
        }
        
        try:
            with open(self.grid_config_file, "w") as f:
                json.dump(config, f, indent=2)
        except Exception as e:
            print(f"Error al guardar configuración del grid: {e}")

    def dragEnterEvent(self, event: QDragEnterEvent):
        if event.mimeData().hasUrls():
            event.acceptProposedAction()

    def dropEvent(self, event: QDropEvent):
        urls = event.mimeData().urls()
        if urls:
            file_path = urls[0].toLocalFile()
            if file_path.lower().endswith((".png", ".jpg", ".jpeg", ".bmp", ".tiff")):
                if self.pattern is not None:
                    reply = QMessageBox.question(
                        self,
                        "Reemplazar imagen",
                        "¿Desea reemplazar la imagen actual?",
                        QMessageBox.Yes | QMessageBox.No,
                        QMessageBox.No,
                    )
                    if reply == QMessageBox.No:
                        return

                image = cv2.imread(file_path, cv2.IMREAD_GRAYSCALE)
                self.pattern = image / 255.0
                self.simulate_optics()
                self._refresh_invert_button_state()

    def load_pattern(self):
        file_path, _ = QFileDialog.getOpenFileName(
            self, "Seleccionar patrón", "", "Imágenes (*.png *.jpg *.bmp *.tiff)"
        )
        if file_path:
            if self.pattern is not None:
                reply = QMessageBox.question(
                    self,
                    "Reemplazar imagen",
                    "¿Desea reemplazar la imagen actual?",
                    QMessageBox.Yes | QMessageBox.No,
                    QMessageBox.No,
                )
                if reply == QMessageBox.No:
                    return

            image = cv2.imread(file_path, cv2.IMREAD_GRAYSCALE)
            self.pattern = image / 255.0
            
            # Asignar ID único a la imagen para cache determinista
            import time
            self._pattern_load_id = f"{file_path}_{time.time()}"
            
            # Limpiar cache de segmentación cuando se carga nueva imagen
            self._last_segmentation_pattern_hash = None
            self._last_segmentation_bounds = None
            self._last_segmentation_grid_config = None
            self._last_image_position = None
            
            self.simulate_optics()
            self.projector_button.setVisible(True)
            self.update_projector_button()
            self._refresh_invert_button_state()

    def _get_projection_image(self):
        """Obtiene la imagen a proyectar, aplicando transformaciones y downscaling."""
        image = None
        
        if self.grid_view_active and self.image_on_grid is not None:
            image = self.image_on_grid
        elif hasattr(self, "last_intensity") and self.last_intensity is not None:
            image = self.last_intensity
        
        # Aplicar transformaciones geométricas (rotación, espejos)
        if image is not None:
            image = self.apply_image_transforms(image)
        
        # NOTA: El downscaling NO se aplica aquí a la imagen completa
        # Se aplica individualmente a cada CHUNK en _apply_effects_to_segment()
        # Esto mantiene la segmentación alineada con el grid
        
        return image
    
    def _get_final_projection_image(self):
        """
        Obtiene la imagen final proyectada con TODOS los efectos aplicados:
        - Sigma (gaussian filter)
        - Downscaling
        - Brillo
        - Matriz de atenuación (si está en grid)
        - Conversión binaria (si está activa)
        
        Esta es la imagen REAL que se proyecta y debe usarse para segmentación.
        """
        import numpy as np
        import cv2
        
        # Obtener imagen base
        base_image = self._get_projection_image()
        
        if base_image is None:
            return None
        
        # Crear copia para no modificar la original
        final_image = base_image.copy()
        
        # Aplicar brillo (normalizado 0-100 -> escala 0-1 para multiplicación)
        if self.brightness != 100:
            brightness_factor = self.brightness / 100.0
            final_image = np.clip(final_image * brightness_factor, 0, 255).astype(np.uint8)
        
        # Aplicar conversión binaria si está activa
        if self.binary_mode_enabled:
            # Convertir a escala de grises si es necesario
            if len(final_image.shape) == 3:
                gray_image = cv2.cvtColor(final_image, cv2.COLOR_BGR2GRAY)
            else:
                gray_image = final_image
            
            # Aplicar umbral binario
            final_image = np.where(gray_image >= self.binary_threshold, 255, 0).astype(np.uint8)
        
        # Aplicar inversión si está activa
        if self.invert_projection:
            final_image = 255 - final_image
        
        return final_image

    def toggle_projector(self):
        self.has_second_monitor = self.check_second_monitor()
        if not self.has_second_monitor and not self.projector_active:
            QMessageBox.warning(
                self,
                "Monitor no detectado",
                "No se detectó un segundo monitor conectado.\n\n"
                "Por favor, conecte un segundo monitor para usar la función de proyección.",
            )
            self.update_projector_button()
            return  # no proyectar si no hay segundo monitor

        # si el monitor se desconectó mientras estaba proyectando, cerrar proyección
        if not self.has_second_monitor and self.projector_active:
            if self.projection_window is not None:
                self.projection_window.close()
                self.projection_window = None
            self.brightness_slider.setVisible(False)
            self.brightness_label.setVisible(False)
            self.projector_active = False
            self.update_projector_button()
            QMessageBox.warning(
                self,
                "Monitor desconectado",
                "Se perdió la conexión con el segundo monitor.\n\n"
                "La proyección se ha detenido.",
            )
            return

        self.projector_active = not self.projector_active

        if self.projector_active:
            # Verificar que hay imagen disponible (aunque no la proyectaremos completa)
            image_to_project = self._get_projection_image()
            if image_to_project is not None:
                # ═══════════════════════════════════════════════════════════════════
                # PROYECTOR SIEMPRE INICIA EN NEGRO
                # ═══════════════════════════════════════════════════════════════════
                # La imagen solo se proyecta cuando:
                # - Se presiona "Proyectar Imagen" explícitamente
                # - Se inicia Exposición
                # - Se inicia Frecuencia
                # - Se inicia Secuencia de Slices
                
                self.projection_window = ProjectionWindow(None, self)  # None = pantalla negra
                self.projection_window.set_inversion(self.invert_projection)
                self.projection_window.set_binary_threshold(self.binary_threshold)
                self.projection_window.set_binary_mode(self.binary_mode_enabled)
                self.projection_window.show_on_secondary_monitor()
                
                # SIEMPRE iniciar con pantalla negra
                self.projection_window.show_black_screen()
                self.log_to_console(
                    "✓ Proyector activado - Pantalla en NEGRO\n"
                    "  La imagen se proyectará al iniciar Exposición, Frecuencia o Secuencia", 
                    "INFO"
                )

                self.brightness_slider.setVisible(True)
                self.brightness_label.setVisible(True)
                # self.binary_section.setVisible(True) - Always visible in sidebar
                self.project_image_button.setVisible(True)  # Botón para proyectar imagen manualmente
                self.exposure_button.setVisible(True)
                self.frequency_button.setVisible(True)
                # NO llamar update_brightness() para no proyectar la imagen completa
                # self.update_brightness()
                
                # Mostrar campos de resolución proyectada ahora que hay proyección activa
                self._update_projection_resolution_fields(True)
            else:
                QMessageBox.warning(
                    self, "Advertencia", "No hay imagen para proyectar.\nCargue una imagen en Vista Normal o Vista Grid."
                )
                self.projector_active = False
        else:
            if self.exposure_active:
                self.force_stop_exposure()

            if self.frequency_mode:
                self.force_stop_frequency()
            
            # Detener secuencia de slices si está activa
            if hasattr(self, 'sequence_running') and self.sequence_running:
                self.stop_sequence()
                self.log_to_console("⏹️ Secuencia detenida - Proyector desactivado", "INFO")

            if self.projection_window is not None:
                self.projection_window.close()
                self.projection_window = None
            self.brightness_slider.setVisible(False)
            self.brightness_label.setVisible(False)
            # self.binary_section.setVisible(False) - Always visible in sidebar
            self.project_image_button.setVisible(False)
            self.exposure_button.setVisible(False)
            self.stop_exposure_button.setVisible(False)
            self.frequency_button.setVisible(False)
            self.stop_frequency_button.setVisible(False)
            
            # Ocultar campos de resolución proyectada al desactivar proyección
            self._update_projection_resolution_fields(False)

        self.update_projector_button()

    def on_projection_closed(self):
        """Se llama cuando se cierra la ventana de proyección."""
        if self.exposure_active:
            self.force_stop_exposure()

        if self.frequency_mode:
            self.force_stop_frequency()

        self.projector_active = False
        self.projection_window = None
        self.brightness_slider.setVisible(False)
        self.brightness_label.setVisible(False)
        # self.binary_section.setVisible(False) - Always visible in sidebar
        self.exposure_button.setVisible(False)
        self.stop_exposure_button.setVisible(False)
        self.frequency_button.setVisible(False)
        self.stop_frequency_button.setVisible(False)
        
        # Ocultar campos de resolución de proyección al cerrar
        self._update_projection_resolution_fields(False)
        
        self.update_projector_button()

    def update_projector_button(self):
        # actualizar detección de segundo monitor
        self.has_second_monitor = self.check_second_monitor()

        if not self.has_second_monitor:
            led = "🟠"
            status = "DESCONECTADO"
            self.projector_button.setStyleSheet(
                """
                QPushButton {
                    background-color: #FF8C00;
                    color: #FFFFFF;
                    font-weight: bold;
                }
                QPushButton:hover {
                    background-color: #FFA500;
                }
            """
            )
        elif self.projector_active:
            led = "🟢"
            status = "ACTIVO"
            self.projector_button.setStyleSheet("")
        else:
            led = "🔴"
            status = "INACTIVO"
            self.projector_button.setStyleSheet("")
        self.projector_button.setText(f"{led} Proyectar ({status})")

    def save_image(self):
        if not hasattr(self, "last_intensity"):
            QMessageBox.warning(
                self, "Advertencia", "No hay imagen procesada para guardar"
            )
            return

        folders = self.get_folders_list()
        folder, ok = QInputDialog.getItem(
            self,
            "Seleccionar carpeta",
            "Carpeta destino:",
            folders + ["[Nueva carpeta]"],
            0,
            False,
        )

        if not ok:
            return

        if folder == "[Nueva carpeta]":
            dialog = self.create_input_dialog("Nueva carpeta", "Nombre de la carpeta:")
            if dialog.exec_() == QInputDialog.Accepted:
                folder = dialog.textValue()
                if not folder:
                    return
                self.create_folder(folder)
            else:
                return

        dialog = self.create_input_dialog("Guardar imagen", "Nombre del archivo:")

        if dialog.exec_() != QInputDialog.Accepted:
            return

        filename = dialog.textValue()

        if not filename or filename.strip() == "":
            from datetime import datetime

            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"imagen_{timestamp}"

        fmt = self.format_combo.currentText().lower()
        filepath = os.path.join(self.cache_dir, folder, f"{filename}.{fmt}")

        os.makedirs(os.path.dirname(filepath), exist_ok=True)

        img_to_save = (self.last_intensity * 255 / self.last_intensity.max()).astype(
            np.uint8
        )
        cv2.imwrite(filepath, img_to_save)

        self.update_file_tree_preserve_state()

        QMessageBox.information(self, "Éxito", f"Imagen guardada en:\n{filepath}")

    def create_folder(self, folder_name, parent=""):
        folder_path = os.path.join(self.cache_dir, parent, folder_name)
        os.makedirs(folder_path, exist_ok=True)

    def get_folders_list(self):
        folders = [""]
        for root, dirs, files in os.walk(self.cache_dir):
            for d in dirs:
                rel_path = os.path.relpath(os.path.join(root, d), self.cache_dir)
                folders.append(rel_path)
        return folders

    def update_file_tree(self):
        self.file_tree.clear()
        self.populate_tree(self.cache_dir, self.file_tree.invisibleRootItem())

    def update_file_tree_preserve_state(self):
        expanded_items = []
        iterator = QTreeWidgetItemIterator(self.file_tree)
        while iterator.value():
            item = iterator.value()
            if item.isExpanded():
                expanded_items.append(item.text(0))
            iterator += 1

        self.update_file_tree()

        iterator = QTreeWidgetItemIterator(self.file_tree)
        while iterator.value():
            item = iterator.value()
            if item.text(0) in expanded_items:
                item.setExpanded(True)
            iterator += 1

    def populate_tree(self, path, parent_item):
        try:
            items = sorted(os.listdir(path))
        except PermissionError:
            return

        for item in items:
            if item == "file_structure.json":
                continue

            item_path = os.path.join(path, item)
            tree_item = QTreeWidgetItem(parent_item, [item])
            tree_item.setData(0, Qt.UserRole, item_path)

            if os.path.isdir(item_path):
                tree_item.setIcon(0, self.style().standardIcon(self.style().SP_DirIcon))
                self.populate_tree(item_path, tree_item)
            else:
                if item.lower().endswith((".png", ".jpg", ".jpeg", ".bmp", ".tiff")):
                    thumbnail = self.create_thumbnail(item_path, size=56)
                    if thumbnail:
                        tree_item.setIcon(0, QIcon(thumbnail))
                else:
                    tree_item.setIcon(
                        0, self.style().standardIcon(self.style().SP_FileIcon)
                    )

    def create_thumbnail(self, image_path, size=56):
        try:
            img = cv2.imread(image_path, cv2.IMREAD_GRAYSCALE)
            if img is None:
                return None

            h, w = img.shape
            if h > w:
                new_h = size
                new_w = int(w * size / h)
            else:
                new_w = size
                new_h = int(h * size / w)

            img_resized = cv2.resize(img, (new_w, new_h), interpolation=cv2.INTER_AREA)

            height, width = img_resized.shape
            bytes_per_line = width
            q_image = QImage(
                img_resized.data,
                width,
                height,
                bytes_per_line,
                QImage.Format_Grayscale8,
            )
            pixmap = QPixmap.fromImage(q_image)

            return pixmap
        except Exception as e:
            print(f"Error creando miniatura: {e}")
            return None

    def show_context_menu(self, position):
        menu = QMenu()
        create_folder = menu.addAction("📁 Nueva carpeta")
        rename_item = menu.addAction("✏️ Renombrar")
        delete_item = menu.addAction("🗑️ Eliminar")

        action = menu.exec_(self.file_tree.viewport().mapToGlobal(position))

        item = self.file_tree.currentItem()

        if action == create_folder:
            dialog = self.create_input_dialog("Nueva carpeta", "Nombre:")
            if dialog.exec_() == QInputDialog.Accepted:
                folder_name = dialog.textValue()
                if folder_name:
                    parent_path = self.cache_dir
                    if item:
                        item_path = item.data(0, Qt.UserRole)
                        if os.path.isdir(item_path):
                            parent_path = item_path

                    new_folder = os.path.join(parent_path, folder_name)
                    os.makedirs(new_folder, exist_ok=True)
                    self.update_file_tree_preserve_state()

        elif action == rename_item and item:
            old_path = item.data(0, Qt.UserRole)
            old_name = item.text(0)

            dialog = self.create_input_dialog(
                "Renombrar", f"Nuevo nombre para '{old_name}':", text=old_name
            )

            if dialog.exec_() == QInputDialog.Accepted:
                new_name = dialog.textValue()
                if new_name and new_name != old_name:
                    parent_dir = os.path.dirname(old_path)
                    new_path = os.path.join(parent_dir, new_name)

                    try:
                        os.rename(old_path, new_path)
                        item.setText(0, new_name)
                        item.setData(0, Qt.UserRole, new_path)
                        QMessageBox.information(
                            self, "Éxito", f"Renombrado a: {new_name}"
                        )
                    except Exception as e:
                        QMessageBox.warning(
                            self, "Error", f"No se pudo renombrar: {str(e)}"
                        )

        elif action == delete_item and item:
            reply = QMessageBox.question(
                self,
                "Confirmar eliminación",
                f"¿Eliminar {item.text(0)}?",
                QMessageBox.Yes | QMessageBox.No,
            )
            if reply == QMessageBox.Yes:
                item_path = item.data(0, Qt.UserRole)
                try:
                    if os.path.isfile(item_path):
                        os.remove(item_path)
                    elif os.path.isdir(item_path):
                        import shutil

                        shutil.rmtree(item_path)

                    parent = item.parent()
                    if parent:
                        parent.removeChild(item)
                    else:
                        index = self.file_tree.indexOfTopLevelItem(item)
                        self.file_tree.takeTopLevelItem(index)

                    QMessageBox.information(
                        self, "Éxito", "Elemento eliminado correctamente"
                    )
                except Exception as e:
                    QMessageBox.warning(self, "Error", f"No se pudo eliminar: {str(e)}")

    def load_from_tree(self, item, column):
        item_path = item.data(0, Qt.UserRole)
        if os.path.isfile(item_path) and item_path.lower().endswith(
            (".png", ".jpg", ".bmp", ".tiff")
        ):
            image = cv2.imread(item_path, cv2.IMREAD_GRAYSCALE)
            self.pattern = image / 255.0
            self.simulate_optics()
            self.projector_button.setVisible(True)
            self.update_projector_button()
            self._refresh_invert_button_state()

    def update_sigma(self):
        self.sigma = self.sigma_slider.value()
        self.sigma_label.setText(f"Sigma (Desenfoque): {self.sigma:.1f}")
        if self.pattern is not None:
            if not self.grid_view_active:
                self.simulate_optics()
            elif self.apply_effects_to_grid and self.grid_generated:
              
                self.image_on_grid = self.apply_grid_effects(self.pattern.copy())
                self.quick_redraw_image()

    def update_brightness(self):
        self.brightness = self.brightness_slider.value()
        self.brightness_label.setText(f"Brillo Proyección: {self.brightness}%")
        if self.projector_active and self.projection_window is not None:
            self.projection_window.set_brightness(self.brightness)
        
        if self.apply_effects_to_grid and self.grid_view_active and self.grid_generated and self.pattern is not None:
            self.image_on_grid = self.apply_grid_effects(self.pattern.copy())
            self.quick_redraw_image()

    def toggle_binary_mode(self, state):
        """Activa o desactiva el modo de binarización."""
        self.binary_mode_enabled = bool(state)
        if self.projector_active and self.projection_window is not None:
            self.projection_window.set_binary_mode(self.binary_mode_enabled)
            
            # Si se desactiva el modo binario y no hay secuencia activa, mostrar imagen
            if not self.binary_mode_enabled and not self.sequence_running and not self.exposure_active and not self.frequency_mode:
                image = self._get_projection_image()
                if image is not None:
                    self.projection_window.set_image(image)
                    
        self.binary_status_label.setText(f"Estado: {'✓ Activo' if self.binary_mode_enabled else '✗ Inactivo'}")

    def update_binary_threshold_from_slider(self):
        """Actualiza el umbral de binarización desde el slider."""
        self.binary_threshold = float(self.binary_threshold_slider.value())
        self.binary_threshold_input.setText(f"{self.binary_threshold:.1f}")
        if self.projector_active and self.projection_window is not None:
            self.projection_window.set_binary_threshold(self.binary_threshold)

    def update_binary_threshold_from_input(self):
        """Actualiza el umbral de binarización desde el campo de texto."""
        try:
            value = float(self.binary_threshold_input.text())
            if 0 <= value <= 100:
                self.binary_threshold = value
                self.binary_threshold_slider.setValue(int(round(value)))
                if self.projector_active and self.projection_window is not None:
                    self.projection_window.set_binary_threshold(self.binary_threshold)
            else:
                self.binary_threshold_input.setText(f"{self.binary_threshold:.1f}")
        except ValueError:
            self.binary_threshold_input.setText(f"{self.binary_threshold:.1f}")

    def toggle_intensity_inversion(self, checked: bool):
        self.invert_projection = bool(checked)
        self.save_grid_config()
        self._update_invert_button_text()
        
        # Actualizar preview
        if self.pattern is not None:
            self.simulate_optics()

        if self.projector_active and self.projection_window is not None:
            self.projection_window.set_inversion(self.invert_projection)
            # NO actualizar imagen completa - solo afecta a segmentos proyectados
            # current_image = self._get_projection_image()
            # if current_image is not None:
            #     self.projection_window.update_image(current_image)
            self.projection_window.set_inversion(self.invert_projection)
            # NO actualizar imagen completa - solo afecta a segmentos proyectados
            # current_image = self._get_projection_image()
            # if current_image is not None:
            #     self.projection_window.update_image(current_image)

    def _update_invert_button_text(self):
        if not hasattr(self, "invert_button"):
            return
        if self.invert_projection:
            self.invert_button.setText("⬛⬜ Intensidad Invertida")
        else:
            self.invert_button.setText("⬜⬛ Invertir Intensidad")

    def _refresh_invert_button_state(self):
        # Actualizar checkbox si existe
        if hasattr(self, "invert_check"):
            self.invert_check.blockSignals(True)
            self.invert_check.setChecked(self.invert_projection)
            self.invert_check.blockSignals(False)

        if not hasattr(self, "invert_button"):
            return
        has_source = self.pattern is not None or (
            hasattr(self, "last_intensity") and self.last_intensity is not None
        )
        self.invert_button.setEnabled(has_source)
        self.invert_button.blockSignals(True)
        self.invert_button.setChecked(self.invert_projection)
        self.invert_button.blockSignals(False)
        self._update_invert_button_text()

    # ═══════════════════════════════════════════════════════════════════════════
    # FUNCIONES DE CONTROL DE PROYECCIÓN Y SECUENCIAS
    # ═══════════════════════════════════════════════════════════════════════════

    def update_downscale_factor(self, value):
        """
        Actualiza el factor de downscaling y muestra la resolución resultante.
        
        IMPORTANTE: El downscaling se aplica a CADA CHUNK INDIVIDUAL después de
        la segmentación, NO a la imagen completa. Esto mantiene la coherencia con
        el grid - la imagen sigue ocupando las mismas celdas, pero cada celda
        proyectada tendrá menor/mayor resolución.
        """
        self.downscale_factor = float(value)
        
        # Calcular y mostrar resolución resultante POR CHUNK
        if self.pattern is not None and hasattr(self, 'grid_pixels_per_cell'):
            # Tamaño de una celda del grid (antes del downscaling)
            cell_size = int(self.grid_pixels_per_cell)
            
            # Tamaño después del downscaling (aplicado a cada chunk)
            chunk_width = max(1, int(cell_size / self.downscale_factor))
            chunk_height = max(1, int(cell_size / self.downscale_factor))
            
            if self.downscale_factor > 1.0:
                direction = f"↓ Reducido {(1.0 - 1.0/self.downscale_factor)*100:.0f}%"
            elif self.downscale_factor < 1.0:
                direction = f"↑ Aumentado {(1.0/self.downscale_factor - 1.0)*100:.0f}%"
            else:
                direction = "= Sin cambio"
            
            self.downscale_info_label.setText(
                f"Resolución por chunk: {chunk_width}×{chunk_height} px {direction} "
                f"(Celda: {cell_size}×{cell_size} px)"
            )
        else:
            self.downscale_info_label.setText("Resolución: Cargue una imagen y genere el grid primero")
        
        # Si hay proyección activa, actualizar
        if self.projector_active and self.projection_window is not None:
            self._update_projection_with_downscale()

    def _update_projection_with_downscale(self):
        """Aplica el downscaling a la imagen proyectada."""
        if self.pattern is None:
            return
        
        # NO actualizar la proyección completa con downscaling
        # El downscaling se aplica individualmente a cada segmento en _apply_effects_to_segment
        # current_image = self._get_projection_image()
        # if current_image is not None and self.downscale_factor != 1.0:
        #     # Aplicar downscaling
        #     original_height, original_width = current_image.shape[:2]
        #     new_width = int(original_width * self.downscale_factor)
        #     new_height = int(original_height * self.downscale_factor)
        #     
        #     if new_width > 0 and new_height > 0:
        #         import cv2
        #         downscaled_image = cv2.resize(
        #             current_image, 
        #             (new_width, new_height),
        #             interpolation=cv2.INTER_AREA if self.downscale_factor < 1.0 else cv2.INTER_LINEAR
        #         )
        #         self.projection_window.update_image(downscaled_image)
        #     else:
        #         self.projection_window.update_image(current_image)

    def start_sequence(self):
        """Inicia la secuencia de proyección con control de movimiento y segmentos de imagen."""
        # Verificar conflictos con otros modos
        if self.exposure_active:
            QMessageBox.warning(self, "Conflicto", "No se puede iniciar secuencia mientras la exposición está activa.")
            return
        if self.frequency_mode:
            QMessageBox.warning(self, "Conflicto", "No se puede iniciar secuencia mientras el modo frecuencia está activo.")
            return

        # Verificar que haya segmentos de imagen
        if not hasattr(self, 'image_segments') or not self.image_segments:
            QMessageBox.warning(
                self,
                "Sin segmentos de imagen",
                "Debe aplicar segmentación de imagen antes de iniciar una secuencia.\n\n"
                "Pasos:\n"
                "1. Cargue una imagen\n"
                "2. Vaya a '✂️ SEGMENTACIÓN DE IMAGEN'\n"
                "3. Configure el modo y número de segmentos\n"
                "4. Presione 'Aplicar Segmentación'"
            )
            return
        
        # Verificar que el proyector esté activo
        if not self.projector_active:
            reply = QMessageBox.question(
                self,
                "Proyector inactivo",
                "El proyector no está activo. ¿Desea activarlo ahora?",
                QMessageBox.Yes | QMessageBox.No
            )
            if reply == QMessageBox.Yes:
                self.toggle_projector()
                if not self.projector_active:
                    return  # No se pudo activar
            else:
                return
        
        # Calcular total de segmentos de imagen
        self.total_segments = len(self.image_segments)
        self.current_segment_index = 0
        self.sequence_running = True
        self.sequence_paused = False
        
        # Actualizar UI
        self.sequence_status_label.setText("Estado: ▶️ En ejecución")
        self.sequence_start_button.setEnabled(False)
        self.sequence_pause_button.setEnabled(True)
        self.sequence_stop_button.setEnabled(True)
        self.segment_progress_bar.setMaximum(self.total_segments)
        
        # ═══════════════════════════════════════════════════════════════════
        # LOG INICIO: MOSTRAR ORDEN SECUENCIAL DE CHUNKS
        # ═══════════════════════════════════════════════════════════════════
        self.log_to_console(
            f"▶️ INICIANDO SECUENCIA DE PROYECCIÓN\n"
            f"  • Total de chunks: {self.total_segments}\n"
            f"  • Orden: Secuencial estricto (fila por fila)\n"
            f"  • Tiempo por chunk: {self.exposure_time_spin.value()}s exposición + {self.movement_time_spin.value()}s movimiento",
            "SUCCESS"
        )
        
        # Mostrar los primeros 5 chunks para verificación
        if self.total_segments > 0:
            preview_count = min(5, self.total_segments)
            preview_chunks = []
            for i in range(preview_count):
                seg = self.image_segments[i]
                preview_chunks.append(f"[{seg['row']},{seg['col']}]")
            preview_str = " → ".join(preview_chunks)
            if self.total_segments > 5:
                preview_str += " → ..."
            self.log_to_console(f"  • Orden chunks: {preview_str}", "INFO")
        
        # Iniciar timer para procesar segmentos
        if not hasattr(self, 'sequence_timer') or self.sequence_timer is None:
            self.sequence_timer = QTimer()
            self.sequence_timer.timeout.connect(self._process_next_segment)
        
        # Iniciar primer segmento
        self._process_next_segment()

    def pause_sequence(self):
        """Pausa/reanuda la secuencia de proyección."""
        if not self.sequence_running:
            return
        
        self.sequence_paused = not self.sequence_paused
        
        if self.sequence_paused:
            self.sequence_status_label.setText("Estado: ⏸️ Pausado")
            self.sequence_pause_button.setText("▶️ Reanudar")
            if self.sequence_timer:
                self.sequence_timer.stop()
        else:
            self.sequence_status_label.setText("Estado: ▶️ En ejecución")
            self.sequence_pause_button.setText("⏸️ Pausar")
            # Continuar con siguiente segmento
            self._process_next_segment()

    def stop_sequence(self):
        """Detiene la secuencia de proyección."""
        self.sequence_running = False
        self.sequence_paused = False
        
        if self.sequence_timer:
            self.sequence_timer.stop()
        
        # Limpiar resaltado del chunk en proyección
        self.current_projecting_segment = None
        
        # Volver a pantalla negra al detener
        if self.projector_active and self.projection_window is not None:
            self.projection_window.show_black_screen()
            self.log_to_console("Secuencia detenida - Pantalla en negro", "INFO")
        
        # Actualizar grid para quitar resaltado PRESERVANDO el zoom
        if self.grid_view_active and hasattr(self, 'grid_generated') and self.grid_generated:
            if hasattr(self, 'ax') and self.ax is not None:
                # Guardar límites actuales del zoom
                current_xlim = self.ax.get_xlim()
                current_ylim = self.ax.get_ylim()
                
                # Redibujar el grid completo
                self.display_grid()
                
                # Restaurar los límites del zoom
                self.ax.set_xlim(current_xlim)
                self.ax.set_ylim(current_ylim)
                self.canvas.draw_idle()
            else:
                self.display_grid()
        
        # Resetear UI
        self.sequence_status_label.setText("Estado: ⏹️ Detenido")
        self.sequence_start_button.setEnabled(True)
        self.sequence_pause_button.setEnabled(False)
        self.sequence_pause_button.setText("⏸️ Pausar")
        self.sequence_stop_button.setEnabled(False)
        self.current_segment_label.setText(f"Segmento: {self.current_segment_index}/{self.total_segments}")
        self.segment_progress_bar.setValue(int(self.current_segment_index))

    def _process_next_segment(self):
        """Procesa el siguiente segmento de la secuencia."""
        if not self.sequence_running or self.sequence_paused:
            return
        
        # Verificar si hay segmentos de imagen disponibles
        if not hasattr(self, 'image_segments') or not self.image_segments:
            QMessageBox.warning(
                self,
                "Sin segmentos",
                "Debe aplicar segmentación de imagen antes de iniciar la secuencia.\n\n"
                "Vaya a la sección '✂️ SEGMENTACIÓN DE IMAGEN' y aplique segmentación."
            )
            self.stop_sequence()
            return
        
        if self.current_segment_index >= len(self.image_segments):
            # Secuencia completada
            self.sequence_status_label.setText("Estado: ✅ Completado")
            
            # Volver a pantalla negra
            if self.projector_active and self.projection_window is not None:
                self.projection_window.show_black_screen()
                self.log_to_console("Proyección finalizada - Pantalla en negro", "SUCCESS")
            
            self.stop_sequence()
            QMessageBox.information(
                self,
                "Secuencia Completada",
                f"Se han proyectado todos los {len(self.image_segments)} segmentos de imagen."
            )
            return
        
        # Obtener segmento actual
        current_segment = self.image_segments[self.current_segment_index]
        row = current_segment['row']
        col = current_segment['col']
        segment_image = current_segment['image']
        effects_already_applied = current_segment.get('effects_applied', False)
        
        # Actualizar UI
        self.current_segment_index += 1
        self.current_segment_label.setText(f"Segmento: {self.current_segment_index}/{len(self.image_segments)}")
        self.segment_progress_bar.setValue(int(self.current_segment_index))
        
        # Log del segmento con información detallada
        self.log_to_console(
            f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
            f"📦 CHUNK {self.current_segment_index}/{len(self.image_segments)}\n"
            f"  • ID: S{current_segment['id']}\n"
            f"  • Posición grid: Fila {row}, Columna {col}\n"
            f"  • Tamaño: {current_segment['width']}×{current_segment['height']} px\n"
            f"  • Orden: Secuencial estricto",
            "SEGMENTATION"
        )
        
        # ═══════════════════════════════════════════════════════════════════════════
        # SECUENCIA TEMPORAL PARA LITOGRAFÍA:
        # 1. Mostrar segmento (EXPOSICIÓN) → Tiempo de exposición
        # 2. Pantalla negra + Movimiento → Tiempo de movimiento
        # 3. Siguiente segmento
        # ═══════════════════════════════════════════════════════════════════════════
        
        # FASE 1: EXPOSICIÓN - Mostrar segmento durante tiempo de exposición
        if self.auto_shutter_checkbox.isChecked():
            exposure_time_s = self.exposure_time_spin.value()
            self.log_to_console(
                f"Exponiendo segmento {self.current_segment_index}/{len(self.image_segments)} durante {exposure_time_s}s", 
                "INFO"
            )
            
            # PROYECTAR SEGMENTO
            if self.projector_active and self.projection_window is not None:
                # Aplicar TODOS los efectos al segmento antes de proyectar
                processed_segment = self._apply_effects_to_segment(segment_image, skip_binary_effects=effects_already_applied)
                
                # DEBUG: Log detallado de coordenadas del chunk
                self.log_to_console(
                    f"🔍 DEBUG Chunk {current_segment['id']} [fila={row}, col={col}]:\n"
                    f"  • Coordenadas en imagen: ({current_segment['x_start']}, {current_segment['y_start']}) → "
                    f"({current_segment['x_end']}, {current_segment['y_end']})\n"
                    f"  • Tamaño chunk: {current_segment['width']}×{current_segment['height']} px\n"
                    f"  • Tamaño procesado: {processed_segment.shape[1]}×{processed_segment.shape[0]} px\n"
                    f"  • Valores: min={processed_segment.min():.2f}, max={processed_segment.max():.2f}, mean={processed_segment.mean():.2f}",
                    "INFO"
                )
                
                # Proyectar el segmento procesado en la pantalla secundaria
                # Durante una secuencia, SIEMPRE se proyecta (no depende de show_projection_image)
                self.projection_window.update_segment(processed_segment)
                self.log_to_console(
                    f"✓ Segmento {current_segment['id']} PROYECTADO: {processed_segment.shape[1]}x{processed_segment.shape[0]} px", 
                    "SUCCESS"
                )
                
                # Actualizar monitor de calibración con info de última proyección
                if hasattr(self, 'last_projection_size_label'):
                    self.last_projection_size_label.setText(
                        f"• Tamaño: {processed_segment.shape[1]}×{processed_segment.shape[0]} px"
                    )
                if hasattr(self, 'last_projection_values_label'):
                    self.last_projection_values_label.setText(
                        f"• Valores: min={processed_segment.min():.2f}, max={processed_segment.max():.2f}, μ={processed_segment.mean():.2f}"
                    )
                
                # Actualizar todo el monitor
                self.update_calibration_monitor()
            
            # Resaltar segmento actual en el grid principal
            self._highlight_current_segment(row, col)
            
            # Después del tiempo de exposición, pasar a fase de movimiento
            exposure_time_ms = int(exposure_time_s * 1000)
            QTimer.singleShot(exposure_time_ms, lambda: self._start_movement_phase(row, col))
        else:
            # Si no hay proyección automática, ir directo al siguiente
            self._process_next_segment()
    
    def _start_movement_phase(self, row, col):
        """
        Fase de movimiento: Apaga proyección (negro) y simula movimiento del stage.
        """
        if not self.sequence_running or self.sequence_paused:
            return
        
        movement_time_s = self.movement_time_spin.value()
        
        # Limpiar resaltado durante fase de movimiento (ya no se proyecta)
        self.current_projecting_segment = None
        
        # FASE 2: MOVIMIENTO - Pantalla negra durante movimiento
        if self.projector_active and self.projection_window is not None:
            self.projection_window.show_black_screen()
            self.log_to_console("🖤 Pantalla en negro - Preparando movimiento", "INFO")
        
        # Actualizar grid para quitar resaltado durante movimiento PRESERVANDO el zoom
        if self.grid_view_active and hasattr(self, 'grid_generated') and self.grid_generated:
            if hasattr(self, 'ax') and self.ax is not None:
                # Guardar límites actuales del zoom
                current_xlim = self.ax.get_xlim()
                current_ylim = self.ax.get_ylim()
                
                # Redibujar el grid completo
                self.display_grid()
                
                # Restaurar los límites del zoom
                self.ax.set_xlim(current_xlim)
                self.ax.set_ylim(current_ylim)
                self.canvas.draw_idle()
            else:
                self.display_grid()
        
        # Simular movimiento de stage si está activo
        if self.auto_movement_checkbox.isChecked() and movement_time_s > 0:
            self.log_to_console(f"🚀 Moviendo stage (tiempo estimado: {movement_time_s}s)", "INFO")
        
        # Después del tiempo de movimiento, procesar siguiente segmento
        if movement_time_s > 0:
            movement_time_ms = int(movement_time_s * 1000)
            QTimer.singleShot(movement_time_ms, self._process_next_segment)
        else:
            # Sin tiempo de movimiento, procesar inmediatamente
            self._process_next_segment()

    def _highlight_current_segment(self, row, col):
        """
        Resalta visualmente el segmento actual en el grid.
        Guarda información del segmento en proyección y actualiza la visualización.
        Registra información detallada en consola.
        """
        # Buscar el segmento actual en la lista
        current_segment_data = None
        for seg in self.image_segments:
            if seg['row'] == row and seg['col'] == col:
                current_segment_data = seg
                break
        
        # Registrar información completa en CONSOLA
        if current_segment_data:
            # Calcular posición en unidades del grid
            pixel_size = self.grid_cell_size / self.grid_pixels_per_cell if hasattr(self, 'grid_cell_size') else 1.0
            x_grid = (self.image_position[0] + current_segment_data['x_start']) * pixel_size if hasattr(self, 'image_position') else 0
            y_grid = (self.image_position[1] + current_segment_data['y_start']) * pixel_size if hasattr(self, 'image_position') else 0
            
            self.log_to_console(
                f"▶ PROYECTANDO CHUNK\n"
                f"  • ID: S{current_segment_data['id']}\n"
                f"  • Posición en grid: [{row}, {col}]\n"
                f"  • Coordenadas imagen (px): [{current_segment_data['x_start']}, {current_segment_data['y_start']}]\n"
                f"  • Tamaño (px): {current_segment_data['width']}×{current_segment_data['height']}\n"
                f"  • Posición en grid ({self.grid_unit if hasattr(self, 'grid_unit') else 'units'}): ({x_grid:.2f}, {y_grid:.2f})",
                "PROJECTION"
            )
        
        # Guardar información del segmento en proyección
        self.current_projecting_segment = {
            'row': row,
            'col': col,
            'segment_data': current_segment_data
        }
        
        # Actualizar visualización del grid con resaltado PRESERVANDO el zoom
        if self.grid_view_active and hasattr(self, 'grid_generated') and self.grid_generated:
            if hasattr(self, 'ax') and self.ax is not None:
                # Guardar límites actuales del zoom
                current_xlim = self.ax.get_xlim()
                current_ylim = self.ax.get_ylim()
                
                # Redibujar el grid completo con resaltado
                self.display_grid()
                
                # Restaurar los límites del zoom
                self.ax.set_xlim(current_xlim)
                self.ax.set_ylim(current_ylim)
                self.canvas.draw_idle()
            else:
                self.display_grid()
    
    def _apply_effects_to_segment(self, segment, skip_binary_effects=False):
        """
        Aplica TODOS los efectos configurados a un segmento individual.
        Incluye: Sigma, Downscaling, Brillo, Binario, Inversión
        
        Args:
            segment: Imagen del segmento (numpy array)
            skip_binary_effects: Si es True, salta los pasos de binario e inversión (útil si ya están aplicados)
        
        Returns:
            Segmento procesado con todos los efectos aplicados
        """
        import numpy as np
        
        processed = segment.copy()
        
        # 1. SIGMA (Gaussian Blur) - si está activo en los ajustes
        if hasattr(self, 'sigma') and self.sigma > 0:
            sigma = self.sigma
            # Calcular kernel size apropiado para el sigma
            kernel_size = int(2 * np.ceil(3 * sigma) + 1)
            if kernel_size > 0 and kernel_size % 2 == 1:  # Debe ser impar
                processed = cv2.GaussianBlur(processed, (kernel_size, kernel_size), sigma)
        
        # 2. DOWNSCALING / UPSCALING
        if hasattr(self, 'downscale_factor') and self.downscale_factor != 1.0:
            factor = self.downscale_factor  # Usar como float, no convertir a int
            
            # Calcular nuevas dimensiones
            original_height, original_width = processed.shape[:2]
            new_height = max(1, int(original_height / factor))
            new_width = max(1, int(original_width / factor))
            
            # Aplicar redimensionamiento PERMANENTE
            # NO volver al tamaño original - el downscaling debe reducir la resolución
            if factor > 1.0:
                # Downscale (reducir): usar INTER_AREA para mejor calidad
                processed = cv2.resize(processed, (new_width, new_height), interpolation=cv2.INTER_AREA)
                self.log_to_console(
                    f"  🔽 Downscaling aplicado: {original_width}×{original_height} → {new_width}×{new_height} px "
                    f"(factor {factor:.2f}×)",
                    "INFO"
                )
            else:
                # Upscale (aumentar): usar INTER_LINEAR
                processed = cv2.resize(processed, (new_width, new_height), interpolation=cv2.INTER_LINEAR)
                self.log_to_console(
                    f"  🔼 Upscaling aplicado: {original_width}×{original_height} → {new_width}×{new_height} px "
                    f"(factor {factor:.2f}×)",
                    "INFO"
                )
        
        # 3. BRILLO (Brightness adjustment)
        if hasattr(self, 'brightness') and self.brightness != 100:
            factor = self.brightness / 100.0
            processed = cv2.convertScaleAbs(processed, alpha=factor, beta=0)
        
        # 4. CONVERSIÓN A BINARIO
        if not skip_binary_effects and hasattr(self, 'binary_mode_enabled') and self.binary_mode_enabled:
            # Normalizar a 0-100
            normalized = processed.astype(np.float64)
            if normalized.max() > 0:
                normalized = normalized / normalized.max()
            normalized = normalized * 100.0
            
            # Aplicar threshold
            threshold = self.binary_threshold if hasattr(self, 'binary_threshold') else 50.0
            processed = np.where(normalized >= threshold, 255, 0).astype(np.uint8)
        
        # 5. INVERSIÓN DE IMAGEN
        if not skip_binary_effects and hasattr(self, 'invert_projection') and self.invert_projection:
            processed = 255 - processed if processed.max() > 1 else 1.0 - processed
        
        # 6. CALIBRACIÓN (MATRIZ DE ATENUACIÓN)
        # Aplicar matriz de compensación de uniformidad si está activa
        if (hasattr(self, 'apply_attenuation_to_grid') and self.apply_attenuation_to_grid and
            hasattr(self, 'attenuation_matrix') and self.attenuation_matrix is not None):
            
            # Normalizar la imagen procesada a rango 0-1 para aplicar calibración
            if processed.max() > 1.0:
                processed_normalized = processed.astype(np.float64) / 255.0
            else:
                processed_normalized = processed.astype(np.float64)
            
            # Obtener matriz con flips aplicados (si están configurados)
            calibration_matrix = self.get_calibration_matrix_with_flips()
            
            # Redimensionar matriz de calibración al tamaño del chunk si es necesario
            chunk_height, chunk_width = processed_normalized.shape[:2]
            matrix_height, matrix_width = calibration_matrix.shape[:2]
            
            if (chunk_height != matrix_height) or (chunk_width != matrix_width):
                # Necesitamos redimensionar la matriz de calibración
                from scipy.ndimage import zoom
                zoom_factors = (chunk_height / matrix_height, chunk_width / matrix_width)
                attenuation_resized = zoom(calibration_matrix, zoom_factors, order=1)
            else:
                attenuation_resized = calibration_matrix
            
            # Aplicar intensidad de calibración
            if hasattr(self, 'attenuation_strength'):
                strength_factor = self.attenuation_strength / 100.0
            else:
                strength_factor = 1.0
            
            # Interpolar entre sin corrección (1.0) y corrección completa
            adjusted_matrix = 1.0 + (attenuation_resized - 1.0) * strength_factor
            
            # Aplicar matriz al chunk
            processed_calibrated = np.clip(processed_normalized * adjusted_matrix, 0, 1.0)
            
            # Volver a escala 0-255 si era necesario
            if processed.max() > 1.0:
                processed = (processed_calibrated * 255.0).astype(np.uint8)
            else:
                processed = processed_calibrated.astype(np.float64)
            
            self.log_to_console(
                f"  ✨ Calibración aplicada: strength={strength_factor*100:.0f}%, "
                f"matriz {matrix_width}×{matrix_height} → chunk {chunk_width}×{chunk_height}",
                "INFO"
            )
        
        return processed

    # ═══════════════════════════════════════════════════════════════════════════
    # FUNCIONES DE TRANSFORMACIÓN DE IMAGEN (ROTACIÓN, ESPEJO)
    # ═══════════════════════════════════════════════════════════════════════════
    
    def apply_image_transforms(self, image):
        """
        Aplica transformaciones geométricas a la imagen: rotación y espejos.
        
        Args:
            image: Imagen numpy array (grayscale o color)
        
        Returns:
            Imagen transformada
        """
        if image is None:
            return None
        
        transformed = image.copy()
        
        # 1. Aplicar rotación (0-360°)
        if self.image_rotation != 0:
            # Obtener dimensiones de la imagen
            h, w = transformed.shape[:2]
            center = (w // 2, h // 2)
            
            # Crear matriz de rotación
            rotation_matrix = cv2.getRotationMatrix2D(center, self.image_rotation, 1.0)
            
            # Calcular nuevas dimensiones después de rotar
            cos_val = abs(rotation_matrix[0, 0])
            sin_val = abs(rotation_matrix[0, 1])
            new_w = int((h * sin_val) + (w * cos_val))
            new_h = int((h * cos_val) + (w * sin_val))
            
            # Ajustar la matriz de rotación para el nuevo centro
            rotation_matrix[0, 2] += (new_w / 2) - center[0]
            rotation_matrix[1, 2] += (new_h / 2) - center[1]
            
            # Aplicar rotación con fondo negro
            transformed = cv2.warpAffine(transformed, rotation_matrix, (new_w, new_h), 
                                        borderMode=cv2.BORDER_CONSTANT, borderValue=0)
        
        # 2. Aplicar espejo horizontal (flip left-right)
        if self.image_mirror_h:
            transformed = cv2.flip(transformed, 1)
        
        # 3. Aplicar espejo vertical (flip up-down)
        if self.image_mirror_v:
            transformed = cv2.flip(transformed, 0)
        
        return transformed
    
    def update_image_transform(self):
        """
        Actualiza las transformaciones de imagen cuando el usuario cambia los controles.
        """
        # Actualizar variables desde el slider (0-360°)
        self.image_rotation = self.rotation_slider.value()
        self.rotation_value_label.setText(f"{self.image_rotation}°")
        
        self.image_mirror_h = self.mirror_horizontal_checkbox.isChecked()
        self.image_mirror_v = self.mirror_vertical_checkbox.isChecked()
        
        # Limpiar cache de segmentación (las transformaciones afectan el slice)
        self._last_segmentation_pattern_id = None
        
        # Actualizar visualización INMEDIATAMENTE en el grid
        if self.pattern is not None and self.grid_view_active:
            if hasattr(self, 'ax') and self.ax is not None:
                # Guardar límites actuales del zoom
                current_xlim = self.ax.get_xlim()
                current_ylim = self.ax.get_ylim()
                
                # Redibujar el grid con la imagen transformada
                self.display_grid()
                
                # Restaurar los límites del zoom
                self.ax.set_xlim(current_xlim)
                self.ax.set_ylim(current_ylim)
                self.canvas.draw_idle()
        
        # Actualizar proyección si está activa
        if self.projector_active and self.projection_window is not None:
            current_image = self._get_projection_image()
            if current_image is not None:
                self.projection_window.update_image(current_image)
        
        self.log_to_console(
            f"🔄 Transformación actualizada: Rotación={self.image_rotation}°, "
            f"Espejo H={self.image_mirror_h}, Espejo V={self.image_mirror_v}",
            "INFO"
        )

    # ═══════════════════════════════════════════════════════════════════════════
    # FUNCIONES DE SEGMENTACIÓN DE IMAGEN (PRE-PROCESAMIENTO LITOGRÁFICO)
    # ═══════════════════════════════════════════════════════════════════════════

    def update_segmentation_mode(self, index):
        """Actualiza el modo de segmentación."""
        self.segmentation_mode = index
        
        # Mostrar/ocultar controles según el modo
        if index == 1:  # Manual
            self.manual_segments_widget.setVisible(True)
        else:
            self.manual_segments_widget.setVisible(False)
        
        self.update_segmentation_preview()

    def update_segmentation_preview(self):
        """Actualiza la información de vista previa de segmentación."""
        if self.segmentation_mode == 3: # Imagen Completa
            self.segments_x = 1
            self.segments_y = 1
            self.segment_info_label.setText("Modo: Imagen Completa (1 segmento)")
        elif self.segmentation_mode == 0:  # Automático (usar grid)
            if self.grid_view_active and hasattr(self, 'grid_width') and self.grid_width > 0:
                # Usar configuración del grid activo
                cells_x = int(self.grid_width / self.grid_cell_size)
                cells_y = int(self.grid_height / self.grid_cell_size)
                self.segments_x = cells_x
                self.segments_y = cells_y
            else:
                # Sin grid activo: usar división inteligente basada en la imagen
                if self.pattern is not None:
                    img_height, img_width = self.pattern.shape[:2]
                    # Usar chunks de tamaño razonable (~512px ideal para proyección)
                    optimal_chunk_size = 512
                    self.segments_x = max(1, img_width // optimal_chunk_size)
                    self.segments_y = max(1, img_height // optimal_chunk_size)
                    self.segment_info_label.setText(
                        f"Modo automático sin grid: {self.segments_x}×{self.segments_y} chunks (~{optimal_chunk_size}px)"
                    )
                else:
                    self.segment_info_label.setText("Cargue una imagen para calcular segmentación automática")
                    return
        elif self.segmentation_mode == 1:  # Manual
            self.segments_x = self.segments_x_spin.value()
            self.segments_y = self.segments_y_spin.value()
        
        total_blocks = self.segments_x * self.segments_y
        
        # Si ya se aplicó segmentación, mostrar segmentos reales (con contenido)
        if hasattr(self, 'image_segments') and self.image_segments:
            actual_segments = len(self.image_segments)
            self.segment_info_label.setText(
                f"Segmentos con imagen: {actual_segments} de {total_blocks} bloques ({self.segments_x}x{self.segments_y})"
            )
        else:
            # Vista previa (antes de aplicar segmentación)
            self.segment_info_label.setText(
                f"Vista previa: {total_blocks} bloques máximo ({self.segments_x}x{self.segments_y})"
            )
        
        # Calcular tamaño por segmento si hay imagen cargada
        if self.pattern is not None:
            img_height, img_width = self.pattern.shape[:2]
            segment_width = img_width // self.segments_x
            segment_height = img_height // self.segments_y
            self.segment_size_label.setText(
                f"Tamaño por segmento: {segment_width}x{segment_height} px"
            )
        else:
            self.segment_size_label.setText("Tamaño por segmento: Cargue una imagen")

    def apply_image_segmentation(self):
        """
        Divide la imagen en segmentos según la configuración.
        
        SLICE ÚNICO: Se calcula un único corte automático basado en las coordenadas
        extremas del contenido de la imagen. Este corte es DETERMINISTA y se mantiene
        en caché mientras la imagen y la configuración del grid no cambien.
        
        NO se permite crear cortes sobre cortes - el único corte válido identifica
        exactamente los chunks donde la imagen está presente.
        """
        if self.pattern is None:
            QMessageBox.warning(
                self,
                "Sin imagen",
                "Cargue una imagen primero antes de aplicar segmentación."
            )
            return
        
        try:
            import numpy as np
            
            # ═══════════════════════════════════════════════════════════════════
            # PASO 1: OBTENER IMAGEN CON TRANSFORMACIONES APLICADAS
            # ═══════════════════════════════════════════════════════════════════
            # Aplicar transformaciones geométricas (rotación, espejos) PRIMERO
            source_image = self.apply_image_transforms(self.pattern.copy())
            img_height, img_width = source_image.shape[:2]
            
            # Convertir a 0-255 si está normalizada (para visualización)
            if source_image.max() <= 1.0:
                visual_image = (source_image * 255).astype(np.uint8)
            else:
                visual_image = source_image.astype(np.uint8)
            
            # ═══════════════════════════════════════════════════════════════════
            # MODO DE SLICE: SOLO CELDA (Grid completo)
            # ═══════════════════════════════════════════════════════════════════
            # Usamos EXACTAMENTE las mismas celdas que ya están dibujadas en el grid
            if hasattr(self, 'grid_width') and hasattr(self, 'grid_cell_size'):
                # Calcular número de celdas del grid (igual a las que se dibujan)
                cells_x = int(self.grid_width / self.grid_cell_size)
                cells_y = int(self.grid_height / self.grid_cell_size)
                self.segments_x = cells_x
                self.segments_y = cells_y
                slice_type = f"CELDA (Grid {cells_x}×{cells_y})"
            else:
                # Sin grid, no se puede segmentar
                self.log_to_console("❌ ERROR: No hay grid configurado", "ERROR")
                return
            
            # Log de configuración con transformaciones
            transform_str = ""
            if self.image_rotation != 0 or self.image_mirror_h or self.image_mirror_v:
                parts = []
                if self.image_rotation != 0:
                    parts.append(f"Rot={self.image_rotation}°")
                if self.image_mirror_h:
                    parts.append("MirrorH")
                if self.image_mirror_v:
                    parts.append("MirrorV")
                transform_str = f" | Transformaciones: {', '.join(parts)}"
            
            self.log_to_console(
                f"🔧 MODO DE SLICE: {slice_type}\n"
                f"  • Divisiones: {self.segments_x}×{self.segments_y}{transform_str}",
                "INFO"
            )
            
            # === PASO 2: VERIFICAR CACHE (DETERMINISMO E IDEMPOTENCIA) ===
            # El cache garantiza que no se recalcule el slice si:
            # - La imagen es la misma (mismo ID de carga)
            # - La configuración del grid no cambió (segments_x, segments_y)
            # - Las transformaciones no cambiaron (rotación, espejos)
            # - La posición de la imagen no cambió
            # IDEMPOTENCIA: Aplicar dos veces con mismos parámetros = mismo resultado
            
            current_grid_config = (self.segments_x, self.segments_y, self.image_rotation, 
                                  self.image_mirror_h, self.image_mirror_v)
            current_image_position = tuple(self.image_position) if hasattr(self, 'image_position') else (0.0, 0.0)
            current_pattern_id = getattr(self, '_pattern_load_id', None)
            
            use_cache = False
            cells_with_content = []  # Inicializar lista de celdas con contenido
            
            if (current_pattern_id is not None and
                hasattr(self, '_last_segmentation_pattern_id') and
                self._last_segmentation_pattern_id == current_pattern_id and 
                self._last_segmentation_grid_config == current_grid_config and
                self._last_segmentation_bounds is not None and
                hasattr(self, '_last_image_position') and
                self._last_image_position == current_image_position and
                hasattr(self, '_last_cells_with_content')):
                use_cache = True
                image_bounds = self._last_segmentation_bounds
                cells_with_content = self._last_cells_with_content  # Restaurar lista de celdas
                self.log_to_console(
                    "✓✓✓ USANDO SLICE EN CACHÉ (IDEMPOTENCIA)\n"
                    "    La operación es idempotente - mismo resultado sin reprocesar", 
                    "SUCCESS"
                )
            else:
                # Explicar por qué se recalcula
                if not hasattr(self, '_last_segmentation_pattern_id') or self._last_segmentation_pattern_id != current_pattern_id:
                    reason = "imagen diferente cargada"
                elif self._last_segmentation_grid_config != current_grid_config:
                    reason = f"configuración cambió de {self._last_segmentation_grid_config} a {current_grid_config}"
                elif hasattr(self, '_last_image_position') and self._last_image_position != current_image_position:
                    reason = f"posición cambió de {self._last_image_position} a {current_image_position}"
                else:
                    reason = "primer cálculo"
                
                self.log_to_console(
                    f"⚙️ CALCULANDO SLICE ÚNICO: {reason}\n"
                    f"    Imagen: {img_width}×{img_height} px | Grid: {self.segments_x}×{self.segments_y}",
                    "SEGMENTATION"
                )
                
                # ═══════════════════════════════════════════════════════════════════
                # CALCULAR CELDAS QUE INTERSECTAN CON LA IMAGEN
                # ═══════════════════════════════════════════════════════════════════
                
                image_bounds = None
                cells_with_content = []
                
                # La imagen está colocada en el grid
                # Necesitamos calcular qué celdas DEL GRID ocupa la imagen
                # La imagen tiene dimensiones img_width × img_height en PÍXELES
                # Cada celda del grid tiene grid_pixels_per_cell píxeles
                
                if hasattr(self, 'grid_pixels_per_cell'):
                    # Calcular cuántas celdas del grid ocupa la imagen
                    cells_occupied_x = int(np.ceil(img_width / self.grid_pixels_per_cell))
                    cells_occupied_y = int(np.ceil(img_height / self.grid_pixels_per_cell))
                    
                    # Las celdas que ocupa la imagen van desde (0,0) hasta (cells_occupied_x-1, cells_occupied_y-1)
                    start_cell_x = 0
                    start_cell_y = 0
                    end_cell_x = min(cells_occupied_x - 1, self.segments_x - 1)
                    end_cell_y = min(cells_occupied_y - 1, self.segments_y - 1)
                    
                    for row in range(start_cell_y, end_cell_y + 1):
                        for col in range(start_cell_x, end_cell_x + 1):
                            cells_with_content.append((row, col))
                else:
                    # Fallback: usar toda la imagen
                    start_cell_x = 0
                    start_cell_y = 0
                    end_cell_x = self.segments_x - 1
                    end_cell_y = self.segments_y - 1
                    
                    for row in range(start_cell_y, end_cell_y + 1):
                        for col in range(start_cell_x, end_cell_x + 1):
                            cells_with_content.append((row, col))
                
                # El bounding box es simplemente todo el grid que cubre la imagen
                image_bounds = {
                    'start_x': start_cell_x,
                    'start_y': start_cell_y,
                    'end_x': end_cell_x,
                    'end_y': end_cell_y
                }
                
                self.log_to_console(
                    f"📊 Cálculo de cobertura de imagen:\n"
                    f"  • Grid total: {self.segments_x}×{self.segments_y} = {self.segments_x * self.segments_y} celdas\n"
                    f"  • Imagen ocupa: {len(cells_with_content)} celdas",
                    "INFO"
                )
                
                # DEBUG: Mostrar las primeras 10 celdas
                if len(cells_with_content) > 0:
                    preview_cells = cells_with_content[:min(10, len(cells_with_content))]
                    cells_str = ", ".join([f"[{r},{c}]" for r, c in preview_cells])
                    suffix = "..." if len(cells_with_content) > 10 else ""
                    self.log_to_console(f"  • Primeras celdas: {cells_str}{suffix}", "INFO")
                
                # ═══════════════════════════════════════════════════════════════════
                # ACTUALIZAR CACHE - GARANTIZAR IDEMPOTENCIA
                # ═══════════════════════════════════════════════════════════════════
                self._last_segmentation_pattern_id = current_pattern_id
                self._last_segmentation_grid_config = current_grid_config
                self._last_segmentation_bounds = image_bounds
                self._last_image_position = current_image_position
                self._last_cells_with_content = cells_with_content
                
                chunks_in_slice = (end_cell_x - start_cell_x + 1) * (end_cell_y - start_cell_y + 1)
                self.log_to_console(
                    f"✓ SLICE CALCULADO:\n"
                    f"  • Rango X: celdas {start_cell_x} → {end_cell_x} ({end_cell_x - start_cell_x + 1} celdas)\n"
                    f"  • Rango Y: celdas {start_cell_y} → {end_cell_y} ({end_cell_y - start_cell_y + 1} celdas)\n"
                    f"  • Total chunks: {chunks_in_slice}",
                    "SUCCESS"
                )
            
            # ═══════════════════════════════════════════════════════════════════
            # CALCULAR TAMAÑO DE CADA CHUNK (basado en celdas del grid)
            # ═══════════════════════════════════════════════════════════════════════
            # Usar el tamaño de las celdas del grid
            # Cada chunk debe tener el tamaño de una celda del grid (en píxeles)
            if hasattr(self, 'grid_pixels_per_cell'):
                cell_width = float(self.grid_pixels_per_cell)
                cell_height = float(self.grid_pixels_per_cell)
            else:
                # Fallback: dividir la imagen uniformemente
                cell_width = img_width / self.segments_x
                cell_height = img_height / self.segments_y
            
            if image_bounds is not None:
                slice_width_cells = image_bounds['end_x'] - image_bounds['start_x'] + 1
                slice_height_cells = image_bounds['end_y'] - image_bounds['start_y'] + 1
                
                self.log_to_console(
                    f"📐 Configuración chunks:\n"
                    f"  • Tamaño celda: {cell_width:.1f}×{cell_height:.1f} px\n"
                    f"  • Área slice: {slice_width_cells}×{slice_height_cells} celdas\n"
                    f"  • Grid total: {self.segments_x}×{self.segments_y}",
                    "INFO"
                )
            
            # ═══════════════════════════════════════════════════════════════════
            # CREAR CHUNKS SOLO PARA LAS CELDAS CON CONTENIDO DETECTADO
            # ═══════════════════════════════════════════════════════════════════
            # IMPORTANTE: No crear chunks para todo el bounding box
            # Solo crear chunks para las celdas específicas en cells_with_content
            self.image_segments = []
            segment_id = 0
            total_blocks = self.segments_x * self.segments_y
            empty_blocks = 0
            skipped_outside_image = 0
            
            # Convertir lista de celdas con contenido a set para búsqueda rápida
            content_cells_set = set(cells_with_content) if 'cells_with_content' in locals() else set()
            
            for row in range(self.segments_y):
                for col in range(self.segments_x):
                    
                    # ═══════════════════════════════════════════════════════════════════
                    # SOLO PROCESAR CELDAS QUE FUERON DETECTADAS CON CONTENIDO
                    # ═══════════════════════════════════════════════════════════════════
                    if (row, col) not in content_cells_set:
                        skipped_outside_image += 1
                        continue
                    
                    # ═══════════════════════════════════════════════════════════════════
                    # CALCULAR COORDENADAS DE LA CELDA EN EL GRID
                    # ═══════════════════════════════════════════════════════════════════
                    x_start = int(col * cell_width)
                    y_start = int(row * cell_height)
                    x_end = int(min((col + 1) * cell_width, img_width))
                    y_end = int(min((row + 1) * cell_height, img_height))
                    
                    # ═══════════════════════════════════════════════════════════════════
                    # EXTRAER SEGMENTO Y RELLENAR A TAMAÑO COMPLETO DE CELDA
                    # ═══════════════════════════════════════════════════════════════════
                    # IMPORTANTE: Todos los chunks deben tener el MISMO tamaño
                    # Si es modo CELDA: todos deben ser cell_width × cell_height (ej: 100×100)
                    # Si hay partes vacías, rellenar con negro para mantener consistencia
                    
                    # Extraer la parte de la imagen que intersecta con esta celda
                    segment_from_image = source_image[y_start:y_end, x_start:x_end].copy()
                    
                    # Crear un chunk del tamaño completo de la celda (rellenado con negro)
                    chunk_width = int(cell_width)
                    chunk_height = int(cell_height)
                    
                    # Crear chunk vacío (negro) del tamaño de la celda
                    if len(source_image.shape) == 3:
                        segment = np.zeros((chunk_height, chunk_width, source_image.shape[2]), dtype=source_image.dtype)
                    else:
                        segment = np.zeros((chunk_height, chunk_width), dtype=source_image.dtype)
                    
                    # Copiar la parte de imagen que tenemos al chunk
                    actual_height = segment_from_image.shape[0]
                    actual_width = segment_from_image.shape[1]
                    segment[0:actual_height, 0:actual_width] = segment_from_image
                    
                    # ═══════════════════════════════════════════════════════════════════
                    # CREAR CHUNK CON TAMAÑO CONSISTENTE
                    # ═══════════════════════════════════════════════════════════════════
                    # Todos los chunks tienen el mismo tamaño (cell_width × cell_height)
                    # Esto garantiza consistencia en la proyección
                    if segment.size > 0:
                        chunk_info = {
                            'id': segment_id,
                            'row': row,
                            'col': col,
                            'image': segment,  # Tamaño completo de celda (con relleno negro si es necesario)
                            'x_start': x_start,
                            'y_start': y_start,
                            'x_end': x_start + chunk_width,  # Usar tamaño completo de celda
                            'y_end': y_start + chunk_height,  # Usar tamaño completo de celda
                            'width': chunk_width,  # Siempre el tamaño completo de la celda
                            'height': chunk_height,  # Siempre el tamaño completo de la celda
                            'effects_applied': False
                        }
                        self.image_segments.append(chunk_info)
                        
                        # DEBUG: Log primeros 5 chunks extraídos
                        if segment_id < 5:
                            self.log_to_console(
                                f"  🔹 Chunk #{segment_id} [fila={row}, col={col}]: "
                                f"coords=({x_start},{y_start})-({x_end},{y_end}), "
                                f"size={x_end-x_start}×{y_end-y_start}px, "
                                f"values=[{segment.min():.2f}, {segment.max():.2f}]",
                                "INFO"
                            )
                        
                        segment_id += 1
                    else:
                        empty_blocks += 1
            
            # Actualizar información
            self.update_segmentation_preview()
            
            # Actualizar grid con overlay PRESERVANDO el zoom
            if self.show_segments_overlay and hasattr(self, 'grid_generated') and self.grid_generated:
                if hasattr(self, 'ax') and self.ax is not None:
                    # Guardar límites actuales del zoom
                    current_xlim = self.ax.get_xlim()
                    current_ylim = self.ax.get_ylim()
                    
                    # Redibujar el grid completo
                    self.display_grid()
                    
                    # Restaurar los límites del zoom
                    self.ax.set_xlim(current_xlim)
                    self.ax.set_ylim(current_ylim)
                    self.canvas.draw_idle()
                else:
                    self.display_grid()
            
            segments_with_content = len(self.image_segments)
            
            # ═══════════════════════════════════════════════════════════════════
            # CALCULAR INFORMACIÓN DETALLADA DEL SLICE Y PROYECCIÓN
            # ═══════════════════════════════════════════════════════════════════
            
            # Información del slice
            if image_bounds is not None:
                slice_info = (
                    f"\n🔲 SLICE ÚNICO ACTIVO:\n"
                    f"  • Rango X: [{image_bounds['start_x']} → {image_bounds['end_x']}]\n"
                    f"  • Rango Y: [{image_bounds['start_y']} → {image_bounds['end_y']}]\n"
                    f"  • Dimensiones: {image_bounds['end_x'] - image_bounds['start_x'] + 1} × "
                    f"{image_bounds['end_y'] - image_bounds['start_y'] + 1} celdas\n"
                )
            else:
                slice_info = ""
            
            # Calcular tamaño promedio de chunks y resolución en proyección
            if segments_with_content > 0:
                # Tamaños de chunks
                chunk_widths = [seg['width'] for seg in self.image_segments]
                chunk_heights = [seg['height'] for seg in self.image_segments]
                avg_chunk_width = sum(chunk_widths) / len(chunk_widths)
                avg_chunk_height = sum(chunk_heights) / len(chunk_heights)
                min_chunk_width = min(chunk_widths)
                max_chunk_width = max(chunk_widths)
                min_chunk_height = min(chunk_heights)
                max_chunk_height = max(chunk_heights)
                
                # Calcular resolución de proyección (si hay proyector activo)
                projection_info = ""
                if self.projector_active and self.projection_window is not None:
                    screen_width = self.projection_window.screen_geometry.width()
                    screen_height = self.projection_window.screen_geometry.height()
                    
                    # Calcular factor de escala para chunk promedio
                    scale_x = screen_width / avg_chunk_width
                    scale_y = screen_height / avg_chunk_height
                    scale_factor = min(scale_x, scale_y)
                    
                    projected_width = int(avg_chunk_width * scale_factor)
                    projected_height = int(avg_chunk_height * scale_factor)
                    
                    projection_info = (
                        f"\n🖥️ RESOLUCIÓN EN PROYECCIÓN:\n"
                        f"  • Monitor: {screen_width}×{screen_height} px\n"
                        f"  • Chunk promedio: {avg_chunk_width:.1f}×{avg_chunk_height:.1f} px\n"
                        f"  • Proyectado como: {projected_width}×{projected_height} px\n"
                        f"  • Factor de escala: {scale_factor:.2f}×\n"
                    )
                
                chunk_size_info = (
                    f"\n📏 CARACTERÍSTICAS DE LOS CHUNKS:\n"
                    f"  • Tamaño promedio: {avg_chunk_width:.1f}×{avg_chunk_height:.1f} px\n"
                    f"  • Rango ancho: {min_chunk_width}-{max_chunk_width} px\n"
                    f"  • Rango alto: {min_chunk_height}-{max_chunk_height} px\n"
                )
            else:
                chunk_size_info = ""
                projection_info = ""
            
            # Información de transformaciones
            transform_info = ""
            if self.image_rotation != 0 or self.image_mirror_h or self.image_mirror_v:
                transforms = []
                if self.image_rotation != 0:
                    transforms.append(f"Rotación {self.image_rotation}°")
                if self.image_mirror_h:
                    transforms.append("Espejo H")
                if self.image_mirror_v:
                    transforms.append("Espejo V")
                transform_info = f"\n🔄 TRANSFORMACIONES: {', '.join(transforms)}\n"
            
            cache_status = "✓ Reutilizado desde caché" if use_cache else "⚙️ Recién calculado"
            
            QMessageBox.information(
                self,
                "✓ Segmentación Completada",
                f"SISTEMA DE SLICE POR CELDA (Grid)\n"
                f"Estado: {cache_status}\n"
                f"{transform_info}"
                f"{slice_info}"
                f"{chunk_size_info}"
                f"{projection_info}\n"
                f"📊 ESTADÍSTICAS:\n"
                f"  • Grid configurado: {self.segments_x}×{self.segments_y} = {total_blocks} divisiones\n"
                f"  • Chunks activos (con contenido): {segments_with_content}\n"
                f"  • Chunks fuera del slice: {skipped_outside_image}\n"
                f"  • Chunks vacíos (dentro del slice): {empty_blocks}\n\n"
                f"✓ Los chunks se proyectarán en orden secuencial\n"
                f"✓ Cada chunk se escalará al máximo tamaño posible\n"
                f"✓ El slice es DETERMINISTA y se mantendrá mientras\n"
                f"   no cambie la imagen, su posición o el grid"
            )
                
        except Exception as e:
            QMessageBox.critical(
                self,
                "Error",
                f"Error al segmentar imagen: {str(e)}"
            )

    def toggle_segments_overlay(self, state):
        """Activa/desactiva el overlay visual de segmentos en el grid."""
        self.show_segments_overlay = bool(state)
        if self.grid_view_active and hasattr(self, 'grid_generated') and self.grid_generated:
            # Guardar límites actuales del zoom
            if hasattr(self, 'ax') and self.ax is not None:
                current_xlim = self.ax.get_xlim()
                current_ylim = self.ax.get_ylim()
                
                # Redibujar el grid completo
                self.display_grid()
                
                # Restaurar los límites del zoom
                self.ax.set_xlim(current_xlim)
                self.ax.set_ylim(current_ylim)
                self.canvas.draw_idle()
            else:
                self.display_grid()

    def draw_segments_overlay(self):
        """
        Dibuja el overlay de segmentos en el grid.
        Muestra rectángulos con líneas discontinuas sobre cada segmento de imagen.
        """
        if not self.show_segments_overlay or not self.image_segments:
            return
        
        if not hasattr(self, 'ax') or self.ax is None:
            return
        
        if not hasattr(self, 'image_on_grid') or self.image_on_grid is None:
            return
        
        # Convertir píxeles a unidades del grid
        pixel_size = self.grid_cell_size / self.grid_pixels_per_cell
        
        # Dibujar rectángulos de segmentos
        for segment in self.image_segments:
            # Coordenadas en píxeles de la imagen
            x_start_px = segment['x_start']
            y_start_px = segment['y_start']
            width_px = segment['width']
            height_px = segment['height']
            
            # Convertir a coordenadas del grid (unidades del grid)
            # Sumar la posición de la imagen en el grid
            x_start_grid = (self.image_position[0] + x_start_px) * pixel_size
            y_start_grid = (self.image_position[1] + y_start_px) * pixel_size
            width_grid = width_px * pixel_size
            height_grid = height_px * pixel_size
            
            # Dibujar rectángulo del segmento
            from matplotlib.patches import Rectangle
            rect = Rectangle(
                (x_start_grid, y_start_grid), width_grid, height_grid,
                linewidth=2, edgecolor='cyan', facecolor='none',
                linestyle='--', alpha=0.8
            )
            self.ax.add_patch(rect)
            
            # Añadir etiqueta del segmento en el centro
            center_x = x_start_grid + width_grid / 2
            center_y = y_start_grid + height_grid / 2
            self.ax.text(
                center_x, center_y,
                f"S{segment['id']}",
                ha='center', va='center',
                fontsize=10, color='cyan', weight='bold',
                bbox=dict(boxstyle='round,pad=0.5', 
                         facecolor='black', alpha=0.7, 
                         edgecolor='cyan', linewidth=1.5)
            )
    
    def draw_projecting_segment_highlight(self):
        """
        Resalta con color rojo tenue el chunk que se está proyectando actualmente.
        Solo relleno visual, sin texto ni etiquetas (info va a consola).
        """
        if not self.current_projecting_segment:
            return
        
        if not hasattr(self, 'ax') or self.ax is None:
            return
        
        if not hasattr(self, 'image_on_grid') or self.image_on_grid is None:
            return
        
        segment_data = self.current_projecting_segment.get('segment_data')
        if not segment_data:
            return
        
        # Convertir píxeles a unidades del grid
        pixel_size = self.grid_cell_size / self.grid_pixels_per_cell
        
        # Coordenadas en píxeles de la imagen
        x_start_px = segment_data['x_start']
        y_start_px = segment_data['y_start']
        width_px = segment_data['width']
        height_px = segment_data['height']
        
        # Convertir a coordenadas del grid (unidades del grid)
        x_start_grid = (self.image_position[0] + x_start_px) * pixel_size
        y_start_grid = (self.image_position[1] + y_start_px) * pixel_size
        width_grid = width_px * pixel_size
        height_grid = height_px * pixel_size
        
        # Dibujar SOLO rectángulo con relleno rojo tenue (sin texto)
        from matplotlib.patches import Rectangle
        
        # Rectángulo con relleno rojo semi-transparente
        rect_highlight = Rectangle(
            (x_start_grid, y_start_grid), width_grid, height_grid,
            linewidth=0, edgecolor='none', facecolor='red',
            alpha=0.4, zorder=98
        )
        self.ax.add_patch(rect_highlight)

    def project_full_image(self):
        """
        Proyecta la imagen completa manualmente en el monitor secundario.
        La imagen permanecerá hasta que se apague el proyector o se inicie otra operación.
        """
        if not self.projector_active:
            QMessageBox.warning(
                self,
                "Proyector inactivo",
                "Debe activar el proyector antes de proyectar la imagen.\n\n"
                "Use el botón '🎬 Proyectar' primero."
            )
            return
        
        if self.projection_window is None:
            QMessageBox.warning(
                self,
                "Error",
                "No hay ventana de proyección disponible."
            )
            return
        
        # Obtener imagen a proyectar
        image_to_project = self._get_projection_image()
        
        if image_to_project is None:
            QMessageBox.warning(
                self,
                "Sin imagen",
                "No hay imagen disponible para proyectar.\n\n"
                "Cargue una imagen primero."
            )
            return
        
        # Proyectar imagen completa
        self.projection_window.set_image(image_to_project)
        
        self.log_to_console(
            "🖼️ Proyectando imagen completa en monitor secundario",
            "SUCCESS"
        )
    
    def start_timed_exposure(self):
        # Verificar conflictos con otros modos
        if self.sequence_running:
            QMessageBox.warning(self, "Conflicto", "No se puede iniciar exposición mientras la secuencia de segmentos está activa.")
            return
        if self.frequency_mode:
            QMessageBox.warning(self, "Conflicto", "No se puede iniciar exposición mientras el modo frecuencia está activo.")
            return

        if not self.projector_active:
            QMessageBox.warning(
                self,
                "Proyección inactiva",
                "Debe activar la proyección antes de iniciar la exposición.",
            )
            return

        # Asegurar que se proyecta la imagen completa
        if self.projection_window is not None and self.pattern is not None:
            self.projection_window.set_image(self.pattern)
            # Aplicar configuración binaria global si está activa
            if self.binary_mode_enabled:
                self.projection_window.set_binary_mode(True)
                self.projection_window.set_binary_threshold(self.binary_threshold)
                self.projection_window.set_inversion(self.invert_projection)

        try:
            # Precisión float para tiempos de exposición (microsegundos)
            exposure_time = float(self.exposure_time_input.text())
            if exposure_time <= 0:
                raise ValueError("El tiempo debe ser mayor a 0")
        except ValueError:
            QMessageBox.warning(
                self,
                "Tiempo inválido",
                "Por favor ingrese un tiempo de exposición válido (en segundos).\n\n"
                "Ejemplo: 5, 10.5, 0.001 (1ms), 0.000001 (1μs)",
            )
            return

        try:
            # Intensidad normalizada como float 0-100
            intensity = float(self.exposure_intensity_input.text())
            if intensity < 0 or intensity > 100:
                raise ValueError("La intensidad debe estar entre 0 y 100")
        except ValueError:
            QMessageBox.warning(
                self,
                "Intensidad inválida",
                "Por favor ingrese una intensidad válida (0-100).\n\n"
                "Ejemplo: 50, 80, 100, 75.5",
            )
            return

        try:
            cycles = int(self.exposure_cycles_input.text())
            if cycles <= 0:
                raise ValueError("Los ciclos deben ser mayor a 0")
        except ValueError:
            QMessageBox.warning(
                self,
                "Ciclos inválidos",
                "Por favor ingrese un número de ciclos válido (número entero positivo).\n\n"
                "Ejemplo: 1, 3 o 5",
            )
            return

        # Almacenar con precisión float para litografía
        self.exposure_duration = float(exposure_time)
        self.exposure_cycles_total = cycles
        self.exposure_cycles_completed = 0
        self.exposure_start_time = float(time.time())  # Timestamp con precisión μs
        self.exposure_target_brightness = float(intensity)

        # QSlider requiere int, pero mantenemos precisión internamente
        self.brightness_slider.setValue(int(round(intensity)))
        self.update_brightness()

        self.exposure_active = True
        self.exposure_button.setVisible(False)
        self.stop_exposure_button.setVisible(True)

        self.exposure_time_input.setEnabled(False)
        self.exposure_intensity_input.setEnabled(False)
        self.exposure_cycles_input.setEnabled(False)
        self.brightness_slider.setEnabled(False)

        # Timer requiere int (milisegundos)
        self.exposure_timer.start(int(round(exposure_time * 1000)))
        self.countdown_timer.start()

        self.update_countdown()

    def update_countdown(self):
        """
        Actualiza el contador de tiempo de exposición.
        Precisión de décimas de segundo para visualización (internamente μs).
        """
        if not self.exposure_active:
            return

        # Cálculo con precisión float (microsegundos)
        elapsed = float(time.time()) - self.exposure_start_time
        remaining = max(0.0, self.exposure_duration - elapsed)

        # Mostrar con 3 decimales para tiempos cortos (ms/μs)
        if remaining < 1.0:
            self.exposure_status_label.setText(
                f"⏱️ Ciclo {self.exposure_cycles_completed + 1}/{self.exposure_cycles_total} | "
                f"Tiempo restante: {remaining*1000:.3f}ms"
            )
        else:
            self.exposure_status_label.setText(
                f"⏱️ Ciclo {self.exposure_cycles_completed + 1}/{self.exposure_cycles_total} | "
                f"Tiempo restante: {remaining:.3f}s"
            )

    def stop_timed_exposure(self):
        self.countdown_timer.stop()

        self.exposure_cycles_completed += 1

        if self.exposure_cycles_completed < self.exposure_cycles_total:
            self.brightness_slider.setValue(0)
            self.update_brightness()

            self.exposure_status_label.setText(
                f"⏸️ Ciclo {self.exposure_cycles_completed}/{self.exposure_cycles_total} completado | "
                f"Preparando siguiente ciclo..."
            )

            if self.inter_cycle_delay > 0:
                self.inter_cycle_timer.start(self.inter_cycle_delay)
            else:
                self.resume_next_cycle()
        else:
            if self.final_brightness_mode == "zero":
                self.brightness_slider.setValue(0)
            else:
                self.brightness_slider.setValue(100)
            self.update_brightness()

            self.finish_exposure_sequence()

    def finish_exposure_sequence(self):
        self.exposure_timer.stop()
        self.countdown_timer.stop()
        self.inter_cycle_timer.stop()

        self.exposure_active = False
        self.exposure_button.setVisible(True)
        self.stop_exposure_button.setVisible(False)

        self.exposure_time_input.setEnabled(True)
        self.exposure_intensity_input.setEnabled(True)
        self.exposure_cycles_input.setEnabled(True)
        self.brightness_slider.setEnabled(True)

        brightness_text = "0%" if self.final_brightness_mode == "zero" else "100%"
        self.exposure_status_label.setText(
            f"✅ Exposición completada: {self.exposure_cycles_completed} ciclo(s) | "
            f"Brillo final: {brightness_text}"
        )

    def force_stop_exposure(self):
        self.exposure_timer.stop()
        self.countdown_timer.stop()
        self.inter_cycle_timer.stop()

        if self.final_brightness_mode == "zero":
            self.brightness_slider.setValue(0)
        else:
            self.brightness_slider.setValue(100)
        self.update_brightness()

        self.exposure_active = False
        self.exposure_button.setVisible(True)
        self.stop_exposure_button.setVisible(False)

        self.exposure_time_input.setEnabled(True)
        self.exposure_intensity_input.setEnabled(True)
        self.exposure_cycles_input.setEnabled(True)
        self.brightness_slider.setEnabled(True)

        self.exposure_status_label.setText(
            f"⏹️ Exposición detenida: {self.exposure_cycles_completed}/{self.exposure_cycles_total} ciclo(s) completados"
        )

    def start_frequency_mode(self):
        # Verificar conflictos con otros modos
        if self.sequence_running:
            QMessageBox.warning(self, "Conflicto", "No se puede iniciar frecuencia mientras la secuencia de segmentos está activa.")
            return
        if self.exposure_active:
            QMessageBox.warning(self, "Conflicto", "No se puede iniciar frecuencia mientras la exposición está activa.")
            return

        if not self.projector_active:
            QMessageBox.warning(
                self,
                "Proyección inactiva",
                "Debe activar la proyección antes de iniciar el modo de frecuencia.",
            )
            return

        # Asegurar que se proyecta la imagen completa
        if self.projection_window is not None and self.pattern is not None:
            self.projection_window.set_image(self.pattern)
            # Aplicar configuración binaria global si está activa
            if self.binary_mode_enabled:
                self.projection_window.set_binary_mode(True)
                self.projection_window.set_binary_threshold(self.binary_threshold)
                self.projection_window.set_inversion(self.invert_projection)

        try:
            freq_value = float(self.frequency_value_input.text())
            if freq_value <= 0:
                raise ValueError("La frecuencia debe ser mayor a 0")
        except ValueError:
            QMessageBox.warning(
                self,
                "Frecuencia inválida",
                "Por favor ingrese una frecuencia válida (mayor a 0).\n\n"
                "Ejemplo: 1, 2.5 o 10",
            )
            return

        unit = self.frequency_unit_combo.currentText()
        if unit == "kHz":
            freq_hz = freq_value * 1000
        elif unit == "MHz":
            freq_hz = freq_value * 1000000
        else:  # Hz
            freq_hz = freq_value

        period = 1.0 / freq_hz

        try:
            duration = float(self.frequency_duration_input.text())
            if duration < 0:
                raise ValueError("La duración debe ser 0 o mayor")
        except ValueError:
            QMessageBox.warning(
                self,
                "Duración inválida",
                "Por favor ingrese una duración válida (0 para infinito).\n\n"
                "Ejemplo: 0, 30 o 60",
            )
            return

        try:
            intensity = int(self.exposure_intensity_input.text())
            if intensity < 0 or intensity > 100:
                raise ValueError("La intensidad debe estar entre 0 y 100")
        except ValueError:
            QMessageBox.warning(
                self,
                "Intensidad inválida",
                "Por favor configure una intensidad válida en la sección de exposición (0-100).",
            )
            return

        self.frequency_mode = True
        self.frequency_period = period
        self.exposure_target_brightness = intensity
        self.frequency_duration = duration
        self.frequency_start_time = time.time()

        self.frequency_button.setVisible(False)
        self.stop_frequency_button.setVisible(True)
        self.frequency_value_input.setEnabled(False)
        self.frequency_unit_combo.setEnabled(False)
        self.frequency_duration_input.setEnabled(False)
        self.exposure_intensity_input.setEnabled(False)
        self.brightness_slider.setEnabled(False)

        if duration > 0:
            self.frequency_timer.start(int(duration * 1000))

        self.frequency_cycle_count = 0
        self.start_frequency_cycle()

    def start_frequency_cycle(self):

        if not self.frequency_mode:
            return

        # QSlider requiere int, redondear desde float interno
        self.brightness_slider.setValue(int(round(self.exposure_target_brightness)))
        self.update_brightness()

        on_time = self.frequency_period / 2.0

        self.frequency_cycle_count += 1

        if self.frequency_duration > 0:
            elapsed = time.time() - self.frequency_start_time
            remaining = max(0, self.frequency_duration - elapsed)
            self.frequency_status_label.setText(
                f"🌊 Ciclo #{self.frequency_cycle_count} | "
                f"Frecuencia activa | Tiempo restante: {remaining:.1f}s"
            )
        else:
            self.frequency_status_label.setText(
                f"🌊 Ciclo #{self.frequency_cycle_count} | "
                f"Frecuencia activa (infinito)"
            )

        QTimer.singleShot(int(on_time * 1000), self.frequency_off_phase)

    def frequency_off_phase(self):

        if not self.frequency_mode:
            return

        self.brightness_slider.setValue(0)
        self.update_brightness()

        off_time = self.frequency_period / 2.0

        QTimer.singleShot(int(off_time * 1000), self.start_frequency_cycle)

    def stop_frequency_mode(self):

        self.force_stop_frequency()

        if self.final_brightness_mode == "full":
            final_brightness = 100
            brightness_text = "Brillo final: 100%"
        else:
            final_brightness = 0
            brightness_text = "Brillo final: 0%"

        self.frequency_status_label.setText(
            f"✅ Modo de frecuencia completado: {self.frequency_cycle_count} ciclos - {brightness_text}"
        )

    def force_stop_frequency(self):
        self.frequency_mode = False
        self.frequency_timer.stop()

        if self.final_brightness_mode == "full":
            final_brightness = 100
            brightness_text = "Brillo final: 100%"
        else:
            final_brightness = 0
            brightness_text = "Brillo final: 0%"

        self.brightness_slider.setValue(final_brightness)
        self.update_brightness()

        self.frequency_button.setVisible(True)
        self.stop_frequency_button.setVisible(False)
        self.frequency_value_input.setEnabled(True)
        self.frequency_unit_combo.setEnabled(True)
        self.frequency_duration_input.setEnabled(True)
        self.exposure_intensity_input.setEnabled(True)
        self.brightness_slider.setEnabled(True)

        if not hasattr(self, "frequency_cycle_count"):
            self.frequency_cycle_count = 0

        self.frequency_status_label.setText(
            f"⏹️ Modo de frecuencia detenido: {self.frequency_cycle_count} ciclos completados - {brightness_text}"
        )

    def show_preferences_menu(self):
        menu = QMenu(self)
        menu.setStyleSheet(
            """
            QMenu {
                background-color: """
            + ("#1E1E1E" if self.dark_mode else "#FFFFFF")
            + """;
                color: """
            + ("#E0E0E0" if self.dark_mode else "#000000")
            + """;
                border: 1px solid """
            + ("#2E2E2E" if self.dark_mode else "#CCCCCC")
            + """;
                border-radius: 8px;
                padding: 8px;
            }
            QMenu::item {
                padding: 8px 20px;
                border-radius: 4px;
            }
            QMenu::item:selected {
                background-color: #03DAC6;
                color: #121212;
            }
        """
        )

        if self.dark_mode:
            theme_action = menu.addAction("☀️ Modo Claro")
        else:
            theme_action = menu.addAction("🌙 Modo Oscuro")

        theme_action.triggered.connect(self.toggle_theme)

        scale_action = menu.addAction("📐 Configuración de Escala")
        scale_action.triggered.connect(self.show_scale_config)

        exposure_config_action = menu.addAction("⏱️ Configuración de Exposición")
        exposure_config_action.triggered.connect(self.show_exposure_config)

        grid_config_action = menu.addAction("📏 Configuración de Grid")
        grid_config_action.triggered.connect(self.show_grid_color_config)
        
        effects_action = menu.addAction("✨ Aplicar Efectos en Grid" if not self.apply_effects_to_grid else "✨ Desactivar Efectos en Grid")
        effects_action.triggered.connect(self.toggle_grid_effects)
        
        # Opción para limpiar cache de segmentación
        clear_cache_action = menu.addAction("🗑️ Limpiar Cache de Segmentación")
        clear_cache_action.triggered.connect(self.clear_segmentation_cache)

        menu.exec_(
            self.preferences_button.mapToGlobal(
                self.preferences_button.rect().bottomLeft()
            )
        )

    def toggle_theme(self):
        self.dark_mode = not self.dark_mode

        self.opacity_effect = QGraphicsOpacityEffect()
        self.setGraphicsEffect(self.opacity_effect)

        self.fade_animation = QPropertyAnimation(self.opacity_effect, b"opacity")
        self.fade_animation.setDuration(100)
        self.fade_animation.setStartValue(1.0)
        self.fade_animation.setEndValue(0.5)
        self.fade_animation.setEasingCurve(QEasingCurve.OutCubic)

        self.fade_animation.finished.connect(self.apply_theme_and_fade_in)
        self.fade_animation.start()

    def toggle_grid_effects(self):
        """Activa o desactiva la aplicación de efectos (intensidad/desenfoque) en el grid"""
        self.apply_effects_to_grid = not self.apply_effects_to_grid
        self.save_grid_config()  
        
        if self.grid_view_active and self.grid_generated:
        
            if self.pattern is not None:
                self.image_on_grid = self.apply_grid_effects(self.pattern.copy()) if self.apply_effects_to_grid else self.pattern.copy()
                self.display_grid()
        
        status = "activados" if self.apply_effects_to_grid else "desactivados"
        QMessageBox.information(
            self,
            "Efectos en Grid",
            f"Los efectos de intensidad y desenfoque han sido {status} para la vista grid.\n\n"
            f"Los sliders ahora {'aplicarán' if self.apply_effects_to_grid else 'NO aplicarán'} los cambios en tiempo real al grid."
        )

    def clear_segmentation_cache(self):
        """
        Limpia el cache de segmentación, forzando un recálculo en la próxima segmentación.
        Útil para debugging o cuando se sospecha que el cache está desincronizado.
        """
        # Verificar si hay cache activo
        has_cache = (
            hasattr(self, '_last_segmentation_pattern_id') and 
            self._last_segmentation_pattern_id is not None
        )
        
        if not has_cache:
            QMessageBox.information(
                self,
                "Cache Vacío",
                "No hay cache de segmentación activo para limpiar."
            )
            return
        
        # Guardar información del cache antes de limpiar
        old_config = self._last_segmentation_grid_config if hasattr(self, '_last_segmentation_grid_config') else None
        old_bounds = self._last_segmentation_bounds if hasattr(self, '_last_segmentation_bounds') else None
        
        # Limpiar cache
        self._last_segmentation_pattern_id = None
        self._last_segmentation_grid_config = None
        self._last_segmentation_bounds = None
        if hasattr(self, '_last_image_position'):
            self._last_image_position = None
        
        # Limpiar segmentos existentes
        if hasattr(self, 'image_segments'):
            self.image_segments = []
        
        # Log
        self.log_to_console("🗑️ Cache de segmentación limpiado", "WARNING")
        
        # Mensaje informativo
        info_msg = "Cache de segmentación limpiado.\n\n"
        if old_config:
            info_msg += f"Cache anterior:\n  • Configuración: {old_config[0]}×{old_config[1]}\n"
        if old_bounds:
            info_msg += f"  • Bounds: X[{old_bounds['start_x']}-{old_bounds['end_x']}] Y[{old_bounds['start_y']}-{old_bounds['end_y']}]\n"
        info_msg += "\nLa próxima segmentación recalculará desde cero."
        
        QMessageBox.information(
            self,
            "Cache Limpiado",
            info_msg
        )

    def show_scale_config(self):

        dialog = QDialog(self)
        dialog.setWindowTitle("Configuración de Escala de Proyección")
        dialog.setFixedWidth(450)
        dialog.setWindowFlags(dialog.windowFlags() & ~Qt.WindowContextHelpButtonHint)

        if self.dark_mode and sys.platform == "win32":
            try:
                hwnd = int(dialog.winId())
                DWMWA_USE_IMMERSIVE_DARK_MODE = 20
                value = ctypes.c_int(1)
                ctypes.windll.dwmapi.DwmSetWindowAttribute(
                    hwnd,
                    DWMWA_USE_IMMERSIVE_DARK_MODE,
                    ctypes.byref(value),
                    ctypes.sizeof(value),
                )
            except:
                pass

        layout = QVBoxLayout()
        layout.setSpacing(16)
        layout.setContentsMargins(20, 20, 20, 20)

        title_label = QLabel("📐 Escala de Imagen Proyectada")
        title_label.setStyleSheet(
            f"""
            font-size: 16px;
            font-weight: bold;
            color: {'#03DAC6' if self.dark_mode else '#00796B'};
            padding: 10px 0;
        """
        )
        layout.addWidget(title_label)

        mode_group = QButtonGroup(dialog)

        automatic_radio = QRadioButton("🔄 Automático (Ajustar al monitor)")
        automatic_radio.setChecked(self.scale_mode == "automatic")
        mode_group.addButton(automatic_radio, 0)

        manual_radio = QRadioButton("🎚️ Manual (Porcentaje personalizado)")
        manual_radio.setChecked(self.scale_mode == "manual")
        mode_group.addButton(manual_radio, 1)

        layout.addWidget(automatic_radio)
        layout.addWidget(manual_radio)

        manual_container = QWidget()
        manual_layout = QVBoxLayout(manual_container)
        manual_layout.setContentsMargins(20, 10, 0, 10)

        scale_slider_label = QLabel(f"Escala: {self.scale_percentage}%")
        scale_slider_label.setStyleSheet("font-size: 13px;")
        manual_layout.addWidget(scale_slider_label)

        scale_slider = QSlider(Qt.Horizontal)
        scale_slider.setMinimum(0)
        scale_slider.setMaximum(200)
        scale_slider.setValue(self.scale_percentage)
        scale_slider.setEnabled(self.scale_mode == "manual")

        def update_slider_label(value):
            scale_slider_label.setText(f"Escala: {value}%")

        scale_slider.valueChanged.connect(update_slider_label)
        manual_layout.addWidget(scale_slider)

        range_label = QLabel(
            "0% = Sin imagen | 100% = Tamaño original | 200% = Doble tamaño"
        )
        range_label.setStyleSheet("font-size: 11px; color: #888888;")
        manual_layout.addWidget(range_label)

        layout.addWidget(manual_container)

        def on_mode_changed():
            is_manual = manual_radio.isChecked()
            scale_slider.setEnabled(is_manual)

        automatic_radio.toggled.connect(on_mode_changed)
        manual_radio.toggled.connect(on_mode_changed)

        button_layout = QHBoxLayout()
        button_layout.addStretch()

        cancel_button = QPushButton("Cancelar")
        cancel_button.clicked.connect(dialog.reject)
        button_layout.addWidget(cancel_button)

        apply_button = QPushButton("✓ Aplicar")
        apply_button.setDefault(True)
        apply_button.clicked.connect(dialog.accept)
        button_layout.addWidget(apply_button)

        layout.addLayout(button_layout)

        dialog.setLayout(layout)

        dialog.setStyleSheet(
            f"""
            QDialog {{
                background-color: {'#1E1E1E' if self.dark_mode else '#FFFFFF'};
                color: {'#E0E0E0' if self.dark_mode else '#000000'};
            }}
            QRadioButton {{
                color: {'#E0E0E0' if self.dark_mode else '#000000'};
                font-size: 13px;
                padding: 5px;
            }}
            QRadioButton::indicator {{
                width: 18px;
                height: 18px;
            }}
            QPushButton {{
                background-color: {'#2C2C2C' if self.dark_mode else '#F0F0F0'};
                border: 1px solid {'#3E3E3E' if self.dark_mode else '#CCCCCC'};
                border-radius: 6px;
                padding: 8px 16px;
                color: {'#E0E0E0' if self.dark_mode else '#000000'};
                min-width: 80px;
            }}
            QPushButton:hover {{
                background-color: {'#3A3A3A' if self.dark_mode else '#E0E0E0'};
            }}
            QPushButton:default {{
                background-color: #03DAC6;
                color: #000000;
                border: 1px solid #03DAC6;
            }}
            QPushButton:default:hover {{
                background-color: #00BFA5;
            }}
        """
        )

        if dialog.exec_() == QDialog.Accepted:
            old_mode = self.scale_mode
            old_percentage = self.scale_percentage

            self.scale_mode = "automatic" if automatic_radio.isChecked() else "manual"
            self.scale_percentage = scale_slider.value()

            if (
                old_mode != self.scale_mode or old_percentage != self.scale_percentage
            ) and self.projector_active:
                if self.projection_window:
                    self.projection_window._apply_brightness_and_display()

    def update_projection_stats(
        self, original_width, original_height, scaled_width, scaled_height
    ):
        if original_width > 0 and original_height > 0:
            scale_w = (scaled_width / original_width) * 100
            scale_h = (scaled_height / original_height) * 100
            avg_scale = (scale_w + scale_h) / 2
        else:
            avg_scale = 0

        self.current_scale_info = {
            "original": (original_width, original_height),
            "scaled": (scaled_width, scaled_height),
            "percentage": avg_scale,
        }

        self.scale_info_label.setText(f"Escala proyección: {avg_scale:.1f}%")
        self.projected_resolution_label.setText(
            f"Resolución proyectada: {scaled_width}x{scaled_height} px"
        )
        
        self.check_second_monitor()

    def show_exposure_config(self):

        dialog = QDialog(self)
        dialog.setWindowTitle("Configuración de Exposición")
        dialog.setFixedWidth(500)
        dialog.setWindowFlags(dialog.windowFlags() & ~Qt.WindowContextHelpButtonHint)

        if self.dark_mode and sys.platform == "win32":
            try:
                hwnd = int(dialog.winId())
                DWMWA_USE_IMMERSIVE_DARK_MODE = 20
                value = ctypes.c_int(1)
                ctypes.windll.dwmapi.DwmSetWindowAttribute(
                    hwnd,
                    DWMWA_USE_IMMERSIVE_DARK_MODE,
                    ctypes.byref(value),
                    ctypes.sizeof(value),
                )
            except:
                pass

        layout = QVBoxLayout()
        layout.setSpacing(16)
        layout.setContentsMargins(20, 20, 20, 20)

        title_label = QLabel("⏱️ Configuración de Exposición")
        title_label.setStyleSheet(
            f"""
            font-size: 16px;
            font-weight: bold;
            color: {'#03DAC6' if self.dark_mode else '#00796B'};
            padding: 10px 0;
        """
        )
        layout.addWidget(title_label)

        brightness_title = QLabel("💡 Brillo Final al Completar")
        brightness_title.setStyleSheet(
            "font-size: 14px; font-weight: bold; margin-top: 10px;"
        )
        layout.addWidget(brightness_title)

        brightness_group = QButtonGroup(dialog)

        brightness_zero_radio = QRadioButton("🔴 Apagar (0% de brillo)")
        brightness_zero_radio.setChecked(self.final_brightness_mode == "zero")
        brightness_group.addButton(brightness_zero_radio, 0)

        brightness_full_radio = QRadioButton("🟢 Mantener encendido (100% de brillo)")
        brightness_full_radio.setChecked(self.final_brightness_mode == "full")
        brightness_group.addButton(brightness_full_radio, 1)

        layout.addWidget(brightness_zero_radio)
        layout.addWidget(brightness_full_radio)

        brightness_desc = QLabel(
            "Esta configuración controla el brillo de la imagen al finalizar todos los ciclos de exposición o el modo de frecuencia."
        )
        brightness_desc.setStyleSheet(
            "font-size: 11px; color: #888888; margin-left: 20px;"
        )
        brightness_desc.setWordWrap(True)
        layout.addWidget(brightness_desc)

        separator1 = QLabel()
        separator1.setStyleSheet(
            f"background-color: {'#3E3E3E' if self.dark_mode else '#CCCCCC'}; max-height: 1px;"
        )
        separator1.setFixedHeight(1)
        layout.addWidget(separator1)

        delay_title = QLabel("⏸️ Tiempo entre Ciclos")
        delay_title.setStyleSheet(
            "font-size: 14px; font-weight: bold; margin-top: 10px;"
        )
        layout.addWidget(delay_title)

        delay_desc = QLabel(
            "Tiempo de pausa (oscuridad) entre cada ciclo de exposición:"
        )
        delay_desc.setStyleSheet("font-size: 12px; margin-bottom: 5px;")
        layout.addWidget(delay_desc)

        delay_input_layout = QHBoxLayout()

        delay_input = QLineEdit()
        delay_input.setText(
            str(
                self.inter_cycle_delay
                if self.inter_cycle_delay < 1000
                else self.inter_cycle_delay // 1000
            )
        )
        delay_input.setPlaceholderText("0")
        delay_input.setMaximumWidth(100)
        delay_input_layout.addWidget(QLabel("Tiempo:"))
        delay_input_layout.addWidget(delay_input)

        delay_unit_combo = QComboBox()
        delay_unit_combo.addItems(["milisegundos", "segundos"])
        if self.inter_cycle_delay >= 1000:
            delay_unit_combo.setCurrentText("segundos")
        else:
            delay_unit_combo.setCurrentText("milisegundos")
        delay_unit_combo.setMaximumWidth(120)
        delay_input_layout.addWidget(delay_unit_combo)
        delay_input_layout.addStretch()

        layout.addLayout(delay_input_layout)

        delay_note = QLabel(
            "0 = Sin pausa entre ciclos | Durante la pausa, la imagen estará en 0% de brillo"
        )
        delay_note.setStyleSheet("font-size: 11px; color: #888888; margin-left: 20px;")
        delay_note.setWordWrap(True)
        layout.addWidget(delay_note)

        button_layout = QHBoxLayout()
        button_layout.addStretch()

        cancel_button = QPushButton("Cancelar")
        cancel_button.clicked.connect(dialog.reject)
        button_layout.addWidget(cancel_button)

        apply_button = QPushButton("✓ Aplicar")
        apply_button.setDefault(True)
        apply_button.clicked.connect(dialog.accept)
        button_layout.addWidget(apply_button)

        layout.addLayout(button_layout)

        dialog.setLayout(layout)

        dialog.setStyleSheet(
            f"""
            QDialog {{
                background-color: {'#1E1E1E' if self.dark_mode else '#FFFFFF'};
                color: {'#E0E0E0' if self.dark_mode else '#000000'};
            }}
            QRadioButton {{
                color: {'#E0E0E0' if self.dark_mode else '#000000'};
                font-size: 13px;
                padding: 5px;
            }}
            QRadioButton::indicator {{
                width: 18px;
                height: 18px;
            }}
            QLabel {{
                color: {'#E0E0E0' if self.dark_mode else '#000000'};
            }}
            QLineEdit {{
                background-color: {'#2C2C2C' if self.dark_mode else '#FFFFFF'};
                border: 1px solid {'#3E3E3E' if self.dark_mode else '#CCCCCC'};
                border-radius: 6px;
                padding: 6px;
                color: {'#E0E0E0' if self.dark_mode else '#000000'};
            }}
            QComboBox {{
                background-color: {'#2C2C2C' if self.dark_mode else '#F5F5F5'};
                border: 1px solid {'#3E3E3E' if self.dark_mode else '#CCCCCC'};
                border-radius: 6px;
                padding: 6px;
                color: {'#E0E0E0' if self.dark_mode else '#000000'};
            }}
            QPushButton {{
                background-color: {'#2C2C2C' if self.dark_mode else '#F0F0F0'};
                border: 1px solid {'#3E3E3E' if self.dark_mode else '#CCCCCC'};
                border-radius: 6px;
                padding: 8px 16px;
                color: {'#E0E0E0' if self.dark_mode else '#000000'};
                min-width: 80px;
            }}
            QPushButton:hover {{
                background-color: {'#3A3A3A' if self.dark_mode else '#E0E0E0'};
            }}
            QPushButton:default {{
                background-color: #03DAC6;
                color: #000000;
                border: 1px solid #03DAC6;
            }}
            QPushButton:default:hover {{
                background-color: #00BFA5;
            }}
        """
        )

        if dialog.exec_() == QDialog.Accepted:
            self.final_brightness_mode = (
                "zero" if brightness_zero_radio.isChecked() else "full"
            )

            try:
                delay_value = float(delay_input.text())
                if delay_value < 0:
                    delay_value = 0

                if delay_unit_combo.currentText() == "segundos":
                    self.inter_cycle_delay = int(delay_value * 1000)
                else:
                    self.inter_cycle_delay = int(delay_value)
            except ValueError:
                self.inter_cycle_delay = 0

    def resume_next_cycle(self):
        if not self.exposure_active:
            return

        # QSlider requiere int, redondear desde float interno
        self.brightness_slider.setValue(int(round(self.exposure_target_brightness)))
        self.update_brightness()

        self.exposure_start_time = time.time()
        self.exposure_timer.start(int(round(self.exposure_duration * 1000)))
        self.countdown_timer.start()

    def show_grid_color_config(self):
        dialog = QDialog(self)
        dialog.setWindowTitle("Configuración de Grid")
        dialog.setFixedWidth(500)
        dialog.setWindowFlags(dialog.windowFlags() & ~Qt.WindowContextHelpButtonHint)

        if self.dark_mode and sys.platform == "win32":
            try:
                hwnd = int(dialog.winId())
                DWMWA_USE_IMMERSIVE_DARK_MODE = 20
                value = ctypes.c_int(1)
                ctypes.windll.dwmapi.DwmSetWindowAttribute(
                    hwnd, DWMWA_USE_IMMERSIVE_DARK_MODE, ctypes.byref(value), ctypes.sizeof(value)
                )
            except:
                pass

        layout = QVBoxLayout(dialog)
        layout.setSpacing(15)
        layout.setContentsMargins(20, 20, 20, 20)

        # SECCIÓN 1: Color Grid Principal
        title1 = QLabel("🎨 Color del Grid Principal")
        title1.setStyleSheet("font-size: 16px; font-weight: bold; margin-bottom: 10px;")
        layout.addWidget(title1)

        color_layout1 = QHBoxLayout()
        color_label1 = QLabel("Color (hex):")
        self.temp_grid_color_input = QLineEdit()
        self.temp_grid_color_input.setText(self.grid_color)
        self.temp_grid_color_input.setPlaceholderText("#00FF00")
        self.temp_grid_color_input.setMaximumWidth(100)
        
        color_preview1 = QLabel("   ")
        color_preview1.setStyleSheet(f"background-color: {self.grid_color}; border: 1px solid #888; border-radius: 3px;")
        color_preview1.setFixedSize(40, 40)
        
        def update_preview1():
            try:
                color = self.temp_grid_color_input.text()
                if color.startswith('#') and len(color) in [4, 7, 9]:
                    color_preview1.setStyleSheet(f"background-color: {color}; border: 1px solid #888; border-radius: 3px;")
            except:
                pass
        
        self.temp_grid_color_input.textChanged.connect(update_preview1)
        
        color_layout1.addWidget(color_label1)
        color_layout1.addWidget(self.temp_grid_color_input)
        color_layout1.addWidget(color_preview1)
        color_layout1.addStretch()
        layout.addLayout(color_layout1)

        desc_label1 = QLabel("Seleccione un color predefinido:")
        desc_label1.setStyleSheet("font-size: 11px; margin-top: 10px;")
        layout.addWidget(desc_label1)

        colors_grid1 = QHBoxLayout()
        preset_colors = [
            ("#00FF00", "Verde"),
            ("#FF0000", "Rojo"),
            ("#0000FF", "Azul"),
            ("#FFFF00", "Amarillo"),
            ("#FF00FF", "Magenta"),
            ("#00FFFF", "Cian"),
            ("#FFFFFF", "Blanco")
        ]
        
        for color, name in preset_colors:
            color_btn = QPushButton()
            color_btn.setFixedSize(40, 40)
            color_btn.setStyleSheet(f"background-color: {color}; border: 2px solid #888; border-radius: 5px;")
            color_btn.setToolTip(name)
            color_btn.clicked.connect(lambda checked, c=color: (self.temp_grid_color_input.setText(c), update_preview1()))
            colors_grid1.addWidget(color_btn)
        
        layout.addLayout(colors_grid1)

        # SEPARADOR, pal grid
        separator = QLabel("─" * 60)
        separator.setStyleSheet("color: #555; margin: 15px 0;")
        layout.addWidget(separator)

    
        title2 = QLabel("🔍 Color del Grid de Píxeles")
        title2.setStyleSheet("font-size: 16px; font-weight: bold; margin-bottom: 10px;")
        layout.addWidget(title2)

        color_layout2 = QHBoxLayout()
        color_label2 = QLabel("Color (hex):")
        self.temp_pixel_grid_color_input = QLineEdit()
        self.temp_pixel_grid_color_input.setText(self.grid_pixel_color)
        self.temp_pixel_grid_color_input.setPlaceholderText("#FF00FF")
        self.temp_pixel_grid_color_input.setMaximumWidth(100)
        
        color_preview2 = QLabel("   ")
        color_preview2.setStyleSheet(f"background-color: {self.grid_pixel_color}; border: 1px solid #888; border-radius: 3px;")
        color_preview2.setFixedSize(40, 40)
        
        def update_preview2():
            try:
                color = self.temp_pixel_grid_color_input.text()
                if color.startswith('#') and len(color) in [4, 7, 9]:
                    color_preview2.setStyleSheet(f"background-color: {color}; border: 1px solid #888; border-radius: 3px;")
            except:
                pass
        
        self.temp_pixel_grid_color_input.textChanged.connect(update_preview2)
        
        color_layout2.addWidget(color_label2)
        color_layout2.addWidget(self.temp_pixel_grid_color_input)
        color_layout2.addWidget(color_preview2)
        color_layout2.addStretch()
        layout.addLayout(color_layout2)

        desc_label2 = QLabel("Seleccione un color predefinido:")
        desc_label2.setStyleSheet("font-size: 11px; margin-top: 10px;")
        layout.addWidget(desc_label2)

        colors_grid2 = QHBoxLayout()
        
        for color, name in preset_colors:
            color_btn = QPushButton()
            color_btn.setFixedSize(40, 40)
            color_btn.setStyleSheet(f"background-color: {color}; border: 2px solid #888; border-radius: 5px;")
            color_btn.setToolTip(name)
            color_btn.clicked.connect(lambda checked, c=color: (self.temp_pixel_grid_color_input.setText(c), update_preview2()))
            colors_grid2.addWidget(color_btn)
        
        layout.addLayout(colors_grid2)

        
        button_layout = QHBoxLayout()
        ok_button = QPushButton("✓ Aceptar")
        ok_button.clicked.connect(dialog.accept)
        cancel_button = QPushButton("✗ Cancelar")
        cancel_button.clicked.connect(dialog.reject)
        button_layout.addWidget(ok_button)
        button_layout.addWidget(cancel_button)
        layout.addLayout(button_layout)

        dialog_style = f"""
            QDialog {{
                background-color: {'#1E1E1E' if self.dark_mode else '#FFFFFF'};
                color: {'#E0E0E0' if self.dark_mode else '#000000'};
            }}
            QLabel {{
                color: {'#E0E0E0' if self.dark_mode else '#000000'};
            }}
            QLineEdit {{
                background-color: {'#2E2E2E' if self.dark_mode else '#F5F5F5'};
                color: {'#E0E0E0' if self.dark_mode else '#000000'};
                border: 1px solid {'#3E3E3E' if self.dark_mode else '#CCCCCC'};
                border-radius: 4px;
                padding: 5px;
            }}
            QPushButton {{
                background-color: {'#2E2E2E' if self.dark_mode else '#E0E0E0'};
                color: {'#E0E0E0' if self.dark_mode else '#000000'};
                border: none;
                border-radius: 4px;
                padding: 8px 16px;
                font-weight: bold;
            }}
            QPushButton:hover {{
                background-color: #03DAC6;
                color: #121212;
            }}
        """
        dialog.setStyleSheet(dialog_style)

        if dialog.exec_() == QDialog.Accepted:
            try:
           
                new_color = self.temp_grid_color_input.text()
                if new_color.startswith('#') and len(new_color) in [4, 7, 9]:
                    self.grid_color = new_color
                
                new_pixel_color = self.temp_pixel_grid_color_input.text()
                if new_pixel_color.startswith('#') and len(new_pixel_color) in [4, 7, 9]:
                    self.grid_pixel_color = new_pixel_color
                
                self.save_grid_config()
                
                if self.grid_view_active and hasattr(self, 'grid_generated') and self.grid_generated:
                    self.display_grid()
            except:
                pass

    def apply_theme_and_fade_in(self):
        self.apply_theme()

        self.fade_in_animation = QPropertyAnimation(self.opacity_effect, b"opacity")
        self.fade_in_animation.setDuration(100)
        self.fade_in_animation.setStartValue(0.5)
        self.fade_in_animation.setEndValue(1.0)
        self.fade_in_animation.setEasingCurve(QEasingCurve.InCubic)

        self.fade_in_animation.finished.connect(lambda: self.setGraphicsEffect(None))
        self.fade_in_animation.start()

    def log_to_console(self, message, message_type="INFO"):
        """
        Agrega un mensaje a la consola del sistema con timestamp y tipo.
        
        Args:
            message (str): Mensaje a mostrar
            message_type (str): Tipo de mensaje - "INFO", "SUCCESS", "WARNING", "ERROR", "OPTIMIZATION", "SEGMENTATION"
        """
        from datetime import datetime
        
        timestamp = datetime.now().strftime("%H:%M:%S")
        
        # Definir colores según tipo de mensaje (HTML)
        color_map = {
            "INFO": "#BBBBBB",
            "SUCCESS": "#4CAF50",
            "WARNING": "#FFC107",
            "ERROR": "#F44336",
            "OPTIMIZATION": "#03DAC6",
            "SEGMENTATION": "#BB86FC",
        }
        
        color = color_map.get(message_type, "#BBBBBB")
        
        # Formatear mensaje con HTML
        formatted_message = f'<span style="color: #888888;">[{timestamp}]</span> <span style="color: {color}; font-weight: bold;">[{message_type}]</span> <span style="color: #E0E0E0;">{message}</span>'
        
        # Agregar a la consola
        self.system_console.append(formatted_message)
        
        # Scroll automático al final
        scrollbar = self.system_console.verticalScrollBar()
        scrollbar.setValue(scrollbar.maximum())
    
    def clear_console(self):
        """Limpia todos los mensajes de la consola."""
        self.system_console.clear()
        self.log_to_console("Consola limpiada", "INFO")

    def apply_theme(self):
        if self.dark_mode:
            self.apply_dark_theme()
        else:
            self.apply_light_theme()

        self.set_dark_titlebar() if self.dark_mode else self.set_light_titlebar()

        if self.pattern is not None:
            self.simulate_optics()

    def apply_dark_theme(self):
        self.figure.set_facecolor("#121212")
        self.canvas.draw()

        self.setStyleSheet(
            """
            QWidget {
                background-color: #121212;
                color: #f0f0f0;
                font-family: 'Segoe UI', sans-serif;
                font-size: 13px;
            }

            QPushButton {
                background-color: #1E1E1E;
                border: 1px solid #2E2E2E;
                border-radius: 8px;
                padding: 8px 12px;
                color: #E0E0E0;
            }
            QPushButton:hover {
                background-color: #2C2C2C;
                border: 1px solid #3E3E3E;
            }
            QPushButton:pressed {
                background-color: #3A3A3A;
            }
            QPushButton:disabled {
                background-color: #1A1A1A;
                color: #666666;
                border: 1px solid #252525;
            }
            
            QPushButton#modernButton {
                background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                    stop:0 #03DAC6, stop:1 #018786);
                border: none;
                border-radius: 12px;
                padding: 12px 20px;
                color: #121212;
                font-weight: bold;
                font-size: 14px;
                text-transform: uppercase;
                letter-spacing: 1px;
            }
            QPushButton#modernButton:hover {
                background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                    stop:0 #00E5CC, stop:1 #01A299);
            }
            QPushButton#modernButton:pressed {
                background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                    stop:0 #018786, stop:1 #016968);
                padding: 13px 20px 11px 20px;
            }
            
            QPushButton#tabButton {
                background-color: #1E1E1E;
                border: 1px solid #2E2E2E;
                border-radius: 8px;
                padding: 10px 16px;
                color: #A0A0A0;
                font-weight: bold;
                font-size: 12px;
            }
            QPushButton#tabButton:hover {
                background-color: #2C2C2C;
                border: 1px solid #3E3E3E;
                color: #C0C0C0;
            }
            QPushButton#tabButton:checked {
                background-color: #03DAC6;
                border: 1px solid #03DAC6;
                color: #121212;
            }
            QPushButton#tabButton:checked:hover {
                background-color: #00BFA5;
                border: 1px solid #00BFA5;
            }

            QComboBox {
                background-color: #1E1E1E;
                border: 1px solid #2E2E2E;
                border-radius: 8px;
                padding: 8px 12px;
                color: #E0E0E0;
                min-width: 80px;
            }
            QComboBox:hover {
                background-color: #2C2C2C;
                border: 1px solid #3E3E3E;
            }
            QComboBox::drop-down {
                border: none;
                width: 30px;
            }
            QComboBox::down-arrow {
                image: none;
                width: 0;
                height: 0;
                border-left: 6px solid transparent;
                border-right: 6px solid transparent;
                border-top: 8px solid #888888;
                margin-right: 8px;
            }
            QComboBox QAbstractItemView {
                background-color: #1E1E1E;
                border: 1px solid #2E2E2E;
                border-radius: 8px;
                selection-background-color: #03DAC6;
                selection-color: #121212;
                padding: 4px;
                color: #E0E0E0;
            }
            QComboBox QAbstractItemView::item {
                padding: 8px;
                border-radius: 4px;
            }
            QComboBox QAbstractItemView::item:hover {
                background-color: #2C2C2C;
            }
            
            QCheckBox {
                color: #E0E0E0;
                spacing: 8px;
                padding: 6px;
            }
            QCheckBox::indicator {
                width: 20px;
                height: 20px;
                border-radius: 6px;
                border: 2px solid #3E3E3E;
                background-color: #1E1E1E;
            }
            QCheckBox::indicator:hover {
                border: 2px solid #03DAC6;
                background-color: #2C2C2C;
            }
            QCheckBox::indicator:checked {
                background-color: #03DAC6;
                border: 2px solid #03DAC6;
                image: url(none);
            }
            QCheckBox::indicator:checked:hover {
                background-color: #00BFA5;
                border: 2px solid #00BFA5;
            }

            QLabel {
                color: #f0f0f0;
            }
            
            QLabel#sectionTitle,
            QToolButton#sectionTitle {
                color: #03DAC6;
                font-size: 11px;
                font-weight: bold;
                letter-spacing: 1px;
            }

            QLabel#sectionTitle {
                padding: 8px 0px;
                margin-top: 4px;
            }

            QToolButton#sectionTitle {
                background-color: #1A1A1A;
                border: 1px solid #2A2A2A;
                border-radius: 8px;
                padding: 8px 12px;
                text-align: left;
            }

            QToolButton#sectionTitle:hover {
                background-color: #242424;
            }

            QToolButton#sectionTitle:checked {
                background-color: #222222;
            }
            
            QLabel#statLabel {
                color: #B0B0B0;
                font-size: 12px;
                padding: 4px 0px;
            }
            
            QWidget#statsContainer {
                background-color: #1A1A1A;
                border: 1px solid #2A2A2A;
                border-radius: 8px;
                border-left: 3px solid #03DAC6;
            }

            QSlider::groove:horizontal {
                background: #2E2E2E;
                height: 6px;
                border-radius: 3px;
            }

            QSlider::handle:horizontal {
                background: #03DAC6;
                width: 14px;
                border-radius: 7px;
                margin: -4px 0;
            }

            QSlider::handle:horizontal:hover {
                background: #00BFA5;
            }

            QTreeWidget#fileTree {
                background-color: #1A1A1A;
                border: 1px solid #2A2A2A;
                border-radius: 8px;
                padding: 8px;
            }

            QTreeWidget::item {
                padding: 8px;
                min-height: 64px;
                border-radius: 6px;
                margin: 3px 0px;
            }

            QTreeWidget::item:hover {
                background-color: #252525;
            }

            QTreeWidget::item:selected {
                background-color: #03DAC6;
                color: #121212;
            }
            
            QScrollBar:vertical {
                background-color: transparent;
                width: 10px;
                margin: 0px;
            }
            
            QScrollBar::handle:vertical {
                background-color: #3A3A3A;
                border-radius: 5px;
                min-height: 40px;
            }
            
            QScrollBar::handle:vertical:hover {
                background-color: #4A4A4A;
            }
            
            QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {
                height: 0px;
            }
            
            QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical {
                background: transparent;
            }
            
            QScrollBar:horizontal {
                background-color: transparent;
                height: 10px;
                margin: 0px;
            }
            
            QScrollBar::handle:horizontal {
                background-color: #3A3A3A;
                border-radius: 5px;
                min-width: 40px;
            }
            
            QScrollBar::handle:horizontal:hover {
                background-color: #4A4A4A;
            }
            
            QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal {
                width: 0px;
            }
            
            QScrollBar::add-page:horizontal, QScrollBar::sub-page:horizontal {
                background: transparent;
            }
            
            QScrollArea {
                background-color: transparent;
                border: none;
            }
            
            QTextEdit {
                background-color: #1A1A1A;
                border: 1px solid #2A2A2A;
                border-radius: 8px;
                padding: 8px;
                color: #E0E0E0;
                font-family: 'Consolas', 'Courier New', monospace;
                font-size: 12px;
                selection-background-color: #03DAC6;
                selection-color: #121212;
            }
            
            QTextEdit:focus {
                border: 1px solid #03DAC6;
            }
            
            QTabWidget {
                background-color: #121212;
            }
            
            QTabWidget::pane {
                background-color: #121212;
                border: 1px solid #2A2A2A;
                border-radius: 8px;
                padding: 10px;
            }
            
            QTabWidget::tab-bar {
                alignment: left;
            }
            
            QTabBar::tab {
                background-color: #1E1E1E;
                border: 1px solid #2E2E2E;
                border-bottom: none;
                border-top-left-radius: 8px;
                border-top-right-radius: 8px;
                padding: 12px 30px;
                color: #A0A0A0;
                font-weight: bold;
                font-size: 12px;
                margin-right: 4px;
                min-width: 150px;
            }
            
            QTabBar::tab:selected {
                background-color: #121212;
                border: 1px solid #03DAC6;
                border-bottom: 1px solid #121212;
                color: #03DAC6;
            }
            
            QTabBar::tab:hover:!selected {
                background-color: #2C2C2C;
                border: 1px solid #3E3E3E;
                color: #C0C0C0;
            }
        """
        )

    def apply_light_theme(self):
        self.figure.set_facecolor("#FFFFFF")
        self.canvas.draw()

        self.setStyleSheet(
            """
            QWidget {
                background-color: #FFFFFF;
                color: #000000;
                font-family: 'Segoe UI', sans-serif;
                font-size: 13px;
            }

            QPushButton {
                background-color: #F5F5F5;
                border: 1px solid #CCCCCC;
                border-radius: 8px;
                padding: 8px 12px;
                color: #000000;
            }
            QPushButton:hover {
                background-color: #E0E0E0;
                border: 1px solid #BBBBBB;
            }
            QPushButton:pressed {
                background-color: #D0D0D0;
            }
            QPushButton:disabled {
                background-color: #F0F0F0;
                color: #AAAAAA;
                border: 1px solid #DDDDDD;
            }
            
            QPushButton#modernButton {
                background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                    stop:0 #03DAC6, stop:1 #018786);
                border: none;
                border-radius: 12px;
                padding: 12px 20px;
                color: #000000;
                font-weight: bold;
                font-size: 14px;
                text-transform: uppercase;
                letter-spacing: 1px;
            }
            QPushButton#modernButton:hover {
                background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                    stop:0 #00E5CC, stop:1 #01A299);
            }
            QPushButton#modernButton:pressed {
                background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                    stop:0 #018786, stop:1 #016968);
                padding: 13px 20px 11px 20px;
            }
            
            QPushButton#tabButton {
                background-color: #F5F5F5;
                border: 1px solid #CCCCCC;
                border-radius: 8px;
                padding: 10px 16px;
                color: #666666;
                font-weight: bold;
                font-size: 12px;
            }
            QPushButton#tabButton:hover {
                background-color: #E0E0E0;
                border: 1px solid #BBBBBB;
                color: #444444;
            }
            QPushButton#tabButton:checked {
                background-color: #03DAC6;
                border: 1px solid #03DAC6;
                color: #000000;
            }
            QPushButton#tabButton:checked:hover {
                background-color: #00BFA5;
                border: 1px solid #00BFA5;
            }

            QComboBox {
                background-color: #F5F5F5;
                border: 1px solid #CCCCCC;
                border-radius: 8px;
                padding: 8px 12px;
                color: #000000;
                min-width: 80px;
            }
            QComboBox:hover {
                background-color: #E0E0E0;
                border: 1px solid #BBBBBB;
            }
            QComboBox::drop-down {
                border: none;
                width: 30px;
            }
            QComboBox::down-arrow {
                image: none;
                width: 0;
                height: 0;
                border-left: 6px solid transparent;
                border-right: 6px solid transparent;
                border-top: 8px solid #666666;
                margin-right: 8px;
            }
            QComboBox QAbstractItemView {
                background-color: #FFFFFF;
                border: 1px solid #CCCCCC;
                border-radius: 8px;
                selection-background-color: #03DAC6;
                selection-color: #000000;
                padding: 4px;
                color: #000000;
            }
            QComboBox QAbstractItemView::item {
                padding: 8px;
                border-radius: 4px;
            }
            QComboBox QAbstractItemView::item:hover {
                background-color: #F0F0F0;
            }
            
            QCheckBox {
                color: #000000;
                spacing: 8px;
                padding: 6px;
            }
            QCheckBox::indicator {
                width: 20px;
                height: 20px;
                border-radius: 6px;
                border: 2px solid #CCCCCC;
                background-color: #FFFFFF;
            }
            QCheckBox::indicator:hover {
                border: 2px solid #03DAC6;
                background-color: #F5F5F5;
            }
            QCheckBox::indicator:checked {
                background-color: #03DAC6;
                border: 2px solid #03DAC6;
                image: url(none);
            }
            QCheckBox::indicator:checked:hover {
                background-color: #00BFA5;
                border: 2px solid #00BFA5;
            }

            QLabel {
                color: #000000;
            }
            
            QLabel#sectionTitle,
            QToolButton#sectionTitle {
                color: #03DAC6;
                font-size: 11px;
                font-weight: bold;
                letter-spacing: 1px;
            }

            QLabel#sectionTitle {
                padding: 8px 0px;
                margin-top: 4px;
            }

            QToolButton#sectionTitle {
                background-color: #F8F8F8;
                border: 1px solid #E0E0E0;
                border-radius: 8px;
                padding: 8px 12px;
                text-align: left;
            }

            QToolButton#sectionTitle:hover {
                background-color: #F0F0F0;
            }

            QToolButton#sectionTitle:checked {
                background-color: #EAEAEA;
            }
            
            QLabel#statLabel {
                color: #555555;
                font-size: 12px;
                padding: 4px 0px;
            }
            
            QWidget#statsContainer {
                background-color: #F8F8F8;
                border: 1px solid #E0E0E0;
                border-radius: 8px;
                border-left: 3px solid #03DAC6;
            }

            QSlider::groove:horizontal {
                background: #CCCCCC;
                height: 6px;
                border-radius: 3px;
            }

            QSlider::handle:horizontal {
                background: #03DAC6;
                width: 14px;
                border-radius: 7px;
                margin: -4px 0;
            }

            QSlider::handle:horizontal:hover {
                background: #00BFA5;
            }

            QTreeWidget#fileTree {
                background-color: #F8F8F8;
                border: 1px solid #E0E0E0;
                border-radius: 8px;
                padding: 8px;
            }

            QTreeWidget::item {
                padding: 6px;
                min-height: 85px;
                border-radius: 6px;
                margin: 2px 0px;
            }

            QTreeWidget::item:hover {
                background-color: #E8E8E8;
            }

            QTreeWidget::item:selected {
                background-color: #03DAC6;
                color: #000000;
            }
            
            QScrollBar:vertical {
                background-color: transparent;
                width: 10px;
                margin: 0px;
            }
            
            QScrollBar::handle:vertical {
                background-color: #BEBEBE;
                border-radius: 5px;
                min-height: 40px;
            }
            
            QScrollBar::handle:vertical:hover {
                background-color: #A0A0A0;
            }
            
            QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {
                height: 0px;
            }
            
            QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical {
                background: transparent;
            }
            
            QScrollBar:horizontal {
                background-color: transparent;
                height: 10px;
                margin: 0px;
            }
            
            QScrollBar::handle:horizontal {
                background-color: #BEBEBE;
                border-radius: 5px;
                min-width: 40px;
            }
            
            QScrollBar::handle:horizontal:hover {
                background-color: #A0A0A0;
            }
            
            QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal {
                width: 0px;
            }
            
            QScrollBar::add-page:horizontal, QScrollBar::sub-page:horizontal {
                background: transparent;
            }
            
            QScrollArea {
                background-color: transparent;
                border: none;
            }
            
            QTextEdit {
                background-color: #FAFAFA;
                border: 1px solid #DDDDDD;
                border-radius: 8px;
                padding: 8px;
                color: #000000;
                font-family: 'Consolas', 'Courier New', monospace;
                font-size: 12px;
                selection-background-color: #03DAC6;
                selection-color: #000000;
            }
            
            QTextEdit:focus {
                border: 1px solid #03DAC6;
            }
            
            QTabWidget {
                background-color: #FFFFFF;
            }
            
            QTabWidget::pane {
                background-color: #FFFFFF;
                border: 1px solid #CCCCCC;
                border-radius: 8px;
                padding: 10px;
            }
            
            QTabWidget::tab-bar {
                alignment: left;
            }
            
            QTabBar::tab {
                background-color: #F5F5F5;
                border: 1px solid #CCCCCC;
                border-bottom: none;
                border-top-left-radius: 8px;
                border-top-right-radius: 8px;
                padding: 12px 30px;
                color: #666666;
                font-weight: bold;
                font-size: 12px;
                margin-right: 4px;
                min-width: 150px;
            }
            
            QTabBar::tab:selected {
                background-color: #FFFFFF;
                border: 1px solid #03DAC6;
                border-bottom: 1px solid #FFFFFF;
                color: #018786;
            }
            
            QTabBar::tab:hover:!selected {
                background-color: #E0E0E0;
                border: 1px solid #BBBBBB;
                color: #444444;
            }
        """
        )

    def set_light_titlebar(self):
        try:
            if sys.platform == "win32":
                hwnd = int(self.winId())
                DWMWA_USE_IMMERSIVE_DARK_MODE = 20
                value = ctypes.c_int(0)
                ctypes.windll.dwmapi.DwmSetWindowAttribute(
                    hwnd,
                    DWMWA_USE_IMMERSIVE_DARK_MODE,
                    ctypes.byref(value),
                    ctypes.sizeof(value),
                )
        except Exception as e:
            print(f"No se pudo aplicar barra de título clara: {e}")

    def simulate_optics(self):
        psf_result = gaussian_filter(self.pattern, sigma=self.sigma)
        intensity_percentage = (psf_result / psf_result.max()) * 100
        self.last_intensity = intensity_percentage
        self.plot_results(self.pattern, psf_result, intensity_percentage)
        self.update_info_panel(intensity_percentage)

        # Si estamos en modo "Imagen Completa" (segmentation_mode == 3) y hay proyección activa,
        # actualizar la proyección con la imagen completa
        if self.projector_active and self.projection_window is not None and self.segmentation_mode == 3:
             # Aplicar efectos si corresponde
             processed = self._apply_effects_to_segment(self.pattern)
             self.projection_window.update_segment(processed)

    def plot_results(self, pattern, simulated, intensity_percentage):
        self.figure.clear()

        bg_color = "#121212" if self.dark_mode else "#FFFFFF"
        text_color = "white" if self.dark_mode else "black"

        ax1 = self.figure.add_subplot(1, 2, 1)
        ax2 = self.figure.add_subplot(1, 2, 2)

        for ax in [ax1, ax2]:
            ax.set_facecolor(bg_color)
            ax.tick_params(colors=text_color)
            ax.xaxis.label.set_color(text_color)
            ax.yaxis.label.set_color(text_color)
            for spine in ax.spines.values():
                spine.set_edgecolor(text_color)

        # Aplicar inversión si está activa
        display_pattern = pattern
        if self.invert_projection:
            display_pattern = 1.0 - pattern

        ax1.imshow(display_pattern, cmap="gray")
        ax1.set_xlabel("X")
        ax1.set_ylabel("Y")

        ax2.imshow(intensity_percentage, cmap="inferno")
        ax2.set_xlabel("X")
        ax2.set_ylabel("Y")

        self.canvas.draw()

    def update_info_panel(self, intensity_map):
        if intensity_map is not None:
            h, w = intensity_map.shape
            self.resolution_label.setText(f"Resolución: {w} × {h}")
            self.min_label.setText(f"Intensidad mínima: {intensity_map.min():.2f}")
            self.avg_label.setText(f"Intensidad promedio: {intensity_map.mean():.2f}")
            self.max_label.setText(f"Intensidad máxima: {intensity_map.max():.2f}")
        
        self.check_second_monitor()


if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = LithographySimulator()
    window.show()
    sys.exit(app.exec_())
