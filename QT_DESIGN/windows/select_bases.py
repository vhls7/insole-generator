from PyQt5.QtCore import pyqtSignal  # pylint: disable=no-name-in-module
from PyQt5 import QtWidgets, uic


class SelectBases(QtWidgets.QMainWindow):
    closed_signal = pyqtSignal(str)
    flag_insert='false'
    def __init__(self):
        super().__init__()

        self.base_name = None

        # Loading interface developed in Qt Designer
        uic.loadUi(r"QT_DESIGN\select_base.ui", self)

        # region Connecting buttons to functions
        self.select_base_button = self.findChild(QtWidgets.QPushButton, "btn_inserir_base")
        self.select_base_button.clicked.connect(self.load_parametric_base)

        self.cb_sizing = self.findChild(QtWidgets.QComboBox, "CB_numeracao")
        self.cb_sizing.currentTextChanged.connect(self.update_button_state)
    
        self.cb_thickness = self.findChild(QtWidgets.QComboBox, "CB_espessura")
        self.cb_thickness.currentTextChanged.connect(self.update_button_state)

        self.cb_height = self.findChild(QtWidgets.QComboBox, "CB_calcanhar")
        self.cb_height.currentTextChanged.connect(self.update_button_state)
        # endregion

        self.update_button_state()

    def closeEvent(self, event):
        # Emite o sinal ao fechar a janela, passando a string desejada
        if self.flag_insert == 'true':
            self.closed_signal.emit(self.base_name)
        event.accept()

    def load_parametric_base(self):
        num = self.cb_sizing.currentText()
        esp = self.cb_thickness.currentText()
        alt = self.cb_height.currentText()

        self.base_name = f'PAMLILHAS_STL/{num}/BASES/CONTATO_{esp}_{alt}.STL'
        self.flag_insert='true'

        self.close()

    def update_button_state(self):
        default_text = "Escolha uma opção"

        # Check if all ComboBoxes have a valid selection
        is_valid_num = self.cb_sizing.currentText() != default_text
        is_valid_esp = self.cb_thickness.currentText() != default_text
        is_valid_alt = self.cb_height.currentText() != default_text

        # Enables or disables the button based on conditions
        self.select_base_button.setEnabled(is_valid_num and is_valid_esp and is_valid_alt)
