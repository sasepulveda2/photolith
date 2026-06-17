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
        
        # Tracker de posición interna y límites
        self.positions = {"X": 0, "Y": 0, "Z": 0, "E": 0}
        self.limits_enabled = False
        self.limits = {"X": None, "Y": None, "Z": None, "E": None}
        
        # Backlash compensation
        self.backlash = {"X": 0.0, "Y": 0.0, "Z": 0.0, "E": 0.0}
        self.backlash_enabled = False
        self.last_direction = {"X": 0, "Y": 0, "Z": 0, "E": 0}
        self.accumulated_backlash = {"X": 0.0, "Y": 0.0, "Z": 0.0, "E": 0.0}
        
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

    def enable_limits(self, state: bool):
        """Activa o desactiva la protección de límites digitales."""
        self.limits_enabled = state

    def set_limit(self, axis: str, limit_value=None):
        """Fija el límite máximo del eje. Si limit_value es None, usa la posición actual."""
        if limit_value is None:
            self.limits[axis] = self.positions[axis]
        else:
            self.limits[axis] = limit_value

    def connect(self):
        try:
            self.ser = serial.Serial(self.port, self.baud, timeout=1)
            time.sleep(4)
            # Bypass silencioso de protecciones y seteo inicial
            for cmd in ["M999", "M121", "M302 S0", "M211 S0", "G91", "M17"]:
                self.ser.write(f"{cmd}\n".encode())
                
            # Sincronizar el origen físico con nuestro origen lógico inicial
            self.ser.write(b"G92 X0 Y0 Z0 E0\n")
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

    def step_move(self, axis: str, steps: int, multiplier=1, feedrate=150, ignore_limits=False):
        """Envía el comando de movimiento y actualiza la odometría."""
        if not self.ser:
            raise RuntimeError("Puerto serial no disponible")
            
        total_steps = steps * multiplier
        
        # Validación de límites de seguridad digitales (Soft Limits) bidireccionales
        if getattr(self, "limits_enabled", False) and not ignore_limits:
            target_pos = self.positions[axis] + total_steps
            axis_limit = self.limits.get(axis)
            
            if axis_limit is not None:
                # El rango de movimiento válido está entre 0 y el límite fijado, sin importar si es positivo o negativo
                min_limit = min(0, axis_limit)
                max_limit = max(0, axis_limit)
                
                if target_pos < min_limit:
                    raise ValueError(f"Excede límite inferior ({min_limit} steps)")
                if target_pos > max_limit:
                    raise ValueError(f"Excede límite superior ({max_limit} steps)")
            else:
                # Si no hay límite definido pero activó la protección, asumimos que 0 es el tope mínimo por defecto
                if target_pos < 0 and total_steps < 0:
                    raise ValueError(f"no puede moverse a valores negativos sin definir un límite primero. Origen es 0.")
        
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

        if total_steps == 0:
            return

        direction = 1 if total_steps > 0 else -1

        if self.ser:
            # Detect direction change for backlash compensation
            last_dir = self.last_direction.get(axis, 0)
            try:
                backlash_steps = int(float(self.backlash.get(axis, 0.0)))
            except (TypeError, ValueError):
                backlash_steps = 0
            
            # Si cambió de dirección, existe un valor de backlash configurado, y está habilitado globalmente
            if self.backlash_enabled and last_dir != 0 and last_dir != direction and backlash_steps > 0:
                physical_invert = axis_config["invert"]
                physical_backlash_distance = backlash_steps * self.step_size * direction * (-1 if physical_invert else 1)
                
                # 1. Devorar la holgura físicamente
                self._write(f"G1 {physical_motor.upper()}{physical_backlash_distance:.4f} F{feedrate}\n")
                
                # 2. Registrar el backlash acumulado en lugar de usar G92 para no corromper el planner de Marlin
                self.accumulated_backlash[axis] += physical_backlash_distance
                
            self.last_direction[axis] = direction
            
            # Movimiento real
            self._write(f"G1 {physical_motor.upper()}{physical_distance:.4f} F{feedrate}\n")

        print(
            f"Lógico: {axis} -> Físico: {physical_motor} | Steps: {total_steps} | Dist: {distance:.4f}mm | Deg: {degrees}° | Multi: x{multiplier} | F{feedrate}",
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
        """Reinicia el contador del eje actual a cero (Tara virtual) y sincroniza la placa."""
        self.positions[axis] = 0
        self.accumulated_backlash[axis] = 0.0
        if self.ser:
            phys = self.mapping.get(axis, {}).get("motor", axis)
            self.ser.write(f"G92 {phys.upper()}0\n".encode())
            
        if self.on_positions_changed:
            self.on_positions_changed(dict(self.positions))

    def emergency_stop(self):
        """Envía el comando M410 de parada rápida y recupera el estado."""
        if self.ser:
            try:
                self.ser.write(b"M410\n")
                time.sleep(0.2)
                # M999 reinicia el estado de Halt
                self.ser.write(b"M999\n")
                time.sleep(0.2)
                self.ser.write(b"G91\n")
            except Exception:
                pass

    def sync_position_from_hardware(self):
        """Consulta M114 a la placa, extrae la posición física real en la que se detuvo, y ajusta Python."""
        if not self.ser: return
        try:
            self.ser.flushInput()
            self.ser.write(b"M114\n")
            t0 = time.time()
            pos_str = ""
            while time.time() - t0 < 1.5:
                if self.ser.in_waiting:
                    line = self.ser.readline().decode('utf-8', errors='ignore')
                    if "X:" in line and "Y:" in line and "Z:" in line:
                        pos_str = line
                        break
            
            if pos_str:
                import re
                # Parsear "X:10.00 Y:-5.50 Z:0.00 E:0.00"
                for logical_axis, data in self.mapping.items():
                    phys = data["motor"].upper()
                    match = re.search(fr"{phys}:([-\d\.]+)", pos_str)
                    if match:
                        mm_val = float(match.group(1))
                        # Descontar el backlash acumulado físico para obtener la coordenada lógica real
                        mm_val -= self.accumulated_backlash.get(logical_axis, 0.0)
                        
                        # Convertir mm físicos de vuelta a steps lógicos
                        steps = int(mm_val / self.step_size)
                        if data.get("invert", False):
                            steps = -steps
                        self.positions[logical_axis] = steps
                
                if self.on_positions_changed:
                    self.on_positions_changed(dict(self.positions))
        except Exception as e:
            print(f"Error al sincronizar hardware: {e}")

    def query_max_feedrates(self):
        """Envía M503 a la placa y parsea M203 para obtener los max feedrates reales del firmware."""
        if not self.ser:
            return None
        try:
            self.ser.flushInput()
            self.ser.write(b"M503\n")
            t0 = time.time()
            lines = []
            while time.time() - t0 < 3.0:
                if self.ser.in_waiting:
                    line = self.ser.readline().decode('utf-8', errors='ignore').strip()
                    lines.append(line)
                    if "ok" in line.lower() and len(lines) > 5:
                        break
            
            import re
            for line in lines:
                # Marlin M203: "echo:  M203 X500.00 Y500.00 Z10.00 E25.00"
                if "M203" in line:
                    result = {}
                    for axis in ["X", "Y", "Z", "E"]:
                        match = re.search(fr"{axis}([\d\.]+)", line)
                        if match:
                            result[axis] = float(match.group(1))
                    if result:
                        return result
            
            return None
        except Exception as e:
            print(f"Error al consultar max feedrates: {e}")
            return None

    def home_all(self):
        """Mueve cada eje en sentido contrario a lo acumulado para regresar a 0."""
        movimientos = 0
        for axis in ["X", "Y", "Z", "E"]:
            current_steps = self.positions[axis]
            if current_steps == 0:
                continue
            
            # Al mandar -current_steps, internamente step_move ajustará la odometría a 0
            self.step_move(axis, -current_steps, 1, ignore_limits=True)
            movimientos += 1
            
        return movimientos

    def close(self):
        if self.ser:
            try:
                self.ser.close()
            finally:
                self.ser = None
