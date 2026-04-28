"""
Mixin de control de proyeccion.

Gestiona proyeccion en monitor secundario, exposicion temporizada,
modo frecuencia, secuencias de segmentos y aplicacion de efectos.
"""
import sys
import time
import cv2
import numpy as np
import ctypes

from PyQt5.QtWidgets import QApplication, QMessageBox
from PyQt5.QtCore import QTimer
from matplotlib.patches import Rectangle
from projection_window import ProjectionWindow


class ProjectionMixin:
    """Mixin: Projection functionality."""

    def toggle_projector(self):
        self.has_second_monitor = self.check_second_monitor()
        if not self.has_second_monitor and not self.projector_active:
            QMessageBox.warning(
                self,
                "Monitor no detectado",
                "No se detectó un segundo monitor conectado.\n\n"
                "Por favor, conecte un segundo monitor para usar la función de proyección.",
            )
            self.update_projector_button()
            return  # no proyectar si no hay segundo monitor

        # si el monitor se desconectó mientras estaba proyectando, cerrar proyección
        if not self.has_second_monitor and self.projector_active:
            if self.projection_window is not None:
                self.projection_window.close()
                self.projection_window = None
            self.brightness_slider.setVisible(False)
            self.brightness_label.setVisible(False)
            self.projector_active = False
            self.update_projector_button()
            QMessageBox.warning(
                self,
                "Monitor desconectado",
                "Se perdió la conexión con el segundo monitor.\n\n"
                "La proyección se ha detenido.",
            )
            return

        self.projector_active = not self.projector_active

        if self.projector_active:
            # Verificar que hay imagen disponible (aunque no la proyectaremos completa)
            image_to_project = self._get_projection_image()
            if image_to_project is not None:
                # ═══════════════════════════════════════════════════════════════════
                # PROYECTOR SIEMPRE INICIA EN NEGRO
                # ═══════════════════════════════════════════════════════════════════
                # La imagen solo se proyecta cuando:
                # - Se presiona "Proyectar Imagen" explícitamente
                # - Se inicia Exposición
                # - Se inicia Frecuencia
                # - Se inicia Secuencia de Slices

                self.projection_window = ProjectionWindow(
                    None, self
                )  # None = pantalla negra
                self.projection_window.set_inversion(self.invert_projection)
                self.projection_window.set_binary_threshold(self.binary_threshold)
                self.projection_window.set_binary_mode(self.binary_mode_enabled)
                self.projection_window.show_on_secondary_monitor()

                # SIEMPRE iniciar con pantalla negra
                self.projection_window.show_black_screen()
                self.log_to_console(
                    "✓ Proyector activado - Pantalla en NEGRO\n"
                    "  La imagen se proyectará al iniciar Exposición, Frecuencia o Secuencia",
                    "INFO",
                )

                self.brightness_slider.setVisible(True)
                self.brightness_label.setVisible(True)
                # self.binary_section.setVisible(True) - Always visible in sidebar
                self.project_image_button.setVisible(
                    True
                )  # Botón para proyectar imagen manualmente
                self.exposure_button.setVisible(True)
                self.frequency_button.setVisible(True)
                # NO llamar update_brightness() para no proyectar la imagen completa
                # self.update_brightness()

                # Mostrar campos de resolución proyectada ahora que hay proyección activa
                self._update_projection_resolution_fields(True)
            else:
                QMessageBox.warning(
                    self,
                    "Advertencia",
                    "No hay imagen para proyectar.\nCargue una imagen en Vista Normal o Vista Grid.",
                )
                self.projector_active = False
        else:
            if self.exposure_active:
                self.force_stop_exposure()

            if self.frequency_mode:
                self.force_stop_frequency()

            # Detener secuencia de slices si está activa
            if hasattr(self, "sequence_running") and self.sequence_running:
                self.stop_sequence()
                self.log_to_console(
                    "⏹️ Secuencia detenida - Proyector desactivado", "INFO"
                )

            if self.projection_window is not None:
                self.projection_window.close()
                self.projection_window = None
            self.brightness_slider.setVisible(False)
            self.brightness_label.setVisible(False)
            # self.binary_section.setVisible(False) - Always visible in sidebar
            self.project_image_button.setVisible(False)
            self.exposure_button.setVisible(False)
            self.stop_exposure_button.setVisible(False)
            self.frequency_button.setVisible(False)
            self.stop_frequency_button.setVisible(False)

            # Ocultar campos de resolución proyectada al desactivar proyección
            self._update_projection_resolution_fields(False)

        self.update_projector_button()


    def on_projection_closed(self):
        """Se llama cuando se cierra la ventana de proyección."""
        if self.exposure_active:
            self.force_stop_exposure()

        if self.frequency_mode:
            self.force_stop_frequency()

        self.projector_active = False
        self.projection_window = None
        self.brightness_slider.setVisible(False)
        self.brightness_label.setVisible(False)
        # self.binary_section.setVisible(False) - Always visible in sidebar
        self.exposure_button.setVisible(False)
        self.stop_exposure_button.setVisible(False)
        self.frequency_button.setVisible(False)
        self.stop_frequency_button.setVisible(False)

        # Ocultar campos de resolución de proyección al cerrar
        self._update_projection_resolution_fields(False)

        self.update_projector_button()


    def update_projector_button(self):
        # actualizar detección de segundo monitor
        self.has_second_monitor = self.check_second_monitor()

        if not self.has_second_monitor:
            led = "🟠"
            status = "DESCONECTADO"
            self.projector_button.setStyleSheet("""
                QPushButton {
                    background-color: #FF8C00;
                    color: #FFFFFF;
                    font-weight: bold;
                }
                QPushButton:hover {
                    background-color: #FFA500;
                }
            """)
        elif self.projector_active:
            led = "🟢"
            status = "ACTIVO"
            self.projector_button.setStyleSheet("")
        else:
            led = "🔴"
            status = "INACTIVO"
            self.projector_button.setStyleSheet("")
        self.projector_button.setText(f"{led} Proyectar ({status})")


    def project_full_image(self):
        """
        Proyecta la imagen completa manualmente en el monitor secundario.
        La imagen permanecerá hasta que se apague el proyector o se inicie otra operación.
        """
        if not self.projector_active:
            QMessageBox.warning(
                self,
                "Proyector inactivo",
                "Debe activar el proyector antes de proyectar la imagen.\n\n"
                "Use el botón '🎬 Proyectar' primero.",
            )
            return

        if self.projection_window is None:
            QMessageBox.warning(
                self, "Error", "No hay ventana de proyección disponible."
            )
            return

        # Obtener imagen a proyectar
        image_to_project = self._get_projection_image()

        if image_to_project is None:
            QMessageBox.warning(
                self,
                "Sin imagen",
                "No hay imagen disponible para proyectar.\n\n"
                "Cargue una imagen primero.",
            )
            return

        # Proyectar imagen completa
        self.projection_window.set_image(image_to_project)

        self.log_to_console(
            "🖼️ Proyectando imagen completa en monitor secundario", "SUCCESS"
        )


    def start_timed_exposure(self):
        # Verificar conflictos con otros modos
        if self.sequence_running:
            QMessageBox.warning(
                self,
                "Conflicto",
                "No se puede iniciar exposición mientras la secuencia de segmentos está activa.",
            )
            return
        if self.frequency_mode:
            QMessageBox.warning(
                self,
                "Conflicto",
                "No se puede iniciar exposición mientras el modo frecuencia está activo.",
            )
            return

        if not self.projector_active:
            QMessageBox.warning(
                self,
                "Proyección inactiva",
                "Debe activar la proyección antes de iniciar la exposición.",
            )
            return

        # Asegurar que se proyecta la imagen completa
        if self.projection_window is not None and self.pattern is not None:
            self.projection_window.set_image(self.pattern)
            # Aplicar configuración binaria global si está activa
            if self.binary_mode_enabled:
                self.projection_window.set_binary_mode(True)
                self.projection_window.set_binary_threshold(self.binary_threshold)
                self.projection_window.set_inversion(self.invert_projection)

        try:
            # Precisión float para tiempos de exposición (microsegundos)
            exposure_time = float(self.exposure_time_input.text())
            if exposure_time <= 0:
                raise ValueError("El tiempo debe ser mayor a 0")
        except ValueError:
            QMessageBox.warning(
                self,
                "Tiempo inválido",
                "Por favor ingrese un tiempo de exposición válido (en segundos).\n\n"
                "Ejemplo: 5, 10.5, 0.001 (1ms), 0.000001 (1μs)",
            )
            return

        try:
            # Intensidad normalizada como float 0-100
            intensity = float(self.exposure_intensity_input.text())
            if intensity < 0 or intensity > 100:
                raise ValueError("La intensidad debe estar entre 0 y 100")
        except ValueError:
            QMessageBox.warning(
                self,
                "Intensidad inválida",
                "Por favor ingrese una intensidad válida (0-100).\n\n"
                "Ejemplo: 50, 80, 100, 75.5",
            )
            return

        try:
            cycles = int(self.exposure_cycles_input.text())
            if cycles <= 0:
                raise ValueError("Los ciclos deben ser mayor a 0")
        except ValueError:
            QMessageBox.warning(
                self,
                "Ciclos inválidos",
                "Por favor ingrese un número de ciclos válido (número entero positivo).\n\n"
                "Ejemplo: 1, 3 o 5",
            )
            return

        # Almacenar con precisión float para litografía
        self.exposure_duration = float(exposure_time)
        self.exposure_cycles_total = cycles
        self.exposure_cycles_completed = 0
        self.exposure_start_time = float(time.time())  # Timestamp con precisión μs
        self.exposure_target_brightness = float(intensity)

        # QSlider requiere int, pero mantenemos precisión internamente
        self.brightness_slider.setValue(int(round(intensity)))
        self.update_brightness()

        self.exposure_active = True
        self.exposure_button.setVisible(False)
        self.stop_exposure_button.setVisible(True)

        self.exposure_time_input.setEnabled(False)
        self.exposure_intensity_input.setEnabled(False)
        self.exposure_cycles_input.setEnabled(False)
        self.brightness_slider.setEnabled(False)

        # Timer requiere int (milisegundos)
        self.exposure_timer.start(int(round(exposure_time * 1000)))
        self.countdown_timer.start()

        self.update_countdown()


    def update_countdown(self):
        """
        Actualiza el contador de tiempo de exposición.
        Precisión de décimas de segundo para visualización (internamente μs).
        """
        if not self.exposure_active:
            return

        # Cálculo con precisión float (microsegundos)
        elapsed = float(time.time()) - self.exposure_start_time
        remaining = max(0.0, self.exposure_duration - elapsed)

        # Mostrar con 3 decimales para tiempos cortos (ms/μs)
        if remaining < 1.0:
            self.exposure_status_label.setText(
                f"⏱️ Ciclo {self.exposure_cycles_completed + 1}/{self.exposure_cycles_total} | "
                f"Tiempo restante: {remaining*1000:.3f}ms"
            )
        else:
            self.exposure_status_label.setText(
                f"⏱️ Ciclo {self.exposure_cycles_completed + 1}/{self.exposure_cycles_total} | "
                f"Tiempo restante: {remaining:.3f}s"
            )


    def stop_timed_exposure(self):
        self.countdown_timer.stop()

        self.exposure_cycles_completed += 1

        if self.exposure_cycles_completed < self.exposure_cycles_total:
            self.brightness_slider.setValue(0)
            self.update_brightness()

            self.exposure_status_label.setText(
                f"⏸️ Ciclo {self.exposure_cycles_completed}/{self.exposure_cycles_total} completado | "
                f"Preparando siguiente ciclo..."
            )

            if self.inter_cycle_delay > 0:
                self.inter_cycle_timer.start(self.inter_cycle_delay)
            else:
                self.resume_next_cycle()
        else:
            if self.final_brightness_mode == "zero":
                self.brightness_slider.setValue(0)
            else:
                self.brightness_slider.setValue(100)
            self.update_brightness()

            self.finish_exposure_sequence()


    def finish_exposure_sequence(self):
        self.exposure_timer.stop()
        self.countdown_timer.stop()
        self.inter_cycle_timer.stop()

        self.exposure_active = False
        self.exposure_button.setVisible(True)
        self.stop_exposure_button.setVisible(False)

        self.exposure_time_input.setEnabled(True)
        self.exposure_intensity_input.setEnabled(True)
        self.exposure_cycles_input.setEnabled(True)
        self.brightness_slider.setEnabled(True)

        brightness_text = "0%" if self.final_brightness_mode == "zero" else "100%"
        self.exposure_status_label.setText(
            f"✅ Exposición completada: {self.exposure_cycles_completed} ciclo(s) | "
            f"Brillo final: {brightness_text}"
        )


    def force_stop_exposure(self):
        self.exposure_timer.stop()
        self.countdown_timer.stop()
        self.inter_cycle_timer.stop()

        if self.final_brightness_mode == "zero":
            self.brightness_slider.setValue(0)
        else:
            self.brightness_slider.setValue(100)
        self.update_brightness()

        self.exposure_active = False
        self.exposure_button.setVisible(True)
        self.stop_exposure_button.setVisible(False)

        self.exposure_time_input.setEnabled(True)
        self.exposure_intensity_input.setEnabled(True)
        self.exposure_cycles_input.setEnabled(True)
        self.brightness_slider.setEnabled(True)

        self.exposure_status_label.setText(
            f"⏹️ Exposición detenida: {self.exposure_cycles_completed}/{self.exposure_cycles_total} ciclo(s) completados"
        )


    def start_frequency_mode(self):
        # Verificar conflictos con otros modos
        if self.sequence_running:
            QMessageBox.warning(
                self,
                "Conflicto",
                "No se puede iniciar frecuencia mientras la secuencia de segmentos está activa.",
            )
            return
        if self.exposure_active:
            QMessageBox.warning(
                self,
                "Conflicto",
                "No se puede iniciar frecuencia mientras la exposición está activa.",
            )
            return

        if not self.projector_active:
            QMessageBox.warning(
                self,
                "Proyección inactiva",
                "Debe activar la proyección antes de iniciar el modo de frecuencia.",
            )
            return

        # Asegurar que se proyecta la imagen completa
        if self.projection_window is not None and self.pattern is not None:
            self.projection_window.set_image(self.pattern)
            # Aplicar configuración binaria global si está activa
            if self.binary_mode_enabled:
                self.projection_window.set_binary_mode(True)
                self.projection_window.set_binary_threshold(self.binary_threshold)
                self.projection_window.set_inversion(self.invert_projection)

        try:
            freq_value = float(self.frequency_value_input.text())
            if freq_value <= 0:
                raise ValueError("La frecuencia debe ser mayor a 0")
        except ValueError:
            QMessageBox.warning(
                self,
                "Frecuencia inválida",
                "Por favor ingrese una frecuencia válida (mayor a 0).\n\n"
                "Ejemplo: 1, 2.5 o 10",
            )
            return

        unit = self.frequency_unit_combo.currentText()
        if unit == "kHz":
            freq_hz = freq_value * 1000
        elif unit == "MHz":
            freq_hz = freq_value * 1000000
        else:  # Hz
            freq_hz = freq_value

        period = 1.0 / freq_hz

        try:
            duration = float(self.frequency_duration_input.text())
            if duration < 0:
                raise ValueError("La duración debe ser 0 o mayor")
        except ValueError:
            QMessageBox.warning(
                self,
                "Duración inválida",
                "Por favor ingrese una duración válida (0 para infinito).\n\n"
                "Ejemplo: 0, 30 o 60",
            )
            return

        try:
            intensity = int(self.exposure_intensity_input.text())
            if intensity < 0 or intensity > 100:
                raise ValueError("La intensidad debe estar entre 0 y 100")
        except ValueError:
            QMessageBox.warning(
                self,
                "Intensidad inválida",
                "Por favor configure una intensidad válida en la sección de exposición (0-100).",
            )
            return

        self.frequency_mode = True
        self.frequency_period = period
        self.exposure_target_brightness = intensity
        self.frequency_duration = duration
        self.frequency_start_time = time.time()

        self.frequency_button.setVisible(False)
        self.stop_frequency_button.setVisible(True)
        self.frequency_value_input.setEnabled(False)
        self.frequency_unit_combo.setEnabled(False)
        self.frequency_duration_input.setEnabled(False)
        self.exposure_intensity_input.setEnabled(False)
        self.brightness_slider.setEnabled(False)

        if duration > 0:
            self.frequency_timer.start(int(duration * 1000))

        self.frequency_cycle_count = 0
        self.start_frequency_cycle()


    def start_frequency_cycle(self):

        if not self.frequency_mode:
            return

        # QSlider requiere int, redondear desde float interno
        self.brightness_slider.setValue(int(round(self.exposure_target_brightness)))
        self.update_brightness()

        on_time = self.frequency_period / 2.0

        self.frequency_cycle_count += 1

        if self.frequency_duration > 0:
            elapsed = time.time() - self.frequency_start_time
            remaining = max(0, self.frequency_duration - elapsed)
            self.frequency_status_label.setText(
                f"🌊 Ciclo #{self.frequency_cycle_count} | "
                f"Frecuencia activa | Tiempo restante: {remaining:.1f}s"
            )
        else:
            self.frequency_status_label.setText(
                f"🌊 Ciclo #{self.frequency_cycle_count} | "
                f"Frecuencia activa (infinito)"
            )

        QTimer.singleShot(int(on_time * 1000), self.frequency_off_phase)


    def frequency_off_phase(self):

        if not self.frequency_mode:
            return

        self.brightness_slider.setValue(0)
        self.update_brightness()

        off_time = self.frequency_period / 2.0

        QTimer.singleShot(int(off_time * 1000), self.start_frequency_cycle)


    def stop_frequency_mode(self):

        self.force_stop_frequency()

        if self.final_brightness_mode == "full":
            final_brightness = 100
            brightness_text = "Brillo final: 100%"
        else:
            final_brightness = 0
            brightness_text = "Brillo final: 0%"

        self.frequency_status_label.setText(
            f"✅ Modo de frecuencia completado: {self.frequency_cycle_count} ciclos - {brightness_text}"
        )


    def force_stop_frequency(self):
        self.frequency_mode = False
        self.frequency_timer.stop()

        if self.final_brightness_mode == "full":
            final_brightness = 100
            brightness_text = "Brillo final: 100%"
        else:
            final_brightness = 0
            brightness_text = "Brillo final: 0%"

        self.brightness_slider.setValue(final_brightness)
        self.update_brightness()

        self.frequency_button.setVisible(True)
        self.stop_frequency_button.setVisible(False)
        self.frequency_value_input.setEnabled(True)
        self.frequency_unit_combo.setEnabled(True)
        self.frequency_duration_input.setEnabled(True)
        self.exposure_intensity_input.setEnabled(True)
        self.brightness_slider.setEnabled(True)

        if not hasattr(self, "frequency_cycle_count"):
            self.frequency_cycle_count = 0

        self.frequency_status_label.setText(
            f"⏹️ Modo de frecuencia detenido: {self.frequency_cycle_count} ciclos completados - {brightness_text}"
        )


    def start_sequence(self):
        """Inicia la secuencia de proyección con control de movimiento y segmentos de imagen."""
        # Verificar conflictos con otros modos
        if self.exposure_active:
            QMessageBox.warning(
                self,
                "Conflicto",
                "No se puede iniciar secuencia mientras la exposición está activa.",
            )
            return
        if self.frequency_mode:
            QMessageBox.warning(
                self,
                "Conflicto",
                "No se puede iniciar secuencia mientras el modo frecuencia está activo.",
            )
            return

        # Verificar que haya segmentos de imagen
        if not hasattr(self, "image_segments") or not self.image_segments:
            QMessageBox.warning(
                self,
                "Sin segmentos de imagen",
                "Debe aplicar segmentación de imagen antes de iniciar una secuencia.\n\n"
                "Pasos:\n"
                "1. Cargue una imagen\n"
                "2. Vaya a '✂️ SEGMENTACIÓN DE IMAGEN'\n"
                "3. Configure el modo y número de segmentos\n"
                "4. Presione 'Aplicar Segmentación'",
            )
            return

        # Verificar que el proyector esté activo
        if not self.projector_active:
            reply = QMessageBox.question(
                self,
                "Proyector inactivo",
                "El proyector no está activo. ¿Desea activarlo ahora?",
                QMessageBox.Yes | QMessageBox.No,
            )
            if reply == QMessageBox.Yes:
                self.toggle_projector()
                if not self.projector_active:
                    return  # No se pudo activar
            else:
                return

        # Calcular total de segmentos de imagen
        self.total_segments = len(self.image_segments)
        self.current_segment_index = 0
        self.sequence_running = True
        self.sequence_paused = False

        # Actualizar UI
        self.sequence_status_label.setText("Estado: ▶️ En ejecución")
        self.sequence_start_button.setEnabled(False)
        self.sequence_pause_button.setEnabled(True)
        self.sequence_stop_button.setEnabled(True)
        self.segment_progress_bar.setMaximum(self.total_segments)

        # ═══════════════════════════════════════════════════════════════════
        # LOG INICIO: MOSTRAR ORDEN SECUENCIAL DE CHUNKS
        # ═══════════════════════════════════════════════════════════════════
        self.log_to_console(
            f"▶️ INICIANDO SECUENCIA DE PROYECCIÓN\n"
            f"  • Total de chunks: {self.total_segments}\n"
            f"  • Orden: Secuencial estricto (fila por fila)\n"
            f"  • Tiempo por chunk: {self.exposure_time_spin.value()}s exposición + {self.movement_time_spin.value()}s movimiento",
            "SUCCESS",
        )

        # Mostrar los primeros 5 chunks para verificación
        if self.total_segments > 0:
            preview_count = min(5, self.total_segments)
            preview_chunks = []
            for i in range(preview_count):
                seg = self.image_segments[i]
                preview_chunks.append(f"[{seg['row']},{seg['col']}]")
            preview_str = " → ".join(preview_chunks)
            if self.total_segments > 5:
                preview_str += " → ..."
            self.log_to_console(f"  • Orden chunks: {preview_str}", "INFO")

        # Iniciar timer para procesar segmentos
        if not hasattr(self, "sequence_timer") or self.sequence_timer is None:
            self.sequence_timer = QTimer()
            self.sequence_timer.timeout.connect(self._process_next_segment)

        # Iniciar primer segmento
        self._process_next_segment()


    def pause_sequence(self):
        """Pausa/reanuda la secuencia de proyección."""
        if not self.sequence_running:
            return

        self.sequence_paused = not self.sequence_paused

        if self.sequence_paused:
            self.sequence_status_label.setText("Estado: ⏸️ Pausado")
            self.sequence_pause_button.setText("▶️ Reanudar")
            if self.sequence_timer:
                self.sequence_timer.stop()
        else:
            self.sequence_status_label.setText("Estado: ▶️ En ejecución")
            self.sequence_pause_button.setText("⏸️ Pausar")
            # Continuar con siguiente segmento
            self._process_next_segment()


    def stop_sequence(self):
        """Detiene la secuencia de proyección."""
        self.sequence_running = False
        self.sequence_paused = False

        if self.sequence_timer:
            self.sequence_timer.stop()

        # Limpiar resaltado del chunk en proyección
        self.current_projecting_segment = None

        # Volver a pantalla negra al detener
        if self.projector_active and self.projection_window is not None:
            self.projection_window.show_black_screen()
            self.log_to_console("Secuencia detenida - Pantalla en negro", "INFO")

        # Actualizar grid para quitar resaltado PRESERVANDO el zoom
        if (
            self.grid_view_active
            and hasattr(self, "grid_generated")
            and self.grid_generated
        ):
            if hasattr(self, "ax") and self.ax is not None:
                # Guardar límites actuales del zoom
                current_xlim = self.ax.get_xlim()
                current_ylim = self.ax.get_ylim()

                # Redibujar el grid completo
                self.display_grid()

                # Restaurar los límites del zoom
                self.ax.set_xlim(current_xlim)
                self.ax.set_ylim(current_ylim)
                self.canvas.draw_idle()
            else:
                self.display_grid()

        # Resetear UI
        self.sequence_status_label.setText("Estado: ⏹️ Detenido")
        self.sequence_start_button.setEnabled(True)
        self.sequence_pause_button.setEnabled(False)
        self.sequence_pause_button.setText("⏸️ Pausar")
        self.sequence_stop_button.setEnabled(False)
        self.current_segment_label.setText(
            f"Segmento: {self.current_segment_index}/{self.total_segments}"
        )
        self.segment_progress_bar.setValue(int(self.current_segment_index))


    def _process_next_segment(self):
        """Procesa el siguiente segmento de la secuencia."""
        if not self.sequence_running or self.sequence_paused:
            return

        # Verificar si hay segmentos de imagen disponibles
        if not hasattr(self, "image_segments") or not self.image_segments:
            QMessageBox.warning(
                self,
                "Sin segmentos",
                "Debe aplicar segmentación de imagen antes de iniciar la secuencia.\n\n"
                "Vaya a la sección '✂️ SEGMENTACIÓN DE IMAGEN' y aplique segmentación.",
            )
            self.stop_sequence()
            return

        if self.current_segment_index >= len(self.image_segments):
            # Secuencia completada
            self.sequence_status_label.setText("Estado: ✅ Completado")

            # Volver a pantalla negra
            if self.projector_active and self.projection_window is not None:
                self.projection_window.show_black_screen()
                self.log_to_console(
                    "Proyección finalizada - Pantalla en negro", "SUCCESS"
                )

            self.stop_sequence()
            QMessageBox.information(
                self,
                "Secuencia Completada",
                f"Se han proyectado todos los {len(self.image_segments)} segmentos de imagen.",
            )
            return

        # Obtener segmento actual
        current_segment = self.image_segments[self.current_segment_index]
        row = current_segment["row"]
        col = current_segment["col"]
        segment_image = current_segment["image"]
        effects_already_applied = current_segment.get("effects_applied", False)

        # Actualizar UI
        self.current_segment_index += 1
        self.current_segment_label.setText(
            f"Segmento: {self.current_segment_index}/{len(self.image_segments)}"
        )
        self.segment_progress_bar.setValue(int(self.current_segment_index))

        # Log del segmento con información detallada
        self.log_to_console(
            f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
            f"📦 CHUNK {self.current_segment_index}/{len(self.image_segments)}\n"
            f"  • ID: S{current_segment['id']}\n"
            f"  • Posición grid: Fila {row}, Columna {col}\n"
            f"  • Tamaño: {current_segment['width']}×{current_segment['height']} px\n"
            f"  • Orden: Secuencial estricto",
            "SEGMENTATION",
        )

        # ═══════════════════════════════════════════════════════════════════════════
        # SECUENCIA TEMPORAL PARA LITOGRAFÍA:
        # 1. Mostrar segmento (EXPOSICIÓN) → Tiempo de exposición
        # 2. Pantalla negra + Movimiento → Tiempo de movimiento
        # 3. Siguiente segmento
        # ═══════════════════════════════════════════════════════════════════════════

        # FASE 1: EXPOSICIÓN - Mostrar segmento durante tiempo de exposición
        if self.auto_shutter_checkbox.isChecked():
            exposure_time_s = self.exposure_time_spin.value()
            self.log_to_console(
                f"Exponiendo segmento {self.current_segment_index}/{len(self.image_segments)} durante {exposure_time_s}s",
                "INFO",
            )

            # PROYECTAR SEGMENTO
            if self.projector_active and self.projection_window is not None:
                # Aplicar TODOS los efectos al segmento antes de proyectar
                processed_segment = self._apply_effects_to_segment(
                    segment_image, skip_binary_effects=effects_already_applied
                )

                # DEBUG: Log detallado de coordenadas del chunk
                self.log_to_console(
                    f"🔍 DEBUG Chunk {current_segment['id']} [fila={row}, col={col}]:\n"
                    f"  • Coordenadas en imagen: ({current_segment['x_start']}, {current_segment['y_start']}) → "
                    f"({current_segment['x_end']}, {current_segment['y_end']})\n"
                    f"  • Tamaño chunk: {current_segment['width']}×{current_segment['height']} px\n"
                    f"  • Tamaño procesado: {processed_segment.shape[1]}×{processed_segment.shape[0]} px\n"
                    f"  • Valores: min={processed_segment.min():.2f}, max={processed_segment.max():.2f}, mean={processed_segment.mean():.2f}",
                    "INFO",
                )

                # Proyectar el segmento procesado en la pantalla secundaria
                # Durante una secuencia, SIEMPRE se proyecta (no depende de show_projection_image)
                self.projection_window.update_segment(processed_segment)
                self.log_to_console(
                    f"✓ Segmento {current_segment['id']} PROYECTADO: {processed_segment.shape[1]}x{processed_segment.shape[0]} px",
                    "SUCCESS",
                )

                # Actualizar monitor de calibración con info de última proyección
                if hasattr(self, "last_projection_size_label"):
                    self.last_projection_size_label.setText(
                        f"• Tamaño: {processed_segment.shape[1]}×{processed_segment.shape[0]} px"
                    )
                if hasattr(self, "last_projection_values_label"):
                    self.last_projection_values_label.setText(
                        f"• Valores: min={processed_segment.min():.2f}, max={processed_segment.max():.2f}, μ={processed_segment.mean():.2f}"
                    )

                # Actualizar todo el monitor
                self.update_calibration_monitor()

            # Resaltar segmento actual en el grid principal
            self._highlight_current_segment(row, col)

            # Después del tiempo de exposición, pasar a fase de movimiento
            exposure_time_ms = int(exposure_time_s * 1000)
            QTimer.singleShot(
                exposure_time_ms, lambda: self._start_movement_phase(row, col)
            )
        else:
            # Si no hay proyección automática, ir directo al siguiente
            self._process_next_segment()


    def _start_movement_phase(self, row, col):
        """
        Fase de movimiento: Apaga proyección (negro) y simula movimiento del stage.
        """
        if not self.sequence_running or self.sequence_paused:
            return

        movement_time_s = self.movement_time_spin.value()

        # Limpiar resaltado durante fase de movimiento (ya no se proyecta)
        self.current_projecting_segment = None

        # FASE 2: MOVIMIENTO - Pantalla negra durante movimiento
        if self.projector_active and self.projection_window is not None:
            self.projection_window.show_black_screen()
            self.log_to_console("🖤 Pantalla en negro - Preparando movimiento", "INFO")

        # Actualizar grid para quitar resaltado durante movimiento PRESERVANDO el zoom
        if (
            self.grid_view_active
            and hasattr(self, "grid_generated")
            and self.grid_generated
        ):
            if hasattr(self, "ax") and self.ax is not None:
                # Guardar límites actuales del zoom
                current_xlim = self.ax.get_xlim()
                current_ylim = self.ax.get_ylim()

                # Redibujar el grid completo
                self.display_grid()

                # Restaurar los límites del zoom
                self.ax.set_xlim(current_xlim)
                self.ax.set_ylim(current_ylim)
                self.canvas.draw_idle()
            else:
                self.display_grid()

        # Simular movimiento de stage si está activo
        if self.auto_movement_checkbox.isChecked() and movement_time_s > 0:
            self.log_to_console(
                f"🚀 Moviendo stage (tiempo estimado: {movement_time_s}s)", "INFO"
            )

        # Después del tiempo de movimiento, procesar siguiente segmento
        if movement_time_s > 0:
            movement_time_ms = int(movement_time_s * 1000)
            QTimer.singleShot(movement_time_ms, self._process_next_segment)
        else:
            # Sin tiempo de movimiento, procesar inmediatamente
            self._process_next_segment()


    def _highlight_current_segment(self, row, col):
        """
        Resalta visualmente el segmento actual en el grid.
        Guarda información del segmento en proyección y actualiza la visualización.
        Registra información detallada en consola.
        """
        # Buscar el segmento actual en la lista
        current_segment_data = None
        for seg in self.image_segments:
            if seg["row"] == row and seg["col"] == col:
                current_segment_data = seg
                break

        # Registrar información completa en CONSOLA
        if current_segment_data:
            # Calcular posición en unidades del grid
            pixel_size = (
                self.grid_cell_size / self.grid_pixels_per_cell
                if hasattr(self, "grid_cell_size")
                else 1.0
            )
            x_grid = (
                (self.image_position[0] + current_segment_data["x_start"]) * pixel_size
                if hasattr(self, "image_position")
                else 0
            )
            y_grid = (
                (self.image_position[1] + current_segment_data["y_start"]) * pixel_size
                if hasattr(self, "image_position")
                else 0
            )

            self.log_to_console(
                f"▶ PROYECTANDO CHUNK\n"
                f"  • ID: S{current_segment_data['id']}\n"
                f"  • Posición en grid: [{row}, {col}]\n"
                f"  • Coordenadas imagen (px): [{current_segment_data['x_start']}, {current_segment_data['y_start']}]\n"
                f"  • Tamaño (px): {current_segment_data['width']}×{current_segment_data['height']}\n"
                f"  • Posición en grid ({self.grid_unit if hasattr(self, 'grid_unit') else 'units'}): ({x_grid:.2f}, {y_grid:.2f})",
                "PROJECTION",
            )

        # Guardar información del segmento en proyección
        self.current_projecting_segment = {
            "row": row,
            "col": col,
            "segment_data": current_segment_data,
        }

        # Actualizar visualización del grid con resaltado PRESERVANDO el zoom
        if (
            self.grid_view_active
            and hasattr(self, "grid_generated")
            and self.grid_generated
        ):
            if hasattr(self, "ax") and self.ax is not None:
                # Guardar límites actuales del zoom
                current_xlim = self.ax.get_xlim()
                current_ylim = self.ax.get_ylim()

                # Redibujar el grid completo con resaltado
                self.display_grid()

                # Restaurar los límites del zoom
                self.ax.set_xlim(current_xlim)
                self.ax.set_ylim(current_ylim)
                self.canvas.draw_idle()
            else:
                self.display_grid()


    def _apply_effects_to_segment(self, segment, skip_binary_effects=False):
        """
        Aplica TODOS los efectos configurados a un segmento individual.
        Incluye: Sigma, Downscaling, Brillo, Binario, Inversión

        Args:
            segment: Imagen del segmento (numpy array)
            skip_binary_effects: Si es True, salta los pasos de binario e inversión (útil si ya están aplicados)

        Returns:
            Segmento procesado con todos los efectos aplicados
        """
        import numpy as np

        processed = segment.copy()

        # 1. SIGMA (Gaussian Blur) - si está activo en los ajustes
        if hasattr(self, "sigma") and self.sigma > 0:
            sigma = self.sigma
            # Calcular kernel size apropiado para el sigma
            kernel_size = int(2 * np.ceil(3 * sigma) + 1)
            if kernel_size > 0 and kernel_size % 2 == 1:  # Debe ser impar
                processed = cv2.GaussianBlur(
                    processed, (kernel_size, kernel_size), sigma
                )

        # 2. DOWNSCALING / UPSCALING
        if hasattr(self, "downscale_factor") and self.downscale_factor != 1.0:
            factor = self.downscale_factor  # Usar como float, no convertir a int

            # Calcular nuevas dimensiones
            original_height, original_width = processed.shape[:2]
            new_height = max(1, int(original_height / factor))
            new_width = max(1, int(original_width / factor))

            # Aplicar redimensionamiento PERMANENTE
            # NO volver al tamaño original - el downscaling debe reducir la resolución
            if factor > 1.0:
                # Downscale (reducir): usar INTER_AREA para mejor calidad
                processed = cv2.resize(
                    processed, (new_width, new_height), interpolation=cv2.INTER_AREA
                )
                self.log_to_console(
                    f"  🔽 Downscaling aplicado: {original_width}×{original_height} → {new_width}×{new_height} px "
                    f"(factor {factor:.2f}×)",
                    "INFO",
                )
            else:
                # Upscale (aumentar): usar INTER_LINEAR
                processed = cv2.resize(
                    processed, (new_width, new_height), interpolation=cv2.INTER_LINEAR
                )
                self.log_to_console(
                    f"  🔼 Upscaling aplicado: {original_width}×{original_height} → {new_width}×{new_height} px "
                    f"(factor {factor:.2f}×)",
                    "INFO",
                )

        # 3. BRILLO (Brightness adjustment)
        if hasattr(self, "brightness") and self.brightness != 100:
            factor = self.brightness / 100.0
            processed = cv2.convertScaleAbs(processed, alpha=factor, beta=0)

        # 4. CONVERSIÓN A BINARIO
        if (
            not skip_binary_effects
            and hasattr(self, "binary_mode_enabled")
            and self.binary_mode_enabled
        ):
            # Normalizar a 0-100
            normalized = processed.astype(np.float64)
            if normalized.max() > 0:
                normalized = normalized / normalized.max()
            normalized = normalized * 100.0

            # Aplicar threshold
            threshold = (
                self.binary_threshold if hasattr(self, "binary_threshold") else 50.0
            )
            processed = np.where(normalized >= threshold, 255, 0).astype(np.uint8)

        # 5. INVERSIÓN DE IMAGEN
        if (
            not skip_binary_effects
            and hasattr(self, "invert_projection")
            and self.invert_projection
        ):
            processed = 255 - processed if processed.max() > 1 else 1.0 - processed

        # 6. CALIBRACIÓN (MATRIZ DE ATENUACIÓN)
        # Aplicar matriz de compensación de uniformidad si está activa
        if (
            hasattr(self, "apply_attenuation_to_grid")
            and self.apply_attenuation_to_grid
            and hasattr(self, "attenuation_matrix")
            and self.attenuation_matrix is not None
        ):

            # Normalizar la imagen procesada a rango 0-1 para aplicar calibración
            if processed.max() > 1.0:
                processed_normalized = processed.astype(np.float64) / 255.0
            else:
                processed_normalized = processed.astype(np.float64)

            # Obtener matriz con flips aplicados (si están configurados)
            calibration_matrix = self.get_calibration_matrix_with_flips()

            # Redimensionar matriz de calibración al tamaño del chunk si es necesario
            chunk_height, chunk_width = processed_normalized.shape[:2]
            matrix_height, matrix_width = calibration_matrix.shape[:2]

            if (chunk_height != matrix_height) or (chunk_width != matrix_width):
                # Necesitamos redimensionar la matriz de calibración
                from scipy.ndimage import zoom

                zoom_factors = (
                    chunk_height / matrix_height,
                    chunk_width / matrix_width,
                )
                attenuation_resized = zoom(calibration_matrix, zoom_factors, order=1)
            else:
                attenuation_resized = calibration_matrix

            # Aplicar intensidad de calibración
            if hasattr(self, "attenuation_strength"):
                strength_factor = self.attenuation_strength / 100.0
            else:
                strength_factor = 1.0

            # Interpolar entre sin corrección (1.0) y corrección completa
            adjusted_matrix = 1.0 + (attenuation_resized - 1.0) * strength_factor

            # Aplicar matriz al chunk
            processed_calibrated = np.clip(
                processed_normalized * adjusted_matrix, 0, 1.0
            )

            # Volver a escala 0-255 si era necesario
            if processed.max() > 1.0:
                processed = (processed_calibrated * 255.0).astype(np.uint8)
            else:
                processed = processed_calibrated.astype(np.float64)

            self.log_to_console(
                f"  ✨ Calibración aplicada: strength={strength_factor*100:.0f}%, "
                f"matriz {matrix_width}×{matrix_height} → chunk {chunk_width}×{chunk_height}",
                "INFO",
            )

        return processed

    # ═══════════════════════════════════════════════════════════════════════════
    # FUNCIONES DE TRANSFORMACIÓN DE IMAGEN (ROTACIÓN, ESPEJO)
    # ═══════════════════════════════════════════════════════════════════════════


    def draw_segments_overlay(self):
        """
        Dibuja el overlay de segmentos en el grid.
        Muestra rectángulos con líneas discontinuas sobre cada segmento de imagen.
        """
        if not self.show_segments_overlay or not self.image_segments:
            return

        if not hasattr(self, "ax") or self.ax is None:
            return

        if not hasattr(self, "image_on_grid") or self.image_on_grid is None:
            return

        # Convertir píxeles a unidades del grid
        pixel_size = self.grid_cell_size / self.grid_pixels_per_cell

        # Dibujar rectángulos de segmentos
        for segment in self.image_segments:
            # Coordenadas en píxeles de la imagen
            x_start_px = segment["x_start"]
            y_start_px = segment["y_start"]
            width_px = segment["width"]
            height_px = segment["height"]

            # Convertir a coordenadas del grid (unidades del grid)
            # Sumar la posición de la imagen en el grid
            x_start_grid = (self.image_position[0] + x_start_px) * pixel_size
            y_start_grid = (self.image_position[1] + y_start_px) * pixel_size
            width_grid = width_px * pixel_size
            height_grid = height_px * pixel_size

            # Dibujar rectángulo del segmento
            from matplotlib.patches import Rectangle

            rect = Rectangle(
                (x_start_grid, y_start_grid),
                width_grid,
                height_grid,
                linewidth=2,
                edgecolor="cyan",
                facecolor="none",
                linestyle="--",
                alpha=0.8,
            )
            self.ax.add_patch(rect)

            # Añadir etiqueta del segmento en el centro
            center_x = x_start_grid + width_grid / 2
            center_y = y_start_grid + height_grid / 2
            self.ax.text(
                center_x,
                center_y,
                f"S{segment['id']}",
                ha="center",
                va="center",
                fontsize=10,
                color="cyan",
                weight="bold",
                bbox=dict(
                    boxstyle="round,pad=0.5",
                    facecolor="black",
                    alpha=0.7,
                    edgecolor="cyan",
                    linewidth=1.5,
                ),
            )


    def draw_projecting_segment_highlight(self):
        """
        Resalta con color rojo tenue el chunk que se está proyectando actualmente.
        Solo relleno visual, sin texto ni etiquetas (info va a consola).
        """
        if not self.current_projecting_segment:
            return

        if not hasattr(self, "ax") or self.ax is None:
            return

        if not hasattr(self, "image_on_grid") or self.image_on_grid is None:
            return

        segment_data = self.current_projecting_segment.get("segment_data")
        if not segment_data:
            return

        # Convertir píxeles a unidades del grid
        pixel_size = self.grid_cell_size / self.grid_pixels_per_cell

        # Coordenadas en píxeles de la imagen
        x_start_px = segment_data["x_start"]
        y_start_px = segment_data["y_start"]
        width_px = segment_data["width"]
        height_px = segment_data["height"]

        # Convertir a coordenadas del grid (unidades del grid)
        x_start_grid = (self.image_position[0] + x_start_px) * pixel_size
        y_start_grid = (self.image_position[1] + y_start_px) * pixel_size
        width_grid = width_px * pixel_size
        height_grid = height_px * pixel_size

        # Dibujar SOLO rectángulo con relleno rojo tenue (sin texto)
        from matplotlib.patches import Rectangle

        # Rectángulo con relleno rojo semi-transparente
        rect_highlight = Rectangle(
            (x_start_grid, y_start_grid),
            width_grid,
            height_grid,
            linewidth=0,
            edgecolor="none",
            facecolor="red",
            alpha=0.4,
            zorder=98,
        )
        self.ax.add_patch(rect_highlight)

