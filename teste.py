import pyvista as pv
import numpy as np
from pyvista.core import _vtk_core as _vtk
from pyvista.core.filters import _get_output
from pyvista.core.filters import _update_alg


def smooth(
        malha,
        n_iter=20,
        relaxation_factor=0.01,
        convergence=0.1,
        edge_angle=10,
        feature_angle=70,  ##
        boundary_smoothing=False,
        feature_smoothing=True, #preservação das bordas
        progress_bar=False,
        type='default',
        non_manifold_smoothing=False,
        pass_band=0.01,
        normalize_coordinates=False
    ):
    if type == 'default':
        alg = _vtk.vtkSmoothPolyDataFilter()
        alg.SetInputData(malha)
        alg.SetNumberOfIterations(n_iter)
        alg.SetConvergence(convergence)
        alg.SetFeatureEdgeSmoothing(feature_smoothing)
        alg.SetFeatureAngle(feature_angle)
        alg.SetEdgeAngle(edge_angle)
        alg.SetBoundarySmoothing(boundary_smoothing)
        alg.SetRelaxationFactor(relaxation_factor)
        

        
        _update_alg(alg, progress_bar, 'Smoothing Mesh')
        mesh = _get_output(alg)
        return mesh

    if type == 'taubin':
        alg = _vtk.vtkWindowedSincPolyDataFilter()
        alg.SetInputData(malha)
        alg.SetNumberOfIterations(n_iter)
        alg.SetFeatureEdgeSmoothing(feature_smoothing)
        alg.SetNonManifoldSmoothing(non_manifold_smoothing)
        alg.SetFeatureAngle(feature_angle)
        alg.SetEdgeAngle(edge_angle)
        alg.SetBoundarySmoothing(boundary_smoothing)
        alg.SetPassBand(pass_band)
        alg.SetNormalizeCoordinates(normalize_coordinates)


        _update_alg(alg, progress_bar, 'Smoothing Mesh')
        mesh = _get_output(alg)
        return mesh
    
    return mesh

def profundar_rebaixos(malha, intensidade=0.2):
   
    # Calcular as normais da malha
    malha.compute_normals(inplace=True)

    # Identificar arestas externas e faces externas
    bordas = malha.extract_feature_edges(boundary_edges=True, non_manifold_edges=False)
    ids_borda = np.unique(bordas.points[:, 0])  # Extrair coordenadas X como referência

    # Obter a curvatura gaussiana como uma medida para identificar rebaixos
    curvatura = malha.curvature(curv_type='gaussian')

    # Normalizar a curvatura para a faixa [-1, 1]
    curvatura_normalizada = (curvatura - np.min(curvatura)) / (np.max(curvatura) - np.min(curvatura))
    curvatura_normalizada = 2 * (curvatura_normalizada - 0.5)

    # Criar um vetor de deslocamento baseado na curvatura
    deslocamento = -curvatura_normalizada * intensidade

    # Aplicar deslocamento ao longo das normais apenas nos pontos internos
    novos_pontos = malha.points.copy()
    for i in range(len(novos_pontos)):
        if novos_pontos[i][0] not in ids_borda:  # Checar se o ponto está na borda
            novos_pontos[i] += malha.point_normals[i] * deslocamento[i]

    # Atualizar a malha com os novos pontos
    malha_modificada = malha.copy()
    malha_modificada.points = novos_pontos

    return malha_modificada


def smooth_stl(mesh, feature_angle=70):

    # Detecta arestas nítidas com base no ângulo fornecido
    feature_edges = mesh.extract_feature_edges(feature_angle=feature_angle)

    # Cria uma máscara para identificar células próximas às arestas
    proximity = mesh.compute_cell_sizes()
    proximity["near_feature_edges"] = proximity.cell_centers().select_enclosed_points(
        feature_edges, tolerance=1.0, inside_out=False
    )["SelectedPoints"]

    # Aplica suavização apenas nas células próximas às arestas
    smoothed_mesh = mesh.copy()
    smoothed_mesh =smooth(smoothed_mesh,n_iter=5,type='taubin')

    # Substitui apenas as células suavizadas próximas às arestas
    for i in range(mesh.n_cells):
        if proximity["near_feature_edges"][i]:
            cell_points = mesh.get_cell(i)  # Obter a célula
            cell_point_ids = cell_points.point_ids  # IDs dos pontos da célula
            for pid in cell_point_ids:
                mesh.points[pid] = smoothed_mesh.points[pid]
    print("Suavizado com sucesso!")
    return mesh


# Ler a malha STL
param_insole_mesh = pv.read('./output.stl').triangulate()
#smoothed_mesh_0=profundar_rebaixos(param_insole_mesh, intensidade=0.5)
smoothed_mesh_0=smooth_stl(param_insole_mesh)


smoothed_mesh_1 = smooth(param_insole_mesh,n_iter=50,type='default')
smoothed_mesh_2 = smooth(param_insole_mesh,n_iter=5,type='taubin')
smoothed_mesh_3 = smooth(param_insole_mesh,n_iter=50,type='default')
smoothed_mesh_3 = smooth(smoothed_mesh_3,n_iter=5,type='taubin')



smoothed_mesh_4 = smooth(param_insole_mesh,n_iter=500,type='default')
smoothed_mesh_5 = smooth(param_insole_mesh,n_iter=50,type='taubin')
smoothed_mesh_6 = smooth(param_insole_mesh,n_iter=500,type='default')
smoothed_mesh_6 = smooth(smoothed_mesh_6,n_iter=50,type='taubin')


mask = smoothed_mesh_0.edge_mask(25)

# Configurar o plotter para exibir os resultados
plotter = pv.Plotter(shape=(3, 3))

# Exibir a malha original
plotter.subplot(0, 0)
plotter.add_mesh(param_insole_mesh, color='orange', line_width=0.01,show_edges=False)
plotter.add_text("Original", font_size=10)
# Exibir a malha original
plotter.subplot(0, 1)
plotter.add_mesh(param_insole_mesh, color='orange', scalars=mask, line_width=0.01,show_edges=False)
plotter.add_text("angulos", font_size=10)
# Exibir a malha original
plotter.subplot(0, 2)
plotter.add_mesh(smoothed_mesh_0, color='orange', line_width=0.01,show_edges=False)
plotter.add_text("angulos + aprofundar", font_size=10)

# Exibir a malha suavizada com as arestas exclusivas
plotter.subplot(1, 0)
plotter.add_mesh(smoothed_mesh_1, color='orange', line_width=0.01,show_edges=False)
plotter.add_text("Suavização Padrão - Int=50 ", font_size=10)

# Exibir a malha suavizada com as arestas exclusivas
plotter.subplot(1, 1)
plotter.add_mesh(smoothed_mesh_2, color='orange', line_width=0.01,show_edges=False)
plotter.add_text("Suavização Taubin - Int=5 ", font_size=10)
# Exibir a malha suavizada com as arestas exclusivas

plotter.subplot(1, 2)
plotter.add_mesh(smoothed_mesh_3, color='orange', line_width=0.01,show_edges=False)
plotter.add_text("Suavização Padrão + Taubin - 50 x 5", font_size=10)



# Exibir a malha suavizada com as arestas exclusivas
plotter.subplot(2, 0)
plotter.add_mesh(smoothed_mesh_4, color='orange', line_width=0.01,show_edges=False)
plotter.add_text("Suavização Padrão - Int=500", font_size=10)

# Exibir a malha suavizada com as arestas exclusivas
plotter.subplot(2, 1)
plotter.add_mesh(smoothed_mesh_5, color='orange', line_width=0.01,show_edges=False)
plotter.add_text("Suavização Taubin - Int=50", font_size=10)
# Exibir a malha suavizada com as arestas exclusivas

plotter.subplot(2, 2)
plotter.add_mesh(smoothed_mesh_6, color='orange', line_width=0.01,show_edges=False)
plotter.add_text("Suavização Padrão + Taubin - 500 x 50", font_size=10)

# Mostrar os resultados
plotter.show()
