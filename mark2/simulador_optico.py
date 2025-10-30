import sys
import cv2
import os
import json
import time
from scipy.ndimage import gaussian_filter
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
)
from PyQt5.QtCore import Qt, QPropertyAnimation, QEasingCurve, QSize, QTimer
from PyQt5.QtGui import QDragEnterEvent, QDropEvent, QIcon, QPixmap, QImage
from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg as FigureCanvas
from matplotlib.figure import Figure
import numpy as np
import ctypes


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
        self.screen_geometry = None

        layout = QVBoxLayout()
        layout.setContentsMargins(0, 0, 0, 0)

        self.image_label = QLabel()
        self.image_label.setAlignment(Qt.AlignCenter)
        self.image_label.setScaledContents(False)

        self.update_image(image_array)

        layout.addWidget(self.image_label)
        self.setLayout(layout)

        self.setFocusPolicy(Qt.StrongFocus)

    def update_image(self, image_array):
        self.original_image = image_array.copy()

        self._apply_brightness_and_display()

    def set_brightness(self, brightness_percent):
        self.brightness_factor = brightness_percent / 100.0
        self._apply_brightness_and_display()

    def _apply_brightness_and_display(self):
        if self.original_image is None:
            return

        adjusted_image = self.original_image * self.brightness_factor

        normalized = adjusted_image / 100.0
        adjusted_image_uint8 = (normalized * 255).astype(np.uint8)

        height, width = adjusted_image_uint8.shape
        bytes_per_line = width

        q_image = QImage(
            adjusted_image_uint8.data,
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
        self.setGeometry(100, 100, 1600, 700)
        self.setAcceptDrops(True)

        icon_path = os.path.join(os.path.dirname(__file__), "icono.ico")
        if os.path.exists(icon_path):
            self.setWindowIcon(QIcon(icon_path))

        self.set_dark_titlebar()

        self.pattern = None
        self.sigma = 2.0
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

        self.exposure_timer = QTimer()
        self.exposure_timer.timeout.connect(self.stop_timed_exposure)
        self.exposure_active = False
        self.exposure_start_time = 0
        self.exposure_duration = 0
        self.exposure_cycles_completed = 0
        self.exposure_target_brightness = 0

        self.countdown_timer = QTimer()
        self.countdown_timer.timeout.connect(self.update_countdown)
        self.countdown_timer.setInterval(100)

        self.inter_cycle_timer = QTimer()
        self.inter_cycle_timer.setSingleShot(True)
        self.inter_cycle_timer.timeout.connect(self.resume_next_cycle)

        self.frequency_mode = False
        self.frequency_timer = QTimer()
        self.frequency_timer.timeout.connect(self.stop_frequency_mode)
        self.frequency_start_time = 0
        self.frequency_duration = 0

        self.init_cache_system()

        main_layout = QVBoxLayout()
        control_layout = QHBoxLayout()

        self.load_button = QPushButton("📂 Cargar patrón")
        self.load_button.clicked.connect(self.load_pattern)

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

        self.save_button = QPushButton("💾 Guardar imagen")
        self.save_button.clicked.connect(self.save_image)

        self.format_combo = QComboBox()
        self.format_combo.addItems(["PNG", "JPG", "BMP", "TIFF"])

        control_layout.addWidget(self.load_button)
        control_layout.addWidget(self.preferences_button)
        control_layout.addWidget(self.projector_button)
        control_layout.addWidget(self.sigma_label)
        control_layout.addWidget(self.sigma_slider)
        control_layout.addWidget(self.brightness_label)
        control_layout.addWidget(self.brightness_slider)
        control_layout.addWidget(self.save_button)
        control_layout.addWidget(QLabel("Formato:"))
        control_layout.addWidget(self.format_combo)

        self.figure = Figure(facecolor="#121212")
        self.canvas = FigureCanvas(self.figure)

        self.info_layout = QVBoxLayout()
        self.info_layout.setSpacing(12)

        stats_title = QLabel("📊 DATA:")
        stats_title.setObjectName("sectionTitle")
        self.info_layout.addWidget(stats_title)

        stats_container = QWidget()
        stats_container.setObjectName("statsContainer")
        stats_layout = QVBoxLayout(stats_container)
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
        self.projected_resolution_label = QLabel("Resolución proyectada: -")
        self.projected_resolution_label.setObjectName("statLabel")

        stats_layout.addWidget(self.resolution_label)
        stats_layout.addWidget(self.min_label)
        stats_layout.addWidget(self.avg_label)
        stats_layout.addWidget(self.max_label)
        stats_layout.addWidget(self.scale_info_label)
        stats_layout.addWidget(self.projected_resolution_label)

        self.info_layout.addWidget(stats_container)

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

        self.exposure_container = QWidget()
        self.exposure_container.setObjectName("statsContainer")
        exposure_layout = QVBoxLayout(self.exposure_container)
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
        exposure_layout.addWidget(self.exposure_button)
        exposure_layout.addWidget(self.stop_exposure_button)
        exposure_layout.addWidget(self.exposure_status_label)

        self.info_layout.addWidget(self.exposure_container)

        self.frequency_container = QWidget()
        self.frequency_container.setObjectName("statsContainer")
        frequency_main_layout = QVBoxLayout(self.frequency_container)
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

        self.info_layout.addWidget(self.frequency_container)
        self.frequency_container.setVisible(False)

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
        scroll_area.setMinimumWidth(320)
        scroll_area.setMaximumWidth(400)

        canvas_layout = QHBoxLayout()
        canvas_layout.addWidget(self.canvas, stretch=3)
        canvas_layout.addWidget(scroll_area, stretch=1)

        main_layout.addLayout(control_layout)
        main_layout.addLayout(canvas_layout)
        self.setLayout(main_layout)

        self.apply_theme()

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

    def showEvent(self, event):
        super().showEvent(event)
        self.set_dark_titlebar()

    def closeEvent(self, event):
        if self.projection_window is not None:
            self.projection_window.close()
            self.projection_window = None
        super().closeEvent(event)

    def check_second_monitor(self):
        screens = QApplication.screens()
        return len(screens) > 1

    def show_exposure_section(self):
        self.exposure_container.setVisible(True)
        self.frequency_container.setVisible(False)
        self.exposure_tab_button.setChecked(True)
        self.frequency_tab_button.setChecked(False)

    def show_frequency_section(self):
        self.exposure_container.setVisible(False)
        self.frequency_container.setVisible(True)
        self.exposure_tab_button.setChecked(False)
        self.frequency_tab_button.setChecked(True)

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
            self.simulate_optics()
            self.projector_button.setVisible(True)
            self.update_projector_button()

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
            if hasattr(self, "last_intensity") and self.last_intensity is not None:
                self.projection_window = ProjectionWindow(self.last_intensity, self)
                self.projection_window.show_on_secondary_monitor()
                self.brightness_slider.setVisible(True)
                self.brightness_label.setVisible(True)
                self.exposure_button.setVisible(True)
                self.frequency_button.setVisible(True)
                self.update_brightness()
            else:
                QMessageBox.warning(
                    self, "Advertencia", "No hay imagen procesada para proyectar"
                )
                self.projector_active = False
        else:
            if self.exposure_active:
                self.force_stop_exposure()

            if self.frequency_mode:
                self.force_stop_frequency()

            if self.projection_window is not None:
                self.projection_window.close()
                self.projection_window = None
            self.brightness_slider.setVisible(False)
            self.brightness_label.setVisible(False)
            self.exposure_button.setVisible(False)
            self.stop_exposure_button.setVisible(False)
            self.frequency_button.setVisible(False)
            self.stop_frequency_button.setVisible(False)

        self.update_projector_button()

    def on_projection_closed(self):

        if self.exposure_active:
            self.force_stop_exposure()

        if self.frequency_mode:
            self.force_stop_frequency()

        self.projector_active = False
        self.projection_window = None
        self.brightness_slider.setVisible(False)
        self.brightness_label.setVisible(False)
        self.exposure_button.setVisible(False)
        self.stop_exposure_button.setVisible(False)
        self.frequency_button.setVisible(False)
        self.stop_frequency_button.setVisible(False)
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

    def update_sigma(self):
        self.sigma = self.sigma_slider.value()
        self.sigma_label.setText(f"Sigma (Desenfoque): {self.sigma:.1f}")
        if self.pattern is not None:
            self.simulate_optics()

    def update_brightness(self):
        self.brightness = self.brightness_slider.value()
        self.brightness_label.setText(f"Brillo Proyección: {self.brightness}%")
        if self.projector_active and self.projection_window is not None:
            self.projection_window.set_brightness(self.brightness)

    def start_timed_exposure(self):
        if not self.projector_active:
            QMessageBox.warning(
                self,
                "Proyección inactiva",
                "Debe activar la proyección antes de iniciar la exposición.",
            )
            return

        try:
            exposure_time = float(self.exposure_time_input.text())
            if exposure_time <= 0:
                raise ValueError("El tiempo debe ser mayor a 0")
        except ValueError:
            QMessageBox.warning(
                self,
                "Tiempo inválido",
                "Por favor ingrese un tiempo de exposición válido (en segundos).\n\n"
                "Ejemplo: 5 o 10.5",
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
                "Por favor ingrese una intensidad válida (0-100).\n\n"
                "Ejemplo: 50, 80 o 100",
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

        self.exposure_duration = exposure_time
        self.exposure_cycles_total = cycles
        self.exposure_cycles_completed = 0
        self.exposure_start_time = time.time()
        self.exposure_target_brightness = intensity

        self.brightness_slider.setValue(intensity)
        self.update_brightness()

        self.exposure_active = True
        self.exposure_button.setVisible(False)
        self.stop_exposure_button.setVisible(True)

        self.exposure_time_input.setEnabled(False)
        self.exposure_intensity_input.setEnabled(False)
        self.exposure_cycles_input.setEnabled(False)
        self.brightness_slider.setEnabled(False)

        self.exposure_timer.start(int(exposure_time * 1000))
        self.countdown_timer.start()

        self.update_countdown()

    def update_countdown(self):

        if not self.exposure_active:
            return

        elapsed = time.time() - self.exposure_start_time
        remaining = max(0, self.exposure_duration - elapsed)

        self.exposure_status_label.setText(
            f"⏱️ Ciclo {self.exposure_cycles_completed + 1}/{self.exposure_cycles_total} | "
            f"Tiempo restante: {remaining:.1f}s"
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

        if not self.projector_active:
            QMessageBox.warning(
                self,
                "Proyección inactiva",
                "Debe activar la proyección antes de iniciar el modo de frecuencia.",
            )
            return

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

        self.brightness_slider.setValue(self.exposure_target_brightness)
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

        self.brightness_slider.setValue(self.exposure_target_brightness)
        self.update_brightness()

        self.exposure_start_time = time.time()
        self.exposure_timer.start(int(self.exposure_duration * 1000))
        self.countdown_timer.start()

    def apply_theme_and_fade_in(self):
        self.apply_theme()

        self.fade_in_animation = QPropertyAnimation(self.opacity_effect, b"opacity")
        self.fade_in_animation.setDuration(100)
        self.fade_in_animation.setStartValue(0.5)
        self.fade_in_animation.setEndValue(1.0)
        self.fade_in_animation.setEasingCurve(QEasingCurve.InCubic)

        self.fade_in_animation.finished.connect(lambda: self.setGraphicsEffect(None))
        self.fade_in_animation.start()

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

            QLabel {
                color: #f0f0f0;
            }
            
            QLabel#sectionTitle {
                color: #03DAC6;
                font-size: 11px;
                font-weight: bold;
                letter-spacing: 1px;
                padding: 8px 0px;
                margin-top: 4px;
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

            QLabel {
                color: #000000;
            }
            
            QLabel#sectionTitle {
                color: #03DAC6;
                font-size: 11px;
                font-weight: bold;
                letter-spacing: 1px;
                padding: 8px 0px;
                margin-top: 4px;
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

        if self.projector_active and self.projection_window is not None:
            self.projection_window.update_image(intensity_percentage)

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

        ax1.imshow(pattern, cmap="gray")
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


if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = LithographySimulator()
    window.show()
    sys.exit(app.exec_())
