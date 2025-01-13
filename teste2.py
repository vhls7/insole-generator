import pyvista as pv

def smooth_stl(input_file, feature_angle=70, iterations=100):
    """
    Suaviza arestas em um modelo STL e plota antes e depois.

    Parâmetros:
        input_file (str): Caminho para o arquivo STL de entrada.
        feature_angle (float): Ângulo para detectar bordas nítidas.
        iterations (int): Número de iterações de suavização.
    """
    # Carrega o modelo STL
    mesh = pv.read(input_file)

    # Detecta arestas nítidas com base no ângulo fornecido
    feature_edges = mesh.extract_feature_edges(feature_angle=feature_angle)

    # Cria uma máscara para identificar células próximas às arestas
    proximity = mesh.compute_cell_sizes()
    proximity["near_feature_edges"] = proximity.cell_centers().select_enclosed_points(
        feature_edges, tolerance=1.0, inside_out=False
    )["SelectedPoints"]

    # Aplica suavização apenas nas células próximas às arestas
    smoothed_mesh = mesh.copy()
    smoothed_mesh = smoothed_mesh.smooth(n_iter=iterations, inplace=False,feature_smoothing=True,relaxation_factor=0.05)

    # Substitui apenas as células suavizadas próximas às arestas
    for i in range(mesh.n_cells):
        if proximity["near_feature_edges"][i]:
            cell_points = mesh.get_cell(i)  # Obter a célula
            cell_point_ids = cell_points.point_ids  # IDs dos pontos da célula
            for pid in cell_point_ids:
                mesh.points[pid] = smoothed_mesh.points[pid]

    # Plota o modelo original e suavizado lado a lado
    plotter = pv.Plotter(shape=(1, 2))

    # Malha original
    plotter.subplot(0, 0)
    plotter.add_mesh(pv.read(input_file), color="orange", show_edges=False)
    plotter.add_title("Antes da Suavização")

    # Malha suavizada
    plotter.subplot(0, 1)
    plotter.add_mesh(mesh, color="orange", show_edges=False)
    plotter.add_title("Depois da Suavização")

    plotter.link_views()
    plotter.show()

# Caminho do arquivo STL
input_stl = "output.stl"  # Substitua pelo caminho do seu arquivo STL

# Executa a função de suavização
smooth_stl(input_stl)
