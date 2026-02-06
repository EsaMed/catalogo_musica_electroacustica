import streamlit as st
import pandas as pd
import unicodedata

# Importamos solo lo necesario
from storage import DriveStorage
from data_utils import formatear_compositor_para_csv

# =====================================================
# UTILIDADES INTERNAS
# =====================================================

def remover_tildes(texto):
    if not isinstance(texto, str):
        texto = str(texto)
    texto_norm = unicodedata.normalize("NFD", texto)
    return "".join(c for c in texto_norm if unicodedata.category(c) != "Mn").lower()

def coincide_busqueda(texto, busqueda):
    if not texto or not busqueda:
        return False
    texto_norm = remover_tildes(texto)
    palabras = remover_tildes(busqueda).split()
    return all(p in texto_norm for p in palabras)

# =====================================================
# CONFIGURACIÓN APP
# =====================================================

st.set_page_config(
    page_title="Catálogo de Música Electroacústica",
    layout="wide",
    page_icon="🎵",
    initial_sidebar_state="expanded" # Barra lateral abierta por defecto
)

FILE_ID = "1yu0nemxng0i4Qc_rlTnx7AackuJbebJX"

@st.cache_resource
def inicializar_almacenamiento():
    return DriveStorage(file_id=FILE_ID)

storage = inicializar_almacenamiento()

# --- CARGA DE DATOS (Con blindaje automático) ---
if "df" not in st.session_state:
    with st.spinner("Cargando catálogo..."):
        df_loaded = storage.load()
        
        # BLINDAJE: Si vienen huecos del pasado, los rellenamos en memoria al instante.
        if "Compositor" in df_loaded.columns:
            df_loaded["Compositor"] = df_loaded["Compositor"].apply(
                lambda x: pd.NA if pd.isna(x) or str(x).strip() == "" else str(x).strip()
            )
            df_loaded["Compositor"] = df_loaded["Compositor"].ffill()
            df_loaded["Compositor"] = df_loaded["Compositor"].fillna("")
            
        st.session_state.df = df_loaded

# =====================================================
# 💾 BARRA LATERAL (GUARDADO PINEADO)
# =====================================================

with st.sidebar:
    st.header("💾 Control de Cambios")
    st.info("El botón de guardar está siempre disponible aquí.")
    
    # Botón grande y visible
    if st.button("GUARDAR CAMBIOS EN DRIVE", type="primary", use_container_width=True):
        with st.spinner("Sincronizando..."):
            # Blindaje final antes de guardar
            df_a_guardar = st.session_state.df.copy()
            
            # Asegurar consistencia de datos (rellenar huecos)
            if "Compositor" in df_a_guardar.columns:
                 df_a_guardar["Compositor"] = df_a_guardar["Compositor"].fillna("").replace("", pd.NA).ffill().fillna("")
            
            storage.save(df_a_guardar)
            
        st.success("✅ Sincronizado correctamente.")

# =====================================================
# UI PRINCIPAL
# =====================================================

st.title("Editor de Catálogo Electroacústico")

# -----------------------------------------------------
# 🛠️ ZONA DE GESTIÓN (AGREGAR / ELIMINAR)
# -----------------------------------------------------

# Pestañas de gestión
tab_add, tab_del = st.tabs(["➕ Agregar Obra", "🗑️ Eliminar Obra"])

# --- PESTAÑA AGREGAR (Formulario directo) ---
with tab_add:
    st.write("Ingresa los datos de la nueva obra:")
    
    # Usamos st.form para agrupar los campos y evitar recargas mientras escribes
    # clear_on_submit=True limpia el formulario automáticamente al guardar.
    with st.form("form_alta_obra", clear_on_submit=True):
        datos_nuevos = {}
        
        # Organizamos los campos en 2 columnas para que no sea una lista eterna
        col1, col2 = st.columns(2)
        columnas = list(st.session_state.df.columns)
        mitad = len(columnas) // 2
        
        # Primera mitad de campos
        with col1:
            for col in columnas[:mitad]:
                datos_nuevos[col] = st.text_input(f"{col}:")
        
        # Segunda mitad de campos
        with col2:
            for col in columnas[mitad:]:
                datos_nuevos[col] = st.text_input(f"{col}:")

        st.markdown("---")
        submitted = st.form_submit_button("Confirmar registro", type="primary")

        if submitted:
            # 1. Normalización automática del Compositor
            if "Compositor" in datos_nuevos and datos_nuevos["Compositor"]:
                datos_nuevos["Compositor"] = formatear_compositor_para_csv(
                    datos_nuevos["Compositor"]
                )

            # 2. Agregar al DataFrame
            nueva_fila = pd.DataFrame([datos_nuevos])
            st.session_state.df = pd.concat(
                [st.session_state.df, nueva_fila],
                ignore_index=True
            )
            
            # 3. Feedback inmediato
            st.success("✅ Obra agregada al listado (Recuerda guardar en Drive al finalizar).")
            # No usamos st.rerun() aquí para dejar ver el mensaje de éxito y limpiar el form

# --- PESTAÑA ELIMINAR ---
with tab_del:
    col_del_1, col_del_2 = st.columns([1, 2])
    with col_del_1:
        termino_elim = st.text_input(
            "Buscar obra a eliminar:",
            placeholder="Escribe el nombre...",
            key="input_eliminar"
        )
    
    with col_del_2:
        if termino_elim:
            mask_elim = st.session_state.df.apply(
                lambda row: row.astype(str).apply(
                    lambda cell: coincide_busqueda(cell, termino_elim)
                ).any(),
                axis=1
            )
            opciones = st.session_state.df[mask_elim]

            if not opciones.empty:
                lista = opciones.apply(
                    lambda x: f"{x['Obra']} - [{x['Compositor']}]",
                    axis=1
                ).tolist()

                seleccion = st.multiselect("Selecciona obras:", lista, key="multi_eliminar")

                if seleccion:
                    if st.button("Confirmar eliminación", type="primary"):
                        indices = []
                        for item in seleccion:
                            partes = item.split(" - [")
                            if len(partes) >= 2:
                                obra = partes[0]
                                comp = partes[1].replace("]", "")
                                idx = st.session_state.df[
                                    (st.session_state.df["Obra"] == obra) &
                                    (st.session_state.df["Compositor"] == comp)
                                ].index
                                indices.extend(idx.tolist())

                        st.session_state.df = st.session_state.df.drop(indices).reset_index(drop=True)
                        # Auto-guardado de seguridad al eliminar
                        storage.save(st.session_state.df)
                        st.success("Obras eliminadas.")
                        st.rerun()
            else:
                st.caption("No se encontraron coincidencias.")
# -----------------------------------------------------
# 🔍 BÚSQUEDA Y VISTA PRINCIPAL
# -----------------------------------------------------

busqueda = st.text_input(
    "🔍 Buscar en el catálogo:",
    placeholder="Ej: Juan Amenábar o nombre de obra"
)

df_original = st.session_state.df
df_filtrado = df_original

if busqueda:
    tokens = remover_tildes(busqueda).split()
    mask = df_original.apply(
        lambda row: any(
            all(t in remover_tildes(str(cell)) for t in tokens)
            for cell in row
        ),
        axis=1
    )
    df_filtrado = df_original[mask]

# Pestañas de visualización
tab_vista, tab_tabla = st.tabs(["👁️ Vista Catálogo (Editable)", "✏️ Tabla Completa"])

# --- VISTA 1: ACORDEONES EDITABLES ---
with tab_vista:
    if df_filtrado.empty:
        st.info("No se encontraron resultados.")
    else:
        df_sorted = df_filtrado.sort_values(by="Compositor")
        grupos = df_sorted.groupby("Compositor")
        estado_expansion = True if busqueda else False

        for compositor, obras in grupos:
            with st.expander(f"🎵 {compositor} ({len(obras)} obras)", expanded=estado_expansion):
                cols_mostrar = [c for c in obras.columns if c != "Compositor"]
                
                # Configuración de seguridad para scroll (Texto plano)
                configuracion_cols = {
                    "Año": st.column_config.TextColumn("Año", help="Año (Texto)"),
                    "Duración": st.column_config.TextColumn("Duración", help="Duración"),
                }

                cambios = st.data_editor(
                    obras[cols_mostrar],
                    use_container_width=True,
                    hide_index=True,
                    column_config=configuracion_cols,
                    key=f"editor_{compositor}"
                )

                if not cambios.equals(obras[cols_mostrar]):
                    for i in cambios.index:
                        fila_editada = cambios.loc[i]
                        for col in cols_mostrar:
                            st.session_state.df.at[i, col] = fila_editada[col]

# --- VISTA 2: TABLA COMPLETA ---
with tab_tabla:
    st.caption("Esta vista muestra la tabla completa sin agrupar.")
    df_editado = st.data_editor(
        df_filtrado,
        use_container_width=True,
        hide_index=True,
        num_rows="dynamic",
        key="editor_principal"
    )
    if not df_editado.equals(df_filtrado):
        st.session_state.df.update(df_editado)

# -----------------------------------------------------
# MANTENIMIENTO (Limpio)
# -----------------------------------------------------


# st.divider()
# st.subheader("Herramientas de Limpieza")

# col_m1, col_m2, col_m3 = st.columns(3)

# # 1. Normalizar
# with col_m1:
#     if st.button("🎼 Normalizar Compositores"):
#         with st.spinner("Normalizando formatos..."):
#             st.session_state.df["Compositor"] = (
#                 st.session_state.df["Compositor"]
#                 .astype(str)
#                 .apply(formatear_compositor_para_csv)
#             )
#         st.success("Formato 'Apellido, Nombre' aplicado.")

# # 2. Duplicados
# with col_m2:
#     if st.button("🔁 Buscar Duplicados"):
#         duplicados = st.session_state.df[
#             st.session_state.df.duplicated(subset=["Obra", "Compositor"], keep=False)
#         ]
#         if duplicados.empty:
#             st.info("No hay duplicados exactos.")
#         else:
#             st.warning(f"Se encontraron {len(duplicados)} filas duplicadas:")
#             st.dataframe(duplicados, use_container_width=True)

# # 3. Espacios
# with col_m3:
#     if st.button("🧹 Limpiar Espacios Extra"):
#         st.session_state.df = st.session_state.df.applymap(
#             lambda x: x.strip() if isinstance(x, str) else x
#         )
#         st.success("Espacios al inicio y final eliminados.")
