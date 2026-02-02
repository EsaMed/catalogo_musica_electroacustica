import streamlit as st
import json

st.write("Secrets keys:", st.secrets.keys())

if "google" in st.secrets:
    st.write("Google secret found")
    st.write("Google keys:", st.secrets["google"].keys())


import pandas as pd
import unicodedata
from storage import DriveStorage
from data_utils import formatear_compositor_para_csv, preparar_para_guardar

# --- FUNCIÓN PARA IGNORAR TILDES ---
def remover_tildes(texto):
    if not isinstance(texto, str):
        texto = str(texto)
    texto_norm = unicodedata.normalize('NFD', texto)
    return "".join(c for c in texto_norm if unicodedata.category(c) != 'Mn').lower()

st.set_page_config(page_title="Catálogo de Música Electroacústica", layout="wide")

FILE_ID = "1yu0nemxng0i4Qc_rlTnx7AackuJbebJX"

@st.cache_resource
def inicializar_almacenamiento():
    return DriveStorage(file_id=FILE_ID)

storage = inicializar_almacenamiento()

if 'df' not in st.session_state:
    st.session_state.df = storage.load()

st.title("Editor de Catálogo de Música Electroacústica")

# --- BLOQUE DE BÚSQUEDA ---
busqueda = st.text_input("🔍 Buscar en el catálogo:", placeholder="Ej: Juan Amenábar")

# --- CUADRO DE DIÁLOGO PARA AGREGAR ---
@st.dialog("Agregar nueva obra")
def agregar_obra_form():
    datos_nuevos = {}
    for col in st.session_state.df.columns:
        datos_nuevos[col] = st.text_input(f"{col}:")
    
    if st.button("Confirmar Registro"):
        if "Compositor" in datos_nuevos:
            datos_nuevos["Compositor"] = formatear_compositor_para_csv(datos_nuevos["Compositor"])
        
        nueva_fila = pd.DataFrame([datos_nuevos])
        st.session_state.df = pd.concat([st.session_state.df, nueva_fila], ignore_index=True)
        st.rerun()

col1, col2 = st.columns([1, 4])
with col1:
    if st.button("➕ Agregar nueva obra"):
        agregar_obra_form()

# --- VISUALIZACIÓN Y EDICIÓN DE LA TABLA ---
st.subheader("Catálogo")
st.info("💡 Haz doble clic en una celda para editar.")

# 1. Filtramos el DataFrame original según la búsqueda
df_filtrado = st.session_state.df
if busqueda:
    busqueda_norm = remover_tildes(busqueda)
    mask = st.session_state.df.apply(
        lambda row: row.astype(str).apply(remover_tildes).str.contains(busqueda_norm).any(), 
        axis=1
    )
    df_filtrado = st.session_state.df[mask]

# 2. CREAMOS LA VERSIÓN ESTÉTICA (Nombres blanqueados)
# Usamos tu función preparar_para_guardar para ocultar nombres repetidos
df_visual = preparar_para_guardar(df_filtrado.copy())

# 3. Componente de edición sobre la versión visual
df_editado_visual = st.data_editor(
    df_visual,
    use_container_width=True,
    hide_index=True,
    key="catalogo_editor"
)

# 4. SINCRONIZACIÓN INTELIGENTE
# Si hubo cambios, debemos pasar esos cambios de vuelta al DataFrame original
if not df_editado_visual.equals(df_visual):
    # Identificamos qué cambió (ignorando las celdas vacías que pusimos por estética)
    for index_visual, row_visual in df_editado_visual.iterrows():
        real_idx = df_filtrado.index[index_visual]
        
        # Actualizamos todas las columnas excepto el Compositor si este viene vacío (blanqueado)
        for col in df_editado_visual.columns:
            valor_nuevo = row_visual[col]
            # Solo actualizamos si el valor no es el "blanqueo" o si es una edición real
            if col == "Compositor" and (valor_nuevo == "" or valor_nuevo is None):
                continue
            st.session_state.df.at[real_idx, col] = valor_nuevo

# --- BLOQUE DE ELIMINACIÓN ---
# (Se mantiene igual que tu versión funcional actual)
st.divider()
st.subheader("🗑️ Eliminar Obras")
termino_busqueda_elim = st.text_input("Buscar obras para eliminar:", placeholder="Escribe el nombre...")

if termino_busqueda_elim:
    termino_norm = remover_tildes(termino_busqueda_elim)
    mask_elim = st.session_state.df.apply(
        lambda row: row.astype(str).apply(remover_tildes).str.contains(termino_norm).any(), 
        axis=1
    )
    opciones_filtradas = st.session_state.df[mask_elim]
    
    if not opciones_filtradas.empty:
        opciones_lista = opciones_filtradas.apply(lambda x: f"{x['Obra']} - [{x['Compositor']}]", axis=1).tolist()
        selecciones = st.multiselect(f"Resultados para '{termino_busqueda_elim}':", options=opciones_lista)
        
        if selecciones:
            if st.button(f"Confirmar eliminación", type="primary"):
                indices = []
                for item in selecciones:
                    nombre_obra = item.split(" - [")[0]
                    nombre_comp = item.split(" - [")[1].replace("]", "")
                    idx = st.session_state.df[(st.session_state.df['Obra'] == nombre_obra) & 
                                              (st.session_state.df['Compositor'] == nombre_comp)].index
                    indices.extend(idx.tolist())
                st.session_state.df = st.session_state.df.drop(indices).reset_index(drop=True)
                storage.save(st.session_state.df)
                st.success("Eliminado.")
                st.rerun()

st.divider()
if st.button("💾 Guardar todos los cambios en Drive"):
    with st.spinner("Sincronizando..."):
        storage.save(st.session_state.df)
        st.success("¡Catálogo actualizado!")