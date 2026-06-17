"""
Sección: REGLA DE ESCALA

Builder del panel lateral dedicado para la sección Regla de Escala.
Se construye en el sidebar principal pero se oculta por defecto;
se activa mediante el botón de la toolbar.

Métodos:
    _build_ruler_scale_section()  → construye widgets en un QWidget
"""

from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QPushButton, QLabel, 
    QLineEdit, QSpinBox, QComboBox, QFrame, QDoubleSpinBox
)
from PyQt5.QtCore import Qt
from UI.widget_helpers import create_stat_label
class RulerScalePanelBuilder:
    """Mixin: construye la sección de Regla de Escala."""

    def _build_ruler_scale_section(self) -> None:
        """Crea el panel completo de Regla de Escala envuelto en un QScrollArea."""
        from PyQt5.QtWidgets import QScrollArea
        
        self.ruler_panel_widget = QWidget()
        self.ruler_panel_widget.setVisible(False)
        
        main_layout = QVBoxLayout(self.ruler_panel_widget)
        main_layout.setContentsMargins(0, 0, 0, 0)
        
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.NoFrame if 'QFrame' in globals() else 0)
        
        content_widget = QWidget()
        layout = QVBoxLayout(content_widget)
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(8)
        
        scroll.setWidget(content_widget)
        main_layout.addWidget(scroll)

        title = QLabel(" Regla de escala")
        title.setStyleSheet("font-weight: bold; font-size: 13px; color: #A0A0A0;")
        layout.addWidget(title)

        # ── Panel informativo ────────────────────────────────────────────
        self.ruler_info_resolution = create_stat_label("Resolución: -")
        self.ruler_info_scale = create_stat_label("Escala: -")
        self.ruler_info_pixel_size = create_stat_label("Tamaño píxel: -")
        self.ruler_info_dim_mm = create_stat_label("Dimensión: -")
        self.ruler_info_dim_um = create_stat_label("Dimensión: -")

        layout.addWidget(self.ruler_info_resolution)
        layout.addWidget(self.ruler_info_scale)
        layout.addWidget(self.ruler_info_pixel_size)
        layout.addWidget(self.ruler_info_dim_mm)
        layout.addWidget(self.ruler_info_dim_um)

        # ── Separación ───────────────────────────────────────────────────
        sep_row = QHBoxLayout()
        sep_row.addWidget(QLabel("Separación (px):"))
        self.ruler_separation_input = QLineEdit()
        self.ruler_separation_input.setPlaceholderText("Ej. 100")
        self.ruler_separation_input.setMaximumWidth(80)
        cfg = getattr(self, "_ruler_config", {})
        self.ruler_separation_input.setText(str(cfg.get("separation_px", 100)))
        self.ruler_separation_input.editingFinished.connect(self._on_ruler_param_changed)
        sep_row.addWidget(self.ruler_separation_input)
        
        self.lbl_ruler_sep_um = QLabel("~ - µm")
        self.lbl_ruler_sep_um.setStyleSheet("color: #888888; font-style: italic;")
        sep_row.addWidget(self.lbl_ruler_sep_um)
        
        sep_row.addStretch()
        layout.addLayout(sep_row)

        # ── Subdivisiones ────────────────────────────────────────────────
        sub_row = QHBoxLayout()
        sub_row.addWidget(QLabel("Subdivisiones:"))
        self.ruler_subdivisions_spin = QSpinBox()
        self.ruler_subdivisions_spin.setRange(0, 20)
        self.ruler_subdivisions_spin.setValue(cfg.get("subdivisions", 5))
        self.ruler_subdivisions_spin.setMaximumWidth(60)
        self.ruler_subdivisions_spin.valueChanged.connect(self._on_ruler_param_changed)
        sub_row.addWidget(self.ruler_subdivisions_spin)
        sub_row.addStretch()
        layout.addLayout(sub_row)

        # ── Ancho grande línea ────────────────────────────────────────
        wl_row = QHBoxLayout()
        wl_row.addWidget(QLabel("Ancho grande línea (px):"))
        self.ruler_line_large_spin = QSpinBox()
        self.ruler_line_large_spin.setRange(1, 100)
        self.ruler_line_large_spin.setValue(cfg.get("line_width_large_px", 2))
        self.ruler_line_large_spin.setMaximumWidth(60)
        self.ruler_line_large_spin.valueChanged.connect(self._on_ruler_param_changed)
        wl_row.addWidget(self.ruler_line_large_spin)
        wl_row.addStretch()
        layout.addLayout(wl_row)

        # ── Ancho línea subdivisiones ───────────────────────────────────────
        ws_row = QHBoxLayout()
        ws_row.addWidget(QLabel("Ancho línea subdivisiones (px):"))
        self.ruler_line_small_spin = QSpinBox()
        self.ruler_line_small_spin.setRange(1, 100)
        self.ruler_line_small_spin.setValue(cfg.get("line_width_small_px", 1))
        self.ruler_line_small_spin.setMaximumWidth(60)
        self.ruler_line_small_spin.valueChanged.connect(self._on_ruler_param_changed)
        ws_row.addWidget(self.ruler_line_small_spin)
        ws_row.addStretch()
        layout.addLayout(ws_row)

        # ── Altura línea grande (%) y (px) ──────────────────────────────────────
        ht_row = QHBoxLayout()
        ht_row.addWidget(QLabel("Altura línea grande:"))
        self.ruler_height_pct_spin = QSpinBox()
        self.ruler_height_pct_spin.setRange(1, 100)
        self.ruler_height_pct_spin.setSuffix(" %")
        self.ruler_height_pct_spin.setValue(cfg.get("line_height_pct", 100))
        self.ruler_height_pct_spin.setMaximumWidth(70)
        
        self.ruler_height_px_spin = QSpinBox()
        self.ruler_height_px_spin.setRange(1, 4000)
        self.ruler_height_px_spin.setSuffix(" px")
        self.ruler_height_px_spin.setMaximumWidth(80)
        
        # Sincronizar porcentaje y pixeles
        self.ruler_height_pct_spin.valueChanged.connect(self._on_height_pct_changed)
        self.ruler_height_px_spin.valueChanged.connect(self._on_height_px_changed)
        
        ht_row.addWidget(self.ruler_height_pct_spin)
        ht_row.addWidget(self.ruler_height_px_spin)
        ht_row.addStretch()
        layout.addLayout(ht_row)

        # ── Alineación ───────────────────────────────────────────────────
        align_row = QHBoxLayout()
        align_row.addWidget(QLabel("Alineación:"))
        self.ruler_alignment_combo = QComboBox()
        self.ruler_alignment_combo.addItems(["Centro", "Abajo", "Arriba"])
        self.ruler_alignment_combo.setCurrentText(cfg.get("alignment", "Centro"))
        self.ruler_alignment_combo.currentTextChanged.connect(self._on_ruler_param_changed)
        align_row.addWidget(self.ruler_alignment_combo)
        align_row.addStretch()
        layout.addLayout(align_row)

        # ── Margen Origen ────────────────────────────────────────────────
        offset_row = QHBoxLayout()
        offset_row.addWidget(QLabel("Margen Origen (px):"))
        self.ruler_offset_spin = QSpinBox()
        self.ruler_offset_spin.setRange(0, 500)
        self.ruler_offset_spin.setValue(cfg.get("offset_x", 0))
        self.ruler_offset_spin.setMaximumWidth(60)
        self.ruler_offset_spin.valueChanged.connect(self._on_ruler_param_changed)
        offset_row.addWidget(self.ruler_offset_spin)
        offset_row.addStretch()
        layout.addLayout(offset_row)



        # ── Tiempo de exposición ─────────────────────────────────────────
        exp_row = QHBoxLayout()
        exp_row.addWidget(QLabel("Tiempo exposición (s):"))
        self.ruler_exposure_time_input = QLineEdit()
        self.ruler_exposure_time_input.setPlaceholderText("Ej. 10")
        self.ruler_exposure_time_input.setMaximumWidth(80)
        self.ruler_exposure_time_input.setText(str(cfg.get("exposure_time_s", 10.0)))
        exp_row.addWidget(self.ruler_exposure_time_input)
        exp_row.addStretch()
        layout.addLayout(exp_row)



        # ── Secuencia Step and Repeat ────────────────────────────────────
        proj_row = QHBoxLayout()
        proj_row.addWidget(QLabel("Nº de proyecciones:"))
        self.ruler_num_proj_spin = QSpinBox()
        self.ruler_num_proj_spin.setRange(1, 1000)
        self.ruler_num_proj_spin.setValue(cfg.get("num_projections", 1))
        self.ruler_num_proj_spin.setMaximumWidth(60)
        self.ruler_num_proj_spin.valueChanged.connect(self._on_ruler_param_changed)
        proj_row.addWidget(self.ruler_num_proj_spin)
        proj_row.addStretch()
        layout.addLayout(proj_row)
        
        proj_sep_row = QHBoxLayout()
        proj_sep_row.addWidget(QLabel("Separación Motor (mm):"))
        self.ruler_motor_sep_spin = QDoubleSpinBox()
        self.ruler_motor_sep_spin.setRange(0.00, 1000.0)
        self.ruler_motor_sep_spin.setDecimals(3)
        self.ruler_motor_sep_spin.setSingleStep(0.1)
        self.ruler_motor_sep_spin.setValue(cfg.get("motor_sep_mm", 1.0))
        self.ruler_motor_sep_spin.setMaximumWidth(80)
        self.ruler_motor_sep_spin.valueChanged.connect(self._on_ruler_param_changed)
        proj_sep_row.addWidget(self.ruler_motor_sep_spin)
        proj_sep_row.addStretch()
        layout.addLayout(proj_sep_row)

        self.lbl_ruler_total_len = QLabel("Largo Total a recorrer: - mm")
        layout.addWidget(self.lbl_ruler_total_len)

        layout.addSpacing(10)

        # ── Botones de control ───────────────────────────────────────────
        self.ruler_preview_btn = QPushButton("Vista previa")
        self.ruler_preview_btn.clicked.connect(self._on_ruler_preview)
        layout.addWidget(self.ruler_preview_btn)

        self.ruler_start_btn = QPushButton("Iniciar secuencia de escala")
        self.ruler_start_btn.clicked.connect(self._on_ruler_start)
        layout.addWidget(self.ruler_start_btn)

        self.ruler_stop_btn = QPushButton("Detener")
        self.ruler_stop_btn.clicked.connect(self._on_ruler_stop)
        self.ruler_stop_btn.setVisible(False)
        layout.addWidget(self.ruler_stop_btn)

        layout.addSpacing(10)

        self.ruler_connect_btn = QPushButton("Conectar Motor")
        self.ruler_connect_btn.clicked.connect(self._on_ruler_connect_motor)
        layout.addWidget(self.ruler_connect_btn)

        # ── Estado ───────────────────────────────────────────────────────
        self.ruler_status_label = create_stat_label("Estado: Inactivo")
        layout.addWidget(self.ruler_status_label)

        layout.addStretch()

    # ── Callbacks ────────────────────────────────────────────────────────

    def _on_ruler_param_changed(self):
        if hasattr(self, "_sync_ruler_config_from_ui"):
            self._sync_ruler_config_from_ui()
        if hasattr(self, "update_ruler_info_panel"):
            self.update_ruler_info_panel()

    def _on_height_pct_changed(self, val):
        if hasattr(self, "_ruler_get_dims"):
            dims = self._ruler_get_dims()
            if dims:
                _, h = dims
                px = int(h * val / 100.0)
                self.ruler_height_px_spin.blockSignals(True)
                self.ruler_height_px_spin.setValue(px)
                self.ruler_height_px_spin.blockSignals(False)
        self._on_ruler_param_changed()

    def _on_height_px_changed(self, val):
        if hasattr(self, "_ruler_get_dims"):
            dims = self._ruler_get_dims()
            if dims:
                _, h = dims
                if h > 0:
                    pct = int(val * 100.0 / h)
                    pct = max(1, min(100, pct))
                    self.ruler_height_pct_spin.blockSignals(True)
                    self.ruler_height_pct_spin.setValue(pct)
                    self.ruler_height_pct_spin.blockSignals(False)
        self._on_ruler_param_changed()

    def _on_ruler_preview(self):
        self._on_ruler_param_changed()
        if hasattr(self, "preview_ruler_image"):
            self.preview_ruler_image()

    def _on_ruler_start(self):
        self._on_ruler_param_changed()
        if hasattr(self, "start_ruler_sequence"):
            self.start_ruler_sequence()

    def _on_ruler_stop(self):
        if hasattr(self, "stop_ruler_sequence"):
            self.stop_ruler_sequence()

    def _on_ruler_connect_motor(self):
        # Si ya esta conectado desde Motores, reusar la conexion
        controller = getattr(self, "motor_controller_instance", None)
        if controller and getattr(controller, "ser", None):
            self._ruler_update_status("Motor conectado")
            return
        
        # Si no, intentar conectar
        if hasattr(self, "connect_motors_sidebar"):
            self.connect_motors_sidebar()
            controller = getattr(self, "motor_controller_instance", None)
            if controller and getattr(controller, "ser", None):
                self._ruler_update_status("Motor conectado")
            else:
                self._ruler_update_status("No se pudo conectar")
