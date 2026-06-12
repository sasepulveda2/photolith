import sys
from PyQt5.QtWidgets import QApplication
from system_functions import LithographySimulator

app = QApplication(sys.argv)
app.setStyle("Fusion")
window = LithographySimulator()
window.show()
sys.exit(app.exec_())
