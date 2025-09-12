# data_utils.py
import pandas as pd
import re

def normalizar_compositor(nombre):
    """
    Elimina paréntesis si TODO el nombre está entre paréntesis, y limpia espacios.
    Si el valor es NaN, retorna cadena vacía.
    """
    if pd.isna(nombre):
        return ""
    nombre = str(nombre).strip()
    if nombre.startswith("(") and nombre.endswith(")"):
        return nombre[1:-1].strip()
    return nombre

def unificar_compositores(df: pd.DataFrame) -> pd.DataFrame:
    """
    Reemplaza variantes del mismo compositor (p.ej. con/sin fechas)
    por la versión más completa (normalmente la que incluye fechas).
    Se usa un 'nombre base' = texto antes del primer '(' y sin coma final.
    """
    if "Compositor" not in df.columns:
        return df

    candidatos = df["Compositor"].dropna().unique()
    mapa_unificado = {}

    # Crear mapa: "Apellido, Nombre" -> "Apellido, Nombre (YYYY–YYYY)"
    for nombre in candidatos:
        if "(" in nombre and ")" in nombre:
            base = nombre.split("(")[0].strip().rstrip(",").replace("  ", " ")
            mapa_unificado[base] = nombre

    def reemplazar(n):
        if not isinstance(n, str):
            return n
        base = n.strip().split("(")[0].strip().rstrip(",")
        return mapa_unificado.get(base, n.strip())

    df["Compositor"] = df["Compositor"].apply(reemplazar)
    return df

def cargar_catalogo(csv_path: str) -> pd.DataFrame:
    """
    Lee el CSV en UTF-8 con BOM (utf-8-sig), rellena compositores vacíos con ffill,
    normaliza y unifica nombres.
    """
    df = pd.read_csv(csv_path, encoding="utf-8-sig", index_col=False)
    if "Compositor" in df.columns:
        df["Compositor"] = df["Compositor"].replace("", pd.NA).ffill()
        df["Compositor"] = df["Compositor"].apply(normalizar_compositor)
        df = unificar_compositores(df)
    return df

def preparar_para_guardar(df: pd.DataFrame) -> pd.DataFrame:
    """
    Prepara una versión 'visual' para CSV:
    - Ordena por 'Compositor' (A-Z).
    - Deja en blanco los compositores repetidos (solo visible en el CSV).
    """
    df2 = df.copy()
    if "Compositor" in df2.columns:
        df2.sort_values(by="Compositor", inplace=True, ignore_index=True)
        comp_prev = None
        for i in range(len(df2)):
            comp = df2.at[i, "Compositor"]
            if comp == comp_prev:
                df2.at[i, "Compositor"] = ""
            else:
                comp_prev = comp
    return df2

def formatear_compositor_para_csv(nombre: str) -> str:
    """
    Recibe variantes como:
      - "Esau Medina"
      - "Medina, Esau"
      - "Medina, Esau (1980–)"
      - "Esau Medina (1980–)"
    y devuelve "Apellido, Nombre (fechas)" cuando es posible.
    No toca tildes ni capitalización: respeta lo escrito.
    """
    if not isinstance(nombre, str):
        return ""
    s = nombre.strip()
    if not s:
        return ""

    # Extraer fechas entre paréntesis (si existen) y quitarlas del base
    m = re.search(r"\([^)]*\)", s)
    fechas = m.group(0).strip() if m else ""
    base = (s[:m.start()] + s[m.end():]).strip() if m else s

    # Colapsar espacios
    base = " ".join(base.split())

    # Si ya viene "Apellido, Nombre" => normaliza espacio tras coma
    if "," in base:
        ap, nom = [p.strip() for p in base.split(",", 1)]
        base_fmt = f"{ap}, {nom}" if nom else ap
    else:
        # Asume "Nombre(s) Apellido" (última palabra = apellido)
        trozos = base.split()
        if len(trozos) >= 2:
            ap = trozos[-1]
            nom = " ".join(trozos[:-1])
            base_fmt = f"{ap}, {nom}"
        else:
            # Un solo token: no hay forma de separar con certeza
            base_fmt = base

    return f"{base_fmt} {fechas}".strip()
