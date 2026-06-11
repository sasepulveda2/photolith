"""
Mixin de preferencias y configuracion.

Dialogos de escala de proyeccion, configuracion de exposicion,
colores del grid y opciones avanzadas.
"""
import sys
import ctypes
import time

from PyQt5.QtWidgets import (
    QGraphicsOpacityEffect, QMenu, QVBoxLayout, QHBoxLayout, QPushButton, QLabel, QSlider,
    QComboBox, QLineEdit, QDialog, QRadioButton, QButtonGroup,
    QMessageBox, QWidget,
)
from PyQt5.QtCore import QEasingCurve, QPropertyAnimation, Qt


class PreferencesMixin:
    """Mixin: Preferences functionality."""

    def show_preferences_menu(self):
        menu = QMenu(self)
        menu.setStyleSheet(
            """
            QMenu {
                background-color: """
            + ("#1E1E1E" if self.dark_mode else "#FFFFFF")
            + """;
                color: """
            + ("#E0E0E0" if self.dark_mode else "#000000")
            + """;
                border: 1px solid """
            + ("#2E2E2E" if self.dark_mode else "#CCCCCC")
            + """;
                border-radius: 8px;
                padding: 8px;
            }
            QMenu::item {
                padding: 8px 20px;
                border-radius: 4px;
            }
            QMenu::item:selected {
                background-color: #A0A0A0;
                color: #121212;
            }
        """
        )

        if self.dark_mode:
            theme_action = menu.addAction("☀️ Modo Claro")
        else:
            theme_action = menu.addAction("🌙 Modo Oscuro")

        theme_action.triggered.connect(self.toggle_theme)

        scale_action = menu.addAction("📐 Configuración de Escala")
        scale_action.triggered.connect(self.show_scale_config)

        exposure_config_action = menu.addAction("⏱️ Configuración de Exposición")
        exposure_config_action.triggered.connect(self.show_exposure_config)

        grid_config_action = menu.addAction("📏 Configuración de Grid")
        grid_config_action.triggered.connect(self.show_grid_color_config)

        effects_action = menu.addAction(
            "✨ Aplicar Efectos en Grid"
            if not self.apply_effects_to_grid
            else "✨ Desactivar Efectos en Grid"
        )
        effects_action.triggered.connect(self.toggle_grid_effects)

        # Opción para mostrar/ocultar heatmap
        heatmap_action = menu.addAction(
            "Ocultar Heatmap en vista principal" if getattr(self, "show_heatmap", False) else "Mostrar Heatmap en vista principal"
        )
        heatmap_action.triggered.connect(self.toggle_heatmap_visibility)

        # Opción para limpiar cache de segmentación
        clear_cache_action = menu.addAction("🗑️ Limpiar Cache de Segmentación")
        clear_cache_action.triggered.connect(self.clear_segmentation_cache)

        menu.exec_(
            self.preferences_button.mapToGlobal(
                self.preferences_button.rect().bottomLeft()
            )
        )


    def toggle_theme(self):
        self.dark_mode = not self.dark_mode

        self.opacity_effect = QGraphicsOpacityEffect()
        self.setGraphicsEffect(self.opacity_effect)

        self.fade_animation = QPropertyAnimation(self.opacity_effect, b"opacity")
        self.fade_animation.setDuration(100)
        self.fade_animation.setStartValue(1.0)
        self.fade_animation.setEndValue(0.5)
        self.fade_animation.setEasingCurve(QEasingCurve.OutCubic)

        self.fade_animation.finished.connect(self.apply_theme_and_fade_in)
        self.fade_animation.start()

    def toggle_heatmap_visibility(self):
        """Activa o desactiva la vista del heatmap en la pantalla principal."""
        self.show_heatmap = not getattr(self, "show_heatmap", False)
        # Si hay una imagen cargada, volver a dibujarla para reflejar el cambio
        if hasattr(self, 'pattern') and self.pattern is not None:
            if not self.grid_view_active:
                if hasattr(self, 'simulate_optics'):
                    self.simulate_optics()

    def toggle_grid_effects(self):
        """Activa o desactiva la aplicación de efectos (intensidad/desenfoque) en el grid"""
        self.apply_effects_to_grid = not self.apply_effects_to_grid
        self.save_grid_config()

        if self.grid_view_active and self.grid_generated:

            if self.pattern is not None:
                self.image_on_grid = (
                    self.apply_grid_effects(self.pattern.copy())
                    if self.apply_effects_to_grid
                    else self.pattern.copy()
                )
                self.display_grid()

        status = "activados" if self.apply_effects_to_grid else "desactivados"
        QMessageBox.information(
            self,
            "Efectos en Grid",
            f"Los efectos de intensidad y desenfoque han sido {status} para la vista grid.\n\n"
            f"Los sliders ahora {'aplicarán' if self.apply_effects_to_grid else 'NO aplicarán'} los cambios en tiempo real al grid.",
        )


    def clear_segmentation_cache(self):
        """
        Limpia el cache de segmentación, forzando un recálculo en la próxima segmentación.
        Útil para debugging o cuando se sospecha que el cache está desincronizado.
        """
        # Verificar si hay cache activo
        has_cache = (
            hasattr(self, "_last_segmentation_pattern_id")
            and self._last_segmentation_pattern_id is not None
        )

        if not has_cache:
            QMessageBox.information(
                self, "Cache Vacío", "No hay cache de segmentación activo para limpiar."
            )
            return

        # Guardar información del cache antes de limpiar
        old_config = (
            self._last_segmentation_grid_config
            if hasattr(self, "_last_segmentation_grid_config")
            else None
        )
        old_bounds = (
            self._last_segmentation_bounds
            if hasattr(self, "_last_segmentation_bounds")
            else None
        )

        # Limpiar cache
        self._last_segmentation_pattern_id = None
        self._last_segmentation_grid_config = None
        self._last_segmentation_bounds = None
        if hasattr(self, "_last_image_position"):
            self._last_image_position = None

        # Limpiar segmentos existentes
        if hasattr(self, "image_segments"):
            self.image_segments = []

        # Log
        self.log_to_console("🗑️ Cache de segmentación limpiado", "WARNING")

        # Mensaje informativo
        info_msg = "Cache de segmentación limpiado.\n\n"
        if old_config:
            info_msg += (
                f"Cache anterior:\n  • Configuración: {old_config[0]}×{old_config[1]}\n"
            )
        if old_bounds:
            info_msg += f"  • Bounds: X[{old_bounds['start_x']}-{old_bounds['end_x']}] Y[{old_bounds['start_y']}-{old_bounds['end_y']}]\n"
        info_msg += "\nLa próxima segmentación recalculará desde cero."

        QMessageBox.information(self, "Cache Limpiado", info_msg)


    def show_scale_config(self):

        dialog = QDialog(self)
        dialog.setWindowTitle("Configuración de Escala de Proyección")
        dialog.setFixedWidth(450)
        dialog.setWindowFlags(dialog.windowFlags() & ~Qt.WindowContextHelpButtonHint)

        if self.dark_mode and sys.platform == "win32":
            try:
                hwnd = int(dialog.winId())
                DWMWA_USE_IMMERSIVE_DARK_MODE = 20
                value = ctypes.c_int(1)
                ctypes.windll.dwmapi.DwmSetWindowAttribute(
                    hwnd,
                    DWMWA_USE_IMMERSIVE_DARK_MODE,
                    ctypes.byref(value),
                    ctypes.sizeof(value),
                )
            except:
                pass

        layout = QVBoxLayout()
        layout.setSpacing(16)
        layout.setContentsMargins(20, 20, 20, 20)

        title_label = QLabel("📐 Escala de Imagen Proyectada")
        title_label.setStyleSheet(f"""
            font-size: 16px;
            font-weight: bold;
            color: {'#A0A0A0' if self.dark_mode else '#00796B'};
            padding: 10px 0;
        """)
        layout.addWidget(title_label)

        mode_group = QButtonGroup(dialog)

        automatic_radio = QRadioButton("🔄 Automático (Ajustar al monitor)")
        automatic_radio.setChecked(self.scale_mode == "automatic")
        mode_group.addButton(automatic_radio, 0)

        manual_radio = QRadioButton("🎚️ Manual (Porcentaje personalizado)")
        manual_radio.setChecked(self.scale_mode == "manual")
        mode_group.addButton(manual_radio, 1)

        layout.addWidget(automatic_radio)
        layout.addWidget(manual_radio)

        manual_container = QWidget()
        manual_layout = QVBoxLayout(manual_container)
        manual_layout.setContentsMargins(20, 10, 0, 10)

        scale_slider_label = QLabel(f"Escala: {self.scale_percentage}%")
        scale_slider_label.setStyleSheet("font-size: 13px;")
        manual_layout.addWidget(scale_slider_label)

        scale_slider = QSlider(Qt.Horizontal)
        scale_slider.setMinimum(0)
        scale_slider.setMaximum(200)
        scale_slider.setValue(self.scale_percentage)
        scale_slider.setEnabled(self.scale_mode == "manual")

        def update_slider_label(value):
            scale_slider_label.setText(f"Escala: {value}%")

        scale_slider.valueChanged.connect(update_slider_label)
        manual_layout.addWidget(scale_slider)

        range_label = QLabel(
            "0% = Sin imagen | 100% = Tamaño original | 200% = Doble tamaño"
        )
        range_label.setStyleSheet("font-size: 11px; color: #888888;")
        manual_layout.addWidget(range_label)

        layout.addWidget(manual_container)

        def on_mode_changed():
            is_manual = manual_radio.isChecked()
            scale_slider.setEnabled(is_manual)

        automatic_radio.toggled.connect(on_mode_changed)
        manual_radio.toggled.connect(on_mode_changed)

        button_layout = QHBoxLayout()
        button_layout.addStretch()

        cancel_button = QPushButton("Cancelar")
        cancel_button.clicked.connect(dialog.reject)
        button_layout.addWidget(cancel_button)

        apply_button = QPushButton("✓ Aplicar")
        apply_button.setDefault(True)
        apply_button.clicked.connect(dialog.accept)
        button_layout.addWidget(apply_button)

        layout.addLayout(button_layout)

        dialog.setLayout(layout)

        dialog.setStyleSheet(f"""
            QDialog {{
                background-color: {'#1E1E1E' if self.dark_mode else '#FFFFFF'};
                color: {'#E0E0E0' if self.dark_mode else '#000000'};
            }}
            QRadioButton {{
                color: {'#E0E0E0' if self.dark_mode else '#000000'};
                font-size: 13px;
                padding: 5px;
            }}
            QRadioButton::indicator {{
                width: 18px;
                height: 18px;
            }}
            QPushButton {{
                background-color: {'#2C2C2C' if self.dark_mode else '#F0F0F0'};
                border: 1px solid {'#3E3E3E' if self.dark_mode else '#CCCCCC'};
                border-radius: 6px;
                padding: 8px 16px;
                color: {'#E0E0E0' if self.dark_mode else '#000000'};
                min-width: 80px;
            }}
            QPushButton:hover {{
                background-color: {'#3A3A3A' if self.dark_mode else '#E0E0E0'};
            }}
            QPushButton:default {{
                background-color: #A0A0A0;
                color: #000000;
                border: 1px solid #A0A0A0;
            }}
            QPushButton:default:hover {{
                background-color: #A0A0A0;
            }}
        """)

        if dialog.exec_() == QDialog.Accepted:
            old_mode = self.scale_mode
            old_percentage = self.scale_percentage

            self.scale_mode = "automatic" if automatic_radio.isChecked() else "manual"
            self.scale_percentage = scale_slider.value()

            if (
                old_mode != self.scale_mode or old_percentage != self.scale_percentage
            ) and self.projector_active:
                if self.projection_window:
                    self.projection_window._apply_brightness_and_display()


    def update_projection_stats(
        self, original_width, original_height, scaled_width, scaled_height
    ):
        if original_width > 0 and original_height > 0:
            scale_w = (scaled_width / original_width) * 100
            scale_h = (scaled_height / original_height) * 100
            avg_scale = (scale_w + scale_h) / 2
        else:
            avg_scale = 0

        self.current_scale_info = {
            "original": (original_width, original_height),
            "scaled": (scaled_width, scaled_height),
            "percentage": avg_scale,
        }

        self.scale_info_label.setText(f"Escala proyección: {avg_scale:.1f}%")
        self.projected_resolution_label.setText(
            f"Resolución proyectada: {scaled_width}x{scaled_height} px"
        )

        self.check_second_monitor()


    def show_exposure_config(self):

        dialog = QDialog(self)
        dialog.setWindowTitle("Configuración de Exposición")
        dialog.setFixedWidth(500)
        dialog.setWindowFlags(dialog.windowFlags() & ~Qt.WindowContextHelpButtonHint)

        if self.dark_mode and sys.platform == "win32":
            try:
                hwnd = int(dialog.winId())
                DWMWA_USE_IMMERSIVE_DARK_MODE = 20
                value = ctypes.c_int(1)
                ctypes.windll.dwmapi.DwmSetWindowAttribute(
                    hwnd,
                    DWMWA_USE_IMMERSIVE_DARK_MODE,
                    ctypes.byref(value),
                    ctypes.sizeof(value),
                )
            except:
                pass

        layout = QVBoxLayout()
        layout.setSpacing(16)
        layout.setContentsMargins(20, 20, 20, 20)

        title_label = QLabel("⏱️ Configuración de Exposición")
        title_label.setStyleSheet(f"""
            font-size: 16px;
            font-weight: bold;
            color: {'#A0A0A0' if self.dark_mode else '#00796B'};
            padding: 10px 0;
        """)
        layout.addWidget(title_label)

        brightness_title = QLabel("💡 Brillo Final al Completar")
        brightness_title.setStyleSheet(
            "font-size: 14px; font-weight: bold; margin-top: 10px;"
        )
        layout.addWidget(brightness_title)

        brightness_group = QButtonGroup(dialog)

        brightness_zero_radio = QRadioButton("🔴 Apagar (0% de brillo)")
        brightness_zero_radio.setChecked(self.final_brightness_mode == "zero")
        brightness_group.addButton(brightness_zero_radio, 0)

        brightness_full_radio = QRadioButton("🟢 Mantener encendido (100% de brillo)")
        brightness_full_radio.setChecked(self.final_brightness_mode == "full")
        brightness_group.addButton(brightness_full_radio, 1)

        layout.addWidget(brightness_zero_radio)
        layout.addWidget(brightness_full_radio)

        brightness_desc = QLabel(
            "Esta configuración controla el brillo de la imagen al finalizar todos los ciclos de exposición o el modo de frecuencia."
        )
        brightness_desc.setStyleSheet(
            "font-size: 11px; color: #888888; margin-left: 20px;"
        )
        brightness_desc.setWordWrap(True)
        layout.addWidget(brightness_desc)

        separator1 = QLabel()
        separator1.setStyleSheet(
            f"background-color: {'#3E3E3E' if self.dark_mode else '#CCCCCC'}; max-height: 1px;"
        )
        separator1.setFixedHeight(1)
        layout.addWidget(separator1)

        delay_title = QLabel("⏸️ Tiempo entre Ciclos")
        delay_title.setStyleSheet(
            "font-size: 14px; font-weight: bold; margin-top: 10px;"
        )
        layout.addWidget(delay_title)

        delay_desc = QLabel(
            "Tiempo de pausa (oscuridad) entre cada ciclo de exposición:"
        )
        delay_desc.setStyleSheet("font-size: 12px; margin-bottom: 5px;")
        layout.addWidget(delay_desc)

        delay_input_layout = QHBoxLayout()

        delay_input = QLineEdit()
        delay_input.setText(
            str(
                self.inter_cycle_delay
                if self.inter_cycle_delay < 1000
                else self.inter_cycle_delay // 1000
            )
        )
        delay_input.setPlaceholderText("0")
        delay_input.setMaximumWidth(100)
        delay_input_layout.addWidget(QLabel("Tiempo:"))
        delay_input_layout.addWidget(delay_input)

        delay_unit_combo = QComboBox()
        delay_unit_combo.addItems(["milisegundos", "segundos"])
        if self.inter_cycle_delay >= 1000:
            delay_unit_combo.setCurrentText("segundos")
        else:
            delay_unit_combo.setCurrentText("milisegundos")
        delay_unit_combo.setMaximumWidth(120)
        delay_input_layout.addWidget(delay_unit_combo)
        delay_input_layout.addStretch()

        layout.addLayout(delay_input_layout)

        delay_note = QLabel(
            "0 = Sin pausa entre ciclos | Durante la pausa, la imagen estará en 0% de brillo"
        )
        delay_note.setStyleSheet("font-size: 11px; color: #888888; margin-left: 20px;")
        delay_note.setWordWrap(True)
        layout.addWidget(delay_note)

        button_layout = QHBoxLayout()
        button_layout.addStretch()

        cancel_button = QPushButton("Cancelar")
        cancel_button.clicked.connect(dialog.reject)
        button_layout.addWidget(cancel_button)

        apply_button = QPushButton("✓ Aplicar")
        apply_button.setDefault(True)
        apply_button.clicked.connect(dialog.accept)
        button_layout.addWidget(apply_button)

        layout.addLayout(button_layout)

        dialog.setLayout(layout)

        dialog.setStyleSheet(f"""
            QDialog {{
                background-color: {'#1E1E1E' if self.dark_mode else '#FFFFFF'};
                color: {'#E0E0E0' if self.dark_mode else '#000000'};
            }}
            QRadioButton {{
                color: {'#E0E0E0' if self.dark_mode else '#000000'};
                font-size: 13px;
                padding: 5px;
            }}
            QRadioButton::indicator {{
                width: 18px;
                height: 18px;
            }}
            QLabel {{
                color: {'#E0E0E0' if self.dark_mode else '#000000'};
            }}
            QLineEdit {{
                background-color: {'#2C2C2C' if self.dark_mode else '#FFFFFF'};
                border: 1px solid {'#3E3E3E' if self.dark_mode else '#CCCCCC'};
                border-radius: 6px;
                padding: 6px;
                color: {'#E0E0E0' if self.dark_mode else '#000000'};
            }}
            QComboBox {{
                background-color: {'#2C2C2C' if self.dark_mode else '#F5F5F5'};
                border: 1px solid {'#3E3E3E' if self.dark_mode else '#CCCCCC'};
                border-radius: 6px;
                padding: 6px;
                color: {'#E0E0E0' if self.dark_mode else '#000000'};
            }}
            QPushButton {{
                background-color: {'#2C2C2C' if self.dark_mode else '#F0F0F0'};
                border: 1px solid {'#3E3E3E' if self.dark_mode else '#CCCCCC'};
                border-radius: 6px;
                padding: 8px 16px;
                color: {'#E0E0E0' if self.dark_mode else '#000000'};
                min-width: 80px;
            }}
            QPushButton:hover {{
                background-color: {'#3A3A3A' if self.dark_mode else '#E0E0E0'};
            }}
            QPushButton:default {{
                background-color: #A0A0A0;
                color: #000000;
                border: 1px solid #A0A0A0;
            }}
            QPushButton:default:hover {{
                background-color: #A0A0A0;
            }}
        """)

        if dialog.exec_() == QDialog.Accepted:
            self.final_brightness_mode = (
                "zero" if brightness_zero_radio.isChecked() else "full"
            )

            try:
                delay_value = float(delay_input.text())
                if delay_value < 0:
                    delay_value = 0

                if delay_unit_combo.currentText() == "segundos":
                    self.inter_cycle_delay = int(delay_value * 1000)
                else:
                    self.inter_cycle_delay = int(delay_value)
            except ValueError:
                self.inter_cycle_delay = 0


    def resume_next_cycle(self):
        if not self.exposure_active:
            return

        # QSlider requiere int, redondear desde float interno
        self.brightness_slider.setValue(int(round(self.exposure_target_brightness)))
        self.update_brightness()

        self.exposure_start_time = time.time()
        self.exposure_timer.start(int(round(self.exposure_duration * 1000)))
        self.countdown_timer.start()


    def show_grid_color_config(self):
        dialog = QDialog(self)
        dialog.setWindowTitle("Configuración de Grid")
        dialog.setFixedWidth(500)
        dialog.setWindowFlags(dialog.windowFlags() & ~Qt.WindowContextHelpButtonHint)

        if self.dark_mode and sys.platform == "win32":
            try:
                hwnd = int(dialog.winId())
                DWMWA_USE_IMMERSIVE_DARK_MODE = 20
                value = ctypes.c_int(1)
                ctypes.windll.dwmapi.DwmSetWindowAttribute(
                    hwnd,
                    DWMWA_USE_IMMERSIVE_DARK_MODE,
                    ctypes.byref(value),
                    ctypes.sizeof(value),
                )
            except:
                pass

        layout = QVBoxLayout(dialog)
        layout.setSpacing(15)
        layout.setContentsMargins(20, 20, 20, 20)

        # SECCIÓN 1: Color Grid Principal
        title1 = QLabel("🎨 Color del Grid Principal")
        title1.setStyleSheet("font-size: 16px; font-weight: bold; margin-bottom: 10px;")
        layout.addWidget(title1)

        color_layout1 = QHBoxLayout()
        color_label1 = QLabel("Color (hex):")
        self.temp_grid_color_input = QLineEdit()
        self.temp_grid_color_input.setText(self.grid_color)
        self.temp_grid_color_input.setPlaceholderText("#00FF00")
        self.temp_grid_color_input.setMaximumWidth(100)

        color_preview1 = QLabel("   ")
        color_preview1.setStyleSheet(
            f"background-color: {self.grid_color}; border: 1px solid #888; border-radius: 3px;"
        )
        color_preview1.setFixedSize(40, 40)

        def update_preview1():
            try:
                color = self.temp_grid_color_input.text()
                if color.startswith("#") and len(color) in [4, 7, 9]:
                    color_preview1.setStyleSheet(
                        f"background-color: {color}; border: 1px solid #888; border-radius: 3px;"
                    )
            except:
                pass

        self.temp_grid_color_input.textChanged.connect(update_preview1)

        color_layout1.addWidget(color_label1)
        color_layout1.addWidget(self.temp_grid_color_input)
        color_layout1.addWidget(color_preview1)
        color_layout1.addStretch()
        layout.addLayout(color_layout1)

        desc_label1 = QLabel("Seleccione un color predefinido:")
        desc_label1.setStyleSheet("font-size: 11px; margin-top: 10px;")
        layout.addWidget(desc_label1)

        colors_grid1 = QHBoxLayout()
        preset_colors = [
            ("#00FF00", "Verde"),
            ("#FF0000", "Rojo"),
            ("#0000FF", "Azul"),
            ("#FFFF00", "Amarillo"),
            ("#FF00FF", "Magenta"),
            ("#00FFFF", "Cian"),
            ("#FFFFFF", "Blanco"),
        ]

        for color, name in preset_colors:
            color_btn = QPushButton()
            color_btn.setFixedSize(40, 40)
            color_btn.setStyleSheet(
                f"background-color: {color}; border: 2px solid #888; border-radius: 5px;"
            )
            color_btn.setToolTip(name)
            color_btn.clicked.connect(
                lambda checked, c=color: (
                    self.temp_grid_color_input.setText(c),
                    update_preview1(),
                )
            )
            colors_grid1.addWidget(color_btn)

        layout.addLayout(colors_grid1)

        # SEPARADOR, pal grid
        separator = QLabel("─" * 60)
        separator.setStyleSheet("color: #555; margin: 15px 0;")
        layout.addWidget(separator)

        title2 = QLabel("🔍 Color del Grid de Píxeles")
        title2.setStyleSheet("font-size: 16px; font-weight: bold; margin-bottom: 10px;")
        layout.addWidget(title2)

        color_layout2 = QHBoxLayout()
        color_label2 = QLabel("Color (hex):")
        self.temp_pixel_grid_color_input = QLineEdit()
        self.temp_pixel_grid_color_input.setText(self.grid_pixel_color)
        self.temp_pixel_grid_color_input.setPlaceholderText("#FF00FF")
        self.temp_pixel_grid_color_input.setMaximumWidth(100)

        color_preview2 = QLabel("   ")
        color_preview2.setStyleSheet(
            f"background-color: {self.grid_pixel_color}; border: 1px solid #888; border-radius: 3px;"
        )
        color_preview2.setFixedSize(40, 40)

        def update_preview2():
            try:
                color = self.temp_pixel_grid_color_input.text()
                if color.startswith("#") and len(color) in [4, 7, 9]:
                    color_preview2.setStyleSheet(
                        f"background-color: {color}; border: 1px solid #888; border-radius: 3px;"
                    )
            except:
                pass

        self.temp_pixel_grid_color_input.textChanged.connect(update_preview2)

        color_layout2.addWidget(color_label2)
        color_layout2.addWidget(self.temp_pixel_grid_color_input)
        color_layout2.addWidget(color_preview2)
        color_layout2.addStretch()
        layout.addLayout(color_layout2)

        desc_label2 = QLabel("Seleccione un color predefinido:")
        desc_label2.setStyleSheet("font-size: 11px; margin-top: 10px;")
        layout.addWidget(desc_label2)

        colors_grid2 = QHBoxLayout()

        for color, name in preset_colors:
            color_btn = QPushButton()
            color_btn.setFixedSize(40, 40)
            color_btn.setStyleSheet(
                f"background-color: {color}; border: 2px solid #888; border-radius: 5px;"
            )
            color_btn.setToolTip(name)
            color_btn.clicked.connect(
                lambda checked, c=color: (
                    self.temp_pixel_grid_color_input.setText(c),
                    update_preview2(),
                )
            )
            colors_grid2.addWidget(color_btn)

        layout.addLayout(colors_grid2)

        button_layout = QHBoxLayout()
        ok_button = QPushButton("✓ Aceptar")
        ok_button.clicked.connect(dialog.accept)
        cancel_button = QPushButton("✗ Cancelar")
        cancel_button.clicked.connect(dialog.reject)
        button_layout.addWidget(ok_button)
        button_layout.addWidget(cancel_button)
        layout.addLayout(button_layout)

        dialog_style = f"""
            QDialog {{
                background-color: {'#1E1E1E' if self.dark_mode else '#FFFFFF'};
                color: {'#E0E0E0' if self.dark_mode else '#000000'};
            }}
            QLabel {{
                color: {'#E0E0E0' if self.dark_mode else '#000000'};
            }}
            QLineEdit {{
                background-color: {'#2E2E2E' if self.dark_mode else '#F5F5F5'};
                color: {'#E0E0E0' if self.dark_mode else '#000000'};
                border: 1px solid {'#3E3E3E' if self.dark_mode else '#CCCCCC'};
                border-radius: 4px;
                padding: 5px;
            }}
            QPushButton {{
                background-color: {'#2E2E2E' if self.dark_mode else '#E0E0E0'};
                color: {'#E0E0E0' if self.dark_mode else '#000000'};
                border: none;
                border-radius: 4px;
                padding: 8px 16px;
                font-weight: bold;
            }}
            QPushButton:hover {{
                background-color: #A0A0A0;
                color: #121212;
            }}
        """
        dialog.setStyleSheet(dialog_style)

        if dialog.exec_() == QDialog.Accepted:
            try:

                new_color = self.temp_grid_color_input.text()
                if new_color.startswith("#") and len(new_color) in [4, 7, 9]:
                    self.grid_color = new_color

                new_pixel_color = self.temp_pixel_grid_color_input.text()
                if new_pixel_color.startswith("#") and len(new_pixel_color) in [
                    4,
                    7,
                    9,
                ]:
                    self.grid_pixel_color = new_pixel_color

                self.save_grid_config()

                if (
                    self.grid_view_active
                    and hasattr(self, "grid_generated")
                    and self.grid_generated
                ):
                    self.display_grid()
            except:
                pass


    def apply_theme_and_fade_in(self):
        self.apply_theme()

        self.fade_in_animation = QPropertyAnimation(self.opacity_effect, b"opacity")
        self.fade_in_animation.setDuration(100)
        self.fade_in_animation.setStartValue(0.5)
        self.fade_in_animation.setEndValue(1.0)
        self.fade_in_animation.setEasingCurve(QEasingCurve.InCubic)

        self.fade_in_animation.finished.connect(lambda: self.setGraphicsEffect(None))
        self.fade_in_animation.start()

