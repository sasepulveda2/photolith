"""
Mixin de temas visuales y eventos de ventana.

Aplica temas dark/light, gestiona la consola de log,
toolbar, deteccion de monitores y eventos de ventana.
"""
import sys
import ctypes

from PyQt5.QtWidgets import (
    QApplication, QMessageBox,
)


class ThemeMixin:
    """Mixin: Theme functionality."""

    def log_to_console(self, message, message_type="INFO"):
        """
        Agrega un mensaje a la consola del sistema con timestamp y tipo.

        Args:
            message (str): Mensaje a mostrar
            message_type (str): Tipo de mensaje - "INFO", "SUCCESS", "WARNING", "ERROR", "OPTIMIZATION", "SEGMENTATION"
        """
        from datetime import datetime

        timestamp = datetime.now().strftime("%H:%M:%S")

        # Definir colores según tipo de mensaje (HTML)
        color_map = {
            "INFO": "#BBBBBB",
            "SUCCESS": "#4CAF50",
            "WARNING": "#FFC107",
            "ERROR": "#F44336",
            "OPTIMIZATION": "#03DAC6",
            "SEGMENTATION": "#BB86FC",
        }

        color = color_map.get(message_type, "#BBBBBB")

        # Formatear mensaje con HTML
        formatted_message = f'<span style="color: #888888;">[{timestamp}]</span> <span style="color: {color}; font-weight: bold;">[{message_type}]</span> <span style="color: #E0E0E0;">{message}</span>'

        # Agregar a la consola
        self.system_console.append(formatted_message)

        # Scroll automático al final
        scrollbar = self.system_console.verticalScrollBar()
        scrollbar.setValue(scrollbar.maximum())


    def clear_console(self):
        """Limpia todos los mensajes de la consola."""
        self.system_console.clear()
        self.log_to_console("Consola limpiada", "INFO")


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
            
            QPushButton#modernButton {
                background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                    stop:0 #03DAC6, stop:1 #018786);
                border: none;
                border-radius: 12px;
                padding: 12px 20px;
                color: #121212;
                font-weight: bold;
                font-size: 14px;
                text-transform: uppercase;
                letter-spacing: 1px;
            }
            QPushButton#modernButton:hover {
                background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                    stop:0 #00E5CC, stop:1 #01A299);
            }
            QPushButton#modernButton:pressed {
                background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                    stop:0 #018786, stop:1 #016968);
                padding: 13px 20px 11px 20px;
            }
            
            QPushButton#tabButton {
                background-color: #1E1E1E;
                border: 1px solid #2E2E2E;
                border-radius: 8px;
                padding: 10px 16px;
                color: #A0A0A0;
                font-weight: bold;
                font-size: 12px;
            }
            QPushButton#tabButton:hover {
                background-color: #2C2C2C;
                border: 1px solid #3E3E3E;
                color: #C0C0C0;
            }
            QPushButton#tabButton:checked {
                background-color: #03DAC6;
                border: 1px solid #03DAC6;
                color: #121212;
            }
            QPushButton#tabButton:checked:hover {
                background-color: #00BFA5;
                border: 1px solid #00BFA5;
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
            
            QCheckBox {
                color: #E0E0E0;
                spacing: 8px;
                padding: 6px;
            }
            QCheckBox::indicator {
                width: 20px;
                height: 20px;
                border-radius: 6px;
                border: 2px solid #3E3E3E;
                background-color: #1E1E1E;
            }
            QCheckBox::indicator:hover {
                border: 2px solid #03DAC6;
                background-color: #2C2C2C;
            }
            QCheckBox::indicator:checked {
                background-color: #03DAC6;
                border: 2px solid #03DAC6;
                image: url(none);
            }
            QCheckBox::indicator:checked:hover {
                background-color: #00BFA5;
                border: 2px solid #00BFA5;
            }

            QLabel {
                color: #f0f0f0;
            }
            
            QLabel#sectionTitle,
            QToolButton#sectionTitle {
                color: #03DAC6;
                font-size: 11px;
                font-weight: bold;
                letter-spacing: 1px;
            }

            QLabel#sectionTitle {
                padding: 8px 0px;
                margin-top: 4px;
            }

            QToolButton#sectionTitle {
                background-color: #1A1A1A;
                border: 1px solid #2A2A2A;
                border-radius: 8px;
                padding: 8px 12px;
                text-align: left;
            }

            QToolButton#sectionTitle:hover {
                background-color: #242424;
            }

            QToolButton#sectionTitle:checked {
                background-color: #222222;
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
            
            QScrollArea {
                background-color: transparent;
                border: none;
            }
            
            QTextEdit {
                background-color: #1A1A1A;
                border: 1px solid #2A2A2A;
                border-radius: 8px;
                padding: 8px;
                color: #E0E0E0;
                font-family: 'Consolas', 'Courier New', monospace;
                font-size: 12px;
                selection-background-color: #03DAC6;
                selection-color: #121212;
            }
            
            QTextEdit:focus {
                border: 1px solid #03DAC6;
            }
            
            QTabWidget {
                background-color: #121212;
            }
            
            QTabWidget::pane {
                background-color: #121212;
                border: 1px solid #2A2A2A;
                border-radius: 8px;
                padding: 10px;
            }
            
            QTabWidget::tab-bar {
                alignment: left;
            }
            
            QTabBar::tab {
                background-color: #1E1E1E;
                border: 1px solid #2E2E2E;
                border-bottom: none;
                border-top-left-radius: 8px;
                border-top-right-radius: 8px;
                padding: 12px 30px;
                color: #A0A0A0;
                font-weight: bold;
                font-size: 12px;
                margin-right: 4px;
                min-width: 150px;
            }
            
            QTabBar::tab:selected {
                background-color: #121212;
                border: 1px solid #03DAC6;
                border-bottom: 1px solid #121212;
                color: #03DAC6;
            }
            
            QTabBar::tab:hover:!selected {
                background-color: #2C2C2C;
                border: 1px solid #3E3E3E;
                color: #C0C0C0;
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
            
            QPushButton#modernButton {
                background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                    stop:0 #03DAC6, stop:1 #018786);
                border: none;
                border-radius: 12px;
                padding: 12px 20px;
                color: #000000;
                font-weight: bold;
                font-size: 14px;
                text-transform: uppercase;
                letter-spacing: 1px;
            }
            QPushButton#modernButton:hover {
                background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                    stop:0 #00E5CC, stop:1 #01A299);
            }
            QPushButton#modernButton:pressed {
                background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                    stop:0 #018786, stop:1 #016968);
                padding: 13px 20px 11px 20px;
            }
            
            QPushButton#tabButton {
                background-color: #F5F5F5;
                border: 1px solid #CCCCCC;
                border-radius: 8px;
                padding: 10px 16px;
                color: #666666;
                font-weight: bold;
                font-size: 12px;
            }
            QPushButton#tabButton:hover {
                background-color: #E0E0E0;
                border: 1px solid #BBBBBB;
                color: #444444;
            }
            QPushButton#tabButton:checked {
                background-color: #03DAC6;
                border: 1px solid #03DAC6;
                color: #000000;
            }
            QPushButton#tabButton:checked:hover {
                background-color: #00BFA5;
                border: 1px solid #00BFA5;
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
            
            QCheckBox {
                color: #000000;
                spacing: 8px;
                padding: 6px;
            }
            QCheckBox::indicator {
                width: 20px;
                height: 20px;
                border-radius: 6px;
                border: 2px solid #CCCCCC;
                background-color: #FFFFFF;
            }
            QCheckBox::indicator:hover {
                border: 2px solid #03DAC6;
                background-color: #F5F5F5;
            }
            QCheckBox::indicator:checked {
                background-color: #03DAC6;
                border: 2px solid #03DAC6;
                image: url(none);
            }
            QCheckBox::indicator:checked:hover {
                background-color: #00BFA5;
                border: 2px solid #00BFA5;
            }

            QLabel {
                color: #000000;
            }
            
            QLabel#sectionTitle,
            QToolButton#sectionTitle {
                color: #03DAC6;
                font-size: 11px;
                font-weight: bold;
                letter-spacing: 1px;
            }

            QLabel#sectionTitle {
                padding: 8px 0px;
                margin-top: 4px;
            }

            QToolButton#sectionTitle {
                background-color: #F8F8F8;
                border: 1px solid #E0E0E0;
                border-radius: 8px;
                padding: 8px 12px;
                text-align: left;
            }

            QToolButton#sectionTitle:hover {
                background-color: #F0F0F0;
            }

            QToolButton#sectionTitle:checked {
                background-color: #EAEAEA;
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
            
            QScrollArea {
                background-color: transparent;
                border: none;
            }
            
            QTextEdit {
                background-color: #FAFAFA;
                border: 1px solid #DDDDDD;
                border-radius: 8px;
                padding: 8px;
                color: #000000;
                font-family: 'Consolas', 'Courier New', monospace;
                font-size: 12px;
                selection-background-color: #03DAC6;
                selection-color: #000000;
            }
            
            QTextEdit:focus {
                border: 1px solid #03DAC6;
            }
            
            QTabWidget {
                background-color: #FFFFFF;
            }
            
            QTabWidget::pane {
                background-color: #FFFFFF;
                border: 1px solid #CCCCCC;
                border-radius: 8px;
                padding: 10px;
            }
            
            QTabWidget::tab-bar {
                alignment: left;
            }
            
            QTabBar::tab {
                background-color: #F5F5F5;
                border: 1px solid #CCCCCC;
                border-bottom: none;
                border-top-left-radius: 8px;
                border-top-right-radius: 8px;
                padding: 12px 30px;
                color: #666666;
                font-weight: bold;
                font-size: 12px;
                margin-right: 4px;
                min-width: 150px;
            }
            
            QTabBar::tab:selected {
                background-color: #FFFFFF;
                border: 1px solid #03DAC6;
                border-bottom: 1px solid #FFFFFF;
                color: #018786;
            }
            
            QTabBar::tab:hover:!selected {
                background-color: #E0E0E0;
                border: 1px solid #BBBBBB;
                color: #444444;
            }
        """)


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
                    ctypes.sizeof(value),
                )
        except Exception as e:
            print(f"No se pudo aplicar barra de título oscura: {e}")


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
                    ctypes.sizeof(value),
                )
        except Exception as e:
            print(f"No se pudo aplicar barra de título clara: {e}")


    def toggle_grid_view(self):
        self.grid_view_active = not self.grid_view_active

        if self.grid_view_active:
            # Asegurar que la vista de calibración esté oculta
            if self.calibration_view_active:
                self.hide_calibration_interface()
                self.calibration_view_active = False
                self.calibration_button.setText("🎯 Calibración")

            self.toggle_view_button.setText("🖼️ Vista Imagen")
            self.grid_config_section.setVisible(True)
            self.grid_config_section.set_collapsed(False)
            self.grid_stats_section.setVisible(True)
            self.grid_stats_section.set_collapsed(False)
            self.segmentation_section.setVisible(
                True
            )  # Mostrar segmentación en modo grid
            self.segmentation_section.set_collapsed(False)
            self.projection_control_section.setVisible(
                True
            )  # Mostrar control de proyección en modo grid
            self.projection_control_section.set_collapsed(False)
            self.toolbar.setVisible(True)  # Mostrar toolbar en modo grid

            # Preparar imagen para el grid si existe un patrón cargado
            if self.pattern is not None:
                # Aplicar efectos si la opción está activada
                if self.apply_effects_to_grid:
                    self.image_on_grid = self.apply_grid_effects(self.pattern.copy())
                else:
                    self.image_on_grid = self.pattern.copy()
                self.image_position = [0, 0]
                self.image_coords_section.setVisible(True)
                self.image_coords_section.set_collapsed(False)
                self.update_image_coordinates()
            else:
                self.image_on_grid = None
                self.image_coords_section.setVisible(False)

            if hasattr(self, "grid_generated") and self.grid_generated:
                self.generate_grid_button.setText("💾 Guardar Nuevo Tamaño")
                self.display_grid()
            else:
                self.generate_grid_button.setText("🎨 Generar Grid")
                self.grid_stats_section.setVisible(False)
                if hasattr(self, "ax"):
                    self.canvas.figure.clear()
                    self.ax = self.canvas.figure.add_subplot(111)
                    self.ax.set_facecolor("#1E1E1E" if self.dark_mode else "#FFFFFF")
                    self.ax.text(
                        0.5,
                        0.5,
                        'Presione "Generar Grid" para visualizar',
                        ha="center",
                        va="center",
                        fontsize=14,
                        color="#E0E0E0" if self.dark_mode else "#000000",
                    )
                    self.ax.set_xlim(0, 1)
                    self.ax.set_ylim(0, 1)
                    self.ax.axis("off")
                    self.canvas.draw()
        else:
            self.toggle_view_button.setText("📏 Vista Grid")
            self.grid_config_section.setVisible(False)
            self.grid_stats_section.setVisible(False)
            self.image_coords_section.setVisible(False)
            self.segmentation_section.setVisible(
                False
            )  # Ocultar segmentación en modo normal
            self.projection_control_section.setVisible(
                False
            )  # Ocultar control de proyección en modo normal
            self.toolbar.setVisible(False)  # Ocultar toolbar en modo normal

            if self.pattern is not None:
                self.simulate_optics()
            else:
                if hasattr(self, "ax"):
                    self.canvas.figure.clear()
                    self.ax = self.canvas.figure.add_subplot(111)
                    self.ax.set_facecolor("#1E1E1E" if self.dark_mode else "#FFFFFF")
                    self.ax.text(
                        0.5,
                        0.5,
                        "Cargue un patrón para comenzar",
                        ha="center",
                        va="center",
                        fontsize=14,
                        color="#E0E0E0" if self.dark_mode else "#000000",
                    )
                    self.ax.set_xlim(0, 1)
                    self.ax.set_ylim(0, 1)
                    self.ax.axis("off")
                    self.canvas.draw()

        # NO actualizar proyector automáticamente al cargar imagen
        # Solo se mostrará cuando se proyecten segmentos individuales
        # if self.projector_active and self.projection_window is not None:
        #     current_image = self._get_projection_image()
        #     if current_image is not None:
        #         self.projection_window.update_image(current_image)

        self._refresh_invert_button_state()


    def toggle_calibration_view(self):
        """Alterna entre vista normal y vista de calibración."""
        self.calibration_view_active = not self.calibration_view_active

        if self.calibration_view_active:
            # Desactivar vista grid si está activa
            if self.grid_view_active:
                self.toggle_grid_view()

            self.calibration_button.setText("🖼️ Vista Normal")
            self.show_calibration_interface()
        else:
            self.calibration_button.setText("🎯 Calibración")
            self.hide_calibration_interface()

            # Volver a mostrar vista normal
            if self.pattern is not None:
                self.simulate_optics()
            else:
                if hasattr(self, "ax"):
                    self.canvas.figure.clear()
                    self.ax = self.canvas.figure.add_subplot(111)
                    self.ax.set_facecolor("#1E1E1E" if self.dark_mode else "#FFFFFF")
                    self.ax.text(
                        0.5,
                        0.5,
                        "Cargue un patrón para comenzar",
                        ha="center",
                        va="center",
                        fontsize=14,
                        color="#E0E0E0" if self.dark_mode else "#000000",
                    )
                    self.ax.set_xlim(0, 1)
                    self.ax.set_ylim(0, 1)
                    self.ax.axis("off")
                    self.canvas.draw()


    def check_second_monitor(self):
        """
        Detecta el monitor secundario y gestiona dinámicamente la interfaz de proyección.
        Los campos de resolución se deshabilitan/ocultan si no hay monitor externo detectado.
        """
        screens = QApplication.screens()
        has_second = len(screens) > 1

        # Gestionar visibilidad y estado de campos relacionados con proyección
        if hasattr(self, "monitor_resolution_label"):
            if has_second:
                # Monitor secundario detectado - mostrar información con indicador verde
                secondary = screens[1]
                geometry = secondary.geometry()
                self.monitor_resolution_label.setText(
                    f"✓ Monitor proyección: {geometry.width()}x{geometry.height()}"
                )
                self.monitor_resolution_label.setStyleSheet(
                    "color: #00FF00;" if self.dark_mode else "color: #008800;"
                )
                self.monitor_resolution_label.setVisible(True)

                # Habilitar el botón de proyección
                if hasattr(self, "projector_button"):
                    self.projector_button.setEnabled(True)
                    self.projector_button.setToolTip(
                        "Activar/desactivar proyección en monitor secundario"
                    )
            else:
                # Sin monitor secundario - mostrar advertencia clara
                self.monitor_resolution_label.setText("⚠️ Monitor externo no detectado")
                self.monitor_resolution_label.setStyleSheet(
                    "color: #FF6B6B; font-weight: bold;"
                )
                self.monitor_resolution_label.setVisible(True)

                # Deshabilitar el botón de proyección si no hay proyección activa
                if hasattr(self, "projector_button"):
                    if not self.projector_active:
                        self.projector_button.setEnabled(False)
                        self.projector_button.setToolTip(
                            "⚠️ Conecte un monitor secundario para usar la proyección"
                        )

        # Gestionar campos de resolución proyectada
        if hasattr(self, "projected_resolution_label"):
            if has_second and self.projector_active:
                # Mostrar solo si hay monitor Y proyección activa
                self.projected_resolution_label.setVisible(True)
            else:
                # Ocultar si no hay monitor o no hay proyección
                self.projected_resolution_label.setVisible(False)

        # Gestionar escala de proyección
        if hasattr(self, "scale_info_label"):
            if has_second and self.projector_active:
                self.scale_info_label.setVisible(True)
            else:
                self.scale_info_label.setVisible(False)

        return has_second


    def _update_projection_resolution_fields(self, show):
        """
        Gestiona dinámicamente la visibilidad de los campos de resolución de proyección.

        Args:
            show (bool): True para mostrar los campos, False para ocultarlos
        """
        # Campo de resolución proyectada
        if hasattr(self, "projected_resolution_label"):
            self.projected_resolution_label.setVisible(show)

        # Campo de escala de proyección
        if hasattr(self, "scale_info_label"):
            self.scale_info_label.setVisible(show)

        # Si se ocultan, limpiar valores para evitar confusión
        if not show:
            if hasattr(self, "projected_resolution_label"):
                self.projected_resolution_label.setText("Resolución proyectada: -")
            if hasattr(self, "scale_info_label"):
                self.scale_info_label.setText("Escala proyección: -")


    def on_screen_changed(self):
        """
        Se llama cuando cambia la configuración de monitores.
        Actualiza dinámicamente la interfaz según disponibilidad del monitor.
        """
        has_monitor = self.check_second_monitor()

        # Si hay una proyección activa, actualizar su geometría
        if self.projection_window and self.projection_window.isVisible():
            screens = QApplication.screens()
            if len(screens) > 1:
                secondary_screen = screens[1]
            else:
                # Si se desconectó el monitor secundario durante la proyección
                if has_monitor:
                    secondary_screen = screens[0]
                else:
                    # Cerrar proyección si se perdió el monitor
                    QMessageBox.warning(
                        self,
                        "Monitor desconectado",
                        "El monitor secundario se desconectó.\n\n"
                        "La proyección se cerrará automáticamente.",
                    )
                    self.projector_active = False
                    self.projection_window.close()
                    self.projection_window = None
                    self.update_projector_button()
                    return

            geometry = secondary_screen.geometry()
            self.projection_window.screen_geometry = geometry
            self.projection_window.setGeometry(geometry)


    def show_exposure_section(self):
        self.exposure_section.setVisible(True)
        self.exposure_section.set_collapsed(False)
        self.frequency_section.setVisible(False)
        self.exposure_tab_button.setChecked(True)
        self.frequency_tab_button.setChecked(False)


    def show_frequency_section(self):
        self.exposure_section.setVisible(False)
        self.frequency_section.setVisible(True)
        self.frequency_section.set_collapsed(False)
        self.exposure_tab_button.setChecked(False)
        self.frequency_tab_button.setChecked(True)


    def showEvent(self, event):
        super().showEvent(event)
        self.set_dark_titlebar()


    def closeEvent(self, event):
        if self.projection_window is not None:
            self.projection_window.close()
            self.projection_window = None
        super().closeEvent(event)


    def customize_toolbar(self):
        """Personaliza la toolbar de matplotlib, eliminando botones innecesarios"""
        # Obtener todas las acciones
        actions = self.toolbar.actions()

        # Nombres de las acciones a eliminar
        actions_to_remove = ["Save", "Subplots", "Customize"]

        for action in actions:
            # Eliminar acciones no deseadas
            if action.text() in actions_to_remove:
                self.toolbar.removeAction(action)

        # Actualizar tooltips para hacerlos más descriptivos
        for action in self.toolbar.actions():
            if action.text() == "Home":
                action.setToolTip("🏠 Vista inicial")
            elif action.text() == "Back":
                action.setToolTip("◀ Retroceder vista")
            elif action.text() == "Forward":
                action.setToolTip("▶ Avanzar vista")
            elif action.text() == "Pan":
                action.setToolTip("✋ Mover/Zoom (Click: mover, Arrastrar: zoom)")

