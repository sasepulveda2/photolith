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
    "separation_um": 100.0,
    "subdivisions": 5,
    "line_width_large_px": 2,
    "line_width_small_px": 1,
    "line_height_pct": 100,
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
                "(botón 'Calibrar Tamaño') antes de usar la Regla de Escala.",
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

        # Ocultar sidebar normal, mostrar panel de regla
        if hasattr(self, "_main_sidebar"):
            self._main_sidebar.setVisible(False)
        if hasattr(self, "ruler_panel_widget"):
            self.ruler_panel_widget.setVisible(True)

        # Actualizar botón de la toolbar
        if hasattr(self, "ruler_scale_button"):
            self.ruler_scale_button.setText("🖼️ Salir Regla")

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

        self.log_to_console("Modo Regla de Escala activado.", "INFO")

    def _deactivate_ruler_view(self):
        """Desactiva la vista de Regla de Escala: muestra sidebar normal."""
        # Ocultar panel de regla, mostrar sidebar normal
        if hasattr(self, "ruler_panel_widget"):
            self.ruler_panel_widget.setVisible(False)
        if hasattr(self, "_main_sidebar"):
            self._main_sidebar.setVisible(True)

        # Restaurar botón de la toolbar
        if hasattr(self, "ruler_scale_button"):
            self.ruler_scale_button.setText("📏 Regla de Escala")
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

        separation_um = cfg["separation_um"]
        if separation_um <= 0:
            return None

        separation_mm = separation_um / 1000.0
        separation_px = separation_mm / mm_per_px

        if separation_px < 1.0:
            self.log_to_console(
                f"La separación ({separation_um} µm = {separation_px:.2f} px) "
                "es menor a 1 píxel. No se pueden resolver las líneas.",
                "WARNING",
            )
            return None

        subdivisions = max(1, cfg["subdivisions"])
        w_large = max(1, cfg["line_width_large_px"])
        w_small = max(1, cfg["line_width_small_px"])
        height_pct = max(10, min(100, cfg["line_height_pct"]))

        h_large = int(screen_h * height_pct / 100.0)
        h_small = h_large // 2

        # Centrar verticalmente
        y_center = screen_h // 2
        y_top_large = y_center - h_large // 2
        y_bot_large = y_top_large + h_large
        y_top_small = y_center - h_small // 2
        y_bot_small = y_top_small + h_small

        canvas = np.zeros((screen_h, screen_w), dtype=np.uint8)

        # Dibujar líneas grandes y subdivisiones
        x = 0.0
        while x < screen_w:
            x_int = int(round(x))
            x_start = max(0, x_int - w_large // 2)
            x_end = min(screen_w, x_start + w_large)
            canvas[y_top_large:y_bot_large, x_start:x_end] = 255

            # Subdivisiones entre esta línea grande y la siguiente
            next_x = x + separation_px
            if next_x < screen_w:
                step = separation_px / (subdivisions + 1)
                for s in range(1, subdivisions + 1):
                    sx = x + step * s
                    sx_int = int(round(sx))
                    if sx_int >= screen_w:
                        break
                    sx_start = max(0, sx_int - w_small // 2)
                    sx_end = min(screen_w, sx_start + w_small)
                    canvas[y_top_small:y_bot_small, sx_start:sx_end] = 255

            x = next_x

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
        self._ruler_motor_steps_moved = 0
        self._ruler_exposure_time_ms = int(self._ruler_config["exposure_time_s"] * 1000)

        self._ruler_update_ui_state(running=True)
        self.log_to_console(
            f"Secuencia de escala iniciada: {self._ruler_total_projections} proyección(es), "
            f"{self._ruler_config['exposure_time_s']}s cada una.",
            "SUCCESS",
        )

        # Arrancar la primera exposición directamente
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
        """Mueve el motor en X la distancia equivalente al ancho de pantalla."""
        controller = getattr(self, "motor_controller_instance", None)
        if controller is None or controller.ser is None:
            self.log_to_console(
                "Motor no conectado. Proyectando sin desplazamiento.",
                "WARNING",
            )
            # Continuar sin mover
            self._ruler_stabilize_timer.start(100)
            return

        mm_per_px = self.mm_per_pixel
        dims = self._get_screen_dimensions()
        if dims is None:
            self._ruler_stabilize_timer.start(100)
            return

        screen_w_px = dims[0]
        screen_w_mm = screen_w_px * mm_per_px
        steps_per_mm = 1.0 / controller.step_size
        steps_to_move = int(round(screen_w_mm * steps_per_mm))

        if steps_to_move <= 0:
            self._ruler_stabilize_timer.start(100)
            return

        self._ruler_update_status("Moviendo motor X...")

        try:
            controller.step_move("X", 1, steps_to_move)
            self._ruler_motor_steps_moved += steps_to_move
            self.log_to_console(
                f"Motor X: +{steps_to_move} steps ({screen_w_mm:.3f} mm)",
                "INFO",
            )
        except Exception as e:
            self.log_to_console(f"Error moviendo motor: {e}", "ERROR")

        # Esperar estabilización antes de la siguiente exposición
        self._ruler_stabilize_timer.start(500)

    def _ruler_finish(self):
        """Finaliza la secuencia y regresa el motor al origen."""
        controller = getattr(self, "motor_controller_instance", None)

        if controller is not None and controller.ser is not None and self._ruler_motor_steps_moved > 0:
            self._ruler_update_status("Regresando motor a posición inicial...")
            try:
                controller.step_move("X", -1, self._ruler_motor_steps_moved)
                self.log_to_console(
                    f"Motor X regresado: -{self._ruler_motor_steps_moved} steps",
                    "INFO",
                )
            except Exception as e:
                self.log_to_console(f"Error regresando motor: {e}", "ERROR")

        self._ruler_running = False
        self._ruler_motor_steps_moved = 0
        self._ruler_update_ui_state(running=False)
        self._ruler_update_status("Secuencia completada")
        self.log_to_console("Secuencia de regla de escala completada.", "SUCCESS")

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
        if controller is not None and controller.ser is not None and self._ruler_motor_steps_moved > 0:
            try:
                controller.step_move("X", -1, self._ruler_motor_steps_moved)
                self.log_to_console(
                    f"Motor X regresado: -{self._ruler_motor_steps_moved} steps",
                    "INFO",
                )
            except Exception as e:
                self.log_to_console(f"Error regresando motor: {e}", "ERROR")

        self._ruler_running = False
        self._ruler_motor_steps_moved = 0
        self._ruler_update_ui_state(running=False)
        self._ruler_update_status("Secuencia detenida")
        self.log_to_console("Secuencia de escala detenida por el usuario.", "WARNING")

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
            self.ruler_info_dim_mm.setText("Dimensión: -")
            self.ruler_info_dim_um.setText("Dimensión: -")
            return

        w, h = dims
        self.ruler_info_resolution.setText(f"Resolución: {w} × {h} px")

        if mm_per_px is None:
            self.ruler_info_scale.setText("Escala: Sin calibrar")
            self.ruler_info_dim_mm.setText("Dimensión: -")
            self.ruler_info_dim_um.setText("Dimensión: -")
            return

        self.ruler_info_scale.setText(f"Escala: {mm_per_px:.5f} mm/px")
        w_mm = w * mm_per_px
        h_mm = h * mm_per_px
        self.ruler_info_dim_mm.setText(f"Dimensión: {w_mm:.3f} × {h_mm:.3f} mm")
        w_um = w_mm * 1000
        h_um = h_mm * 1000
        self.ruler_info_dim_um.setText(f"Dimensión: {w_um:.1f} × {h_um:.1f} µm")

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
            self._ruler_config["separation_um"] = float(
                self.ruler_separation_input.text().replace(",", ".")
            )
        except (ValueError, AttributeError):
            pass

        for attr, key in [
            ("ruler_subdivisions_spin", "subdivisions"),
            ("ruler_line_large_spin", "line_width_large_px"),
            ("ruler_line_small_spin", "line_width_small_px"),
            ("ruler_height_pct_spin", "line_height_pct"),
            ("ruler_num_proj_spin", "num_projections"),
        ]:
            widget = getattr(self, attr, None)
            if widget is not None:
                self._ruler_config[key] = widget.value()

        try:
            self._ruler_config["exposure_time_s"] = float(
                self.ruler_exposure_time_input.text().replace(",", ".")
            )
        except (ValueError, AttributeError):
            pass
