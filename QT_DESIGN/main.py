import sys
from PyQt5 import QtWidgets, uic
from PyQt5.QtWidgets import QVBoxLayout
from pyvistaqt import QtInteractor  # Integração PyVista com Qt
import pyvista  # Import necessário para usar recursos do PyVista
import numpy as np


# Caminho do arquivo STL a ser carregado
SCANNED_FILE_PATH = r'input_files\CFFFP_Clayton Esquerdo.stl'
PARAMETRIC_INSOLE_FILE_PATH = r'input_files\ESQ_base45_tipo3_S.stl'

#Variáveis globais 
Pan_X_value=0
Pan_Y_value=0
Pan_Z_value=0
Orbit_Z_value=0

def get_centroid(your_mesh):
    centroid = np.mean(your_mesh.points.reshape(-1, 3), axis=0)
    return centroid
        
def rotate_mesh(mesh: pyvista.PolyData, angle_x=0, angle_y=0, angle_z=0, around_centroid=False) -> pyvista.PolyData:
    centroid = get_centroid(mesh)

    if around_centroid:
        mesh.translate(-centroid, inplace=True)

    mesh.rotate_x(angle_x, inplace=True)
    mesh.rotate_y(angle_y, inplace=True)
    mesh.rotate_z(angle_z, inplace=True)

    if around_centroid:
        mesh.translate(centroid, inplace=True)

    return mesh

def get_centroid(your_mesh):
    centroid = np.mean(your_mesh.points.reshape(-1, 3), axis=0)
    return centroid

def get_centroid2(your_mesh):
    bounds = your_mesh.bounds

    # Calculate the centroid as the average of the min and max coordinates
    centroid = np.array([
        (bounds[0] + bounds[1]) / 2, # x
        (bounds[2] + bounds[3]) / 2, # y
        (bounds[4] + bounds[5]) / 2  # z
    ])
    return centroid
def rotate_mesh(mesh: pyvista.PolyData, angle_x=0, angle_y=0, angle_z=0, around_centroid=False) -> pyvista.PolyData:
    """Rotate the mesh around its centroid."""
    centroid = get_centroid(mesh)

    if around_centroid:
        mesh.translate(-centroid, inplace=True)

    mesh.rotate_x(angle_x, inplace=True)
    mesh.rotate_y(angle_y, inplace=True)
    mesh.rotate_z(angle_z, inplace=True)

    if around_centroid:
        mesh.translate(centroid, inplace=True)

    return mesh

def cut_mesh(mesh: pyvista.PolyData, axis, cut_value=0) -> pyvista.PolyData:
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
        super(MainWindow, self).__init__()
        # Carregar a interface criada no Qt Designer
        uic.loadUi("main.ui", self)
        
        # Obtenha o widget onde o PyVista será inserido
        container = self.findChild(QtWidgets.QWidget, "pyvistaWidget")
        
        # Configurar o layout e adicionar o plotter
        layout = QVBoxLayout()
        self.plotter = QtInteractor(container)
        layout.addWidget(self.plotter.interactor)
        container.setLayout(layout)

        # Conectar o botão
        load = self.findChild(QtWidgets.QPushButton, "btn_load_files")
        load.clicked.connect(self.load_models)

        # Conectar o botão
        Pan_X = self.findChild(QtWidgets.QSlider, "Pan_X")
        Pan_X.valueChanged.connect(self.update_slider_value)

        # Conectar o botão
        Pan_Y = self.findChild(QtWidgets.QSlider, "Pan_Y")
        Pan_Y.valueChanged.connect(self.update_slider_value)

        # Conectar o botão
        Pan_Z = self.findChild(QtWidgets.QSlider, "Pan_Z")
        Pan_Z.valueChanged.connect(self.update_slider_value)

        # Conectar o botão
        Orbit_Z = self.findChild(QtWidgets.QDial, "Orbit_Z")
        Orbit_Z.valueChanged.connect(self.update_dial_value)

        # Conectar o botão
        CUT = self.findChild(QtWidgets.QPushButton, "btn_CUT")
        CUT.clicked.connect(self.CUT_PALMILHA)

        # Conectar o botão
        cam_topo = self.findChild(QtWidgets.QPushButton, "cam_topo")
        cam_topo.clicked.connect(self.TOPO_VIEW)

        
        # Conectar o botão
        cam_lateral = self.findChild(QtWidgets.QPushButton, "cam_lateral")
        cam_lateral.clicked.connect(self.LATERAL_VIEW)

        # Conectar o botão
        cam_frontal = self.findChild(QtWidgets.QPushButton, "cam_frontal")
        cam_frontal.clicked.connect(self.FRONT_VIEW)



    def update_slider_value(self):
        global Pan_X_value
        global Pan_Y_value
        global Pan_Z_value

        delta_X=Pan_X_value-self.Pan_X.value()
        delta_Y=Pan_Y_value-self.Pan_Y.value()
        delta_Z=Pan_Z_value-self.Pan_Z.value()
        Pan_X_value = self.Pan_X.value()
        Pan_Y_value = self.Pan_Y.value()
        Pan_Z_value = self.Pan_Z.value()
        self.mesh_scanned.translate([delta_X, delta_Y, delta_Z], inplace=True)

    def update_dial_value(self):
        global Orbit_Z_value
        delta_Z=Orbit_Z_value-self.Orbit_Z.value()
        Orbit_Z_value = self.Orbit_Z.value()
        self.mesh_scanned = rotate_mesh(self.mesh_scanned, 0, 0, delta_Z, True)

    def load_models(self):
        self.mesh_scanned = pyvista.read(SCANNED_FILE_PATH)  # Lê o arquivo STL do SCANNED_FILE_PATH
        self.mesh_parametric = pyvista.read(PARAMETRIC_INSOLE_FILE_PATH)  # Lê o arquivo STL do PARAMETRIC_INSOLE_FILE_PATH
        # Exibe o arquivo SCANNED_FILE_PATH no gráfico 3D
        self.plotter.add_mesh(self.mesh_scanned, color="lightblue", label="Scanned")
        
        # Exibe o arquivo PARAMETRIC_INSOLE_FILE_PATH no gráfico 3D
        self.plotter.add_mesh(self.mesh_parametric, color="orange", label="Parametric Insole")
        
        # Mostrar a grade e os eixos
        self.plotter.add_axes()
        
        # Ajustar a câmera para se ajustar aos modelos
        self.plotter.reset_camera()

    def update_plotter(self):
        """Atualiza o gráfico 3D com o modelo rotacionado sem resetar a câmera ou outras configurações"""       
        self.plotter.clear_actors()  # Limpa o gráfico atual
        # Repinta os dois modelos no gráfico
        self.plotter.add_mesh(self.result, color="lightblue", label="Resultado")
        self.plotter.update()  # Atualiza o gráfico sem perder as configurações de exibição
    
    def CUT_PALMILHA(self):
        result_1 = self.mesh_parametric.boolean_difference(self.mesh_scanned)
        result_2 = self.mesh_parametric.boolean_intersection(self.mesh_scanned)

        if (result_1.volume>result_2.volume):
            self.result=result_1
        else:
            self.result=result_2
        self.update_plotter()
        

    def TOPO_VIEW(self):
        self.plotter.camera_position = [
            (0, 0, 1),  # Posição da câmera (em Z positivo)
            (0, 0, 0),  # Ponto focal (olhando para a origem)
            (0, 1, 0)   # Vetor "up" (eixo Z positivo aponta para cima)
        ]
        self.plotter.reset_camera()

    def LATERAL_VIEW(self):
        self.plotter.camera_position = [
            (1, 0, 0),  # Posição da câmera (em X positivo)
            (0, 0, 0),  # Ponto focal (olhando para a origem)
            (0, 0, 1)   # Vetor "up" (eixo Z positivo aponta para cima)
        ]
        self.plotter.reset_camera()

    def FRONT_VIEW(self):
        self.plotter.camera_position = [
            (0, 1, 0),  # Posição da câmera (em Y positivo)
            (0, 0, 0),  # Ponto focal (olhando para a origem)
            (0, 0, 1)   # Vetor "up" (eixo Z positivo aponta para cima)
        ]
        self.plotter.reset_camera()

if __name__ == "__main__":
    app = QtWidgets.QApplication(sys.argv)
    app.setStyle('Fusion')
    window = MainWindow()
    window.show()
    sys.exit(app.exec_())