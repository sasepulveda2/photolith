"""
Secciones del sidebar relacionadas con el grid:
    🖼️ IMAGEN EN GRID y 📏 CONFIGURACIÓN GRID.

Métodos:
    _build_image_coords_section()  → posición, arrastre, grabación
    _build_grid_config_section()   → dimensiones, píxeles/celda, generación
"""
from PyQt5.QtWidgets import QVBoxLayout, QHBoxLayout, QPushButton, QCheckBox, QComboBox
from UI.collapsible_section import CollapsibleSection
from UI.widget_helpers import (
    create_section_content, create_stat_label, create_stat_labels_batch,
    create_input_row,
)
from constants import (
    INPUT_FIELD_NARROW_MAX_WIDTH,
    BUTTON_MIN_HEIGHT_LARGE, BUTTON_MIN_HEIGHT_XLARGE,
    GRID_UNITS, DRAG_MODES,
)


class GridPanelsBuilder:
    """Mixin: construye las secciones de grid (coordenadas + configuración)."""

    def _build_image_coords_section(self) -> None:
        """🖼️ IMAGEN EN GRID — posición, modo de arrastre y grabación de movimientos."""
        self.image_coords_section = CollapsibleSection(
            "Coordenadas originales", self, expanded=True, section_id="image_coords"
        )
        content, layout = create_section_content()

        # Modo de arrastre
        drag_row = QHBoxLayout()
        drag_row.addWidget(create_stat_label("Modo:"))
        self.drag_mode_combo = QComboBox()
        self.drag_mode_combo.addItems(DRAG_MODES)
        self.drag_mode_combo.setCurrentIndex(0)
        self.drag_mode_combo.currentIndexChanged.connect(self.change_drag_mode)
        drag_row.addWidget(self.drag_mode_combo)
        layout.addLayout(drag_row)

        # Coordenadas de las cuatro esquinas de la imagen
        create_stat_labels_batch(self, [
            ("coord_top_left_label",     "Superior Izq: -"),
            ("coord_top_right_label",    "Superior Der: -"),
            ("coord_bottom_left_label",  "Inferior Izq: -"),
            ("coord_bottom_right_label", "Inferior Der: -"),
        ], layout)

        # Grabación de movimiento
        self.record_button = QPushButton("Grabar movimiento")
        self.record_button.clicked.connect(self.toggle_recording)
        self.record_button.setObjectName("modernButton")
        self.record_button.setMinimumHeight(BUTTON_MIN_HEIGHT_LARGE)
        layout.addWidget(self.record_button)

        self.play_button = QPushButton("Reproducir")
        self.play_button.clicked.connect(self.play_movement)
        self.play_button.setEnabled(False)
        layout.addWidget(self.play_button)

        self.recorded_positions_label = create_stat_label("Posiciones grabadas: 0")
        layout.addWidget(self.recorded_positions_label)

        self.image_coords_section.setContentWidget(content)
        self.image_coords_section.setVisible(False)
        self.info_layout.addWidget(self.image_coords_section)

    def _build_grid_config_section(self) -> None:
        """📏 CONFIGURACIÓN GRID — dimensiones, píxeles por celda, unidad y generación."""
        self.grid_config_section = CollapsibleSection(
            "Configuración de grid", self, expanded=True, section_id="grid_config"
        )
        content, layout = create_section_content()

        # Dimensiones del grid
        row_w, self.grid_width_input   = create_input_row("Ancho (W):",     self.grid_width)
        row_h, self.grid_height_input  = create_input_row("Alto (H):",      self.grid_height)
        row_c, self.grid_cell_input    = create_input_row("Tamaño celda:",  self.grid_cell_size)
        row_p, self.grid_pixels_input  = create_input_row("Píxeles/celda:", self.grid_pixels_per_cell)
        for row in (row_w, row_h, row_c, row_p):
            layout.addLayout(row)

        # Unidad de medida
        unit_row = QHBoxLayout()
        unit_row.addWidget(create_stat_label("Unidad:"))
        self.grid_unit_combo = QComboBox()
        self.grid_unit_combo.addItems(GRID_UNITS)
        self.grid_unit_combo.setCurrentText(self.grid_unit)
        self.grid_unit_combo.setMaximumWidth(INPUT_FIELD_NARROW_MAX_WIDTH + 30)
        unit_row.addWidget(self.grid_unit_combo)
        unit_row.addStretch()
        layout.addLayout(unit_row)

        # Mostrar grid de píxeles
        self.show_pixel_grid_checkbox = QCheckBox("Mostrar grid de píxeles")
        self.show_pixel_grid_checkbox.setChecked(self.show_pixel_grid)
        self.show_pixel_grid_checkbox.stateChanged.connect(self.toggle_pixel_grid)
        self.show_pixel_grid_checkbox.setObjectName("statLabel")
        layout.addWidget(self.show_pixel_grid_checkbox)

        # Generar grid
        self.generate_grid_button = QPushButton("Generar grid")
        self.generate_grid_button.clicked.connect(self.generate_grid)
        self.generate_grid_button.setObjectName("modernButton")
        self.generate_grid_button.setMinimumHeight(BUTTON_MIN_HEIGHT_XLARGE)
        layout.addWidget(self.generate_grid_button)

        self.grid_status_label = create_stat_label("Estado: No generado")
        layout.addWidget(self.grid_status_label)

        self.grid_config_section.setContentWidget(content)
        self.grid_config_section.setVisible(False)
        self.info_layout.addWidget(self.grid_config_section)
