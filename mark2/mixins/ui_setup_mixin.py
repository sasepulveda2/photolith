"""
Mixin de configuracion de interfaz de usuario.

Contiene el metodo _build_ui() que construye toda la interfaz grafica:
toolbar, sidebar, canvas, secciones colapsables, controles de exposicion,
segmentacion, calibracion y consola de log.
"""
import os
from PyQt5.QtWidgets import (
    QApplication, QVBoxLayout, QHBoxLayout, QPushButton, QLabel, QSlider,
    QComboBox, QCheckBox, QLineEdit, QScrollArea, QWidget,
    QSpinBox, QDoubleSpinBox, QProgressBar, QTextEdit,
    QTreeWidget,
)
from PyQt5.QtCore import Qt, QSize, QTimer
from PyQt5.QtGui import QIcon
from matplotlib.backends.backend_qt5agg import (
    FigureCanvasQTAgg as FigureCanvas,
    NavigationToolbar2QT as NavigationToolbar,
)
from matplotlib.figure import Figure
from UI.collapsible_section import CollapsibleSection


class UISetupMixin:
    """Construye la interfaz grafica completa del simulador."""

    def _build_ui(self) -> None:
        """
        Construye todos los widgets, layouts, secciones y conexiones de senales.
        Llamado desde __init__ despues de _init_state().
        """
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

        self.canvas.mpl_connect("button_press_event", self.on_mouse_press)
        self.canvas.mpl_connect("button_release_event", self.on_mouse_release)
        self.canvas.mpl_connect("motion_notify_event", self.on_mouse_move)
        self.canvas.mpl_connect("scroll_event", self.on_mouse_scroll)

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
        if hasattr(self, "apply_attenuation_to_grid"):
            self.calibration_status_label.setText(
                f"Calibración: {'✓ Activa' if self.apply_attenuation_to_grid else 'Inactiva'}"
            )

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
        self.binary_status_label = QLabel(
            f"Estado: {'✓ Activo' if self.binary_mode_enabled else '✗ Inactivo'}"
        )
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
        self.binary_threshold_slider.valueChanged.connect(
            self.update_binary_threshold_from_slider
        )

        self.binary_threshold_input = QLineEdit(str(self.binary_threshold))
        self.binary_threshold_input.setMaximumWidth(50)
        self.binary_threshold_input.returnPressed.connect(
            self.update_binary_threshold_from_input
        )

        threshold_layout.addWidget(self.binary_threshold_slider)
        threshold_layout.addWidget(self.binary_threshold_input)
        threshold_layout.addWidget(QLabel("%"))
        binary_layout.addLayout(threshold_layout)

        self.binary_section.setContentWidget(binary_content)
        self.info_layout.addWidget(self.binary_section)

        self.check_second_monitor()

        self.grid_stats_section = CollapsibleSection(
            "📏 ESTADÍSTICAS GRID", self, expanded=False
        )
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
        self.basler_sidebar_section = CollapsibleSection(
            "🎥 CÁMARA BASLER", self, expanded=True
        )
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
        self.basler_sidebar_exposure_slider.valueChanged.connect(
            self.update_basler_exposure_from_slider
        )
        self.basler_sidebar_exposure_input = QLineEdit("10000")
        self.basler_sidebar_exposure_input.setMaximumWidth(70)
        self.basler_sidebar_exposure_input.returnPressed.connect(
            self.update_basler_exposure_from_input
        )
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
        self.basler_sidebar_gain_slider.setMaximum(
            240
        )  # 24.0 dB máximo (x10 para precisión)
        self.basler_sidebar_gain_slider.setValue(0)
        self.basler_sidebar_gain_slider.valueChanged.connect(
            self.update_basler_gain_from_slider
        )
        self.basler_sidebar_gain_input = QLineEdit("0.0")
        self.basler_sidebar_gain_input.setMaximumWidth(70)
        self.basler_sidebar_gain_input.returnPressed.connect(
            self.update_basler_gain_from_input
        )
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
        self.basler_sidebar_gamma_slider.valueChanged.connect(
            self.update_basler_gamma_from_slider
        )
        self.basler_sidebar_gamma_input = QLineEdit("1.0")
        self.basler_sidebar_gamma_input.setMaximumWidth(70)
        self.basler_sidebar_gamma_input.returnPressed.connect(
            self.update_basler_gamma_from_input
        )
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
        self.basler_sidebar_black_slider.valueChanged.connect(
            self.update_basler_black_from_slider
        )
        self.basler_sidebar_black_input = QLineEdit("0")
        self.basler_sidebar_black_input.setMaximumWidth(70)
        self.basler_sidebar_black_input.returnPressed.connect(
            self.update_basler_black_from_input
        )
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

        self.image_coords_section = CollapsibleSection(
            "🖼️ IMAGEN EN GRID", self, expanded=False
        )
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

        self.grid_config_section = CollapsibleSection(
            "📏 CONFIGURACIÓN GRID", self, expanded=False
        )
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
        self.segmentation_section = CollapsibleSection(
            "✂️ SEGMENTACIÓN DE IMAGEN", self, expanded=False
        )
        segmentation_content = QWidget()
        segmentation_content.setObjectName("statsContainer")
        segmentation_layout = QVBoxLayout(segmentation_content)
        segmentation_layout.setContentsMargins(12, 12, 12, 12)
        segmentation_layout.setSpacing(10)

        # Descripción
        seg_desc = QLabel(
            "División de la imagen en segmentos/subcampos para exposición secuencial en stepper litográfico"
        )
        seg_desc.setWordWrap(True)
        seg_desc.setStyleSheet("font-size: 10px; color: #888888;")
        segmentation_layout.addWidget(seg_desc)

        # Modo de segmentación
        seg_mode_layout = QHBoxLayout()
        seg_mode_label = QLabel("Modo:")
        seg_mode_label.setObjectName("statLabel")
        self.segmentation_mode_combo = QComboBox()
        self.segmentation_mode_combo.addItems(
            [
                "Automático (usar grid)",
                "Manual (especificar)",
                "Por tamaño de campo",
                "Imagen Completa (sin slice)",
            ]
        )
        self.segmentation_mode_combo.currentIndexChanged.connect(
            self.update_segmentation_mode
        )
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
        self.mirror_horizontal_checkbox.stateChanged.connect(
            self.update_image_transform
        )
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
        self.apply_segmentation_button.setToolTip(
            "Divide la imagen según la configuración de segmentos"
        )
        segmentation_layout.addWidget(self.apply_segmentation_button)

        # Checkbox para mostrar overlay de segmentos
        self.show_segments_overlay_checkbox = QCheckBox(
            "Mostrar overlay de segmentos en grid"
        )
        self.show_segments_overlay_checkbox.setChecked(False)
        self.show_segments_overlay_checkbox.setObjectName("statLabel")
        self.show_segments_overlay_checkbox.stateChanged.connect(
            self.toggle_segments_overlay
        )
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
        self.project_image_button.setToolTip(
            "Proyecta la imagen completa en el monitor secundario"
        )

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
        self.projection_control_section = CollapsibleSection(
            "🎬 CONTROL DE PROYECCIÓN", self, expanded=False
        )
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

        downscale_desc = QLabel(
            "Reduce la imagen proyectada para lograr la resolución final deseada en el sustrato (típico de steppers)"
        )
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
        self.downscale_factor_spin.setToolTip(
            "Factor de reducción: <1 reduce tamaño, >1 aumenta tamaño"
        )
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

        sequence_desc = QLabel(
            "Gestión de secuencias de movimiento (stage/platina) y activación de proyección (shutter)"
        )
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
        self.sequence_start_button.setToolTip(
            "Inicia la secuencia de proyección con los segmentos del grid"
        )

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
        self.auto_shutter_checkbox.setToolTip(
            "Activa/desactiva la proyección automáticamente en cada segmento"
        )
        sequence_options_layout.addWidget(self.auto_shutter_checkbox)

        self.auto_movement_checkbox = QCheckBox("Movimiento automático de stage")
        self.auto_movement_checkbox.setChecked(True)
        self.auto_movement_checkbox.setObjectName("statLabel")
        self.auto_movement_checkbox.setToolTip(
            "Mueve la platina automáticamente entre segmentos"
        )
        sequence_options_layout.addWidget(self.auto_movement_checkbox)

        sequence_layout.addLayout(sequence_options_layout)

        # Tiempo de exposición (imagen visible)
        exposure_time_layout = QHBoxLayout()
        exposure_time_label = QLabel("⏱️ Tiempo de exposición:")
        exposure_time_label.setObjectName("statLabel")
        self.exposure_time_spin = QDoubleSpinBox()
        self.exposure_time_spin.setMinimum(0.001)  # Mínimo 1ms
        self.exposure_time_spin.setMaximum(60.0)  # Máximo 60 segundos
        self.exposure_time_spin.setValue(0.5)
        self.exposure_time_spin.setSingleStep(0.1)
        self.exposure_time_spin.setDecimals(3)
        self.exposure_time_spin.setSuffix(" s")
        self.exposure_time_spin.setToolTip(
            "Tiempo que se muestra cada segmento (exposición)"
        )
        exposure_time_layout.addWidget(exposure_time_label)
        exposure_time_layout.addWidget(self.exposure_time_spin)
        exposure_time_layout.addStretch()
        sequence_layout.addLayout(exposure_time_layout)

        # Tiempo de movimiento (pantalla negra)
        movement_time_layout = QHBoxLayout()
        movement_time_label = QLabel("🚀 Tiempo de movimiento:")
        movement_time_label.setObjectName("statLabel")
        self.movement_time_spin = QDoubleSpinBox()
        self.movement_time_spin.setMinimum(0.0)  # Puede ser 0 si no hay movimiento
        self.movement_time_spin.setMaximum(60.0)  # Máximo 60 segundos
        self.movement_time_spin.setValue(0.2)
        self.movement_time_spin.setSingleStep(0.1)
        self.movement_time_spin.setDecimals(3)
        self.movement_time_spin.setSuffix(" s")
        self.movement_time_spin.setToolTip(
            "Tiempo para mover stage entre segmentos (pantalla negra)"
        )
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
        self.calibration_monitor_section = CollapsibleSection(
            "🔍 MONITOREO DE CALIBRACIÓN", self, expanded=True
        )
        calibration_monitor_content = QWidget()
        calibration_monitor_content.setObjectName("statsContainer")
        calibration_monitor_layout = QVBoxLayout(calibration_monitor_content)
        calibration_monitor_layout.setContentsMargins(12, 12, 12, 12)
        calibration_monitor_layout.setSpacing(8)

        monitor_desc = QLabel(
            "Estado en tiempo real de efectos aplicados a la proyección"
        )
        monitor_desc.setWordWrap(True)
        monitor_desc.setStyleSheet("font-size: 10px; color: #888888;")
        calibration_monitor_layout.addWidget(monitor_desc)

        # ─── Estado de Calibración ───
        calib_status_title = QLabel("📊 Estado de Calibración:")
        calib_status_title.setStyleSheet(
            "font-weight: bold; font-size: 10px; margin-top: 5px;"
        )
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
        atten_title.setStyleSheet(
            "font-weight: bold; font-size: 10px; margin-top: 8px;"
        )
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
        effects_title.setStyleSheet(
            "font-weight: bold; font-size: 10px; margin-top: 8px;"
        )
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
        projection_title.setStyleSheet(
            "font-weight: bold; font-size: 10px; margin-top: 8px;"
        )
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
        preview_title.setStyleSheet(
            "font-weight: bold; font-size: 10px; margin-top: 8px;"
        )
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
        self.calib_preview_strength_slider.setToolTip(
            "Ajusta la intensidad de la calibración en el preview"
        )
        self.calib_preview_strength_slider.valueChanged.connect(
            self.update_calibration_preview
        )

        self.calib_preview_strength_value = QLabel("100%")
        self.calib_preview_strength_value.setObjectName("statLabel")
        self.calib_preview_strength_value.setStyleSheet(
            "font-size: 10px; min-width: 35px;"
        )

        strength_layout.addWidget(strength_label)
        strength_layout.addWidget(self.calib_preview_strength_slider)
        strength_layout.addWidget(self.calib_preview_strength_value)
        calibration_monitor_layout.addLayout(strength_layout)

        # Botones de control de preview
        preview_buttons_layout = QHBoxLayout()

        self.calib_show_before_btn = QPushButton("👁️ Ver Original")
        self.calib_show_before_btn.setObjectName("modernButton")
        self.calib_show_before_btn.clicked.connect(
            lambda: self.update_calibration_preview(show_mode="before")
        )
        self.calib_show_before_btn.setToolTip("Muestra la imagen sin calibración")

        self.calib_show_after_btn = QPushButton("✨ Ver Calibrado")
        self.calib_show_after_btn.setObjectName("modernButton")
        self.calib_show_after_btn.clicked.connect(
            lambda: self.update_calibration_preview(show_mode="after")
        )
        self.calib_show_after_btn.setToolTip(
            "Muestra la imagen con calibración aplicada"
        )

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
        self.calib_flip_x_checkbox.setToolTip(
            "Invierte la matriz de calibración horizontalmente (eje X)"
        )
        self.calib_flip_x_checkbox.setChecked(self.calibration_flip_x)
        self.calib_flip_x_checkbox.stateChanged.connect(self.toggle_calibration_flip_x)

        self.calib_flip_y_checkbox = QCheckBox("↕️ Invertir Y")
        self.calib_flip_y_checkbox.setObjectName("modernCheckbox")
        self.calib_flip_y_checkbox.setToolTip(
            "Invierte la matriz de calibración verticalmente (eje Y)"
        )
        self.calib_flip_y_checkbox.setChecked(self.calibration_flip_y)
        self.calib_flip_y_checkbox.stateChanged.connect(self.toggle_calibration_flip_y)

        flip_controls_layout.addWidget(self.calib_flip_x_checkbox)
        flip_controls_layout.addWidget(self.calib_flip_y_checkbox)
        calibration_monitor_layout.addLayout(flip_controls_layout)

        # Botón para actualizar manualmente
        update_monitor_btn = QPushButton("🔄 Actualizar Monitor")
        update_monitor_btn.setObjectName("modernButton")
        update_monitor_btn.clicked.connect(self.update_calibration_monitor)
        update_monitor_btn.setToolTip(
            "Actualiza la información del monitor de calibración"
        )
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

        # variables para grabación de movimientos
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
        self.system_console.setPlaceholderText(
            "Los mensajes del sistema aparecerán aquí..."
        )

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

