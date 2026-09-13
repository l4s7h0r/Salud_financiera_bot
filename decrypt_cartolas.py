import os
import io
import json
from google.oauth2 import service_account
from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseDownload, MediaIoBaseUpload
from pypdf import PdfReader, PdfWriter

FOLDER_ID = '1bi-yrLPXtqbJnZxdptRKJxX4pKaX21fo'
PASSWORDS = ['20347130', '7130', '20347']

def get_drive_service():
    service_account_info = json.loads(os.environ['GDRIVE_SERVICE_ACCOUNT_KEY'])
    credentials = service_account.Credentials.from_service_account_info(
        service_account_info,
        scopes=['https://www.googleapis.com/auth/drive']
    )
    return build('drive', 'v3', credentials=credentials)

def process_pdfs():
    service = get_drive_service()
    
    # Listar PDFs en la carpeta
    query = f"'{FOLDER_ID}' in parents and mimeType = 'application/pdf' and trashed = false"
    results = service.files().list(q=query, fields="files(id, name, description)").execute()
    files = results.get('files', [])
    
    print(f"Total de archivos encontrados: {len(files)}")
    
    for file in files:
        file_id = file['id']
        file_name = file['name']
        description = file.get('description', '')

        # Si ya fue procesado, se omite
        if description == 'desencriptado':
            continue

        print(f"\nVerificando: {file_name} ({file_id})")

        # Descargar archivo a memoria
        request = service.files().get_media(fileId=file_id)
        fh = io.BytesIO()
        downloader = MediaIoBaseDownload(fh, request)
        done = False
        while not done:
            status, done = downloader.next_chunk()
        
        fh.seek(0)
        try:
            reader = PdfReader(fh)
        except Exception as e:
            print(f"Error al leer PDF {file_name}: {e}")
            continue

        if not reader.is_encrypted:
            print(f"-> Ya está desencriptado. Marcando metadato...")
            service.files().update(fileId=file_id, body={'description': 'desencriptado'}).execute()
            continue

        # Intentar desencriptar con las contraseñas conocidas
        unlocked = False
        for pwd in PASSWORDS:
            if reader.decrypt(pwd) != 0:
                print(f"-> Desencriptado con éxito usando clave: {pwd}")
                unlocked = True
                break
        
        if not unlocked:
            print(f"-> No se pudo desencriptar con las claves provistas.")
            continue

        # Escribir PDF sin clave
        writer = PdfWriter()
        for page in reader.pages:
            writer.add_page(page)

        output_stream = io.BytesIO()
        writer.write(output_stream)
        output_stream.seek(0)

        # Actualizar el archivo existente en Drive
        media = MediaIoBaseUpload(output_stream, mimetype='application/pdf', resumable=True)
        updated_file = service.files().update(
            fileId=file_id,
            body={'description': 'desencriptado'},
            media_body=media
        ).execute()

        print(f"-> Archivo actualizado en Google Drive sin contraseña.")

if __name__ == '__main__':
    process_pdfs()