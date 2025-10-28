import sys
import cv2
import os
import json
from scipy.ndimage import gaussian_filter
from PyQt5.QtWidgets import (
    QApplication, QWidget, QVBoxLayout, QHBoxLayout, QPushButton, QLabel,
    QFileDialog, QSlider, QMessageBox, QTreeWidget, QTreeWidgetItem, 
    QInputDialog, QMenu, QComboBox, QTreeWidgetItemIterator, QGraphicsOpacityEffect
)
from PyQt5.QtCore import Qt, QPropertyAnimation, QEasingCurve, QSize
from PyQt5.QtGui import QDragEnterEvent, QDropEvent, QIcon, QPixmap, QImage
from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg as FigureCanvas
from matplotlib.figure import Figure
import numpy as np
import ctypes

class ProjectionWindow(QWidget):
    def __init__(self, image_array, parent_simulator=None):
        super().__init__(None)
        self.parent_simulator = parent_simulator
        self.setWindowTitle("Proyección")
        self.setWindowFlags(Qt.Window | Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint)
        self.setStyleSheet("background-color: black;")
        
        self.original_image = None
        self.brightness_factor = 1.0
        
        layout = QVBoxLayout()
        layout.setContentsMargins(0, 0, 0, 0)
        
        self.image_label = QLabel()
        self.image_label.setAlignment(Qt.AlignCenter)
        self.image_label.setScaledContents(False)
        
        self.update_image(image_array)
        
        layout.addWidget(self.image_label)
        self.setLayout(layout)
        
        self.setFocusPolicy(Qt.StrongFocus)
    
    def update_image(self, image_array):
        self.original_image = image_array.copy()
        
        self._apply_brightness_and_display()
    
    def set_brightness(self, brightness_percent):
        self.brightness_factor = brightness_percent / 100.0
        self._apply_brightness_and_display()
    
    def _apply_brightness_and_display(self):
        if self.original_image is None:
            return
        
        adjusted_image = self.original_image * self.brightness_factor
        
        normalized = adjusted_image / 100.0
        adjusted_image_uint8 = (normalized * 255).astype(np.uint8)
        
        height, width = adjusted_image_uint8.shape
        bytes_per_line = width
        
        q_image = QImage(adjusted_image_uint8.data, width, height, bytes_per_line, QImage.Format_Grayscale8)
        
        pixmap = QPixmap.fromImage(q_image)
        
        self.image_label.setPixmap(pixmap)
    
    def keyPressEvent(self, event):
        if event.key() == Qt.Key_Escape:
            self.close()
        super().keyPressEvent(event)
    
    def closeEvent(self, event):
        if self.parent_simulator is not None:
            self.parent_simulator.on_projection_closed()
        super().closeEvent(event)
    
    def show_on_secondary_monitor(self):
        screens = QApplication.screens()
        
        if len(screens) > 1:
            secondary_screen = screens[1]
        else:
            secondary_screen = screens[0]
        
        geometry = secondary_screen.geometry()
        
        self.setGeometry(geometry)
        self.showFullScreen()

class LithographySimulator(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Simulador Litografía Uandes V1.1")
        self.setGeometry(100, 100, 1600, 700)
        self.setAcceptDrops(True)
        
        icon_path = os.path.join(os.path.dirname(__file__), "icono.ico")
        if os.path.exists(icon_path):
            self.setWindowIcon(QIcon(icon_path))
        
        self.set_dark_titlebar()

        self.pattern = None
        self.sigma = 2.0
        self.cache_dir = "cache_photolith"
        self.config_file = os.path.join(self.cache_dir, "file_structure.json")
        self.dark_mode = True
        self.projector_active = False
        self.projection_window = None
        self.has_second_monitor = self.check_second_monitor()  # Detectar segundo monitor
        self.init_cache_system()
        
        main_layout = QVBoxLayout()
        control_layout = QHBoxLayout()

        self.load_button = QPushButton("📂 Cargar patrón")
        self.load_button.clicked.connect(self.load_pattern)
        
        self.preferences_button = QPushButton("⚙️ Preferencias")
        self.preferences_button.clicked.connect(self.show_preferences_menu)
        
        self.projector_button = QPushButton("🎬 Proyectar")
        self.projector_button.clicked.connect(self.toggle_projector)
        self.projector_button.setVisible(False)

        self.sigma_label = QLabel(f"Sigma (Desenfoque): {self.sigma:.1f}")
        self.sigma_slider = QSlider(Qt.Horizontal)
        self.sigma_slider.setMinimum(1)
        self.sigma_slider.setMaximum(30)
        self.sigma_slider.setValue(int(self.sigma))
        self.sigma_slider.valueChanged.connect(self.update_sigma)
        
        self.brightness = 100
        self.brightness_label = QLabel(f"Brillo Proyección: {self.brightness}%")
        self.brightness_slider = QSlider(Qt.Horizontal)
        self.brightness_slider.setMinimum(0)
        self.brightness_slider.setMaximum(100)
        self.brightness_slider.setValue(self.brightness)
        self.brightness_slider.valueChanged.connect(self.update_brightness)
        self.brightness_slider.setVisible(False)
        self.brightness_label.setVisible(False)

        self.save_button = QPushButton("💾 Guardar imagen")
        self.save_button.clicked.connect(self.save_image)
        
        self.format_combo = QComboBox()
        self.format_combo.addItems(["PNG", "JPG", "BMP", "TIFF"])

        control_layout.addWidget(self.load_button)
        control_layout.addWidget(self.preferences_button)
        control_layout.addWidget(self.projector_button)
        control_layout.addWidget(self.sigma_label)
        control_layout.addWidget(self.sigma_slider)
        control_layout.addWidget(self.brightness_label)
        control_layout.addWidget(self.brightness_slider)
        control_layout.addWidget(self.save_button)
        control_layout.addWidget(QLabel("Formato:"))
        control_layout.addWidget(self.format_combo)

        self.figure = Figure(facecolor="#121212")
        self.canvas = FigureCanvas(self.figure)

        self.info_layout = QVBoxLayout()
        self.info_layout.setSpacing(12)
        
        stats_title = QLabel("📊 DATA:")
        stats_title.setObjectName("sectionTitle")
        self.info_layout.addWidget(stats_title)
        
        stats_container = QWidget()
        stats_container.setObjectName("statsContainer")
        stats_layout = QVBoxLayout(stats_container)
        stats_layout.setContentsMargins(12, 12, 12, 12)
        stats_layout.setSpacing(8)
        
        self.resolution_label = QLabel("Resolución: -")
        self.resolution_label.setObjectName("statLabel")
        self.min_label = QLabel("Intensidad mínima: -")
        self.min_label.setObjectName("statLabel")
        self.avg_label = QLabel("Intensidad promedio: -")
        self.avg_label.setObjectName("statLabel")
        self.max_label = QLabel("Intensidad máxima: -")
        self.max_label.setObjectName("statLabel")
        
        stats_layout.addWidget(self.resolution_label)
        stats_layout.addWidget(self.min_label)
        stats_layout.addWidget(self.avg_label)
        stats_layout.addWidget(self.max_label)
        
        self.info_layout.addWidget(stats_container)
        
        self.info_layout.addSpacing(20)
        
        files_title = QLabel("📁 ARCHIVOS")
        files_title.setObjectName("sectionTitle")
        self.info_layout.addWidget(files_title)
        
        self.file_tree = QTreeWidget()
        self.file_tree.setHeaderLabel("")
        self.file_tree.setHeaderHidden(True)
        self.file_tree.setContextMenuPolicy(Qt.CustomContextMenu)
        self.file_tree.customContextMenuRequested.connect(self.show_context_menu)
        self.file_tree.itemDoubleClicked.connect(self.load_from_tree)
        self.file_tree.setIconSize(QSize(56, 56))
        self.file_tree.setMinimumWidth(300)
        self.file_tree.setMinimumHeight(350)
        self.file_tree.setObjectName("fileTree")
        self.update_file_tree()
        
        self.info_layout.addWidget(self.file_tree)
        self.info_layout.addStretch()

        canvas_layout = QHBoxLayout()
        canvas_layout.addWidget(self.canvas, stretch=3)
        canvas_layout.addLayout(self.info_layout, stretch=1)

        main_layout.addLayout(control_layout)
        main_layout.addLayout(canvas_layout)
        self.setLayout(main_layout)

        self.apply_theme()
    
    def set_dark_titlebar(self):
        try:
            if sys.platform == "win32":
                hwnd = int(self.winId())
                
                DWMWA_USE_IMMERSIVE_DARK_MODE = 20
                
                value = ctypes.c_int(1)
                
                ctypes.windll.dwmapi.DwmSetWindowAttribute(
                    hwnd,
                    DWMWA_USE_IMMERSIVE_DARK_MODE,
                    ctypes.byref(value),
                    ctypes.sizeof(value)
                )
        except Exception as e:
            print(f"No se pudo aplicar barra de título oscura: {e}")
    
    def showEvent(self, event):
        super().showEvent(event)
        self.set_dark_titlebar()
    
    def closeEvent(self, event):
        if self.projection_window is not None:
            self.projection_window.close()
            self.projection_window = None
        super().closeEvent(event)
    
    def check_second_monitor(self):
        """Verifica si hay un segundo monitor conectado"""
        screens = QApplication.screens()
        return len(screens) > 1
    
    def create_input_dialog(self, title, label, text=""):
        dialog = QInputDialog(self)
        dialog.setWindowTitle(title)
        dialog.setLabelText(label)
        dialog.setTextValue(text)
        dialog.setWindowFlags(dialog.windowFlags() & ~Qt.WindowContextHelpButtonHint)
        
        if self.dark_mode and sys.platform == 'win32':
            try:
                hwnd = int(dialog.winId())
                DWMWA_USE_IMMERSIVE_DARK_MODE = 20
                value = ctypes.c_int(1)
                ctypes.windll.dwmapi.DwmSetWindowAttribute(
                    hwnd,
                    DWMWA_USE_IMMERSIVE_DARK_MODE,
                    ctypes.byref(value),
                    ctypes.sizeof(value)
                )
            except:
                pass
        
        return dialog

    def init_cache_system(self):
        if not os.path.exists(self.cache_dir):
            os.makedirs(self.cache_dir)
        
        if not os.path.exists(self.config_file):
            with open(self.config_file, 'w') as f:
                json.dump({"folders": {}}, f)

    def dragEnterEvent(self, event: QDragEnterEvent):
        if event.mimeData().hasUrls():
            event.acceptProposedAction()

    def dropEvent(self, event: QDropEvent):
        urls = event.mimeData().urls()
        if urls:
            file_path = urls[0].toLocalFile()
            if file_path.lower().endswith(('.png', '.jpg', '.jpeg', '.bmp', '.tiff')):
                if self.pattern is not None:
                    reply = QMessageBox.question(
                        self, 
                        'Reemplazar imagen',
                        '¿Desea reemplazar la imagen actual?',
                        QMessageBox.Yes | QMessageBox.No,
                        QMessageBox.No
                    )
                    if reply == QMessageBox.No:
                        return
                
                image = cv2.imread(file_path, cv2.IMREAD_GRAYSCALE)
                self.pattern = image / 255.0
                self.simulate_optics()

    def load_pattern(self):
        file_path, _ = QFileDialog.getOpenFileName(
            self, "Seleccionar patrón", "", "Imágenes (*.png *.jpg *.bmp *.tiff)"
        )
        if file_path:
            if self.pattern is not None:
                reply = QMessageBox.question(
                    self, 
                    'Reemplazar imagen',
                    '¿Desea reemplazar la imagen actual?',
                    QMessageBox.Yes | QMessageBox.No,
                    QMessageBox.No
                )
                if reply == QMessageBox.No:
                    return
            
            image = cv2.imread(file_path, cv2.IMREAD_GRAYSCALE)
            self.pattern = image / 255.0
            self.simulate_optics()
            self.projector_button.setVisible(True)
            self.update_projector_button()

    def toggle_projector(self):
        self.has_second_monitor = self.check_second_monitor()
        if not self.has_second_monitor and not self.projector_active:
            QMessageBox.warning(
                self, 
                "Monitor no detectado", 
                "No se detectó un segundo monitor conectado.\n\n"
                "Por favor, conecte un segundo monitor para usar la función de proyección."
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
                "La proyección se ha detenido."
            )
            return
        
        self.projector_active = not self.projector_active
        
        if self.projector_active:
            if hasattr(self, 'last_intensity') and self.last_intensity is not None:
                self.projection_window = ProjectionWindow(self.last_intensity, self)
                self.projection_window.show_on_secondary_monitor()
                self.brightness_slider.setVisible(True)
                self.brightness_label.setVisible(True)
                self.update_brightness()
            else:
                QMessageBox.warning(self, "Advertencia", "No hay imagen procesada para proyectar")
                self.projector_active = False
        else:
            if self.projection_window is not None:
                self.projection_window.close()
                self.projection_window = None
            self.brightness_slider.setVisible(False)
            self.brightness_label.setVisible(False)
        
        self.update_projector_button()
    
    def on_projection_closed(self):
        self.projector_active = False
        self.projection_window = None
        self.brightness_slider.setVisible(False)
        self.brightness_label.setVisible(False)
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

    def save_image(self):
        if not hasattr(self, 'last_intensity'):
            QMessageBox.warning(self, "Advertencia", "No hay imagen procesada para guardar")
            return
        
        folders = self.get_folders_list()
        folder, ok = QInputDialog.getItem(
            self, "Seleccionar carpeta", 
            "Carpeta destino:", 
            folders + ["[Nueva carpeta]"], 0, False
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
        
        img_to_save = (self.last_intensity * 255 / self.last_intensity.max()).astype(np.uint8)
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
                if item.lower().endswith(('.png', '.jpg', '.jpeg', '.bmp', '.tiff')):
                    thumbnail = self.create_thumbnail(item_path, size=56)
                    if thumbnail:
                        tree_item.setIcon(0, QIcon(thumbnail))
                else:
                    tree_item.setIcon(0, self.style().standardIcon(self.style().SP_FileIcon))
    
    def create_thumbnail(self, image_path, size=56):
        try:
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
            q_image = QImage(img_resized.data, width, height, bytes_per_line, QImage.Format_Grayscale8)
            pixmap = QPixmap.fromImage(q_image)
            
            return pixmap
        except Exception as e:
            print(f"Error creando miniatura: {e}")
            return None

    def show_context_menu(self, position):
        menu = QMenu()
        create_folder = menu.addAction("📁 Nueva carpeta")
        rename_item = menu.addAction("✏️ Renombrar")
        delete_item = menu.addAction("🗑️ Eliminar")
        
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
                "Renombrar", 
                f"Nuevo nombre para '{old_name}':", 
                text=old_name
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
                        QMessageBox.information(self, "Éxito", f"Renombrado a: {new_name}")
                    except Exception as e:
                        QMessageBox.warning(self, "Error", f"No se pudo renombrar: {str(e)}")
        
        elif action == delete_item and item:
            reply = QMessageBox.question(
                self, 'Confirmar eliminación',
                f'¿Eliminar {item.text(0)}?',
                QMessageBox.Yes | QMessageBox.No
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
                    
                    QMessageBox.information(self, "Éxito", "Elemento eliminado correctamente")
                except Exception as e:
                    QMessageBox.warning(self, "Error", f"No se pudo eliminar: {str(e)}")

    def load_from_tree(self, item, column):
        item_path = item.data(0, Qt.UserRole)
        if os.path.isfile(item_path) and item_path.lower().endswith(('.png', '.jpg', '.bmp', '.tiff')):
            image = cv2.imread(item_path, cv2.IMREAD_GRAYSCALE)
            self.pattern = image / 255.0
            self.simulate_optics()
            self.projector_button.setVisible(True)
            self.update_projector_button()

    def update_sigma(self):
        self.sigma = self.sigma_slider.value()
        self.sigma_label.setText(f"Sigma (Desenfoque): {self.sigma:.1f}")
        if self.pattern is not None:
            self.simulate_optics()
    
    def update_brightness(self):
        self.brightness = self.brightness_slider.value()
        self.brightness_label.setText(f"Brillo Proyección: {self.brightness}%")
        if self.projector_active and self.projection_window is not None:
            self.projection_window.set_brightness(self.brightness)
    
    def show_preferences_menu(self):
        menu = QMenu(self)
        menu.setStyleSheet("""
            QMenu {
                background-color: """ + ("#1E1E1E" if self.dark_mode else "#FFFFFF") + """;
                color: """ + ("#E0E0E0" if self.dark_mode else "#000000") + """;
                border: 1px solid """ + ("#2E2E2E" if self.dark_mode else "#CCCCCC") + """;
                border-radius: 8px;
                padding: 8px;
            }
            QMenu::item {
                padding: 8px 20px;
                border-radius: 4px;
            }
            QMenu::item:selected {
                background-color: #03DAC6;
                color: #121212;
            }
        """)
        
        if self.dark_mode:
            theme_action = menu.addAction("☀️ Modo Claro")
        else:
            theme_action = menu.addAction("🌙 Modo Oscuro")
        
        theme_action.triggered.connect(self.toggle_theme)
        
        menu.exec_(self.preferences_button.mapToGlobal(self.preferences_button.rect().bottomLeft()))
    
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
    
    def apply_theme_and_fade_in(self):
        self.apply_theme()
        
        self.fade_in_animation = QPropertyAnimation(self.opacity_effect, b"opacity")
        self.fade_in_animation.setDuration(100)
        self.fade_in_animation.setStartValue(0.5)
        self.fade_in_animation.setEndValue(1.0)
        self.fade_in_animation.setEasingCurve(QEasingCurve.InCubic)
        
        self.fade_in_animation.finished.connect(lambda: self.setGraphicsEffect(None))
        self.fade_in_animation.start()
    
    def apply_theme(self):
        if self.dark_mode:
            self.apply_dark_theme()
        else:
            self.apply_light_theme()
        
        self.set_dark_titlebar() if self.dark_mode else self.set_light_titlebar()
        
        if self.pattern is not None:
            self.simulate_optics()
    
    def apply_dark_theme(self):
        self.figure.set_facecolor("#121212")
        self.canvas.draw()
        
        self.setStyleSheet("""
            QWidget {
                background-color: #121212;
                color: #f0f0f0;
                font-family: 'Segoe UI', sans-serif;
                font-size: 13px;
            }

            QPushButton {
                background-color: #1E1E1E;
                border: 1px solid #2E2E2E;
                border-radius: 8px;
                padding: 8px 12px;
                color: #E0E0E0;
            }
            QPushButton:hover {
                background-color: #2C2C2C;
                border: 1px solid #3E3E3E;
            }
            QPushButton:pressed {
                background-color: #3A3A3A;
            }
            QPushButton:disabled {
                background-color: #1A1A1A;
                color: #666666;
                border: 1px solid #252525;
            }

            QComboBox {
                background-color: #1E1E1E;
                border: 1px solid #2E2E2E;
                border-radius: 8px;
                padding: 8px 12px;
                color: #E0E0E0;
                min-width: 80px;
            }
            QComboBox:hover {
                background-color: #2C2C2C;
                border: 1px solid #3E3E3E;
            }
            QComboBox::drop-down {
                border: none;
                width: 30px;
            }
            QComboBox::down-arrow {
                image: none;
                width: 0;
                height: 0;
                border-left: 6px solid transparent;
                border-right: 6px solid transparent;
                border-top: 8px solid #888888;
                margin-right: 8px;
            }
            QComboBox QAbstractItemView {
                background-color: #1E1E1E;
                border: 1px solid #2E2E2E;
                border-radius: 8px;
                selection-background-color: #03DAC6;
                selection-color: #121212;
                padding: 4px;
                color: #E0E0E0;
            }
            QComboBox QAbstractItemView::item {
                padding: 8px;
                border-radius: 4px;
            }
            QComboBox QAbstractItemView::item:hover {
                background-color: #2C2C2C;
            }

            QLabel {
                color: #f0f0f0;
            }
            
            QLabel#sectionTitle {
                color: #03DAC6;
                font-size: 11px;
                font-weight: bold;
                letter-spacing: 1px;
                padding: 8px 0px;
                margin-top: 4px;
            }
            
            QLabel#statLabel {
                color: #B0B0B0;
                font-size: 12px;
                padding: 4px 0px;
            }
            
            QWidget#statsContainer {
                background-color: #1A1A1A;
                border: 1px solid #2A2A2A;
                border-radius: 8px;
                border-left: 3px solid #03DAC6;
            }

            QSlider::groove:horizontal {
                background: #2E2E2E;
                height: 6px;
                border-radius: 3px;
            }

            QSlider::handle:horizontal {
                background: #03DAC6;
                width: 14px;
                border-radius: 7px;
                margin: -4px 0;
            }

            QSlider::handle:horizontal:hover {
                background: #00BFA5;
            }

            QTreeWidget#fileTree {
                background-color: #1A1A1A;
                border: 1px solid #2A2A2A;
                border-radius: 8px;
                padding: 8px;
            }

            QTreeWidget::item {
                padding: 8px;
                min-height: 64px;
                border-radius: 6px;
                margin: 3px 0px;
            }

            QTreeWidget::item:hover {
                background-color: #252525;
            }

            QTreeWidget::item:selected {
                background-color: #03DAC6;
                color: #121212;
            }
            
            QScrollBar:vertical {
                background-color: transparent;
                width: 10px;
                margin: 0px;
            }
            
            QScrollBar::handle:vertical {
                background-color: #3A3A3A;
                border-radius: 5px;
                min-height: 40px;
            }
            
            QScrollBar::handle:vertical:hover {
                background-color: #4A4A4A;
            }
            
            QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {
                height: 0px;
            }
            
            QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical {
                background: transparent;
            }
            
            QScrollBar:horizontal {
                background-color: transparent;
                height: 10px;
                margin: 0px;
            }
            
            QScrollBar::handle:horizontal {
                background-color: #3A3A3A;
                border-radius: 5px;
                min-width: 40px;
            }
            
            QScrollBar::handle:horizontal:hover {
                background-color: #4A4A4A;
            }
            
            QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal {
                width: 0px;
            }
            
            QScrollBar::add-page:horizontal, QScrollBar::sub-page:horizontal {
                background: transparent;
            }
        """)
    
    def apply_light_theme(self):
        self.figure.set_facecolor("#FFFFFF")
        self.canvas.draw()
        
        self.setStyleSheet("""
            QWidget {
                background-color: #FFFFFF;
                color: #000000;
                font-family: 'Segoe UI', sans-serif;
                font-size: 13px;
            }

            QPushButton {
                background-color: #F5F5F5;
                border: 1px solid #CCCCCC;
                border-radius: 8px;
                padding: 8px 12px;
                color: #000000;
            }
            QPushButton:hover {
                background-color: #E0E0E0;
                border: 1px solid #BBBBBB;
            }
            QPushButton:pressed {
                background-color: #D0D0D0;
            }
            QPushButton:disabled {
                background-color: #F0F0F0;
                color: #AAAAAA;
                border: 1px solid #DDDDDD;
            }

            QComboBox {
                background-color: #F5F5F5;
                border: 1px solid #CCCCCC;
                border-radius: 8px;
                padding: 8px 12px;
                color: #000000;
                min-width: 80px;
            }
            QComboBox:hover {
                background-color: #E0E0E0;
                border: 1px solid #BBBBBB;
            }
            QComboBox::drop-down {
                border: none;
                width: 30px;
            }
            QComboBox::down-arrow {
                image: none;
                width: 0;
                height: 0;
                border-left: 6px solid transparent;
                border-right: 6px solid transparent;
                border-top: 8px solid #666666;
                margin-right: 8px;
            }
            QComboBox QAbstractItemView {
                background-color: #FFFFFF;
                border: 1px solid #CCCCCC;
                border-radius: 8px;
                selection-background-color: #03DAC6;
                selection-color: #000000;
                padding: 4px;
                color: #000000;
            }
            QComboBox QAbstractItemView::item {
                padding: 8px;
                border-radius: 4px;
            }
            QComboBox QAbstractItemView::item:hover {
                background-color: #F0F0F0;
            }

            QLabel {
                color: #000000;
            }
            
            QLabel#sectionTitle {
                color: #03DAC6;
                font-size: 11px;
                font-weight: bold;
                letter-spacing: 1px;
                padding: 8px 0px;
                margin-top: 4px;
            }
            
            QLabel#statLabel {
                color: #555555;
                font-size: 12px;
                padding: 4px 0px;
            }
            
            QWidget#statsContainer {
                background-color: #F8F8F8;
                border: 1px solid #E0E0E0;
                border-radius: 8px;
                border-left: 3px solid #03DAC6;
            }

            QSlider::groove:horizontal {
                background: #CCCCCC;
                height: 6px;
                border-radius: 3px;
            }

            QSlider::handle:horizontal {
                background: #03DAC6;
                width: 14px;
                border-radius: 7px;
                margin: -4px 0;
            }

            QSlider::handle:horizontal:hover {
                background: #00BFA5;
            }

            QTreeWidget#fileTree {
                background-color: #F8F8F8;
                border: 1px solid #E0E0E0;
                border-radius: 8px;
                padding: 8px;
            }

            QTreeWidget::item {
                padding: 6px;
                min-height: 85px;
                border-radius: 6px;
                margin: 2px 0px;
            }

            QTreeWidget::item:hover {
                background-color: #E8E8E8;
            }

            QTreeWidget::item:selected {
                background-color: #03DAC6;
                color: #000000;
            }
            
            QScrollBar:vertical {
                background-color: transparent;
                width: 10px;
                margin: 0px;
            }
            
            QScrollBar::handle:vertical {
                background-color: #BEBEBE;
                border-radius: 5px;
                min-height: 40px;
            }
            
            QScrollBar::handle:vertical:hover {
                background-color: #A0A0A0;
            }
            
            QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {
                height: 0px;
            }
            
            QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical {
                background: transparent;
            }
            
            QScrollBar:horizontal {
                background-color: transparent;
                height: 10px;
                margin: 0px;
            }
            
            QScrollBar::handle:horizontal {
                background-color: #BEBEBE;
                border-radius: 5px;
                min-width: 40px;
            }
            
            QScrollBar::handle:horizontal:hover {
                background-color: #A0A0A0;
            }
            
            QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal {
                width: 0px;
            }
            
            QScrollBar::add-page:horizontal, QScrollBar::sub-page:horizontal {
                background: transparent;
            }
        """)
    
    def set_light_titlebar(self):
        try:
            if sys.platform == "win32":
                hwnd = int(self.winId())
                DWMWA_USE_IMMERSIVE_DARK_MODE = 20
                value = ctypes.c_int(0)
                ctypes.windll.dwmapi.DwmSetWindowAttribute(
                    hwnd,
                    DWMWA_USE_IMMERSIVE_DARK_MODE,
                    ctypes.byref(value),
                    ctypes.sizeof(value)
                )
        except Exception as e:
            print(f"No se pudo aplicar barra de título clara: {e}")

    def simulate_optics(self):
        psf_result = gaussian_filter(self.pattern, sigma=self.sigma)
        intensity_percentage = (psf_result / psf_result.max()) * 100
        self.last_intensity = intensity_percentage
        self.plot_results(self.pattern, psf_result, intensity_percentage)
        self.update_info_panel(intensity_percentage)
        
        if self.projector_active and self.projection_window is not None:
            self.projection_window.update_image(intensity_percentage)

    def plot_results(self, pattern, simulated, intensity_percentage):
        self.figure.clear()
        
        bg_color = "#121212" if self.dark_mode else "#FFFFFF"
        text_color = "white" if self.dark_mode else "black"
        
        ax1 = self.figure.add_subplot(1, 2, 1)
        ax2 = self.figure.add_subplot(1, 2, 2)

        for ax in [ax1, ax2]:
            ax.set_facecolor(bg_color)
            ax.tick_params(colors=text_color)
            ax.xaxis.label.set_color(text_color)
            ax.yaxis.label.set_color(text_color)
            for spine in ax.spines.values():
                spine.set_edgecolor(text_color)
        
        ax1.imshow(pattern, cmap='gray')
        ax1.set_xlabel("X")
        ax1.set_ylabel("Y")
        
        ax2.imshow(intensity_percentage, cmap='inferno')
        ax2.set_xlabel("X")
        ax2.set_ylabel("Y")

        self.canvas.draw()

    def update_info_panel(self, intensity_map):
        if intensity_map is not None:
            h, w = intensity_map.shape
            self.resolution_label.setText(f"Resolución: {w} × {h}")
            self.min_label.setText(f"Intensidad mínima: {intensity_map.min():.2f}")
            self.avg_label.setText(f"Intensidad promedio: {intensity_map.mean():.2f}")
            self.max_label.setText(f"Intensidad máxima: {intensity_map.max():.2f}")


if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = LithographySimulator()
    window.show()
    sys.exit(app.exec_())
