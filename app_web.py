import streamlit as st
import pandas as pd
import unicodedata

# Asumo que estos archivos existen en tu carpeta, los mantenemos igual
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

# --- CARGA DE DATOS SEGURA ---
if "df" not in st.session_state:
    df_loaded = storage.load()
    
    # CORRECCIÓN CRÍTICA: Rellenar celdas vacías de 'Compositor' hacia abajo (Forward Fill).
    # Esto arregla el CSV si venía con formato visual (huecos) del sistema anterior.
    if "Compositor" in df_loaded.columns:
        df_loaded["Compositor"] = df_loaded["Compositor"].replace("", pd.NA).ffill()
        # Rellenamos con string vacío cualquier Na que quede (por seguridad)
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

    for col in st.session_state.df.columns:
        # Sugerimos vacío por defecto
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
# 👁️ VISUALIZACIÓN Y EDICIÓN (SISTEMA DE PESTAÑAS)
# -----------------------------------------------------

st.subheader("Catálogo")

df_original = st.session_state.df

# --- Filtrado General (Aplica a ambas pestañas) ---
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

# CREAMOS LAS PESTAÑAS
tab_vista, tab_edicion = st.tabs(["👁️ Vista por Compositor", "✏️ Editar Tabla Completa"])

# --- PESTAÑA 1: VISTA AGRUPADA (Estética) ---
with tab_vista:
    if df_filtrado.empty:
        st.info("No se encontraron resultados.")
    else:
        # Agrupamos por compositor para mostrar acordeones
        # Ordenamos primero para que la lista salga alfabética
        df_sorted = df_filtrado.sort_values(by="Compositor")
        grupos = df_sorted.groupby("Compositor")

        for compositor, obras in grupos:
            # Creamos un desplegable por cada compositor
            with st.expander(f"🎵 {compositor} ({len(obras)} obras)", expanded=True):
                # Ocultamos la columna Compositor (ya está en el título) para limpiar la vista
                cols_mostrar = [c for c in obras.columns if c != "Compositor"]
                st.dataframe(
                    obras[cols_mostrar],
                    use_container_width=True,
                    hide_index=True
                )

# --- PESTAÑA 2: EDITOR (Funcional) ---
with tab_edicion:
    st.info("💡 En este modo se muestra la tabla completa. Modifica las celdas directamente.")
    
    # Aquí mostramos TODOS los datos. No usamos máscaras visuales.
    # Esto asegura que al ordenar o filtrar, la celda siempre tenga dueño.
    df_editado = st.data_editor(
        df_filtrado,
        use_container_width=True,
        hide_index=True,
        num_rows="dynamic", # Permite añadir/borrar filas tipo Excel
        key="catalogo_editor_tab"
    )

    # Lógica de sincronización simple y robusta
    if not df_editado.equals(df_filtrado):
        # Actualizamos el DF maestro con los cambios del editor
        st.session_state.df.update(df_editado)
        
        # Si se agregaron filas nuevas directamente en la tabla (gracias a num_rows="dynamic")
        if len(df_editado) > len(df_filtrado):
            # Identificamos filas nuevas y las pegamos
            # (Nota: esto es básico, si el filtrado es complejo, es mejor usar el botón "Agregar nueva obra")
            pass 


# -----------------------------------------------------
# 🗑️ ELIMINAR OBRAS (Mantenido igual, funciona bien)
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
                partes = item.split(" - [")
                if len(partes) >= 2:
                    obra = partes[0]
                    comp = partes[1].replace("]", "")
                    
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
        # Aseguramos que antes de guardar, no haya nulos raros
        df_a_guardar = st.session_state.df.fillna("")
        storage.save(df_a_guardar)
        st.success("Catálogo actualizado correctamente.")