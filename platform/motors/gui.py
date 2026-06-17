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
    def __init__(self, controller, mapping=None, on_mapping_changed=None, steps_360=None, on_steps_360_changed=None, feedrates=None, on_feedrates_changed=None, arrow_updown_axis="Y", on_arrow_axis_changed=None, keyboard_mode="set_movement"):
        super().__init__()
        self.ctrl = controller
        self.arrow_updown_axis = arrow_updown_axis
        self.on_arrow_axis_changed = on_arrow_axis_changed
        self.keyboard_mode = keyboard_mode
        self.mapping = mapping or {
            "X": {"motor": "X", "invert": False},
            "Y": {"motor": "Y", "invert": False},
            "Z": {"motor": "Z", "invert": False},
            "E": {"motor": "E", "invert": False}
        }
        self.on_mapping_changed = on_mapping_changed
        self.steps_360 = steps_360 or {"X": 3200, "Y": 3200, "Z": 640, "E": 3200}
        self.on_steps_360_changed = on_steps_360_changed
        self.feedrates = feedrates or {"X": 5000, "Y": 5000, "Z": 500, "E": 5000}
        self.on_feedrates_changed = on_feedrates_changed
        
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
        self.setWindowTitle("Controlador de motores")
        
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

        # Botón de emergencia
        self.btn_stop = QPushButton("Stop")
        self.btn_stop.setObjectName("btnStop")
        self.btn_stop.setMinimumHeight(45)
        self.btn_stop.setStyleSheet("""
            QPushButton#btnStop {
                background-color: #D32F2F;
                color: white;
                font-size: 14px;
                font-weight: bold;
                border: 1px solid #B71C1C;
                border-radius: 6px;
                margin-top: 10px;
            }
            QPushButton#btnStop:hover { background-color: #F44336; }
            QPushButton#btnStop:pressed { background-color: #B71C1C; }
        """)
        self.btn_stop.clicked.connect(self.detener_motor)
        main_layout.addWidget(self.btn_stop)

        main_layout.addStretch()

        from PyQt5.QtCore import QTimer
        self.poll_timer = QTimer(self)
        self.poll_timer.timeout.connect(self.actualizar_pantalla)
        self.poll_timer.start(50)
        self.actualizar_pantalla()

        # Atajos de Teclado
        from PyQt5.QtWidgets import QShortcut
        from PyQt5.QtGui import QKeySequence
        
        QShortcut(QKeySequence(Qt.Key_Left), self).activated.connect(lambda: self.arrow_move("X", -1))
        QShortcut(QKeySequence(Qt.Key_Right), self).activated.connect(lambda: self.arrow_move("X", 1))
        QShortcut(QKeySequence(Qt.Key_Up), self).activated.connect(lambda: self.arrow_move(self.arrow_updown_axis, 1))
        QShortcut(QKeySequence(Qt.Key_Down), self).activated.connect(lambda: self.arrow_move(self.arrow_updown_axis, -1))

    def arrow_move(self, eje, direccion):
        if not eje: return
        if getattr(self, "keyboard_mode", "set_movement") == "360":
            self.ejecutar_giro_completo(direccion, eje_forzado=eje)
        else:
            self.ejecutar_movimiento(direccion, eje_forzado=eje)

    def actualizar_config_limites(self):
        enabled = self.chk_limits.isChecked()
        self.ctrl.enable_limits(enabled)
        # We need a callback to save settings in main.py/system_functions.py
        if hasattr(self.ctrl, "on_limits_enabled_changed") and self.ctrl.on_limits_enabled_changed:
            self.ctrl.on_limits_enabled_changed(enabled)

    def actualizar_config_backlash(self):
        if hasattr(self.ctrl, "backlash_enabled"):
            self.ctrl.backlash_enabled = self.chk_backlash.isChecked()
        if hasattr(self.ctrl, "backlash"):
            for logical in ["X", "Y", "Z"]:
                self.ctrl.backlash[logical] = self.map_backlash[logical].value()
        self._guardar_preferencias()
            
    def fijar_origen(self, axis):
        self.ctrl.set_zero(axis)

    def _format_limit_label(self, axis, val):
        if val is None:
            return "Sin límite"
        steps_per_rev = self.steps_360.get(axis, 3200)
        steps_per_mm = 2 * steps_per_rev
        if steps_per_mm > 0:
            mm = val / steps_per_mm
            return f"Máx: {val} Steps ({mm:.3f} mm)"
        return f"Máx: {val} Steps"

    def _guardar_preferencias(self):
        import json
        import os
        cfg = {}
        if os.path.exists("motor_settings.json"):
            try:
                with open("motor_settings.json", "r") as f:
                    cfg = json.load(f)
            except:
                pass
                
        cfg["mapping"] = self.mapping
        cfg["steps_360"] = self.steps_360
        cfg["feedrates"] = self.feedrates
        if hasattr(self.ctrl, "limits"):
            cfg["limits"] = self.ctrl.limits
        if hasattr(self.ctrl, "limits_enabled"):
            cfg["limits_enabled"] = self.ctrl.limits_enabled
        if hasattr(self.ctrl, "backlash"):
            cfg["backlash_mm"] = self.ctrl.backlash
        if hasattr(self.ctrl, "backlash_enabled"):
            cfg["backlash_enabled"] = self.ctrl.backlash_enabled
            
        try:
            with open("motor_settings.json", "w") as f:
                json.dump(cfg, f, indent=4)
        except Exception as e:
            print(f"Error al guardar config: {e}")

    def fijar_limite_max(self, eje):
        self.ctrl.set_limit(eje)
        val = self.ctrl.limits.get(eje)
        self.lbl_limits[eje].setText(self._format_limit_label(eje, val))

    def volver_al_origen_eje(self, eje):
        if not self.ctrl.ser:
            return
        current_steps = self.ctrl.positions.get(eje, 0)
        if current_steps == 0:
            return
        feedrate = self.feedrates.get(eje, 3000)
        try:
            self.ctrl.step_move(eje, -current_steps, 1, feedrate=feedrate, ignore_limits=True)
        except Exception as e:
            return

    def apply_styles(self):
        # El estilo ahora se hereda de los temas globales
        pass


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

    def ejecutar_movimiento(self, direccion, eje_forzado=None):
        eje = eje_forzado or self.axis_sel.currentText()
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
        except Exception as e:
            if not isinstance(e, ValueError):
                import traceback
                traceback.print_exc()
            self.status_label.setText(f"Error: {e}")
            self.status_label.setStyleSheet("color: #FFC107;")
            self.repaint()
            if not isinstance(e, ValueError):
                if self.ctrl.reconnect():
                    self.status_label.setText("Reconectado.")
                    self.status_label.setStyleSheet("color: #A0A0A0;")
                else:
                    self.status_label.setText("Motor desconectado")
                    self.status_label.setStyleSheet("color: #F44336;")

    def ejecutar_giro_completo(self, direccion, eje_forzado=None):
        eje = eje_forzado or self.axis_sel.currentText()
        steps_totales = self.steps_360[eje] * direccion
        feedrate = self.feedrates.get(eje, 5000)

        try:
            self.ctrl.step_move(eje, steps_totales, 1, feedrate=feedrate)
            self.status_label.setText(f"Giro completo exitoso en {eje}")
            self.status_label.setStyleSheet("color: #A0A0A0;")
        except Exception as e:
            if not isinstance(e, ValueError):
                import traceback
                traceback.print_exc()
            self.status_label.setText(f"Error: {e}")
            self.status_label.setStyleSheet("color: #FFC107;")
            self.repaint()
            if not isinstance(e, ValueError):
                if self.ctrl.reconnect():
                    self.status_label.setText("Reconectado.")
                    self.status_label.setStyleSheet("color: #A0A0A0;")
                else:
                    self.status_label.setText("Motor desconectado")
                    self.status_label.setStyleSheet("color: #F44336;")

    def actualizar_pantalla(self):
        if not hasattr(self, "_display_positions"):
            self._display_positions = {}
            
        for axis in ["X", "Y", "Z", "E"]:
            true_pos = self.ctrl.positions.get(axis, 0)
            disp_pos = self._display_positions.get(axis, true_pos)
            
            if disp_pos != true_pos:
                feedrate = self.feedrates.get(axis, 3000)
                speed_steps_s = (feedrate / 60.0) / self.ctrl.step_size
                max_delta = speed_steps_s * 0.05
                if abs(true_pos - disp_pos) <= max_delta:
                    self._display_positions[axis] = true_pos
                else:
                    direction = 1 if true_pos > disp_pos else -1
                    self._display_positions[axis] += direction * max_delta
            
            if axis == self.axis_sel.currentText():
                steps_per_rev = self.steps_360.get(axis, 3200)
                steps_per_mm = 2 * steps_per_rev
                disp_pos = self._display_positions.get(axis, true_pos)
                mm = disp_pos / steps_per_mm if steps_per_mm > 0 else 0
                deg = disp_pos * 1.8
                self.odo_title.setText(f"EJE ACTIVO: {axis} | POSICIÓN ABSOLUTA")
                self.odo_label.setText(f"{disp_pos:.0f} Steps\n{mm:.3f} mm\n{deg:.1f}°")
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
        except Exception as e:
            import traceback
            traceback.print_exc()
            self.status_label.setText(f"Error: {e}")
            self.status_label.setStyleSheet("color: #FFC107;")
            self.repaint()
            if not isinstance(e, ValueError):
                if self.ctrl.reconnect():
                    self.status_label.setText("Reconectado.")
                    self.status_label.setStyleSheet("color: #A0A0A0;")
                else:
                    self.status_label.setText("Motor desconectado")
                    self.status_label.setStyleSheet("color: #F44336;")

    def detener_motor(self):
        self.ctrl.emergency_stop()
        if hasattr(self.ctrl, "sync_position_from_hardware"):
            self.ctrl.sync_position_from_hardware()
        if hasattr(self, "_display_positions"):
            for axis in ["X", "Y", "Z", "E"]:
                self._display_positions[axis] = self.ctrl.positions.get(axis, 0)
        self.status_label.setText("Parada de emergencia (Movimiento cancelado en seco)")
        self.status_label.setStyleSheet("color: #F44336;")
        self.actualizar_pantalla()

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
    def __init__(self, controller, keyboard_mode="set_movement", on_keyboard_mode_changed=None, mapping=None, on_mapping_changed=None, steps_360=None, on_steps_360_changed=None, feedrates=None, on_feedrates_changed=None, max_feedrates=None, on_max_feedrates_changed=None, arrow_updown_axis="Y", on_arrow_axis_changed=None, backlash_steps=None, on_backlash_steps_changed=None, backlash_enabled=True, on_backlash_enabled_changed=None):
        super().__init__()
        self.ctrl = controller
        self.keyboard_mode = keyboard_mode
        self.on_keyboard_mode_changed = on_keyboard_mode_changed
        self.arrow_updown_axis = arrow_updown_axis
        self.on_arrow_axis_changed = on_arrow_axis_changed
        self.backlash_steps = backlash_steps or {"X": 0, "Y": 0, "Z": 0, "E": 0}
        self.on_backlash_steps_changed = on_backlash_steps_changed
        self.backlash_enabled = backlash_enabled
        self.on_backlash_enabled_changed = on_backlash_enabled_changed
        
        self.mapping = mapping or {"X": {"motor": "X", "invert": False}, "Y": {"motor": "Y", "invert": False}, "Z": {"motor": "Z", "invert": False}, "E": {"motor": "E", "invert": False}}
        self.on_mapping_changed = on_mapping_changed
        self.steps_360 = steps_360 or {"X": 3200, "Y": 3200, "Z": 640, "E": 3200}
        self.on_steps_360_changed = on_steps_360_changed
        self.feedrates = feedrates or {"X": 5000, "Y": 5000, "Z": 500, "E": 5000}
        self.on_feedrates_changed = on_feedrates_changed
        self.max_feedrates = max_feedrates or {"X": 5000, "Y": 5000, "Z": 500, "E": 5000}
        self.on_max_feedrates_changed = on_max_feedrates_changed

        self.initUI()
        self.apply_styles()

    def initUI(self):
        from PyQt5.QtWidgets import QVBoxLayout, QLabel, QScrollArea, QWidget, QGroupBox, QGridLayout, QComboBox, QCheckBox, QSpinBox, QFormLayout, QPushButton, QHBoxLayout
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
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        scroll.setStyleSheet("QScrollArea { border: none; background: transparent; }")
        
        content_widget = QWidget()
        layout = QVBoxLayout(content_widget)
        layout.setContentsMargins(0, 0, 0, 0)
        
        # Mapeo de Ejes
        gb_map = QGroupBox("Mapeo Físico de Ejes")
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
        feed_layout = QFormLayout(gb_feed)
        
        self.btn_unlock = QPushButton("Desbloquear Velocidades")
        self.btn_unlock.setCheckable(True)
        self.btn_unlock.setStyleSheet("QPushButton:checked { background-color: #F44336; color: white; border: none; }")
        self.btn_unlock.toggled.connect(self.toggle_feedrates)
        feed_layout.addRow(self.btn_unlock)

        self.map_feedrates = {}
        self.map_max_feedrates = {}
        
        for logical in ["X", "Y", "Z", "E"]:
            row_layout = QHBoxLayout()
            
            sb = QSpinBox()
            max_limit = self.max_feedrates.get(logical, 500000)
            sb.setRange(10, max_limit)
            sb.setSingleStep(100)
            sb.setValue(min(self.feedrates.get(logical, 5000), max_limit))
            sb.setEnabled(False)
            sb.valueChanged.connect(self.actualizar_config)
            self.map_feedrates[logical] = sb
            row_layout.addWidget(QLabel("Normal:"))
            row_layout.addWidget(sb)
            
            sb_max = QSpinBox()
            sb_max.setRange(10, 500000)
            sb_max.setSingleStep(100)
            sb_max.setValue(self.max_feedrates.get(logical, 5000))
            sb_max.setEnabled(False)
            sb_max.setToolTip("Límite máximo real del firmware. Evita que la matemática falle si el feedrate normal lo excede.")
            sb_max.valueChanged.connect(self.actualizar_config)
            self.map_max_feedrates[logical] = sb_max
            row_layout.addWidget(QLabel("Máx Real:"))
            row_layout.addWidget(sb_max)
            
            feed_layout.addRow(f"Eje {logical}:", row_layout)

        self.btn_autodetect_feedrates = QPushButton("Auto-detectar Max Real (M503)")
        self.btn_autodetect_feedrates.setToolTip("Consulta la placa vía M503 para leer los max feedrates del firmware.")
        self.btn_autodetect_feedrates.clicked.connect(self._autodetect_max_feedrates)
        feed_layout.addRow(self.btn_autodetect_feedrates)

        self.lbl_autodetect_status = QLabel("")
        feed_layout.addRow(self.lbl_autodetect_status)

        layout.addWidget(gb_feed)

        # Seguridad y Límites
        gb_limits = QGroupBox("Seguridad y Límites Digitales")
        limits_layout = QVBoxLayout(gb_limits)
        
        self.chk_limits = QCheckBox("Activar protección de límites de hardware")
        self.chk_limits.setChecked(getattr(self.ctrl, "limits_enabled", False))
        self.chk_limits.toggled.connect(self.actualizar_config_limites)
        limits_layout.addWidget(self.chk_limits)
        
        self.lbl_limits = {}
        for axis in ["X", "Y", "Z"]:
            axis_layout = QVBoxLayout()
            
            # Row 1: Labels
            labels_layout = QHBoxLayout()
            labels_layout.addWidget(QLabel(f"<b>Eje {axis}</b>"))
            
            val = self.ctrl.limits.get(axis) if hasattr(self.ctrl, "limits") else None
            txt = self._format_limit_label(axis, val)
            lbl = QLabel(txt)
            lbl.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
            lbl.setWordWrap(True)
            self.lbl_limits[axis] = lbl
            labels_layout.addWidget(lbl)
            
            axis_layout.addLayout(labels_layout)
            
            # Row 2: Buttons
            btns_layout = QHBoxLayout()
            
            btn_return = QPushButton("Volver a 0")
            btn_return.clicked.connect(lambda checked=False, a=axis: self.volver_al_origen_eje(a))
            btns_layout.addWidget(btn_return)

            btn_home = QPushButton("Fijar Cero")
            btn_home.clicked.connect(lambda checked=False, a=axis: self.fijar_origen(a))
            btns_layout.addWidget(btn_home)
            
            btn_max = QPushButton("Límite Máx")
            btn_max.clicked.connect(lambda checked=False, a=axis: self.fijar_limite_max(a))
            btns_layout.addWidget(btn_max)
            
            axis_layout.addLayout(btns_layout)
            
            # Add a small line separator or just add to main
            limits_layout.addLayout(axis_layout)
            
            # Add spacing between axes
            limits_layout.addSpacing(10)
        layout.addWidget(gb_limits)

        # Backlash Compensation
        gb_backlash = QGroupBox("Compensación de Backlash (Holgura)")
        backlash_layout = QFormLayout(gb_backlash)
        
        self.chk_backlash = QCheckBox("Activar compensación de Backlash")
        self.chk_backlash.setChecked(self.backlash_enabled)
        self.chk_backlash.toggled.connect(self.actualizar_config_backlash)
        backlash_layout.addRow(self.chk_backlash)
        
        self.chk_lock_backlash = QCheckBox("Bloquear modificación")
        self.chk_lock_backlash.setChecked(getattr(self, "backlash_locked", False))
        self.chk_lock_backlash.toggled.connect(self.toggle_lock_backlash)
        backlash_layout.addRow(self.chk_lock_backlash)
        
        self.map_backlash = {}
        for logical in ["X", "Y", "Z"]:
            sb = QSpinBox()
            sb.setRange(0, 100000)
            sb.setSingleStep(1)
            sb.setSuffix(" Steps")
            sb.setValue(self.backlash_steps.get(logical, 0))
            sb.setEnabled(not self.chk_lock_backlash.isChecked())
            sb.valueChanged.connect(self.actualizar_config_backlash)
            self.map_backlash[logical] = sb
            backlash_layout.addRow(f"Eje {logical}:", sb)
            
        layout.addWidget(gb_backlash)

        # Keyboard Controls
        gb_keys = QGroupBox("Atajos de Teclado (Globales)")
        keys_layout = QVBoxLayout(gb_keys)
        
        self.cb_arrow_axis = QComboBox()
        self.cb_arrow_axis.addItems(["Eje Y", "Eje Z"])
        if self.arrow_updown_axis == "Z":
            self.cb_arrow_axis.setCurrentIndex(1)
        self.cb_arrow_axis.currentTextChanged.connect(self.actualizar_config_teclado)
        
        keys_layout.addWidget(QLabel("Seleccionar eje para arriba/abajo:"))
        keys_layout.addWidget(self.cb_arrow_axis)
        
        keys_layout.addWidget(QLabel("Comportamiento de las flechas:"))
        self.cb_keyboard_mode = QComboBox()
        self.cb_keyboard_mode.addItems(["Movimiento seteado (panel)", "Giro 360°"])
        self.cb_keyboard_mode.setCurrentIndex(1 if self.keyboard_mode == "360" else 0)
        self.cb_keyboard_mode.currentTextChanged.connect(self.actualizar_config_teclado)
        keys_layout.addWidget(self.cb_keyboard_mode)
        
        layout.addWidget(gb_keys)

        layout.addStretch()
        scroll.setWidget(content_widget)
        main_layout.addWidget(scroll)

    def _autodetect_max_feedrates(self):
        """Consulta M503 a la placa y rellena los campos Máx Real."""
        if not self.ctrl or not self.ctrl.ser:
            self.lbl_autodetect_status.setText("Motor no conectado")
            self.lbl_autodetect_status.setStyleSheet("color: #F44336;")
            return
        
        self.lbl_autodetect_status.setText("Consultando firmware...")
        self.lbl_autodetect_status.setStyleSheet("color: #FFC107;")
        from PyQt5.QtWidgets import QApplication
        QApplication.processEvents()
        
        result = self.ctrl.query_max_feedrates()
        
        if result:
            for axis, val in result.items():
                max_val = int(val)
                if axis in self.map_max_feedrates:
                    self.map_max_feedrates[axis].setValue(max_val)
                    self.max_feedrates[axis] = max_val
                
                # Limitar el spinbox normal para que no se pueda exceder el max real
                if axis in self.map_feedrates:
                    self.map_feedrates[axis].setMaximum(max_val)
                    # Si el valor actual excede el max detectado, recortarlo
                    if self.map_feedrates[axis].value() > max_val:
                        self.map_feedrates[axis].setValue(max_val)
                        self.feedrates[axis] = max_val
            
            txt = ", ".join(f"{a}: F{int(v)}" for a, v in result.items())
            self.lbl_autodetect_status.setText(f"Detectado: {txt}")
            self.lbl_autodetect_status.setStyleSheet("color: #4CAF50;")
            self.actualizar_config()
        else:
            self.lbl_autodetect_status.setText("No se pudo leer M203. Firmware no compatible.")
            self.lbl_autodetect_status.setStyleSheet("color: #F44336;")

    def toggle_feedrates(self, checked):
        for sb in self.map_feedrates.values():
            sb.setEnabled(checked)
        for sb in self.map_max_feedrates.values():
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
            self.max_feedrates[logical] = self.map_max_feedrates[logical].value()
            
        if self.on_mapping_changed:
            self.on_mapping_changed(self.mapping)
        if self.on_steps_360_changed:
            self.on_steps_360_changed(self.steps_360)
        if self.on_feedrates_changed:
            self.on_feedrates_changed(self.feedrates)
        if self.on_max_feedrates_changed:
            self.on_max_feedrates_changed(self.max_feedrates)
        
        self.ctrl.set_mapping(self.mapping)

    def actualizar_config_limites(self):
        enabled = self.chk_limits.isChecked()
        self.ctrl.enable_limits(enabled)
        # We need a callback to save settings in main.py/system_functions.py
        if hasattr(self.ctrl, "on_limits_enabled_changed") and self.ctrl.on_limits_enabled_changed:
            self.ctrl.on_limits_enabled_changed(enabled)

    def actualizar_config_backlash(self):
        self.backlash_enabled = self.chk_backlash.isChecked()
        if hasattr(self.ctrl, "backlash_enabled"):
            self.ctrl.backlash_enabled = self.backlash_enabled
        if self.on_backlash_enabled_changed:
            self.on_backlash_enabled_changed(self.backlash_enabled)
            
        for logical in ["X", "Y", "Z"]:
            self.backlash_steps[logical] = self.map_backlash[logical].value()
            if hasattr(self.ctrl, "backlash"):
                self.ctrl.backlash[logical] = self.backlash_steps[logical]
                
        if self.on_backlash_steps_changed:
            self.on_backlash_steps_changed(self.backlash_steps)
            
        self._guardar_preferencias()

    def toggle_lock_backlash(self, checked):
        self.backlash_locked = checked
        for logical in ["X", "Y", "Z"]:
            self.map_backlash[logical].setEnabled(not checked)
        self._guardar_preferencias()

    def actualizar_config_teclado(self):
        val = "Z" if self.cb_arrow_axis.currentIndex() == 1 else "Y"
        self.arrow_updown_axis = val
        if self.on_arrow_axis_changed:
            self.on_arrow_axis_changed(val)
            
        kb_mode = "360" if self.cb_keyboard_mode.currentIndex() == 1 else "set_movement"
        self.keyboard_mode = kb_mode
        if self.on_keyboard_mode_changed:
            self.on_keyboard_mode_changed(kb_mode)
            
        self._guardar_preferencias()
            
    def fijar_origen(self, axis):
        self.ctrl.set_zero(axis)

    def _format_limit_label(self, axis, val):
        if val is None:
            return "Sin límite"
        steps_per_rev = self.steps_360.get(axis, 3200)
        steps_per_mm = 2 * steps_per_rev
        if steps_per_mm > 0:
            mm = val / steps_per_mm
            return f"Máx: {val} Steps ({mm:.3f} mm)"
        return f"Máx: {val} Steps"

    def _guardar_preferencias(self):
        import json
        import os
        cfg = {}
        if os.path.exists("motor_settings.json"):
            try:
                with open("motor_settings.json", "r") as f:
                    cfg = json.load(f)
            except:
                pass
                
        cfg["mapping"] = self.mapping
        cfg["steps_360"] = self.steps_360
        cfg["feedrates"] = self.feedrates
        cfg["max_feedrates"] = getattr(self, "max_feedrates", {"X": 5000, "Y": 5000, "Z": 500, "E": 5000})
        if hasattr(self.ctrl, "limits"):
            cfg["limits"] = self.ctrl.limits
        if hasattr(self.ctrl, "limits_enabled"):
            cfg["limits_enabled"] = self.ctrl.limits_enabled
        if hasattr(self.ctrl, "backlash"):
            cfg["backlash_mm"] = self.ctrl.backlash
        if hasattr(self.ctrl, "backlash_enabled"):
            cfg["backlash_enabled"] = self.ctrl.backlash_enabled
            
        if hasattr(self, "backlash_locked"):
            cfg["backlash_locked"] = self.backlash_locked
            
        if hasattr(self, "arrow_updown_axis"):
            cfg["arrow_updown_axis"] = self.arrow_updown_axis
            
        try:
            with open("motor_settings.json", "w") as f:
                json.dump(cfg, f, indent=4)
        except Exception as e:
            print(f"Error al guardar config: {e}")

    def fijar_limite_max(self, eje):
        self.ctrl.set_limit(eje)
        val = self.ctrl.limits.get(eje)
        self.lbl_limits[eje].setText(self._format_limit_label(eje, val))

    def volver_al_origen_eje(self, eje):
        if not self.ctrl.ser:
            return
        current_steps = self.ctrl.positions.get(eje, 0)
        if current_steps == 0:
            return
        feedrate = self.feedrates.get(eje, 3000)
        try:
            self.ctrl.step_move(eje, -current_steps, 1, feedrate=feedrate, ignore_limits=True)
        except Exception as e:
            return

    def apply_styles(self):
        # Hereda los estilos de los temas principales
        pass
