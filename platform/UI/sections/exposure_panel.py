"""
Secciones: ⏱️ EXPOSICIÓN + 〜 FRECUENCIA.

Métodos:
    _build_exposure_frequency_tabs()  → tabs de selección
    _build_exposure_section()         → tiempo, intensidad, ciclos, start/stop
    _build_frequency_section()        → valor, unidad, duración, start/stop
"""
from PyQt5.QtWidgets import (
    QVBoxLayout, QHBoxLayout, QPushButton, QCheckBox, QLineEdit, QComboBox,
)
from UI.collapsible_section import CollapsibleSection
from UI.widget_helpers import (
    create_section_content, create_stat_label, create_text_input_row,
)
from constants import (
    INPUT_FIELD_NARROW_MAX_WIDTH,
    FREQUENCY_UNITS,
)


class ExposurePanelBuilder:
    """Mixin: construye las secciones de exposición y frecuencia."""

    def _build_exposure_frequency_tabs(self) -> None:
        """Crea los botones de tab para alternar entre Exposición y Frecuencia."""
        tabs_row = QHBoxLayout()
        self.exposure_tab_button = QPushButton("⏱️ EXPOSICIÓN")
        self.exposure_tab_button.setCheckable(True)
        self.exposure_tab_button.setChecked(True)
        self.exposure_tab_button.clicked.connect(self.show_exposure_section)
        self.exposure_tab_button.setObjectName("tabButton")

        self.frequency_tab_button = QPushButton(" FRECUENCIA")
        self.frequency_tab_button.setCheckable(True)
        self.frequency_tab_button.clicked.connect(self.show_frequency_section)
        self.frequency_tab_button.setObjectName("tabButton")

        tabs_row.addWidget(self.exposure_tab_button)
        tabs_row.addWidget(self.frequency_tab_button)
        self.info_layout.addLayout(tabs_row)

    def _build_exposure_section(self) -> None:
        """⏱️ EXPOSICIÓN — tiempo, intensidad, ciclos y controles de start/stop."""
        self.exposure_section = CollapsibleSection(
            "⏱️ EXPOSICIÓN", self, expanded=True
        )
        content, layout = create_section_content()

        # Campos de entrada
        row_time, self.exposure_time_input = create_text_input_row(
            "Tiempo (segundos):", "10", "Ej: 5",
        )
        row_intensity, self.exposure_intensity_input = create_text_input_row(
            "Intensidad (%):", "100", "0-100",
        )
        row_cycles, self.exposure_cycles_input = create_text_input_row(
            "Ciclos:", "1", "Ej: 3",
        )
        layout.addLayout(row_time)
        layout.addLayout(row_intensity)
        layout.addLayout(row_cycles)

        # Espejo de exposición
        self.mirror_exposure_checkbox = QCheckBox("🪞 Espejo (Invertir Proyección)")
        self.mirror_exposure_checkbox.setChecked(False)
        self.mirror_exposure_checkbox.toggled.connect(self.toggle_exposure_mirror)
        layout.addWidget(self.mirror_exposure_checkbox)

        # Proyectar imagen completa manualmente (toggle)
        self.project_image_button = QPushButton("🖼️ Proyectar Imagen Completa")
        self.project_image_button.clicked.connect(self.project_full_image)
        self.project_image_button.setVisible(False)
        self.project_image_button.setToolTip(
            "Proyecta la imagen completa en el monitor secundario"
        )
        layout.addWidget(self.project_image_button)

        # Controles de exposición temporizada
        self.exposure_button = QPushButton("▶️ Iniciar Exposición")
        self.exposure_button.clicked.connect(self.start_timed_exposure)
        self.exposure_button.setVisible(False)
        layout.addWidget(self.exposure_button)

        self.stop_exposure_button = QPushButton("⏹️ Detener")
        self.stop_exposure_button.clicked.connect(self.force_stop_exposure)
        self.stop_exposure_button.setVisible(False)
        layout.addWidget(self.stop_exposure_button)

        self.exposure_status_label = create_stat_label("Estado: Inactivo")
        layout.addWidget(self.exposure_status_label)

        self.exposure_section.setContentWidget(content)
        self.info_layout.addWidget(self.exposure_section)

    def _build_frequency_section(self) -> None:
        """〜 FRECUENCIA — valor, unidad, duración y controles de start/stop."""
        self.frequency_section = CollapsibleSection(
            " FRECUENCIA", self, expanded=False
        )
        content, layout = create_section_content()

        # Valor y unidad de frecuencia
        freq_row = QHBoxLayout()
        freq_row.addWidget(create_stat_label("Frecuencia:"))
        self.frequency_value_input = QLineEdit("1")
        self.frequency_value_input.setPlaceholderText("Ej: 2.5")
        self.frequency_value_input.setMaximumWidth(INPUT_FIELD_NARROW_MAX_WIDTH + 30)
        self.frequency_unit_combo = QComboBox()
        self.frequency_unit_combo.addItems(FREQUENCY_UNITS)
        self.frequency_unit_combo.setMaximumWidth(INPUT_FIELD_NARROW_MAX_WIDTH + 30)
        freq_row.addWidget(self.frequency_value_input)
        freq_row.addWidget(self.frequency_unit_combo)
        freq_row.addStretch()
        layout.addLayout(freq_row)

        # Duración total
        dur_row, self.frequency_duration_input = create_text_input_row(
            "Duración (segundos):", "60", "0 = infinito",
        )
        layout.addLayout(dur_row)

        self.frequency_button = QPushButton("🌊 Iniciar Modo Frecuencia")
        self.frequency_button.clicked.connect(self.start_frequency_mode)
        self.frequency_button.setVisible(False)
        layout.addWidget(self.frequency_button)

        self.stop_frequency_button = QPushButton("⏹️ Detener Frecuencia")
        self.stop_frequency_button.clicked.connect(self.force_stop_frequency)
        self.stop_frequency_button.setVisible(False)
        layout.addWidget(self.stop_frequency_button)

        self.frequency_status_label = create_stat_label("Estado: Inactivo")
        layout.addWidget(self.frequency_status_label)

        self.frequency_section.setContentWidget(content)
        self.frequency_section.setVisible(False)
        self.info_layout.addWidget(self.frequency_section)
