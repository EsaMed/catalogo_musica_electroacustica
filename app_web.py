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
    initial_sidebar_state="expanded"
)

# ---BLOQUEAR BARRA LATERAL ---
st.markdown("""
    <style>
    /* Oculta la flecha/botón para colapsar el sidebar */
    [data-testid="stSidebarCollapsedControl"] {
        display: none;
    }
    </style>
""", unsafe_allow_html=True)

FILE_ID = "1yu0nemxng0i4Qc_rlTnx7AackuJbebJX"

@st.cache_resource
def inicializar_almacenamiento():
    return DriveStorage(file_id=FILE_ID)

storage = inicializar_almacenamiento()

# --- CARGA DE DATOS (Blindada) ---
if "df" not in st.session_state:
    with st.spinner("Cargando catálogo..."):
        df_loaded = storage.load()
        if "Compositor" in df_loaded.columns:
            df_loaded["Compositor"] = df_loaded["Compositor"].apply(
                lambda x: pd.NA if pd.isna(x) or str(x).strip() == "" else str(x).strip()
            )
            df_loaded["Compositor"] = df_loaded["Compositor"].ffill()
            df_loaded["Compositor"] = df_loaded["Compositor"].fillna("")
            
        st.session_state.df = df_loaded

# =====================================================
# 💾 BARRA LATERAL (GUARDADO)
# =====================================================

with st.sidebar:
    #st.header("Guardar cambios en Drive")
    #st.info("💾")
    
    if st.button("💾 GUARDAR CAMBIOS EN DRIVE", type="primary", use_container_width=True):
        with st.spinner("Sincronizando..."):
            df_a_guardar = st.session_state.df.copy()
            if "Compositor" in df_a_guardar.columns:
                 df_a_guardar["Compositor"] = df_a_guardar["Compositor"].fillna("").replace("", pd.NA).ffill().fillna("")
            storage.save(df_a_guardar)
        st.success("✅ Sincronizado correctamente.")

# =====================================================
# LÓGICA DE AGREGAR OBRA (MODAL / VENTANITA)
# =====================================================

@st.dialog("Agregar nueva obra")
def agregar_obra_form():
    st.write("Ingresa los datos de la nueva obra:")
    datos_nuevos = {}
    
    # Formulario limpio
    columnas = list(st.session_state.df.columns)
    for col in columnas:
        datos_nuevos[col] = st.text_input(f"{col}:")

    if st.button("Confirmar registro", type="primary"):
        # Normalizar y guardar
        if "Compositor" in datos_nuevos and datos_nuevos["Compositor"]:
            datos_nuevos["Compositor"] = formatear_compositor_para_csv(
                datos_nuevos["Compositor"]
            )

        nueva_fila = pd.DataFrame([datos_nuevos])
        st.session_state.df = pd.concat(
            [st.session_state.df, nueva_fila],
            ignore_index=True
        )
        st.rerun()

# =====================================================
# UI PRINCIPAL
# =====================================================

st.title("Editor de Catálogo Electroacústico")

# -----------------------------------------------------
# 🛠️ PANEL DE ACCIONES (2 BOTONES SUPERIORES)
# -----------------------------------------------------

# Creamos dos columnas para los botones de acción
col_accion_1, col_accion_2 = st.columns(2)

# --- BOTÓN 1: AGREGAR (Abre Ventanita) ---
with col_accion_1:
    if st.button("➕ Agregar nueva obra", use_container_width=True):
        agregar_obra_form()

# --- BOTÓN 2: ELIMINAR (Despliega Buscador) ---
with col_accion_2:
    # Usamos un expander que actúa visualmente como un botón que despliega herramientas
    with st.expander("🗑️ Eliminar una obra (Clic para desplegar)"):
        termino_elim = st.text_input(
            "Buscar obra a eliminar:",
            placeholder="...",
            key="input_eliminar"
        )
        
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
                        storage.save(st.session_state.df)
                        st.success("Obras eliminadas.")
                        st.rerun()
            else:
                st.caption("No se encontraron coincidencias.")

st.divider()

# -----------------------------------------------------
# 🔍 BÚSQUEDA Y VISTA DEL CATÁLOGO
# -----------------------------------------------------

busqueda = st.text_input(
    "🔍 Buscar en el catálogo:",
    placeholder="Ej: Obra, compositor, año..."
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

# Pestañas de visualización (solo para ver o ver todo)
tab_vista, tab_tabla = st.tabs(["👁️ Vista Catálogo (Editable)", "✏️ Tabla Completa"])

# --- VISTA 1: ACORDEONES EDITABLES (Segura) ---
with tab_vista:
    if df_filtrado.empty:
        st.info("No se encontraron resultados.")
    else:
        df_sorted = df_filtrado.sort_values(by="Compositor")
        grupos = df_sorted.groupby("Compositor")
        
        # Expande solo si buscas
        estado_expansion = True if busqueda else False

        for compositor, obras in grupos:
            with st.expander(f"🎵 {compositor} ({len(obras)} obras)", expanded=estado_expansion):
                cols_mostrar = [c for c in obras.columns if c != "Compositor"]
                
                # Configuración anti-scroll accidental (Texto)
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
    st.caption("Es posible editar sobre las celdas...")
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
