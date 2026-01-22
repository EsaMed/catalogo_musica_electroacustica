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
        
        # ---LÓGICA PARA LA WEB ---
        try:
            
            if "google" in st.secrets:
                token_info = json.loads(st.secrets["google"]["token"])
                creds = Credentials.from_authorized_user_info(token_info, SCOPES)
        except Exception:
            
            pass
        
        # --- LÓGICA LOCAL DE SIEMPRE ---
        if not creds and os.path.exists(token_path):
            creds = Credentials.from_authorized_user_file(token_path, SCOPES)

        # 3. SI EL TOKEN EXPIRÓ, INTENTAR RENOVARLO
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
            if "google" not in st.secrets:
                with open(self.token_path, "w") as f:
                    f.write(creds.to_json())

        # 4. SI NO HAY CREDENCIALES VÁLIDAS, LOGIN INTERACTIVO
        if not creds or not creds.valid:
            flow = InstalledAppFlow.from_client_secrets_file(self.credentials_path, SCOPES)
            creds = flow.run_local_server(
                port=0, 
                access_type='offline', 
                prompt='consent'
            )
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