"""
Builder para la barra lateral específica de Calibración de Patrón (Tamaño y Exposición).
"""

from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit,
    QPushButton, QStackedWidget, QComboBox, QFormLayout,
    QSpinBox, QDoubleSpinBox, QCheckBox
)
from PyQt5.QtCore import Qt

from constants import SIDEBAR_MIN_WIDTH, SIDEBAR_MAX_WIDTH

class PatternCalibPanelBuilder:
    """Construye el sidebar para Calibración Espacial y de Exposición."""

    def _build_pattern_calib_section(self):
        """Construye el sidebar dedicado que reemplaza al sidebar principal."""
        self.pattern_calib_sidebar_widget = QWidget()
        self.pattern_calib_sidebar_widget.setVisible(False)
        self.pattern_calib_sidebar_widget.setMinimumWidth(SIDEBAR_MIN_WIDTH)
        self.pattern_calib_sidebar_widget.setMaximumWidth(SIDEBAR_MAX_WIDTH)

        main_layout = QVBoxLayout(self.pattern_calib_sidebar_widget)
        main_layout.setContentsMargins(10, 10, 10, 10)
        main_layout.setSpacing(10)

        title = QLabel("CALIBRACIÓN DE PATRÓN")
        title.setAlignment(Qt.AlignCenter)
        title.setStyleSheet("font-weight: bold; font-size: 14px; color: #03DAC6;")
        main_layout.addWidget(title)

        # Botones de selección en lugar de Tabs
        btn_layout = QHBoxLayout()
        self.btn_mode_spatial = QPushButton("📏 Tamaño")
        self.btn_mode_exposure = QPushButton("⏱️ Exposición")
        
        # Estilos para indicar cual está activo (opcional, por ahora simples)
        self.btn_mode_spatial.setCheckable(True)
        self.btn_mode_exposure.setCheckable(True)
        self.btn_mode_spatial.setChecked(True)

        btn_layout.addWidget(self.btn_mode_spatial)
        btn_layout.addWidget(self.btn_mode_exposure)
        main_layout.addLayout(btn_layout)

        # Stacked widget para intercambiar el contenido
        self.pattern_calib_stacked = QStackedWidget()

        # --- VIEW 1: TAMAÑO ESPACIAL ---
        spatial_view = QWidget()
        spatial_layout = QVBoxLayout(spatial_view)
        spatial_layout.setSpacing(15)

        help_label = QLabel("Dibuja una línea en la imagen y establece su tamaño real.")
        help_label.setWordWrap(True)
        help_label.setStyleSheet("color: #888888; font-style: italic;")
        spatial_layout.addWidget(help_label)

        self.btn_load_pattern_calib = QPushButton("📂 Cargar Patrón de Calibración")
        self.btn_load_pattern_calib.clicked.connect(self.load_calibration_pattern)
        spatial_layout.addWidget(self.btn_load_pattern_calib)

        spatial_layout.addSpacing(10)
        self.lbl_pixels_calib = QLabel("Distancia en Píxeles: 0.00")
        self.lbl_pixels_calib.setStyleSheet("font-weight: bold;")
        spatial_layout.addWidget(self.lbl_pixels_calib)

        spatial_layout.addWidget(QLabel("Medida real (mm):"))
        self.input_mm_calib = QLineEdit()
        self.input_mm_calib.setPlaceholderText("Ej. 10.5")
        self.input_mm_calib.textChanged.connect(self.calculate_spatial_scale)
        spatial_layout.addWidget(self.input_mm_calib)

        self.lbl_result_calib = QLabel("Escala: -")
        self.lbl_result_calib.setStyleSheet("font-weight: bold; color: #00BFA5; font-size: 13px;")
        spatial_layout.addWidget(self.lbl_result_calib)

        spatial_layout.addStretch()

        self.btn_save_spatial_calib = QPushButton("💾 Guardar Calibración")
        self.btn_save_spatial_calib.clicked.connect(self.save_spatial_scale_from_ui)
        spatial_layout.addWidget(self.btn_save_spatial_calib)

        self.pattern_calib_stacked.addWidget(spatial_view)

        # --- VIEW 2: TIEMPO DE EXPOSICIÓN ---
        exposure_view = QWidget()
        exposure_layout = QVBoxLayout(exposure_view)
        exposure_layout.setSpacing(10)
        
        exp_help = QLabel("Genera una matriz dinámica para prueba de exposición óptima.")
        exp_help.setWordWrap(True)
        exp_help.setStyleSheet("color: #888888; font-style: italic;")
        exposure_layout.addWidget(exp_help)

        # --- CARGAR CONFIGURACION PREVIA ---
        import os, json
        from constants import CONFIG_FILE
        config = {}
        if os.path.exists(CONFIG_FILE):
            try:
                with open(CONFIG_FILE, 'r', encoding='utf-8') as f:
                    config = json.load(f)
            except:
                pass

        form_layout = QFormLayout()
        
        self.input_exp_base = QDoubleSpinBox()
        self.input_exp_base.setRange(0.0, 3600.0)
        self.input_exp_base.setSingleStep(0.5)
        self.input_exp_base.setValue(config.get('exp_base_time', 5.0))
        form_layout.addRow("Tiempo base (s):", self.input_exp_base)
        
        self.input_exp_step = QDoubleSpinBox()
        self.input_exp_step.setRange(0.1, 3600.0)
        self.input_exp_step.setSingleStep(0.5)
        self.input_exp_step.setValue(config.get('exp_step_time', 1.0))
        form_layout.addRow("Incremento (s):", self.input_exp_step)
        
        self.input_exp_stripes = QSpinBox()
        self.input_exp_stripes.setRange(1, 100)
        self.input_exp_stripes.setValue(config.get('exp_stripes', 10))
        form_layout.addRow("Franjas:", self.input_exp_stripes)
        
        self.combo_exp_dir = QComboBox()
        self.combo_exp_dir.addItems(["Horizontal", "Vertical", "Rectángulo Central", "Círculo Central", "Triángulo Central"])
        self.combo_exp_dir.setCurrentText(config.get('exp_direction', "Horizontal"))
        form_layout.addRow("Dirección:", self.combo_exp_dir)

        self.combo_exp_mode = QComboBox()
        self.combo_exp_mode.addItems(["Decremento", "Incremento"])
        self.combo_exp_mode.setCurrentText(config.get('exp_mode', "Decremento"))
        form_layout.addRow("Modo:", self.combo_exp_mode)

        exposure_layout.addLayout(form_layout)
        
        self.chk_exp_invert = QCheckBox("Invertir colores (Fondo oscuro, figura clara)")
        self.chk_exp_invert.setChecked(config.get('exp_invert', False))
        exposure_layout.addWidget(self.chk_exp_invert)
        
        # Conectar para autoguardar
        def on_param_changed(*args):
            if hasattr(self, "_save_exposure_params"):
                self._save_exposure_params()
                
        self.input_exp_base.valueChanged.connect(on_param_changed)
        self.input_exp_step.valueChanged.connect(on_param_changed)
        self.input_exp_stripes.valueChanged.connect(on_param_changed)
        self.combo_exp_dir.currentIndexChanged.connect(on_param_changed)
        self.combo_exp_mode.currentIndexChanged.connect(on_param_changed)
        self.chk_exp_invert.stateChanged.connect(on_param_changed)
        
        self.lbl_exp_status = QLabel("Estado: Inactivo")
        self.lbl_exp_status.setStyleSheet("font-weight: bold; color: #00BFA5;")
        exposure_layout.addWidget(self.lbl_exp_status)
        
        self.lbl_exp_time = QLabel("Tiempo transcurrido: 0.0 s")
        self.lbl_exp_time.setStyleSheet("font-weight: bold; color: #FFD700; font-size: 13px;")
        exposure_layout.addWidget(self.lbl_exp_time)
        
        exposure_layout.addStretch()

        btn_exp_layout = QHBoxLayout()
        self.btn_start_exposure = QPushButton("▶ Iniciar")
        self.btn_start_exposure.clicked.connect(self.start_exposure_matrix)
        self.btn_stop_exposure = QPushButton("⏹ Detener")
        self.btn_stop_exposure.clicked.connect(self.stop_exposure_matrix)
        
        btn_exp_layout.addWidget(self.btn_start_exposure)
        btn_exp_layout.addWidget(self.btn_stop_exposure)
        exposure_layout.addLayout(btn_exp_layout)

        self.pattern_calib_stacked.addWidget(exposure_view)

        main_layout.addWidget(self.pattern_calib_stacked)

        # Conectar botones
        self.btn_mode_spatial.clicked.connect(lambda: self._switch_pattern_calib_mode(0))
        self.btn_mode_exposure.clicked.connect(lambda: self._switch_pattern_calib_mode(1))

    def _switch_pattern_calib_mode(self, index):
        """Cambia entre la vista de Tamaño Espacial y Tiempo de Exposición."""
        self.pattern_calib_stacked.setCurrentIndex(index)
        self.btn_mode_spatial.setChecked(index == 0)
        self.btn_mode_exposure.setChecked(index == 1)
        if hasattr(self, "_update_pattern_calib_canvas"):
            self._update_pattern_calib_canvas(index)
