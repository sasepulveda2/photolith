from PyQt5.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QPushButton,
    QComboBox,
    QLabel,
    QSpinBox,
)
from PyQt5.QtCore import Qt


class MotorGUI(QWidget):
    def __init__(
        self,
        controller,
        initial_positions=None,
        on_positions_changed=None,
        on_last_movement_changed=None,
    ):
        super().__init__()
        self.ctrl = controller
        self.on_positions_changed = on_positions_changed
        self.on_last_movement_changed = on_last_movement_changed

        # --- TRACKER DE POSICIÓN INTERNO ---
        # Diccionario para guardar la posición absoluta de cada eje en "steps"
        self.posiciones = {"X": 0, "Y": 0, "Z": 0, "E": 0}
        if isinstance(initial_positions, dict):
            for eje in self.posiciones:
                try:
                    self.posiciones[eje] = int(initial_positions.get(eje, 0))
                except (TypeError, ValueError):
                    self.posiciones[eje] = 0

        self.initUI()

    def initUI(self):
        self.setWindowTitle("Fotolitografía Step-Control (Con Odómetro)")
        self.resize(400, 250)
        layout = QVBoxLayout()

        # --- PANTALLA DE POSICIÓN ABSOLUTA ---
        self.odo_label = QLabel("POSICIÓN ABSOLUTA\n0 Steps | 0.000 mm | 0.0°")
        self.odo_label.setStyleSheet(
            "background-color: #1a1a1a; color: #00ff00; font-family: monospace; font-size: 14px; padding: 10px; border: 2px solid grey;"
        )
        self.odo_label.setAlignment(Qt.AlignCenter)
        layout.addWidget(self.odo_label)

        # --- CUADRO DE UNIDAD DEL MOVIMIENTO ---
        self.unit_box = QLabel("MOVIMIENTO: 12.5 µm (1 Step)")
        self.unit_box.setStyleSheet("color: grey; font-weight: bold;")
        self.unit_box.setAlignment(Qt.AlignCenter)
        layout.addWidget(self.unit_box)

        self.status_label = QLabel("Control listo")
        self.status_label.setStyleSheet("color: #b0b0b0; font-style: italic;")
        self.status_label.setAlignment(Qt.AlignCenter)
        layout.addWidget(self.status_label)

        # --- CONFIGURACIÓN DE EJE Y MULTIPLICADOR ---
        row1 = QHBoxLayout()
        self.axis_sel = QComboBox()
        self.axis_sel.addItems(["X", "Y", "Z", "E"])
        self.axis_sel.currentTextChanged.connect(
            self.actualizar_pantalla
        )  # Actualiza al cambiar de eje

        self.multi_sel = QSpinBox()
        self.multi_sel.setRange(1, 10000)
        self.multi_sel.setValue(1)
        self.multi_sel.valueChanged.connect(self.update_unit_display)

        row1.addWidget(QLabel("Eje:"))
        row1.addWidget(self.axis_sel)
        row1.addWidget(QLabel("Mult. Steps:"))
        row1.addWidget(self.multi_sel)
        layout.addLayout(row1)

        # --- BOTONES DE MOVIMIENTO ---
        row2 = QHBoxLayout()
        self.btn_left = QPushButton("⬅ IZQUIERDA (-)")
        self.btn_right = QPushButton("DERECHA (+) ➡")

        self.btn_left.clicked.connect(lambda: self.ejecutar_movimiento(-1))
        self.btn_right.clicked.connect(lambda: self.ejecutar_movimiento(1))

        row2.addWidget(self.btn_left)
        row2.addWidget(self.btn_right)
        layout.addLayout(row2)

        # Botón para resetear el cero (Homing Virtual)
        btn_zero = QPushButton("Establecer Cero Aquí (Zero Axis)")
        btn_zero.clicked.connect(self.set_zero)
        layout.addWidget(btn_zero)

        btn_home_all = QPushButton("Volver al Origen (Todos los ejes)")
        btn_home_all.clicked.connect(self.volver_al_origen)
        layout.addWidget(btn_home_all)

        self.setLayout(layout)
        self.actualizar_pantalla()

    def persist_positions(self):
        if self.on_positions_changed:
            self.on_positions_changed(dict(self.posiciones))

    def persist_last_movement(self, movement):
        if self.on_last_movement_changed:
            self.on_last_movement_changed(movement)

    def update_unit_display(self):
        # Actualiza el cuadro de texto para saber cuánto se va a mover con cada clic
        val_mm = self.multi_sel.value() * 0.0125
        if val_mm < 1:
            self.unit_box.setText(f"MOVIMIENTO: {val_mm*1000:.1f} µm")
        elif val_mm < 10:
            self.unit_box.setText(f"MOVIMIENTO: {val_mm:.3f} mm")
        else:
            self.unit_box.setText(f"MOVIMIENTO: {val_mm/10:.2f} cm")

    def ejecutar_movimiento(self, direccion):
        eje = self.axis_sel.currentText()
        steps_base = direccion
        multiplicador = self.multi_sel.value()

        # 1. Enviar el comando físico
        try:
            self.ctrl.step_move(eje, steps_base, multiplicador)
        except Exception as exc:
            self.status_label.setText(f"Conexión perdida: {exc}")
            return

        # 2. Actualizar nuestro rastreador interno
        pasos_totales_movidos = steps_base * multiplicador
        self.posiciones[eje] += pasos_totales_movidos
        self.persist_positions()
        self.persist_last_movement(
            {
                "axis": eje,
                "delta_steps": pasos_totales_movidos,
                "multiplier": multiplicador,
                "position_after": self.posiciones[eje],
            }
        )

        # 3. Refrescar la pantalla
        self.actualizar_pantalla()

    def actualizar_pantalla(self):
        eje = self.axis_sel.currentText()
        pasos_actuales = self.posiciones[eje]

        # Matemáticas de conversión
        mm = pasos_actuales * 0.0125
        # 1 step = 1.8 grados de rotación física del motor NEMA 17
        grados = pasos_actuales * 1.8

        self.odo_label.setText(
            f"EJE {eje} | POSICIÓN ABSOLUTA\n{pasos_actuales} Steps | {mm:.3f} mm | {grados:.1f}°"
        )

    def set_zero(self):
        # Reinicia el contador del eje actual a cero (como hacer la tara en una balanza)
        eje = self.axis_sel.currentText()
        self.posiciones[eje] = 0
        self.persist_positions()
        self.actualizar_pantalla()

    def volver_al_origen(self):
        # Mueve cada eje en sentido contrario a lo acumulado para regresar a 0
        movimientos = 0
        for eje in ["X", "Y", "Z", "E"]:
            pasos_actuales = self.posiciones[eje]
            if pasos_actuales == 0:
                continue

            try:
                self.ctrl.step_move(eje, -pasos_actuales, 1)
            except Exception as exc:
                self.status_label.setText(f"Conexión perdida: {exc}")
                return

            self.posiciones[eje] = 0
            movimientos += 1

        if movimientos == 0:
            self.status_label.setText("Ya está en origen")
        else:
            self.status_label.setText("Regreso al origen completado")
            self.persist_positions()
        self.actualizar_pantalla()
