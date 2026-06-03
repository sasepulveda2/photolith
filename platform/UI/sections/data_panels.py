"""
Secciones de datos del sidebar: DATA, BINARIO y ESTADÍSTICAS GRID.

Métodos:
    _build_stats_section()       → 📊 estadísticas de imagen/proyector
    _build_binary_section()      → ⚫⚪ modo binario + inversión
    _build_grid_stats_section()  → 📏 info de solo lectura del grid
"""
from PyQt5.QtWidgets import QVBoxLayout, QHBoxLayout, QLabel, QSlider, QCheckBox, QLineEdit
from PyQt5.QtCore import Qt
from UI.collapsible_section import CollapsibleSection
from UI.widget_helpers import (
    create_section_content, create_stat_label, create_stat_labels_batch,
)
from constants import (
    SECTION_CONTENT_SPACING_EXTRA,
    INPUT_FIELD_NARROW_MAX_WIDTH,
    BINARY_THRESHOLD_SLIDER_MIN, BINARY_THRESHOLD_SLIDER_MAX,
)


class DataPanelsBuilder:
    """Mixin: construye las secciones de datos (stats, binario, grid stats)."""

    def _build_stats_section(self) -> None:
        """📊 DATA — estadísticas de la imagen cargada y del proyector activo."""
        self.stats_section = CollapsibleSection("📊 DATA", self, expanded=True)
        content, layout = create_section_content()

        self.resolution_label          = QLabel("Resolución: -")
        self.min_label                 = QLabel("Intensidad mínima: -")
        self.avg_label                 = QLabel("Intensidad promedio: -")
        self.max_label                 = QLabel("Intensidad máxima: -")
        self.scale_info_label          = QLabel("Escala proyección: -")
        self.projected_resolution_label= QLabel("Resolución proyectada: -")
        self.monitor_resolution_label  = QLabel("Monitor proyección: -")
        self.calibration_status_label  = QLabel("Calibración: Inactiva")

        # Spatial calibration labels
        self.pixel_scale_label = QLabel("Escala: No calibrada")
        self.image_physical_size_label = QLabel("Tamaño físico: -")

        # Visibilidad inicial
        self.scale_info_label.setVisible(False)
        self.projected_resolution_label.setVisible(False)

        # Actualizar estado de calibración si ya está disponible
        if hasattr(self, "apply_attenuation_to_grid"):
            self.calibration_status_label.setText(
                f"Calibración: {'✓ Activa' if self.apply_attenuation_to_grid else 'Inactiva'}"
            )

        for lbl in (
            self.resolution_label, self.min_label, self.avg_label, self.max_label,
            self.scale_info_label, self.projected_resolution_label,
            self.monitor_resolution_label, self.calibration_status_label,
            self.pixel_scale_label, self.image_physical_size_label,
        ):
            lbl.setObjectName("statLabel")
            layout.addWidget(lbl)

        self.stats_section.setContentWidget(content)
        self.info_layout.addWidget(self.stats_section)

    def _build_binary_section(self) -> None:
        """⚫⚪ BINARIO — modo binario estricto (0/1) e inversión de intensidad."""
        self.binary_section = CollapsibleSection("⚫⚪ BINARIO", self, expanded=True)
        content, layout = create_section_content(spacing=SECTION_CONTENT_SPACING_EXTRA)

        # Activar modo binario
        self.binary_mode_check = QCheckBox("Activar Modo Binario (0/1)")
        self.binary_mode_check.setChecked(self.binary_mode_enabled)
        self.binary_mode_check.stateChanged.connect(self.toggle_binary_mode)
        self.binary_mode_check.setObjectName("statLabel")
        layout.addWidget(self.binary_mode_check)

        self.binary_status_label = create_stat_label(
            f"Estado: {'✓ Activo' if self.binary_mode_enabled else '✗ Inactivo'}"
        )
        layout.addWidget(self.binary_status_label)

        # Inversión de color
        self.invert_check = QCheckBox("Invertir Color (Negativo)")
        self.invert_check.setChecked(self.invert_projection)
        self.invert_check.stateChanged.connect(self.toggle_intensity_inversion)
        self.invert_check.setObjectName("statLabel")
        layout.addWidget(self.invert_check)

        # Control de umbral (threshold)
        layout.addWidget(create_stat_label("Umbral (Threshold):"))

        threshold_row = QHBoxLayout()
        self.binary_threshold_slider = QSlider(Qt.Horizontal)
        self.binary_threshold_slider.setMinimum(BINARY_THRESHOLD_SLIDER_MIN)
        self.binary_threshold_slider.setMaximum(BINARY_THRESHOLD_SLIDER_MAX)
        self.binary_threshold_slider.setValue(int(self.binary_threshold))
        self.binary_threshold_slider.valueChanged.connect(
            self.update_binary_threshold_from_slider
        )
        self.binary_threshold_input = QLineEdit(str(self.binary_threshold))
        self.binary_threshold_input.setMaximumWidth(INPUT_FIELD_NARROW_MAX_WIDTH)
        self.binary_threshold_input.returnPressed.connect(
            self.update_binary_threshold_from_input
        )
        threshold_row.addWidget(self.binary_threshold_slider)
        threshold_row.addWidget(self.binary_threshold_input)
        threshold_row.addWidget(QLabel("%"))
        layout.addLayout(threshold_row)

        self.binary_section.setContentWidget(content)
        self.info_layout.addWidget(self.binary_section)

    def _build_grid_stats_section(self) -> None:
        """📏 ESTADÍSTICAS GRID — info de solo lectura del grid activo (oculta por defecto)."""
        self.grid_stats_section = CollapsibleSection(
            "📏 ESTADÍSTICAS GRID", self, expanded=False
        )
        content, layout = create_section_content()

        create_stat_labels_batch(self, [
            ("grid_dimensions_label",  "Dimensiones: -"),
            ("grid_cells_x_label",     "Celdas X: -"),
            ("grid_cells_y_label",     "Celdas Y: -"),
            ("grid_cell_size_label",   "Tamaño celda: -"),
            ("grid_pixels_label",      "Píxeles/celda: -"),
            ("grid_resolution_label",  "Resolución: -"),
            ("grid_pixel_size_label",  "Tamaño píxel: -"),
            ("grid_total_cells_label", "Total celdas: -"),
            ("grid_color_label",       "Color: -"),
        ], layout)

        self.grid_stats_section.setContentWidget(content)
        self.grid_stats_section.setVisible(False)
        self.info_layout.addWidget(self.grid_stats_section)
