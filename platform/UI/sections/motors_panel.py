"""
Sección: ⚙️ CONTROL DE MOTORES.

Métodos:
    _build_motors_section()          → sección principal (conexión + parámetros)
    _build_motor_pulse_controls()    → steps + velocidad
    _build_motor_direction_pad()     → pad XY en cruz + columna Z
"""
from PyQt5.QtWidgets import QVBoxLayout, QHBoxLayout, QSpinBox
from PyQt5.QtCore import Qt
from UI.collapsible_section import CollapsibleSection
from UI.widget_helpers import (
    create_section_content, create_stat_label,
    create_modern_button, create_pad_button,
)
from constants import (
    SECTION_CONTENT_SPACING_WIDE,
    MOTOR_PAD_BUTTON_SIZE, MOTOR_PAD_SPACING,
    MOTOR_STEPS_RANGE, MOTOR_STEPS_DEFAULT,
    MOTOR_INTERVAL_RANGE, MOTOR_INTERVAL_DEFAULT,
    MOTOR_PAD_AUTOREPEAT_DELAY,
    STYLE_MOTOR_STATUS_DISCONNECTED, STYLE_MOTOR_PULSE_TITLE,
    STYLE_MOTOR_PAD_BUTTON, STYLE_BOLD,
)


class MotorsPanelBuilder:
    """Mixin: construye la sección de control de motores."""

    def _build_motors_section(self) -> None:
        """⚙️ CONTROL DE MOTORES — conexión, parámetros de pulso y pad XY+Z."""
        self.motors_sidebar_section = CollapsibleSection(
            "⚙️ MOTORES (X, Y, Z)", self, expanded=False, section_id="motors"
        )
        content, layout = create_section_content(spacing=SECTION_CONTENT_SPACING_WIDE)

        # Estado de conexión
        self.motors_sidebar_status = create_stat_label("Desconectado")
        self.motors_sidebar_status.setStyleSheet(STYLE_MOTOR_STATUS_DISCONNECTED)
        layout.addWidget(self.motors_sidebar_status)

        layout.addWidget(create_modern_button(
            "🔌 Conectar Hardware", slot=self.connect_motors_sidebar,
        ))

        # Parámetros de pulso
        pulse_title = create_stat_label("Parámetros de Pulso:")
        pulse_title.setStyleSheet(STYLE_MOTOR_PULSE_TITLE)
        layout.addWidget(pulse_title)

        self._build_motor_pulse_controls(layout)
        self._build_motor_direction_pad(layout)

        self.motors_sidebar_section.setContentWidget(content)
        self.motors_sidebar_section.setVisible(True)
        self.info_layout.addWidget(self.motors_sidebar_section)

    def _build_motor_pulse_controls(self, layout: QVBoxLayout) -> None:
        """Controles de steps y velocidad (intervalo) para los motores."""
        steps_row = QHBoxLayout()
        steps_row.addWidget(create_stat_label("Steps:"))
        self.motor_steps_spin = QSpinBox()
        self.motor_steps_spin.setRange(*MOTOR_STEPS_RANGE)
        self.motor_steps_spin.setValue(MOTOR_STEPS_DEFAULT)  # sobrescrito al cargar configuración
        self.motor_steps_spin.valueChanged.connect(self.save_motor_sidebar_settings)
        steps_row.addWidget(self.motor_steps_spin)
        layout.addLayout(steps_row)

        interval_row = QHBoxLayout()
        interval_row.addWidget(create_stat_label("Velocidad (ms):"))
        self.motor_interval_spin = QSpinBox()
        self.motor_interval_spin.setRange(*MOTOR_INTERVAL_RANGE)
        self.motor_interval_spin.setValue(MOTOR_INTERVAL_DEFAULT)  # sobrescrito al cargar configuración
        self.motor_interval_spin.setToolTip(
            "Retardo entre pulsos cuando se mantiene presionado el botón"
        )
        self.motor_interval_spin.valueChanged.connect(
            self.update_motor_autorepeat_settings
        )
        interval_row.addWidget(self.motor_interval_spin)
        layout.addLayout(interval_row)

    def _build_motor_direction_pad(self, layout: QVBoxLayout) -> None:
        """Construye el pad direccional XY en cruz y la columna Z."""
        # Crear los 6 botones del pad
        directions = [
            ("Y+", "Y",  1), ("Y-", "Y", -1),
            ("X-", "X", -1), ("X+", "X",  1),
            ("Z+", "Z",  1), ("Z-", "Z", -1),
        ]
        buttons = {}
        for label, axis, direction in directions:
            btn = create_pad_button(
                label, STYLE_MOTOR_PAD_BUTTON,
                MOTOR_PAD_BUTTON_SIZE, MOTOR_PAD_AUTOREPEAT_DELAY,
            )
            btn.clicked.connect(
                lambda checked=False, a=axis, d=direction: self.execute_sidebar_motor_move(a, d)
            )
            buttons[label] = btn

        self.motor_buttons = list(buttons.values())

        # Pad en cruz para X/Y
        row_top = QHBoxLayout()
        row_top.addStretch()
        row_top.addWidget(buttons["Y+"])
        row_top.addStretch()

        row_mid = QHBoxLayout()
        row_mid.addStretch()
        row_mid.addWidget(buttons["X-"])
        row_mid.addSpacing(MOTOR_PAD_SPACING)
        row_mid.addWidget(buttons["X+"])
        row_mid.addStretch()

        row_bot = QHBoxLayout()
        row_bot.addStretch()
        row_bot.addWidget(buttons["Y-"])
        row_bot.addStretch()

        xy_pad = QVBoxLayout()
        xy_pad.addLayout(row_top)
        xy_pad.addLayout(row_mid)
        xy_pad.addLayout(row_bot)

        # Columna para eje Z
        z_lbl = create_stat_label("Eje Z")
        z_lbl.setAlignment(Qt.AlignCenter)
        z_lbl.setStyleSheet(STYLE_BOLD)

        z_col = QVBoxLayout()
        z_col.setAlignment(Qt.AlignCenter)
        z_col.addWidget(z_lbl)
        z_col.addWidget(buttons["Z+"])
        z_col.addWidget(buttons["Z-"])

        controls_row = QHBoxLayout()
        controls_row.addLayout(xy_pad)
        controls_row.addSpacing(MOTOR_PAD_SPACING)
        controls_row.addLayout(z_col)
        layout.addLayout(controls_row)
