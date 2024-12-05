# pylint: disable=I1101, W0401

import os
import sys

import numpy as np
import pyvista as pv
import resources_rc
from PyQt5 import QtWidgets, uic
from PyQt5.QtCore import Qt  # pylint: disable=no-name-in-module
from PyQt5.QtGui import *
from PyQt5.QtWidgets import *
from pyvistaqt import QtInteractor

# Caminho do arquivo STL a ser carregado
SCANNED_FILE_PATH = r'input_files\CFFFP_Clayton Esquerdo.stl'
PARAMETRIC_INSOLE_FILE_PATH = r'input_files\base45_tipo3_S.stl'

pan_x_value = 0
pan_y_value = 0
pan_z_value = 0

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

def get_centroid2(your_mesh):
    bounds = your_mesh.bounds

    # Calculate the centroid as the average of the min and max coordinates
    centroid = np.array([
        (bounds[0] + bounds[1]) / 2, # x
        (bounds[2] + bounds[3]) / 2, # y
        (bounds[4] + bounds[5]) / 2  # z
    ])
    return centroid

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
        self.layout = QVBoxLayout() # pylint: disable=undefined-variable
        self.plotter = QtInteractor(pyvista_widget)
        self.plotter.add_axes()

        self.layout.addWidget(self.plotter.interactor)
        pyvista_widget.setLayout(self.layout)

        # region Connecting buttons to functions
        load_scan = self.findChild(QtWidgets.QPushButton, "loadScanButton")
        load_scan.clicked.connect(self.load_scan_model)

        load_base = self.findChild(QtWidgets.QPushButton, "loadBaseButton")
        load_base.clicked.connect(self.load_bases)

        pan_x = self.findChild(QtWidgets.QSlider, "panX")
        pan_x.valueChanged.connect(self.update_slider_value)

        pan_y = self.findChild(QtWidgets.QSlider, "panY")
        pan_y.valueChanged.connect(self.update_slider_value)

        pan_z = self.findChild(QtWidgets.QSlider, "panZ")
        pan_z.valueChanged.connect(self.update_slider_value)

        orbit_z = self.findChild(QtWidgets.QDial, "orbitZ")
        orbit_z.valueChanged.connect(self.update_dial_value)

        cut_but = self.findChild(QtWidgets.QPushButton, "cutButton")
        cut_but.clicked.connect(self.cut_insole)

        top_cam = self.findChild(QtWidgets.QPushButton, "topCam")
        top_cam.clicked.connect(lambda: self.set_camera_view('top'))

        lat_cam = self.findChild(QtWidgets.QPushButton, "latCam")
        lat_cam.clicked.connect(lambda: self.set_camera_view('lateral'))

        front_cam = self.findChild(QtWidgets.QPushButton, "frontCam")
        front_cam.clicked.connect(lambda: self.set_camera_view('front'))

        clean_but = self.findChild(QtWidgets.QPushButton, "cleanButton")
        clean_but.clicked.connect(self.clean_plot)

        self.files_info_container = self.findChild(QtWidgets.QVBoxLayout, "filesInfoContainer")
        # endregion

    def build_files_list(self):
        # Cleaning the files_info_container to build from scratch
        while self.files_info_container.count() > 0:
            child = self.files_info_container.takeAt(0)
            if child.widget():
                child.widget().deleteLater()

        for file_info in (self.scanned_file_info, self.base_insole_file_info):
            if not file_info:
                continue
            file_name = file_info['file_name']
            # Criação de um QFrame para representar o item
            selec_file_container = QtWidgets.QFrame()
            selec_file_container.setFrameShape(QtWidgets.QFrame.StyledPanel)

            # Horizontal layout for the item
            item_hlayout = QtWidgets.QHBoxLayout(selec_file_container)

            file_label = QtWidgets.QLabel(file_name)
            item_hlayout.addWidget(file_label)

            description_label = QtWidgets.QLabel(file_info['description'])
            item_hlayout.addWidget(description_label)

            delete_button = QtWidgets.QPushButton()
            delete_button.setIcon(self.style().standardIcon(QtWidgets.QStyle.SP_TrashIcon))

            # Usar lambda com parâmetro fixado para evitar erro de referência tardia
            delete_button.clicked.connect(lambda _, item=selec_file_container, name=file_name: self.remove_file_item(item, name))
            item_hlayout.addWidget(delete_button)

            # Adding the frame to the vBox container
            self.files_info_container.addWidget(selec_file_container)

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

        # Starting the loading component
        self.window_loading = loading()
        self.window_loading.show()

        # Getting file name
        file_path, _ = QFileDialog.getOpenFileName(self, 'SELECIONAR ARQUIVO ESCANEADO', "", '*.stl') # pylint: disable=undefined-variable

        # Reading and filtering file
        mesh_scanned = pv.read(file_path)
        mesh_scanned = esphere_filt(mesh_scanned.points, 2)

        # Remaking surface
        self.scanned_file_info = {
            'mesh_scanned': pv.wrap(mesh_scanned).reconstruct_surface(), # type: ignore
            'file_path': file_path,
            'file_name': os.path.basename(file_path),
            'description': 'Escaneado'
        }

        # Generating 3D plot
        self.scanned_mesh_display = self.plotter.add_mesh(self.scanned_file_info['mesh_scanned'], color="lightblue", label="Scanned")
        self.plotter.reset_camera()

        self.build_files_list()

        # Interrupting the loading component
        self.window_loading.close()

    def load_bases(self):

        # Starting the loading component
        self.window_loading = loading()
        self.window_loading.show()

        # Getting file name
        file_path, _ = QFileDialog.getOpenFileName(self, 'SELECIONAR ARQUIVO DA PALMILHA',"",'*.stl') # pylint: disable=undefined-variable
        param_insole_mesh = pv.read(file_path)  # Lê o arquivo STL do SCANNED_FILE_PATH

        self.base_insole_file_info = {
            'mesh_scanned': param_insole_mesh,
            'file_path': file_path,
            'file_name': os.path.basename(file_path),
            'description': 'Palmilha Base'
        }

        # Remaking surface
        self.base_insole_mesh_display = self.plotter.add_mesh(param_insole_mesh, color="orange", label="Parametric Insole")
        self.plotter.reset_camera()

        self.build_files_list()

        # Interrupting the loading component
        self.window_loading.close()

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

    def clean_plot(self):
        self.remove_file_item(remove_all=True)


class loading(QtWidgets.QDialog):
    def __init__(self):
        super().__init__()
        # Loading interface developed in Qt Designer
        uic.loadUi(r"QT_DESIGN\loading.ui", self)
        self.setWindowFlags(Qt.FramelessWindowHint)



if __name__ == "__main__":
    app = QtWidgets.QApplication(sys.argv)
    app.setStyle('Fusion')
    window_main = MainWindow()
    window_main.show()
    sys.exit(app.exec_())
