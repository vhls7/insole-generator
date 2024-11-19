import pyvista as pv
import trimesh

def repair_stl(input_path, output_path, merge_threshold=1e-4, max_iterations=5):
    """
    Repara uma malha STL, preenchendo buracos e mesclando vértices iterativamente.
    
    :param input_path: Caminho do arquivo STL de entrada.
    :param output_path: Caminho do arquivo STL reparado.
    :param merge_threshold: Tolerância para fusão de vértices próximos (padrão: 1e-4).
    :param max_iterations: Número máximo de iterações para tentativas de reparo.
    :return: True se o reparo foi bem-sucedido, False caso contrário.
    """
    try:
        # Carregar a malha
        mesh = trimesh.load(input_path)
        
        # Garantir que carregamos uma malha Trimesh
        if not isinstance(mesh, trimesh.Trimesh):
            print("O arquivo não contém uma malha válida.")
            return False

        # Exibir informações iniciais
        print(f"Malha carregada: {len(mesh.faces)} faces, {len(mesh.vertices)} vértices.")
        print(f"Malha está fechada: {mesh.is_watertight}")

        for iteration in range(max_iterations):
            if mesh.is_watertight:
                print(f"Malha fechada após {iteration} iteração(ões).")
                break

            # Tentar preencher buracos
            filled_holes = trimesh.repair.fill_holes(mesh)
            print(f"Buracos preenchidos na iteração {iteration}: {filled_holes}")

            # Mesclar vértices próximos
            mesh.merge_vertices(merge_threshold)
            print(f"Vértices mesclados com tolerância {merge_threshold}.")

            # Corrigir normais
            mesh.fix_normals()

        # Verificar se a malha está fechada
        if mesh.is_watertight:
            # Exportar a malha reparada
            mesh.export(output_path)
            print("Malha reparada e exportada com sucesso.")
            return True
        else:
            print("Não foi possível fechar completamente a malha após todas as tentativas.")
            mesh.export(output_path)
            return False
    except Exception as e:
        print(f"Erro ao reparar a malha: {e}")
        return False


# Reparar o objeto novamente
INSOLE_FILE_PATH = r'input_files\CFFFP_Clayton DIreito.stl'
INSOLE_FILE_PATH_OUTPUT = r'output_files\insole_fix.stl'

repair_success_fixed = repair_stl(INSOLE_FILE_PATH, INSOLE_FILE_PATH_OUTPUT)

mesh_fix = pv.read(INSOLE_FILE_PATH)

pl = pv.Plotter()
pl.add_mesh(mesh_fix)
pl.add_title('Superfície Reparada')
pl.show()
