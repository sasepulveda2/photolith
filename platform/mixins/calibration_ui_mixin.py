"""
Mixin de interfaz de calibracion.

Construye y gestiona la interfaz completa de calibracion con pestanas
para fuente de imagen, analisis de brillo y generacion de matrices.
"""

try:
    from pypylon import pylon
    BASLER_AVAILABLE = True
except ImportError:
    BASLER_AVAILABLE = False
    pylon = None

from PyQt5.QtWidgets import (
    QVBoxLayout, QHBoxLayout, QPushButton, QLabel, QSlider,
    QComboBox, QCheckBox, QLineEdit, QScrollArea, QWidget,
    QRadioButton, QButtonGroup, QFrame,
)
from PyQt5.QtCore import Qt
from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg as FigureCanvas
from matplotlib.figure import Figure
from UI.collapsible_section import CollapsibleSection


class CalibrationUIMixin:
    """Construye y navega la interfaz de calibracion."""

    def show_calibration_interface(self):
        """Muestra la interfaz de calibración con pestañas."""
        self.canvas.setVisible(False)
        if hasattr(self, "toolbar"):
            self.toolbar.setVisible(False)

        from PyQt5.QtWidgets import QTabWidget

        if not hasattr(self, "calibration_widget"):
            self.calibration_widget = QWidget()
            self.calibration_widget.setParent(self)
            calib_layout = QVBoxLayout(self.calibration_widget)

            title = QLabel("CALIBRACIÓN DE IMAGEN Y UNIFORMIDAD")
            title.setObjectName("sectionTitle")
            title.setAlignment(Qt.AlignCenter)
            calib_layout.addWidget(title)

            # Se ha eliminado el selector de modo manual

            # Pestañas (Calibración Cámara)
            self.calibration_tabs = QTabWidget()
            self.calibration_tabs.setObjectName("calibrationTabs")

            # ════════════════════════════════════════════════════════════
            # PESTAÑA Fuente de Imagen
            # ════════════════════════════════════════════════════════════
            source_tab = QWidget()
            source_tab.setAutoFillBackground(False)
            source_tab.setStyleSheet("background-color: transparent;")
            source_layout = QVBoxLayout(source_tab)
            source_layout.setContentsMargins(20, 20, 20, 20)
            source_layout.setSpacing(15)

            # Establecer tamaño mínimo cómodo
            source_tab.setMinimumWidth(750)

            # Título de la sección
            source_title = QLabel(" Selección de Fuente de Imagen")
            source_title.setStyleSheet(
                "font-size: 14px; font-weight: bold; margin-bottom: 10px; "
            )
            source_layout.addWidget(source_title)

            source_desc = QLabel(
                "Seleccione la fuente de imagen para realizar la calibración:"
            )
            source_desc.setWordWrap(True)
            source_desc.setStyleSheet("")
            source_layout.addWidget(source_desc)

            source_layout.addSpacing(10)

            # Grupo de radio buttons para selección de fuente
            self.source_button_group = QButtonGroup()

            # Cámara en vivo
            self.camera_radio = QRadioButton("Cámara en vivo")
            self.camera_radio.setChecked(True)
            self.source_button_group.addButton(self.camera_radio, 0)
            source_layout.addWidget(self.camera_radio)

            camera_info = QLabel(
                "     Captura imágenes en tiempo real desde la cámara conectada"
            )
            camera_info.setStyleSheet(
                "font-size: 11px; margin-left: 20px;"
            )
            camera_info.setWordWrap(True)
            source_layout.addWidget(camera_info)

            # Selector de cámara
            camera_selector_layout = QHBoxLayout()
            camera_selector_layout.setContentsMargins(40, 5, 0, 5)
            camera_label = QLabel("Cámara:")
            camera_label.setStyleSheet("")
            self.camera_combo = QComboBox()
            self.refresh_cameras_button = QPushButton("Actualizar")
            self.refresh_cameras_button.setMinimumWidth(80)
            self.refresh_cameras_button.clicked.connect(self.refresh_available_cameras)
            camera_selector_layout.addWidget(camera_label)
            camera_selector_layout.addWidget(self.camera_combo, stretch=1)
            camera_selector_layout.addWidget(self.refresh_cameras_button)
            source_layout.addLayout(camera_selector_layout)

            # Botón para iniciar/detener cámara
            camera_control_layout = QHBoxLayout()
            camera_control_layout.setContentsMargins(40, 5, 0, 10)
            self.start_camera_button = QPushButton("Iniciar cámara")
            self.start_camera_button.clicked.connect(self.toggle_camera_capture)
            camera_control_layout.addWidget(self.start_camera_button)
            camera_control_layout.addStretch()
            source_layout.addLayout(camera_control_layout)

            source_layout.addSpacing(10)

            # Cámara Basler (si está disponible)
            if BASLER_AVAILABLE:
                self.basler_radio = QRadioButton("Cámara Basler aCA640-750um")
                self.source_button_group.addButton(self.basler_radio, 1)
                source_layout.addWidget(self.basler_radio)

                basler_info = QLabel(
                    "     Cámara industrial con controles avanzados de exposición y ganancia"
                )
                basler_info.setStyleSheet(
                    "font-size: 11px; margin-left: 20px;"
                )
                basler_info.setWordWrap(True)
                source_layout.addWidget(basler_info)

                # Botón para iniciar/detener cámara Basler
                basler_control_layout = QHBoxLayout()
                basler_control_layout.setContentsMargins(40, 5, 0, 10)
                self.start_basler_button = QPushButton("Iniciar cámara Basler")
                self.start_basler_button.clicked.connect(self.toggle_basler_capture)
                basler_control_layout.addWidget(self.start_basler_button)
                basler_control_layout.addStretch()
                source_layout.addLayout(basler_control_layout)

                # Panel de controles Basler (colapsable)
                self.basler_controls_section = CollapsibleSection(
                    "Controles avanzados Basler", expanded=False
                )
                basler_controls_content = QWidget()
                basler_controls_layout = QVBoxLayout(basler_controls_content)
                basler_controls_layout.setContentsMargins(10, 10, 10, 10)
                basler_controls_layout.setSpacing(12)

                # Control de Exposición
                exp_label = QLabel("Exposición (μs):")
                exp_label.setStyleSheet("font-weight: bold;")
                basler_controls_layout.addWidget(exp_label)

                exp_layout = QHBoxLayout()
                self.basler_exposure_slider = QSlider(Qt.Horizontal)
                self.basler_exposure_slider.setMinimum(100)  # 100 μs mínimo
                self.basler_exposure_slider.setMaximum(1000000)  # 1 segundo máximo
                self.basler_exposure_slider.setValue(10000)  # 10ms por defecto
                self.basler_exposure_slider.valueChanged.connect(
                    self.update_basler_exposure_from_slider
                )
                self.basler_exposure_input = QLineEdit("10000")
                self.basler_exposure_input.setMaximumWidth(80)
                self.basler_exposure_input.returnPressed.connect(
                    self.update_basler_exposure_from_input
                )
                exp_layout.addWidget(self.basler_exposure_slider, stretch=1)
                exp_layout.addWidget(self.basler_exposure_input)
                exp_layout.addWidget(QLabel("μs"))
                basler_controls_layout.addLayout(exp_layout)

                # Control de Ganancia
                gain_label = QLabel("Ganancia (dB):")
                gain_label.setStyleSheet("font-weight: bold;")
                basler_controls_layout.addWidget(gain_label)

                gain_layout = QHBoxLayout()
                self.basler_gain_slider = QSlider(Qt.Horizontal)
                self.basler_gain_slider.setMinimum(0)
                self.basler_gain_slider.setMaximum(
                    240
                )  # 24.0 dB máximo (x10 para precisión)
                self.basler_gain_slider.setValue(0)
                self.basler_gain_slider.valueChanged.connect(
                    self.update_basler_gain_from_slider
                )
                self.basler_gain_input = QLineEdit("0.0")
                self.basler_gain_input.setMaximumWidth(80)
                self.basler_gain_input.returnPressed.connect(
                    self.update_basler_gain_from_input
                )
                gain_layout.addWidget(self.basler_gain_slider, stretch=1)
                gain_layout.addWidget(self.basler_gain_input)
                gain_layout.addWidget(QLabel("dB"))
                basler_controls_layout.addLayout(gain_layout)

                # Control de Gamma
                gamma_label = QLabel("Gamma:")
                gamma_label.setStyleSheet("font-weight: bold;")
                basler_controls_layout.addWidget(gamma_label)

                gamma_layout = QHBoxLayout()
                self.basler_gamma_slider = QSlider(Qt.Horizontal)
                self.basler_gamma_slider.setMinimum(10)  # 0.1 (x10)
                self.basler_gamma_slider.setMaximum(40)  # 4.0 (x10)
                self.basler_gamma_slider.setValue(10)  # 1.0 por defecto
                self.basler_gamma_slider.valueChanged.connect(
                    self.update_basler_gamma_from_slider
                )
                self.basler_gamma_input = QLineEdit("1.0")
                self.basler_gamma_input.setMaximumWidth(80)
                self.basler_gamma_input.returnPressed.connect(
                    self.update_basler_gamma_from_input
                )
                gamma_layout.addWidget(self.basler_gamma_slider, stretch=1)
                gamma_layout.addWidget(self.basler_gamma_input)
                basler_controls_layout.addLayout(gamma_layout)

                # Control de Black Level
                black_label = QLabel("Nivel de negro:")
                black_label.setStyleSheet("font-weight: bold;")
                basler_controls_layout.addWidget(black_label)

                black_layout = QHBoxLayout()
                self.basler_black_slider = QSlider(Qt.Horizontal)
                self.basler_black_slider.setMinimum(0)
                self.basler_black_slider.setMaximum(255)
                self.basler_black_slider.setValue(0)
                self.basler_black_slider.valueChanged.connect(
                    self.update_basler_black_from_slider
                )
                self.basler_black_input = QLineEdit("0")
                self.basler_black_input.setMaximumWidth(80)
                self.basler_black_input.returnPressed.connect(
                    self.update_basler_black_from_input
                )
                black_layout.addWidget(self.basler_black_slider, stretch=1)
                black_layout.addWidget(self.basler_black_input)
                basler_controls_layout.addLayout(black_layout)

                # Botón para aplicar cambios
                apply_basler_btn = QPushButton("Aplicar configuración")
                apply_basler_btn.clicked.connect(self.apply_basler_settings)
                basler_controls_layout.addWidget(apply_basler_btn)

                # Botón para resetear a valores por defecto
                reset_basler_btn = QPushButton("Valores por defecto")
                reset_basler_btn.clicked.connect(self.reset_basler_settings)
                basler_controls_layout.addWidget(reset_basler_btn)

                self.basler_controls_section.setContentWidget(basler_controls_content)
                source_layout.addWidget(self.basler_controls_section)

                source_layout.addSpacing(10)
            else:
                self.basler_radio = None
                # Mostrar mensaje de que Basler no está disponible
                basler_unavailable = QLabel(
                    "Cámara Basler no disponible (pypylon no instalado)"
                )
                basler_unavailable.setStyleSheet(
                    "font-size: 11px; font-style: italic;"
                )
                source_layout.addWidget(basler_unavailable)
                source_layout.addSpacing(10)

            self.image_radio = QRadioButton("Imagen estática")
            self.source_button_group.addButton(
                self.image_radio, 2 if BASLER_AVAILABLE else 1
            )
            source_layout.addWidget(self.image_radio)

            image_info = QLabel("     Carga una imagen preexistente desde el disco")
            image_info.setStyleSheet(
                "font-size: 11px; margin-left: 20px;"
            )
            image_info.setWordWrap(True)
            source_layout.addWidget(image_info)

            # Botón para cargar imagen
            image_loader_layout = QHBoxLayout()
            image_loader_layout.setContentsMargins(40, 5, 0, 5)
            self.load_calib_image_button = QPushButton("Cargar imagen...")
            self.load_calib_image_button.clicked.connect(self.load_calibration_image)
            image_loader_layout.addWidget(self.load_calib_image_button)
            image_loader_layout.addStretch()
            source_layout.addLayout(image_loader_layout)

            # Label para mostrar imagen cargada
            self.calib_image_status = QLabel("   Sin imagen cargada")
            self.calib_image_status.setStyleSheet(
                "font-size: 11px; margin-left: 40px;"
            )
            source_layout.addWidget(self.calib_image_status)

            source_layout.addSpacing(20)

            # Vista previa
            preview_label = QLabel("Vista previa:")
            preview_label.setStyleSheet(
                "font-size: 13px; font-weight: bold; "
            )
            source_layout.addWidget(preview_label)

            # Canvas para vista previa de calibración
            self.calib_preview_figure = Figure(
                facecolor="#121212" if self.dark_mode else "#FFFFFF"
            )
            self.calib_preview_canvas = FigureCanvas(self.calib_preview_figure)
            self.calib_preview_canvas.setMinimumHeight(150)
            self.calib_preview_ax = self.calib_preview_figure.add_subplot(111)
            self.calib_preview_ax.set_facecolor(
                "#1E1E1E" if self.dark_mode else "#F5F5F5"
            )
            self.calib_preview_ax.text(
                0.5,
                0.5,
                "Seleccione una fuente para comenzar",
                ha="center",
                va="center",
                fontsize=12,
                color="#E0E0E0" if self.dark_mode else "#000000",
            )
            self.calib_preview_ax.axis("off")
            self.calib_preview_canvas.draw()
            source_layout.addWidget(self.calib_preview_canvas, stretch=1)

            source_layout.addStretch()

            # Conectar cambios de fuente
            self.source_button_group.buttonClicked.connect(
                self.on_calibration_source_changed
            )

            self.calibration_tabs.addTab(source_tab, "Fuente de imagen")

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
            analysis_title = QLabel("Análisis y visualización del brillo")
            analysis_title.setStyleSheet(
                "font-size: 14px; font-weight: bold; margin-bottom: 10px; "
            )
            analysis_layout.addWidget(analysis_title)

            analysis_desc = QLabel(
                "Análisis de intensidad y uniformidad de la imagen capturada:"
            )
            analysis_desc.setWordWrap(True)
            analysis_desc.setStyleSheet("")
            analysis_layout.addWidget(analysis_desc)

            analysis_layout.addSpacing(10)

            # ─────────────────────────────────────────────────────────
            # Visualización en Escala de Grises
            # ─────────────────────────────────────────────────────────
            grayscale_group = QWidget()
            grayscale_group.setObjectName("statsContainer")
            grayscale_layout = QVBoxLayout(grayscale_group)
            grayscale_layout.setContentsMargins(10, 10, 10, 10)

            gray_title = QLabel("Visualización en escala de grises")
            gray_title.setStyleSheet(
                "font-size: 13px; font-weight: bold; "
            )
            grayscale_layout.addWidget(gray_title)

            gray_desc = QLabel(
                "Vista de la imagen en escala de grises para análisis de intensidad:"
            )
            gray_desc.setWordWrap(True)
            gray_desc.setStyleSheet("font-size: 11px; ")
            grayscale_layout.addWidget(gray_desc)

            # Botones de control
            gray_controls = QHBoxLayout()
            self.show_grayscale_button = QPushButton("Mostrar escala de grises")
            self.show_grayscale_button.clicked.connect(self.show_grayscale_fullscreen)
            self.show_grayscale_button.setEnabled(
                False
            )  # Habilitado solo cuando hay imagen
            gray_controls.addWidget(self.show_grayscale_button)

            # Botón de inversión (espejo)
            self.mirror_preview_button = QPushButton("Espejo")
            self.mirror_preview_button.setCheckable(True)
            self.mirror_preview_button.clicked.connect(self.toggle_mirror_preview)
            self.mirror_preview_button.setEnabled(False)
            gray_controls.addWidget(self.mirror_preview_button)

            gray_controls.addStretch()
            grayscale_layout.addLayout(gray_controls)

            # Canvas para vista previa en escala de grises
            self.gray_preview_figure = Figure(
                facecolor="#121212" if self.dark_mode else "#FFFFFF"
            )
            self.gray_preview_canvas = FigureCanvas(self.gray_preview_figure)
            self.gray_preview_canvas.setMinimumHeight(150)
            self.gray_preview_ax = self.gray_preview_figure.add_subplot(111)
            self.gray_preview_ax.set_facecolor(
                "#1E1E1E" if self.dark_mode else "#F5F5F5"
            )
            self.gray_preview_ax.text(
                0.5,
                0.5,
                "Capture o cargue una imagen en la pestaña anterior",
                ha="center",
                va="center",
                fontsize=11,
                color="#E0E0E0" if self.dark_mode else "#000000",
            )
            self.gray_preview_ax.axis("off")
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

            intensity_title = QLabel("Análisis de intensidad")
            intensity_title.setStyleSheet(
                "font-size: 13px; font-weight: bold; "
            )
            intensity_layout.addWidget(intensity_title)

            intensity_desc = QLabel(
                "Análisis zonal de brillo/atenuación con mapa de calor:"
            )
            intensity_desc.setWordWrap(True)
            intensity_desc.setStyleSheet("font-size: 11px; ")
            intensity_layout.addWidget(intensity_desc)

            # Controles de análisis zonal
            zone_controls_layout = QHBoxLayout()

            zone_label = QLabel("División de Zonas:")
            zone_label.setStyleSheet("")
            zone_controls_layout.addWidget(zone_label)

            self.zone_grid_combo = QComboBox()
            self.zone_grid_combo.addItems(
                [
                    "3x3 (9 zonas)",
                    "4x4 (16 zonas)",
                    "5x5 (25 zonas)",
                    "8x8 (64 zonas)",
                    "Píxel a Píxel",
                ]
            )
            self.zone_grid_combo.setCurrentIndex(1)  # 4x4 por defecto
            self.zone_grid_combo.currentIndexChanged.connect(
                self.update_intensity_analysis
            )
            zone_controls_layout.addWidget(self.zone_grid_combo)

            zone_controls_layout.addSpacing(20)

            self.analyze_intensity_button = QPushButton("Analizar intensidad")
            self.analyze_intensity_button.clicked.connect(self.analyze_brightness_zones)
            self.analyze_intensity_button.setEnabled(False)
            zone_controls_layout.addWidget(self.analyze_intensity_button)

            zone_controls_layout.addStretch()
            intensity_layout.addLayout(zone_controls_layout)

            # Opciones de visualización
            viz_options = QHBoxLayout()

            self.show_percentages_check = QCheckBox("Mostrar Porcentajes")
            self.show_percentages_check.setChecked(True)
            self.show_percentages_check.stateChanged.connect(
                self.update_intensity_analysis
            )
            viz_options.addWidget(self.show_percentages_check)

            self.show_heatmap_check = QCheckBox("Mapa de Calor")
            self.show_heatmap_check.setChecked(True)
            self.show_heatmap_check.stateChanged.connect(self.update_intensity_analysis)
            viz_options.addWidget(self.show_heatmap_check)

            viz_options.addStretch()
            intensity_layout.addLayout(viz_options)

            # Canvas para mapa de intensidad
            self.intensity_map_figure = Figure(
                facecolor="#121212" if self.dark_mode else "#FFFFFF"
            )
            self.intensity_map_canvas = FigureCanvas(self.intensity_map_figure)
            self.intensity_map_canvas.setMinimumHeight(150)
            self.intensity_map_ax = self.intensity_map_figure.add_subplot(111)
            self.intensity_map_ax.set_facecolor(
                "#1E1E1E" if self.dark_mode else "#F5F5F5"
            )
            self.intensity_map_ax.text(
                0.5,
                0.5,
                'Presione "Analizar Intensidad" para comenzar',
                ha="center",
                va="center",
                fontsize=11,
                color="#E0E0E0" if self.dark_mode else "#000000",
            )
            self.intensity_map_ax.axis("off")
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
            self.uniformity_indicator.setStyleSheet(
                "font-size: 16px; font-weight: bold; "
            )
            uniformity_layout.addWidget(self.uniformity_indicator)

            self.uniformity_status = QLabel("Sin datos")
            self.uniformity_status.setStyleSheet("font-size: 11px; ")
            uniformity_layout.addWidget(self.uniformity_status)

            uniformity_layout.addStretch()
            intensity_layout.addLayout(uniformity_layout)

            analysis_layout.addWidget(intensity_group)

            analysis_layout.addStretch()

            self.calibration_tabs.addTab(analysis_tab, "Análisis de brillo")

            adjustment_tab = QWidget()
            adjustment_tab.setAutoFillBackground(False)
            adjustment_tab.setStyleSheet("background-color: transparent;")
            adjustment_layout = QVBoxLayout(adjustment_tab)
            adjustment_layout.setContentsMargins(20, 20, 20, 20)
            adjustment_layout.setSpacing(15)

            adjustment_title = QLabel("Herramientas de Ajuste de Calibración")
            adjustment_title.setStyleSheet(
                "font-size: 14px; font-weight: bold; margin-bottom: 10px; "
            )
            adjustment_layout.addWidget(adjustment_title)

            adjustment_desc = QLabel(
                "Ajuste del umbral y generación de matriz de atenuación:"
            )
            adjustment_desc.setWordWrap(True)
            adjustment_desc.setStyleSheet("")
            adjustment_layout.addWidget(adjustment_desc)

            adjustment_layout.addSpacing(10)

            # ─────────────────────────────────────────────────────────
            # Control de Umbral (Threshold)
            # ─────────────────────────────────────────────────────────
            threshold_group = QWidget()
            threshold_group.setObjectName("statsContainer")
            threshold_layout = QVBoxLayout(threshold_group)
            threshold_layout.setContentsMargins(10, 10, 10, 10)

            threshold_title = QLabel("Control de umbral binario")
            threshold_title.setStyleSheet(
                "font-size: 13px; font-weight: bold; "
            )
            threshold_layout.addWidget(threshold_title)

            threshold_desc = QLabel(
                "Ajuste del punto de corte para conversión binaria de la imagen:"
            )
            threshold_desc.setWordWrap(True)
            threshold_desc.setStyleSheet("font-size: 11px; ")
            threshold_layout.addWidget(threshold_desc)

            # Control de umbral con slider e input
            threshold_controls = QHBoxLayout()

            threshold_label = QLabel("Umbral de Intensidad:")
            threshold_label.setStyleSheet("")
            threshold_controls.addWidget(threshold_label)

            self.calib_threshold_slider = QSlider(Qt.Horizontal)
            self.calib_threshold_slider.setMinimum(0)
            self.calib_threshold_slider.setMaximum(100)
            self.calib_threshold_slider.setValue(int(self.calibration_threshold))
            self.calib_threshold_slider.setMinimumWidth(200)
            self.calib_threshold_slider.valueChanged.connect(
                self.update_calibration_threshold_from_slider
            )
            self.calib_threshold_slider.sliderReleased.connect(
                self.save_calibration_data
            )
            threshold_controls.addWidget(self.calib_threshold_slider)

            self.calib_threshold_input = QLineEdit()
            self.calib_threshold_input.setText(f"{self.calibration_threshold:.1f}")
            self.calib_threshold_input.setMaximumWidth(60)
            self.calib_threshold_input.setPlaceholderText("0-100")
            self.calib_threshold_input.editingFinished.connect(
                self.update_calibration_threshold_from_input
            )
            self.calib_threshold_input.editingFinished.connect(
                self.save_calibration_data
            )
            threshold_controls.addWidget(self.calib_threshold_input)

            threshold_unit_label = QLabel("%")
            threshold_unit_label.setStyleSheet("")
            threshold_controls.addWidget(threshold_unit_label)

            threshold_controls.addStretch()
            threshold_layout.addLayout(threshold_controls)

            threshold_info = QLabel(
                "El umbral determina el punto de corte para conversión binaria\n"
                "Intensidad >= umbral -> 100% (Blanco/Expuesto)\n"
                "Intensidad < umbral -> 0% (Negro/No expuesto)"
            )
            threshold_info.setWordWrap(True)
            threshold_info.setStyleSheet(
                "font-size: 10px; margin-left: 10px;"
            )
            threshold_layout.addWidget(threshold_info)

            preview_threshold_layout = QHBoxLayout()
            self.preview_threshold_button = QPushButton("Previsualizar conversión")
            self.preview_threshold_button.clicked.connect(
                self.preview_threshold_conversion
            )
            self.preview_threshold_button.setEnabled(False)
            preview_threshold_layout.addWidget(self.preview_threshold_button)
            preview_threshold_layout.addStretch()
            threshold_layout.addLayout(preview_threshold_layout)
            self.threshold_preview_figure = Figure(
                facecolor="#121212" if self.dark_mode else "#FFFFFF"
            )
            self.threshold_preview_canvas = FigureCanvas(self.threshold_preview_figure)
            self.threshold_preview_canvas.setMinimumHeight(150)
            self.threshold_preview_ax = self.threshold_preview_figure.add_subplot(111)
            self.threshold_preview_ax.set_facecolor(
                "#1E1E1E" if self.dark_mode else "#F5F5F5"
            )
            self.threshold_preview_ax.text(
                0.5,
                0.5,
                'Capture/cargue una imagen y presione "Previsualizar"',
                ha="center",
                va="center",
                fontsize=11,
                color="#E0E0E0" if self.dark_mode else "#000000",
            )
            self.threshold_preview_ax.axis("off")
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

            atten_title = QLabel("Matriz de compensación de uniformidad")
            atten_title.setStyleSheet(
                "font-size: 13px; font-weight: bold; "
            )
            attenuation_layout.addWidget(atten_title)

            atten_desc = QLabel(
                "Corrección automática de variaciones de brillo en la proyección:"
            )
            atten_desc.setWordWrap(True)
            atten_desc.setStyleSheet("font-size: 11px; ")
            attenuation_layout.addWidget(atten_desc)

            # Controles de generación de matriz
            matrix_gen_layout = QHBoxLayout()

            self.generate_attenuation_button = QPushButton(
                "Generar matriz de atenuación"
            )
            self.generate_attenuation_button.clicked.connect(
                self.generate_attenuation_matrix
            )
            self.generate_attenuation_button.setEnabled(False)
            matrix_gen_layout.addWidget(self.generate_attenuation_button)

            matrix_gen_layout.addSpacing(20)

            self.apply_attenuation_check = QCheckBox("Aplicar a Grid de Proyección")
            self.apply_attenuation_check.setEnabled(False)
            self.apply_attenuation_check.stateChanged.connect(
                self.toggle_attenuation_application
            )
            matrix_gen_layout.addWidget(self.apply_attenuation_check)

            matrix_gen_layout.addStretch()
            attenuation_layout.addLayout(matrix_gen_layout)

            # Método de compensación
            method_layout = QHBoxLayout()
            method_label = QLabel("Método de Compensación:")
            method_label.setStyleSheet("")
            method_layout.addWidget(method_label)

            self.attenuation_method_combo = QComboBox()
            self.attenuation_method_combo.addItems(
                [
                    "Inversión Normalizada (Recomendado)",
                    "Inversión Simple",
                    "Ecualizador Adaptativo",
                    "Compensación Proporcional",
                ]
            )
            self.attenuation_method_combo.currentIndexChanged.connect(
                self.update_attenuation_preview
            )
            self.attenuation_method_combo.currentIndexChanged.connect(
                self.save_calibration_data
            )
            method_layout.addWidget(self.attenuation_method_combo)

            method_layout.addStretch()
            attenuation_layout.addLayout(method_layout)

            # Intensidad de corrección
            intensity_layout = QHBoxLayout()
            intensity_label = QLabel("Intensidad de Corrección:")
            intensity_label.setStyleSheet("")
            intensity_layout.addWidget(intensity_label)

            self.attenuation_strength_slider = QSlider(Qt.Horizontal)
            self.attenuation_strength_slider.setMinimum(0)
            self.attenuation_strength_slider.setMaximum(100)
            self.attenuation_strength_slider.setValue(int(self.attenuation_strength))
            self.attenuation_strength_slider.setMinimumWidth(150)
            self.attenuation_strength_slider.valueChanged.connect(
                self.update_attenuation_preview
            )
            self.attenuation_strength_slider.sliderReleased.connect(
                self.save_calibration_data
            )
            intensity_layout.addWidget(self.attenuation_strength_slider)

            self.attenuation_strength_label = QLabel(f"{self.attenuation_strength}%")
            self.attenuation_strength_label.setStyleSheet("")
            intensity_layout.addWidget(self.attenuation_strength_label)

            intensity_layout.addStretch()
            attenuation_layout.addLayout(intensity_layout)

            # Botones de acción
            action_layout = QHBoxLayout()

            self.preview_attenuation_button = QPushButton("Previsualizar corrección")
            self.preview_attenuation_button.clicked.connect(
                self.preview_attenuation_effect
            )
            self.preview_attenuation_button.setEnabled(False)
            action_layout.addWidget(self.preview_attenuation_button)

            self.save_attenuation_button = QPushButton("Guardar matriz")
            self.save_attenuation_button.clicked.connect(self.save_attenuation_matrix)
            self.save_attenuation_button.setEnabled(False)
            action_layout.addWidget(self.save_attenuation_button)

            self.load_attenuation_button = QPushButton("Cargar matriz")
            self.load_attenuation_button.clicked.connect(self.load_attenuation_matrix)
            action_layout.addWidget(self.load_attenuation_button)

            action_layout.addStretch()
            attenuation_layout.addLayout(action_layout)

            # Canvas para visualización de matriz de atenuación
            self.attenuation_figure = Figure(
                facecolor="#121212" if self.dark_mode else "#FFFFFF"
            )
            self.attenuation_canvas = FigureCanvas(self.attenuation_figure)
            self.attenuation_canvas.setMinimumHeight(150)
            self.attenuation_ax = self.attenuation_figure.add_subplot(111)
            self.attenuation_ax.set_facecolor(
                "#1E1E1E" if self.dark_mode else "#F5F5F5"
            )
            self.attenuation_ax.text(
                0.5,
                0.5,
                "Genere la matriz para visualizar",
                ha="center",
                va="center",
                fontsize=11,
                color="#E0E0E0" if self.dark_mode else "#000000",
            )
            self.attenuation_ax.axis("off")
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

            self.calibration_tabs.addTab(adjustment_tab, "Ajustes y matriz")

            # Crear scroll area para las pestañas de calibración
            calibration_scroll = QScrollArea()
            calibration_scroll.setWidget(self.calibration_tabs)
            calibration_scroll.setWidgetResizable(True)
            calibration_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAsNeeded)
            calibration_scroll.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)
            calibration_scroll.setFrameShape(QFrame.NoFrame)

            # Establecer tamaño mínimo cómodo para el área de calibración
            calibration_scroll.setMinimumWidth(800)
            calibration_scroll.setMinimumHeight(400)

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
        if hasattr(self, "calibration_widget"):
            self.calibration_widget.setVisible(False)

        # Mostrar el canvas normal
        self.canvas.setVisible(True)
        if hasattr(self, "toolbar"):
            self.toolbar.setVisible(
                self.grid_view_active
            )  # Solo mostrar si estamos en modo grid

        # Detener cámaras si están activas
        if self.calibration_camera is not None:
            self.stop_camera_capture()
        if BASLER_AVAILABLE and self.basler_camera is not None:
            self.stop_basler_capture()



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

    def _update_calibration_theme(self):
        """Actualiza los colores de las figuras de matplotlib en calibración al cambiar de tema."""
        if not hasattr(self, "calibration_widget"):
            return
            
        is_dark = self.dark_mode
        
        # Actualizar el estilo de las pestañas dinámicamente
        if hasattr(self, "calibration_tabs"):
            self.calibration_tabs.setStyleSheet(
                """
                QTabWidget::pane {
                    background-color: #1E1E1E;
                    border: none;
                }
                QTabWidget > QWidget {
                    background-color: #1E1E1E;
                }
                """ if is_dark else """
                QTabWidget::pane {
                    background-color: #FFFFFF;
                    border: none;
                }
                QTabWidget > QWidget {
                    background-color: #FFFFFF;
                }
                """
            )
            
        bg_color = "#1E1E1E" if is_dark else "#FFFFFF"
        ax_bg = "#1E1E1E" if is_dark else "#FFFFFF"
        text_color = "#E0E0E0" if is_dark else "#000000"
        
        figures = [
            (getattr(self, "calib_preview_figure", None), getattr(self, "calib_preview_ax", None), getattr(self, "calib_preview_canvas", None)),
            (getattr(self, "gray_preview_figure", None), getattr(self, "gray_preview_ax", None), getattr(self, "gray_preview_canvas", None)),
            (getattr(self, "intensity_map_figure", None), getattr(self, "intensity_map_ax", None), getattr(self, "intensity_map_canvas", None)),
            (getattr(self, "threshold_preview_figure", None), getattr(self, "threshold_preview_ax", None), getattr(self, "threshold_preview_canvas", None)),
            (getattr(self, "attenuation_figure", None), getattr(self, "attenuation_ax", None), getattr(self, "attenuation_canvas", None))
        ]
        
        for fig, ax, canvas in figures:
            if fig and ax and canvas:
                fig.set_facecolor(bg_color)
                ax.set_facecolor(ax_bg)
                for txt in ax.texts:
                    txt.set_color(text_color)
                canvas.draw()
 