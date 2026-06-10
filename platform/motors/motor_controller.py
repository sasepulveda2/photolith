import serial
import time


class CrealityController:
    """
    Controlador para los motores NEMA (vía placa Creality/G-code).
    Maneja la conexión Serial, la lógica de movimiento (step_move),
    la odometría interna (tracker de posiciones en steps) y el homing.
    """
    def __init__(self, port="COM3", baud=250000, steps_per_mm=80, initial_positions=None, mapping=None):
        self.ser = None
        self.port = port
        self.baud = baud
        self.step_size = 1.0 / steps_per_mm  # 0.0125 mm por paso
        
        self.mapping = mapping or {
            "X": {"motor": "X", "invert": False},
            "Y": {"motor": "Y", "invert": False},
            "Z": {"motor": "Z", "invert": False},
            "E": {"motor": "E", "invert": False}
        }
        
        # Tracker de posición interna
        self.positions = {"X": 0, "Y": 0, "Z": 0, "E": 0}
        if isinstance(initial_positions, dict):
            for axis in self.positions:
                try:
                    self.positions[axis] = int(initial_positions.get(axis, 0))
                except (TypeError, ValueError):
                    pass
                    
        # Callbacks para persistencia/actualización externa
        self.on_positions_changed = None
        self.on_last_movement_changed = None

    def set_mapping(self, mapping):
        self.mapping = mapping

    def connect(self):
        try:
            self.ser = serial.Serial(self.port, self.baud, timeout=1)
            time.sleep(4)
            # Bypass silencioso de protecciones de extrusor frío y modo relativo
            for cmd in ["M999", "M121", "M302 S0", "G91", "M17"]:
                self.ser.write(f"{cmd}\n".encode())
            return True
        except Exception:
            self.ser = None
            return False

    def reconnect(self):
        self.close()
        return self.connect()

    def _write(self, command):
        if not self.ser:
            raise RuntimeError("Puerto serial no disponible")

        try:
            self.ser.write(command.encode())
        except Exception as exc:
            self.close()
            raise RuntimeError("Se perdió la conexión con el controlador") from exc

    def step_move(self, axis, steps, multiplier=1):
        """Envía el comando de movimiento y actualiza la odometría."""
        if not self.ser:
            raise RuntimeError("Puerto serial no disponible")
            
        total_steps = steps * multiplier
        
        # Consultar el mapeo físico
        axis_config = self.mapping.get(axis, {"motor": axis, "invert": False})
        physical_motor = axis_config["motor"]
        invert_factor = -1 if axis_config["invert"] else 1
        
        # Calcular los pasos físicos reales y distancia para el comando de hardware
        physical_steps = total_steps * invert_factor
        physical_distance = physical_steps * self.step_size
        
        # La odometría guarda el movimiento LÓGICO solicitado
        distance = total_steps * self.step_size
        degrees = total_steps * 1.8

        # Comando G-Code dirigido al motor físico mapeado
        self._write(f"G1 {physical_motor.upper()}{physical_distance:.4f} F150\n")

        print(
            f"Lógico: {axis} ➔ Físico: {physical_motor} | Steps: {total_steps} | Dist: {distance:.4f}mm | Deg: {degrees}° | Multi: x{multiplier}",
            end="\r",
        )
        
        # Actualizar estado interno
        self.positions[axis] += total_steps
        
        # Emitir eventos si están configurados
        if self.on_positions_changed:
            self.on_positions_changed(dict(self.positions))
            
        if self.on_last_movement_changed:
            self.on_last_movement_changed({
                "axis": axis,
                "delta_steps": total_steps,
                "multiplier": multiplier,
                "position_after": self.positions[axis],
            })

    def set_zero(self, axis):
        """Reinicia el contador del eje actual a cero (Tara virtual)."""
        self.positions[axis] = 0
        if self.on_positions_changed:
            self.on_positions_changed(dict(self.positions))

    def home_all(self):
        """Mueve cada eje en sentido contrario a lo acumulado para regresar a 0."""
        movimientos = 0
        for axis in ["X", "Y", "Z", "E"]:
            current_steps = self.positions[axis]
            if current_steps == 0:
                continue
            
            # Al mandar -current_steps, internamente step_move ajustará la odometría a 0
            self.step_move(axis, -current_steps, 1)
            movimientos += 1
            
        return movimientos

    def close(self):
        if self.ser:
            try:
                self.ser.close()
            finally:
                self.ser = None
