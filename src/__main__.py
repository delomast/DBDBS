# Starting window

from PyQt6.QtCore import QSize, Qt
from PyQt6.QtWidgets import (
	QApplication, QMainWindow, QPushButton, QLabel, QLineEdit, QComboBox, 
	 QGridLayout, QWidget, QCheckBox, QDialog
)
from .interact import interactWindow

# a little redundant, but that's ok
if __name__ == "__main__":
	app = QApplication([]) # create application instance
	# create main window
	window = interactWindow()
	window.show()
	app.exec()
