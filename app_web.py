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
    page_icon="🎵"
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
            # Limpieza básica de espacios
            df_loaded["Compositor"] = df_loaded["Compositor"].apply(
                lambda x: pd.NA if pd.isna(x) or str(x).strip() == "" else str(x).strip()
            )
            # Relleno hacia abajo (Forward Fill)
            df_loaded["Compositor"] = df_loaded["Compositor"].ffill()
            # Seguridad final para nulos
            df_loaded["Compositor"] = df_loaded["Compositor"].fillna("")
            
        st.session_state.df = df_loaded

# =====================================================
# UI PRINCIPAL
# =====================================================

st.title("Editor de Catálogo de Música Electroacústica")

# -----------------------------------------------------
# 🔍 BÚSQUEDA
# -----------------------------------------------------

busqueda = st.text_input(
    "🔍 Buscar en el catálogo:",
    placeholder="Ej: Juan Amenábar o nombre de obra"
)

# -----------------------------------------------------
# ➕ AGREGAR OBRA
# -----------------------------------------------------

@st.dialog("Agregar nueva obra")
def agregar_obra_form():
    datos_nuevos = {}
    
    # Creamos campos para todas las columnas
    for col in st.session_state.df.columns:
        datos_nuevos[col] = st.text_input(f"{col}:")

    if st.button("Confirmar registro", type="primary"):
        # Autorelleno inteligente del formato de compositor
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

col_btn, _ = st.columns([1, 4])
with col_btn:
    if st.button("➕ Agregar nueva obra"):
        agregar_obra_form()

# -----------------------------------------------------
# 👁️ VISUALIZACIÓN Y EDICIÓN (Pestañas)
# -----------------------------------------------------

st.divider()
df_original = st.session_state.df

# --- Filtrado ---
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

# Pestañas
tab_vista, tab_edicion = st.tabs(["👁️ Vista Catálogo", "✏️ Editar Tabla"])

# --- PESTAÑA 1: VISTA AGRUPADA (Solo Lectura) ---
with tab_vista:
    if df_filtrado.empty:
        st.info("No se encontraron resultados.")
    else:
        df_sorted = df_filtrado.sort_values(by="Compositor")
        grupos = df_sorted.groupby("Compositor")

        for compositor, obras in grupos:
            with st.expander(f"🎵 {compositor} ({len(obras)} obras)", expanded=False):
                # Mostramos las obras sin repetir la columna compositor
                cols_mostrar = [c for c in obras.columns if c != "Compositor"]
                st.dataframe(
                    obras[cols_mostrar],
                    use_container_width=True,
                    hide_index=True
                )

# --- PESTAÑA 2: EDITOR (Edición Real) ---
with tab_edicion:
    st.caption("💡 Modifica los datos directamente en las celdas.")
    
    df_editado = st.data_editor(
        df_filtrado,
        use_container_width=True,
        hide_index=True,
        num_rows="dynamic",
        key="editor_principal"
    )

    # Sincronización
    if not df_editado.equals(df_filtrado):
        st.session_state.df.update(df_editado)
        # Manejo simple de filas nuevas agregadas directo en la tabla
        if len(df_editado) > len(df_filtrado):
            # Nota: Para agregar obras complejas es mejor usar el botón "Agregar nueva obra",
            # pero esto permite ediciones rápidas.
            pass

# -----------------------------------------------------
# 🗑️ ELIMINAR OBRAS
# -----------------------------------------------------

st.divider()
with st.expander("🗑️ Zona de Eliminación"):
    termino_busqueda_elim = st.text_input(
        "Buscar obras para eliminar:",
        placeholder="Escribe el nombre de la obra..."
    )

    if termino_busqueda_elim:
        mask_elim = st.session_state.df.apply(
            lambda row: row.astype(str).apply(
                lambda cell: coincide_busqueda(cell, termino_busqueda_elim)
            ).any(),
            axis=1
        )
        opciones = st.session_state.df[mask_elim]

        if not opciones.empty:
            lista = opciones.apply(
                lambda x: f"{x['Obra']} - [{x['Compositor']}]",
                axis=1
            ).tolist()

            seleccion = st.multiselect("Selecciona las obras a borrar:", lista)

            if seleccion and st.button("Confirmar eliminación", type="primary"):
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
                # Guardado automático al eliminar para mayor seguridad
                storage.save(st.session_state.df)
                st.success("Obras eliminadas y cambios guardados.")
                st.rerun()

# -----------------------------------------------------
# 🧰 MANTENIMIENTO (Limpio)
# -----------------------------------------------------

st.divider()
st.subheader("Herramientas de Limpieza")

col_m1, col_m2, col_m3 = st.columns(3)

# 1. Normalizar
with col_m1:
    if st.button("🎼 Normalizar Compositores"):
        with st.spinner("Normalizando formatos..."):
            st.session_state.df["Compositor"] = (
                st.session_state.df["Compositor"]
                .astype(str)
                .apply(formatear_compositor_para_csv)
            )
        st.success("Formato 'Apellido, Nombre' aplicado.")

# 2. Duplicados
with col_m2:
    if st.button("🔁 Buscar Duplicados"):
        duplicados = st.session_state.df[
            st.session_state.df.duplicated(subset=["Obra", "Compositor"], keep=False)
        ]
        if duplicados.empty:
            st.info("No hay duplicados exactos.")
        else:
            st.warning(f"Se encontraron {len(duplicados)} filas duplicadas:")
            st.dataframe(duplicados, use_container_width=True)

# 3. Espacios
with col_m3:
    if st.button("🧹 Limpiar Espacios Extra"):
        st.session_state.df = st.session_state.df.applymap(
            lambda x: x.strip() if isinstance(x, str) else x
        )
        st.success("Espacios al inicio y final eliminados.")

# -----------------------------------------------------
# 💾 GUARDAR FINAL
# -----------------------------------------------------

st.divider()
col_save, _ = st.columns([2, 3])
with col_save:
    if st.button("💾 GUARDAR CAMBIOS EN DRIVE", type="primary", use_container_width=True):
        with st.spinner("Sincronizando con Google Drive..."):
            # Blindaje final antes de guardar
            df_a_guardar = st.session_state.df.copy()
            if "Compositor" in df_a_guardar.columns:
                 df_a_guardar["Compositor"] = df_a_guardar["Compositor"].fillna("").replace("", pd.NA).ffill().fillna("")
            
            storage.save(df_a_guardar)
        st.balloons()
        st.success("¡Catálogo actualizado correctamente!")