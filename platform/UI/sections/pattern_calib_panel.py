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
        self.btn_mode_cd = QPushButton("🔍 Test CD")
        
        # Estilos para indicar cual está activo (opcional, por ahora simples)
        self.btn_mode_spatial.setCheckable(True)
        self.btn_mode_exposure.setCheckable(True)
        self.btn_mode_cd.setCheckable(True)
        self.btn_mode_spatial.setChecked(True)

        btn_layout.addWidget(self.btn_mode_spatial)
        btn_layout.addWidget(self.btn_mode_exposure)
        btn_layout.addWidget(self.btn_mode_cd)
        main_layout.addLayout(btn_layout)

        # Stacked widget para intercambiar el contenido
        self.pattern_calib_stacked = QStackedWidget()

        # --- VIEW 1: TAMAÑO ESPACIAL ---
        spatial_view = QWidget()
        spatial_layout = QVBoxLayout(spatial_view)
        spatial_layout.setSpacing(15)

        self.btn_toggle_motor_calib = QPushButton("⚙️ Calibración por Solapamiento (Motores)")
        self.btn_toggle_motor_calib.setCheckable(True)
        spatial_layout.addWidget(self.btn_toggle_motor_calib)
        
        # Contenedor de motor calib (oculto por defecto)
        self.motor_container = QWidget()
        self.motor_container.setVisible(False)
        motor_layout = QVBoxLayout(self.motor_container)
        motor_layout.setContentsMargins(0,0,0,0)
        motor_layout.setSpacing(5)
        
        motor_form = QFormLayout()
        
        self.combo_motor_axis = QComboBox()
        self.combo_motor_axis.addItems(["Eje X (Líneas Verticales)", "Eje Y (Líneas Horizontales)"])
        import os, json
        from constants import CONFIG_FILE
        config = {}
        if os.path.exists(CONFIG_FILE):
            try:
                with open(CONFIG_FILE, 'r', encoding='utf-8') as f:
                    config = json.load(f)
            except:
                pass
        if not isinstance(config, dict):
            config = {}
        self.combo_motor_axis.setCurrentText(config.get('motor_calib_axis', "Eje X (Líneas Verticales)"))
        motor_form.addRow("Eje:", self.combo_motor_axis)
        
        self.input_motor_dist_mm = QDoubleSpinBox()
        self.input_motor_dist_mm.setRange(0.01, 1000.0)
        self.input_motor_dist_mm.setSingleStep(1.0)
        self.input_motor_dist_mm.setValue(config.get('motor_calib_dist_mm', 1.0))
        motor_form.addRow("Distancia Motor (mm):", self.input_motor_dist_mm)
        
        self.input_motor_exp_time = QDoubleSpinBox()
        self.input_motor_exp_time.setRange(0.1, 3600.0)
        self.input_motor_exp_time.setValue(config.get('motor_exp_time', 10.0))
        self.input_motor_exp_time.setSingleStep(0.5)
        motor_form.addRow("Tiempo Exp. (s):", self.input_motor_exp_time)
        
        self.input_motor_line_width = QSpinBox()
        self.input_motor_line_width.setRange(1, 100)
        self.input_motor_line_width.setValue(config.get('motor_calib_line_width', 1))
        motor_form.addRow("Grosor de Línea (px):", self.input_motor_line_width)
        
        motor_layout.addLayout(motor_form)
        
        u_layout = QHBoxLayout()
        u_layout.addWidget(QLabel("Distancia U (px):"))
        self.btn_motor_u_minus = QPushButton("-")
        self.btn_motor_u_minus.setFixedWidth(30)
        u_layout.addWidget(self.btn_motor_u_minus)
        
        self.input_motor_u = QSpinBox()
        self.input_motor_u.setRange(1, 5000)
        self.input_motor_u.setValue(config.get('motor_px_per_mm', 150))
        u_layout.addWidget(self.input_motor_u)
        
        self.btn_motor_u_plus = QPushButton("+")
        self.btn_motor_u_plus.setFixedWidth(30)
        u_layout.addWidget(self.btn_motor_u_plus)
        motor_layout.addLayout(u_layout)
        
        mot_ctrl_layout = QHBoxLayout()
        self.btn_motor_move_mm = QPushButton("Mover motor")
        self.btn_motor_move_mm.setStyleSheet("font-weight: bold; background-color: #00BFA5; color: black;")
        mot_ctrl_layout.addWidget(self.btn_motor_move_mm)
        
        self.btn_motor_return = QPushButton("Volver al origen")
        mot_ctrl_layout.addWidget(self.btn_motor_return)
        motor_layout.addLayout(mot_ctrl_layout)
        
        proj_btn_layout = QHBoxLayout()
        self.btn_preview_motor = QPushButton("Proyectar")
        proj_btn_layout.addWidget(self.btn_preview_motor)
        
        self.btn_expose_motor = QPushButton("Iniciar exposición")
        self.btn_expose_motor.setStyleSheet("font-weight: bold; background-color: #00BFA5; color: black;")
        proj_btn_layout.addWidget(self.btn_expose_motor)
        
        self.btn_stop_motor_expose = QPushButton("Detener")
        proj_btn_layout.addWidget(self.btn_stop_motor_expose)
        motor_layout.addLayout(proj_btn_layout)
        
        self.btn_save_motor_calib = QPushButton("Guardar factor (solapamiento)")
        self.btn_save_motor_calib.setStyleSheet("font-weight: bold; color: #FFD700;")
        motor_layout.addWidget(self.btn_save_motor_calib)
        
        spatial_layout.addWidget(self.motor_container)
        spatial_layout.addSpacing(10)

        # Contenedor de calib manual (por defecto visible)
        self.manual_calib_container = QWidget()
        manual_layout = QVBoxLayout(self.manual_calib_container)
        manual_layout.setContentsMargins(0,0,0,0)
        
        help_label = QLabel("Dibuja una línea en la imagen y establece su tamaño real.")
        help_label.setWordWrap(True)
        help_label.setStyleSheet("color: #888888; font-style: italic;")
        manual_layout.addWidget(help_label)
        
        self.btn_load_pattern_calib = QPushButton("Cargar patrón de calibración")
        self.btn_load_pattern_calib.clicked.connect(self.load_calibration_pattern)
        manual_layout.addWidget(self.btn_load_pattern_calib)
        
        manual_layout.addSpacing(10)
        
        self.lbl_pixels_calib = QLabel("Distancia en Píxeles: 0.00")
        self.lbl_pixels_calib.setStyleSheet("font-weight: bold;")
        manual_layout.addWidget(self.lbl_pixels_calib)
        
        manual_layout.addWidget(QLabel("Medida real (mm):"))
        self.input_mm_calib = QLineEdit()
        self.input_mm_calib.setPlaceholderText("Ej. 10.5")
        self.input_mm_calib.textChanged.connect(self.calculate_spatial_scale)
        manual_layout.addWidget(self.input_mm_calib)
        
        self.lbl_result_calib = QLabel("Escala: -")
        self.lbl_result_calib.setStyleSheet("font-weight: bold; color: #00BFA5; font-size: 13px;")
        manual_layout.addWidget(self.lbl_result_calib)
        
        manual_layout.addStretch()
        
        self.btn_save_spatial_calib = QPushButton("Guardar calibración")
        self.btn_save_spatial_calib.clicked.connect(self.save_spatial_scale_from_ui)
        manual_layout.addWidget(self.btn_save_spatial_calib)
        
        spatial_layout.addWidget(self.manual_calib_container)
        
        def toggle_calib_mode(checked):
            self.motor_container.setVisible(checked)
            self.manual_calib_container.setVisible(not checked)
            if hasattr(self, "_spatial_cursor") and self._spatial_cursor:
                self._spatial_cursor.set_active(not checked)
                self.canvas.draw_idle()
            
        self.btn_toggle_motor_calib.toggled.connect(toggle_calib_mode)

        self.pattern_calib_stacked.addWidget(spatial_view)

        # --- VIEW 2: TIEMPO DE EXPOSICIÓN ---
        exposure_view = QWidget()
        exposure_layout = QVBoxLayout(exposure_view)
        exposure_layout.setSpacing(10)
        
        exp_help = QLabel("Genera una matriz dinámica para prueba de exposición óptima.")
        exp_help.setWordWrap(True)
        exp_help.setStyleSheet("color: #888888; font-style: italic;")
        exposure_layout.addWidget(exp_help)

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
        self.combo_exp_dir.addItems(["Horizontal", "Vertical", "Rectángulo Central", "Círculo Central", "Triángulo Central", "Líneas Múltiples (Horizontal)", "Líneas Múltiples (Vertical)"])
        self.combo_exp_dir.setCurrentText(config.get('exp_direction', "Horizontal"))
        form_layout.addRow("Dirección:", self.combo_exp_dir)

        self.combo_exp_mode = QComboBox()
        self.combo_exp_mode.addItems(["Decremento", "Incremento"])
        self.combo_exp_mode.setCurrentText(config.get('exp_mode', "Decremento"))
        form_layout.addRow("Modo:", self.combo_exp_mode)
        
        exposure_layout.addLayout(form_layout)
        
        # --- Parámetros de Rejilla (Ocultos por defecto) ---
        self.grating_container = QWidget()
        grating_form = QFormLayout(self.grating_container)
        grating_form.setContentsMargins(0, 0, 0, 0)
        
        self.input_grating_lines = QSpinBox()
        self.input_grating_lines.setRange(2, 500)
        self.input_grating_lines.setValue(config.get('grating_lines', 10))
        grating_form.addRow("Cant. Líneas:", self.input_grating_lines)
        
        self.input_grating_width = QSpinBox()
        self.input_grating_width.setRange(1, 1000)
        self.input_grating_width.setValue(config.get('grating_width', 10))
        grating_form.addRow("Grosor (px):", self.input_grating_width)
        
        self.input_grating_spacing = QSpinBox()
        self.input_grating_spacing.setRange(1, 1000)
        self.input_grating_spacing.setValue(config.get('grating_spacing', 10))
        grating_form.addRow("Espaciado (px):", self.input_grating_spacing)
        
        exposure_layout.addWidget(self.grating_container)
        self.grating_container.setVisible(False)
        
        def toggle_grating_params(text):
            is_grating = "Líneas Múltiples" in text
            self.grating_container.setVisible(is_grating)
            self.input_exp_stripes.setEnabled(not is_grating)
            if is_grating:
                self.input_exp_stripes.setValue(self.input_grating_lines.value())
            
        self.combo_exp_dir.currentTextChanged.connect(toggle_grating_params)
        toggle_grating_params(self.combo_exp_dir.currentText())
        # --------------------------------------------------
        
        self.lbl_exp_dimensions = QLabel("Dimensión por franja: -")
        self.lbl_exp_dimensions.setStyleSheet("color: #00BFA5; font-style: italic; font-size: 12px;")
        exposure_layout.addWidget(self.lbl_exp_dimensions)
        
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
        
        self.input_grating_lines.valueChanged.connect(on_param_changed)
        self.input_grating_width.valueChanged.connect(on_param_changed)
        self.input_grating_spacing.valueChanged.connect(on_param_changed)
        
        # Synchronize lines with stripes directly when changed
        def on_lines_changed(val):
            if "Líneas Múltiples" in self.combo_exp_dir.currentText():
                self.input_exp_stripes.setValue(val)
                
        self.input_grating_lines.valueChanged.connect(on_lines_changed)
        
        self.lbl_exp_status = QLabel("Estado: Inactivo")
        self.lbl_exp_status.setStyleSheet("font-weight: bold; color: #00BFA5;")
        exposure_layout.addWidget(self.lbl_exp_status)
        
        self.lbl_exp_time = QLabel("Tiempo transcurrido: 0.0 s")
        self.lbl_exp_time.setStyleSheet("font-weight: bold; color: #FFD700; font-size: 13px;")
        exposure_layout.addWidget(self.lbl_exp_time)
        
        exposure_layout.addStretch()

        self.btn_start_exp_matrix = QPushButton("Iniciar secuencia de exposición")
        self.btn_start_exp_matrix.setStyleSheet("font-weight: bold; background-color: #00BFA5; color: black;")
        self.btn_start_exp_matrix.clicked.connect(self.start_exposure_matrix)
        exposure_layout.addWidget(self.btn_start_exp_matrix)

        self.btn_stop_exp_matrix = QPushButton("Detener")
        self.btn_stop_exp_matrix.clicked.connect(self.stop_exposure_matrix)
        exposure_layout.addWidget(self.btn_stop_exp_matrix)

        self.pattern_calib_stacked.addWidget(exposure_view)

        # --- VIEW 3: TEST CD ---
        cd_view = QWidget()
        cd_layout = QVBoxLayout(cd_view)
        cd_layout.setSpacing(10)
        
        cd_help = QLabel("Proyecta un patrón progresivo para test de dimensión crítica.")
        cd_help.setWordWrap(True)
        cd_help.setStyleSheet("color: #888888; font-style: italic;")
        cd_layout.addWidget(cd_help)

        cd_form = QFormLayout()
        
        self.combo_cd_orient = QComboBox()
        self.combo_cd_orient.addItems(["Vertical", "Horizontal"])
        self.combo_cd_orient.setCurrentText(config.get('cd_orient', "Vertical"))
        cd_form.addRow("Orientación:", self.combo_cd_orient)

        self.input_cd_limit = QSpinBox()
        self.input_cd_limit.setRange(1, 500)
        self.input_cd_limit.setValue(config.get('cd_limit', 20))
        cd_form.addRow("Límite (px):", self.input_cd_limit)

        self.input_cd_spacing = QSpinBox()
        self.input_cd_spacing.setRange(1, 500)
        self.input_cd_spacing.setValue(config.get('cd_spacing', 10))
        cd_form.addRow("Separación (px):", self.input_cd_spacing)

        self.input_cd_exp_time = QDoubleSpinBox()
        self.input_cd_exp_time.setRange(0.1, 3600.0)
        self.input_cd_exp_time.setValue(config.get('cd_exp_time', 10.0))
        self.input_cd_exp_time.setSingleStep(0.5)
        cd_form.addRow("Tiempo Exp. (s):", self.input_cd_exp_time)

        cd_layout.addLayout(cd_form)
        
        self.chk_cd_invert = QCheckBox("Invertir figura y fondo")
        self.chk_cd_invert.setChecked(config.get('cd_invert', False))
        cd_layout.addWidget(self.chk_cd_invert)
        
        self.btn_save_cd_image = QPushButton("Guardar patrón como imagen")
        self.btn_save_cd_image.clicked.connect(self.save_cd_image)
        cd_layout.addWidget(self.btn_save_cd_image)
        
        cd_layout.addStretch()

        cd_btn_layout = QHBoxLayout()
        self.btn_preview_cd = QPushButton("Previsualizar")
        self.btn_preview_cd.clicked.connect(self.preview_cd_test)
        cd_btn_layout.addWidget(self.btn_preview_cd)

        self.btn_expose_cd = QPushButton("Iniciar exposición")
        self.btn_expose_cd.setStyleSheet("font-weight: bold; background-color: #00BFA5; color: black;")
        self.btn_expose_cd.clicked.connect(self.expose_cd_test)
        cd_btn_layout.addWidget(self.btn_expose_cd)
        
        self.btn_stop_cd_expose = QPushButton("Detener")
        self.btn_stop_cd_expose.clicked.connect(self.stop_cd_exposure)
        cd_btn_layout.addWidget(self.btn_stop_cd_expose)
        
        cd_layout.addLayout(cd_btn_layout)
        
        self.combo_cd_orient.currentIndexChanged.connect(on_param_changed)
        self.input_cd_limit.valueChanged.connect(on_param_changed)
        self.input_cd_spacing.valueChanged.connect(on_param_changed)
        self.input_cd_exp_time.valueChanged.connect(on_param_changed)
        self.chk_cd_invert.stateChanged.connect(on_param_changed)

        self.pattern_calib_stacked.addWidget(cd_view)

        main_layout.addWidget(self.pattern_calib_stacked)

        # Conectar botones
        self.btn_mode_spatial.clicked.connect(lambda: self._switch_pattern_calib_mode(0))
        self.btn_mode_exposure.clicked.connect(lambda: self._switch_pattern_calib_mode(1))
        self.btn_mode_cd.clicked.connect(lambda: self._switch_pattern_calib_mode(2))

        # Conectar eventos de motor
        self.btn_motor_u_minus.clicked.connect(lambda: self.input_motor_u.setValue(self.input_motor_u.value() - 1))
        self.btn_motor_u_plus.clicked.connect(lambda: self.input_motor_u.setValue(self.input_motor_u.value() + 1))
        self.input_motor_u.valueChanged.connect(self.render_motor_calib_pattern)
        self.combo_motor_axis.currentIndexChanged.connect(self.render_motor_calib_pattern)
        self.input_motor_line_width.valueChanged.connect(self.render_motor_calib_pattern)
        self.btn_toggle_motor_calib.toggled.connect(lambda state: self.render_motor_calib_pattern() if state else (self._update_pattern_calib_canvas(0) if hasattr(self, '_update_pattern_calib_canvas') else None))
        
        self.btn_motor_move_mm.clicked.connect(lambda: self.move_motor_calib(1))
        self.btn_motor_return.clicked.connect(lambda: self.move_motor_calib(-1))
        self.btn_save_motor_calib.clicked.connect(self.save_motor_calib)
        
        # Conectar preview y exposicion de motor calib
        self.btn_preview_motor.clicked.connect(self.preview_motor_calib)
        self.btn_expose_motor.clicked.connect(self.expose_motor_calib)
        self.btn_stop_motor_expose.clicked.connect(self.stop_motor_exposure)

    def _switch_pattern_calib_mode(self, index):
        """Cambia entre la vista de Tamaño Espacial y Tiempo de Exposición."""
        if hasattr(self, "btn_toggle_motor_calib"):
            self.btn_toggle_motor_calib.setChecked(False)
            
        self.pattern_calib_stacked.setCurrentIndex(index)
        self.btn_mode_spatial.setChecked(index == 0)
        self.btn_mode_exposure.setChecked(index == 1)
        if hasattr(self, "btn_mode_cd"):
            self.btn_mode_cd.setChecked(index == 2)
        if hasattr(self, "_update_pattern_calib_canvas"):
            self._update_pattern_calib_canvas(index)
