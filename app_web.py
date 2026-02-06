import streamlit as st
import pandas as pd
import unicodedata

from storage import DriveStorage
from data_utils import formatear_compositor_para_csv, preparar_para_guardar


# =====================================================
# UTILIDADES
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
    layout="wide"
)

FILE_ID = "1yu0nemxng0i4Qc_rlTnx7AackuJbebJX"


@st.cache_resource
def inicializar_almacenamiento():
    return DriveStorage(file_id=FILE_ID)


storage = inicializar_almacenamiento()

if "df" not in st.session_state:
    st.session_state.df = storage.load()


# =====================================================
# UI PRINCIPAL
# =====================================================

st.title("Editor de Catálogo de Música Electroacústica")

# -----------------------------------------------------
# 🔍 BÚSQUEDA
# -----------------------------------------------------

busqueda = st.text_input(
    "🔍 Buscar en el catálogo:",
    placeholder="Ej: Juan Amenábar"
)


# -----------------------------------------------------
# ➕ AGREGAR OBRA
# -----------------------------------------------------

@st.dialog("Agregar nueva obra")
def agregar_obra_form():
    datos_nuevos = {}

    for col in st.session_state.df.columns:
        datos_nuevos[col] = st.text_input(f"{col}:")

    if st.button("Confirmar registro"):
        if "Compositor" in datos_nuevos:
            datos_nuevos["Compositor"] = formatear_compositor_para_csv(
                datos_nuevos["Compositor"]
            )

        nueva_fila = pd.DataFrame([datos_nuevos])
        st.session_state.df = pd.concat(
            [st.session_state.df, nueva_fila],
            ignore_index=True
        )
        st.rerun()


col1, col2 = st.columns([1, 4])
with col1:
    if st.button("➕ Agregar nueva obra"):
        agregar_obra_form()


# -----------------------------------------------------
# 📋 TABLA (EDICIÓN SEGURA)
# -----------------------------------------------------

st.subheader("Catálogo")
st.info("💡 Doble clic para editar. La columna Compositor no se guarda vacía.")

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

# --- Vista estética (blanquea repetidos SOLO para mostrar) ---
df_visual = preparar_para_guardar(df_filtrado.copy())

# --- Editor ---
df_editado_visual = st.data_editor(
    df_visual,
    use_container_width=True,
    hide_index=True,
    key="catalogo_editor"
)

# --- Sincronización segura ---
if not df_editado_visual.equals(df_visual):
    for i_visual, fila_visual in df_editado_visual.iterrows():
        idx_real = df_filtrado.index[i_visual]

        for col in df_visual.columns:
            nuevo_valor = fila_visual[col]

            # Nunca sobreescribimos compositor con vacío visual
            if col == "Compositor" and (nuevo_valor == "" or pd.isna(nuevo_valor)):
                continue

            st.session_state.df.at[idx_real, col] = nuevo_valor


# -----------------------------------------------------
# 🗑️ ELIMINAR OBRAS
# -----------------------------------------------------

st.divider()
st.subheader("🗑️ Eliminar obras")

termino_busqueda_elim = st.text_input(
    "Buscar obras para eliminar:",
    placeholder="Ej: Variaciones"
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

        seleccion = st.multiselect("Resultados:", lista)

        if seleccion and st.button("Confirmar eliminación", type="primary"):
            indices = []
            for item in seleccion:
                obra, comp = item.split(" - [")
                comp = comp.replace("]", "")
                idx = st.session_state.df[
                    (st.session_state.df["Obra"] == obra) &
                    (st.session_state.df["Compositor"] == comp)
                ].index
                indices.extend(idx.tolist())

            st.session_state.df = (
                st.session_state.df
                .drop(indices)
                .reset_index(drop=True)
            )

            storage.save(st.session_state.df)
            st.success("Obras eliminadas.")
            st.rerun()


# -----------------------------------------------------
# 🧰 MANTENIMIENTO DEL CATÁLOGO
# -----------------------------------------------------

st.divider()
st.subheader("🧰 Mantenimiento del catálogo")
st.caption("Herramientas internas para limpiar y normalizar el CSV")

col_m1, col_m2, col_m3 = st.columns(3)

# --- Normalizar compositores ---
with col_m1:
    if st.button("🎼 Normalizar compositores"):
        st.session_state.df["Compositor"] = (
            st.session_state.df["Compositor"]
            .astype(str)
            .apply(formatear_compositor_para_csv)
        )
        st.success("Compositores normalizados.")

# --- Detectar duplicados ---
with col_m2:
    if st.button("🔁 Detectar duplicados"):
        duplicados = st.session_state.df[
            st.session_state.df.duplicated(
                subset=["Obra", "Compositor"],
                keep=False
            )
        ]

        if duplicados.empty:
            st.success("No hay duplicados.")
        else:
            st.warning(f"{len(duplicados)} filas duplicadas.")
            st.dataframe(duplicados, use_container_width=True)

# --- Limpiar espacios ---
with col_m3:
    if st.button("🧹 Limpiar espacios"):
        st.session_state.df = st.session_state.df.applymap(
            lambda x: x.strip() if isinstance(x, str) else x
        )
        st.success("Espacios eliminados.")


# -----------------------------------------------------
# 💾 GUARDAR
# -----------------------------------------------------

st.divider()
if st.button("💾 Guardar todos los cambios en Drive"):
    with st.spinner("Sincronizando con Drive…"):
        storage.save(st.session_state.df)
        st.success("Catálogo actualizado correctamente.")
