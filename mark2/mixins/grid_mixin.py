"""
Mixin de grid litografico.

Genera, dibuja y gestiona el grid de celdas, pixel grid,
interacciones de mouse (drag, zoom, pan) y grabacion de movimiento.
"""
import numpy as np
from scipy.ndimage import gaussian_filter

from PyQt5.QtWidgets import QMessageBox
from PyQt5.QtCore import Qt


class GridMixin:
    """Mixin: Grid functionality."""

    def generate_grid(self):
        """
        Genera el grid de litografía con precisión float para todas las dimensiones.
        Unidades: μm, mm, cm (configurables), con resolución en px/unidad.
        """
        try:
            # Convertir a float para máxima precisión litográfica
            self.grid_width = float(self.grid_width_input.text())
            self.grid_height = float(self.grid_height_input.text())
            self.grid_cell_size = float(self.grid_cell_input.text())
            self.grid_pixels_per_cell = int(self.grid_pixels_input.text())
            self.grid_unit = self.grid_unit_combo.currentText()

            if (
                self.grid_width <= 0
                or self.grid_height <= 0
                or self.grid_cell_size <= 0
                or self.grid_pixels_per_cell <= 0
            ):
                QMessageBox.warning(
                    self, "Valores inválidos", "Los valores deben ser mayores que cero."
                )
                return

            self.save_grid_config()
            self.grid_generated = True
            self.generate_grid_button.setText("💾 Guardar Nuevo Tamaño")
            self.display_grid()

            # Actualizar información de segmentación si está en modo automático
            if self.segmentation_mode == 0:
                self.update_segmentation_preview()

        except ValueError:
            QMessageBox.warning(
                self, "Error de entrada", "Por favor ingrese valores numéricos válidos."
            )
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Error al generar el grid: {str(e)}")


    def display_grid(self):
        try:
            import numpy as np

            cells_x = int(self.grid_width / self.grid_cell_size)
            cells_y = int(self.grid_height / self.grid_cell_size)

            self.canvas.figure.clear()
            self.ax = self.canvas.figure.add_subplot(111)
            self.ax.set_facecolor("#1E1E1E" if self.dark_mode else "#FFFFFF")

            for i in range(cells_x + 1):
                x_pos = i * self.grid_cell_size
                self.ax.axvline(x=x_pos, color=self.grid_color, linewidth=1, alpha=0.8)

            for i in range(cells_y + 1):
                y_pos = i * self.grid_cell_size
                self.ax.axhline(y=y_pos, color=self.grid_color, linewidth=1, alpha=0.8)

            # Dibujar grilla de píxeles si está activada
            if self.show_pixel_grid:
                self._draw_pixel_grid()

            self.ax.set_xlim(0, self.grid_width)
            self.ax.set_ylim(0, self.grid_height)

            # Conectar evento para redibujar grid de píxeles cuando se hace zoom/pan
            if self.show_pixel_grid:
                self.ax.callbacks.connect("xlim_changed", self._on_zoom_or_pan)
                self.ax.callbacks.connect("ylim_changed", self._on_zoom_or_pan)
            self.ax.set_aspect("equal")

            self.ax.set_xlabel(
                f"Ancho ({self.grid_unit})",
                color="#E0E0E0" if self.dark_mode else "#000000",
            )
            self.ax.set_ylabel(
                f"Alto ({self.grid_unit})",
                color="#E0E0E0" if self.dark_mode else "#000000",
            )
            self.ax.tick_params(colors="#E0E0E0" if self.dark_mode else "#000000")

            for spine in self.ax.spines.values():
                spine.set_edgecolor("#E0E0E0" if self.dark_mode else "#000000")

            # Superponer imagen si existe
            if self.image_on_grid is not None:
                self.overlay_image_on_grid()

            # Dibujar overlay de segmentos si está activo
            self.draw_segments_overlay()

            # Dibujar resaltado del chunk que se está proyectando actualmente
            self.draw_projecting_segment_highlight()

            self.canvas.draw()

            resolution = self.grid_pixels_per_cell / self.grid_cell_size
            pixel_size = self.grid_cell_size / self.grid_pixels_per_cell

            self.grid_dimensions_label.setText(
                f"Dimensiones: {self.grid_width} x {self.grid_height} {self.grid_unit}"
            )
            self.grid_cells_x_label.setText(f"Celdas X: {cells_x}")
            self.grid_cells_y_label.setText(f"Celdas Y: {cells_y}")
            self.grid_cell_size_label.setText(
                f"Tamaño celda: {self.grid_cell_size} {self.grid_unit}"
            )
            self.grid_pixels_label.setText(
                f"Píxeles/celda: {self.grid_pixels_per_cell} px"
            )
            self.grid_resolution_label.setText(
                f"Resolución: {resolution:.2f} px/{self.grid_unit}"
            )
            self.grid_pixel_size_label.setText(
                f"Tamaño píxel: {pixel_size:.4f} {self.grid_unit}/px"
            )
            self.grid_total_cells_label.setText(f"Total celdas: {cells_x * cells_y}")
            self.grid_color_label.setText(f"Color: {self.grid_color}")

            self.grid_stats_section.setVisible(True)
            self.grid_stats_section.set_collapsed(False)
            self.grid_status_label.setText(f"✅ Grid: {cells_x}x{cells_y} celdas")

        except Exception as e:
            QMessageBox.critical(self, "Error", f"Error al mostrar el grid: {str(e)}")


    def _draw_pixel_grid(self):
        """
        Dibuja el grid de píxeles basándose en la vista actual (zoom).
        Solo dibuja las líneas visibles en la vista actual para optimizar rendimiento.
        """
        if not hasattr(self, "ax") or self.ax is None:
            return

        # Obtener límites visibles actuales
        xlim = self.ax.get_xlim()
        ylim = self.ax.get_ylim()

        pixel_step = self.grid_cell_size / self.grid_pixels_per_cell

        # Calcular número de líneas de píxeles en la región VISIBLE
        visible_width = xlim[1] - xlim[0]
        visible_height = ylim[1] - ylim[0]
        visible_pixel_lines_x = int(visible_width / pixel_step)
        visible_pixel_lines_y = int(visible_height / pixel_step)

        max_pixel_lines = 1000  # Límite para mantener rendimiento óptimo

        # Solo dibujar si el número de líneas es razonable
        if (visible_pixel_lines_x + visible_pixel_lines_y) <= max_pixel_lines:
            # Calcular índices de las líneas visibles
            start_x = int(xlim[0] / pixel_step)
            end_x = int(xlim[1] / pixel_step) + 1
            start_y = int(ylim[0] / pixel_step)
            end_y = int(ylim[1] / pixel_step) + 1

            # Dibujar líneas verticales de píxeles (solo las visibles)
            for i in range(start_x, end_x):
                x_pos = i * pixel_step
                # Verificar que está en el rango del grid y no es línea principal
                if 0 <= x_pos <= self.grid_width and x_pos % self.grid_cell_size != 0:
                    self.ax.axvline(
                        x=x_pos, color=self.grid_pixel_color, linewidth=0.5, alpha=0.5
                    )

            # Dibujar líneas horizontales de píxeles (solo las visibles)
            for i in range(start_y, end_y):
                y_pos = i * pixel_step
                # Verificar que está en el rango del grid y no es línea principal
                if 0 <= y_pos <= self.grid_height and y_pos % self.grid_cell_size != 0:
                    self.ax.axhline(
                        y=y_pos, color=self.grid_pixel_color, linewidth=0.5, alpha=0.5
                    )


    def _on_zoom_or_pan(self, event=None):
        """
        Callback que se ejecuta cuando se hace zoom o pan.
        Redibuja el grid de píxeles solo en la región visible.
        """
        if not self.show_pixel_grid or not hasattr(self, "ax") or self.ax is None:
            return

        # Evitar recursión: desconectar temporalmente los callbacks
        if hasattr(self, "_updating_pixel_grid") and self._updating_pixel_grid:
            return

        self._updating_pixel_grid = True

        try:
            # Guardar límites actuales
            xlim = self.ax.get_xlim()
            ylim = self.ax.get_ylim()

            # Eliminar solo las líneas de píxeles (las delgadas)
            # Mantener las líneas principales del grid (las gruesas)
            lines_to_remove = []
            for line in self.ax.get_lines():
                if line.get_linewidth() < 1.0:  # Las líneas de píxeles son más delgadas
                    lines_to_remove.append(line)

            for line in lines_to_remove:
                line.remove()

            # Redibujar grid de píxeles en la región visible
            self._draw_pixel_grid()

            # Redibujar canvas (sin restaurar límites, ya están correctos)
            self.canvas.draw_idle()
        finally:
            self._updating_pixel_grid = False


    def toggle_pixel_grid(self, state):
        """Activa o desactiva la visualización de la grilla de píxeles"""
        try:
            self.show_pixel_grid = bool(state)
            self.save_grid_config()

            if self.grid_generated:
                self.display_grid()
        except Exception as e:
            QMessageBox.warning(
                self,
                "Error",
                f"Error al cambiar visibilidad de grid de píxeles: {str(e)}",
            )


    def change_drag_mode(self, index):
        """Cambia entre modo Fixed y Free para arrastrar la imagen"""
        self.drag_mode = "fixed" if index == 0 else "free"
        if self.image_on_grid is not None and self.drag_mode == "fixed":
            # Ajustar posición al chunk más cercano
            self.snap_to_optimal_chunks()


    def update_image_coordinates(self):
        """
        Actualiza las etiquetas de coordenadas de la imagen en el grid.
        Coordenadas en píxeles con precisión float para litografía de alta resolución.
        """
        if self.image_on_grid is None:
            self.coord_top_left_label.setText("🔺 Superior Izq: -")
            self.coord_top_right_label.setText("🔺 Superior Der: -")
            self.coord_bottom_left_label.setText("🔻 Inferior Izq: -")
            self.coord_bottom_right_label.setText("🔻 Inferior Der: -")
            return

        h, w = self.image_on_grid.shape[:2]
        x, y = self.image_position

        # Calcular coordenadas de las esquinas en píxeles del grid (precisión float)
        top_left = (x, y)
        top_right = (x + w - 1, y)
        bottom_left = (x, y + h - 1)
        bottom_right = (x + w - 1, y + h - 1)

        # Mostrar con precisión de 2 decimales para coordenadas sub-pixel
        self.coord_top_left_label.setText(
            f"🔺 Superior Izq: ({top_left[0]:.2f}, {top_left[1]:.2f})"
        )
        self.coord_top_right_label.setText(
            f"🔺 Superior Der: ({top_right[0]:.2f}, {top_right[1]:.2f})"
        )
        self.coord_bottom_left_label.setText(
            f"🔻 Inferior Izq: ({bottom_left[0]:.2f}, {bottom_left[1]:.2f})"
        )
        self.coord_bottom_right_label.setText(
            f"🔻 Inferior Der: ({bottom_right[0]:.2f}, {bottom_right[1]:.2f})"
        )


    def snap_to_optimal_chunks(self):
        """
        Ajusta la posición de la imagen para alinearla con los chunks del grid.
        Utiliza precisión float para permitir ajustes sub-pixel si es necesario.
        """
        if self.image_on_grid is None:
            return

        h, w = self.image_on_grid.shape[:2]
        chunk_size_px = float(self.grid_pixels_per_cell)  # float para precisión

        # Calcular cuántos chunks ocupa la imagen
        chunks_w = int(np.ceil(w / chunk_size_px))
        chunks_h = int(np.ceil(h / chunk_size_px))

        # Ajustar a la esquina del chunk más cercano (float para precisión)
        chunk_x = round(self.image_position[0] / chunk_size_px)
        chunk_y = round(self.image_position[1] / chunk_size_px)

        self.image_position = [
            float(chunk_x * chunk_size_px),
            float(chunk_y * chunk_size_px),
        ]
        self.update_image_coordinates()
        self.display_grid()


    def apply_grid_effects(self, image):
        """Aplica los efectos de intensidad, desenfoque y modo binario a la imagen para el grid"""
        if image is None:
            return None

        result = image.copy().astype(np.float64)

        # Aplicar desenfoque (sigma)
        if self.sigma > 0:
            result = gaussian_filter(result, sigma=self.sigma)

        # Aplicar intensidad (brightness) - mejorado para mayor visibilidad
        # Normalizar a 0-1 si es necesario
        if result.max() > 1.0:
            result = result / 255.0

        intensity_factor = self.brightness / 100.0
        result = result * intensity_factor

        # Aplicar modo binario si está activado
        if self.binary_mode_enabled:
            # Convertir a porcentaje 0-100 para comparar con threshold
            intensity_percent = result * 100.0

            # Aplicar inversión antes de binarización si está activada
            if self.invert_projection:
                intensity_percent = 100.0 - intensity_percent

            # Binarización estricta: >= threshold → blanco (255), < threshold → negro (0)
            result = np.where(intensity_percent >= self.binary_threshold, 1.0, 0.0)
        else:
            # Aplicar inversión en modo escala de grises si está activada
            if self.invert_projection:
                result = 1.0 - result

        # Volver a rango 0-255 para visualización
        result = (result * 255.0).clip(0, 255).astype(np.uint8)

        return result


    def overlay_image_on_grid(self):
        """
        Superpone la imagen cargada sobre el grid.

        NOTA: La calibración NO se aplica aquí porque:
        - Esta es solo una VISUALIZACIÓN en el grid
        - La calibración real se aplica a cada CHUNK durante la SEGMENTACIÓN
        - Cada chunk recibe su porción específica de la matriz de calibración
        """
        if self.image_on_grid is None:
            return

        # Aplicar transformaciones geométricas (rotación, espejos) y luego mostrar
        display_image = self.apply_image_transforms(self.image_on_grid)

        # Aplicar efectos (sigma, brightness, binario, inversión) a la visualización
        display_image = self.apply_grid_effects(display_image)

        # NOTA: El downscaling NO se aplica aquí en la visualización del grid
        # Se aplica individualmente a cada CHUNK después de la segmentación
        # Esto mantiene la coherencia: la imagen en el grid muestra el tamaño original,
        # pero cada chunk proyectado tendrá el downscaling aplicado

        h, w = display_image.shape[:2]
        pixel_size = self.grid_cell_size / self.grid_pixels_per_cell

        # Convertir posición en píxeles a coordenadas del grid
        x_pos = self.image_position[0] * pixel_size
        y_pos = self.image_position[1] * pixel_size

        # Dimensiones de la imagen en unidades del grid
        img_width = w * pixel_size
        img_height = h * pixel_size

        # Mostrar la imagen en escala de grises o color según corresponda
        if len(display_image.shape) == 2:
            # Imagen en escala de grises
            self.ax.imshow(
                display_image,
                cmap="gray",
                extent=[x_pos, x_pos + img_width, y_pos + img_height, y_pos],
                alpha=0.7,
                interpolation="nearest",
            )
        else:
            # Imagen a color
            self.ax.imshow(
                display_image,
                extent=[x_pos, x_pos + img_width, y_pos + img_height, y_pos],
                alpha=0.7,
                interpolation="nearest",
            )


    def on_mouse_press(self, event):
        """Maneja el evento de presionar el mouse"""
        if not self.grid_view_active:
            return

        if not hasattr(self, "ax") or self.ax is None:
            return

        if event.inaxes != self.ax:
            return

        # Botón central (2) = Pan de vista
        if event.button == 2:
            self.panning = True
            self.pan_start_pos = [event.xdata, event.ydata]
            self.canvas.setCursor(Qt.ClosedHandCursor)
            return

        # Botón izquierdo (1) = Mover imagen
        if event.button == 1 and self.image_on_grid is not None:
            # Verificar si el click está sobre la imagen
            pixel_size = self.grid_cell_size / self.grid_pixels_per_cell
            h, w = self.image_on_grid.shape[:2]

            x_pos = self.image_position[0] * pixel_size
            y_pos = self.image_position[1] * pixel_size
            img_width = w * pixel_size
            img_height = h * pixel_size

            if (
                x_pos <= event.xdata <= x_pos + img_width
                and y_pos <= event.ydata <= y_pos + img_height
            ):
                self.dragging_image = True
                self.drag_start_pos = [event.xdata, event.ydata]


    def on_mouse_release(self, event):
        """Maneja el evento de soltar el mouse"""
        # Terminar pan con botón central
        if event.button == 2 and self.panning:
            self.panning = False
            self.pan_start_pos = None
            self.canvas.setCursor(Qt.ArrowCursor)
            return

        # Terminar arrastre de imagen
        if self.dragging_image:
            self.dragging_image = False
            self.drag_start_pos = None

            if self.drag_mode == "fixed":
                self.snap_to_optimal_chunks()

            # Grabar posición si está grabando
            if self.recording:
                self.recorded_positions.append(tuple(self.image_position))
                self.recorded_positions_label.setText(
                    f"Posiciones grabadas: {len(self.recorded_positions)}"
                )


    def on_mouse_move(self, event):
        """
        Maneja el movimiento del mouse para pan de vista o arrastre de imagen.
        """
        if not hasattr(self, "ax") or self.ax is None:
            return

        if event.inaxes != self.ax:
            return

        # Pan con botón central
        if self.panning and self.pan_start_pos is not None:
            dx = event.xdata - self.pan_start_pos[0]
            dy = event.ydata - self.pan_start_pos[1]

            # Obtener límites actuales
            xlim = self.ax.get_xlim()
            ylim = self.ax.get_ylim()

            # Aplicar desplazamiento
            self.ax.set_xlim(xlim[0] - dx, xlim[1] - dx)
            self.ax.set_ylim(ylim[0] - dy, ylim[1] - dy)

            # Redibujar
            self.canvas.draw_idle()
            return

        # Arrastre de imagen
        if not self.dragging_image:
            return

        if self.drag_start_pos is None:
            return

        pixel_size = float(self.grid_cell_size) / float(self.grid_pixels_per_cell)

        # Calcular el desplazamiento (float para precisión)
        dx = float(event.xdata - self.drag_start_pos[0])
        dy = float(event.ydata - self.drag_start_pos[1])

        # Convertir a píxeles del grid (mantener como float en modo libre)
        dx_px = dx / pixel_size
        dy_px = dy / pixel_size

        moved = False

        if self.drag_mode == "free":
            # Modo libre: movimiento continuo con precisión float (sub-pixel)
            if (
                abs(dx_px) > 0.01 or abs(dy_px) > 0.01
            ):  # Umbral mínimo para evitar ruido
                self.image_position[0] += dx_px
                self.image_position[1] += dy_px
                self.drag_start_pos = [event.xdata, event.ydata]
                moved = True
        else:
            # Modo fixed: movimiento por chunks completos (precisión int)
            chunk_size_px = float(self.grid_pixels_per_cell)
            if abs(dx_px) >= 1.0 or abs(dy_px) >= 1.0:
                chunks_x = int(dx_px // 1.0)
                chunks_y = int(dy_px // 1.0)
                self.image_position[0] += float(chunks_x)
                self.image_position[1] += float(chunks_y)
                self.drag_start_pos[0] += chunks_x * pixel_size
                self.drag_start_pos[1] += chunks_y * pixel_size
                moved = True

        if moved:
            self.update_image_coordinates()
            self.quick_redraw_image()


    def on_mouse_scroll(self, event):
        """
        Maneja el evento de scroll del mouse para hacer zoom.
        Scroll up = zoom in, Scroll down = zoom out
        """
        if not self.grid_view_active:
            return

        if not hasattr(self, "ax") or self.ax is None:
            return

        if event.inaxes != self.ax:
            return

        # Factor de zoom
        zoom_factor = 1.2 if event.button == "up" else 0.8

        # Obtener límites actuales
        xlim = self.ax.get_xlim()
        ylim = self.ax.get_ylim()

        # Calcular punto central del zoom (posición del mouse)
        xdata = event.xdata
        ydata = event.ydata

        # Calcular nuevos límites centrados en el cursor
        x_range = xlim[1] - xlim[0]
        y_range = ylim[1] - ylim[0]

        new_x_range = x_range / zoom_factor
        new_y_range = y_range / zoom_factor

        # Mantener el punto bajo el cursor fijo
        x_ratio = (xdata - xlim[0]) / x_range
        y_ratio = (ydata - ylim[0]) / y_range

        new_xlim = [xdata - new_x_range * x_ratio, xdata + new_x_range * (1 - x_ratio)]
        new_ylim = [ydata - new_y_range * y_ratio, ydata + new_y_range * (1 - y_ratio)]

        # Limitar el zoom para no alejarse demasiado
        grid_width = self.grid_width if hasattr(self, "grid_width") else 100
        grid_height = self.grid_height if hasattr(self, "grid_height") else 100

        # No permitir zoom out más allá de 1.5x el tamaño del grid
        if new_x_range > grid_width * 1.5 or new_y_range > grid_height * 1.5:
            return

        # No permitir zoom in más allá de 1 píxel
        if new_x_range < 1 or new_y_range < 1:
            return

        # Aplicar nuevos límites
        self.ax.set_xlim(new_xlim)
        self.ax.set_ylim(new_ylim)

        # Redibujar
        self.canvas.draw_idle()


    def quick_redraw_image(self):
        """Redibuja solo la imagen sin regenerar todo el grid para movimiento fluido"""
        if self.image_on_grid is None:
            return

        try:
            # Limpiar solo las imágenes superpuestas, manteniendo el grid
            for img in self.ax.images[:]:
                img.remove()

            # Superponer la imagen en la nueva posición
            self.overlay_image_on_grid()

            # Redibujar solo el canvas (más rápido que display_grid completo)
            self.canvas.draw_idle()

            # NO actualizar proyección automáticamente - solo mostrar segmentos individuales
            # if self.projector_active and self.projection_window is not None and self.grid_view_active:
            #     self.projection_window.set_image(self.image_on_grid)
        except:
            # Si falla, usar el método completo
            self.display_grid()


    def toggle_recording(self):
        """Inicia o detiene la grabación de posiciones"""
        if not self.recording:
            # Iniciar grabación
            self.recording = True
            self.recorded_positions = []
            self.record_button.setText("⏹️ Detener Grabación")
            self.record_button.setStyleSheet("background-color: #FF4444;")
            QMessageBox.information(
                self,
                "Grabación iniciada",
                "Mueve la imagen por el grid.\nCada posición se guardará automáticamente.",
            )
        else:
            # Detener grabación
            self.recording = False
            self.record_button.setText("⏺️ Grabar Movimiento")
            self.record_button.setStyleSheet("")
            self.play_button.setEnabled(len(self.recorded_positions) > 0)
            QMessageBox.information(
                self,
                "Grabación finalizada",
                f"Se grabaron {len(self.recorded_positions)} posiciones.\n"
                f"Presiona '▶️ Reproducir' para ver el movimiento.",
            )


    def play_movement(self):
        """Reproduce el movimiento grabado"""
        if len(self.recorded_positions) == 0:
            return

        if self.playback_active:
            # Detener reproducción
            self.playback_active = False
            self.playback_timer.stop()
            self.play_button.setText("▶️ Reproducir")
            self.record_button.setEnabled(True)
            self.drag_mode_combo.setEnabled(True)
        else:
            # Iniciar reproducción
            self.playback_active = True
            self.playback_index = 0
            self.play_button.setText("⏸️ Pausar")
            self.record_button.setEnabled(False)
            self.drag_mode_combo.setEnabled(False)
            # 100ms entre cada posición (10 fps)
            self.playback_timer.start(100)


    def playback_step(self):
        """Ejecuta un paso de la reproducción"""
        if self.playback_index >= len(self.recorded_positions):
            # Finalizar reproducción
            self.playback_active = False
            self.playback_timer.stop()
            self.play_button.setText("▶️ Reproducir")
            self.record_button.setEnabled(True)
            self.drag_mode_combo.setEnabled(True)
            return

        # Mover a la siguiente posición
        self.image_position = list(self.recorded_positions[self.playback_index])
        self.update_image_coordinates()
        self.quick_redraw_image()
        self.playback_index += 1

