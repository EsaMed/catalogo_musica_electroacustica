import streamlit as st
import pandas as pd
import unicodedata
from storage import DriveStorage
from data_utils import formatear_compositor_para_csv, preparar_para_guardar

# --- FUNCIÓN PARA IGNORAR TILDES ---
def remover_tildes(texto):
    """Convierte a minúsculas y elimina acentos de un texto."""
    if not isinstance(texto, str):
        texto = str(texto)
    # Normaliza a NFD (separa la letra del acento) y filtra los acentos
    texto_norm = unicodedata.normalize('NFD', texto)
    return "".join(c for c in texto_norm if unicodedata.category(c) != 'Mn').lower()

st.set_page_config(page_title="Catálogo de Música Electroacústica", layout="wide")

FILE_ID = "1yu0nemxng0i4Qc_rlTnx7AackuJbebJX"

@st.cache_resource
def inicializar_almacenamiento():
    return DriveStorage(file_id=FILE_ID)

storage = inicializar_almacenamiento()

# Inicializar el DataFrame en la sesión si no existe
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

# --- INTERFAZ DE ACCIONES ---
col1, col2 = st.columns([1, 4])
with col1:
    if st.button("➕ Agregar nueva obra"):
        agregar_obra_form()

# --- VISUALIZACIÓN Y EDICIÓN DE LA TABLA ---
st.subheader("Catálogo")
st.info("💡 Puedes editar cualquier celda haciendo doble clic sobre ella. No olvides guardar los cambios al final.")

# Filtrado para visualización
df_mostrar = st.session_state.df

if busqueda:
    busqueda_norm = remover_tildes(busqueda)
    mask = st.session_state.df.apply(
        lambda row: row.astype(str).apply(remover_tildes).str.contains(busqueda_norm).any(), 
        axis=1
    )
    df_mostrar = st.session_state.df[mask]

# Componente de edición
# Editamos directamente sobre df_mostrar y capturamos el resultado
df_editado = st.data_editor(
    df_mostrar,
    use_container_width=True,
    hide_index=True,
    key="catalogo_editor"
)

# Si el usuario editó la tabla, actualizamos el DataFrame principal en la sesión
if not df_editado.equals(df_mostrar):
    # Actualizamos las filas correspondientes en el DataFrame original
    st.session_state.df.update(df_editado)

# --- BLOQUE DE ELIMINACIÓN TIPO BUSCADOR LIMPIO ---
st.divider()
st.subheader("🗑️ Eliminar Obras")

termino_busqueda_elim = st.text_input("Buscar obras para eliminar:", placeholder="Escribe el nombre de la obra o compositor...")

if termino_busqueda_elim:
    termino_norm = remover_tildes(termino_busqueda_elim)
    mask_elim = st.session_state.df.apply(
        lambda row: row.astype(str).apply(remover_tildes).str.contains(termino_norm).any(), 
        axis=1
    )
    opciones_filtradas = st.session_state.df[mask_elim]
    
    if not opciones_filtradas.empty:
        opciones_lista = opciones_filtradas.apply(lambda x: f"{x['Obra']} - [{x['Compositor']}]", axis=1).tolist()
        
        selecciones = st.multiselect(
            f"Resultados para '{termino_busqueda_elim}':",
            options=opciones_lista,
            default=opciones_lista if len(opciones_lista) == 1 else None
        )
        
        if selecciones:
            if st.button(f"Confirmar eliminación de {len(selecciones)} obra(s)", type="primary"):
                indices_a_borrar = []
                for item in selecciones:
                    nombre_obra = item.split(" - [")[0]
                    nombre_comp = item.split(" - [")[1].replace("]", "")
                    idx = st.session_state.df[(st.session_state.df['Obra'] == nombre_obra) & 
                                              (st.session_state.df['Compositor'] == nombre_comp)].index
                    indices_a_borrar.extend(idx.tolist())
                
                st.session_state.df = st.session_state.df.drop(indices_a_borrar).reset_index(drop=True)
                storage.save(st.session_state.df)
                st.success("Eliminación completada.")
                st.rerun()
    else:
        st.warning(f"No se encontraron obras que coincidan con '{termino_busqueda_elim}'")
else:
    st.info("Ingresa un nombre arriba para comenzar a buscar obras.")

# --- BOTÓN DE GUARDADO GENERAL ---
st.divider()
if st.button("💾 Guardar todos los cambios en Drive"):
    with st.spinner("Sincronizando con Google Drive..."):
        storage.save(st.session_state.df)
        st.success("¡Catálogo actualizado en la nube!")