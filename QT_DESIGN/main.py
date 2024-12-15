# pylint: disable=I1101, W0401, C0115

import os
import sys

import numpy as np
import pyvista as pv
import resources_rc  # pylint: disable=unused-import
from PyQt5 import QtCore, QtGui, QtWidgets, uic
from pyvistaqt import QtInteractor
from windows.select_bases import SelectBases
from services.api_connector import get_file_from_firebase


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

def esphere_filt(points, radius, self):
    remaining_points = points.copy()
    filtered_points = []
    index=len(remaining_points)
    while len(remaining_points) > 0:
        current_point = remaining_points[0]
        filtered_points.append(current_point)

        distances = np.linalg.norm(remaining_points - current_point, axis=1)

        remaining_points = remaining_points[distances > radius]
        process=round((index-len(remaining_points))*100/(index))
        self.loading_label.setText(f"Aplicando filtro de malha . . . ({process}%)")
        self.update_screen()
        
    return np.array(filtered_points)

def cut_mesh(mesh: pv.PolyData, axis, cut_value=0) -> pv.PolyData:
    """Clip the mesh along a specified axis at a given cut value."""
    bounds = mesh.bounds  # mesh.bounds returns [xmin, xmax, ymin, ymax, zmin, zmax]

    if axis == 'x':
        clip_bounds = [bounds[0], cut_value, bounds[2], bounds[3], bounds[4], bounds[5]]
    elif axis == 'y':
        clip_bounds = [bounds[0], bounds[1], bounds[2], cut_value, bounds[4], bounds[5]]
    elif axis == 'z':
        clip_bounds = [bounds[0], bounds[1], bounds[2], bounds[3], bounds[4], cut_value]
    else:
        raise ValueError("Invalid axis. Choose between 'x', 'y', 'z'.")

    # Clip the mesh with the computed bounds
    cutted_mesh = mesh.clip_box(bounds=clip_bounds, invert=False)

    if cutted_mesh is not None:
        cutted_mesh = cutted_mesh.extract_surface()
        if isinstance(cutted_mesh, pv.PolyData):
            return cutted_mesh
    raise TypeError("Error cutting the file")


class MainWindow(QtWidgets.QMainWindow):
    def __init__(self, application):
        super().__init__()
        self.app = application

        self.window_loading = None
        self.window_select_base = None

        self.scanned_file_info = {}
        self.scanned_mesh_display = None

        self.base_insole_file_info = {}
        self.base_insole_mesh_display = None

        self.output_insole_file_info = {}
        self.output_insole_mesh_display = None

        self.window_loading_bases = None

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
        self.lb_loaded_files = self.findChild(QtWidgets.QLabel, "lb_loaded_files")
        self.lb_loaded_files.setVisible(False)
        # endregion

    def create_loading_component(self):
        loading_label = QtWidgets.QLabel("Carregando...")
        loading_label.setStyleSheet("font-size: 20px; color: red; text-align: center;")
        loading_label.setAlignment(QtCore.Qt.AlignCenter)
        loading_label.hide()  # Oculta inicialmente
        return loading_label

    def update_screen(self):
        self.app.processEvents()

    def build_files_list(self):
        # Cleaning the files_info_container to build from scratch
        while self.files_info_container.count() > 0:
            child = self.files_info_container.takeAt(0)
            if child.widget():
                child.widget().deleteLater()

        if self.scanned_file_info or self.base_insole_file_info:
            self.lb_loaded_files.setVisible(True)
        else:
            self.lb_loaded_files.setVisible(False)


        for file_info in (self.scanned_file_info, self.base_insole_file_info, self.output_insole_file_info):
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
        delete_button.setIcon(QtGui.QIcon(r"QT_DESIGN\resources\icons\trash-can-solid.svg"))
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

    def remove_file_item(self, file_item=None, file_name='', remove_all=False):
        # Removing selected file
        for attr, display_attr in [
            ("scanned_file_info", "scanned_mesh_display"), 
            ("base_insole_file_info", "base_insole_mesh_display"),
            ("output_insole_file_info", "output_insole_mesh_display"),
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
        self.build_files_list()

    def update_slider_value(self):
        delta_x = self.offset_x - self.panX.value()
        delta_y = self.offset_y - self.panY.value()
        delta_z = self.offset_z - self.panZ.value()

        self.offset_x = self.panX.value()
        self.offset_y = self.panY.value()
        self.offset_z = self.panZ.value()

        self.scanned_file_info['mesh'].translate([-delta_x, delta_y, delta_z], inplace=True)

    def update_dial_value(self):
        if 'mesh' in self.scanned_file_info:
            delta_z = self.rotation_angle - self.orbitZ.value()
            self.rotation_angle = self.orbitZ.value()
            self.scanned_file_info['mesh'] = rotate_mesh(self.scanned_file_info['mesh'], 0, 0, delta_z, True)

    def load_scan_model(self):
        # Abre o diálogo para seleção de arquivo
        file_path, _ = QtWidgets.QFileDialog.getOpenFileName(self, 'SELECIONAR ARQUIVO ESCANEADO', "", '*.stl')

        # Verifica se nenhum arquivo foi selecionado
        if not file_path:
            return

        # Exibe o indicador de loading e oculta o widget do PyVista
        self.loading_label.show()
        self.loading_label.setText("Carregando o Modelo . . .")

        self.plotter.interactor.hide()
        self.update_screen()  # Atualiza a interface imediatamente

        try:
            # Processa o modelo escaneado
            mesh_scanned = pv.read(file_path)
            # mesh_scanned = cut_mesh(mesh_scanned, 'z', 15)
            self.loading_label.setText("Aplicando filtro de malha . . .")
            self.update_screen()
            mesh_scanned = esphere_filt(mesh_scanned.points, 3, self)

            self.scanned_file_info = {
                'mesh': pv.wrap(mesh_scanned).reconstruct_surface(), # type: ignore
                'file_path': file_path,
                'file_name': os.path.basename(file_path),
                'description': 'Escaneado'
            }

            # Adding mesh to plot
            if self.scanned_mesh_display:
                self.plotter.remove_actor(self.scanned_mesh_display)
            self.scanned_mesh_display = self.plotter.add_mesh(self.scanned_file_info['mesh'], color="lightblue", label="Scanned")
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

        # Connecting the closing sinal to the function
        self.window_loading_bases.closed_signal.connect(self.load_base_insole)

        # Showing the select base tab
        self.window_loading_bases.show()

    def cut_insole(self):
        output_mesh = self.base_insole_file_info['mesh'].boolean_difference(self.scanned_file_info['mesh'])

        # Removing all the selected files
        self.remove_file_item(remove_all=True)

        self.output_insole_file_info = {
            'mesh': output_mesh,
            'file_path': 'path',
            'file_name': 'Palmilha Gerada',
            'description': 'Informações'
        }
        self.output_insole_mesh_display = self.plotter.add_mesh(output_mesh, color="orange", label="Output Insole")
        self.plotter.reset_camera()

        self.build_files_list()

    def set_camera_view(self, view):
        views = {
            "top": [(0, 0, 1), (0, 0, 0), (0, 1, 0)],
            "lateral": [(1, 0, 0), (0, 0, 0), (0, 0, 1)],
            "front": [(0, 1, 0), (0, 0, 0), (0, 0, 1)]
        }

        position, focal, up = views[view]
        self.plotter.camera_position = [position, focal, up]
        self.plotter.reset_camera()

    def load_base_insole(self, message, side):

        base_name = message
        temp_file_name = get_file_from_firebase(base_name)
        param_insole_mesh = pv.read(temp_file_name)

        if side == 'Esquerdo':
            param_insole_mesh.reflect((1, 0, 0), point=(0, 0, 0), inplace=True)
            param_insole_mesh.flip_normals()

        self.base_insole_file_info = {
            'mesh': param_insole_mesh,
            'file_path': base_name,
            'file_name': 'BASE',
            'description': 'Palmilha Base'
        }

        # Adding mesh to plot
        if self.base_insole_mesh_display:
            self.plotter.remove_actor(self.base_insole_mesh_display)
        self.base_insole_mesh_display = self.plotter.add_mesh(param_insole_mesh, color="orange", label="Parametric Insole")
        self.plotter.reset_camera()

        self.build_files_list()

if __name__ == "__main__":
    app = QtWidgets.QApplication(sys.argv)
    app.setStyle('Fusion')
    window_main = MainWindow(app)
    window_main.show()
    sys.exit(app.exec_())
