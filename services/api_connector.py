from firebase_admin import credentials, firestore, storage
import firebase_admin

cred = credentials.Certificate(r"propulsao.json")
firebase_admin.initialize_app(cred, {
    'storageBucket': 'site-propulsao-allpe.appspot.com'  # Substitua pelo nome do bucket do Firebase
})

# CONECTAR FIREBASE E STORAGE
db = firestore.client()
bucket = storage.bucket()


# BAIXA O ARQUIVO COM AS PARTES STL DA PALMILHA 
def get_file_from_firebase(caminho):
    try:
        blob = bucket.blob(caminho)
        temp_file_path = r"tmp\temp_file.stl"
        blob.download_to_filename(temp_file_path)
        return temp_file_path
    except Exception as e:
        raise(f"Erro ao baixar arquivo: {e}")