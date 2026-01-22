import streamlit as st
import pandas as pd
from storage import DriveStorage
from data_utils import formatear_compositor_para_csv, preparar_para_guardar

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
        # Nota: Aquí no guardamos en Drive aún, solo en la sesión
        st.rerun()

# --- INTERFAZ DE ACCIONES ---
col1, col2 = st.columns([1, 4])
with col1:
    if st.button("➕ Agregar nueva obra"):
        agregar_obra_form()

# --- VISUALIZACIÓN DE LA TABLA ---
st.subheader("Catálogo")

# Creamos la versión estética (con nombres blanqueados si se repiten)
df_estetico = preparar_para_guardar(st.session_state.df)

# Filtro de búsqueda
if busqueda:
    mask = st.session_state.df.apply(lambda row: row.astype(str).str.contains(busqueda, case=False).any(), axis=1)
    df_estetico = df_estetico[mask]

st.dataframe(
    df_estetico,
    use_container_width=True,
    hide_index=True,
)

# --- BLOQUE DE ELIMINACIÓN TIPO BUSCADOR LIMPIO ---
st.divider()
st.subheader("🗑️ Eliminar Obras")

# 1. Cuadro de texto para la búsqueda (Sin flechas, solo texto)
termino_busqueda = st.text_input("Buscar obras para eliminar:", placeholder="Escribe el nombre de la obra o compositor...")

if termino_busqueda:
    # 2. Filtramos las opciones basadas en lo que escribiste
    opciones_filtradas = st.session_state.df[
        st.session_state.df.apply(lambda row: row.astype(str).str.contains(termino_busqueda, case=False).any(), axis=1)
    ]
    
    if not opciones_filtradas.empty:
        # 3. Solo si hay resultados, mostramos el multiselect para confirmar la selección
        opciones_lista = opciones_filtradas.apply(lambda x: f"{x['Obra']} - [{x['Compositor']}]", axis=1).tolist()
        
        selecciones = st.multiselect(
            f"Resultados para '{termino_busqueda}':",
            options=opciones_lista,
            default=opciones_lista if len(opciones_lista) == 1 else None, # Si solo hay uno, lo pre-selecciona
            help="Selecciona de la lista los que realmente quieres borrar"
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
        st.warning(f"No se encontraron obras que coincidan con '{termino_busqueda}'")
else:
    st.info("Ingresa un nombre arriba para comenzar a buscar obras.")

# --- BOTÓN DE GUARDADO GENERAL ---
st.divider()
if st.button("💾 Guardar todos los cambios en Drive"):
    with st.spinner("Sincronizando con Google Drive..."):
        storage.save(st.session_state.df)
        st.success("¡Catálogo actualizado en la nube!")