import streamlit as st
import pandas as pd
from storage import DriveStorage
# Importamos tu función de formateo para mantener la consistencia
from data_utils import formatear_compositor_para_csv 

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

# --- CUADRO DE DIÁLOGO (SIMULADO CON MODAL) ---
# Usamos st.dialog para crear esa ventana flotante que querías
@st.dialog("Agregar nueva obra")
def agregar_obra_form():
    datos_nuevos = {}
    # Creamos un campo por cada columna del DataFrame original
    for col in st.session_state.df.columns:
        datos_nuevos[col] = st.text_input(f"{col}:")
    
    if st.button("Confirmar Registro"):
        # Aplicamos tu lógica de formateo de compositor antes de guardar
        if "Compositor" in datos_nuevos:
            datos_nuevos["Compositor"] = formatear_compositor_para_csv(datos_nuevos["Compositor"])
        
        # Actualizamos el estado de la aplicación
        nueva_fila = pd.DataFrame([datos_nuevos])
        st.session_state.df = pd.concat([st.session_state.df, nueva_fila], ignore_index=True)
        st.rerun() # Recarga para mostrar la nueva fila

# Botón para abrir el formulario
if st.button("➕ Agregar nueva obra"):
    agregar_obra_form()

# --- VISUALIZACIÓN DE LA TABLA ---
st.subheader("Catálogo")

# 1. Traemos la función que ya escribiste en tu data_utils.py
from data_utils import preparar_para_guardar

# 2. Creamos una versión "estética" del dataframe para mostrar
# Usamos tu lógica de blanquear nombres repetidos
df_estetico = preparar_para_guardar(st.session_state.df)

# 3. Si hay una búsqueda activa, filtramos sobre la versión estética
if busqueda:
    # Nota: buscamos en el original para no perder filas por el "blanqueo"
    mask = st.session_state.df.apply(lambda row: row.astype(str).str.contains(busqueda, case=False).any(), axis=1)
    df_estetico = df_estetico[mask]

# 4. Mostrar la tabla (No editable)
st.dataframe(
    df_estetico,
    use_container_width=True,
    hide_index=True,
)

# --- BOTÓN DE GUARDADO ---
# Importante: Aquí guardamos st.session_state.df (el que tiene todos los datos)
# Tu storage.save() ya se encarga de llamar a preparar_para_guardar internamente.
if st.button("💾 Guardar cambios permanentes en Drive"):
    with st.spinner("Sincronizando con Google Drive..."):
        storage.save(st.session_state.df)
        st.success("¡Catálogo actualizado en la nube!")