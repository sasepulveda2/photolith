"""
Mixin: generación y proyección de regla de escala calibrada.

Genera una imagen de líneas (grandes y pequeñas) cuya separación
corresponde a una distancia física real en micrones, basándose en
la calibración espacial (mm_per_pixel). Soporta proyección
temporizada con desplazamiento motorizado en X.
"""
import json
import os
import numpy as np

from PyQt5.QtCore import QTimer
from PyQt5.QtWidgets import QMessageBox, QApplication

from constants import CACHE_DIR


RULER_CONFIG_FILE = os.path.join(CACHE_DIR, "ruler_config.json")

RULER_DEFAULTS = {
    "separation_px": 100,
    "subdivisions": 5,
    "line_width_large_px": 2,
    "line_width_small_px": 1,
    "line_height_pct": 100,
    "alignment": "Centro",
    "offset_x": 0,
    "step_mode": "Pantalla Completa",
    "exposure_time_s": 10.0,
    "num_projections": 1,
}


class RulerScaleMixin:
    """Mixin: lógica de la sección Regla de Escala."""

    # ═══════════════════════════════════════════════════════════════════════
    # INICIALIZACIÓN
    # ═══════════════════════════════════════════════════════════════════════

    def _init_ruler_scale(self):
        self._ruler_config = dict(RULER_DEFAULTS)
        self._ruler_running = False
        self._ruler_current_projection = 0
        self._ruler_total_projections = 1
        self._ruler_motor_steps_moved = 0
        self._ruler_scale_view_active = False
        self._ruler_exposure_timer = QTimer()
        self._ruler_exposure_timer.setSingleShot(True)
        self._ruler_exposure_timer.timeout.connect(self._ruler_on_exposure_done)
        self._ruler_stabilize_timer = QTimer()
        self._ruler_stabilize_timer.setSingleShot(True)
        self._ruler_stabilize_timer.timeout.connect(self._ruler_expose_step)
        self._load_ruler_config()

    # ═══════════════════════════════════════════════════════════════════════
    # TOGGLE VISTA
    # ═══════════════════════════════════════════════════════════════════════

    def toggle_ruler_scale_view(self):
        """Alterna entre la vista normal y la vista de Regla de Escala."""
        # Verificar calibración
        if getattr(self, "mm_per_pixel", None) is None and not self._ruler_scale_view_active:
            self._show_warning(
                "Sin Calibración Espacial",
                "Debe calibrar primero el tamaño de los píxeles\n"
                "(botón 'Calibrar Tamaño') antes de usar la Regla de escala.",
            )
            return

        self._ruler_scale_view_active = not self._ruler_scale_view_active

        if self._ruler_scale_view_active:
            self._activate_ruler_view()
        else:
            self._deactivate_ruler_view()

    def _activate_ruler_view(self):
        """Activa la vista de Regla de Escala: muestra panel, oculta sidebar normal."""
        # Desactivar otros modos si están activos
        if getattr(self, "grid_view_active", False):
            self.toggle_grid_view()
        if getattr(self, "calibration_view_active", False):
            self.toggle_calibration_view()
        if getattr(self, "_pattern_calib_view_active", False):
            self.toggle_pattern_calibration_view()
        if getattr(self, "_motors_view_active", False):
            self.toggle_motors_view()
        if getattr(self, "_proyecciones_view_active", False):
            self.toggle_proyecciones_view()

        # Ocultar sidebar normal, mostrar panel de regla
        if hasattr(self, "_main_sidebar"):
            self._main_sidebar.setVisible(False)
        if hasattr(self, "motors_panel_widget"):
            self.motors_panel_widget.setVisible(False)
        if hasattr(self, "motor_central_widget"):
            self.motor_central_widget.setVisible(False)
        if hasattr(self, "ruler_panel_widget"):
            self.ruler_panel_widget.setVisible(True)

        # Actualizar botón de la toolbar
        if hasattr(self, "ruler_scale_button"):
            self.ruler_scale_button.setText("️ Salir Regla")

        # Actualizar info del panel
        self.update_ruler_info_panel()

        # Mostrar canvas con fondo negro y mensaje
        if hasattr(self, "figure"):
            self.figure.clear()
            self.ax = self.figure.add_subplot(111)
            self.ax.set_facecolor("black")
            self.ax.text(
                0.5, 0.5,
                "Presione 'Vista Previa' para generar la imagen de líneas",
                transform=self.ax.transAxes,
                ha="center", va="center",
                color="#888888", fontsize=12,
            )
            self.ax.axis("off")
            self.canvas.draw_idle()

        # Mostrar el botón del proyector
        if hasattr(self, "projector_button"):
            self._ruler_prev_proj_visible = self.projector_button.isVisible()
            self.projector_button.setVisible(True)

        self.log_to_console("Modo Regla de escala activado.", "INFO")

    def _deactivate_ruler_view(self):
        """Desactiva la vista de Regla de Escala: muestra sidebar normal."""
        # Ocultar panel de regla, mostrar sidebar normal
        if hasattr(self, "ruler_panel_widget"):
            self.ruler_panel_widget.setVisible(False)
        if hasattr(self, "_main_sidebar"):
            self._main_sidebar.setVisible(True)

        # Restaurar botón de la toolbar
        if hasattr(self, "ruler_scale_button"):
            self.ruler_scale_button.setText("Regla de escala")
        if hasattr(self, "projector_button"):
            self.projector_button.setVisible(getattr(self, "_ruler_prev_proj_visible", False))

        # Restaurar canvas
        if hasattr(self, "figure"):
            self.figure.clear()
            self.ax = self.figure.add_subplot(111)
            self.ax.set_facecolor("#121212")
            self.ax.axis("off")
            # Restaurar imagen si existe
            if getattr(self, "pattern", None) is not None:
                self.simulate_optics()
            else:
                self.canvas.draw_idle()

        self.log_to_console("Modo Regla de Escala desactivado.", "INFO")

    # ═══════════════════════════════════════════════════════════════════════
    # GENERACIÓN DE IMAGEN
    # ═══════════════════════════════════════════════════════════════════════

    def _get_screen_dimensions(self):
        """Devuelve (width, height) del monitor secundario o None."""
        pw = getattr(self, "projection_window", None)
        if pw is not None and pw.screen_geometry is not None:
            return pw.screen_geometry.width(), pw.screen_geometry.height()

        screens = QApplication.screens()
        if len(screens) > 1:
            geo = screens[1].geometry()
            return geo.width(), geo.height()
        return None

    def generate_ruler_image(self):
        """Genera un numpy array (uint8) con las líneas de escala.

        Returns:
            numpy array de forma (height, width) con valores 0 o 255,
            o None si los parámetros son inválidos.
        """
        mm_per_px = getattr(self, "mm_per_pixel", None)
        if mm_per_px is None or mm_per_px <= 0:
            return None

        dims = self._get_screen_dimensions()
        if dims is None:
            return None

        screen_w, screen_h = dims
        cfg = self._ruler_config

        separation_px = cfg.get("separation_px", 100)
        
        if separation_px < 0:
            return None

        subdivisions = max(0, cfg["subdivisions"])
        w_large = max(1, cfg["line_width_large_px"])
        w_small = max(1, cfg["line_width_small_px"])
        height_pct = max(10, min(100, cfg["line_height_pct"]))
        alignment = cfg.get("alignment", "Centro")

        h_large = int(screen_h * height_pct / 100.0)
        h_small = h_large // 2

        if alignment == "Abajo":
            y_bot_large = screen_h
            y_top_large = screen_h - h_large
            y_bot_small = screen_h
            y_top_small = screen_h - h_small
        elif alignment == "Arriba":
            y_top_large = 0
            y_bot_large = h_large
            y_top_small = 0
            y_bot_small = h_small
        else:  # Centro
            y_center = screen_h // 2
            y_top_large = y_center - h_large // 2
            y_bot_large = y_top_large + h_large
            y_top_small = y_center - h_small // 2
            y_bot_small = y_top_small + h_small

        # Fondo
        canvas = np.zeros((screen_h, screen_w), dtype=np.uint8)

        # Margen inicial configurable
        x_offset = cfg.get("offset_x", 0)

        # Dibujar líneas grandes y subdivisiones
        x = 0.0
        last_drawn_x = 0.0
        
        # Si la separación es 0, dibujamos una sola línea y paramos
        if separation_px == 0:
            x_pos = x + x_offset
            x_int = int(round(x_pos))
            if x_int < screen_w:
                x_start = max(0, x_int - w_large // 2)
                x_end = min(screen_w, x_start + w_large)
                canvas[y_top_large:y_bot_large, x_start:x_end] = 255
            last_drawn_x = x
        else:
            while (x + x_offset) < screen_w:
                last_drawn_x = x
                x_pos = x + x_offset
                x_int = int(round(x_pos))
                x_start = max(0, x_int - w_large // 2)
                x_end = min(screen_w, x_start + w_large)
                canvas[y_top_large:y_bot_large, x_start:x_end] = 255
    
                # Subdivisiones entre esta línea grande y la siguiente
                next_x = x + separation_px
                if (next_x + x_offset) < screen_w and subdivisions > 0:
                    step = separation_px / (subdivisions + 1)
                    for s in range(1, subdivisions + 1):
                        sx = x + step * s + x_offset
                        sx_int = int(round(sx))
                        if sx_int >= screen_w:
                            break
                        sx_start = max(0, sx_int - w_small // 2)
                        sx_end = min(screen_w, sx_start + w_small)
                        canvas[y_top_small:y_bot_small, sx_start:sx_end] = 255
    
                x = next_x

        self._ruler_last_line_distance_px = last_drawn_x
        return canvas

    # ═══════════════════════════════════════════════════════════════════════
    # VISTA PREVIA
    # ═══════════════════════════════════════════════════════════════════════

    def preview_ruler_image(self):
        """Genera la imagen de líneas y la muestra en el canvas principal."""
        if getattr(self, "mm_per_pixel", None) is None:
            self.log_to_console(
                "Debe calibrar primero (mm/px) antes de usar la Regla de Escala.",
                "WARNING",
            )
            return

        image = self.generate_ruler_image()
        if image is None:
            self.log_to_console(
                "No se pudo generar la imagen. Revise los parámetros.",
                "WARNING",
            )
            return

        self._save_ruler_config()

        # Mostrar en el canvas principal usando la misma lógica que simulate_optics
        if hasattr(self, "ax") and hasattr(self, "canvas"):
            self.ax.clear()
            self.ax.imshow(image, cmap="gray", vmin=0, vmax=255, aspect="equal")
            self.ax.set_facecolor("black")
            self.ax.set_title("Vista Previa — Regla de Escala", color="#E0E0E0", fontsize=11)
            self.ax.axis("off")
            self.canvas.draw_idle()
            self.log_to_console(
                f"Vista previa generada: {image.shape[1]}×{image.shape[0]} px",
                "SUCCESS",
            )

    # ═══════════════════════════════════════════════════════════════════════
    # SECUENCIA DE PROYECCIÓN
    # ═══════════════════════════════════════════════════════════════════════

    def start_ruler_sequence(self):
        """Inicia la secuencia de proyección de la regla de escala."""
        if self._ruler_running:
            self.log_to_console("Ya hay una secuencia de escala en curso.", "WARNING")
            return

        if not getattr(self, "projector_active", False):
            self._show_warning(
                "Proyector inactivo",
                "Active el proyector antes de iniciar la secuencia.",
            )
            return

        if getattr(self, "projection_window", None) is None:
            self._show_warning("Error", "No hay ventana de proyección disponible.")
            return

        if getattr(self, "mm_per_pixel", None) is None:
            self._show_warning(
                "Sin Calibración",
                "Debe calibrar primero (mm/px) para usar la Regla de Escala.",
            )
            return

        image = self.generate_ruler_image()
        if image is None:
            self._show_warning(
                "Error de Generación",
                "No se pudo generar la imagen de escala. Revise los parámetros.",
            )
            return

        self._save_ruler_config()

        self._ruler_image = image
        self._ruler_running = True
        self._ruler_current_projection = 0
        self._ruler_total_projections = max(1, self._ruler_config["num_projections"])
        self._ruler_exposure_time_ms = int(self._ruler_config["exposure_time_s"] * 1000)

        # Validaciones de límites del motor
        controller = getattr(self, "motor_controller_instance", None)
        if controller is None or controller.ser is None:
            self._show_warning("Error", "Controlador de motor desconectado. No se puede hacer la secuencia automática.")
            self._ruler_running = False
            return
            
        m_sep = self._ruler_config.get("motor_sep_mm", 1.0)
        tot_len_mm = max(0, self._ruler_total_projections - 1) * m_sep
        steps_per_mm = 6400.0
        tot_len_steps = int(round(tot_len_mm * steps_per_mm))
        
        axis_limit = controller.limits.get("X", None)
        if axis_limit is None:
            self._show_warning("Error", "No hay un limite asignado al eje X. Configure los limites del motor primero.")
            self._ruler_running = False
            return
        
        # La vuelta previa sera siempre dos vueltas 360 (segun la configuracion del motor X)
        from motors.main import load_settings
        settings = load_settings()
        steps_360_x = settings.get("steps_360", {}).get("X", 3200)
        self._ruler_preturn_steps = int(steps_360_x) * 2
        
        self.log_to_console(f"Vuelta previa configurada: {self._ruler_preturn_steps} steps (2 vueltas 360).", "INFO")
        
        # Sumar la vuelta previa al total para la validacion de limites
        total_needed_steps = tot_len_steps + self._ruler_preturn_steps
            
        if total_needed_steps > abs(axis_limit):
            preturn_mm = self._ruler_preturn_steps / steps_per_mm
            self._show_warning("Error", 
                f"El largo total ({tot_len_mm:.3f} mm) + vuelta previa backlash ({preturn_mm:.3f} mm) "
                f"excede la distancia hasta el limite del motor X.")
            self._ruler_running = False
            return

        self._ruler_update_ui_state(running=True)
        
        preturn_info = ""
        if self._ruler_preturn_steps > 0:
            preturn_info = f" (+ vuelta previa backlash: {self._ruler_preturn_steps} steps)"
        
        self.log_to_console(
            f"Secuencia iniciada: {self._ruler_total_projections} proyeccion(es), "
            f"separacion {m_sep} mm.{preturn_info}",
            "SUCCESS",
        )

        # 1. Mover al extremo (limite) antes de comenzar
        self._ruler_update_status("Moviendo al extremo del eje X...")
        current_pos = controller.positions.get("X", 0)
        steps_to_limit = axis_limit - current_pos
        
        if steps_to_limit != 0:
            self.log_to_console(f"Moviendo al limite X ({axis_limit} steps)...", "INFO")
            
            x_feedrate = settings.get("feedrates", {}).get("X", 5000)
            x_max_feedrate = settings.get("max_feedrates", {}).get("X", 5000)
            
            # La velocidad real fisica no puede superar el limite del firmware
            effective_feedrate = min(x_feedrate, x_max_feedrate)
            
            try:
                controller.step_move("X", int(steps_to_limit), feedrate=x_feedrate)
                
                # Distancia en unidades de firmware (step_size = 1/80)
                firmware_dist_mm = abs(steps_to_limit) * controller.step_size
                time_s = firmware_dist_mm / (effective_feedrate / 60.0)
                wait_time_ms = max(500, int(time_s * 1000) + 1500)
                
                self.log_to_console(f"Esperando {time_s:.1f}s de viaje + 1.5s estabilizacion...", "INFO")
                try: self._ruler_stabilize_timer.timeout.disconnect()
                except TypeError: pass
                self._ruler_stabilize_timer.timeout.connect(self._ruler_preturn_step)
                self._ruler_stabilize_timer.start(wait_time_ms)
            except Exception as e:
                self.log_to_console(f"Error moviendo motor: {e}", "ERROR")
                self._ruler_finish()
        else:
            # Ya estamos en el limite
            self._ruler_preturn_step()

    def _ruler_preturn_step(self):
        """Ejecuta la vuelta previa de backlash mecanico si es necesario."""
        if not self._ruler_running:
            return
        
        if self._ruler_preturn_steps <= 0:
            # No hay vuelta previa, pasar directo a proyectar
            self._ruler_expose_step()
            return
        
        controller = getattr(self, "motor_controller_instance", None)
        if controller is None or controller.ser is None:
            self._ruler_expose_step()
            return
        
        from motors.main import load_settings
        settings = load_settings()
        x_feedrate = settings.get("feedrates", {}).get("X", 5000)
        x_max_feedrate = settings.get("max_feedrates", {}).get("X", 5000)
        effective_feedrate = min(x_feedrate, x_max_feedrate)
        
        current_pos = controller.positions.get("X", 0)
        # Determinar direccion hacia el origen.
        # Si el limite (posicion actual) es negativo, el origen (0) esta hacia el positivo.
        # Si es positivo, el origen esta hacia el negativo.
        direction_to_origin = 1 if current_pos < 0 else -1
        return_steps = int(direction_to_origin * self._ruler_preturn_steps)
        
        self._ruler_update_status("Vuelta previa (backlash mecanico)...")
        self.log_to_console(
            f"Vuelta previa: moviendo {self._ruler_preturn_steps} steps hacia el origen para enganchar engranajes...", "INFO"
        )
        
        try:
            # Mover hacia el origen por la cantidad de backlash
            controller.step_move("X", return_steps, feedrate=x_feedrate, ignore_limits=False)
            
            firmware_dist = abs(return_steps) * controller.step_size
            time_s = firmware_dist / (effective_feedrate / 60.0)
            wait_ms = max(500, int(time_s * 1000) + 1000)
            
            try: self._ruler_stabilize_timer.timeout.disconnect()
            except TypeError: pass
            self._ruler_stabilize_timer.timeout.connect(self._ruler_expose_step)
            self._ruler_stabilize_timer.start(wait_ms)
        except Exception as e:
            self.log_to_console(f"Error en vuelta previa: {e}", "ERROR")
            self._ruler_expose_step()


    def _ruler_expose_step(self):
        """Proyecta la imagen de escala e inicia el timer de exposición."""
        if not self._ruler_running:
            return

        self._ruler_current_projection += 1
        self._ruler_update_status(
            f"Proyectando {self._ruler_current_projection}/{self._ruler_total_projections}..."
        )

        self.projection_window.set_brightness(100.0)
        self.projection_window.set_inversion(False) # Asegurar líneas blancas en fondo negro
        self.projection_window.update_image(self._ruler_image.astype(np.float64) / 255.0)

        self._ruler_exposure_timer.start(self._ruler_exposure_time_ms)

    def _ruler_on_exposure_done(self):
        """Callback cuando el timer de exposición termina."""
        if not self._ruler_running:
            return

        # Pantalla negra
        if self.projection_window:
            self.projection_window.show_black_screen()

        self.log_to_console(
            f"Exposición {self._ruler_current_projection}/{self._ruler_total_projections} completada.",
            "INFO",
        )

        if self._ruler_current_projection >= self._ruler_total_projections:
            self._ruler_finish()
            return

        # Mover motor en X y luego proyectar la siguiente
        self._ruler_move_step()

    def _ruler_move_step(self):
        """Mueve el motor en X en dirección al origen (negativo) por la separación asignada."""
        controller = getattr(self, "motor_controller_instance", None)
        if controller is None or controller.ser is None:
            self.log_to_console("Motor no conectado.", "WARNING")
            self._ruler_stabilize_timer.start(100)
            return

        m_sep = self._ruler_config.get("motor_sep_mm", 1.0)
        if m_sep <= 0:
            self._ruler_stabilize_timer.start(100)
            return
            
        steps_per_mm = 6400.0
        steps_to_move = int(round(m_sep * steps_per_mm))
        
        # Validar si nos pasaríamos del origen (0)
        current_pos = controller.positions.get("X", 0)
        if abs(current_pos) - steps_to_move < 0:
            self._ruler_update_status("Se alcanzó el origen prematuramente.")
            self.log_to_console("Origen (0) alcanzado. Deteniendo secuencia.", "WARNING")
            self._ruler_finish()
            return

        direction_sign = 1 if current_pos < 0 else -1
        move_steps = int(direction_sign * steps_to_move)

        self._ruler_update_status("Moviendo motor X...")
        
        from motors.main import load_settings
        settings = load_settings()
        x_feedrate = settings.get("feedrates", {}).get("X", 5000)
        x_max_feedrate = settings.get("max_feedrates", {}).get("X", 5000)
        
        effective_feedrate = min(x_feedrate, x_max_feedrate)
        
        self.log_to_console(
            f"Moviendo Motor X: {move_steps} pasos hacia origen ({m_sep:.3f} mm a F{x_feedrate})...", "INFO"
        )

        # Distancia en unidades de firmware (step_size = 1/80)
        firmware_dist_mm = abs(move_steps) * controller.step_size
        time_s = firmware_dist_mm / (effective_feedrate / 60.0)
        wait_time_ms = max(500, int(time_s * 1000) + 1500) # 1.5s extra de estabilización

        try:
            controller.step_move("X", move_steps, feedrate=x_feedrate)
            self.log_to_console(f"Estabilizando {wait_time_ms/1000:.1f}s ({firmware_dist_mm:.1f}mm firmware a F{effective_feedrate})...", "SUCCESS")
        except Exception as e:
            self.log_to_console(f"Error moviendo motor: {e}", "ERROR")
            wait_time_ms = 500

        self._ruler_stabilize_timer.start(wait_time_ms)

    def _ruler_finish(self):
        """Finaliza la secuencia y regresa el motor al origen (0)."""
        controller = getattr(self, "motor_controller_instance", None)

        if controller is not None and controller.ser is not None:
            current_pos = controller.positions.get("X", 0)
            if current_pos != 0:
                self._ruler_update_status("Regresando motor al origen...")
                
                from motors.main import load_settings
                settings = load_settings()
                x_feedrate = settings.get("feedrates", {}).get("X", 5000)
                x_max_feedrate = settings.get("max_feedrates", {}).get("X", 5000)
                
                effective_feedrate = min(x_feedrate, x_max_feedrate)
                
                self.log_to_console(f"Devolviendo Motor X al origen ({-current_pos} pasos a F{x_feedrate})...", "INFO")
                try:
                    controller.step_move("X", int(-current_pos), feedrate=x_feedrate, ignore_limits=True)
                    self.log_to_console("Motor X regresado correctamente al origen (0).", "SUCCESS")
                except Exception as e:
                    self.log_to_console(f"Error regresando motor: {e}", "ERROR")

        self._ruler_running = False
        self._ruler_update_ui_state(running=False)
        self._ruler_update_status("Secuencia completada")
        self.log_to_console("Secuencia Step-and-Repeat completada.", "SUCCESS")

    def stop_ruler_sequence(self):
        """Aborta la secuencia en curso."""
        if not self._ruler_running:
            return

        self._ruler_exposure_timer.stop()
        self._ruler_stabilize_timer.stop()

        # Pantalla negra
        if getattr(self, "projection_window", None) is not None:
            self.projection_window.show_black_screen()

        # Regresar motor
        controller = getattr(self, "motor_controller_instance", None)
        if controller is not None and controller.ser is not None:
            current_pos = controller.positions.get("X", 0)
            if current_pos != 0:
                from motors.main import load_settings
                settings = load_settings()
                x_feedrate = settings.get("feedrates", {}).get("X", 5000)
                x_max_feedrate = settings.get("max_feedrates", {}).get("X", 5000)
                
                effective_feedrate = min(x_feedrate, x_max_feedrate)
                
                self.log_to_console(f"Devolviendo Motor X al origen ({-current_pos} pasos a F{x_feedrate})...", "INFO")
                try:
                    controller.step_move("X", int(-current_pos), feedrate=x_feedrate, ignore_limits=True)
                    self.log_to_console("Motor X regresado correctamente al origen.", "SUCCESS")
                except Exception as e:
                    self.log_to_console(f"Error regresando motor: {e}", "ERROR")

        self._ruler_running = False
        self._ruler_update_ui_state(running=False)
        self._ruler_update_status("Secuencia detenida")
        self.log_to_console("Secuencia de escala detenida por el usuario.", "WARNING")

    def _ruler_go_home_x(self):
        """Mueve el motor X de regreso a su posición de inicio lógica (0) usando la odometría."""
        controller = getattr(self, "motor_controller_instance", None)
        if controller is None or not controller.ser:
            self._show_warning("Error", "Controlador de motor desconectado.")
            return
            
        current_steps = controller.positions.get("X", 0)
        if current_steps == 0:
            return
            
        try:
            self.ruler_panel_widget.setEnabled(False)
            self.log_to_console(f"Regresando motor X al origen ({-current_steps} steps)...", "INFO")
            controller.step_move("X", -current_steps, 1, ignore_limits=True)
            self.log_to_console("Motor X en origen", "SUCCESS")
        except Exception as e:
            self.log_to_console(f"Error al regresar al origen: {e}", "ERROR")
        finally:
            self.ruler_panel_widget.setEnabled(True)

    def _ruler_manual_move(self, direction):
        """Mueve manualmente el motor X la distancia especificada en mm."""
        controller = getattr(self, "motor_controller_instance", None)
        if controller is None or controller.ser is None:
            self.log_to_console("Motor no conectado. No se puede mover.", "WARNING")
            return
            
        dist_mm = getattr(self, "ruler_motor_dist_input", None)
        if dist_mm is None: return
        dist_val = dist_mm.value()
        if dist_val <= 0: return
        
        steps_per_mm = 6400.0
        steps = int(round(dist_val * steps_per_mm))
        
        axis_limit = controller.limits.get("X", None)
        if axis_limit is None: axis_limit = float('inf')
        current_pos = controller.positions.get("X", 0)
        target_pos = current_pos + (steps * direction)
        
        if target_pos < 0 or target_pos > axis_limit:
            self.log_to_console(f"Movimiento manual excede límites del motor X (0 - {axis_limit} steps). Destino: {target_pos}.", "WARNING")
            return
            
        try:
            controller.step_move("X", direction, steps)
            sign = "+" if direction > 0 else "-"
            self.log_to_console(f"Motor X movido {sign}{steps} pasos ({sign}{dist_val:.3f} mm) manualmente.", "INFO")
        except Exception as e:
            self.log_to_console(f"Error en movimiento manual: {e}", "ERROR")

    # ═══════════════════════════════════════════════════════════════════════
    # UI HELPERS
    # ═══════════════════════════════════════════════════════════════════════

    def _ruler_update_status(self, text):
        if hasattr(self, "ruler_status_label"):
            self.ruler_status_label.setText(f"Estado: {text}")

    def _ruler_update_ui_state(self, running):
        if hasattr(self, "ruler_start_btn"):
            self.ruler_start_btn.setVisible(not running)
        if hasattr(self, "ruler_stop_btn"):
            self.ruler_stop_btn.setVisible(running)
        if hasattr(self, "ruler_preview_btn"):
            self.ruler_preview_btn.setEnabled(not running)

    def update_ruler_info_panel(self):
        """Actualiza las etiquetas informativas del panel de Regla de Escala."""
        if not hasattr(self, "ruler_info_resolution"):
            return

        dims = self._get_screen_dimensions()
        mm_per_px = getattr(self, "mm_per_pixel", None)

        if dims is None:
            self.ruler_info_resolution.setText("Resolución: Sin monitor")
            self.ruler_info_scale.setText("Escala: -")
            if hasattr(self, "ruler_info_pixel_size"):
                self.ruler_info_pixel_size.setText("Tamaño Píxel: -")
            self.ruler_info_dim_mm.setText("Dimensión: -")
            self.ruler_info_dim_um.setText("Dimensión: -")
            return

        w, h = dims
        self.ruler_info_resolution.setText(f"Resolución: {w} × {h} px")

        if mm_per_px is None:
            self.ruler_info_scale.setText("Escala: Sin calibrar")
            if hasattr(self, "ruler_info_pixel_size"):
                self.ruler_info_pixel_size.setText("Tamaño Píxel: Sin calibrar")
            self.ruler_info_dim_mm.setText("Dimensión: -")
            self.ruler_info_dim_um.setText("Dimensión: -")
            return

        self.ruler_info_scale.setText(f"Escala: {mm_per_px:.5f} mm/px")
        if hasattr(self, "ruler_info_pixel_size"):
            self.ruler_info_pixel_size.setText(f"Tamaño Píxel: {mm_per_px * 1000.0:.2f} µm/px")

        w_mm = w * mm_per_px
        h_mm = h * mm_per_px
        self.ruler_info_dim_mm.setText(f"Dimensión: {w_mm:.3f} × {h_mm:.3f} mm")
        w_um = w_mm * 1000
        h_um = h_mm * 1000
        self.ruler_info_dim_um.setText(f"Dimensión: {w_um:.1f} × {h_um:.1f} µm")
        
        if hasattr(self, "lbl_ruler_sep_um") and hasattr(self, "_ruler_config"):
            sep_px = self._ruler_config.get("separation_px", 0)
            if sep_px > 0:
                sep_um = sep_px * mm_per_px * 1000.0
                self.lbl_ruler_sep_um.setText(f"~ {sep_um:.1f} µm")
            else:
                self.lbl_ruler_sep_um.setText("~ 0 µm")

        if hasattr(self, "lbl_ruler_total_len") and hasattr(self, "_ruler_config"):
            n_proj = self._ruler_config.get("num_projections", 1)
            m_sep = self._ruler_config.get("motor_sep_mm", 1.0)
            tot_len = max(0, n_proj - 1) * m_sep
            self.lbl_ruler_total_len.setText(f"Largo total a recorrer: {tot_len:.3f} mm")
            
        # Sincronizar el spinbox de px con el porcentaje actual
        if hasattr(self, "ruler_height_px_spin") and hasattr(self, "ruler_height_pct_spin"):
            pct = self.ruler_height_pct_spin.value()
            px = int(h * pct / 100.0)
            self.ruler_height_px_spin.blockSignals(True)
            self.ruler_height_px_spin.setValue(px)
            self.ruler_height_px_spin.blockSignals(False)

    # ═══════════════════════════════════════════════════════════════════════
    # PERSISTENCIA
    # ═══════════════════════════════════════════════════════════════════════

    def _save_ruler_config(self):
        try:
            os.makedirs(CACHE_DIR, exist_ok=True)
            with open(RULER_CONFIG_FILE, "w", encoding="utf-8") as f:
                json.dump(self._ruler_config, f, indent=2)
        except Exception as e:
            print(f"Error guardando ruler config: {e}")

    def _load_ruler_config(self):
        if not os.path.exists(RULER_CONFIG_FILE):
            return
        try:
            with open(RULER_CONFIG_FILE, "r", encoding="utf-8") as f:
                saved = json.load(f)
            for key in RULER_DEFAULTS:
                if key in saved:
                    self._ruler_config[key] = type(RULER_DEFAULTS[key])(saved[key])
        except Exception:
            pass

    def _sync_ruler_config_from_ui(self):
        """Lee los valores actuales de los widgets y los guarda en _ruler_config."""
        try:
            val_text = self.ruler_separation_input.text().replace(",", ".")
            self._ruler_config["separation_px"] = int(round(float(val_text)))
        except (ValueError, AttributeError):
            pass

        for attr, key in [
            ("ruler_subdivisions_spin", "subdivisions"),
            ("ruler_line_large_spin", "line_width_large_px"),
            ("ruler_line_small_spin", "line_width_small_px"),
            ("ruler_height_pct_spin", "line_height_pct"),
            ("ruler_offset_spin", "offset_x"),
            ("ruler_num_proj_spin", "num_projections"),
        ]:
            widget = getattr(self, attr, None)
            if widget is not None:
                self._ruler_config[key] = widget.value()

        if hasattr(self, "ruler_alignment_combo"):
            self._ruler_config["alignment"] = self.ruler_alignment_combo.currentText()
            
        if hasattr(self, "ruler_motor_sep_spin"):
            self._ruler_config["motor_sep_mm"] = self.ruler_motor_sep_spin.value()

        try:
            self._ruler_config["exposure_time_s"] = float(
                self.ruler_exposure_time_input.text().replace(",", ".")
            )
        except (ValueError, AttributeError):
            pass
