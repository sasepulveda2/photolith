"""
Funciones auxiliares para la construcción de widgets de la UI.

Cada función es pura (no muta estado global), recibe parámetros explícitos
y retorna el widget creado. Están diseñadas para eliminar la repetición
de patrones de creación de widgets en los mixins de UI.
"""
from typing import Optional, Sequence, Tuple

from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QSlider, QLineEdit,
    QPushButton, QDoubleSpinBox, QSpinBox,
)
from PyQt5.QtCore import Qt

from constants import (
    SECTION_CONTENT_MARGINS, SECTION_CONTENT_SPACING,
    INPUT_FIELD_MAX_WIDTH, STYLE_MUTED_10PX, STYLE_BOLD_10PX,
    STYLE_SMALL_10PX,
)


# ═════════════════════════════════════════════════════════════════════════
# SECTION CONTAINERS
# ═════════════════════════════════════════════════════════════════════════

def create_section_content(
    spacing: int = SECTION_CONTENT_SPACING,
    margins: Tuple[int, int, int, int] = SECTION_CONTENT_MARGINS,
    object_name: str = "statsContainer",
) -> Tuple[QWidget, QVBoxLayout]:
    """Crea el par (QWidget, QVBoxLayout) estándar para el contenido de una
    CollapsibleSection. Retorna ambos para que el caller agregue widgets
    al layout y luego pase el widget al setContentWidget()."""
    content = QWidget()
    content.setObjectName(object_name)
    layout = QVBoxLayout(content)
    layout.setContentsMargins(*margins)
    layout.setSpacing(spacing)
    return content, layout


# ═════════════════════════════════════════════════════════════════════════
# LABELS
# ═════════════════════════════════════════════════════════════════════════

def create_stat_label(text: str) -> QLabel:
    """QLabel con objectName='statLabel' — el estilo base del sidebar."""
    lbl = QLabel(text)
    lbl.setObjectName("statLabel")
    return lbl


def create_description_label(text: str) -> QLabel:
    """QLabel descriptivo con word-wrap y color muted, usado como intro
    de secciones complejas."""
    lbl = QLabel(text)
    lbl.setWordWrap(True)
    lbl.setStyleSheet(STYLE_MUTED_10PX)
    return lbl


def create_section_title_label(text: str) -> QLabel:
    """Título bold pequeño para sub-secciones dentro de una CollapsibleSection."""
    lbl = QLabel(text)
    lbl.setStyleSheet(STYLE_BOLD_10PX)
    return lbl


def create_info_label(text: str, color: str = "") -> QLabel:
    """QLabel de estado con estilo pequeño, opcionalmente coloreado.
    Usado en el monitor de calibración."""
    lbl = QLabel(text)
    lbl.setObjectName("statLabel")
    style = STYLE_SMALL_10PX
    if color:
        style += f" color: {color};"
    lbl.setStyleSheet(style)
    return lbl


# ═════════════════════════════════════════════════════════════════════════
# INPUT ROWS
# ═════════════════════════════════════════════════════════════════════════

def create_input_row(
    label_text: str,
    default_value,
    max_width: int = INPUT_FIELD_MAX_WIDTH,
) -> Tuple[QHBoxLayout, QLineEdit]:
    """Crea una fila [QLabel + QLineEdit + stretch] y retorna (layout, input).
    El caller asigna el input a self.<attr> según corresponda."""
    row = QHBoxLayout()
    lbl = create_stat_label(label_text)
    inp = QLineEdit(str(default_value))
    inp.setMaximumWidth(max_width)
    row.addWidget(lbl)
    row.addWidget(inp)
    row.addStretch()
    return row, inp


def create_text_input_row(
    label_text: str,
    default: str,
    placeholder: str,
    max_width: int = INPUT_FIELD_MAX_WIDTH,
) -> Tuple[QHBoxLayout, QLineEdit]:
    """Variante de create_input_row con placeholder text.
    Retorna (layout, QLineEdit)."""
    row = QHBoxLayout()
    lbl = create_stat_label(label_text)
    inp = QLineEdit(default)
    inp.setPlaceholderText(placeholder)
    inp.setMaximumWidth(max_width)
    row.addWidget(lbl)
    row.addWidget(inp)
    row.addStretch()
    return row, inp


def create_camera_control_row(
    layout: QVBoxLayout,
    title: str,
    minimum: int,
    maximum: int,
    default: int,
    slider_slot,
    input_slot,
    unit: str = "",
    input_text: str = "",
    input_max_width: int = 70,
) -> Tuple[QSlider, QLineEdit]:
    """Crea una fila de control de cámara: título + slider + campo numérico + unidad.
    Agrega directamente al layout. Retorna (slider, input)."""
    from constants import STYLE_BOLD_11PX, STYLE_UNIT_10PX

    title_lbl = QLabel(title)
    title_lbl.setStyleSheet(STYLE_BOLD_11PX)
    layout.addWidget(title_lbl)

    slider = QSlider(Qt.Horizontal)
    slider.setMinimum(minimum)
    slider.setMaximum(maximum)
    slider.setValue(default)
    slider.valueChanged.connect(slider_slot)

    inp = QLineEdit(input_text or str(default))
    inp.setMaximumWidth(input_max_width)
    inp.returnPressed.connect(input_slot)

    row = QHBoxLayout()
    row.addWidget(slider, stretch=1)
    row.addWidget(inp)
    if unit:
        unit_lbl = QLabel(unit)
        unit_lbl.setStyleSheet(STYLE_UNIT_10PX)
        row.addWidget(unit_lbl)
    layout.addLayout(row)

    return slider, inp


def create_spin_row(
    label_text: str,
    min_v: float,
    max_v: float,
    default: float,
    step: float,
    decimals: int,
    suffix: str,
    tooltip: str,
) -> Tuple[QHBoxLayout, QDoubleSpinBox]:
    """Crea una fila [QLabel + QDoubleSpinBox + stretch].
    Retorna (layout, spin) para que el caller conecte señales y asigne."""
    row = QHBoxLayout()
    lbl = create_stat_label(label_text)
    spin = QDoubleSpinBox()
    spin.setMinimum(min_v)
    spin.setMaximum(max_v)
    spin.setValue(default)
    spin.setSingleStep(step)
    spin.setDecimals(decimals)
    spin.setSuffix(suffix)
    spin.setToolTip(tooltip)
    row.addWidget(lbl)
    row.addWidget(spin)
    row.addStretch()
    return row, spin


# ═════════════════════════════════════════════════════════════════════════
# BUTTONS
# ═════════════════════════════════════════════════════════════════════════

def create_modern_button(
    text: str,
    slot=None,
    min_height: int = 0,
    tooltip: str = "",
) -> QPushButton:
    """QPushButton con objectName='modernButton' y conexión opcional."""
    btn = QPushButton(text)
    btn.setObjectName("modernButton")
    if min_height:
        btn.setMinimumHeight(min_height)
    if tooltip:
        btn.setToolTip(tooltip)
    if slot is not None:
        btn.clicked.connect(slot)
    return btn


def create_pad_button(
    label: str,
    style: str,
    size: int,
    autorepeat_delay: int,
) -> QPushButton:
    """QPushButton cuadrado para el pad de motores (XY/Z)."""
    btn = QPushButton(label)
    btn.setObjectName("motorPadButton")
    btn.setFixedSize(size, size)
    btn.setAutoRepeat(True)
    btn.setAutoRepeatDelay(autorepeat_delay)
    return btn


# ═════════════════════════════════════════════════════════════════════════
# BATCH LABEL CREATION
# ═════════════════════════════════════════════════════════════════════════

def create_stat_labels_batch(
    owner,
    definitions: Sequence[Tuple[str, str]],
    layout: QVBoxLayout,
) -> None:
    """Crea múltiples stat labels de una vez, asignándolos como atributos
    del owner. Cada tupla es (attr_name, default_text)."""
    for attr, text in definitions:
        lbl = create_stat_label(text)
        setattr(owner, attr, lbl)
        layout.addWidget(lbl)
