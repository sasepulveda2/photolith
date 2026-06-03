"""
Mixin de temas visuales y eventos de ventana.

Aplica temas dark/light, gestiona la consola de log,
toolbar, deteccion de monitores y eventos de ventana.
"""
import sys
import ctypes
from datetime import datetime

from PyQt5.QtWidgets import QApplication, QMessageBox

from UI.themes import load_theme
from constants import (
    CONSOLE_LOG_COLORS,
    TOOLBAR_ACTIONS_TO_REMOVE,
    TOOLBAR_TOOLTIPS,
    EMPTY_CANVAS_TEXT_NORMAL,
    EMPTY_CANVAS_TEXT_GRID,
    EMPTY_CANVAS_FONT_SIZE,
    MONITOR_STATUS_CONNECTED,
    MONITOR_STATUS_CONNECTED_OFF,
    MONITOR_STATUS_DISCONNECTED,
    STYLE_MONITOR_CONNECTED_DARK,
    STYLE_MONITOR_CONNECTED_LIGHT,
    STYLE_MONITOR_CONNECTED_OFF_DARK,
    STYLE_MONITOR_CONNECTED_OFF_LIGHT,
    STYLE_MONITOR_DISCONNECTED,
    TOOLTIP_PROJECTOR_ENABLE,
    TOOLTIP_PROJECTOR_DISABLE,
    MSG_MONITOR_DISCONNECTED_TITLE,
    MSG_MONITOR_DISCONNECTED_BODY,
    DWMWA_USE_IMMERSIVE_DARK_MODE,
    DARK_BG_PRIMARY,
    LIGHT_BG_PRIMARY,
    DARK_TEXT_PRIMARY,
    LIGHT_TEXT_PRIMARY,
)


class ThemeMixin:
    """Mixin: Theme functionality."""

    def log_to_console(self, message: str, message_type: str = "INFO") -> None:
        """
        Agrega un mensaje a la consola del sistema con timestamp y tipo.

        Args:
            message: Mensaje a mostrar
            message_type: Tipo de mensaje - "INFO", "SUCCESS", "WARNING", "ERROR", "OPTIMIZATION", "SEGMENTATION"
        """
        timestamp = datetime.now().strftime("%H:%M:%S")
        color = CONSOLE_LOG_COLORS.get(message_type, CONSOLE_LOG_COLORS["INFO"])

        formatted_message = (
            f'<span style="color: #888888;">[{timestamp}]</span> '
            f'<span style="color: {color}; font-weight: bold;">[{message_type}]</span> '
            f'<span style="color: #E0E0E0;">{message}</span>'
        )

        self.system_console.append(formatted_message)
        
        # Scroll automático al final
        scrollbar = self.system_console.verticalScrollBar()
        scrollbar.setValue(scrollbar.maximum())

    def clear_console(self) -> None:
        """Limpia todos los mensajes de la consola."""
        self.system_console.clear()
        self.log_to_console("Consola limpiada", "INFO")

    def execute_system_command(self):
        """Ejecuta comandos del sistema desde la consola."""
        if not hasattr(self, "console_input"):
            return
            
        cmd = self.console_input.text().strip()
        if not cmd:
            return
            
        self.console_input.clear()
        self.log_to_console(f"$&gt; {cmd}", "INFO")
        
        if cmd.lower() in ["clear", "cls"]:
            self.clear_console()
            return
            
        if not hasattr(self, "cmd_process"):
            from PyQt5.QtCore import QProcess
            self.cmd_process = QProcess()
            self.cmd_process.setProcessChannelMode(QProcess.MergedChannels)
            self.cmd_process.readyReadStandardOutput.connect(self._handle_cmd_output)
            self.cmd_process.finished.connect(self._handle_cmd_finished)
            
        if self.cmd_process.state() == 2: # QProcess::Running
            self.log_to_console("⚠️ Espere a que el comando actual termine.", "WARNING")
            return
            
        import shutil
        if shutil.which("powershell"):
            self.cmd_process.start("powershell.exe", ["-NoProfile", "-Command", cmd])
        elif shutil.which("cmd"):
            self.cmd_process.start("cmd.exe", ["/c", cmd])
        else:
            self.log_to_console("Error: No se encontró PowerShell ni CMD.", "ERROR")

    def _handle_cmd_output(self):
        """Procesa y muestra la salida estándar de comandos del sistema."""
        if not hasattr(self, "cmd_process"): return
        
        output_bytes = self.cmd_process.readAllStandardOutput().data()
        try:
            # PowerShell usually outputs in utf-8 or cp1252 depending on the system
            output = output_bytes.decode('utf-8', errors='replace').strip()
        except:
            output = output_bytes.decode('cp850', errors='replace').strip()
            
        if output:
            import html
            safe_output = html.escape(output).replace("\\n", "<br>")
            formatted_message = f'<div style="color: #A6E3A1; font-family: Consolas, monospace; white-space: pre-wrap; margin-left: 10px;">{safe_output}</div>'
            self.system_console.append(formatted_message)
            
            scrollbar = self.system_console.verticalScrollBar()
            scrollbar.setValue(scrollbar.maximum())

    def _handle_cmd_finished(self, exitCode, exitStatus):
        """Maneja el fin de un comando."""
        if exitCode != 0:
            self.log_to_console(f"Comando finalizó con código {exitCode}", "ERROR")

    def apply_theme(self) -> None:
        """Aplica el tema actual (dark/light) a toda la aplicación."""
        if self.dark_mode:
            self.apply_dark_theme()
        else:
            self.apply_light_theme()

        self._set_titlebar_dark_mode(self.dark_mode)

        if getattr(self, "pattern", None) is not None:
            self.simulate_optics()

    def apply_dark_theme(self) -> None:
        """Aplica la paleta y hoja de estilos del tema oscuro."""
        self.figure.set_facecolor(DARK_BG_PRIMARY)
        self.canvas.draw()
        self.setStyleSheet(load_theme("dark"))

    def apply_light_theme(self) -> None:
        """Aplica la paleta y hoja de estilos del tema claro."""
        self.figure.set_facecolor(LIGHT_BG_PRIMARY)
        self.canvas.draw()
        self.setStyleSheet(load_theme("light"))

    def _set_titlebar_dark_mode(self, enabled: bool) -> None:
        """Aplica el modo inmersivo a la barra de título de Windows si es posible."""
        try:
            if sys.platform == "win32":
                hwnd = int(self.winId())
                value = ctypes.c_int(1 if enabled else 0)
                ctypes.windll.dwmapi.DwmSetWindowAttribute(
                    hwnd,
                    DWMWA_USE_IMMERSIVE_DARK_MODE,
                    ctypes.byref(value),
                    ctypes.sizeof(value),
                )
        except Exception as e:
            mode_name = "oscura" if enabled else "clara"
            print(f"No se pudo aplicar barra de título {mode_name}: {e}")

    # Mantenemos firmas antiguas por compatibilidad para no romper referencias
    # en otras partes del código si existieran
    def set_dark_titlebar(self):
        self._set_titlebar_dark_mode(True)

    def set_light_titlebar(self):
        self._set_titlebar_dark_mode(False)

    def toggle_grid_view(self) -> None:
        """Alterna entre la vista de grid/edición y la vista normal de previsualización."""
        self.grid_view_active = not getattr(self, "grid_view_active", False)

        if self.grid_view_active:
            self._activate_grid_view()
        else:
            self._deactivate_grid_view()

        self._refresh_invert_button_state()

    def _activate_grid_view(self) -> None:
        """Activa los paneles y componentes visuales del modo grid."""
        if getattr(self, "calibration_view_active", False):
            self.hide_calibration_interface()
            self.calibration_view_active = False
            if hasattr(self, "calibration_button"):
                self.calibration_button.setText("🎯 Calibración")

        if hasattr(self, "toggle_view_button"):
            self.toggle_view_button.setText("🖼️ Vista Imagen")
        
        # Mostrar componentes del grid
        if hasattr(self, "grid_config_section"):
            self.grid_config_section.setVisible(True)
            self.grid_config_section.set_collapsed(False)
        if hasattr(self, "grid_stats_section"):
            self.grid_stats_section.setVisible(True)
            self.grid_stats_section.set_collapsed(False)
        if hasattr(self, "segmentation_section"):
            self.segmentation_section.setVisible(True)
            self.segmentation_section.set_collapsed(False)
        if hasattr(self, "projection_control_section"):
            self.projection_control_section.setVisible(True)
            self.projection_control_section.set_collapsed(False)
        if hasattr(self, "toolbar"):
            self.toolbar.setVisible(True)

        # Preparar imagen para grid
        if getattr(self, "pattern", None) is not None:
            if getattr(self, "apply_effects_to_grid", False):
                self.image_on_grid = self.apply_grid_effects(self.pattern.copy())
            else:
                self.image_on_grid = self.pattern.copy()
                
            self.image_position = [0, 0]
            if hasattr(self, "image_coords_section"):
                self.image_coords_section.setVisible(True)
                self.image_coords_section.set_collapsed(False)
            self.update_image_coordinates()
        else:
            self.image_on_grid = None
            if hasattr(self, "image_coords_section"):
                self.image_coords_section.setVisible(False)

        if getattr(self, "grid_generated", False):
            if hasattr(self, "generate_grid_button"):
                self.generate_grid_button.setText("💾 Guardar Nuevo Tamaño")
            self.display_grid()
        else:
            if hasattr(self, "generate_grid_button"):
                self.generate_grid_button.setText("🎨 Generar Grid")
            if hasattr(self, "grid_stats_section"):
                self.grid_stats_section.setVisible(False)
            self._show_empty_canvas(EMPTY_CANVAS_TEXT_GRID)

    def _deactivate_grid_view(self) -> None:
        """Desactiva el modo grid y restaura la vista normal."""
        if hasattr(self, "toggle_view_button"):
            self.toggle_view_button.setText("📏 Vista Grid")
        
        # Ocultar componentes del grid
        if hasattr(self, "grid_config_section"):
            self.grid_config_section.setVisible(False)
        if hasattr(self, "grid_stats_section"):
            self.grid_stats_section.setVisible(False)
        if hasattr(self, "image_coords_section"):
            self.image_coords_section.setVisible(False)
        if hasattr(self, "segmentation_section"):
            self.segmentation_section.setVisible(False)
        if hasattr(self, "projection_control_section"):
            self.projection_control_section.setVisible(False)
        if hasattr(self, "toolbar"):
            self.toolbar.setVisible(False)

        if getattr(self, "pattern", None) is not None:
            self.simulate_optics()
        else:
            self._show_empty_canvas(EMPTY_CANVAS_TEXT_NORMAL)

    def toggle_calibration_view(self) -> None:
        """Alterna entre vista normal y vista de calibración."""
        self.calibration_view_active = not getattr(self, "calibration_view_active", False)

        if self.calibration_view_active:
            if getattr(self, "grid_view_active", False):
                self.toggle_grid_view()

            if hasattr(self, "calibration_button"):
                self.calibration_button.setText("🖼️ Vista Normal")
            self.show_calibration_interface()
        else:
            if hasattr(self, "calibration_button"):
                self.calibration_button.setText("🎯 Calibración")
            self.hide_calibration_interface()

            if getattr(self, "pattern", None) is not None:
                self.simulate_optics()
            else:
                self._show_empty_canvas(EMPTY_CANVAS_TEXT_NORMAL)

    def _show_empty_canvas(self, message: str) -> None:
        """Limpia el canvas y muestra un mensaje centrado."""
        if not hasattr(self, "ax"):
            return
            
        self.canvas.figure.clear()
        self.ax = self.canvas.figure.add_subplot(111)
        
        bg_color = DARK_BG_PRIMARY if self.dark_mode else LIGHT_BG_PRIMARY
        text_color = DARK_TEXT_PRIMARY if self.dark_mode else LIGHT_TEXT_PRIMARY
        
        self.ax.set_facecolor(bg_color)
        self.ax.text(
            0.5, 0.5, message,
            ha="center", va="center",
            fontsize=EMPTY_CANVAS_FONT_SIZE,
            color=text_color,
        )
        self.ax.set_xlim(0, 1)
        self.ax.set_ylim(0, 1)
        self.ax.axis("off")
        self.canvas.draw()

    def check_second_monitor(self) -> bool:
        """
        Detecta el monitor secundario y gestiona dinámicamente la interfaz de proyección.
        Los campos de resolución se deshabilitan/ocultan si no hay monitor externo detectado.
        
        Returns:
            bool: True si hay más de un monitor conectado.
        """
        screens = QApplication.screens()
        has_second = len(screens) > 1

        self._update_monitor_status_label(has_second, screens)
        self._update_projector_button_state(has_second)
        self._update_projection_visibility(has_second)

        return has_second

    def _update_monitor_status_label(self, has_second: bool, screens: list) -> None:
        """Actualiza el label indicador de estado del monitor."""
        if not hasattr(self, "monitor_resolution_label"):
            return

        self.monitor_resolution_label.setVisible(True)

        if not has_second:
            self.monitor_resolution_label.setText(MONITOR_STATUS_DISCONNECTED)
            self.monitor_resolution_label.setStyleSheet(STYLE_MONITOR_DISCONNECTED)
            return

        is_active = getattr(self, "projector_active", False)
        
        if is_active:
            geometry = screens[1].geometry()
            self.monitor_resolution_label.setText(
                MONITOR_STATUS_CONNECTED.format(f"{geometry.width()}x{geometry.height()}")
            )
            self.monitor_resolution_label.setStyleSheet(
                STYLE_MONITOR_CONNECTED_DARK if getattr(self, "dark_mode", True) else STYLE_MONITOR_CONNECTED_LIGHT
            )
        else:
            self.monitor_resolution_label.setText(MONITOR_STATUS_CONNECTED_OFF)
            self.monitor_resolution_label.setStyleSheet(
                STYLE_MONITOR_CONNECTED_OFF_DARK if getattr(self, "dark_mode", True) else STYLE_MONITOR_CONNECTED_OFF_LIGHT
            )

    def _update_projector_button_state(self, has_second: bool) -> None:
        """Habilita o deshabilita el botón de proyección según el monitor."""
        if not hasattr(self, "projector_button"):
            return

        if has_second:
            self.projector_button.setEnabled(True)
            self.projector_button.setToolTip(TOOLTIP_PROJECTOR_ENABLE)
        else:
            is_active = getattr(self, "projector_active", False)
            if not is_active:
                self.projector_button.setEnabled(False)
                self.projector_button.setToolTip(TOOLTIP_PROJECTOR_DISABLE)

    def _update_projection_visibility(self, has_second: bool) -> None:
        """Oculta o muestra campos de escala/resolución según el monitor y proyección."""
        is_active = getattr(self, "projector_active", False)
        should_show = has_second and is_active

        if hasattr(self, "projected_resolution_label"):
            self.projected_resolution_label.setVisible(should_show)
            
        if hasattr(self, "scale_info_label"):
            self.scale_info_label.setVisible(should_show)

    def _update_projection_resolution_fields(self, show: bool) -> None:
        """
        Gestiona dinámicamente la visibilidad de los campos de resolución de proyección.

        Args:
            show: True para mostrar los campos, False para ocultarlos
        """
        if hasattr(self, "projected_resolution_label"):
            self.projected_resolution_label.setVisible(show)
            if not show:
                self.projected_resolution_label.setText("Resolución proyectada: -")

        if hasattr(self, "scale_info_label"):
            self.scale_info_label.setVisible(show)
            if not show:
                self.scale_info_label.setText("Escala proyección: -")

    def on_screen_changed(self) -> None:
        """
        Se llama cuando cambia la configuración de monitores.
        Actualiza dinámicamente la interfaz y la ventana de proyección.
        """
        has_monitor = self.check_second_monitor()

        if getattr(self, "projection_window", None) and self.projection_window.isVisible():
            screens = QApplication.screens()
            
            if len(screens) > 1:
                secondary_screen = screens[1]
            elif has_monitor:
                secondary_screen = screens[0]
            else:
                # Cerrar proyección si se perdió el monitor externo
                QMessageBox.warning(
                    self,
                    MSG_MONITOR_DISCONNECTED_TITLE,
                    MSG_MONITOR_DISCONNECTED_BODY,
                )
                self.projector_active = False
                self.projection_window.close()
                self.projection_window = None
                if hasattr(self, "update_projector_button"):
                    self.update_projector_button()
                return

            geometry = secondary_screen.geometry()
            self.projection_window.screen_geometry = geometry
            self.projection_window.setGeometry(geometry)

    def show_exposure_section(self) -> None:
        """Muestra el tab de exposición y oculta el de frecuencia."""
        if hasattr(self, "exposure_section"):
            self.exposure_section.setVisible(True)
            self.exposure_section.set_collapsed(False)
        if hasattr(self, "frequency_section"):
            self.frequency_section.setVisible(False)
        if hasattr(self, "exposure_tab_button"):
            self.exposure_tab_button.setChecked(True)
        if hasattr(self, "frequency_tab_button"):
            self.frequency_tab_button.setChecked(False)

    def show_frequency_section(self) -> None:
        """Muestra el tab de frecuencia y oculta el de exposición."""
        if hasattr(self, "exposure_section"):
            self.exposure_section.setVisible(False)
        if hasattr(self, "frequency_section"):
            self.frequency_section.setVisible(True)
            self.frequency_section.set_collapsed(False)
        if hasattr(self, "exposure_tab_button"):
            self.exposure_tab_button.setChecked(False)
        if hasattr(self, "frequency_tab_button"):
            self.frequency_tab_button.setChecked(True)

    def showEvent(self, event) -> None:
        super().showEvent(event)
        self._set_titlebar_dark_mode(getattr(self, "dark_mode", True))

    def closeEvent(self, event) -> None:
        if getattr(self, "projection_window", None) is not None:
            self.projection_window.close()
            self.projection_window = None
        super().closeEvent(event)

    def customize_toolbar(self) -> None:
        """Personaliza la toolbar de matplotlib, eliminando botones innecesarios y actualizando tooltips."""
        if not hasattr(self, "toolbar"):
            return
            
        for action in self.toolbar.actions():
            if action.text() in TOOLBAR_ACTIONS_TO_REMOVE:
                self.toolbar.removeAction(action)
            elif action.text() in TOOLBAR_TOOLTIPS:
                action.setToolTip(TOOLBAR_TOOLTIPS[action.text()])
