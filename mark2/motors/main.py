import sys
import json
from pathlib import Path
from serial.tools import list_ports
from PyQt5.QtWidgets import (
    QApplication,
    QDialog,
    QVBoxLayout,
    QHBoxLayout,
    QPushButton,
    QComboBox,
    QLabel,
    QMessageBox,
)
from motor_controller import CrealityController
from gui import MotorGUI

SETTINGS_FILE = Path(__file__).resolve().with_name("motor_settings.json")
DEFAULT_BAUDS = [9600, 57600, 115200, 250000, 500000, 1000000]


def puerto_key(port):
    if port.serial_number:
        return {"serial_number": port.serial_number}

    if port.vid is not None and port.pid is not None:
        return {
            "vid": port.vid,
            "pid": port.pid,
            "manufacturer": port.manufacturer,
            "product": port.product,
        }

    return {"device": port.device}


def port_matches_identity(port, identity):
    if not identity:
        return False

    if identity.get("serial_number"):
        return port.serial_number == identity.get("serial_number")

    if identity.get("vid") is not None and identity.get("pid") is not None:
        return (
            port.vid == identity.get("vid")
            and port.pid == identity.get("pid")
            and port.manufacturer == identity.get("manufacturer")
            and port.product == identity.get("product")
        )

    return port.device == identity.get("device")


def load_settings():
    defaults = {
        "port_identity": None,
        "baud": 250000,
        "positions": {"X": 0, "Y": 0, "Z": 0, "E": 0},
        "last_movement": None,
    }
    try:
        data = json.loads(SETTINGS_FILE.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return defaults

    defaults["port_identity"] = data.get("port_identity")
    try:
        defaults["baud"] = int(data.get("baud", defaults["baud"]))
    except (TypeError, ValueError):
        pass

    positions = data.get("positions", {})
    if isinstance(positions, dict):
        for axis in defaults["positions"]:
            try:
                defaults["positions"][axis] = int(positions.get(axis, 0))
            except (TypeError, ValueError):
                defaults["positions"][axis] = 0

    last_movement = data.get("last_movement")
    if isinstance(last_movement, dict):
        defaults["last_movement"] = last_movement

    return defaults


def save_settings(settings):
    try:
        SETTINGS_FILE.write_text(
            json.dumps(settings, ensure_ascii=True, indent=2), encoding="utf-8"
        )
    except OSError:
        pass


def find_matching_port(ports, identity):
    if not identity:
        return None

    for port in ports:
        if port_matches_identity(port, identity):
            return port

    return None


class PortSelectorDialog(QDialog):
    def __init__(self, ports, settings, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Seleccionar puerto y baudios")
        self.setMinimumWidth(480)

        layout = QVBoxLayout(self)
        layout.addWidget(QLabel("Puertos seriales detectados:"))

        self.combo = QComboBox()
        for port in ports:
            details = [port.description]
            if port.manufacturer:
                details.append(port.manufacturer)
            if port.product:
                details.append(port.product)
            if port.vid is not None and port.pid is not None:
                details.append(f"VID:PID {port.vid:04X}:{port.pid:04X}")
            label = f"{port.device} - {' | '.join(details)}"
            self.combo.addItem(label, port.device)

        if settings.get("port_identity"):
            for index in range(self.combo.count()):
                port = next(
                    (
                        item
                        for item in ports
                        if item.device == self.combo.itemData(index)
                    ),
                    None,
                )
                if port and port_matches_identity(port, settings.get("port_identity")):
                    self.combo.setCurrentIndex(index)
                    break
        layout.addWidget(self.combo)

        layout.addWidget(QLabel("Baud rate:"))
        self.baud_combo = QComboBox()
        baud_values = list(DEFAULT_BAUDS)
        saved_baud = settings.get("baud", 250000)
        if saved_baud not in baud_values:
            baud_values.append(saved_baud)
        for baud in baud_values:
            self.baud_combo.addItem(str(baud), baud)
        saved_index = self.baud_combo.findData(saved_baud)
        if saved_index >= 0:
            self.baud_combo.setCurrentIndex(saved_index)
        layout.addWidget(self.baud_combo)

        buttons = QHBoxLayout()
        btn_cancel = QPushButton("Cancelar")
        btn_ok = QPushButton("Usar este puerto")
        btn_cancel.clicked.connect(self.reject)
        btn_ok.clicked.connect(self.accept)
        buttons.addWidget(btn_cancel)
        buttons.addWidget(btn_ok)
        layout.addLayout(buttons)

    def selected_port(self):
        return self.combo.currentData()

    def selected_baud(self):
        return int(self.baud_combo.currentData())


def seleccionar_puerto_y_baud(settings):
    puertos = list(list_ports.comports())
    if not puertos:
        QMessageBox.warning(
            None, "Sin puertos", "No se detectaron puertos COM conectados."
        )
        return None, None

    reconocido = find_matching_port(puertos, settings.get("port_identity"))
    if reconocido:
        return reconocido, int(settings.get("baud", 250000))

    dialog = PortSelectorDialog(puertos, settings)
    if dialog.exec_() != QDialog.Accepted:
        return None, None

    selected_device = dialog.selected_port()
    selected_port = next(
        (port for port in puertos if port.device == selected_device), None
    )
    if selected_port is None:
        return None, None

    settings["baud"] = dialog.selected_baud()
    return selected_port, settings["baud"]


if __name__ == "__main__":
    app = QApplication(sys.argv)
    settings = load_settings()

    puerto, baud = seleccionar_puerto_y_baud(settings)
    if not puerto:
        sys.exit(0)

    controller = CrealityController(puerto.device, baud=baud)
    if controller.connect():
        settings["port_identity"] = puerto_key(puerto)
        settings["baud"] = baud
        save_settings(settings)

        def guardar_posiciones(positions):
            settings["positions"] = positions
            save_settings(settings)

        def guardar_ultimo_movimiento(movement):
            settings["last_movement"] = movement
            save_settings(settings)

        window = MotorGUI(
            controller,
            initial_positions=settings.get("positions", {}),
            on_positions_changed=guardar_posiciones,
            on_last_movement_changed=guardar_ultimo_movimiento,
        )
        window.show()
        sys.exit(app.exec_())

    dialog = PortSelectorDialog(list(list_ports.comports()), settings)
    if dialog.exec_() != QDialog.Accepted:
        sys.exit(1)

    selected_device = dialog.selected_port()
    selected_port = next(
        (port for port in list_ports.comports() if port.device == selected_device), None
    )
    if not selected_port:
        sys.exit(1)

    settings["baud"] = dialog.selected_baud()
    controller = CrealityController(selected_port.device, baud=settings["baud"])
    if controller.connect():
        settings["port_identity"] = puerto_key(selected_port)
        save_settings(settings)

        def guardar_posiciones(positions):
            settings["positions"] = positions
            save_settings(settings)

        def guardar_ultimo_movimiento(movement):
            settings["last_movement"] = movement
            save_settings(settings)

        window = MotorGUI(
            controller,
            initial_positions=settings.get("positions", {}),
            on_positions_changed=guardar_posiciones,
            on_last_movement_changed=guardar_ultimo_movimiento,
        )
        window.show()
        sys.exit(app.exec_())

    QMessageBox.critical(
        None,
        "Error de conexión",
        f"No se pudo conectar a la placa en {selected_port.device}.",
    )
    sys.exit(1)
