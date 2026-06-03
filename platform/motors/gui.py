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
    QDialog
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
        main_layout.setContentsMargins(25, 25, 25, 25)
        main_layout.setSpacing(15)

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
        self.status_label = QLabel("🟢 Sistema Listo")
        self.status_label.setObjectName("statusLabel")
        
        self.unit_box = QLabel("Movimiento: 12.5 µm")
        self.unit_box.setObjectName("unitBox")
        self.unit_box.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        
        self.btn_prefs = QPushButton("⚙️ Preferencias")
        self.btn_prefs.setObjectName("btnPrefs")
        self.btn_prefs.clicked.connect(self.mostrar_preferencias)
        
        info_layout.addWidget(self.status_label)
        info_layout.addStretch()
        info_layout.addWidget(self.unit_box)
        info_layout.addWidget(self.btn_prefs)
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
        self.axis_sel.setMinimumHeight(45)

        multi_label = QLabel("MULTIPLICADOR (STEPS)")
        multi_label.setObjectName("controlLabel")
        self.multi_sel = QSpinBox()
        self.multi_sel.setRange(1, 10000)
        self.multi_sel.setValue(1)
        self.multi_sel.setMinimumHeight(45)
        self.multi_sel.valueChanged.connect(self.update_unit_display)

        config_layout.addWidget(axis_label, 0, 0)
        config_layout.addWidget(self.axis_sel, 1, 0)
        config_layout.addWidget(multi_label, 0, 1)
        config_layout.addWidget(self.multi_sel, 1, 1)
        
        main_layout.addWidget(config_frame)

        # --- BOTONES DE MOVIMIENTO ---
        move_layout = QHBoxLayout()
        move_layout.setSpacing(15)
        
        self.btn_left = QPushButton("⯇   IZQUIERDA (-)")
        self.btn_left.setObjectName("btnMove")
        self.btn_left.setMinimumHeight(70)
        self.btn_left.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        
        self.btn_right = QPushButton("DERECHA (+)   ⯈")
        self.btn_right.setObjectName("btnMove")
        self.btn_right.setMinimumHeight(70)
        self.btn_right.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)

        self.btn_left.clicked.connect(lambda: self.ejecutar_movimiento(-1))
        self.btn_right.clicked.connect(lambda: self.ejecutar_movimiento(1))

        move_layout.addWidget(self.btn_left)
        move_layout.addWidget(self.btn_right)
        main_layout.addLayout(move_layout)

        # Botones de giro de 360 grados
        move360_layout = QHBoxLayout()
        move360_layout.setSpacing(15)

        self.btn_360_left = QPushButton("⯇  360° (IZQ)")
        self.btn_360_left.setObjectName("btnMove360")
        self.btn_360_left.setMinimumHeight(50)
        self.btn_360_left.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        self.btn_360_left.clicked.connect(lambda: self.ejecutar_giro_completo(-1))

        self.btn_360_right = QPushButton("360° (DER)  ⯈")
        self.btn_360_right.setObjectName("btnMove360")
        self.btn_360_right.setMinimumHeight(50)
        self.btn_360_right.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        self.btn_360_right.clicked.connect(lambda: self.ejecutar_giro_completo(1))

        move360_layout.addWidget(self.btn_360_left)
        move360_layout.addWidget(self.btn_360_right)
        main_layout.addLayout(move360_layout)

        # --- BOTONES DE UTILIDAD ---
        util_layout = QHBoxLayout()
        util_layout.setSpacing(15)
        
        self.btn_zero = QPushButton("⌖ Set Zero")
        self.btn_zero.setObjectName("btnUtil")
        self.btn_zero.setMinimumHeight(45)
        self.btn_zero.clicked.connect(self.set_zero)
        
        self.btn_home = QPushButton("🏠 Origen")
        self.btn_home.setObjectName("btnUtilHome")
        self.btn_home.setMinimumHeight(45)
        self.btn_home.clicked.connect(self.volver_al_origen)

        self.btn_reconnect = QPushButton("🔌 Reconectar")
        self.btn_reconnect.setObjectName("btnUtil")
        self.btn_reconnect.setMinimumHeight(45)
        self.btn_reconnect.clicked.connect(self.reconectar)

        util_layout.addWidget(self.btn_reconnect)
        util_layout.addWidget(self.btn_zero)
        util_layout.addWidget(self.btn_home)
        main_layout.addLayout(util_layout)

        main_layout.addStretch()

        self.actualizar_pantalla()

    def mostrar_preferencias(self):
        dialog = QDialog(self)
        dialog.setWindowTitle("Preferencias de Motores")
        dialog.setFixedWidth(400)
        dialog.setWindowFlags(dialog.windowFlags() & ~Qt.WindowContextHelpButtonHint)
        
        try:
            if sys.platform == "win32":
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

        layout = QVBoxLayout(dialog)
        layout.setSpacing(15)
        layout.setContentsMargins(20, 20, 20, 20)

        title = QLabel("ASIGNACIÓN LÓGICO ➔ FÍSICO (HARDWARE)")
        title.setStyleSheet("font-size: 14px; font-weight: bold; color: #03DAC6; margin-bottom: 10px;")
        layout.addWidget(title)

        mapping_layout = QGridLayout()
        mapping_layout.setSpacing(10)

        self.map_combos = {}
        self.map_invs = {}
        self.map_steps_360 = {}

        mapping_layout.addWidget(QLabel("<b>Eje Lógico</b>"), 0, 0)
        mapping_layout.addWidget(QLabel("<b>Motor Físico</b>"), 0, 1)
        mapping_layout.addWidget(QLabel("<b>Invertir</b>"), 0, 2)
        mapping_layout.addWidget(QLabel("<b>Step 360°</b>"), 0, 3)

        for row, logical in enumerate(["X", "Y", "Z", "E"], start=1):
            lbl = QLabel(f"Eje {logical} ➔")
            
            combo = QComboBox()
            combo.addItems(["X", "Y", "Z", "E"])
            combo.setCurrentText(self.mapping[logical]["motor"])
            combo.currentTextChanged.connect(self.actualizar_mapping)
            self.map_combos[logical] = combo
            
            inv = QCheckBox("Invertir")
            inv.setChecked(self.mapping[logical]["invert"])
            inv.toggled.connect(self.actualizar_mapping)
            self.map_invs[logical] = inv
            
            steps_spin = QSpinBox()
            steps_spin.setRange(1, 100000)
            steps_spin.setValue(self.steps_360[logical])
            steps_spin.valueChanged.connect(self.actualizar_mapping)
            self.map_steps_360[logical] = steps_spin
            
            mapping_layout.addWidget(lbl, row, 0)
            mapping_layout.addWidget(combo, row, 1)
            mapping_layout.addWidget(inv, row, 2)
            mapping_layout.addWidget(steps_spin, row, 3)

        layout.addLayout(mapping_layout)
        
        btn_layout = QHBoxLayout()
        btn_layout.addStretch()
        close_btn = QPushButton("Cerrar")
        close_btn.clicked.connect(dialog.accept)
        btn_layout.addWidget(close_btn)
        
        layout.addLayout(btn_layout)
        
        dialog.setStyleSheet(self.styleSheet())
        dialog.exec_()

    def actualizar_mapping(self):
        for logical in ["X", "Y", "Z", "E"]:
            self.mapping[logical]["motor"] = self.map_combos[logical].currentText()
            self.mapping[logical]["invert"] = self.map_invs[logical].isChecked()
            self.steps_360[logical] = self.map_steps_360[logical].value()
            
        if self.on_mapping_changed:
            self.on_mapping_changed(self.mapping)
            
        if self.on_steps_360_changed:
            self.on_steps_360_changed(self.steps_360)
        
        # También pasamos la actualización al controlador para que lo use inmediatamente
        self.ctrl.set_mapping(self.mapping)
        
        self.status_label.setText("🟢 Asignación de Hardware Guardada")
        self.status_label.setStyleSheet("color: #03DAC6;")

    def apply_styles(self):
        style = """
            QWidget {
                background-color: #121212;
                color: #f0f0f0;
                font-family: "Segoe UI", "Roboto", "Helvetica Neue", sans-serif;
            }
            
            QFrame#screenFrame {
                background-color: #0A0A0A;
                border: 2px solid #2E2E2E;
                border-radius: 12px;
            }
            
            QLabel#odoTitle {
                color: #A0A0A0;
                font-size: 14px;
                font-weight: bold;
                letter-spacing: 2px;
            }
            
            QLabel#odoLabel {
                color: #03DAC6;
                font-family: "Consolas", "Courier New", monospace;
                font-size: 32px;
                font-weight: bold;
                line-height: 1.5;
            }
            
            QLabel#statusLabel {
                color: #03DAC6;
                font-size: 14px;
                font-weight: bold;
            }
            
            QLabel#unitBox {
                color: #E0E0E0;
                font-size: 14px;
                font-weight: bold;
            }
            
            QFrame#controlFrame {
                background-color: #1E1E1E;
                border-radius: 10px;
                border: 1px solid #2E2E2E;
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
                border: 1px solid #03DAC6;
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
            
            QPushButton#btnPrefs {
                background-color: transparent;
                border: 1px solid #2E2E2E;
                border-radius: 8px;
                color: #03DAC6;
                font-weight: bold;
            }
            QPushButton#btnPrefs:hover {
                background-color: #2C2C2C;
                border: 1px solid #03DAC6;
            }
            
            QPushButton#btnMove {
                background: qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 #03DAC6, stop:1 #018786);
                color: #121212;
                font-size: 16px;
                font-weight: 900;
                border: none;
                border-radius: 10px;
            }
            
            QPushButton#btnMove:hover {
                background: qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 #00E5CC, stop:1 #01A299);
            }
            
            QPushButton#btnMove:pressed {
                background: qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 #018786, stop:1 #016968);
            }
            
            QPushButton#btnMove360 {
                background-color: #1E1E1E;
                color: #03DAC6;
                font-size: 14px;
                font-weight: 900;
                border: 2px solid #03DAC6;
                border-radius: 10px;
            }
            
            QPushButton#btnMove360:hover {
                background-color: #03DAC6;
                color: #121212;
            }
            
            QPushButton#btnMove360:pressed {
                background-color: #00BFA5;
                color: #121212;
            }
            
            QPushButton#btnUtil {
                background-color: #1E1E1E;
                color: #A0A0A0;
                font-size: 14px;
                font-weight: bold;
                border: 1px solid #2E2E2E;
                border-radius: 8px;
            }
            
            QPushButton#btnUtil:hover {
                background-color: #2C2C2C;
                border: 1px solid #3E3E3E;
                color: #C0C0C0;
            }
            
            QPushButton#btnUtilHome {
                background-color: #1E1E1E;
                color: #F44336;
                font-size: 14px;
                font-weight: bold;
                border: 1px solid #F44336;
                border-radius: 8px;
            }
            
            QPushButton#btnUtilHome:hover {
                background-color: #F44336;
                color: #121212;
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
                border: 2px solid #03DAC6;
            }
            QCheckBox::indicator:checked {
                background-color: #03DAC6;
                border: 2px solid #03DAC6;
            }
        """
        self.setStyleSheet(style)


    def update_unit_display(self):
        val_mm = self.multi_sel.value() * 0.0125
        if val_mm < 1:
            self.unit_box.setText(f"Movimiento: {val_mm*1000:.1f} µm")
        elif val_mm < 10:
            self.unit_box.setText(f"Movimiento: {val_mm:.3f} mm")
        else:
            self.unit_box.setText(f"Movimiento: {val_mm/10:.2f} cm")

    def ejecutar_movimiento(self, direccion):
        eje = self.axis_sel.currentText()
        steps_base = direccion
        multiplicador = self.multi_sel.value()

        try:
            self.ctrl.step_move(eje, steps_base, multiplicador)
            self.status_label.setText("🟢 Movimiento Exitoso")
            self.status_label.setStyleSheet("color: #03DAC6;")
        except Exception:
            self.status_label.setText("⏳ Error detectado. Intentando Auto-Reconexión...")
            self.status_label.setStyleSheet("color: #FFC107;")
            self.repaint()
            
            if self.ctrl.reconnect():
                self.status_label.setText("🟢 Reconectado. Repita el comando por seguridad.")
                self.status_label.setStyleSheet("color: #03DAC6;")
            else:
                self.status_label.setText("🔴 Motor Desconectado (Fallo en puerto)")
                self.status_label.setStyleSheet("color: #F44336;")

    def ejecutar_giro_completo(self, direccion):
        eje = self.axis_sel.currentText()
        steps_totales = self.steps_360[eje] * direccion

        try:
            self.ctrl.step_move(eje, steps_totales, 1)
            self.status_label.setText(f"🟢 Giro Completo Exitoso en {eje}")
            self.status_label.setStyleSheet("color: #03DAC6;")
        except Exception:
            self.status_label.setText("⏳ Error detectado. Intentando Auto-Reconexión...")
            self.status_label.setStyleSheet("color: #FFC107;")
            self.repaint()
            
            if self.ctrl.reconnect():
                self.status_label.setText("🟢 Reconectado. Repita el comando por seguridad.")
                self.status_label.setStyleSheet("color: #03DAC6;")
            else:
                self.status_label.setText("🔴 Motor Desconectado (Fallo en puerto)")
                self.status_label.setStyleSheet("color: #F44336;")

    def actualizar_pantalla(self):
        eje = self.axis_sel.currentText()
        pasos_actuales = self.ctrl.positions.get(eje, 0)

        mm = pasos_actuales * 0.0125
        grados = pasos_actuales * 1.8

        self.odo_title.setText(f"EJE ACTIVO: {eje} | POSICIÓN ABSOLUTA")
        self.odo_label.setText(
            f"{pasos_actuales} Steps\n{mm:.3f} mm\n{grados:.1f}°"
        )

    def set_zero(self):
        eje = self.axis_sel.currentText()
        self.ctrl.set_zero(eje)
        self.status_label.setText(f"🟢 Cero establecido en eje {eje}")
        self.status_label.setStyleSheet("color: #a6e3a1;")

    def volver_al_origen(self):
        def _do_home():
            movimientos = self.ctrl.home_all()
            if movimientos == 0:
                self.status_label.setText("🟢 Ya está en el origen")
            else:
                self.status_label.setText("🟢 Regreso al origen completado")
            self.status_label.setStyleSheet("color: #03DAC6;")

        try:
            _do_home()
        except Exception:
            self.status_label.setText("⏳ Error detectado. Intentando Auto-Reconexión...")
            self.status_label.setStyleSheet("color: #FFC107;")
            self.repaint()
            
            if self.ctrl.reconnect():
                self.status_label.setText("🟢 Reconectado. Repita el comando por seguridad.")
                self.status_label.setStyleSheet("color: #03DAC6;")
            else:
                self.status_label.setText("🔴 Motor Desconectado (Fallo en puerto)")
                self.status_label.setStyleSheet("color: #F44336;")

    def reconectar(self):
        self.status_label.setText("⏳ Reconectando...")
        self.status_label.setStyleSheet("color: #FFC107;")
        self.repaint()  # Forzar UI a actualizar texto antes del bloqueo
        
        exito = self.ctrl.reconnect()
        if exito:
            self.status_label.setText("🟢 Reconexión Exitosa")
            self.status_label.setStyleSheet("color: #03DAC6;")
        else:
            self.status_label.setText("🔴 Fallo al Reconectar")
            self.status_label.setStyleSheet("color: #F44336;")
