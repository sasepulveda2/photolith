"""
Mixin de procesamiento de imagen.

Simulacion optica (Gaussian), modo binario, transformaciones
geometricas (rotacion, espejo), segmentacion y downscaling.
"""
import cv2
import numpy as np
from scipy.ndimage import gaussian_filter

from PyQt5.QtWidgets import QMessageBox


class ImageProcessingMixin:
    """Mixin: ImageProcessing functionality."""

    def simulate_optics(self):
        # 1. Obtener patrón con transformaciones aplicadas
        working_pattern = self.pattern.copy()
        
        if hasattr(self, "apply_image_transforms"):
            working_pattern = self.apply_image_transforms(working_pattern)
            
        if getattr(self, "exposure_mirror_h", False):
            import cv2
            working_pattern = cv2.flip(working_pattern, 1)
        if getattr(self, "exposure_mirror_v", False):
            import cv2
            working_pattern = cv2.flip(working_pattern, 0)

        # Aplicar desenfoque gaussiano (para mapa de calor)
        psf_result = gaussian_filter(working_pattern, sigma=self.sigma)

        # Calcular intensidad en porcentaje para mapa de calor (derecha)
        intensity_percentage = (
            (psf_result / psf_result.max()) * 100
            if psf_result.max() > 0
            else psf_result
        )

        # Preparar imagen original para visualización (izquierda)
        display_pattern = working_pattern.astype(np.float64)

        # Normalizar a 0-1
        if display_pattern.max() > 0:
            display_pattern = display_pattern / display_pattern.max()

        # Aplicar brillo
        display_pattern = display_pattern * (self.brightness / 100.0)

        # Aplicar modo binario si está activado (SOLO a imagen original izquierda)
        if self.binary_mode_enabled:
            # Convertir a porcentaje
            intensity_percent = display_pattern * 100.0

            # Aplicar inversión antes de binarización si está activada
            if self.invert_projection:
                intensity_percent = 100.0 - intensity_percent

            # Binarización estricta
            display_pattern = np.where(
                intensity_percent >= self.binary_threshold, 1.0, 0.0
            )
        else:
            # Aplicar inversión en modo escala de grises si está activada
            if self.invert_projection:
                display_pattern = 1.0 - display_pattern

        self.last_intensity = intensity_percentage
        # Pasar imagen original procesada (izquierda) y mapa de calor sin cambios (derecha)
        self.plot_results(display_pattern, psf_result, intensity_percentage)
        self.update_info_panel(intensity_percentage)

        # Si estamos en modo "Imagen Completa" (segmentation_mode == 3) y hay proyección activa,
        # actualizar la proyección con la imagen completa
        if (
            self.projector_active
            and self.projection_window is not None
            and self.segmentation_mode == 3
        ):
            # Aplicar efectos si corresponde
            processed = self._apply_effects_to_segment(self.pattern)
            self.projection_window.update_segment(processed)


    def plot_results(self, pattern, simulated, intensity_percentage):
        self.figure.clear()

        bg_color = "#121212" if self.dark_mode else "#FFFFFF"
        text_color = "white" if self.dark_mode else "black"

        show_heat = getattr(self, "show_heatmap", False)

        if show_heat:
            ax1 = self.figure.add_subplot(1, 2, 1)
            ax2 = self.figure.add_subplot(1, 2, 2)
            axes = [ax1, ax2]
        else:
            ax1 = self.figure.add_subplot(1, 1, 1)
            axes = [ax1]

        for ax in axes:
            ax.set_facecolor(bg_color)
            ax.tick_params(colors=text_color)
            ax.xaxis.label.set_color(text_color)
            ax.yaxis.label.set_color(text_color)
            for spine in ax.spines.values():
                spine.set_edgecolor(text_color)

        # Mostrar imagen original procesada (ya con efectos aplicados)
        ax1.imshow(pattern, cmap="gray")
        ax1.set_xlabel("X")
        ax1.set_ylabel("Y")

        if show_heat:
            # Mostrar mapa de calor (sin efectos binarios, solo intensidad)
            ax2.imshow(intensity_percentage, cmap="inferno")
            ax2.set_xlabel("X")
            ax2.set_ylabel("Y")

        self.figure.tight_layout()
        self.canvas.draw()


    def update_info_panel(self, intensity_map):
        if intensity_map is not None:
            h, w = intensity_map.shape
            self.resolution_label.setText(f"Resolución: {w} × {h}")
            self.min_label.setText(f"Intensidad mínima: {intensity_map.min():.2f}")
            self.avg_label.setText(f"Intensidad promedio: {intensity_map.mean():.2f}")
            self.max_label.setText(f"Intensidad máxima: {intensity_map.max():.2f}")

        self.check_second_monitor()

    def toggle_binary_mode(self, state):
        """Activa o desactiva el modo de binarización."""
        self.binary_mode_enabled = bool(state)
        if self.projector_active and self.projection_window is not None:
            self.projection_window.set_binary_mode(self.binary_mode_enabled)

            # Si se desactiva el modo binario y no hay secuencia activa, mostrar imagen
            if (
                not self.binary_mode_enabled
                and not self.sequence_running
                and not self.exposure_active
                and not self.frequency_mode
            ):
                image = self._get_projection_image()
                if image is not None:
                    self.projection_window.update_image(image)

        # Actualizar visualización del grid si está activo
        if self.grid_view_active and self.image_on_grid is not None:
            self.quick_redraw_image()

        # Actualizar vista de imagen principal SOLO si NO estamos en vista de grid
        if not self.grid_view_active and self.pattern is not None:
            self.simulate_optics()

        self.binary_status_label.setText(
            f"Estado: {'✓ Activo' if self.binary_mode_enabled else '✗ Inactivo'}"
        )


    def update_binary_threshold_from_slider(self):
        """Actualiza el umbral de binarización desde el slider."""
        self.binary_threshold = float(self.binary_threshold_slider.value())
        self.binary_threshold_input.setText(f"{self.binary_threshold:.1f}")
        if self.projector_active and self.projection_window is not None:
            self.projection_window.set_binary_threshold(self.binary_threshold)

        # Actualizar visualización del grid si está activo y en modo binario
        if (
            self.binary_mode_enabled
            and self.grid_view_active
            and self.image_on_grid is not None
        ):
            self.quick_redraw_image()

        # Actualizar vista de imagen principal SOLO si NO estamos en vista de grid
        if (
            self.binary_mode_enabled
            and not self.grid_view_active
            and self.pattern is not None
        ):
            self.simulate_optics()


    def update_binary_threshold_from_input(self):
        """Actualiza el umbral de binarización desde el campo de texto."""
        try:
            value = float(self.binary_threshold_input.text())
            if 0 <= value <= 100:
                self.binary_threshold = value
                self.binary_threshold_slider.setValue(int(round(value)))
                if self.projector_active and self.projection_window is not None:
                    self.projection_window.set_binary_threshold(self.binary_threshold)

                # Actualizar visualización del grid si está activo y en modo binario
                if (
                    self.binary_mode_enabled
                    and self.grid_view_active
                    and self.image_on_grid is not None
                ):
                    self.quick_redraw_image()

                # Actualizar vista de imagen principal SOLO si NO estamos en vista de grid
                if (
                    self.binary_mode_enabled
                    and not self.grid_view_active
                    and self.pattern is not None
                ):
                    self.simulate_optics()
            else:
                self.binary_threshold_input.setText(f"{self.binary_threshold:.1f}")
        except ValueError:
            self.binary_threshold_input.setText(f"{self.binary_threshold:.1f}")


    def toggle_intensity_inversion(self, checked: bool):
        self.invert_projection = bool(checked)
        self.save_grid_config()
        self._update_invert_button_text()

        # Actualizar visualización del grid si está activo
        if self.grid_view_active and self.image_on_grid is not None:
            self.quick_redraw_image()

        # Actualizar preview SOLO si NO estamos en vista de grid
        if not self.grid_view_active and self.pattern is not None:
            self.simulate_optics()

        if self.projector_active and self.projection_window is not None:
            self.projection_window.set_inversion(self.invert_projection)
            # NO actualizar imagen completa - solo afecta a segmentos proyectados
            # current_image = self._get_projection_image()
            # if current_image is not None:
            #     self.projection_window.update_image(current_image)
            self.projection_window.set_inversion(self.invert_projection)
            # NO actualizar imagen completa - solo afecta a segmentos proyectados
            # current_image = self._get_projection_image()
            # if current_image is not None:
            #     self.projection_window.update_image(current_image)


    def _update_invert_button_text(self):
        if not hasattr(self, "invert_button"):
            return
        if self.invert_projection:
            self.invert_button.setText("⬛⬜ Intensidad Invertida")
        else:
            self.invert_button.setText("⬜⬛ Invertir Intensidad")


    def _refresh_invert_button_state(self):
        # Actualizar checkbox si existe
        if hasattr(self, "invert_check"):
            self.invert_check.blockSignals(True)
            self.invert_check.setChecked(self.invert_projection)
            self.invert_check.blockSignals(False)

        if not hasattr(self, "invert_button"):
            return
        has_source = self.pattern is not None or (
            hasattr(self, "last_intensity") and self.last_intensity is not None
        )
        self.invert_button.setEnabled(has_source)
        self.invert_button.blockSignals(True)
        self.invert_button.setChecked(self.invert_projection)
        self.invert_button.blockSignals(False)
        self._update_invert_button_text()

    # ═══════════════════════════════════════════════════════════════════════════
    # FUNCIONES DE CONTROL DE PROYECCIÓN Y SECUENCIAS
    # ═══════════════════════════════════════════════════════════════════════════


    def apply_image_transforms(self, image):
        """
        Aplica transformaciones geométricas a la imagen: rotación y espejos.

        Args:
            image: Imagen numpy array (grayscale o color)

        Returns:
            Imagen transformada
        """
        if image is None:
            return None

        transformed = image.copy()

        # 1. Aplicar rotación (0-360°)
        if self.image_rotation != 0:
            # Obtener dimensiones de la imagen
            h, w = transformed.shape[:2]
            center = (w // 2, h // 2)

            # Crear matriz de rotación
            rotation_matrix = cv2.getRotationMatrix2D(center, self.image_rotation, 1.0)

            # Calcular nuevas dimensiones después de rotar
            cos_val = abs(rotation_matrix[0, 0])
            sin_val = abs(rotation_matrix[0, 1])
            new_w = int((h * sin_val) + (w * cos_val))
            new_h = int((h * cos_val) + (w * sin_val))

            # Ajustar la matriz de rotación para el nuevo centro
            rotation_matrix[0, 2] += (new_w / 2) - center[0]
            rotation_matrix[1, 2] += (new_h / 2) - center[1]

            # Detectar el color de fondo usando el píxel de la esquina superior izquierda
            if len(transformed.shape) == 2:
                bg_color = float(transformed[0, 0])
            else:
                bg_color = tuple(float(c) for c in transformed[0, 0])

            # Aplicar rotación con fondo coincidente
            transformed = cv2.warpAffine(
                transformed,
                rotation_matrix,
                (new_w, new_h),
                borderMode=cv2.BORDER_CONSTANT,
                borderValue=bg_color,
            )

        # 2. Aplicar espejo horizontal (flip left-right)
        if self.image_mirror_h:
            transformed = cv2.flip(transformed, 1)

        # 3. Aplicar espejo vertical (flip up-down)
        if self.image_mirror_v:
            transformed = cv2.flip(transformed, 0)

        return transformed


    def update_image_transform(self):
        """
        Actualiza las transformaciones de imagen cuando el usuario cambia los controles.
        """
        # Actualizar variables desde el slider (0-360°)
        self.image_rotation = self.rotation_slider.value()
        self.rotation_value_label.setText(f"{self.image_rotation}°")

        self.image_mirror_h = self.mirror_horizontal_checkbox.isChecked()
        self.image_mirror_v = self.mirror_vertical_checkbox.isChecked()

        # Limpiar cache de segmentación (las transformaciones afectan el slice)
        self._last_segmentation_pattern_id = None

        # Actualizar visualización INMEDIATAMENTE en el grid
        if self.pattern is not None and self.grid_view_active:
            if hasattr(self, "ax") and self.ax is not None:
                # Guardar límites actuales del zoom
                current_xlim = self.ax.get_xlim()
                current_ylim = self.ax.get_ylim()

                # Redibujar el grid con la imagen transformada
                self.display_grid()

                # Restaurar los límites del zoom
                self.ax.set_xlim(current_xlim)
                self.ax.set_ylim(current_ylim)
                self.canvas.draw_idle()
        elif self.pattern is not None and not self.grid_view_active:
            self.simulate_optics()

        # Actualizar proyección si está activa
        if self.projector_active and self.projection_window is not None:
            current_image = self._get_projection_image()
            if current_image is not None:
                self.projection_window.update_image(current_image)

        self.log_to_console(
            f"🔄 Transformación actualizada: Rotación={self.image_rotation}°, "
            f"Espejo H={self.image_mirror_h}, Espejo V={self.image_mirror_v}",
            "INFO",
        )

    # ═══════════════════════════════════════════════════════════════════════════
    # FUNCIONES DE SEGMENTACIÓN DE IMAGEN (PRE-PROCESAMIENTO LITOGRÁFICO)
    # ═══════════════════════════════════════════════════════════════════════════


    def update_downscale_factor(self, value):
        """
        Actualiza el factor de downscaling y muestra la resolución resultante.

        IMPORTANTE: El downscaling se aplica a CADA CHUNK INDIVIDUAL después de
        la segmentación, NO a la imagen completa. Esto mantiene la coherencia con
        el grid - la imagen sigue ocupando las mismas celdas, pero cada celda
        proyectada tendrá menor/mayor resolución.
        """
        self.downscale_factor = float(value)

        # Calcular y mostrar resolución resultante POR CHUNK
        if self.pattern is not None and hasattr(self, "grid_pixels_per_cell"):
            # Tamaño de una celda del grid (antes del downscaling)
            cell_size = int(self.grid_pixels_per_cell)

            # Tamaño después del downscaling (aplicado a cada chunk)
            chunk_width = max(1, int(cell_size / self.downscale_factor))
            chunk_height = max(1, int(cell_size / self.downscale_factor))

            if self.downscale_factor > 1.0:
                direction = f"↓ Reducido {(1.0 - 1.0/self.downscale_factor)*100:.0f}%"
            elif self.downscale_factor < 1.0:
                direction = f"↑ Aumentado {(1.0/self.downscale_factor - 1.0)*100:.0f}%"
            else:
                direction = "= Sin cambio"

            self.downscale_info_label.setText(
                f"Resolución por chunk: {chunk_width}×{chunk_height} px {direction} "
                f"(Celda: {cell_size}×{cell_size} px)"
            )
        else:
            self.downscale_info_label.setText(
                "Resolución: Cargue una imagen y genere el grid primero"
            )

        # Si hay proyección activa, actualizar
        if self.projector_active and self.projection_window is not None:
            self._update_projection_with_downscale()


    def _update_projection_with_downscale(self):
        """Aplica el downscaling a la imagen proyectada."""
        if self.pattern is None:
            return

        # NO actualizar la proyección completa con downscaling
        # El downscaling se aplica individualmente a cada segmento en _apply_effects_to_segment
        # current_image = self._get_projection_image()
        # if current_image is not None and self.downscale_factor != 1.0:
        #     # Aplicar downscaling
        #     original_height, original_width = current_image.shape[:2]
        #     new_width = int(original_width * self.downscale_factor)
        #     new_height = int(original_height * self.downscale_factor)
        #
        #     if new_width > 0 and new_height > 0:
        #         import cv2
        #         downscaled_image = cv2.resize(
        #             current_image,
        #             (new_width, new_height),
        #             interpolation=cv2.INTER_AREA if self.downscale_factor < 1.0 else cv2.INTER_LINEAR
        #         )
        #         self.projection_window.update_image(downscaled_image)
        #     else:
        #         self.projection_window.update_image(current_image)


    def _get_projection_image(self):
        """Obtiene la imagen a proyectar, aplicando transformaciones y downscaling."""
        image = None

        if self.grid_view_active and self.image_on_grid is not None:
            image = self.image_on_grid
            # Aplicar transformaciones geométricas (rotación, espejos)
            if image is not None:
                image = self.apply_image_transforms(image)

            # Aplicar espejo de exposición si está activo
            if image is not None:
                import cv2
                if getattr(self, "exposure_mirror_h", False):
                    image = cv2.flip(image, 1)
                if getattr(self, "exposure_mirror_v", False):
                    image = cv2.flip(image, 0)
        elif hasattr(self, "pattern") and self.pattern is not None:
            image = self.pattern.copy()
            # Aplicar transformaciones geométricas (rotación, espejos)
            if hasattr(self, "apply_image_transforms"):
                image = self.apply_image_transforms(image)

            # Aplicar espejo de exposición si está activo
            import cv2
            if getattr(self, "exposure_mirror_h", False):
                image = cv2.flip(image, 1)
            if getattr(self, "exposure_mirror_v", False):
                image = cv2.flip(image, 0)

        # NOTA: El downscaling NO se aplica aquí a la imagen completa
        # Se aplica individualmente a cada CHUNK en _apply_effects_to_segment()
        # Esto mantiene la segmentación alineada con el grid

        return image


    def _get_final_projection_image(self):
        """
        Obtiene la imagen final proyectada con TODOS los efectos aplicados:
        - Sigma (gaussian filter)
        - Downscaling
        - Brillo
        - Matriz de atenuación (si está en grid)
        - Conversión binaria (si está activa)

        Esta es la imagen REAL que se proyecta y debe usarse para segmentación.
        """
        import numpy as np
        import cv2

        # Obtener imagen base
        base_image = self._get_projection_image()

        if base_image is None:
            return None

        # Crear copia para no modificar la original
        final_image = base_image.copy()

        # Aplicar brillo (normalizado 0-100 -> escala 0-1 para multiplicación)
        if self.brightness != 100:
            brightness_factor = self.brightness / 100.0
            final_image = np.clip(final_image * brightness_factor, 0, 255).astype(
                np.uint8
            )

        # Aplicar conversión binaria si está activa
        if self.binary_mode_enabled:
            # Convertir a escala de grises si es necesario
            if len(final_image.shape) == 3:
                gray_image = cv2.cvtColor(final_image, cv2.COLOR_BGR2GRAY)
            else:
                gray_image = final_image

            # Aplicar umbral binario
            final_image = np.where(gray_image >= self.binary_threshold, 255, 0).astype(
                np.uint8
            )

        # Aplicar inversión si está activa
        if self.invert_projection:
            final_image = 255 - final_image
        return final_image


    def update_sigma(self):
        self.sigma = self.sigma_slider.value()
        self.sigma_label.setText(f"Sigma (Desenfoque): {self.sigma:.1f}")

        # Actualizar visualización del grid si está activo
        if self.grid_view_active and self.image_on_grid is not None:
            self.quick_redraw_image()

        # Actualizar vista de imagen principal SOLO si NO estamos en vista de grid
        if not self.grid_view_active and self.pattern is not None:
            self.simulate_optics()


    def update_brightness(self):
        self.brightness = self.brightness_slider.value()
        self.brightness_label.setText(f"Brillo Proyección: {self.brightness}%")
        if self.projector_active and self.projection_window is not None:
            self.projection_window.set_brightness(self.brightness)

        # Actualizar visualización del grid si está activo
        if self.grid_view_active and self.image_on_grid is not None:
            self.quick_redraw_image()

        # Actualizar vista de imagen principal SOLO si NO estamos en vista de grid
        if not self.grid_view_active and self.pattern is not None:
            self.simulate_optics()


    def update_segmentation_mode(self, index):
        """Actualiza el modo de segmentación."""
        self.segmentation_mode = index

        # Mostrar/ocultar controles según el modo
        if index == 1:  # Manual
            self.manual_segments_widget.setVisible(True)
        else:
            self.manual_segments_widget.setVisible(False)

        self.update_segmentation_preview()


    def update_segmentation_preview(self):
        """Actualiza la información de vista previa de segmentación."""
        if self.segmentation_mode == 3:  # Imagen Completa
            self.segments_x = 1
            self.segments_y = 1
            self.segment_info_label.setText("Modo: Imagen Completa (1 segmento)")
        elif self.segmentation_mode == 0:  # Automático (usar grid)
            if (
                self.grid_view_active
                and hasattr(self, "grid_width")
                and self.grid_width > 0
            ):
                # Usar configuración del grid activo
                cells_x = int(self.grid_width / self.grid_cell_size)
                cells_y = int(self.grid_height / self.grid_cell_size)
                self.segments_x = cells_x
                self.segments_y = cells_y
            else:
                # Sin grid activo: usar división inteligente basada en la imagen
                if self.pattern is not None:
                    img_height, img_width = self.pattern.shape[:2]
                    # Usar chunks de tamaño razonable (~512px ideal para proyección)
                    optimal_chunk_size = 512
                    self.segments_x = max(1, img_width // optimal_chunk_size)
                    self.segments_y = max(1, img_height // optimal_chunk_size)
                    self.segment_info_label.setText(
                        f"Modo automático sin grid: {self.segments_x}×{self.segments_y} chunks (~{optimal_chunk_size}px)"
                    )
                else:
                    self.segment_info_label.setText(
                        "Cargue una imagen para calcular segmentación automática"
                    )
                    return
        elif self.segmentation_mode == 1:  # Manual
            self.segments_x = self.segments_x_spin.value()
            self.segments_y = self.segments_y_spin.value()

        total_blocks = self.segments_x * self.segments_y

        # Si ya se aplicó segmentación, mostrar segmentos reales (con contenido)
        if hasattr(self, "image_segments") and self.image_segments:
            actual_segments = len(self.image_segments)
            self.segment_info_label.setText(
                f"Segmentos con imagen: {actual_segments} de {total_blocks} bloques ({self.segments_x}x{self.segments_y})"
            )
        else:
            # Vista previa (antes de aplicar segmentación)
            self.segment_info_label.setText(
                f"Vista previa: {total_blocks} bloques máximo ({self.segments_x}x{self.segments_y})"
            )

        # Calcular tamaño por segmento si hay imagen cargada
        if self.pattern is not None:
            img_height, img_width = self.pattern.shape[:2]
            segment_width = img_width // self.segments_x
            segment_height = img_height // self.segments_y
            self.segment_size_label.setText(
                f"Tamaño por segmento: {segment_width}x{segment_height} px"
            )
        else:
            self.segment_size_label.setText("Tamaño por segmento: Cargue una imagen")


    def apply_image_segmentation(self):
        """
        Divide la imagen en segmentos según la configuración.

        SLICE ÚNICO: Se calcula un único corte automático basado en las coordenadas
        extremas del contenido de la imagen. Este corte es DETERMINISTA y se mantiene
        en caché mientras la imagen y la configuración del grid no cambien.

        NO se permite crear cortes sobre cortes - el único corte válido identifica
        exactamente los chunks donde la imagen está presente.
        """
        if self.pattern is None:
            QMessageBox.warning(
                self,
                "Sin imagen",
                "Cargue una imagen primero antes de aplicar segmentación.",
            )
            return

        try:
            import numpy as np

            # ═══════════════════════════════════════════════════════════════════
            # PASO 1: OBTENER IMAGEN CON TRANSFORMACIONES APLICADAS
            # ═══════════════════════════════════════════════════════════════════
            # Aplicar transformaciones geométricas (rotación, espejos) PRIMERO
            source_image = self.apply_image_transforms(self.pattern.copy())
            img_height, img_width = source_image.shape[:2]

            # Convertir a 0-255 si está normalizada (para visualización)
            if source_image.max() <= 1.0:
                visual_image = (source_image * 255).astype(np.uint8)
            else:
                visual_image = source_image.astype(np.uint8)

            # ═══════════════════════════════════════════════════════════════════
            # MODO DE SLICE: SOLO CELDA (Grid completo)
            # ═══════════════════════════════════════════════════════════════════
            # Usamos EXACTAMENTE las mismas celdas que ya están dibujadas en el grid
            if hasattr(self, "grid_width") and hasattr(self, "grid_cell_size"):
                # Calcular número de celdas del grid (igual a las que se dibujan)
                cells_x = int(self.grid_width / self.grid_cell_size)
                cells_y = int(self.grid_height / self.grid_cell_size)
                self.segments_x = cells_x
                self.segments_y = cells_y
                slice_type = f"CELDA (Grid {cells_x}×{cells_y})"
            else:
                # Sin grid, no se puede segmentar
                self.log_to_console("❌ ERROR: No hay grid configurado", "ERROR")
                return

            # Log de configuración con transformaciones
            transform_str = ""
            if self.image_rotation != 0 or self.image_mirror_h or self.image_mirror_v:
                parts = []
                if self.image_rotation != 0:
                    parts.append(f"Rot={self.image_rotation}°")
                if self.image_mirror_h:
                    parts.append("MirrorH")
                if self.image_mirror_v:
                    parts.append("MirrorV")
                transform_str = f" | Transformaciones: {', '.join(parts)}"

            self.log_to_console(
                f"🔧 MODO DE SLICE: {slice_type}\n"
                f"  • Divisiones: {self.segments_x}×{self.segments_y}{transform_str}",
                "INFO",
            )

            # === PASO 2: VERIFICAR CACHE (DETERMINISMO E IDEMPOTENCIA) ===
            # El cache garantiza que no se recalcule el slice si:
            # - La imagen es la misma (mismo ID de carga)
            # - La configuración del grid no cambió (segments_x, segments_y)
            # - Las transformaciones no cambiaron (rotación, espejos)
            # - La posición de la imagen no cambió
            # IDEMPOTENCIA: Aplicar dos veces con mismos parámetros = mismo resultado

            current_grid_config = (
                self.segments_x,
                self.segments_y,
                self.image_rotation,
                self.image_mirror_h,
                self.image_mirror_v,
            )
            current_image_position = (
                tuple(self.image_position)
                if hasattr(self, "image_position")
                else (0.0, 0.0)
            )
            current_pattern_id = getattr(self, "_pattern_load_id", None)

            use_cache = False
            cells_with_content = []  # Inicializar lista de celdas con contenido

            if (
                current_pattern_id is not None
                and hasattr(self, "_last_segmentation_pattern_id")
                and self._last_segmentation_pattern_id == current_pattern_id
                and self._last_segmentation_grid_config == current_grid_config
                and self._last_segmentation_bounds is not None
                and hasattr(self, "_last_image_position")
                and self._last_image_position == current_image_position
                and hasattr(self, "_last_cells_with_content")
            ):
                use_cache = True
                image_bounds = self._last_segmentation_bounds
                cells_with_content = (
                    self._last_cells_with_content
                )  # Restaurar lista de celdas
                self.log_to_console(
                    "✓✓✓ USANDO SLICE EN CACHÉ (IDEMPOTENCIA)\n"
                    "    La operación es idempotente - mismo resultado sin reprocesar",
                    "SUCCESS",
                )
            else:
                # Explicar por qué se recalcula
                if (
                    not hasattr(self, "_last_segmentation_pattern_id")
                    or self._last_segmentation_pattern_id != current_pattern_id
                ):
                    reason = "imagen diferente cargada"
                elif self._last_segmentation_grid_config != current_grid_config:
                    reason = f"configuración cambió de {self._last_segmentation_grid_config} a {current_grid_config}"
                elif (
                    hasattr(self, "_last_image_position")
                    and self._last_image_position != current_image_position
                ):
                    reason = f"posición cambió de {self._last_image_position} a {current_image_position}"
                else:
                    reason = "primer cálculo"

                self.log_to_console(
                    f"⚙️ CALCULANDO SLICE ÚNICO: {reason}\n"
                    f"    Imagen: {img_width}×{img_height} px | Grid: {self.segments_x}×{self.segments_y}",
                    "SEGMENTATION",
                )

                # ═══════════════════════════════════════════════════════════════════
                # CALCULAR CELDAS QUE INTERSECTAN CON LA IMAGEN
                # ═══════════════════════════════════════════════════════════════════

                image_bounds = None
                cells_with_content = []

                # La imagen está colocada en el grid
                # Necesitamos calcular qué celdas DEL GRID ocupa la imagen
                # La imagen tiene dimensiones img_width × img_height en PÍXELES
                # Cada celda del grid tiene grid_pixels_per_cell píxeles

                if hasattr(self, "grid_pixels_per_cell"):
                    # Calcular cuántas celdas del grid ocupa la imagen
                    cells_occupied_x = int(
                        np.ceil(img_width / self.grid_pixels_per_cell)
                    )
                    cells_occupied_y = int(
                        np.ceil(img_height / self.grid_pixels_per_cell)
                    )

                    # Las celdas que ocupa la imagen van desde (0,0) hasta (cells_occupied_x-1, cells_occupied_y-1)
                    start_cell_x = 0
                    start_cell_y = 0
                    end_cell_x = min(cells_occupied_x - 1, self.segments_x - 1)
                    end_cell_y = min(cells_occupied_y - 1, self.segments_y - 1)

                    for row in range(start_cell_y, end_cell_y + 1):
                        for col in range(start_cell_x, end_cell_x + 1):
                            cells_with_content.append((row, col))
                else:
                    # Fallback: usar toda la imagen
                    start_cell_x = 0
                    start_cell_y = 0
                    end_cell_x = self.segments_x - 1
                    end_cell_y = self.segments_y - 1

                    for row in range(start_cell_y, end_cell_y + 1):
                        for col in range(start_cell_x, end_cell_x + 1):
                            cells_with_content.append((row, col))

                # El bounding box es simplemente todo el grid que cubre la imagen
                image_bounds = {
                    "start_x": start_cell_x,
                    "start_y": start_cell_y,
                    "end_x": end_cell_x,
                    "end_y": end_cell_y,
                }

                self.log_to_console(
                    f"📊 Cálculo de cobertura de imagen:\n"
                    f"  • Grid total: {self.segments_x}×{self.segments_y} = {self.segments_x * self.segments_y} celdas\n"
                    f"  • Imagen ocupa: {len(cells_with_content)} celdas",
                    "INFO",
                )

                # DEBUG: Mostrar las primeras 10 celdas
                if len(cells_with_content) > 0:
                    preview_cells = cells_with_content[
                        : min(10, len(cells_with_content))
                    ]
                    cells_str = ", ".join([f"[{r},{c}]" for r, c in preview_cells])
                    suffix = "..." if len(cells_with_content) > 10 else ""
                    self.log_to_console(
                        f"  • Primeras celdas: {cells_str}{suffix}", "INFO"
                    )

                # ═══════════════════════════════════════════════════════════════════
                # ACTUALIZAR CACHE - GARANTIZAR IDEMPOTENCIA
                # ═══════════════════════════════════════════════════════════════════
                self._last_segmentation_pattern_id = current_pattern_id
                self._last_segmentation_grid_config = current_grid_config
                self._last_segmentation_bounds = image_bounds
                self._last_image_position = current_image_position
                self._last_cells_with_content = cells_with_content

                chunks_in_slice = (end_cell_x - start_cell_x + 1) * (
                    end_cell_y - start_cell_y + 1
                )
                self.log_to_console(
                    f"✓ SLICE CALCULADO:\n"
                    f"  • Rango X: celdas {start_cell_x} → {end_cell_x} ({end_cell_x - start_cell_x + 1} celdas)\n"
                    f"  • Rango Y: celdas {start_cell_y} → {end_cell_y} ({end_cell_y - start_cell_y + 1} celdas)\n"
                    f"  • Total chunks: {chunks_in_slice}",
                    "SUCCESS",
                )

            # ═══════════════════════════════════════════════════════════════════
            # CALCULAR TAMAÑO DE CADA CHUNK (basado en celdas del grid)
            # ═══════════════════════════════════════════════════════════════════════
            # Usar el tamaño de las celdas del grid
            # Cada chunk debe tener el tamaño de una celda del grid (en píxeles)
            if hasattr(self, "grid_pixels_per_cell"):
                cell_width = float(self.grid_pixels_per_cell)
                cell_height = float(self.grid_pixels_per_cell)
            else:
                # Fallback: dividir la imagen uniformemente
                cell_width = img_width / self.segments_x
                cell_height = img_height / self.segments_y

            if image_bounds is not None:
                slice_width_cells = image_bounds["end_x"] - image_bounds["start_x"] + 1
                slice_height_cells = image_bounds["end_y"] - image_bounds["start_y"] + 1

                self.log_to_console(
                    f"📐 Configuración chunks:\n"
                    f"  • Tamaño celda: {cell_width:.1f}×{cell_height:.1f} px\n"
                    f"  • Área slice: {slice_width_cells}×{slice_height_cells} celdas\n"
                    f"  • Grid total: {self.segments_x}×{self.segments_y}",
                    "INFO",
                )

            # ═══════════════════════════════════════════════════════════════════
            # CREAR CHUNKS SOLO PARA LAS CELDAS CON CONTENIDO DETECTADO
            # ═══════════════════════════════════════════════════════════════════
            # IMPORTANTE: No crear chunks para todo el bounding box
            # Solo crear chunks para las celdas específicas en cells_with_content
            self.image_segments = []
            segment_id = 0
            total_blocks = self.segments_x * self.segments_y
            empty_blocks = 0
            skipped_outside_image = 0

            # Convertir lista de celdas con contenido a set para búsqueda rápida
            content_cells_set = (
                set(cells_with_content) if "cells_with_content" in locals() else set()
            )

            for row in range(self.segments_y):
                for col in range(self.segments_x):

                    # ═══════════════════════════════════════════════════════════════════
                    # SOLO PROCESAR CELDAS QUE FUERON DETECTADAS CON CONTENIDO
                    # ═══════════════════════════════════════════════════════════════════
                    if (row, col) not in content_cells_set:
                        skipped_outside_image += 1
                        continue

                    # ═══════════════════════════════════════════════════════════════════
                    # CALCULAR COORDENADAS DE LA CELDA EN EL GRID
                    # ═══════════════════════════════════════════════════════════════════
                    x_start = int(col * cell_width)
                    y_start = int(row * cell_height)
                    x_end = int(min((col + 1) * cell_width, img_width))
                    y_end = int(min((row + 1) * cell_height, img_height))

                    # ═══════════════════════════════════════════════════════════════════
                    # EXTRAER SEGMENTO Y RELLENAR A TAMAÑO COMPLETO DE CELDA
                    # ═══════════════════════════════════════════════════════════════════
                    # IMPORTANTE: Todos los chunks deben tener el MISMO tamaño
                    # Si es modo CELDA: todos deben ser cell_width × cell_height (ej: 100×100)
                    # Si hay partes vacías, rellenar con negro para mantener consistencia

                    # Extraer la parte de la imagen que intersecta con esta celda
                    segment_from_image = source_image[
                        y_start:y_end, x_start:x_end
                    ].copy()

                    # Crear un chunk del tamaño completo de la celda (rellenado con negro)
                    chunk_width = int(cell_width)
                    chunk_height = int(cell_height)

                    # Crear chunk vacío (negro) del tamaño de la celda
                    if len(source_image.shape) == 3:
                        segment = np.zeros(
                            (chunk_height, chunk_width, source_image.shape[2]),
                            dtype=source_image.dtype,
                        )
                    else:
                        segment = np.zeros(
                            (chunk_height, chunk_width), dtype=source_image.dtype
                        )

                    # Copiar la parte de imagen que tenemos al chunk
                    actual_height = segment_from_image.shape[0]
                    actual_width = segment_from_image.shape[1]
                    segment[0:actual_height, 0:actual_width] = segment_from_image

                    # ═══════════════════════════════════════════════════════════════════
                    # CREAR CHUNK CON TAMAÑO CONSISTENTE
                    # ═══════════════════════════════════════════════════════════════════
                    # Todos los chunks tienen el mismo tamaño (cell_width × cell_height)
                    # Esto garantiza consistencia en la proyección
                    if segment.size > 0:
                        chunk_info = {
                            "id": segment_id,
                            "row": row,
                            "col": col,
                            "image": segment,  # Tamaño completo de celda (con relleno negro si es necesario)
                            "x_start": x_start,
                            "y_start": y_start,
                            "x_end": x_start
                            + chunk_width,  # Usar tamaño completo de celda
                            "y_end": y_start
                            + chunk_height,  # Usar tamaño completo de celda
                            "width": chunk_width,  # Siempre el tamaño completo de la celda
                            "height": chunk_height,  # Siempre el tamaño completo de la celda
                            "effects_applied": False,
                        }
                        self.image_segments.append(chunk_info)

                        # DEBUG: Log primeros 5 chunks extraídos
                        if segment_id < 5:
                            self.log_to_console(
                                f"  🔹 Chunk #{segment_id} [fila={row}, col={col}]: "
                                f"coords=({x_start},{y_start})-({x_end},{y_end}), "
                                f"size={x_end-x_start}×{y_end-y_start}px, "
                                f"values=[{segment.min():.2f}, {segment.max():.2f}]",
                                "INFO",
                            )

                        segment_id += 1
                    else:
                        empty_blocks += 1

            # Actualizar información
            self.update_segmentation_preview()

            # Actualizar grid con overlay PRESERVANDO el zoom
            if (
                self.show_segments_overlay
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

            segments_with_content = len(self.image_segments)

            # ═══════════════════════════════════════════════════════════════════
            # CALCULAR INFORMACIÓN DETALLADA DEL SLICE Y PROYECCIÓN
            # ═══════════════════════════════════════════════════════════════════

            # Información del slice
            if image_bounds is not None:
                slice_info = (
                    f"\n🔲 SLICE ÚNICO ACTIVO:\n"
                    f"  • Rango X: [{image_bounds['start_x']} → {image_bounds['end_x']}]\n"
                    f"  • Rango Y: [{image_bounds['start_y']} → {image_bounds['end_y']}]\n"
                    f"  • Dimensiones: {image_bounds['end_x'] - image_bounds['start_x'] + 1} × "
                    f"{image_bounds['end_y'] - image_bounds['start_y'] + 1} celdas\n"
                )
            else:
                slice_info = ""

            # Calcular tamaño promedio de chunks y resolución en proyección
            if segments_with_content > 0:
                # Tamaños de chunks
                chunk_widths = [seg["width"] for seg in self.image_segments]
                chunk_heights = [seg["height"] for seg in self.image_segments]
                avg_chunk_width = sum(chunk_widths) / len(chunk_widths)
                avg_chunk_height = sum(chunk_heights) / len(chunk_heights)
                min_chunk_width = min(chunk_widths)
                max_chunk_width = max(chunk_widths)
                min_chunk_height = min(chunk_heights)
                max_chunk_height = max(chunk_heights)

                # Calcular resolución de proyección (si hay proyector activo)
                projection_info = ""
                if self.projector_active and self.projection_window is not None:
                    screen_width = self.projection_window.screen_geometry.width()
                    screen_height = self.projection_window.screen_geometry.height()

                    # Calcular factor de escala para chunk promedio
                    scale_x = screen_width / avg_chunk_width
                    scale_y = screen_height / avg_chunk_height
                    scale_factor = min(scale_x, scale_y)

                    projected_width = int(avg_chunk_width * scale_factor)
                    projected_height = int(avg_chunk_height * scale_factor)

                    projection_info = (
                        f"\n🖥️ RESOLUCIÓN EN PROYECCIÓN:\n"
                        f"  • Monitor: {screen_width}×{screen_height} px\n"
                        f"  • Chunk promedio: {avg_chunk_width:.1f}×{avg_chunk_height:.1f} px\n"
                        f"  • Proyectado como: {projected_width}×{projected_height} px\n"
                        f"  • Factor de escala: {scale_factor:.2f}×\n"
                    )

                chunk_size_info = (
                    f"\n📏 CARACTERÍSTICAS DE LOS CHUNKS:\n"
                    f"  • Tamaño promedio: {avg_chunk_width:.1f}×{avg_chunk_height:.1f} px\n"
                    f"  • Rango ancho: {min_chunk_width}-{max_chunk_width} px\n"
                    f"  • Rango alto: {min_chunk_height}-{max_chunk_height} px\n"
                )
            else:
                chunk_size_info = ""
                projection_info = ""

            # Información de transformaciones
            transform_info = ""
            if self.image_rotation != 0 or self.image_mirror_h or self.image_mirror_v:
                transforms = []
                if self.image_rotation != 0:
                    transforms.append(f"Rotación {self.image_rotation}°")
                if self.image_mirror_h:
                    transforms.append("Espejo H")
                if self.image_mirror_v:
                    transforms.append("Espejo V")
                transform_info = f"\n🔄 TRANSFORMACIONES: {', '.join(transforms)}\n"

            cache_status = (
                "✓ Reutilizado desde caché" if use_cache else "⚙️ Recién calculado"
            )

            QMessageBox.information(
                self,
                "✓ Segmentación Completada",
                f"SISTEMA DE SLICE POR CELDA (Grid)\n"
                f"Estado: {cache_status}\n"
                f"{transform_info}"
                f"{slice_info}"
                f"{chunk_size_info}"
                f"{projection_info}\n"
                f"📊 ESTADÍSTICAS:\n"
                f"  • Grid configurado: {self.segments_x}×{self.segments_y} = {total_blocks} divisiones\n"
                f"  • Chunks activos (con contenido): {segments_with_content}\n"
                f"  • Chunks fuera del slice: {skipped_outside_image}\n"
                f"  • Chunks vacíos (dentro del slice): {empty_blocks}\n\n"
                f"✓ Los chunks se proyectarán en orden secuencial\n"
                f"✓ Cada chunk se escalará al máximo tamaño posible\n"
                f"✓ El slice es DETERMINISTA y se mantendrá mientras\n"
                f"   no cambie la imagen, su posición o el grid",
            )

        except Exception as e:
            QMessageBox.critical(self, "Error", f"Error al segmentar imagen: {str(e)}")


    def toggle_segments_overlay(self, state):
        """Activa/desactiva el overlay visual de segmentos en el grid."""
        self.show_segments_overlay = bool(state)
        if (
            self.grid_view_active
            and hasattr(self, "grid_generated")
            and self.grid_generated
        ):
            # Guardar límites actuales del zoom
            if hasattr(self, "ax") and self.ax is not None:
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

