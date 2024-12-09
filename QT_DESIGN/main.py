# pylint: disable=I1101, W0401, C0115

import os
import sys

import numpy as np
import pyvista as pv
import resources_rc  # pylint: disable=unused-import
from PyQt5 import QtCore, QtGui, QtWidgets, uic
from PyQt5.QtCore import pyqtSignal  # pylint: disable=no-name-in-module
from pyvistaqt import QtInteractor


def get_centroid(your_mesh):
    centroid = np.mean(your_mesh.points.reshape(-1, 3), axis=0)
    return centroid

def rotate_mesh(mesh: pv.PolyData, angle_x=0, angle_y=0, angle_z=0, around_centroid=False) -> pv.PolyData:
    centroid = get_centroid(mesh)

    if around_centroid:
        mesh.translate(-centroid, inplace=True)

    mesh.rotate_x(angle_x, inplace=True)
    mesh.rotate_y(angle_y, inplace=True)
    mesh.rotate_z(angle_z, inplace=True)

    if around_centroid:
        mesh.translate(centroid, inplace=True)

    return mesh

def esphere_filt(points, radius):
    remaining_points = points.copy()
    filtered_points = []

    while len(remaining_points) > 0:
        current_point = remaining_points[0]
        filtered_points.append(current_point)

        distances = np.linalg.norm(remaining_points - current_point, axis=1)

        remaining_points = remaining_points[distances > radius]
    return np.array(filtered_points)

class MainWindow(QtWidgets.QMainWindow):
    def __init__(self):
        super().__init__()
        self.window_loading = None
        self.window_select_base = None

        self.scanned_file_info = {}
        self.scanned_mesh_display = None

        self.base_insole_file_info = {}
        self.base_insole_mesh_display = None

        self.insole_output = None

        # Loading interface developed in Qt Designer
        uic.loadUi(r"QT_DESIGN\main.ui", self)

        self.rotation_angle = 0
        self.offset_x = 0
        self.offset_y = 0
        self.offset_z = 0

        self.showMaximized()

        # Adding pyvista plotter to the interface widget
        pyvista_widget = self.findChild(QtWidgets.QWidget, "pyvistaWidget")
        self.layout = QtWidgets.QVBoxLayout()
        self.plotter = QtInteractor(pyvista_widget)
        self.plotter.add_axes()

        self.layout.addWidget(self.plotter.interactor)
        pyvista_widget.setLayout(self.layout)

        self.loading_label = self.create_loading_component()
        self.layout.addWidget(self.loading_label)  # Adiciona ao mesmo layout do PyVista

        # region Connecting buttons to functions
        self.findChild(QtWidgets.QPushButton, "loadScanButton").clicked.connect(self.load_scan_model)

        self.findChild(QtWidgets.QPushButton, "loadBaseButton").clicked.connect(self.load_bases)

        self.findChild(QtWidgets.QSlider, "panX").valueChanged.connect(self.update_slider_value)

        self.findChild(QtWidgets.QSlider, "panY").valueChanged.connect(self.update_slider_value)

        self.findChild(QtWidgets.QSlider, "panZ").valueChanged.connect(self.update_slider_value)

        self.findChild(QtWidgets.QDial, "orbitZ").valueChanged.connect(self.update_dial_value)

        self.findChild(QtWidgets.QPushButton, "cutButton").clicked.connect(self.cut_insole)

        self.findChild(QtWidgets.QPushButton, "topCam").clicked.connect(lambda: self.set_camera_view('top'))

        self.findChild(QtWidgets.QPushButton, "latCam").clicked.connect(lambda: self.set_camera_view('lateral'))

        self.findChild(QtWidgets.QPushButton, "frontCam").clicked.connect(lambda: self.set_camera_view('front'))

        self.findChild(QtWidgets.QPushButton, "cleanButton").clicked.connect(lambda: self.remove_file_item(remove_all=True))

        self.files_info_container = self.findChild(QtWidgets.QVBoxLayout, "filesInfoContainer")
        # endregion

    def create_loading_component(self):
        loading_label = QtWidgets.QLabel("Carregando...")
        loading_label.setStyleSheet("font-size: 20px; color: red; text-align: center;")
        loading_label.setAlignment(QtCore.Qt.AlignCenter)
        loading_label.hide()  # Oculta inicialmente
        return loading_label

    def build_files_list(self):
        # Cleaning the files_info_container to build from scratch
        while self.files_info_container.count() > 0:
            child = self.files_info_container.takeAt(0)
            if child.widget():
                child.widget().deleteLater()

        if self.scanned_file_info or self.base_insole_file_info:
            self.create_selected_files_header()


        for file_info in (self.scanned_file_info, self.base_insole_file_info):
            if not file_info:
                continue
            file_name = file_info['file_name']
            # Criação de um QFrame para representar o item
            selec_file_container = QtWidgets.QFrame()
            selec_file_container.setFrameShape(QtWidgets.QFrame.StyledPanel)

            # Horizontal layout for the item
            item_vlayout = QtWidgets.QVBoxLayout(selec_file_container)
            item_hlayout = QtWidgets.QHBoxLayout(selec_file_container)

            file_label = QtWidgets.QLabel(file_name)
            file_label.setStyleSheet("font-size: 14px; font-weight: bold; color: black;")
            item_hlayout.addWidget(file_label)

            description_label = QtWidgets.QLabel(file_info['description'])
            description_label.setStyleSheet("font-size: 12px; color: gray; margin-left: 10px;")
            item_hlayout.addWidget(description_label)

            delete_button = self.create_delete_button(file_name, selec_file_container)
            item_hlayout.addWidget(delete_button)
            item_vlayout.addLayout(item_hlayout)

            # Adding the frame to the vBox container
            self.files_info_container.addWidget(selec_file_container)

            transparency_slider = QtWidgets.QSlider(QtCore.Qt.Horizontal)
            transparency_slider.setMinimum(0)  # Transparência mínima (opaco)
            transparency_slider.setMaximum(100)  # Transparência máxima (totalmente transparente)
            transparency_slider.setValue(100)  # Transparência inicial (opaco)
            transparency_slider.setTickPosition(QtWidgets.QSlider.TicksBelow)
            transparency_slider.setTickInterval(10)
            transparency_slider.valueChanged.connect(lambda value, info=file_info: self.update_mesh_transparency(info['file_name'], value))
            item_vlayout.addWidget(transparency_slider)

    def update_mesh_transparency(self, file_name, value):
        """Atualiza a transparência da malha com base no valor do slider."""
        for attr, display_attr in [
            ("scanned_file_info", "scanned_mesh_display"),
            ("base_insole_file_info", "base_insole_mesh_display")
        ]:
            file_info = getattr(self, attr)
            if (file_info and file_info['file_name'] == file_name):
                mesh_display = getattr(self, display_attr)
                opacity = value / 100.0
                mesh_display.GetProperty().SetOpacity(opacity)  # Define a opacidade da malha
                self.plotter.render()  # Atualiza a renderização do PyVista


    def create_delete_button(self, file_name, container):
        delete_button = QtWidgets.QPushButton()
        delete_button.setIcon(QtGui.QIcon("QT_DESIGN/resources/icons/trash-can-solid.svg"))
        delete_button.setStyleSheet(
            """
            QPushButton {
                background-color: #FF4D4D;  /* Cor de fundo do botão */
                border-radius: 10px;       /* Bordas arredondadas */
                padding: 5px;             /* Espaçamento interno */
            }
            QPushButton:hover {
                background-color: #FF3333;  /* Cor ao passar o mouse */
            }
            """
        )
        delete_button.setFixedSize(30, 30)
        # Usar lambda com parâmetro fixado para evitar erro de referência tardia
        delete_button.clicked.connect(lambda _, item=container, name=file_name: self.remove_file_item(item, name))
        return delete_button

    def create_selected_files_header(self):
        title_label = QtWidgets.QLabel("Arquivos Carregados")
        title_label.setAlignment(QtCore.Qt.AlignCenter)
        title_label.setStyleSheet(
            """
            QLabel {
                background-color: qlineargradient(
                    spread: pad, x1: 0, y1: 0, x2: 1, y2: 0,
                    stop: 0 #007BFF, stop: 1 #00C6FF
                );
                color: white;
                font-size: 16px;
                font-weight: bold;
                padding: 8px;
                border-radius: 10px;
            }
            """
        )
        self.files_info_container.addWidget(title_label)

    def remove_file_item(self, file_item=None, file_name='', remove_all=False):
        # Removing selected file
        for attr, display_attr in [
            ("scanned_file_info", "scanned_mesh_display"), 
            ("base_insole_file_info", "base_insole_mesh_display")
        ]:
            file_info = getattr(self, attr)
            if (file_info and file_info['file_name'] == file_name) or remove_all:
                setattr(self, attr, {})  # Reset the attribute
                display_mesh = getattr(self, display_attr)
                if display_mesh:
                    self.plotter.remove_actor(display_mesh)
                    setattr(self, display_attr, None) # Reset the display attribute

        # Remove o widget do layout
        for i in range(self.files_info_container.count() - 1, -1, -1):
            layout_item = self.files_info_container.itemAt(i)
            if layout_item is None:
                continue
            widget = layout_item.widget()
            if widget == file_item or remove_all:
                # Remove o widget e o exclui
                self.files_info_container.removeWidget(widget)
                widget.deleteLater()

    def update_slider_value(self):
        delta_x = self.offset_x - self.panX.value()
        delta_y = self.offset_y - self.panY.value()
        delta_z = self.offset_z - self.panZ.value()

        self.offset_x = self.panX.value()
        self.offset_y = self.panY.value()
        self.offset_z = self.panZ.value()

        self.scanned_file_info['mesh_scanned'].translate([delta_x, delta_y, delta_z], inplace=True)

    def update_dial_value(self):
        if 'mesh_scanned' in self.scanned_file_info:
            delta_z = self.rotation_angle - self.orbitZ.value()
            self.rotation_angle = self.orbitZ.value()
            self.scanned_file_info['mesh_scanned'] = rotate_mesh(self.scanned_file_info['mesh_scanned'], 0, 0, delta_z, True)

    def load_scan_model(self):
        # Abre o diálogo para seleção de arquivo
        file_path, _ = QtWidgets.QFileDialog.getOpenFileName(self, 'SELECIONAR ARQUIVO ESCANEADO', "", '*.stl')

        # Verifica se nenhum arquivo foi selecionado
        if not file_path:
            return

        # Exibe o indicador de loading e oculta o widget do PyVista
        self.loading_label.show()
        self.plotter.interactor.hide()
        QtWidgets.QApplication.processEvents()  # Atualiza a interface imediatamente

        try:
            # Processa o modelo escaneado
            mesh_scanned = pv.read(file_path)
            mesh_scanned = esphere_filt(mesh_scanned.points, 2)

            self.scanned_file_info = {
                'mesh_scanned': pv.wrap(mesh_scanned).reconstruct_surface(),  # type: ignore
                'file_path': file_path,
                'file_name': os.path.basename(file_path),
                'description': 'Escaneado'
            }

            # Exibe o modelo no PyVista
            self.scanned_mesh_display = self.plotter.add_mesh(self.scanned_file_info['mesh_scanned'], color="lightblue", label="Scanned")
            self.plotter.reset_camera()

            # Atualiza a lista de arquivos carregados
            self.build_files_list()

        except Exception as e:
            QtWidgets.QMessageBox.critical(self, "Erro", f"Ocorreu um erro ao carregar o arquivo: {e}")

        finally:
            # Oculta o indicador de loading e exibe o widget do PyVista
            self.loading_label.hide()
            self.plotter.interactor.show()

    def load_bases(self):

        self.window_loading_bases = SelectBases()
        self.window_loading_bases.closed_signal.connect(self.on_window_loading_bases_closed)
        self.window_loading_bases.show()

    def update_plotter(self):
        """Atualiza o gráfico 3D com o modelo rotacionado sem resetar a câmera ou outras configurações"""
        self.plotter.clear_actors()  # Limpa o gráfico atual
        # Repinta os dois modelos no gráfico
        self.plotter.add_mesh(self.insole_output, color="lightblue", label="Resultado")
        self.plotter.update()  # Atualiza o gráfico sem perder as configurações de exibição

    def cut_insole(self):
        result_1 = self.mesh_parametric.boolean_difference(self.mesh_scanned)
        result_2 = self.mesh_parametric.boolean_intersection(self.mesh_scanned)

        if result_1.volume > result_2.volume:
            self.insole_output = result_1
        else:
            self.insole_output = result_2

        self.update_plotter()

    def set_camera_view(self, view):
        views = {
            "top": [(0, 0, 1), (0, 0, 0), (0, 1, 0)],
            "lateral": [(1, 0, 0), (0, 0, 0), (0, 0, 1)],
            "front": [(0, 1, 0), (0, 0, 0), (0, 0, 1)]
        }

        position, focal, up = views[view]
        self.plotter.camera_position = [position, focal, up]
        self.plotter.reset_camera()

    def on_window_loading_bases_closed(self, message):
        # Esta função será chamada quando a segunda janela for fechada

        base_name = os.path.join(r'QT_DESIGN\palmilhas', message )
        param_insole_mesh = pv.read(base_name)

        self.base_insole_file_info = {
            'mesh_scanned': param_insole_mesh,
            'file_path': base_name,
            'file_name': os.path.basename('BASE'),
            'description': 'Palmilha Base'
        }

        # Remaking surface
        self.base_insole_mesh_display = self.plotter.add_mesh(param_insole_mesh, color="orange", label="Parametric Insole")
        self.plotter.reset_camera()

        self.build_files_list()

class SelectBases(QtWidgets.QMainWindow):
    closed_signal = pyqtSignal(str)
    flag_insert='false'
    def __init__(self):
        super().__init__()
        # Loading interface developed in Qt Designer
        uic.loadUi(r"QT_DESIGN\select_base.ui", self)
        #self.setWindowFlags(Qt.FramelessWindowHint)

        inserir_base = self.findChild(QtWidgets.QPushButton, "btn_inserir_base")
        inserir_base.clicked.connect(self.load_base_padrao)

    def closeEvent(self, event):
        # Emite o sinal ao fechar a janela, passando a string desejada
        if self.flag_insert=='true':
            self.closed_signal.emit(self.base_name)
        event.accept()

    def load_base_padrao(self):
        cb_numeracao = self.findChild(QtWidgets.QComboBox, "CB_numeracao")
        cb_espessura = self.findChild(QtWidgets.QComboBox, "CB_espessura")
        cb_altura = self.findChild(QtWidgets.QComboBox, "CB_calcanhar")
        num=cb_numeracao.currentText()
        esp=cb_espessura.currentText()
        alt=cb_altura.currentText()

        if num == 'Escolha uma opção':
            num=0
        if esp == 'Escolha uma opção':
            esp=0
        if alt == 'Escolha uma opção':
            alt=0

        self.base_name=num+'\\CONTATO_'+esp+'_'+alt+'.STL'
        self.flag_insert='true'

        self.close()



if __name__ == "__main__":
    app = QtWidgets.QApplication(sys.argv)
    app.setStyle('Fusion')
    window_main = MainWindow()
    window_main.show()
    sys.exit(app.exec_())
