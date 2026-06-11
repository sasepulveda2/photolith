"""
Sección: 🎬 CONTROL DE PROYECCIÓN.

Métodos:
    _build_projection_section()   → sección principal
    _build_downscale_controls()   → factor de reducción
    _build_sequence_console()     → estado, progreso, botones, tiempos
"""
from PyQt5.QtWidgets import (
    QVBoxLayout, QHBoxLayout, QLabel, QCheckBox, QDoubleSpinBox, QProgressBar,
)
from UI.collapsible_section import CollapsibleSection
from UI.widget_helpers import (
    create_section_content, create_stat_label, create_description_label,
    create_modern_button, create_spin_row,
)
from constants import (
    SECTION_CONTENT_SPACING_WIDE, STYLE_BOLD_11PX, STYLE_SMALL_10PX,
    DOWNSCALE_SPIN_MIN, DOWNSCALE_SPIN_MAX, DOWNSCALE_SPIN_DEFAULT,
    DOWNSCALE_SPIN_STEP, DOWNSCALE_SPIN_DECIMALS,
    EXPOSURE_TIME_SPIN_MIN, EXPOSURE_TIME_SPIN_MAX,
    EXPOSURE_TIME_SPIN_DEFAULT, EXPOSURE_TIME_SPIN_STEP,
    EXPOSURE_TIME_SPIN_DECIMALS,
    MOVEMENT_TIME_SPIN_MIN, MOVEMENT_TIME_SPIN_MAX,
    MOVEMENT_TIME_SPIN_DEFAULT, MOVEMENT_TIME_SPIN_STEP,
    MOVEMENT_TIME_SPIN_DECIMALS,
    PROGRESS_BAR_MAX_HEIGHT,
)


class ProjectionPanelBuilder:
    """Mixin: construye la sección de control de proyección."""

    def _build_projection_section(self) -> None:
        """🎬 CONTROL DE PROYECCIÓN — factor de downscaling y consola de secuencias."""
        self.projection_control_section = CollapsibleSection(
            " Control de proyección", self, expanded=False, section_id="projection"
        )
        content, layout = create_section_content(spacing=SECTION_CONTENT_SPACING_WIDE)

        self._build_downscale_controls(layout)
        layout.addSpacing(15)
        self._build_sequence_console(layout)

        self.projection_control_section.setContentWidget(content)
        self.projection_control_section.setVisible(False)
        self.info_layout.addWidget(self.projection_control_section)

    def _build_downscale_controls(self, layout: QVBoxLayout) -> None:
        """Sub-sección del factor de reducción (downscaling) para la proyección."""
        ds_title = QLabel(" Factor de reducción")
        ds_title.setStyleSheet(STYLE_BOLD_11PX)
        layout.addWidget(ds_title)

        layout.addWidget(create_description_label(
            "Reduce la imagen proyectada para lograr la resolución final deseada "
            "en el sustrato (típico de steppers)"
        ))

        ds_row = QHBoxLayout()
        ds_row.addWidget(create_stat_label("Factor:"))
        self.downscale_factor_spin = QDoubleSpinBox()
        self.downscale_factor_spin.setMinimum(DOWNSCALE_SPIN_MIN)
        self.downscale_factor_spin.setMaximum(DOWNSCALE_SPIN_MAX)
        self.downscale_factor_spin.setValue(DOWNSCALE_SPIN_DEFAULT)
        self.downscale_factor_spin.setSingleStep(DOWNSCALE_SPIN_STEP)
        self.downscale_factor_spin.setDecimals(DOWNSCALE_SPIN_DECIMALS)
        self.downscale_factor_spin.setSuffix("x")
        self.downscale_factor_spin.setToolTip(
            "Factor de reducción: <1 reduce tamaño, >1 aumenta tamaño"
        )
        self.downscale_factor_spin.valueChanged.connect(self.update_downscale_factor)
        ds_row.addWidget(self.downscale_factor_spin)
        ds_row.addStretch()
        layout.addLayout(ds_row)

        self.downscale_info_label = create_stat_label("Resolución resultante: -")
        self.downscale_info_label.setStyleSheet(STYLE_SMALL_10PX)
        layout.addWidget(self.downscale_info_label)

    def _build_sequence_console(self, layout: QVBoxLayout) -> None:
        """Sub-sección de consola de secuencias: estado, progreso, controles y tiempos."""
        seq_title = QLabel(" Consola de secuencias")
        seq_title.setStyleSheet(STYLE_BOLD_11PX)
        layout.addWidget(seq_title)

        layout.addWidget(create_description_label(
            "Gestión de secuencias de movimiento (stage/platina) "
            "y activación de proyección (shutter)"
        ))

        # Estado y barra de progreso
        self.sequence_status_label = create_stat_label("Estado: Inactivo")
        layout.addWidget(self.sequence_status_label)

        progress_row = QHBoxLayout()
        self.current_segment_label = create_stat_label("Segmento: 0/0")
        self.segment_progress_bar = QProgressBar()
        self.segment_progress_bar.setMaximum(100)
        self.segment_progress_bar.setValue(0)
        self.segment_progress_bar.setMaximumHeight(PROGRESS_BAR_MAX_HEIGHT)
        progress_row.addWidget(self.current_segment_label)
        progress_row.addWidget(self.segment_progress_bar, stretch=1)
        layout.addLayout(progress_row)

        # Botones de control
        btns_row = QHBoxLayout()
        self.sequence_start_button = create_modern_button(
            " Iniciar", slot=self.start_sequence,
            tooltip="Inicia la secuencia de proyección con los segmentos del grid",
        )
        self.sequence_pause_button = create_modern_button(
            " Pausar", slot=self.pause_sequence,
        )
        self.sequence_pause_button.setEnabled(False)
        self.sequence_stop_button = create_modern_button(
            " Detener", slot=self.stop_sequence,
        )
        self.sequence_stop_button.setEnabled(False)
        btns_row.addWidget(self.sequence_start_button)
        btns_row.addWidget(self.sequence_pause_button)
        btns_row.addWidget(self.sequence_stop_button)
        layout.addLayout(btns_row)

        # Opciones de automatización
        self.auto_shutter_checkbox = QCheckBox("Shutter automático por segmento")
        self.auto_shutter_checkbox.setChecked(True)
        self.auto_shutter_checkbox.setObjectName("statLabel")
        self.auto_shutter_checkbox.setToolTip(
            "Activa/desactiva la proyección automáticamente en cada segmento"
        )
        layout.addWidget(self.auto_shutter_checkbox)

        self.auto_movement_checkbox = QCheckBox("Movimiento automático de stage")
        self.auto_movement_checkbox.setChecked(True)
        self.auto_movement_checkbox.setObjectName("statLabel")
        self.auto_movement_checkbox.setToolTip(
            "Mueve la platina automáticamente entre segmentos"
        )
        layout.addWidget(self.auto_movement_checkbox)

        # Tiempos de exposición y movimiento
        exp_spin_row, self.exposure_time_spin = create_spin_row(
            " Tiempo de exposición:",
            EXPOSURE_TIME_SPIN_MIN, EXPOSURE_TIME_SPIN_MAX,
            EXPOSURE_TIME_SPIN_DEFAULT, EXPOSURE_TIME_SPIN_STEP,
            EXPOSURE_TIME_SPIN_DECIMALS, " s",
            "Tiempo que se muestra cada segmento (exposición)",
        )
        layout.addLayout(exp_spin_row)

        mov_spin_row, self.movement_time_spin = create_spin_row(
            " Tiempo de movimiento:",
            MOVEMENT_TIME_SPIN_MIN, MOVEMENT_TIME_SPIN_MAX,
            MOVEMENT_TIME_SPIN_DEFAULT, MOVEMENT_TIME_SPIN_STEP,
            MOVEMENT_TIME_SPIN_DECIMALS, " s",
            "Tiempo para mover stage entre segmentos (pantalla negra)",
        )
        layout.addLayout(mov_spin_row)
