import sys
import os
os.environ["QT_AUTO_SCREEN_SCALE_FACTOR"] = "1"
os.environ["QT_ENABLE_HIGHDPI_SCALING"] = "1"
from PyQt5.QtWidgets import QApplication
from system_functions import LithographySimulator

app = QApplication(sys.argv)
app.setStyle("Fusion")
window = LithographySimulator()
window.show()
sys.exit(app.exec_())
