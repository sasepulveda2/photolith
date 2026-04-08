import serial
import time


class CrealityController:
    def __init__(self, port="COM3", baud=250000, steps_per_mm=80):
        self.ser = None
        self.port = port
        self.baud = baud
        self.step_size = 1.0 / steps_per_mm  # 0.0125 mm por paso

    def connect(self):
        try:
            self.ser = serial.Serial(self.port, self.baud, timeout=1)
            time.sleep(4)
            # Bypass silencioso
            for cmd in ["M999", "M121", "M302 S0", "G91", "M17"]:
                self.ser.write(f"{cmd}\n".encode())
            return True
        except Exception:
            self.ser = None
            return False

    def _write(self, command):
        if not self.ser:
            raise RuntimeError("Puerto serial no disponible")

        try:
            self.ser.write(command.encode())
        except Exception as exc:
            self.close()
            raise RuntimeError("Se perdió la conexión con el controlador") from exc

    def step_move(self, axis, steps, multiplier):
        if not self.ser:
            return
        total_steps = steps * multiplier
        distance = total_steps * self.step_size
        degrees = total_steps * 1.8

        # Comando G-Code
        self._write(f"G1 {axis.upper()}{distance:.4f} F600\n")

        # Print en 1 sola línea como pediste (usando \r para sobreescribir)
        print(
            f"Eje: {axis} | Steps: {total_steps} | Dist: {distance:.4f}mm | Deg: {degrees}° | Multi: x{multiplier}",
            end="\r",
        )

    def close(self):
        if self.ser:
            try:
                self.ser.close()
            finally:
                self.ser = None
