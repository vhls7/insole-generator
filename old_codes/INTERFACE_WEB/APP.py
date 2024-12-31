import sys
import pyvista as pv
from PyQt5.QtWidgets import QApplication, QWidget, QVBoxLayout, QHBoxLayout, QPushButton
from pyvistaqt import QtInteractor  # Importando QtInteractor de pyvistaqt
import numpy as np

# Caminho do arquivo STL a ser carregado
SCANNED_FILE_PATH = r'input_files\CFFFP_Clayton Esquerdo.stl'
PARAMETRIC_INSOLE_FILE_PATH = r'input_files\ESQ_base45_tipo3_S.stl'

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

class App(QWidget):
    def __init__(self):
        super().__init__()
        
        self.initUI()
        self.setup_vtk()
        
    def initUI(self):
        """Configura a interface gráfica"""
        self.setWindowTitle('Visualizador 3D de Arquivo STL')
        self.setGeometry(100, 100, 1000, 600)
        
        # Layout principal (horizontal)
        main_layout = QHBoxLayout()
        
        # Layout para os botões na primeira coluna
        button_layout = QVBoxLayout()
        
        # Botão para rotacionar o modelo em 5 graus ao redor do eixo X
        self.button_x = QPushButton('Rotacionar em X (5°)', self)
        self.button_x.clicked.connect(self.rotate_x)  # Conectar o botão à função de rotação em X
        button_layout.addWidget(self.button_x)
        
        # Botão para rotacionar o modelo em 5 graus ao redor do eixo Y
        self.button_y = QPushButton('Rotacionar em Y (5°)', self)
        self.button_y.clicked.connect(self.rotate_y)  # Conectar o botão à função de rotação em Y
        button_layout.addWidget(self.button_y)
        
        # Botão para rotacionar o modelo em 5 graus ao redor do eixo Z
        self.button_z = QPushButton('Rotacionar em Z (5°)', self)
        self.button_z.clicked.connect(self.rotate_z)  # Conectar o botão à função de rotação em Z
        button_layout.addWidget(self.button_z)
        
        # Configurar a primeira coluna com os botões
        main_layout.addLayout(button_layout)
        
        # Configurar a segunda coluna com o gráfico
        self.plotter = QtInteractor(self)  # Criando o QtInteractor do pyvistaqt
        self.plotter.setGeometry(0, 0, 800, 600)  # Tamanho e posição da área do gráfico
        main_layout.addWidget(self.plotter)  # Adiciona o plotter ao layout

        # Definir o layout principal
        self.setLayout(main_layout)
        

    def setup_vtk(self):

        """Configura o gráfico 3D com os arquivos STL"""
        # Carregar os arquivos STL nas suas coordenadas originais
        self.mesh_scanned = pv.read(SCANNED_FILE_PATH)  # Lê o arquivo STL do SCANNED_FILE_PATH
        self.mesh_parametric = pv.read(PARAMETRIC_INSOLE_FILE_PATH)  # Lê o arquivo STL do PARAMETRIC_INSOLE_FILE_PATH

        self.mesh_scanned = rotate_mesh(self.mesh_scanned, 0, 0, 90, True)

        # Exibe o arquivo SCANNED_FILE_PATH no gráfico 3D
        self.plotter.add_mesh(self.mesh_scanned, color="lightblue", label="Scanned")
        
        # Exibe o arquivo PARAMETRIC_INSOLE_FILE_PATH no gráfico 3D
        self.plotter.add_mesh(self.mesh_parametric, color="orange", label="Parametric Insole")
        
        # Mostrar a grade e os eixos
        self.plotter.show_grid()
        self.plotter.add_axes()
        
        # Ajustar a câmera para se ajustar aos modelos
        self.plotter.reset_camera()

    def rotate_x(self):
        """Rotaciona o modelo SCANNED_FILE_PATH 5 graus ao redor do eixo X"""
        self.mesh_scanned = rotate_mesh(self.mesh_scanned, 5, 0, 0, True)
        #self.mesh_scanned.rotate_x(5)  # Rotaciona o modelo 5 graus em torno do eixo X
        self.update_plotter()

    def rotate_y(self):
        """Rotaciona o modelo SCANNED_FILE_PATH 5 graus ao redor do eixo Y"""
        self.mesh_scanned = rotate_mesh(self.mesh_scanned, 0, 5, 0, True)
        self.update_plotter()

    def rotate_z(self):
        """Rotaciona o modelo SCANNED_FILE_PATH 5 graus ao redor do eixo Z"""
        self.mesh_scanned = rotate_mesh(self.mesh_scanned, 0, 0, 5, True)
        self.update_plotter()

    def update_plotter(self):
        """Atualiza o gráfico 3D com o modelo rotacionado sem resetar a câmera ou outras configurações"""       
        self.plotter.clear_actors()  # Limpa o gráfico atual
        # Repinta os dois modelos no gráfico
        self.plotter.add_mesh(self.mesh_scanned, color="lightblue", label="Scanned")
        self.plotter.add_mesh(self.mesh_parametric, color="orange",  label="Parametric Insole")
        # Mostrar a grade e os eixos
        self.plotter.show_grid()
        self.plotter.add_axes()
        # Ajustar a câmera para se ajustar aos modelos
        self.plotter.update()  # Atualiza o gráfico sem perder as configurações de exibição
        self.plotter.reset_camera()

    def closeEvent(self, event):
        """Fecha a aplicação corretamente"""
        self.plotter.close()  # Fecha o plotter
        event.accept()

if __name__ == '__main__':
    app = QApplication(sys.argv)
    ex = App()
    ex.show()
    sys.exit(app.exec())  # Executa a aplicação
