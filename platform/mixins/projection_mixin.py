"""
Mixin de control de proyeccion.

Gestiona proyeccion en monitor secundario, exposicion temporizada,
modo frecuencia, secuencias de segmentos y aplicacion de efectos.
"""
import time
import cv2
import numpy as np

from PyQt5.QtWidgets import QMessageBox
from PyQt5.QtCore import QTimer
from projection_window import ProjectionWindow
from constants import (
    MSG_PROJECTOR_NOT_DETECTED_TITLE,
    MSG_PROJECTOR_NOT_DETECTED_BODY,
    MSG_PROJECTOR_INACTIVE_TITLE,
    MSG_PROJECTOR_INACTIVE_BODY,
    ERR_CONFLICT_TITLE,
    ERR_CONFLICT_EXPOSURE,
    ERR_CONFLICT_FREQUENCY,
    ERR_CONFLICT_SEQUENCE,
    MSG_NO_IMAGE_PROJ_TITLE,
    MSG_NO_IMAGE_PROJ_BODY,
    MSG_INVALID_EXPOSURE_TIME,
    MSG_INVALID_INTENSITY,
    MSG_INVALID_CYCLES,
    MSG_INVALID_FREQUENCY,
    MSG_INVALID_DURATION,
    MSG_NO_SEGMENTS_TITLE,
    MSG_NO_SEGMENTS_BODY,
    STYLE_PROJECTOR_BTN_DISCONNECTED,
    STYLE_BTN_ACTIVE_RED,
)


class ProjectionMixin:
    """Mixin: Projection functionality."""

    # ═══════════════════════════════════════════════════════════════════════════
    # GESTIÓN DEL PROYECTOR Y VENTANA SECUNDARIA
    # ═══════════════════════════════════════════════════════════════════════════

    def toggle_projector(self):
        """Activa o desactiva la ventana de proyección secundaria."""
        self.has_second_monitor = self.check_second_monitor()
        
        if not self.has_second_monitor and not getattr(self, "projector_active", False):
            self._show_warning(MSG_PROJECTOR_NOT_DETECTED_TITLE, MSG_PROJECTOR_NOT_DETECTED_BODY)
            self.update_projector_button()
            return

        if not self.has_second_monitor and getattr(self, "projector_active", False):
            self._force_close_projection_on_disconnect()
            return

        self.projector_active = not getattr(self, "projector_active", False)

        if self.projector_active:
            self._activate_projector()
        else:
            self._deactivate_projector()

        self.update_projector_button()

    def _activate_projector(self):
        """Inicializa la ventana de proyección con pantalla negra."""
        image_to_project = self._get_projection_image()
        is_ruler = getattr(self, "_ruler_scale_view_active", False)
        is_pattern_calib = getattr(self, "_pattern_calib_view_active", False)
        
        if image_to_project is None and not is_ruler and not is_pattern_calib:
            self.log_to_console("Advertencia: No hay imagen principal cargada, abriendo proyector en negro.", "WARNING")

        self.projection_window = ProjectionWindow(self)
        self.projection_window.set_inversion(getattr(self, "invert_projection", False))
        self.projection_window.set_binary_threshold(getattr(self, "binary_threshold", 127))
        self.projection_window.set_binary_mode(getattr(self, "binary_mode_enabled", False))
        self.projection_window.show_on_secondary_monitor()
        self.projection_window.show_black_screen()

        self.log_to_console(
            "Proyector activado - Pantalla en NEGRO\n"
            "La imagen se proyectará al iniciar Exposición, Frecuencia o Secuencia",
            "INFO",
        )
        self._set_projection_ui_visibility(True)

    def _deactivate_projector(self):
        """Detiene cualquier modo activo y cierra la ventana de proyección."""
        self._stop_all_active_modes()

        if getattr(self, "projection_window", None) is not None:
            self.projection_window.close()
            self.projection_window = None

        self._set_projection_ui_visibility(False)

    def _force_close_projection_on_disconnect(self):
        """Cierra la proyección si el monitor se desconectó abruptamente."""
        if getattr(self, "projection_window", None) is not None:
            self.projection_window.close()
            self.projection_window = None
        
        self.projector_active = False
        self._set_projection_ui_visibility(False)
        self.update_projector_button()
        
        self._show_warning(
            "Monitor desconectado",
            "Se perdió la conexión con el segundo monitor.\n\nLa proyección se ha detenido."
        )

    def _set_projection_ui_visibility(self, visible: bool):
        """Muestra u oculta los controles dependientes de la proyección."""
        if hasattr(self, "brightness_slider"):
            self.brightness_slider.setVisible(visible)
            self.brightness_label.setVisible(visible)
            self.project_image_button.setVisible(visible)
            
            if not visible:
                self.exposure_button.setVisible(False)
                self.stop_exposure_button.setVisible(False)
                self.frequency_button.setVisible(False)
                self.stop_frequency_button.setVisible(False)
            else:
                self.exposure_button.setVisible(True)
                self.frequency_button.setVisible(True)

        self._update_projection_resolution_fields(visible)

    def _stop_all_active_modes(self):
        """Fuerza la detención de cualquier operación de proyección activa."""
        if getattr(self, "exposure_active", False):
            self.force_stop_exposure()
        if getattr(self, "frequency_mode", False):
            self.force_stop_frequency()
        if getattr(self, "sequence_running", False):
            self.stop_sequence()
            self.log_to_console("Secuencia detenida - Proyector desactivado", "INFO")

    def on_projection_closed(self):
        """Callback cuando el usuario cierra la ventana secundaria manualmente."""
        self._stop_all_active_modes()
        self.projector_active = False
        self.projection_window = None
        self._set_projection_ui_visibility(False)
        self.update_projector_button()

    def update_projector_button(self):
        """Actualiza el estilo y texto del botón del proyector."""
        if not hasattr(self, "projector_button"):
            return

        from PyQt5.QtWidgets import QApplication
        self.has_second_monitor = len(QApplication.screens()) > 1

        if not self.has_second_monitor:
            led, status = "", "DESCONECTADO"
            self.projector_button.setStyleSheet(STYLE_PROJECTOR_BTN_DISCONNECTED)
        elif getattr(self, "projector_active", False):
            led, status = "", "ACTIVO"
            self.projector_button.setStyleSheet("")
        else:
            led, status = "", "INACTIVO"
            self.projector_button.setStyleSheet("")
            
        self.projector_button.setText(f"{led} Proyectar ({status})")

    # ═══════════════════════════════════════════════════════════════════════════
    # PROYECCIÓN MANUAL (IMAGEN COMPLETA)
    # ═══════════════════════════════════════════════════════════════════════════

    def project_full_image(self):
        """Alterna la proyección manual de la imagen completa (brillo 100%)."""
        self.is_projecting_full_image = getattr(self, "is_projecting_full_image", False)

        if not getattr(self, "projector_active", False):
            self._show_warning(MSG_PROJECTOR_INACTIVE_TITLE, "Use el botón 'Proyectar' primero.")
            return

        if getattr(self, "projection_window", None) is None:
            self._show_warning("Error", "No hay ventana de proyección disponible.")
            return

        if not self.is_projecting_full_image:
            self._start_full_image_projection()
        else:
            self._stop_full_image_projection()

    def _start_full_image_projection(self):
        image_to_project = self._get_projection_image()
        if image_to_project is None:
            self._show_warning(MSG_NO_IMAGE_PROJ_TITLE, MSG_NO_IMAGE_PROJ_BODY)
            return

        # Guardar brillo y forzar 100%
        self._prev_brightness_for_full_img = getattr(self, "brightness", 100.0)
        self.projection_window.set_brightness(100.0)
        
        self.projection_window.update_image(image_to_project)
        self.is_projecting_full_image = True
        
        if hasattr(self, "project_image_button"):
            self.project_image_button.setText("Detener imagen completa")
            self.project_image_button.setStyleSheet(STYLE_BTN_ACTIVE_RED)

        self.log_to_console("Proyectando imagen completa en monitor secundario (Brillo 100%)", "SUCCESS")

    def _stop_full_image_projection(self):
        # Restaurar brillo original
        prev_brightness = getattr(self, "_prev_brightness_for_full_img", 100.0)
        self.projection_window.set_brightness(prev_brightness)
        
        self.projection_window.show_black_screen()
        self.is_projecting_full_image = False
        
        if hasattr(self, "project_image_button"):
            self.project_image_button.setText("Proyectar imagen completa")
            self.project_image_button.setStyleSheet("")
            
        self.log_to_console("Proyección de imagen completa detenida.", "INFO")

    # ═══════════════════════════════════════════════════════════════════════════
    # MODO EXPOSICIÓN TEMPORIZADA
    # ═══════════════════════════════════════════════════════════════════════════

    def start_timed_exposure(self):
        """Inicia el ciclo de exposición temporizada."""
        if not self._can_start_operation("la exposición temporizada"):
            return

        if getattr(self, "is_projecting_full_image", False):
            self.project_full_image()

        params = self._parse_exposure_parameters()
        if not params:
            return

        self._prepare_projection_for_operation()
        self._initialize_exposure_state(params)
        self._set_exposure_ui_state(active=True)
        self._start_exposure_timers(params["time"])

    def _can_start_operation(self, operation_name: str) -> bool:
        """Verifica que no haya conflictos con otros modos."""
        if getattr(self, "sequence_running", False):
            self._show_warning(ERR_CONFLICT_TITLE, ERR_CONFLICT_SEQUENCE.format(operation_name))
            return False
        if getattr(self, "frequency_mode", False):
            self._show_warning(ERR_CONFLICT_TITLE, ERR_CONFLICT_FREQUENCY.format(operation_name))
            return False
        if getattr(self, "exposure_active", False):
            self._show_warning(ERR_CONFLICT_TITLE, ERR_CONFLICT_EXPOSURE.format(operation_name))
            return False
        if not getattr(self, "projector_active", False):
            self._show_warning(MSG_PROJECTOR_INACTIVE_TITLE, MSG_PROJECTOR_INACTIVE_BODY)
            return False
        return True

    def _parse_exposure_parameters(self) -> dict:
        """Parsea y valida los parámetros de la UI para exposición."""
        try:
            exp_time = float(self.exposure_time_input.text())
            if exp_time <= 0: raise ValueError()
        except ValueError:
            self._show_warning("Tiempo inválido", MSG_INVALID_EXPOSURE_TIME)
            return {}

        try:
            intensity = float(self.exposure_intensity_input.text())
            if not (0 <= intensity <= 100): raise ValueError()
        except ValueError:
            self._show_warning("Intensidad inválida", MSG_INVALID_INTENSITY)
            return {}

        try:
            cycles = int(self.exposure_cycles_input.text())
            if cycles <= 0: raise ValueError()
        except ValueError:
            self._show_warning("Ciclos inválidos", MSG_INVALID_CYCLES)
            return {}

        return {"time": exp_time, "intensity": intensity, "cycles": cycles}

    def _prepare_projection_for_operation(self):
        """Asegura que la imagen base esté cargada en la ventana de proyección."""
        image_to_project = self._get_projection_image()
        if self.projection_window is not None and image_to_project is not None:
            self.projection_window.update_image(image_to_project)
            self.projection_window.set_inversion(getattr(self, "invert_projection", False))
            self.projection_window.set_binary_mode(getattr(self, "binary_mode_enabled", False))
            self.projection_window.set_binary_threshold(getattr(self, "binary_threshold", 127))

    def _initialize_exposure_state(self, params: dict):
        self.exposure_duration = params["time"]
        self.exposure_target_brightness = params["intensity"]
        self.exposure_cycles_total = params["cycles"]
        self.exposure_cycles_completed = 0
        self.exposure_start_time = float(time.time())
        self.exposure_active = True

        self.brightness_slider.setValue(int(round(params["intensity"])))
        self.update_brightness()

    def _set_exposure_ui_state(self, active: bool):
        self.exposure_button.setVisible(not active)
        self.stop_exposure_button.setVisible(active)
        
        state = not active
        self.exposure_time_input.setEnabled(state)
        self.exposure_intensity_input.setEnabled(state)
        self.exposure_cycles_input.setEnabled(state)
        self.brightness_slider.setEnabled(state)

    def _start_exposure_timers(self, exposure_time: float):
        if hasattr(self, "exposure_timer"):
            self.exposure_timer.start(int(round(exposure_time * 1000)))
            self.countdown_timer.start()
            self.update_countdown()

    def update_countdown(self):
        if not getattr(self, "exposure_active", False):
            return

        elapsed = float(time.time()) - self.exposure_start_time
        remaining = max(0.0, self.exposure_duration - elapsed)
        
        cycle_info = f"Ciclo {self.exposure_cycles_completed + 1}/{self.exposure_cycles_total}"
        if remaining < 1.0:
            self.exposure_status_label.setText(f"{cycle_info} | Tiempo restante: {remaining*1000:.3f}ms")
        else:
            self.exposure_status_label.setText(f"{cycle_info} | Tiempo restante: {remaining:.3f}s")

    def stop_timed_exposure(self):
        """Llamado por el timer cuando un ciclo de exposición finaliza."""
        self.countdown_timer.stop()
        self.exposure_cycles_completed += 1

        if self.exposure_cycles_completed < self.exposure_cycles_total:
            self._prepare_next_exposure_cycle()
        else:
            self.finish_exposure_sequence()

    def _prepare_next_exposure_cycle(self):
        self.brightness_slider.setValue(0)
        self.update_brightness()
        self.exposure_status_label.setText(
            f"Ciclo {self.exposure_cycles_completed}/{self.exposure_cycles_total} completado | Preparando siguiente ciclo..."
        )
        
        inter_delay = getattr(self, "inter_cycle_delay", 0)
        if inter_delay > 0 and hasattr(self, "inter_cycle_timer"):
            self.inter_cycle_timer.start(inter_delay)
        elif hasattr(self, "resume_next_cycle"):
            self.resume_next_cycle()

    def finish_exposure_sequence(self):
        self._stop_exposure_timers()
        self._restore_brightness_after_exposure()
        self._set_exposure_ui_state(active=False)
        self.exposure_active = False

        b_mode = getattr(self, "final_brightness_mode", "zero")
        self.exposure_status_label.setText(
            f"Exposición completada: {self.exposure_cycles_completed} ciclo(s) | Brillo final: {'0%' if b_mode == 'zero' else '100%'}"
        )

    def force_stop_exposure(self):
        self._stop_exposure_timers()
        self._restore_brightness_after_exposure()
        self._set_exposure_ui_state(active=False)
        self.exposure_active = False

        self.exposure_status_label.setText(
            f"Exposición detenida: {self.exposure_cycles_completed}/{self.exposure_cycles_total} ciclo(s) completados"
        )

    def _stop_exposure_timers(self):
        if hasattr(self, "exposure_timer"):
            self.exposure_timer.stop()
            self.countdown_timer.stop()
        if hasattr(self, "inter_cycle_timer"):
            self.inter_cycle_timer.stop()

    def _restore_brightness_after_exposure(self):
        target = 0 if getattr(self, "final_brightness_mode", "zero") == "zero" else 100
        self.brightness_slider.setValue(target)
        self.update_brightness()

    def toggle_exposure_mirror(self, checked):
        self.exposure_mirror_h = bool(checked)
        self.log_to_console(f"Modo espejo X de exposición: {'Activado' if checked else 'Desactivado'}", "INFO")
        
        if getattr(self, "is_projecting_full_image", False):
            self.is_projecting_full_image = False
            self.project_full_image()
        elif getattr(self, "current_projecting_segment", None):
            self._update_paused_segment_projection()
            
        if getattr(self, "pattern", None) is not None and not getattr(self, "grid_view_active", False):
            if hasattr(self, "simulate_optics"):
                self.simulate_optics()

    def toggle_exposure_mirror_y(self, checked):
        self.exposure_mirror_v = bool(checked)
        self.log_to_console(f"Modo espejo Y de exposición: {'Activado' if checked else 'Desactivado'}", "INFO")
        
        if getattr(self, "is_projecting_full_image", False):
            self.is_projecting_full_image = False
            self.project_full_image()
        elif getattr(self, "current_projecting_segment", None):
            self._update_paused_segment_projection()
            
        if getattr(self, "pattern", None) is not None and not getattr(self, "grid_view_active", False):
            if hasattr(self, "simulate_optics"):
                self.simulate_optics()

    def _update_paused_segment_projection(self):
        if not getattr(self, "sequence_paused", False): return
        
        seg = self.current_projecting_segment.get("segment_data")
        if seg and getattr(self, "projector_active", False) and self.projection_window:
            processed = self._apply_effects_to_segment(seg["image"], skip_binary_effects=seg.get("effects_applied", False))
            self.projection_window.update_segment(processed)

    # ═══════════════════════════════════════════════════════════════════════════
    # MODO FRECUENCIA
    # ═══════════════════════════════════════════════════════════════════════════

    def start_frequency_mode(self):
        if not self._can_start_operation("el modo de frecuencia"):
            return

        if getattr(self, "is_projecting_full_image", False):
            self.project_full_image()

        params = self._parse_frequency_parameters()
        if not params:
            return

        self._prepare_projection_for_operation()
        
        self.frequency_mode = True
        self.frequency_period = params["period"]
        self.frequency_duration = params["duration"]
        self.exposure_target_brightness = params["intensity"]
        self.frequency_start_time = time.time()
        self.frequency_cycle_count = 0

        self._set_frequency_ui_state(active=True)

        if params["duration"] > 0 and hasattr(self, "frequency_timer"):
            self.frequency_timer.start(int(params["duration"] * 1000))

        self.start_frequency_cycle()

    def _parse_frequency_parameters(self) -> dict:
        try:
            freq = float(self.frequency_value_input.text())
            if freq <= 0: raise ValueError()
        except ValueError:
            self._show_warning("Frecuencia inválida", MSG_INVALID_FREQUENCY)
            return {}

        unit = self.frequency_unit_combo.currentText()
        freq_hz = freq * 1000 if unit == "kHz" else (freq * 1000000 if unit == "MHz" else freq)
        period = 1.0 / freq_hz

        try:
            duration = float(self.frequency_duration_input.text())
            if duration < 0: raise ValueError()
        except ValueError:
            self._show_warning("Duración inválida", MSG_INVALID_DURATION)
            return {}

        try:
            intensity = int(self.exposure_intensity_input.text())
            if not (0 <= intensity <= 100): raise ValueError()
        except ValueError:
            self._show_warning("Intensidad inválida", "Por favor configure una intensidad válida (0-100).")
            return {}

        return {"period": period, "duration": duration, "intensity": intensity}

    def _set_frequency_ui_state(self, active: bool):
        self.frequency_button.setVisible(not active)
        self.stop_frequency_button.setVisible(active)
        
        state = not active
        self.frequency_value_input.setEnabled(state)
        self.frequency_unit_combo.setEnabled(state)
        self.frequency_duration_input.setEnabled(state)
        self.exposure_intensity_input.setEnabled(state)
        self.brightness_slider.setEnabled(state)

    def start_frequency_cycle(self):
        if not getattr(self, "frequency_mode", False):
            return

        self.brightness_slider.setValue(int(round(self.exposure_target_brightness)))
        self.update_brightness()

        self.frequency_cycle_count += 1
        self._update_frequency_status_label()

        on_time_ms = int((self.frequency_period / 2.0) * 1000)
        QTimer.singleShot(on_time_ms, self.frequency_off_phase)

    def _update_frequency_status_label(self):
        prefix = f"Ciclo #{self.frequency_cycle_count} | "
        if self.frequency_duration > 0:
            elapsed = time.time() - self.frequency_start_time
            rem = max(0, self.frequency_duration - elapsed)
            self.frequency_status_label.setText(f"{prefix}Frecuencia activa | Tiempo restante: {rem:.1f}s")
        else:
            self.frequency_status_label.setText(f"{prefix}Frecuencia activa (infinito)")

    def frequency_off_phase(self):
        if not getattr(self, "frequency_mode", False):
            return

        self.brightness_slider.setValue(0)
        self.update_brightness()

        off_time_ms = int((self.frequency_period / 2.0) * 1000)
        QTimer.singleShot(off_time_ms, self.start_frequency_cycle)

    def stop_frequency_mode(self):
        self.force_stop_frequency()
        b_mode = getattr(self, "final_brightness_mode", "zero")
        self.frequency_status_label.setText(
            f"Modo de frecuencia completado: {self.frequency_cycle_count} ciclos - Brillo final: {'0%' if b_mode == 'zero' else '100%'}"
        )

    def force_stop_frequency(self):
        self.frequency_mode = False
        if hasattr(self, "frequency_timer"):
            self.frequency_timer.stop()

        self._restore_brightness_after_exposure()
        self._set_frequency_ui_state(active=False)

        count = getattr(self, "frequency_cycle_count", 0)
        b_mode = getattr(self, "final_brightness_mode", "zero")
        self.frequency_status_label.setText(
            f"Modo de frecuencia detenido: {count} ciclos completados - Brillo final: {'0%' if b_mode == 'zero' else '100%'}"
        )


    # ═══════════════════════════════════════════════════════════════════════════
    # SECUENCIA DE SEGMENTOS LITOGRÁFICOS
    # ═══════════════════════════════════════════════════════════════════════════

    def start_sequence(self):
        if getattr(self, "exposure_active", False) or getattr(self, "frequency_mode", False):
            self._show_warning(ERR_CONFLICT_TITLE, "No se puede iniciar secuencia mientras otro modo está activo.")
            return

        if not getattr(self, "image_segments", None):
            self._show_warning(MSG_NO_SEGMENTS_TITLE, MSG_NO_SEGMENTS_BODY)
            return

        if not getattr(self, "projector_active", False):
            reply = QMessageBox.question(
                self, "Proyector inactivo", "El proyector no está activo. ¿Desea activarlo ahora?",
                QMessageBox.Yes | QMessageBox.No
            )
            if reply == QMessageBox.Yes:
                self.toggle_projector()
                if not getattr(self, "projector_active", False): return
            else:
                return

        if getattr(self, "is_projecting_full_image", False):
            self.project_full_image()

        self._initialize_sequence_state()
        self._log_sequence_start()
        
        if not hasattr(self, "sequence_timer") or self.sequence_timer is None:
            self.sequence_timer = QTimer()
            self.sequence_timer.timeout.connect(self._process_next_segment)
            
        self._process_next_segment()

    def _initialize_sequence_state(self):
        self.total_segments = len(self.image_segments)
        self.current_segment_index = 0
        self.sequence_running = True
        self.sequence_paused = False

        self.sequence_status_label.setText("Estado: En ejecución")
        self.sequence_start_button.setEnabled(False)
        self.sequence_pause_button.setEnabled(True)
        self.sequence_stop_button.setEnabled(True)
        self.segment_progress_bar.setMaximum(self.total_segments)

    def _log_sequence_start(self):
        exp_time = self.exposure_time_spin.value() if hasattr(self, "exposure_time_spin") else 0
        mov_time = self.movement_time_spin.value() if hasattr(self, "movement_time_spin") else 0
        self.log_to_console(
            f"INICIANDO SECUENCIA DE PROYECCIÓN\n"
            f"Total de chunks: {self.total_segments}\n"
            f"Orden: Secuencial estricto (fila por fila)\n"
            f"Tiempo por chunk: {exp_time}s exposición + {mov_time}s movimiento",
            "SUCCESS",
        )

    def pause_sequence(self):
        if not getattr(self, "sequence_running", False): return

        self.sequence_paused = not self.sequence_paused
        if self.sequence_paused:
            self.sequence_status_label.setText("Estado: Pausado")
            self.sequence_pause_button.setText("Reanudar")
            if self.sequence_timer: self.sequence_timer.stop()
        else:
            self.sequence_status_label.setText("Estado: En ejecución")
            self.sequence_pause_button.setText("Pausar")
            self._process_next_segment()

    def stop_sequence(self):
        self.sequence_running = False
        self.sequence_paused = False
        if getattr(self, "sequence_timer", None): self.sequence_timer.stop()
        
        self.current_projecting_segment = None
        if getattr(self, "projector_active", False) and getattr(self, "projection_window", None):
            self.projection_window.show_black_screen()
            self.log_to_console("Secuencia detenida - Pantalla en negro", "INFO")

        self._refresh_grid_preserving_zoom()
        
        self.sequence_status_label.setText("Estado: Detenido")
        self.sequence_start_button.setEnabled(True)
        self.sequence_pause_button.setEnabled(False)
        self.sequence_pause_button.setText("Pausar")
        self.sequence_stop_button.setEnabled(False)
        self.current_segment_label.setText(f"Segmento: {self.current_segment_index}/{getattr(self, 'total_segments', 0)}")
        self.segment_progress_bar.setValue(int(self.current_segment_index))

    def _process_next_segment(self):
        if not getattr(self, "sequence_running", False) or getattr(self, "sequence_paused", False): return

        if not getattr(self, "image_segments", None):
            self._show_warning(MSG_NO_SEGMENTS_TITLE, MSG_NO_SEGMENTS_BODY)
            self.stop_sequence()
            return

        if self.current_segment_index >= len(self.image_segments):
            self._complete_sequence()
            return

        self._expose_current_segment()

    def _complete_sequence(self):
        self.sequence_status_label.setText("Estado: Completado")
        if getattr(self, "projector_active", False) and getattr(self, "projection_window", None):
            self.projection_window.show_black_screen()
            self.log_to_console("Proyección finalizada - Pantalla en negro", "SUCCESS")
        
        self.stop_sequence()
        QMessageBox.information(self, "Secuencia Completada", f"Se han proyectado todos los {len(self.image_segments)} segmentos.")

    def _expose_current_segment(self):
        seg = self.image_segments[self.current_segment_index]
        self.current_segment_index += 1
        
        self.current_segment_label.setText(f"Segmento: {self.current_segment_index}/{len(self.image_segments)}")
        self.segment_progress_bar.setValue(int(self.current_segment_index))
        self._log_segment_details(seg)

        if hasattr(self, "auto_shutter_checkbox") and self.auto_shutter_checkbox.isChecked():
            exp_s = self.exposure_time_spin.value()
            self.log_to_console(f"Exponiendo segmento {self.current_segment_index} durante {exp_s}s", "INFO")
            
            if getattr(self, "projector_active", False) and getattr(self, "projection_window", None):
                processed = self._apply_effects_to_segment(seg["image"], skip_binary_effects=seg.get("effects_applied", False))
                self.projection_window.update_segment(processed)
                self._update_calibration_monitor_info(processed)

            self._highlight_current_segment(seg["row"], seg["col"])
            QTimer.singleShot(int(exp_s * 1000), lambda: self._start_movement_phase(seg["row"], seg["col"]))
        else:
            self._process_next_segment()

    def _start_movement_phase(self, row, col):
        if not getattr(self, "sequence_running", False) or getattr(self, "sequence_paused", False): return

        mov_s = self.movement_time_spin.value() if hasattr(self, "movement_time_spin") else 0
        self.current_projecting_segment = None

        if getattr(self, "projector_active", False) and getattr(self, "projection_window", None):
            self.projection_window.show_black_screen()
            self.log_to_console("Pantalla en negro - Preparando movimiento", "INFO")

        self._refresh_grid_preserving_zoom()

        if hasattr(self, "auto_movement_checkbox") and self.auto_movement_checkbox.isChecked() and mov_s > 0:
            self.log_to_console(f"Moviendo stage (tiempo estimado: {mov_s}s)", "INFO")

        if mov_s > 0:
            QTimer.singleShot(int(mov_s * 1000), self._process_next_segment)
        else:
            self._process_next_segment()

    # ═══════════════════════════════════════════════════════════════════════════
    # EFECTOS Y PROCESAMIENTO DE IMAGEN
    # ═══════════════════════════════════════════════════════════════════════════

    def _apply_effects_to_segment(self, segment, skip_binary_effects=False):
        """Aplica el pipeline completo de efectos a un segmento."""
        img = segment.copy()
        
        img = self._apply_sigma_effect(img)
        img = self._apply_downscale_effect(img)
        img = self._apply_brightness_effect(img)
        
        if not skip_binary_effects:
            img = self._apply_binary_effect(img)
            img = self._apply_invert_effect(img)
            
        img = self._apply_exposure_mirror(img)
        img = self._apply_calibration_matrix(img)
        
        return img

    def _apply_sigma_effect(self, img):
        if getattr(self, "sigma", 0) > 0:
            k = int(2 * np.ceil(3 * self.sigma) + 1)
            if k > 0 and k % 2 == 1:
                return cv2.GaussianBlur(img, (k, k), self.sigma)
        return img

    def _apply_downscale_effect(self, img):
        factor = getattr(self, "downscale_factor", 1.0)
        if factor != 1.0:
            h, w = img.shape[:2]
            nh, nw = max(1, int(h / factor)), max(1, int(w / factor))
            interp = cv2.INTER_AREA if factor > 1.0 else cv2.INTER_LINEAR
            return cv2.resize(img, (nw, nh), interpolation=interp)
        return img

    def _apply_brightness_effect(self, img):
        b = getattr(self, "brightness", 100)
        if b != 100:
            return cv2.convertScaleAbs(img, alpha=b/100.0, beta=0)
        return img

    def _apply_binary_effect(self, img):
        if getattr(self, "binary_mode_enabled", False):
            norm = img.astype(np.float64)
            if norm.max() > 0: norm = norm / norm.max()
            norm = norm * 100.0
            thresh = getattr(self, "binary_threshold", 50.0)
            return np.where(norm >= thresh, 255, 0).astype(np.uint8)
        return img

    def _apply_invert_effect(self, img):
        if getattr(self, "invert_projection", False):
            return 255 - img if img.max() > 1 else 1.0 - img
        return img

    def _apply_exposure_mirror(self, img):
        import cv2
        if getattr(self, "exposure_mirror_h", False):
            img = cv2.flip(img, 1)
        if getattr(self, "exposure_mirror_v", False):
            img = cv2.flip(img, 0)
        return img

    def _apply_calibration_matrix(self, img):
        if not (getattr(self, "apply_attenuation_to_grid", False) and getattr(self, "attenuation_matrix", None) is not None):
            return img

        norm = (img.astype(np.float64) / 255.0) if img.max() > 1.0 else img.astype(np.float64)
        calib_mat = self.get_calibration_matrix_with_flips()
        
        ch, cw = norm.shape[:2]
        mh, mw = calib_mat.shape[:2]

        if ch != mh or cw != mw:
            from scipy.ndimage import zoom
            calib_mat = zoom(calib_mat, (ch/mh, cw/mw), order=1)

        strength = getattr(self, "attenuation_strength", 100) / 100.0
        adj_mat = 1.0 + (calib_mat - 1.0) * strength
        
        calibrated = np.clip(norm * adj_mat, 0, 1.0)
        return (calibrated * 255.0).astype(np.uint8) if img.max() > 1.0 else calibrated.astype(np.float64)

    # ═══════════════════════════════════════════════════════════════════════════
    # UI HELPERS Y OVERLAYS
    # ═══════════════════════════════════════════════════════════════════════════

    def _show_warning(self, title: str, message: str):
        QMessageBox.warning(self, title, message)

    def _refresh_grid_preserving_zoom(self):
        if getattr(self, "grid_view_active", False) and getattr(self, "grid_generated", False) and getattr(self, "ax", None):
            xlim, ylim = self.ax.get_xlim(), self.ax.get_ylim()
            self.display_grid()
            self.ax.set_xlim(xlim)
            self.ax.set_ylim(ylim)
            self.canvas.draw_idle()

    def _log_segment_details(self, seg: dict):
        self.log_to_console(
            f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
            f"CHUNK {self.current_segment_index}/{self.total_segments}\n"
            f"ID: S{seg['id']}\n"
            f"Posición grid: Fila {seg['row']}, Columna {seg['col']}\n"
            f"Tamaño: {seg['width']}×{seg['height']} px\n"
            f"Orden: Secuencial estricto",
            "SEGMENTATION",
        )

    def _update_calibration_monitor_info(self, processed):
        if hasattr(self, "last_projection_size_label"):
            self.last_projection_size_label.setText(f"  Tamaño: {processed.shape[1]}×{processed.shape[0]} px")
        if hasattr(self, "last_projection_values_label"):
            self.last_projection_values_label.setText(f"  Valores: min={processed.min():.2f}, max={processed.max():.2f}, μ={processed.mean():.2f}")
        if hasattr(self, "update_calibration_monitor"):
            self.update_calibration_monitor()

    def _highlight_current_segment(self, row, col):
        seg_data = next((s for s in getattr(self, "image_segments", []) if s["row"] == row and s["col"] == col), None)
        self.current_projecting_segment = {"row": row, "col": col, "segment_data": seg_data}
        self._refresh_grid_preserving_zoom()

    def draw_segments_overlay(self):
        if not getattr(self, "show_segments_overlay", False) or not getattr(self, "image_segments", None) or getattr(self, "ax", None) is None: return

        px_sz = getattr(self, "grid_cell_size", 1) / getattr(self, "grid_pixels_per_cell", 1)
        ox, oy = getattr(self, "image_position", [0, 0])
        
        from matplotlib.patches import Rectangle
        for s in self.image_segments:
            xg, yg = (ox + s["x_start"]) * px_sz, (oy + s["y_start"]) * px_sz
            wg, hg = s["width"] * px_sz, s["height"] * px_sz
            self.ax.add_patch(Rectangle((xg, yg), wg, hg, linewidth=2, edgecolor="cyan", facecolor="none", linestyle="--", alpha=0.8))
            self.ax.text(xg + wg/2, yg + hg/2, f"S{s['id']}", ha="center", va="center", fontsize=10, color="cyan", weight="bold", bbox=dict(boxstyle="round,pad=0.5", facecolor="black", alpha=0.7, edgecolor="cyan"))

    def draw_projecting_segment_highlight(self):
        cps = getattr(self, "current_projecting_segment", None)
        seg = cps.get("segment_data") if cps else None
        if not seg or getattr(self, "ax", None) is None: return

        px_sz = getattr(self, "grid_cell_size", 1) / getattr(self, "grid_pixels_per_cell", 1)
        ox, oy = getattr(self, "image_position", [0, 0])
        xg, yg = (ox + seg["x_start"]) * px_sz, (oy + seg["y_start"]) * px_sz
        wg, hg = seg["width"] * px_sz, seg["height"] * px_sz
        
        from matplotlib.patches import Rectangle
        self.ax.add_patch(Rectangle((xg, yg), wg, hg, linewidth=0, facecolor="red", alpha=0.4, zorder=98))

    def project_white_calibration_pattern(self):
        self.is_projecting_white_pattern = getattr(self, "is_projecting_white_pattern", False)

        if not getattr(self, "projector_active", False):
            self._show_warning("Proyector Inactivo", "Debe encender el proyector antes de calibrar.")
            return

        if getattr(self, "projection_window", None):
            if not self.is_projecting_white_pattern:
                self._prev_brightness_for_calib = getattr(self, "brightness", 100.0)
                self.projection_window.set_brightness(100.0)
                h, w = self.projection_window.screen_geometry.height(), self.projection_window.screen_geometry.width()
                self.projection_window.update_segment(np.ones((h, w, 3), dtype=np.uint8) * 255)
                self.is_projecting_white_pattern = True
                if hasattr(self, "btn_calib_white"):
                    self.btn_calib_white.setText("Detener Proyección Blanca")
                    self.btn_calib_white.setStyleSheet(STYLE_BTN_ACTIVE_RED)
            else:
                self.projection_window.set_brightness(getattr(self, "_prev_brightness_for_calib", 100.0))
                self.is_projecting_white_pattern = False
                if hasattr(self, "btn_calib_white"):
                    self.btn_calib_white.setText("Proyectar Patrón Blanco (Medir)")
                    self.btn_calib_white.setStyleSheet("")
                
                if hasattr(self, "update_projection"): self.update_projection()
                else: self.projection_window.show_black_screen()

    def save_physical_dimensions(self):
        if hasattr(self, "phys_width_spin") and hasattr(self, "phys_height_spin"):
            self.physical_segment_width = self.phys_width_spin.value()
            self.physical_segment_height = self.phys_height_spin.value()
            self.log_to_console(f"Dimensiones físicas actualizadas: {self.physical_segment_width} mm x {self.physical_segment_height} mm", "INFO")
