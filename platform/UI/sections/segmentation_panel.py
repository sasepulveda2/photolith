"""
Sección: ️ SEGMENTACIÓN DE IMAGEN.

Métodos:
    _build_segmentation_section()          → sección principal
    _build_segmentation_transforms()       → rotación + espejos
    _build_segmentation_manual_controls()  → spinboxes X/Y manuales
    _build_segmentation_info_and_actions() → labels, botón aplicar, overlay
"""
from PyQt5.QtWidgets import (
    QVBoxLayout, QHBoxLayout, QPushButton, QCheckBox, QComboBox,
    QWidget, QSlider, QSpinBox,
)
from PyQt5.QtCore import Qt
from UI.collapsible_section import CollapsibleSection
from UI.widget_helpers import (
    create_section_content, create_stat_label, create_description_label,
)
from constants import (
    SECTION_CONTENT_SPACING_WIDE,
    ROTATION_SLIDER_MIN, ROTATION_SLIDER_MAX, ROTATION_TICK_INTERVAL,
    SEGMENTS_SPIN_MIN, SEGMENTS_SPIN_MAX, SEGMENTS_SPIN_DEFAULT,
    STYLE_BOLD_MARGIN_TOP, STYLE_BOLD, STYLE_SMALL_10PX, STYLE_MARGIN_TOP_10,
    SEGMENTATION_MODES,
)


class SegmentationPanelBuilder:
    """Mixin: construye la sección de segmentación de imagen."""

    def _build_segmentation_section(self) -> None:
        """️ SEGMENTACIÓN — modo de corte, transformaciones geométricas y aplicación."""
        self.segmentation_section = CollapsibleSection(
            " Segmentación ", self, expanded=False, section_id="segmentation"
        )
        content, layout = create_section_content(spacing=SECTION_CONTENT_SPACING_WIDE)

        layout.addWidget(create_description_label(
            "División de la imagen en segmentos/subcampos para "
            "exposición secuencial en stepper litográfico"
        ))

        # Modo de segmentación
        mode_row = QHBoxLayout()
        mode_row.addWidget(create_stat_label("Modo:"))
        self.segmentation_mode_combo = QComboBox()
        self.segmentation_mode_combo.addItems(SEGMENTATION_MODES)
        self.segmentation_mode_combo.currentIndexChanged.connect(
            self.update_segmentation_mode
        )
        mode_row.addWidget(self.segmentation_mode_combo)
        layout.addLayout(mode_row)

        self._build_segmentation_transforms(layout)
        self._build_segmentation_manual_controls(layout)
        self._build_segmentation_info_and_actions(layout)

        self.segmentation_section.setContentWidget(content)
        self.segmentation_section.setVisible(False)
        self.info_layout.addWidget(self.segmentation_section)

    def _build_segmentation_transforms(self, layout: QVBoxLayout) -> None:
        """Sub-sección de transformaciones geométricas (rotación + espejos)."""
        transform_lbl = create_stat_label(" Transformaciones:")
        transform_lbl.setStyleSheet(STYLE_BOLD_MARGIN_TOP)
        layout.addWidget(transform_lbl)

        # Rotación
        rot_header = QHBoxLayout()
        rot_header.addWidget(create_stat_label("Rotación:"))
        self.rotation_value_label = create_stat_label("0°")
        self.rotation_value_label.setStyleSheet(STYLE_BOLD)
        rot_header.addWidget(self.rotation_value_label)
        rot_header.addStretch()

        self.rotation_slider = QSlider(Qt.Horizontal)
        self.rotation_slider.setMinimum(ROTATION_SLIDER_MIN)
        self.rotation_slider.setMaximum(ROTATION_SLIDER_MAX)
        self.rotation_slider.setValue(0)
        self.rotation_slider.setTickPosition(QSlider.TicksBelow)
        self.rotation_slider.setTickInterval(ROTATION_TICK_INTERVAL)
        self.rotation_slider.setToolTip("Rotar imagen en sentido horario (0-360°)")
        self.rotation_slider.valueChanged.connect(self.update_image_transform)

        rot_col = QVBoxLayout()
        rot_col.addLayout(rot_header)
        rot_col.addWidget(self.rotation_slider)
        layout.addLayout(rot_col)

        # Espejos
        self.mirror_horizontal_checkbox = QCheckBox(" Espejo horizontal")
        self.mirror_horizontal_checkbox.setObjectName("statLabel")
        self.mirror_horizontal_checkbox.stateChanged.connect(self.update_image_transform)
        layout.addWidget(self.mirror_horizontal_checkbox)

        self.mirror_vertical_checkbox = QCheckBox(" Espejo vertical")
        self.mirror_vertical_checkbox.setObjectName("statLabel")
        self.mirror_vertical_checkbox.stateChanged.connect(self.update_image_transform)
        layout.addWidget(self.mirror_vertical_checkbox)

    def _build_segmentation_manual_controls(self, layout: QVBoxLayout) -> None:
        """Sub-sección de configuración manual de segmentos X/Y (oculta por defecto)."""
        self.manual_segments_widget = QWidget()
        manual_layout = QVBoxLayout(self.manual_segments_widget)
        manual_layout.setContentsMargins(0, 5, 0, 0)
        manual_layout.setSpacing(6)

        for axis, attr in (("X", "segments_x_spin"), ("Y", "segments_y_spin")):
            row = QHBoxLayout()
            row.addWidget(create_stat_label(f"Segmentos {axis}:"))
            spin = QSpinBox()
            spin.setMinimum(SEGMENTS_SPIN_MIN)
            spin.setMaximum(SEGMENTS_SPIN_MAX)
            spin.setValue(SEGMENTS_SPIN_DEFAULT)
            spin.valueChanged.connect(self.update_segmentation_preview)
            setattr(self, attr, spin)
            row.addWidget(spin)
            row.addStretch()
            manual_layout.addLayout(row)

        self.manual_segments_widget.setVisible(False)
        layout.addWidget(self.manual_segments_widget)

    def _build_segmentation_info_and_actions(self, layout: QVBoxLayout) -> None:
        """Sub-sección de labels informativos, botón aplicar y overlay."""
        self.segment_info_label = create_stat_label("Total de segmentos: -")
        self.segment_info_label.setStyleSheet("font-size: 10px; font-weight: bold;")
        layout.addWidget(self.segment_info_label)

        self.segment_size_label = create_stat_label("Tamaño por segmento: -")
        self.segment_size_label.setStyleSheet(STYLE_SMALL_10PX)
        layout.addWidget(self.segment_size_label)

        self.segment_overlap_label = create_stat_label("Solapamiento: 0%")
        self.segment_overlap_label.setStyleSheet(STYLE_SMALL_10PX)
        layout.addWidget(self.segment_overlap_label)

        # Aplicar segmentación
        self.apply_segmentation_button = QPushButton(" Aplicar segmentación")
        self.apply_segmentation_button.setObjectName("modernButton")
        self.apply_segmentation_button.clicked.connect(self.apply_image_segmentation)
        self.apply_segmentation_button.setToolTip(
            "Divide la imagen según la configuración de segmentos"
        )
        self.apply_segmentation_button.setStyleSheet(STYLE_MARGIN_TOP_10)
        layout.addWidget(self.apply_segmentation_button)

        # Overlay de segmentos sobre el grid
        self.show_segments_overlay_checkbox = QCheckBox(
            "Mostrar overlay de segmentos en grid"
        )
        self.show_segments_overlay_checkbox.setChecked(False)
        self.show_segments_overlay_checkbox.setObjectName("statLabel")
        self.show_segments_overlay_checkbox.stateChanged.connect(
            self.toggle_segments_overlay
        )
        layout.addWidget(self.show_segments_overlay_checkbox)
