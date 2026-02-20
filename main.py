"""Минимальное приложение с графическим интерфейсом на PyQt5."""

import sys
from PyQt5.QtWidgets import QApplication, QMainWindow, QLabel, QPushButton, QVBoxLayout, QWidget
from PyQt5.QtCore import Qt


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("PyQt приложение")
        self.setMinimumSize(300, 150)

        central = QWidget()
        self.setCentralWidget(central)
        layout = QVBoxLayout(central)

        self.label = QLabel("Привет, PyQt!")
        self.label.setAlignment(Qt.AlignCenter)
        layout.addWidget(self.label)

        self.button = QPushButton("Нажми меня")
        self.button.clicked.connect(self.on_button_click)
        layout.addWidget(self.button)

    def on_button_click(self):
        self.label.setText("Минимальная программа на Python")


def main():
    app = QApplication(sys.argv)
    window = MainWindow()
    window.show()
    sys.exit(app.exec_())


if __name__ == "__main__":
    main()
