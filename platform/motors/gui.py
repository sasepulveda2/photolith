import sys
import ctypes
from PyQt5.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QPushButton,
    QComboBox,
    QLabel,
    QSpinBox,
    QFrame,
    QGridLayout,
    QSizePolicy,
    QGroupBox,
    QCheckBox,
    QDialog,
    QDoubleSpinBox
)
from PyQt5.QtCore import Qt

class MotorGUI(QWidget):
    def __init__(self, controller, mapping=None, on_mapping_changed=None, steps_360=None, on_steps_360_changed=None):
        super().__init__()
        self.ctrl = controller
        self.mapping = mapping or {
            "X": {"motor": "X", "invert": False},
            "Y": {"motor": "Y", "invert": False},
            "Z": {"motor": "Z", "invert": False},
            "E": {"motor": "E", "invert": False}
        }
        self.on_mapping_changed = on_mapping_changed
        self.steps_360 = steps_360 or {"X": 3200, "Y": 3200, "Z": 640, "E": 3200}
        self.on_steps_360_changed = on_steps_360_changed
        
        # Suscribir la actualización de la pantalla a los cambios en el controlador
        original_callback = self.ctrl.on_positions_changed
        def _update_ui_callback(pos):
            if original_callback:
                original_callback(pos)
            self.actualizar_pantalla()
            
        self.ctrl.on_positions_changed = _update_ui_callback

        self.set_dark_titlebar()
        self.initUI()
        self.apply_styles()

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
            pass

    def initUI(self):
        self.setWindowTitle("Controlador de Motores - NanoFab")
        self.setMinimumSize(500, 480)
        
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(15, 15, 15, 15)
        main_layout.setSpacing(10)

        # --- PANTALLA PRINCIPAL (ODÓMETRO) ---
        self.screen_frame = QFrame()
        self.screen_frame.setObjectName("screenFrame")
        screen_layout = QVBoxLayout(self.screen_frame)
        screen_layout.setContentsMargins(20, 20, 20, 20)
        screen_layout.setSpacing(10)
        
        self.odo_title = QLabel("POSICIÓN ABSOLUTA")
        self.odo_title.setAlignment(Qt.AlignCenter)
        self.odo_title.setObjectName("odoTitle")
        
        self.odo_label = QLabel("0 Steps\n0.000 mm\n0.0°")
        self.odo_label.setAlignment(Qt.AlignCenter)
        self.odo_label.setObjectName("odoLabel")
        
        screen_layout.addWidget(self.odo_title)
        screen_layout.addWidget(self.odo_label)
        main_layout.addWidget(self.screen_frame)

        # --- PANEL DE ESTADO E INFO ---
        info_layout = QHBoxLayout()
        self.status_label = QLabel("Sistema listo")
        self.status_label.setObjectName("statusLabel")
        
        self.unit_box = QLabel("Movimiento: 12.5 µm")
        self.unit_box.setObjectName("unitBox")
        self.unit_box.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        
        info_layout.addWidget(self.status_label)
        info_layout.addStretch()
        info_layout.addWidget(self.unit_box)
        main_layout.addLayout(info_layout)

        # --- CONTROLES DE CONFIGURACIÓN ---
        config_frame = QFrame()
        config_frame.setObjectName("controlFrame")
        config_layout = QGridLayout(config_frame)
        config_layout.setContentsMargins(20, 20, 20, 20)
        config_layout.setSpacing(15)

        axis_label = QLabel("EJE ACTIVO")
        axis_label.setObjectName("controlLabel")
        self.axis_sel = QComboBox()
        self.axis_sel.addItems(["X", "Y", "Z", "E"])
        self.axis_sel.currentTextChanged.connect(self.actualizar_pantalla)
        self.axis_sel.setMinimumHeight(35)

        multi_label = QLabel("CANTIDAD A MOVER")
        multi_label.setObjectName("controlLabel")
        
        multi_layout = QHBoxLayout()
        multi_layout.setContentsMargins(0, 0, 0, 0)
        self.multi_sel = QDoubleSpinBox()
        self.multi_sel.setRange(0.001, 10000)
        self.multi_sel.setValue(1.0)
        self.multi_sel.setDecimals(3)
        self.multi_sel.setMinimumHeight(35)
        self.multi_sel.valueChanged.connect(self.update_unit_display)
        
        self.unit_sel = QComboBox()
        self.unit_sel.addItems(["Steps", "mm", "Grados"])
        self.unit_sel.setMinimumHeight(35)
        self.unit_sel.currentTextChanged.connect(self.update_unit_display)
        
        multi_layout.addWidget(self.multi_sel, stretch=2)
        multi_layout.addWidget(self.unit_sel, stretch=1)

        config_layout.addWidget(axis_label, 0, 0)
        config_layout.addWidget(self.axis_sel, 1, 0)
        config_layout.addWidget(multi_label, 0, 1)
        config_layout.addLayout(multi_layout, 1, 1)
        
        main_layout.addWidget(config_frame)

        # --- BOTONES DE MOVIMIENTO ---
        move_layout = QHBoxLayout()
        move_layout.setSpacing(15)
        
        self.btn_left = QPushButton("IZQUIERDA (-)")
        self.btn_left.setObjectName("btnMove")
        self.btn_left.setMinimumHeight(45)
        self.btn_left.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        
        self.btn_right = QPushButton("DERECHA (+)")
        self.btn_right.setObjectName("btnMove")
        self.btn_right.setMinimumHeight(45)
        self.btn_right.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)

        self.btn_left.clicked.connect(lambda: self.ejecutar_movimiento(-1))
        self.btn_right.clicked.connect(lambda: self.ejecutar_movimiento(1))

        move_layout.addWidget(self.btn_left)
        move_layout.addWidget(self.btn_right)
        main_layout.addLayout(move_layout)

        # Botones de giro de 360 grados
        move360_layout = QHBoxLayout()
        move360_layout.setSpacing(15)

        self.btn_360_left = QPushButton("360° (IZQ)")
        self.btn_360_left.setObjectName("btnMove360")
        self.btn_360_left.setMinimumHeight(35)
        self.btn_360_left.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        self.btn_360_left.clicked.connect(lambda: self.ejecutar_giro_completo(-1))

        self.btn_360_right = QPushButton("360° (DER)")
        self.btn_360_right.setObjectName("btnMove360")
        self.btn_360_right.setMinimumHeight(35)
        self.btn_360_right.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        self.btn_360_right.clicked.connect(lambda: self.ejecutar_giro_completo(1))

        move360_layout.addWidget(self.btn_360_left)
        move360_layout.addWidget(self.btn_360_right)
        main_layout.addLayout(move360_layout)

        # --- BOTONES DE UTILIDAD ---
        util_layout = QHBoxLayout()
        util_layout.setSpacing(15)
        
        self.btn_zero = QPushButton("Set Zero")
        self.btn_zero.setObjectName("btnUtil")
        self.btn_zero.setMinimumHeight(35)
        self.btn_zero.clicked.connect(self.set_zero)
        
        self.btn_home = QPushButton("Origen")
        self.btn_home.setObjectName("btnUtilHome")
        self.btn_home.setMinimumHeight(35)
        self.btn_home.clicked.connect(self.volver_al_origen)

        self.btn_reconnect = QPushButton(" Reconectar")
        self.btn_reconnect.setObjectName("btnUtil")
        self.btn_reconnect.setMinimumHeight(35)
        self.btn_reconnect.clicked.connect(self.reconectar)

        util_layout.addWidget(self.btn_reconnect)
        util_layout.addWidget(self.btn_zero)
        util_layout.addWidget(self.btn_home)
        main_layout.addLayout(util_layout)

        main_layout.addStretch()

        self.actualizar_pantalla()

    def apply_styles(self):
        style = """
            QWidget {
                background-color: #121212;
                color: #f0f0f0;
                font-family: 'Helvetica Neue', Helvetica, Arial, sans-serif;
            }
            
            QFrame#screenFrame {
                background-color: #0A0A0A;
                border: 1px solid #2E2E2E;
                border-radius: 6px;
            }
            
            QLabel#odoTitle {
                color: #808080;
                font-size: 12px;
                font-weight: bold;
                letter-spacing: 1px;
            }
            
            QLabel#odoLabel {
                color: #C0C0C0;
                font-family: 'Roboto Mono', Consolas, monospace;
                font-size: 20px;
                font-weight: 500;
                line-height: 1.2;
            }
            
            QLabel#statusLabel {
                color: #888888;
                font-size: 12px;
                font-weight: normal;
            }
            
            QLabel#unitBox {
                color: #A0A0A0;
                font-size: 12px;
                font-weight: normal;
            }
            
            QFrame#controlFrame {
                background-color: #161616;
                border-radius: 6px;
                border: 1px solid #262626;
            }
            
            QLabel#controlLabel {
                color: #A0A0A0;
                font-size: 12px;
                font-weight: 800;
            }
            
            QComboBox, QSpinBox {
                background-color: #121212;
                color: #f0f0f0;
                border: 1px solid #2E2E2E;
                border-radius: 6px;
                padding: 5px 15px;
                font-size: 16px;
                font-weight: bold;
            }
            
            QComboBox::drop-down {
                border: none;
                width: 30px;
            }
            
            QComboBox:hover, QSpinBox:hover {
                border: 1px solid #A0A0A0;
            }
            
            QSpinBox::up-button, QSpinBox::down-button {
                width: 30px;
                background-color: #2E2E2E;
                border-radius: 4px;
                margin: 2px;
            }
            
            QSpinBox::up-button:hover, QSpinBox::down-button:hover {
                background-color: #3E3E3E;
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
            
            QPushButton#btnMove {
                background-color: #262626;
                color: #E0E0E0;
                font-size: 13px;
                font-weight: 600;
                border: 1px solid #404040;
                border-radius: 6px;
            }
            
            QPushButton#btnMove:hover {
                background-color: #333333;
                border: 1px solid #606060;
            }
            
            QPushButton#btnMove:pressed {
                background-color: #1E1E1E;
            }
            
            QPushButton#btnMove360 {
                background-color: #1A1A1A;
                color: #A0A0A0;
                font-size: 12px;
                font-weight: 500;
                border: 1px solid #3E3E3E;
                border-radius: 6px;
            }
            
            QPushButton#btnMove360:hover {
                background-color: #242424;
                color: #E0E0E0;
            }
            
            QPushButton#btnMove360:pressed {
                background-color: #121212;
            }
            
            QPushButton#btnUtil {
                background-color: #1A1A1A;
                color: #A0A0A0;
                font-size: 12px;
                font-weight: 500;
                border: 1px solid #2E2E2E;
                border-radius: 6px;
            }
            
            QPushButton#btnUtil:hover {
                background-color: #242424;
                border: 1px solid #3E3E3E;
                color: #C0C0C0;
            }
            
            QPushButton#btnUtilHome {
                background-color: #1A1A1A;
                color: #D32F2F;
                font-size: 12px;
                font-weight: 500;
                border: 1px solid #5C1D1D;
                border-radius: 6px;
            }
            
            QPushButton#btnUtilHome:hover {
                background-color: #2B1515;
            }
            
            /* Controles Checkbox para Preferencias */
            QCheckBox {
                color: #E0E0E0;
            }
            QCheckBox::indicator {
                width: 18px;
                height: 18px;
                border-radius: 4px;
                border: 2px solid #3E3E3E;
                background-color: #1E1E1E;
            }
            QCheckBox::indicator:hover {
                border: 2px solid #A0A0A0;
            }
            QCheckBox::indicator:checked {
                background-color: #A0A0A0;
                border: 2px solid #A0A0A0;
            }
        """
        self.setStyleSheet(style)


    def update_unit_display(self):
        valor = self.multi_sel.value()
        unidad = self.unit_sel.currentText()
        eje = self.axis_sel.currentText()
        
        steps_per_rev = self.steps_360.get(eje, 3200)
        steps_per_mm = 2 * steps_per_rev
        
        if unidad == "Steps":
            steps = int(valor)
            mm = steps / steps_per_mm
            grados = steps * (360.0 / steps_per_rev)
            self.unit_box.setText(f"Movimiento: {steps} Steps | {mm:.3f} mm | {grados:.1f}°")
        elif unidad == "mm":
            mm = valor
            steps = int(mm * steps_per_mm)
            grados = steps * (360.0 / steps_per_rev)
            self.unit_box.setText(f"Movimiento: {mm:.3f} mm | {steps} Steps | {grados:.1f}°")
        elif unidad == "Grados":
            grados = valor
            steps = int(grados / (360.0 / steps_per_rev))
            mm = steps / steps_per_mm
            self.unit_box.setText(f"Movimiento: {grados:.1f}° | {steps} Steps | {mm:.3f} mm")

    def ejecutar_movimiento(self, direccion):
        eje = self.axis_sel.currentText()
        valor = self.multi_sel.value()
        unidad = self.unit_sel.currentText()
        
        steps_per_rev = self.steps_360.get(eje, 3200)
        steps_per_mm = 2 * steps_per_rev
        
        if unidad == "Steps":
            steps_totales = int(valor) * direccion
        elif unidad == "mm":
            steps_totales = int(valor * steps_per_mm) * direccion
        elif unidad == "Grados":
            steps_totales = int(valor / (360.0 / steps_per_rev)) * direccion

        feedrate = self.feedrates.get(eje, 5000)

        try:
            self.ctrl.step_move(eje, steps_totales, 1, feedrate=feedrate)
            self.status_label.setText(f"Movimiento exitoso: {steps_totales} steps")
            self.status_label.setStyleSheet("color: #A0A0A0;")
        except Exception:
            self.status_label.setText("Error detectado. Intentando reconexión...")
            self.status_label.setStyleSheet("color: #FFC107;")
            self.repaint()
            
            if self.ctrl.reconnect():
                self.status_label.setText("Reconectado.")
                self.status_label.setStyleSheet("color: #A0A0A0;")
            else:
                self.status_label.setText("Motor desconectado")
                self.status_label.setStyleSheet("color: #F44336;")

    def ejecutar_giro_completo(self, direccion):
        eje = self.axis_sel.currentText()
        steps_totales = self.steps_360[eje] * direccion
        feedrate = self.feedrates.get(eje, 5000)

        try:
            self.ctrl.step_move(eje, steps_totales, 1, feedrate=feedrate)
            self.status_label.setText(f"Giro completo exitoso en {eje}")
            self.status_label.setStyleSheet("color: #A0A0A0;")
        except Exception:
            self.status_label.setText("Error detectado. Intentando reconexión...")
            self.status_label.setStyleSheet("color: #FFC107;")
            self.repaint()
            
            if self.ctrl.reconnect():
                self.status_label.setText("Reconectado.")
                self.status_label.setStyleSheet("color: #A0A0A0;")
            else:
                self.status_label.setText("Motor desconectado")
                self.status_label.setStyleSheet("color: #F44336;")

    def actualizar_pantalla(self):
        eje = self.axis_sel.currentText()
        pasos_actuales = self.ctrl.positions.get(eje, 0)

        steps_per_rev = self.steps_360.get(eje, 3200)
        steps_per_mm = 2 * steps_per_rev

        mm = pasos_actuales / steps_per_mm if steps_per_mm else 0
        grados = pasos_actuales * (360.0 / steps_per_rev) if steps_per_rev else 0

        self.odo_title.setText(f"EJE ACTIVO: {eje} | POSICIÓN ABSOLUTA")
        self.odo_label.setText(
            f"{pasos_actuales} Steps\n{mm:.3f} mm\n{grados:.1f}°"
        )
        self.update_unit_display()

    def set_zero(self):
        eje = self.axis_sel.currentText()
        self.ctrl.set_zero(eje)
        self.status_label.setText(f"Cero establecido en eje {eje}")
        self.status_label.setStyleSheet("color: #a6e3a1;")

    def volver_al_origen(self):
        def _do_home():
            movimientos = self.ctrl.home_all()
            if movimientos == 0:
                self.status_label.setText("Ya está en el origen")
            else:
                self.status_label.setText("Regreso al origen completado")
            self.status_label.setStyleSheet("color: #A0A0A0;")

        try:
            _do_home()
        except Exception:
            self.status_label.setText("Error detectado. Intentando reconexión...")
            self.status_label.setStyleSheet("color: #FFC107;")
            self.repaint()
            
            if self.ctrl.reconnect():
                self.status_label.setText("Reconectado.")
                self.status_label.setStyleSheet("color: #A0A0A0;")
            else:
                self.status_label.setText("Motor desconectado")
                self.status_label.setStyleSheet("color: #F44336;")

    def reconectar(self):
        self.status_label.setText("Reconectando...")
        self.status_label.setStyleSheet("color: #FFC107;")
        self.repaint()  # Forzar UI a actualizar texto antes del bloqueo
        
        exito = self.ctrl.reconnect()
        if exito:
            self.status_label.setText("Reconexión exitosa")
            self.status_label.setStyleSheet("color: #A0A0A0;")
        else:
            self.status_label.setText("Fallo al Reconectar")
            self.status_label.setStyleSheet("color: #F44336;")


class MotorPreferencesGUI(QWidget):
    def __init__(self, controller, mapping=None, on_mapping_changed=None, steps_360=None, on_steps_360_changed=None, feedrates=None, on_feedrates_changed=None):
        super().__init__()
        self.ctrl = controller
        self.mapping = mapping or {"X": {"motor": "X", "invert": False}, "Y": {"motor": "Y", "invert": False}, "Z": {"motor": "Z", "invert": False}, "E": {"motor": "E", "invert": False}}
        self.on_mapping_changed = on_mapping_changed
        self.steps_360 = steps_360 or {"X": 3200, "Y": 3200, "Z": 640, "E": 3200}
        self.on_steps_360_changed = on_steps_360_changed
        self.feedrates = feedrates or {"X": 5000, "Y": 5000, "Z": 500, "E": 5000}
        self.on_feedrates_changed = on_feedrates_changed

        self.initUI()
        self.apply_styles()

    def initUI(self):
        from PyQt5.QtWidgets import QVBoxLayout, QLabel, QScrollArea, QWidget, QGroupBox, QGridLayout, QComboBox, QCheckBox, QSpinBox, QFormLayout, QPushButton
        from PyQt5.QtCore import Qt

        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(15, 15, 15, 15)
        main_layout.setSpacing(15)

        title = QLabel("Preferencias de motores")
        title.setAlignment(Qt.AlignCenter)
        title.setStyleSheet("color: #A0A0A0; font-size: 16px; font-weight: bold; margin-bottom: 10px;")
        main_layout.addWidget(title)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setStyleSheet("QScrollArea { border: none; background: transparent; }")
        
        content_widget = QWidget()
        layout = QVBoxLayout(content_widget)
        layout.setContentsMargins(0, 0, 0, 0)
        
        # Mapeo de Ejes
        gb_map = QGroupBox("Mapeo Físico de Ejes")
        gb_map.setStyleSheet("QGroupBox { color: #A0A0A0; font-weight: bold; border: 1px solid #2E2E2E; border-radius: 8px; margin-top: 10px; padding-top: 15px; } QGroupBox::title { subcontrol-origin: margin; left: 10px; }")
        mapping_layout = QGridLayout(gb_map)
        mapping_layout.addWidget(QLabel("Lógico"), 0, 0)
        mapping_layout.addWidget(QLabel("Físico"), 0, 1)
        mapping_layout.addWidget(QLabel("Invertir"), 0, 2)

        self.map_combos = {}
        self.map_invs = {}
        
        for i, logical in enumerate(["X", "Y", "Z", "E"]):
            mapping_layout.addWidget(QLabel(f"Eje {logical}:"), i+1, 0)
            
            cb = QComboBox()
            cb.addItems(["X", "Y", "Z", "E"])
            cb.setCurrentText(self.mapping[logical]["motor"])
            cb.currentTextChanged.connect(self.actualizar_config)
            self.map_combos[logical] = cb
            mapping_layout.addWidget(cb, i+1, 1)
            
            chk = QCheckBox()
            chk.setChecked(self.mapping[logical]["invert"])
            chk.stateChanged.connect(self.actualizar_config)
            self.map_invs[logical] = chk
            mapping_layout.addWidget(chk, i+1, 2)

        layout.addWidget(gb_map)

        # Pasos por 360
        gb_steps = QGroupBox("Mecánica (Pasos por 360°)")
        gb_steps.setStyleSheet(gb_map.styleSheet())
        steps_layout = QFormLayout(gb_steps)
        self.map_steps_360 = {}
        
        for logical in ["X", "Y", "Z", "E"]:
            sb = QSpinBox()
            sb.setRange(100, 100000)
            sb.setSingleStep(100)
            sb.setValue(self.steps_360.get(logical, 3200))
            sb.valueChanged.connect(self.actualizar_config)
            sb.setEnabled(False)  # Por seguridad, no se modifica por defecto
            sb.setToolTip("Pasos por revolución. Normalmente configurado a nivel firmware.")
            self.map_steps_360[logical] = sb
            steps_layout.addRow(f"Eje {logical}:", sb)
            
        layout.addWidget(gb_steps)

        # Feedrates
        gb_feed = QGroupBox("Feedrates (Velocidad G-Code)")
        gb_feed.setStyleSheet(gb_map.styleSheet())
        feed_layout = QFormLayout(gb_feed)
        
        self.btn_unlock = QPushButton("Desbloquear Velocidades")
        self.btn_unlock.setCheckable(True)
        self.btn_unlock.setStyleSheet("QPushButton:checked { background-color: #F44336; color: white; border: none; }")
        self.btn_unlock.toggled.connect(self.toggle_feedrates)
        feed_layout.addRow(self.btn_unlock)

        self.map_feedrates = {}
        for logical in ["X", "Y", "Z", "E"]:
            sb = QSpinBox()
            sb.setRange(10, 50000)
            sb.setSingleStep(100)
            sb.setValue(self.feedrates.get(logical, 5000))
            sb.setEnabled(False)
            sb.valueChanged.connect(self.actualizar_config)
            self.map_feedrates[logical] = sb
            feed_layout.addRow(f"Eje {logical}:", sb)

        layout.addWidget(gb_feed)

        layout.addStretch()
        scroll.setWidget(content_widget)
        main_layout.addWidget(scroll)

    def toggle_feedrates(self, checked):
        for sb in self.map_feedrates.values():
            sb.setEnabled(checked)
        if checked:
            self.btn_unlock.setText("Bloquear Velocidades")
        else:
            self.btn_unlock.setText("Desbloquear Velocidades")

    def actualizar_config(self):
        for logical in ["X", "Y", "Z", "E"]:
            self.mapping[logical]["motor"] = self.map_combos[logical].currentText()
            self.mapping[logical]["invert"] = self.map_invs[logical].isChecked()
            self.steps_360[logical] = self.map_steps_360[logical].value()
            self.feedrates[logical] = self.map_feedrates[logical].value()
            
        if self.on_mapping_changed:
            self.on_mapping_changed(self.mapping)
        if self.on_steps_360_changed:
            self.on_steps_360_changed(self.steps_360)
        if self.on_feedrates_changed:
            self.on_feedrates_changed(self.feedrates)
        
        self.ctrl.set_mapping(self.mapping)

    def apply_styles(self):
        style = """
            QWidget {
                background-color: #121212;
                color: #f0f0f0;
                font-family: "Segoe UI", "Roboto", "Helvetica Neue", sans-serif;
            }
            QComboBox, QSpinBox {
                background-color: #1E1E1E;
                color: #f0f0f0;
                border: 1px solid #2E2E2E;
                border-radius: 4px;
                padding: 4px;
            }
            QComboBox:hover, QSpinBox:hover {
                border: 1px solid #A0A0A0;
            }
            QPushButton {
                background-color: #1E1E1E;
                border: 1px solid #2E2E2E;
                border-radius: 6px;
                padding: 6px;
                color: #E0E0E0;
            }
            QPushButton:hover {
                background-color: #2C2C2C;
                border: 1px solid #3E3E3E;
            }
        """
        self.setStyleSheet(style)
