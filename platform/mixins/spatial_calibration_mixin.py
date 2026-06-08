"""
mixin: herramienta de calibración espacial para establecer mm/píxel.
"""
from PyQt5.QtWidgets import QInputDialog, QMessageBox, QDialog
from PyQt5.QtCore import Qt
import math
import json
import os
from constants import CONFIG_FILE

class SpatialCalibrationMixin:
    """maneja la lógica de calibración espacial de la imagen (píxel a mm)."""

    def _init_spatial_calibration(self):
        """inicializa variables de estado de la calibración espacial."""
        self.mm_per_pixel = None
        
        # cargar escala guardada si existe
        self._load_spatial_scale()

    def toggle_spatial_calibration_mode(self):
        """Abre la ventana dedicada de calibración espacial."""
        # Le pasamos la imagen original o la que está en grid
        img_to_calib = getattr(self, "pattern", getattr(self, "image_on_grid", None))
        
        if img_to_calib is None:
            import cv2
            from PyQt5.QtWidgets import QFileDialog
            file_path, _ = QFileDialog.getOpenFileName(
                self, "Seleccionar imagen de referencia para calibrar", "", "Imágenes (*.png *.jpg *.bmp *.tiff *.svg)"
            )
            if file_path:
                img_to_calib = cv2.imread(file_path, cv2.IMREAD_GRAYSCALE)
                img_to_calib = img_to_calib / 255.0
            else:
                self.log_to_console("debe cargar una imagen de referencia para calibrar.", "warning")
                return
        
        from UI.dialogs.spatial_calibration_dialog import SpatialCalibrationDialog
        dialog = SpatialCalibrationDialog(self, img_to_calib)
        if dialog.exec_() == QDialog.Accepted:
            if dialog.mm_per_pixel is not None:
                self.mm_per_pixel = dialog.mm_per_pixel
                self.log_to_console(f"calibración guardada: {self.mm_per_pixel:.5f} mm/px", "success")
                self._save_spatial_scale()
                self.update_spatial_labels()
            else:
                self.log_to_console("calibración inválida, no se guardó.", "warning")
        else:
            self.log_to_console("calibración cancelada por el usuario.", "info")

    def update_spatial_labels(self):
        """actualiza el panel derecho con el tamaño físico de la imagen si está calibrada."""
        if not hasattr(self, "pixel_scale_label") or not hasattr(self, "image_physical_size_label"):
            return
            
        if self.mm_per_pixel is None:
            self.pixel_scale_label.setText("escala: no calibrada")
            self.image_physical_size_label.setText("tamaño físico: -")
            return
            
        self.pixel_scale_label.setText(f"escala: {self.mm_per_pixel:.5f} mm/px")
        
        if hasattr(self, "image_on_grid") and self.image_on_grid is not None:
            h, w = self.image_on_grid.shape[:2]
            width_mm = w * self.mm_per_pixel
            height_mm = h * self.mm_per_pixel
            self.image_physical_size_label.setText(f"tamaño físico: {width_mm:.2f} x {height_mm:.2f} mm")
        else:
            self.image_physical_size_label.setText("tamaño físico: -")

    def _save_spatial_scale(self):
        """guarda la escala en config_file (file_structure.json o análogo)."""
        if self.mm_per_pixel is None:
            return
        config = {}
        if os.path.exists(CONFIG_FILE):
            try:
                with open(CONFIG_FILE, 'r', encoding='utf-8') as f:
                    config = json.load(f)
            except:
                pass
        config['mm_per_pixel'] = self.mm_per_pixel
        try:
            with open(CONFIG_FILE, 'w', encoding='utf-8') as f:
                json.dump(config, f, indent=4)
        except Exception as e:
            print(f"error guardando calibración espacial: {e}")

    def _load_spatial_scale(self):
        """carga la escala desde el archivo si existe."""
        if os.path.exists(CONFIG_FILE):
            try:
                with open(CONFIG_FILE, 'r', encoding='utf-8') as f:
                    config = json.load(f)
                    if 'mm_per_pixel' in config:
                        self.mm_per_pixel = float(config['mm_per_pixel'])
            except:
                pass
