"""
Sección: 🔍 MONITOREO DE CALIBRACIÓN.

Métodos:
    _build_calibration_monitor()          → sección principal
    _build_calib_status_labels()          → labels de estado y efectos
    _build_calib_preview_canvas()         → canvas matplotlib + slider intensidad
    _build_calib_orientation_controls()   → checkboxes flip X/Y
"""
from PyQt5.QtWidgets import QVBoxLayout, QHBoxLayout, QSlider, QCheckBox
from PyQt5.QtCore import Qt
from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg as FigureCanvas
from matplotlib.figure import Figure
from UI.collapsible_section import CollapsibleSection
from UI.widget_helpers import (
    create_section_content, create_stat_label, create_description_label,
    create_section_title_label, create_info_label, create_modern_button,
)
from constants import (
    CALIB_PREVIEW_FIGSIZE, CALIB_PREVIEW_DPI,
    CALIB_PREVIEW_MIN_HEIGHT, CALIB_PREVIEW_MAX_HEIGHT,
    CALIB_PREVIEW_STRENGTH_DEFAULT, CALIB_PREVIEW_STRENGTH_MIN_WIDTH,
    STYLE_SMALL_10PX,
)


class CalibrationPanelBuilder:
    """Mixin: construye la sección de monitoreo de calibración."""

    def _build_calibration_monitor(self) -> None:
        """🔍 MONITOREO DE CALIBRACIÓN — estado en tiempo real de efectos y preview."""
        self.calibration_monitor_section = CollapsibleSection(
            "📐 CALIBRACIÓN DE MONITOR", self, expanded=False, section_id="calib_monitor"
        )
        content, layout = create_section_content()

        layout.addWidget(create_description_label(
            "Estado en tiempo real de efectos aplicados a la proyección"
        ))

        self._build_calib_status_labels(layout)
        self._build_calib_preview_canvas(layout)
        self._build_calib_orientation_controls(layout)

        update_btn = create_modern_button(
            "🔄 Actualizar Monitor",
            slot=self.update_calibration_monitor,
            tooltip="Actualiza la información del monitor de calibración",
        )
        layout.addWidget(update_btn)

        self.calibration_monitor_section.setContentWidget(content)
        self.info_layout.addWidget(self.calibration_monitor_section)

    def _build_calib_status_labels(self, layout: QVBoxLayout) -> None:
        """Labels de estado de calibración, atenuación y efectos activos."""
        # Estado de calibración
        layout.addWidget(create_section_title_label("📊 Estado de Calibración:"))
        self.calib_status_label = create_info_label("❌ Sin calibración cargada", "#FF6B6B")
        layout.addWidget(self.calib_status_label)
        self.calib_apply_status_label = create_info_label("⚪ Aplicación: Inactiva")
        layout.addWidget(self.calib_apply_status_label)

        # Parámetros de atenuación
        layout.addWidget(create_section_title_label("🔧 Parámetros de Atenuación:"))
        attenuation_labels = [
            ("atten_threshold_label", "• Threshold: -"),
            ("atten_min_label",       "• Valor mínimo: -"),
            ("atten_max_label",       "• Valor máximo: -"),
        ]
        for attr, text in attenuation_labels:
            lbl = create_info_label(text)
            setattr(self, attr, lbl)
            layout.addWidget(lbl)

        # Efectos activos
        layout.addWidget(create_section_title_label("⚡ Efectos Activos:"))
        effect_labels = [
            ("effect_sigma_label",      "• Sigma (Blur): -"),
            ("effect_downscale_label",  "• Downscaling: -"),
            ("effect_brightness_label", "• Brillo: -"),
            ("effect_binary_label",     "• Modo Binario: -"),
            ("effect_invert_label",     "• Inversión: -"),
        ]
        for attr, text in effect_labels:
            lbl = create_info_label(text)
            setattr(self, attr, lbl)
            layout.addWidget(lbl)

        # Última proyección
        layout.addWidget(create_section_title_label("🖥️ Última Proyección:"))
        projection_labels = [
            ("last_projection_size_label",   "• Tamaño: -"),
            ("last_projection_values_label", "• Valores: -"),
        ]
        for attr, text in projection_labels:
            lbl = create_info_label(text)
            setattr(self, attr, lbl)
            layout.addWidget(lbl)

    def _build_calib_preview_canvas(self, layout: QVBoxLayout) -> None:
        """Canvas matplotlib de preview antes/después de calibración con slider de intensidad."""
        layout.addWidget(create_section_title_label("🔬 Preview Calibración:"))

        self.calib_preview_figure = Figure(
            figsize=CALIB_PREVIEW_FIGSIZE, dpi=CALIB_PREVIEW_DPI,
        )
        self.calib_preview_canvas = FigureCanvas(self.calib_preview_figure)
        self.calib_preview_canvas.setMinimumHeight(CALIB_PREVIEW_MIN_HEIGHT)
        self.calib_preview_canvas.setMaximumHeight(CALIB_PREVIEW_MAX_HEIGHT)
        layout.addWidget(self.calib_preview_canvas)

        strength_row = QHBoxLayout()
        strength_lbl = create_stat_label("Intensidad:")
        strength_lbl.setStyleSheet(STYLE_SMALL_10PX)
        self.calib_preview_strength_slider = QSlider(Qt.Horizontal)
        self.calib_preview_strength_slider.setMinimum(0)
        self.calib_preview_strength_slider.setMaximum(CALIB_PREVIEW_STRENGTH_DEFAULT)
        self.calib_preview_strength_slider.setValue(CALIB_PREVIEW_STRENGTH_DEFAULT)
        self.calib_preview_strength_slider.setToolTip(
            "Ajusta la intensidad de la calibración en el preview"
        )
        self.calib_preview_strength_slider.valueChanged.connect(
            self.update_calibration_preview
        )
        self.calib_preview_strength_value = create_stat_label("100%")
        self.calib_preview_strength_value.setStyleSheet(
            f"{STYLE_SMALL_10PX} min-width: {CALIB_PREVIEW_STRENGTH_MIN_WIDTH}px;"
        )
        strength_row.addWidget(strength_lbl)
        strength_row.addWidget(self.calib_preview_strength_slider)
        strength_row.addWidget(self.calib_preview_strength_value)
        layout.addLayout(strength_row)

        preview_btns = QHBoxLayout()
        self.calib_show_before_btn = create_modern_button(
            "👁️ Ver Original",
            slot=lambda: self.update_calibration_preview(show_mode="before"),
            tooltip="Muestra la imagen sin calibración",
        )
        self.calib_show_after_btn = create_modern_button(
            "✨ Ver Calibrado",
            slot=lambda: self.update_calibration_preview(show_mode="after"),
            tooltip="Muestra la imagen con calibración aplicada",
        )
        preview_btns.addWidget(self.calib_show_before_btn)
        preview_btns.addWidget(self.calib_show_after_btn)
        layout.addLayout(preview_btns)

    def _build_calib_orientation_controls(self, layout: QVBoxLayout) -> None:
        """Checkboxes de orientación (flip X/Y) de la matriz de calibración."""
        layout.addWidget(create_section_title_label("🔄 Orientación de Matriz:"))

        flip_row = QHBoxLayout()
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

        flip_row.addWidget(self.calib_flip_x_checkbox)
        flip_row.addWidget(self.calib_flip_y_checkbox)
        layout.addLayout(flip_row)
