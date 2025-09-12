# storage.py
from __future__ import annotations
from abc import ABC, abstractmethod
import io

import pandas as pd

# Google API imports
from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseDownload, MediaIoBaseUpload
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
import os

# Utilidades de tu proyecto
from data_utils import normalizar_compositor, unificar_compositores, preparar_para_guardar

# Alcance: lectura/escritura sobre archivos del usuario
SCOPES = ["https://www.googleapis.com/auth/drive"]

class CatalogStorage(ABC):
    @abstractmethod
    def load(self) -> pd.DataFrame:
        """Devuelve el catálogo como DataFrame ya normalizado."""
        ...

    @abstractmethod
    def save(self, df: pd.DataFrame) -> None:
        """Guarda el catálogo (versión visual) de vuelta en el mismo recurso."""
        ...

class DriveStorage(CatalogStorage):
    """
    Implementa almacenamiento en Google Drive para un archivo CSV identificado por fileId.
    credentials.json: archivo OAuth descargado desde GCP
    token.json: se crea/actualiza automáticamente tras la primera autorización.
    """
    def __init__(self, file_id: str, credentials_path: str = "credentials.json", token_path: str = "token.json"):
        self.file_id = file_id
        self.credentials_path = credentials_path
        self.token_path = token_path
        self.service = self._get_service()

    def _get_service(self):
        creds = None
        if os.path.exists(self.token_path):
            creds = Credentials.from_authorized_user_file(self.token_path, SCOPES)
        if not creds or not creds.valid:
            if creds and creds.expired and creds.refresh_token:
                # Intento de refresh (si tienes refresh_token)
                from google.auth.transport.requests import Request
                creds.refresh(Request())
            else:
                # Primer login interactivo (abre navegador)
                flow = InstalledAppFlow.from_client_secrets_file(self.credentials_path, SCOPES)
                creds = flow.run_local_server(port=0)
            # Guardar token para próximas ejecuciones
            with open(self.token_path, "w") as f:
                f.write(creds.to_json())

        return build("drive", "v3", credentials=creds)

    # ---------------------------
    # Lectura
    # ---------------------------
    def load(self) -> pd.DataFrame:
        """
        Descarga el CSV desde Drive y retorna DataFrame ya normalizado/unificado,
        emulando tu flujo local actual.
        """
        request = self.service.files().get_media(fileId=self.file_id)
        buf = io.BytesIO()
        downloader = MediaIoBaseDownload(buf, request)

        done = False
        while not done:
            status, done = downloader.next_chunk()

        buf.seek(0)
        # Lee CSV desde bytes (el archivo en Drive debe estar en texto CSV UTF-8)
        df = pd.read_csv(buf, encoding="utf-8-sig", index_col=False)

        # Normalización igual que antes (relleno, limpieza y unificación)
        if "Compositor" in df.columns:
            df["Compositor"] = df["Compositor"].replace("", pd.NA).ffill()
            df["Compositor"] = df["Compositor"].apply(normalizar_compositor)
            df = unificar_compositores(df)

        return df

    # ---------------------------
    # Escritura
    # ---------------------------
    def save(self, df: pd.DataFrame) -> None:
        """
        Aplica preparar_para_guardar(df) para:
          - ordenar por Compositor
          - “blanquear” repetidos
        y sube el CSV actualizado como nueva versión del mismo fileId.
        """
        df_visual = preparar_para_guardar(df)

        # Serializar a CSV (bytes)
        csv_bytes = df_visual.to_csv(index=False, encoding="utf-8-sig").encode("utf-8-sig")
        media = MediaIoBaseUpload(io.BytesIO(csv_bytes), mimetype="text/csv", resumable=True)

        # Actualizar el mismo archivo (nueva versión)
        self.service.files().update(
            fileId=self.file_id,
            media_body=media,
            fields="id, modifiedTime"
        ).execute()
