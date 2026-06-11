"""
Mixin de gestion de archivos.

Sistema de cache, arbol de archivos, carga/guardado de imagenes
y patrones, drag & drop y thumbnails.
"""
import os
import sys
import json
import cv2
import numpy as np
import ctypes

from PyQt5.QtWidgets import (
    QInputDialog, QFileDialog, QMessageBox, QMenu,
    QTreeWidgetItem, QTreeWidgetItemIterator,
)
from PyQt5.QtCore import Qt
from PyQt5.QtGui import QDragEnterEvent, QDropEvent, QIcon, QPixmap, QImage


class FileManagementMixin:
    """Mixin: FileManagement functionality."""

    def create_input_dialog(self, title, label, text=""):
        dialog = QInputDialog(self)
        dialog.setWindowTitle(title)
        dialog.setLabelText(label)
        dialog.setTextValue(text)
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

        return dialog


    def init_cache_system(self):
        if not os.path.exists(self.cache_dir):
            os.makedirs(self.cache_dir)

        if not os.path.exists(self.config_file):
            with open(self.config_file, "w") as f:
                json.dump({"folders": {}}, f)


    def load_grid_config(self):
        default_config = {
            "width": 10,
            "height": 10,
            "cell_size": 1,
            "pixels_per_cell": 100,
            "unit": "mm",
            "color": "#00FF00",
            "pixel_grid_color": "#FF00FF",
            "show_pixel_grid": False,
            "apply_effects_to_grid": False,
            "binary_mode_enabled": False,
            "binary_threshold": 50.0,
            "invert_projection": False,
        }

        self.grid_generated = False

        if os.path.exists(self.grid_config_file):
            try:
                with open(self.grid_config_file, "r") as f:
                    config = json.load(f)
                    self.grid_width = config.get("width", default_config["width"])
                    self.grid_height = config.get("height", default_config["height"])
                    self.grid_cell_size = config.get(
                        "cell_size", default_config["cell_size"]
                    )
                    self.grid_pixels_per_cell = config.get(
                        "pixels_per_cell", default_config["pixels_per_cell"]
                    )
                    self.grid_unit = config.get("unit", default_config["unit"])
                    self.grid_color = config.get("color", default_config["color"])
                    self.grid_pixel_color = config.get(
                        "pixel_grid_color", default_config["pixel_grid_color"]
                    )
                    self.show_pixel_grid = config.get(
                        "show_pixel_grid", default_config["show_pixel_grid"]
                    )
                    self.apply_effects_to_grid = config.get(
                        "apply_effects_to_grid", default_config["apply_effects_to_grid"]
                    )

                    # Cargar configuración binaria
                    self.binary_mode_enabled = config.get(
                        "binary_mode_enabled", default_config["binary_mode_enabled"]
                    )
                    self.binary_threshold = config.get(
                        "binary_threshold", default_config["binary_threshold"]
                    )
                    self.invert_projection = config.get(
                        "invert_projection", default_config["invert_projection"]
                    )

                    self.grid_generated = True
            except:
                self.grid_width = default_config["width"]
                self.grid_height = default_config["height"]
                self.grid_cell_size = default_config["cell_size"]
                self.grid_pixels_per_cell = default_config["pixels_per_cell"]
                self.grid_unit = default_config["unit"]
                self.grid_color = default_config["color"]
                self.grid_pixel_color = default_config["pixel_grid_color"]
                self.show_pixel_grid = default_config["show_pixel_grid"]
                self.apply_effects_to_grid = default_config["apply_effects_to_grid"]

                # Cargar defaults binarios
                self.binary_mode_enabled = default_config["binary_mode_enabled"]
                self.binary_threshold = default_config["binary_threshold"]
                self.invert_projection = default_config["invert_projection"]
        else:
            self.grid_width = default_config["width"]
            self.grid_height = default_config["height"]
            self.grid_cell_size = default_config["cell_size"]
            self.grid_pixels_per_cell = default_config["pixels_per_cell"]
            self.grid_unit = default_config["unit"]
            self.grid_color = default_config["color"]
            self.grid_pixel_color = default_config["pixel_grid_color"]
            self.show_pixel_grid = default_config["show_pixel_grid"]
            self.apply_effects_to_grid = default_config["apply_effects_to_grid"]

            # Cargar defaults binarios
            self.binary_mode_enabled = default_config["binary_mode_enabled"]
            self.binary_threshold = default_config["binary_threshold"]
            self.invert_projection = default_config["invert_projection"]


    def save_grid_config(self):
        config = {
            "width": self.grid_width,
            "height": self.grid_height,
            "cell_size": self.grid_cell_size,
            "pixels_per_cell": self.grid_pixels_per_cell,
            "unit": self.grid_unit,
            "color": self.grid_color,
            "pixel_grid_color": self.grid_pixel_color,
            "show_pixel_grid": self.show_pixel_grid,
            "apply_effects_to_grid": self.apply_effects_to_grid,
            "binary_mode_enabled": self.binary_mode_enabled,
            "binary_threshold": self.binary_threshold,
            "invert_projection": self.invert_projection,
        }

        try:
            with open(self.grid_config_file, "w") as f:
                json.dump(config, f, indent=2)
        except Exception as e:
            print(f"Error al guardar configuración del grid: {e}")


    
    def _load_image_as_numpy(self, file_path):
        import numpy as np
        if file_path.lower().endswith('.svg'):
            from PyQt5.QtSvg import QSvgRenderer
            from PyQt5.QtGui import QPainter, QImage
            
            renderer = QSvgRenderer(file_path)
            default_size = renderer.defaultSize()
            width = default_size.width()
            height = default_size.height()
            
            if width <= 0 or height <= 0:
                width = 1024
                height = 1024
            
            # Scale up small SVGs to prevent pixelation loss
            if width < 512 and height < 512:
                scale = 512 / max(width, height)
                width = int(width * scale)
                height = int(height * scale)
                
            image = QImage(width, height, QImage.Format_ARGB32)
            image.fill(0xFFFFFFFF)  # Fill white
            
            painter = QPainter(image)
            renderer.render(painter)
            painter.end()
            
            image = image.convertToFormat(QImage.Format_Grayscale8)
            ptr = image.bits()
            ptr.setsize(image.height() * image.width())
            arr = np.array(ptr).reshape(image.height(), image.width())
            return arr.copy() / 255.0
        else:
            import cv2
            img = cv2.imread(file_path, cv2.IMREAD_GRAYSCALE)
            if img is None: return None
            return img / 255.0


    def dragEnterEvent(self, event: QDragEnterEvent):
        if event.mimeData().hasUrls():
            event.acceptProposedAction()


    def dropEvent(self, event: QDropEvent):
        urls = event.mimeData().urls()
        if urls:
            file_path = urls[0].toLocalFile()
            if file_path.lower().endswith((".png", ".jpg", ".jpeg", ".bmp", ".tiff", ".svg")):
                if self.pattern is not None:
                    reply = QMessageBox.question(
                        self,
                        "Reemplazar imagen",
                        "¿Desea reemplazar la imagen actual?",
                        QMessageBox.Yes | QMessageBox.No,
                        QMessageBox.No,
                    )
                    if reply == QMessageBox.No:
                        return

                image = cv2.imread(file_path, cv2.IMREAD_GRAYSCALE)
                self.pattern = image / 255.0
                
                if getattr(self, "grid_view_active", False): self.toggle_grid_view()
                if getattr(self, "calibration_view_active", False): self.toggle_calibration_view()
                if getattr(self, "_ruler_scale_view_active", False): self.toggle_ruler_scale_view()
                if getattr(self, "_pattern_calib_view_active", False): self.toggle_pattern_calibration_view()
                
                self.simulate_optics()
                self._refresh_invert_button_state()


    def load_pattern(self, file_path=None):
        if not file_path:
            file_path, _ = QFileDialog.getOpenFileName(
                self, "Seleccionar patrón", "", "Imágenes y Vectores (*.png *.jpg *.bmp *.tiff *.svg *.dxf)"
            )
        if file_path:
            if self.pattern is not None:
                reply = QMessageBox.question(
                    self,
                    "Reemplazar imagen",
                    "¿Desea reemplazar la imagen actual?",
                    QMessageBox.Yes | QMessageBox.No,
                    QMessageBox.No,
                )
                if reply == QMessageBox.No:
                    return

            ext = os.path.splitext(file_path)[1].lower()
            if ext in ['.svg', '.dxf']:
                image = self._load_vector_as_raster(file_path)
                if image is None:
                    self.log_to_console(f"Error al cargar archivo vectorial: {file_path}", "error")
                    return
            else:
                image = cv2.imread(file_path, cv2.IMREAD_GRAYSCALE)
                
            if image is None:
                self.log_to_console(f"No se pudo cargar la imagen: {file_path}", "error")
                return
                
            self.pattern = image / 255.0

            # Asignar ID único a la imagen para cache determinista
            import time

            self._pattern_load_id = f"{file_path}_{time.time()}"

            # Limpiar cache de segmentación cuando se carga nueva imagen
            self._last_segmentation_pattern_hash = None
            self._last_segmentation_bounds = None
            self._last_segmentation_grid_config = None
            self._last_image_position = None

            if getattr(self, "grid_view_active", False): self.toggle_grid_view()
            if getattr(self, "calibration_view_active", False): self.toggle_calibration_view()
            if getattr(self, "_ruler_scale_view_active", False): self.toggle_ruler_scale_view()
            if getattr(self, "_pattern_calib_view_active", False): self.toggle_pattern_calibration_view()

            self.simulate_optics()
            self.projector_button.setVisible(True)
            if hasattr(self, "update_projector_button"):
                self.update_projector_button()
            if hasattr(self, "update_spatial_labels"):
                self.update_spatial_labels()

    def _load_vector_as_raster(self, file_path):
        """Convierte SVG y DXF a numpy array (escala de grises) con resolución alta."""
        ext = os.path.splitext(file_path)[1].lower()
        
        if ext == '.svg':
            try:
                import fitz
                doc = fitz.open(file_path)
                page = doc.load_page(0)
                # Escalar para tener una buena resolución (aprox 4000px max)
                rect = page.rect
                max_dim = max(rect.width, rect.height)
                zoom = 4000.0 / max_dim if max_dim > 0 else 10.0
                mat = fitz.Matrix(zoom, zoom)
                
                pix = page.get_pixmap(matrix=mat, alpha=False, colorspace="gray")
                img = np.frombuffer(pix.samples, dtype=np.uint8).reshape(pix.height, pix.width)
                # Invertir la imagen porque SVG usualmente es negro sobre transparente/blanco
                # Queremos que la geometría proyectada sea blanca sobre negro por defecto
                img = 255 - img
                return img
            except Exception as e:
                self.log_to_console(f"Error parseando SVG: {e}", "error")
                return None
                
        elif ext == '.dxf':
            try:
                import ezdxf
                from ezdxf.addons.drawing.matplotlib import qsave
                from ezdxf.addons.drawing.config import Configuration, ColorPolicy, BackgroundPolicy
                import tempfile
                
                doc = ezdxf.readfile(file_path)
                msp = doc.modelspace()
                
                # Configurar para que las líneas sean blancas y el fondo negro
                # Usamos COLOR para que el fondo negro persista, o BLACK si todo es negro, 
                # Pero MONOCHROME_DARK_BG dibujará líneas blancas con fondo negro correctamente.
                cfg = Configuration(
                    color_policy=ColorPolicy.MONOCHROME_DARK_BG,
                    background_policy=BackgroundPolicy.CUSTOM,
                    lineweight_scaling=2.0
                )
                
                # Guardar en un archivo temporal de alta resolución
                with tempfile.NamedTemporaryFile(suffix='.png', delete=False) as tmp:
                    tmp_path = tmp.name
                    
                try:
                    # dpi=400 da buena resolución sin exceder la memoria
                    qsave(msp, tmp_path, bg='#000000', fg='#FFFFFF', dpi=400, config=cfg)
                    # Cargar con OpenCV
                    img_color = cv2.imread(tmp_path)
                    img_gray = cv2.cvtColor(img_color, cv2.COLOR_BGR2GRAY)
                finally:
                    if os.path.exists(tmp_path):
                        os.remove(tmp_path)
                
                return img_gray
            except Exception as e:
                self.log_to_console(f"Error parseando DXF: {e}", "error")
                return None
        return None

    def save_image(self):
        if not hasattr(self, "last_intensity"):
            QMessageBox.warning(
                self, "Advertencia", "No hay imagen procesada para guardar"
            )
            return

        folders = self.get_folders_list()
        folder, ok = QInputDialog.getItem(
            self,
            "Seleccionar carpeta",
            "Carpeta destino:",
            folders + ["[Nueva carpeta]"],
            0,
            False,
        )

        if not ok:
            return

        if folder == "[Nueva carpeta]":
            dialog = self.create_input_dialog("Nueva carpeta", "Nombre de la carpeta:")
            if dialog.exec_() == QInputDialog.Accepted:
                folder = dialog.textValue()
                if not folder:
                    return
                self.create_folder(folder)
            else:
                return

        dialog = self.create_input_dialog("Guardar imagen", "Nombre del archivo:")

        if dialog.exec_() != QInputDialog.Accepted:
            return

        filename = dialog.textValue()

        if not filename or filename.strip() == "":
            from datetime import datetime

            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"imagen_{timestamp}"

        fmt = self.format_combo.currentText().lower()
        filepath = os.path.join(self.cache_dir, folder, f"{filename}.{fmt}")

        os.makedirs(os.path.dirname(filepath), exist_ok=True)

        img_to_save = (self.last_intensity * 255 / self.last_intensity.max()).astype(
            np.uint8
        )
        cv2.imwrite(filepath, img_to_save)

        self.update_file_tree_preserve_state()

        QMessageBox.information(self, "Éxito", f"Imagen guardada en:\n{filepath}")


    def create_folder(self, folder_name, parent=""):
        folder_path = os.path.join(self.cache_dir, parent, folder_name)
        os.makedirs(folder_path, exist_ok=True)


    def get_folders_list(self):
        folders = [""]
        for root, dirs, files in os.walk(self.cache_dir):
            for d in dirs:
                rel_path = os.path.relpath(os.path.join(root, d), self.cache_dir)
                folders.append(rel_path)
        return folders


    def update_file_tree(self):
        self.file_tree.clear()
        self.populate_tree(self.cache_dir, self.file_tree.invisibleRootItem())


    def update_file_tree_preserve_state(self):
        expanded_items = []
        iterator = QTreeWidgetItemIterator(self.file_tree)
        while iterator.value():
            item = iterator.value()
            if item.isExpanded():
                expanded_items.append(item.text(0))
            iterator += 1

        self.update_file_tree()

        iterator = QTreeWidgetItemIterator(self.file_tree)
        while iterator.value():
            item = iterator.value()
            if item.text(0) in expanded_items:
                item.setExpanded(True)
            iterator += 1


    def populate_tree(self, path, parent_item):
        try:
            items = sorted(os.listdir(path))
        except PermissionError:
            return

        for item in items:
            if item == "file_structure.json":
                continue

            item_path = os.path.join(path, item)
            tree_item = QTreeWidgetItem(parent_item, [item])
            tree_item.setData(0, Qt.UserRole, item_path)

            if os.path.isdir(item_path):
                tree_item.setIcon(0, self.style().standardIcon(self.style().SP_DirIcon))
                self.populate_tree(item_path, tree_item)
            else:
                if item.lower().endswith((".png", ".jpg", ".jpeg", ".bmp", ".tiff", ".svg")):
                    thumbnail = self.create_thumbnail(item_path, size=56)
                    if thumbnail:
                        tree_item.setIcon(0, QIcon(thumbnail))
                else:
                    tree_item.setIcon(
                        0, self.style().standardIcon(self.style().SP_FileIcon)
                    )


    def create_thumbnail(self, image_path, size=56):
        try:
            
            if image_path.lower().endswith('.svg'):
                from PyQt5.QtSvg import QSvgRenderer
                from PyQt5.QtGui import QPainter
                from PyQt5.QtCore import Qt, QRectF
                renderer = QSvgRenderer(image_path)
                image = QImage(size, size, QImage.Format_ARGB32)
                image.fill(0x00000000)
                painter = QPainter(image)
                ds = renderer.defaultSize()
                if ds.width() > 0 and ds.height() > 0:
                    scaled = ds.scaled(size, size, Qt.KeepAspectRatio)
                    x = (size - scaled.width()) / 2
                    y = (size - scaled.height()) / 2
                    renderer.render(painter, QRectF(x, y, scaled.width(), scaled.height()))
                else:
                    renderer.render(painter)
                painter.end()
                return QPixmap.fromImage(image)
            
            img = cv2.imread(image_path, cv2.IMREAD_GRAYSCALE)

            if img is None:
                return None

            h, w = img.shape
            if h > w:
                new_h = size
                new_w = int(w * size / h)
            else:
                new_w = size
                new_h = int(h * size / w)

            img_resized = cv2.resize(img, (new_w, new_h), interpolation=cv2.INTER_AREA)

            height, width = img_resized.shape
            bytes_per_line = width
            q_image = QImage(
                img_resized.data,
                width,
                height,
                bytes_per_line,
                QImage.Format_Grayscale8,
            )
            pixmap = QPixmap.fromImage(q_image)

            return pixmap
        except Exception as e:
            print(f"Error creando miniatura: {e}")
            return None


    def show_context_menu(self, position):
        menu = QMenu()
        create_folder = menu.addAction("Nueva carpeta")
        rename_item = menu.addAction("️ Renombrar")
        delete_item = menu.addAction("️ Eliminar")

        action = menu.exec_(self.file_tree.viewport().mapToGlobal(position))

        item = self.file_tree.currentItem()

        if action == create_folder:
            dialog = self.create_input_dialog("Nueva carpeta", "Nombre:")
            if dialog.exec_() == QInputDialog.Accepted:
                folder_name = dialog.textValue()
                if folder_name:
                    parent_path = self.cache_dir
                    if item:
                        item_path = item.data(0, Qt.UserRole)
                        if os.path.isdir(item_path):
                            parent_path = item_path

                    new_folder = os.path.join(parent_path, folder_name)
                    os.makedirs(new_folder, exist_ok=True)
                    self.update_file_tree_preserve_state()

        elif action == rename_item and item:
            old_path = item.data(0, Qt.UserRole)
            old_name = item.text(0)

            dialog = self.create_input_dialog(
                "Renombrar", f"Nuevo nombre para '{old_name}':", text=old_name
            )

            if dialog.exec_() == QInputDialog.Accepted:
                new_name = dialog.textValue()
                if new_name and new_name != old_name:
                    parent_dir = os.path.dirname(old_path)
                    new_path = os.path.join(parent_dir, new_name)

                    try:
                        os.rename(old_path, new_path)
                        item.setText(0, new_name)
                        item.setData(0, Qt.UserRole, new_path)
                        QMessageBox.information(
                            self, "Éxito", f"Renombrado a: {new_name}"
                        )
                    except Exception as e:
                        QMessageBox.warning(
                            self, "Error", f"No se pudo renombrar: {str(e)}"
                        )

        elif action == delete_item and item:
            reply = QMessageBox.question(
                self,
                "Confirmar eliminación",
                f"¿Eliminar {item.text(0)}?",
                QMessageBox.Yes | QMessageBox.No,
            )
            if reply == QMessageBox.Yes:
                item_path = item.data(0, Qt.UserRole)
                try:
                    if os.path.isfile(item_path):
                        os.remove(item_path)
                    elif os.path.isdir(item_path):
                        import shutil

                        shutil.rmtree(item_path)

                    parent = item.parent()
                    if parent:
                        parent.removeChild(item)
                    else:
                        index = self.file_tree.indexOfTopLevelItem(item)
                        self.file_tree.takeTopLevelItem(index)

                    QMessageBox.information(
                        self, "Éxito", "Elemento eliminado correctamente"
                    )
                except Exception as e:
                    QMessageBox.warning(self, "Error", f"No se pudo eliminar: {str(e)}")


    def load_from_tree(self, item, column):
        item_path = item.data(0, Qt.UserRole)
        if os.path.isfile(item_path) and item_path.lower().endswith(
            (".png", ".jpg", ".bmp", ".tiff", ".svg")
        ):
            image = cv2.imread(item_path, cv2.IMREAD_GRAYSCALE)
            self.pattern = image / 255.0
            
            if getattr(self, "grid_view_active", False): self.toggle_grid_view()
            if getattr(self, "calibration_view_active", False): self.toggle_calibration_view()
            if getattr(self, "_ruler_scale_view_active", False): self.toggle_ruler_scale_view()
            if getattr(self, "_pattern_calib_view_active", False): self.toggle_pattern_calibration_view()
            
            self.simulate_optics()
            self.projector_button.setVisible(True)
            self.update_projector_button()
            self._refresh_invert_button_state()

