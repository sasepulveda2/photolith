"""
Sección: 🎥 CÁMARA BASLER.

Métodos:
    _build_basler_section()  → controles de exposición, ganancia, gamma, negro
"""
from UI.collapsible_section import CollapsibleSection
from UI.widget_helpers import (
    create_section_content, create_camera_control_row, create_modern_button,
)
from constants import (
    SECTION_CONTENT_SPACING, SECTION_CONTENT_SPACING_EXTRA,
    BUTTON_MIN_HEIGHT_STANDARD,
    BASLER_EXPOSURE_SLIDER_MIN, BASLER_EXPOSURE_SLIDER_MAX,
    BASLER_EXPOSURE_SLIDER_DEFAULT,
    BASLER_GAIN_SLIDER_MIN, BASLER_GAIN_SLIDER_MAX,
    BASLER_GAIN_SLIDER_DEFAULT,
    BASLER_GAMMA_SLIDER_MIN, BASLER_GAMMA_SLIDER_MAX,
    BASLER_GAMMA_SLIDER_DEFAULT,
    BASLER_BLACK_SLIDER_MIN, BASLER_BLACK_SLIDER_MAX,
    BASLER_BLACK_SLIDER_DEFAULT,
)


class CameraPanelBuilder:
    """Mixin: construye la sección de cámara Basler del sidebar."""

    def _build_basler_section(self) -> None:
        """🎥 CÁMARA BASLER — controles de exposición, ganancia, gamma y nivel de negro."""
        self.basler_sidebar_section = CollapsibleSection(
            "🎥 CÁMARA BASLER", self, expanded=True
        )
        content, layout = create_section_content(spacing=SECTION_CONTENT_SPACING_EXTRA)

        # Exposición: 100 µs – 1 000 000 µs (1 s), valor inicial 10 000 µs
        self.basler_sidebar_exposure_slider, self.basler_sidebar_exposure_input = (
            create_camera_control_row(
                layout, "⏱️ Exposición (μs):",
                BASLER_EXPOSURE_SLIDER_MIN, BASLER_EXPOSURE_SLIDER_MAX,
                BASLER_EXPOSURE_SLIDER_DEFAULT,
                self.update_basler_exposure_from_slider,
                self.update_basler_exposure_from_input,
                unit="μs", input_text="10000",
            )
        )
        # Ganancia: 0 – 240 (representa 0.0 – 24.0 dB, ×10 para precisión decimal)
        self.basler_sidebar_gain_slider, self.basler_sidebar_gain_input = (
            create_camera_control_row(
                layout, "📊 Ganancia (dB):",
                BASLER_GAIN_SLIDER_MIN, BASLER_GAIN_SLIDER_MAX,
                BASLER_GAIN_SLIDER_DEFAULT,
                self.update_basler_gain_from_slider,
                self.update_basler_gain_from_input,
                unit="dB", input_text="0.0",
            )
        )
        # Gamma: 10 – 40 (representa 1.0 – 4.0, ×10)
        self.basler_sidebar_gamma_slider, self.basler_sidebar_gamma_input = (
            create_camera_control_row(
                layout, "🔆 Gamma:",
                BASLER_GAMMA_SLIDER_MIN, BASLER_GAMMA_SLIDER_MAX,
                BASLER_GAMMA_SLIDER_DEFAULT,
                self.update_basler_gamma_from_slider,
                self.update_basler_gamma_from_input,
                input_text="1.0",
            )
        )
        # Nivel de negro: 0 – 255
        self.basler_sidebar_black_slider, self.basler_sidebar_black_input = (
            create_camera_control_row(
                layout, "⬛ Nivel de Negro:",
                BASLER_BLACK_SLIDER_MIN, BASLER_BLACK_SLIDER_MAX,
                BASLER_BLACK_SLIDER_DEFAULT,
                self.update_basler_black_from_slider,
                self.update_basler_black_from_input,
                input_text="0",
            )
        )

        layout.addSpacing(SECTION_CONTENT_SPACING)

        layout.addWidget(create_modern_button(
            "✓ Aplicar Configuración",
            slot=self.apply_basler_settings,
            min_height=BUTTON_MIN_HEIGHT_STANDARD,
        ))
        layout.addWidget(create_modern_button(
            "↺ Valores por Defecto",
            slot=self.reset_basler_settings,
            min_height=BUTTON_MIN_HEIGHT_STANDARD,
        ))

        self.basler_sidebar_section.setContentWidget(content)
        self.basler_sidebar_section.setVisible(False)
        self.info_layout.addWidget(self.basler_sidebar_section)
