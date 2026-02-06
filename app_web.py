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
    placeholder="Ej: Compositor, año, nombre de obra"
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

# --- PESTAÑA 1: VISTA POR COMPOSITOR (Editable) ---
with tab_vista:
    if df_filtrado.empty:
        st.info("No se encontraron resultados.")
    else:
        # Ordenamos
        df_sorted = df_filtrado.sort_values(by="Compositor")
        grupos = df_sorted.groupby("Compositor")

        # Lógica de expansión automática al buscar
        estado_expansion = True if busqueda else False

        for compositor, obras in grupos:
            # Creamos el expander
            with st.expander(f"🎵 {compositor} ({len(obras)} obras)", expanded=estado_expansion):
                
                # 1. Preparamos los datos para mostrar (ocultando columna Compositor)
                cols_mostrar = [c for c in obras.columns if c != "Compositor"]
                
                # 2. Mostramos el EDITOR en lugar de solo ver
                # Importante: key=f"editor_{compositor}" hace que cada tabla sea independiente
                cambios = st.data_editor(
                    obras[cols_mostrar],
                    use_container_width=True,
                    hide_index=True,
                    key=f"editor_{compositor}" # Clave única por compositor
                )

                # 3. LÓGICA DE GUARDADO EN TIEMPO REAL
                # Si la tabla editada (cambios) es diferente a la original (obras)...
                # (Comparamos solo las columnas mostradas para evitar falsos positivos)
                if not cambios.equals(obras[cols_mostrar]):
                    
                    # Iteramos sobre los índices originales de las obras modificadas
                    for i in cambios.index:
                        # Recuperamos la fila editada
                        fila_editada = cambios.loc[i]
                        
                        # Actualizamos el DataFrame Maestro (st.session_state.df)
                        # Usamos 'i' que es el índice original, así es IMPOSIBLE que se corra.
                        for col in cols_mostrar:
                            st.session_state.df.at[i, col] = fila_editada[col]
                    
                    # Opcional: Mostrar un mensajito discreto de "guardado" o simplemente dejar que fluya
                    # st.toast(f"Cambios guardados para {compositor}")

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
st.subheader("🗑️ Eliminar una obra")

# El buscador queda visible directamente
termino_busqueda_elim = st.text_input(
    "Busca la obra a eliminar por título, compositor, año, etc.:",
    placeholder="..."
)

# Lógica de búsqueda y eliminación
if termino_busqueda_elim:
    # Filtramos usando la función de búsqueda que ya tienes
    mask_elim = st.session_state.df.apply(
        lambda row: row.astype(str).apply(
            lambda cell: coincide_busqueda(cell, termino_busqueda_elim)
        ).any(),
        axis=1
    )
    opciones = st.session_state.df[mask_elim]

    if not opciones.empty:
        # Preparamos la lista legible
        lista = opciones.apply(
            lambda x: f"{x['Obra']} - [{x['Compositor']}]",
            axis=1
        ).tolist()

        # El multiselect aparece abierto/disponible apenas hay resultados
        seleccion = st.multiselect("Selecciona las obras que quieres borrar:", lista)

        if seleccion:
            st.warning(f"⚠️ Estás a punto de eliminar {len(seleccion)} obra(s).")
            
            if st.button("Confirmar eliminación", type="primary"):
                indices = []
                for item in seleccion:
                    partes = item.split(" - [")
                    if len(partes) >= 2:
                        obra = partes[0]
                        comp = partes[1].replace("]", "")
                        
                        # Buscamos los índices reales en el DF
                        idx = st.session_state.df[
                            (st.session_state.df["Obra"] == obra) &
                            (st.session_state.df["Compositor"] == comp)
                        ].index
                        indices.extend(idx.tolist())

                # Eliminamos y reseteamos el índice
                st.session_state.df = st.session_state.df.drop(indices).reset_index(drop=True)
                
                # Guardado automático de seguridad
                storage.save(st.session_state.df)
                
                st.success("Obras eliminadas correctamente.")
                st.rerun()
    else:
        st.info("No se encontraron obras con ese nombre.")

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