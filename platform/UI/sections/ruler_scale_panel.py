"""
Sección: 📏 REGLA DE ESCALA

Builder del panel lateral dedicado para la sección Regla de Escala.
Se construye en el sidebar principal pero se oculta por defecto;
se activa mediante el botón de la toolbar.

Métodos:
    _build_ruler_scale_section()  → construye widgets en un QWidget
"""
from PyQt5.QtWidgets import (
    QVBoxLayout, QHBoxLayout, QPushButton, QLabel, QLineEdit, QSpinBox,
    QWidget,
)
from PyQt5.QtCore import Qt
from UI.widget_helpers import create_stat_label


class RulerScalePanelBuilder:
    """Mixin: construye la sección de Regla de Escala."""

    def _build_ruler_scale_section(self) -> None:
        """Crea el panel completo de Regla de Escala como QWidget oculto."""
        self.ruler_panel_widget = QWidget()
        layout = QVBoxLayout(self.ruler_panel_widget)
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(8)

        title = QLabel("📏 REGLA DE ESCALA")
        title.setStyleSheet("font-weight: bold; font-size: 13px; color: #03DAC6;")
        layout.addWidget(title)

        # ── Panel informativo ────────────────────────────────────────────
        self.ruler_info_resolution = create_stat_label("Resolución: -")
        self.ruler_info_scale = create_stat_label("Escala: -")
        self.ruler_info_dim_mm = create_stat_label("Dimensión: -")
        self.ruler_info_dim_um = create_stat_label("Dimensión: -")

        layout.addWidget(self.ruler_info_resolution)
        layout.addWidget(self.ruler_info_scale)
        layout.addWidget(self.ruler_info_dim_mm)
        layout.addWidget(self.ruler_info_dim_um)

        # ── Separación ───────────────────────────────────────────────────
        sep_row = QHBoxLayout()
        sep_row.addWidget(QLabel("Separación (µm):"))
        self.ruler_separation_input = QLineEdit()
        self.ruler_separation_input.setPlaceholderText("Ej. 100")
        self.ruler_separation_input.setMaximumWidth(80)
        cfg = getattr(self, "_ruler_config", {})
        self.ruler_separation_input.setText(str(cfg.get("separation_um", 100.0)))
        self.ruler_separation_input.editingFinished.connect(self._on_ruler_param_changed)
        sep_row.addWidget(self.ruler_separation_input)
        sep_row.addStretch()
        layout.addLayout(sep_row)

        # ── Subdivisiones ────────────────────────────────────────────────
        sub_row = QHBoxLayout()
        sub_row.addWidget(QLabel("Subdivisiones:"))
        self.ruler_subdivisions_spin = QSpinBox()
        self.ruler_subdivisions_spin.setRange(1, 20)
        self.ruler_subdivisions_spin.setValue(cfg.get("subdivisions", 5))
        self.ruler_subdivisions_spin.setMaximumWidth(60)
        self.ruler_subdivisions_spin.valueChanged.connect(self._on_ruler_param_changed)
        sub_row.addWidget(self.ruler_subdivisions_spin)
        sub_row.addStretch()
        layout.addLayout(sub_row)

        # ── Ancho de línea grande ────────────────────────────────────────
        wl_row = QHBoxLayout()
        wl_row.addWidget(QLabel("Ancho línea grande (px):"))
        self.ruler_line_large_spin = QSpinBox()
        self.ruler_line_large_spin.setRange(1, 10)
        self.ruler_line_large_spin.setValue(cfg.get("line_width_large_px", 2))
        self.ruler_line_large_spin.setMaximumWidth(60)
        self.ruler_line_large_spin.valueChanged.connect(self._on_ruler_param_changed)
        wl_row.addWidget(self.ruler_line_large_spin)
        wl_row.addStretch()
        layout.addLayout(wl_row)

        # ── Ancho de línea pequeña ───────────────────────────────────────
        ws_row = QHBoxLayout()
        ws_row.addWidget(QLabel("Ancho línea pequeña (px):"))
        self.ruler_line_small_spin = QSpinBox()
        self.ruler_line_small_spin.setRange(1, 10)
        self.ruler_line_small_spin.setValue(cfg.get("line_width_small_px", 1))
        self.ruler_line_small_spin.setMaximumWidth(60)
        self.ruler_line_small_spin.valueChanged.connect(self._on_ruler_param_changed)
        ws_row.addWidget(self.ruler_line_small_spin)
        ws_row.addStretch()
        layout.addLayout(ws_row)

        # ── Altura línea grande (%) ──────────────────────────────────────
        ht_row = QHBoxLayout()
        ht_row.addWidget(QLabel("Altura línea grande (%):"))
        self.ruler_height_pct_spin = QSpinBox()
        self.ruler_height_pct_spin.setRange(10, 100)
        self.ruler_height_pct_spin.setValue(cfg.get("line_height_pct", 100))
        self.ruler_height_pct_spin.setMaximumWidth(60)
        self.ruler_height_pct_spin.valueChanged.connect(self._on_ruler_param_changed)
        ht_row.addWidget(self.ruler_height_pct_spin)
        ht_row.addStretch()
        layout.addLayout(ht_row)

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

        # ── Número de proyecciones ───────────────────────────────────────
        proj_row = QHBoxLayout()
        proj_row.addWidget(QLabel("Nº de proyecciones:"))
        self.ruler_num_proj_spin = QSpinBox()
        self.ruler_num_proj_spin.setRange(1, 50)
        self.ruler_num_proj_spin.setValue(cfg.get("num_projections", 1))
        self.ruler_num_proj_spin.setMaximumWidth(60)
        proj_row.addWidget(self.ruler_num_proj_spin)
        proj_row.addStretch()
        layout.addLayout(proj_row)

        # ── Botones de control ───────────────────────────────────────────
        self.ruler_preview_btn = QPushButton("🔍 Vista Previa")
        self.ruler_preview_btn.clicked.connect(self._on_ruler_preview)
        layout.addWidget(self.ruler_preview_btn)

        self.ruler_start_btn = QPushButton("▶ Iniciar Secuencia de Escala")
        self.ruler_start_btn.clicked.connect(self._on_ruler_start)
        layout.addWidget(self.ruler_start_btn)

        self.ruler_stop_btn = QPushButton("⏹ Detener")
        self.ruler_stop_btn.clicked.connect(self._on_ruler_stop)
        self.ruler_stop_btn.setVisible(False)
        layout.addWidget(self.ruler_stop_btn)

        # ── Estado ───────────────────────────────────────────────────────
        self.ruler_status_label = create_stat_label("Estado: Inactivo")
        layout.addWidget(self.ruler_status_label)

        layout.addStretch()

        # Oculto por defecto, se muestra al apretar el botón de la toolbar
        self.ruler_panel_widget.setVisible(False)

    # ── Callbacks ────────────────────────────────────────────────────────

    def _on_ruler_param_changed(self):
        if hasattr(self, "_sync_ruler_config_from_ui"):
            self._sync_ruler_config_from_ui()

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
