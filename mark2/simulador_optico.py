import sys
import cv2
import os
import json
from scipy.ndimage import gaussian_filter
from PyQt5.QtWidgets import (
    QApplication, QWidget, QVBoxLayout, QHBoxLayout, QPushButton, QLabel,
    QFileDialog, QSlider, QMessageBox, QTreeWidget, QTreeWidgetItem, 
    QInputDialog, QMenu, QComboBox
)
from PyQt5.QtCore import Qt
from PyQt5.QtGui import QDragEnterEvent, QDropEvent
from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg as FigureCanvas
from matplotlib.figure import Figure
import numpy as np

class LithographySimulator(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Simulador Óptico de Maggi V1.0")
        self.setGeometry(100, 100, 1600, 700)
        self.setAcceptDrops(True)

        self.pattern = None
        self.sigma = 2.0
        self.cache_dir = "cache_photolith"
        self.config_file = os.path.join(self.cache_dir, "file_structure.json")
        self.init_cache_system()
        
        main_layout = QVBoxLayout()
        control_layout = QHBoxLayout()

        # botones y controles
        self.load_button = QPushButton("📂 Cargar patrón")
        self.load_button.clicked.connect(self.load_pattern)

        self.sigma_label = QLabel(f"Sigma (Desenfoque): {self.sigma:.1f}")
        self.sigma_slider = QSlider(Qt.Horizontal)
        self.sigma_slider.setMinimum(1)
        self.sigma_slider.setMaximum(30)
        self.sigma_slider.setValue(int(self.sigma))
        self.sigma_slider.valueChanged.connect(self.update_sigma)

        # Botón guardar
        self.save_button = QPushButton("💾 Guardar imagen")
        self.save_button.clicked.connect(self.save_image)
        
        # Selector de formato
        self.format_combo = QComboBox()
        self.format_combo.addItems(["PNG", "JPG", "BMP", "TIFF"])

        # controles
        control_layout.addWidget(self.load_button)
        control_layout.addWidget(self.sigma_label)
        control_layout.addWidget(self.sigma_slider)
        control_layout.addWidget(self.save_button)
        control_layout.addWidget(QLabel("Formato:"))
        control_layout.addWidget(self.format_combo)

        self.figure = Figure(facecolor="#121212")
        self.canvas = FigureCanvas(self.figure)

        # Panel de información
        self.info_layout = QVBoxLayout()
        self.resolution_label = QLabel("Resolución: -")
        self.min_label = QLabel("Intensidad mínima: -")
        self.avg_label = QLabel("Intensidad promedio: -")
        self.max_label = QLabel("Intensidad máxima: -")
        self.info_layout.addWidget(self.resolution_label)
        self.info_layout.addWidget(self.min_label)
        self.info_layout.addWidget(self.avg_label)
        self.info_layout.addWidget(self.max_label)
        
        # Árbol de archivos
        self.file_tree = QTreeWidget()
        self.file_tree.setHeaderLabel("Archivos guardados")
        self.file_tree.setContextMenuPolicy(Qt.CustomContextMenu)
        self.file_tree.customContextMenuRequested.connect(self.show_context_menu)
        self.file_tree.itemDoubleClicked.connect(self.load_from_tree)
        self.update_file_tree()
        
        self.info_layout.addWidget(QLabel("─" * 20))
        self.info_layout.addWidget(self.file_tree)
        self.info_layout.addStretch()

        canvas_layout = QHBoxLayout()
        canvas_layout.addWidget(self.canvas, stretch=3)
        canvas_layout.addLayout(self.info_layout, stretch=1)

        main_layout.addLayout(control_layout)
        main_layout.addLayout(canvas_layout)
        self.setLayout(main_layout)

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

            QComboBox {
                background-color: #1E1E1E;
                border: 1px solid #2E2E2E;
                border-radius: 6px;
                padding: 4px 8px;
            }

            QLabel {
                color: #f0f0f0;
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

            QTreeWidget {
                background-color: #1E1E1E;
                border: 1px solid #2E2E2E;
                border-radius: 6px;
            }

            QTreeWidget::item:hover {
                background-color: #2C2C2C;
            }

            QTreeWidget::item:selected {
                background-color: #03DAC6;
                color: #121212;
            }
        """)

    def init_cache_system(self):
        """Inicializa el sistema de caché y carpetas"""
        if not os.path.exists(self.cache_dir):
            os.makedirs(self.cache_dir)
        
        if not os.path.exists(self.config_file):
            with open(self.config_file, 'w') as f:
                json.dump({"folders": {}}, f)

    def dragEnterEvent(self, event: QDragEnterEvent):
        """Acepta archivos arrastrados"""
        if event.mimeData().hasUrls():
            event.acceptProposedAction()

    def dropEvent(self, event: QDropEvent):
        """Maneja archivos soltados"""
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

    def save_image(self):
        if not hasattr(self, 'last_intensity'):
            QMessageBox.warning(self, "Advertencia", "No hay imagen procesada para guardar")
            return
        
        # seleccionar carpeta
        folders = self.get_folders_list()
        folder, ok = QInputDialog.getItem(
            self, "Seleccionar carpeta", 
            "Carpeta destino (o crea una nueva):", 
            folders + ["[Nueva carpeta]"], 0, False
        )
        
        if not ok:
            return
        
        if folder == "[Nueva carpeta]":
            folder, ok = QInputDialog.getText(self, "Nueva carpeta", "Nombre de la carpeta:")
            if not ok or not folder:
                return
            self.create_folder(folder)
        
        # nombre del archivo
        filename, ok = QInputDialog.getText(self, "Guardar imagen", "Nombre del archivo:")
        if not ok or not filename:
            return
        
        # formato
        fmt = self.format_combo.currentText().lower()
        filepath = os.path.join(self.cache_dir, folder, f"{filename}.{fmt}")
        
        # crear directorio 
        os.makedirs(os.path.dirname(filepath), exist_ok=True)
        
        # convertir y guardar
        img_to_save = (self.last_intensity * 255 / self.last_intensity.max()).astype(np.uint8)
        cv2.imwrite(filepath, img_to_save)
        
        self.update_file_tree()
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
                tree_item.setIcon(0, self.style().standardIcon(self.style().SP_FileIcon))

    def show_context_menu(self, position):
        menu = QMenu()
        create_folder = menu.addAction("📁 Nueva carpeta")
        delete_item = menu.addAction("🗑️ Eliminar")
        
        action = menu.exec_(self.file_tree.viewport().mapToGlobal(position))
        
        item = self.file_tree.currentItem()
        
        if action == create_folder:
            folder_name, ok = QInputDialog.getText(self, "Nueva carpeta", "Nombre:")
            if ok and folder_name:
                parent_path = self.cache_dir
                if item:
                    item_path = item.data(0, Qt.UserRole)
                    if os.path.isdir(item_path):
                        parent_path = item_path
                
                new_folder = os.path.join(parent_path, folder_name)
                os.makedirs(new_folder, exist_ok=True)
                self.update_file_tree()
        
        elif action == delete_item and item:
            reply = QMessageBox.question(
                self, 'Confirmar eliminación',
                f'¿Eliminar {item.text(0)}?',
                QMessageBox.Yes | QMessageBox.No
            )
            if reply == QMessageBox.Yes:
                item_path = item.data(0, Qt.UserRole)
                if os.path.isfile(item_path):
                    os.remove(item_path)
                elif os.path.isdir(item_path):
                    import shutil
                    shutil.rmtree(item_path)
                self.update_file_tree()

    def load_from_tree(self, item, column):
        item_path = item.data(0, Qt.UserRole)
        if os.path.isfile(item_path) and item_path.lower().endswith(('.png', '.jpg', '.bmp', '.tiff')):
            image = cv2.imread(item_path, cv2.IMREAD_GRAYSCALE)
            self.pattern = image / 255.0
            self.simulate_optics()

    def update_sigma(self):
        self.sigma = self.sigma_slider.value()
        self.sigma_label.setText(f"Sigma (Desenfoque): {self.sigma:.1f}")
        if self.pattern is not None:
            self.simulate_optics()

    def simulate_optics(self):
        psf_result = gaussian_filter(self.pattern, sigma=self.sigma)
        intensity_percentage = (psf_result / psf_result.max()) * 100
        self.last_intensity = intensity_percentage
        self.plot_results(self.pattern, psf_result, intensity_percentage)
        self.update_info_panel(intensity_percentage)

    def plot_results(self, pattern, simulated, intensity_percentage):
        self.figure.clear()
        
        ax1 = self.figure.add_subplot(1, 2, 1)
        ax2 = self.figure.add_subplot(1, 2, 2)  

        for ax in [ax1, ax2]:
            ax.set_facecolor("#121212")
            ax.tick_params(colors='white')  
            ax.xaxis.label.set_color('white')  
            ax.yaxis.label.set_color('white')  
        
        ax1.imshow(pattern, cmap='gray')
        ax1.set_title("Patrón de entrada", color="white")
        ax1.set_xlabel("X")
        ax1.set_ylabel("Y")
        
        ax2.imshow(intensity_percentage, cmap='inferno')
        ax2.set_title(f"Mapa de intensidad", color="white") 
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
