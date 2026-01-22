# storage.py limpio y listo
from __future__ import annotations
from abc import ABC, abstractmethod
import io
import os
import json
import pandas as pd
import streamlit as st

# Google API imports
from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseDownload, MediaIoBaseUpload
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request

# Utilidades de proyecto
from data_utils import normalizar_compositor, unificar_compositores, preparar_para_guardar

SCOPES = ["https://www.googleapis.com/auth/drive"]

class CatalogStorage(ABC):
    @abstractmethod
    def load(self) -> pd.DataFrame:
        ...
    @abstractmethod
    def save(self, df: pd.DataFrame) -> None:
        ...

class DriveStorage(CatalogStorage):
    def __init__(self, file_id: str, credentials_path: str = "credentials.json", token_path: str = "token.json"):
        self.file_id = file_id
        self.credentials_path = credentials_path
        self.token_path = token_path
        
        creds = None
        is_web = False

        # 1. INTENTO PARA LA WEB (Blindado contra errores de Streamlit)
        try:
            if "google" in st.secrets:
                token_info = json.loads(st.secrets["google"]["token"])
                creds = Credentials.from_authorized_user_info(token_info, SCOPES)
                is_web = True
        except Exception:
            # Si no hay secretos (entorno local), simplemente ignoramos
            pass
        
        # 2. INTENTO LOCAL (Si no estamos en la web y el archivo existe)
        if not is_web and os.path.exists(token_path):
            creds = Credentials.from_authorized_user_file(token_path, SCOPES)

        # 3. RENOVACIÓN DE TOKEN (Si expiró)
        if creds and creds.expired and creds.refresh_token:
            from google.auth.transport.requests import Request
            creds.refresh(Request())
            # Solo guardamos el archivo si estamos en local
            if not is_web:
                with open(self.token_path, "w") as f:
                    f.write(creds.to_json())

        # 4. LOGIN INTERACTIVO (Solo si falló todo lo anterior y no es web)
        if not creds or not creds.valid:
            if is_web:
                st.error("Error crítico: Las credenciales de la web no son válidas.")
                st.stop()
            else:
                flow = InstalledAppFlow.from_client_secrets_file(self.credentials_path, SCOPES)
                creds = flow.run_local_server(port=0, access_type='offline', prompt='consent')
                with open(self.token_path, "w") as f:
                    f.write(creds.to_json())

        # CREACIÓN DEL SERVICIO ÚNICO
        self.service = build("drive", "v3", credentials=creds)

    def load(self) -> pd.DataFrame:
        # Usamos self.service directamente
        request = self.service.files().get_media(fileId=self.file_id)
        buf = io.BytesIO()
        downloader = MediaIoBaseDownload(buf, request)

        done = False
        while not done:
            _, done = downloader.next_chunk()

        buf.seek(0)
        df = pd.read_csv(buf, encoding="utf-8-sig", index_col=False)

        if "Compositor" in df.columns:
            df["Compositor"] = df["Compositor"].replace("", pd.NA).ffill()
            df["Compositor"] = df["Compositor"].apply(normalizar_compositor)
            df = unificar_compositores(df)

        return df

    def save(self, df: pd.DataFrame) -> None:
        df_visual = preparar_para_guardar(df)
        csv_bytes = df_visual.to_csv(index=False, encoding="utf-8-sig").encode("utf-8-sig")
        media = MediaIoBaseUpload(io.BytesIO(csv_bytes), mimetype="text/csv", resumable=True)

        # Usamos self.service directamente
        self.service.files().update(
            fileId=self.file_id,
            media_body=media,
            fields="id, modifiedTime"
        ).execute()