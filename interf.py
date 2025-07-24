import sys
import pandas as pd
from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QTableWidget, QPushButton, QTableWidgetItem,
    QMessageBox, QApplication, QDialog, QLabel, QLineEdit,
    QDialogButtonBox, QFormLayout, QHBoxLayout
)
from PyQt5.QtCore import Qt, QSize
from PyQt5.QtGui import QIcon, QColor

CSV_PATH = "catalogo_inicial.csv"  # Ruta al CSV base

# Funciones auxiliares

def normalizar_compositor(nombre):
    """Elimina paréntesis en nombres de compositores si están rodeando el nombre."""
    if pd.isna(nombre):
        return ""
    nombre = str(nombre).strip()
    if nombre.startswith("(") and nombre.endswith(")"):
        return nombre[1:-1].strip()
    return nombre

def unificar_compositores(df):
    """Reemplaza variantes de nombres por la versión más completa, si incluye fechas."""
    candidatos = df["Compositor"].dropna().unique()
    mapa_unificado = {}
    for nombre in candidatos:
        if "(" in nombre and ")" in nombre:
            base = nombre.split("(")[0].strip().rstrip(",").replace("  ", " ")
            mapa_unificado[base] = nombre

    def reemplazar(nombre):
        if not isinstance(nombre, str):
            return nombre
        base = nombre.strip().split("(")[0].strip().rstrip(",")
        return mapa_unificado.get(base, nombre.strip())

    df["Compositor"] = df["Compositor"].apply(reemplazar)
    return df

# Diálogo para agregar una obra nueva

class DialogoAgregarObra(QDialog):
    def __init__(self, columnas, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Agregar nueva obra")
        self.entradas = {}
        layout = QFormLayout(self)
        for columna in columnas:
            entrada = QLineEdit(self)
            layout.addRow(QLabel(columna), entrada)
            self.entradas[columna] = entrada
        botones = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel, self)
        botones.accepted.connect(self.accept)
        botones.rejected.connect(self.reject)
        layout.addWidget(botones)

    def obtener_datos(self):
        return [self.entradas[col].text() for col in self.entradas]

# Ventana principal

class CatalogoEditor(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Editor de Catálogo Electroacústico")
        self.resize(1350, 600)
        self.layout = QVBoxLayout()
        self.setLayout(self.layout)

        # Tabla principal
        self.table = QTableWidget()
        self.layout.addWidget(self.table)

        # Botones principales
        self.add_button = QPushButton("Agregar nueva obra")
        self.add_button.clicked.connect(self.agregar_fila)
        self.layout.addWidget(self.add_button)

        self.delete_button = QPushButton("Eliminar obra seleccionada")
        self.delete_button.clicked.connect(self.eliminar_fila)
        self.layout.addWidget(self.delete_button)

        # Buscador con campo de texto
        self.search_layout = QHBoxLayout()
        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText("Buscar por compositor, obra, año...")
        self.search_input.returnPressed.connect(self.buscar)  # Ejecutar búsqueda al presionar Enter
        self.search_layout.addWidget(self.search_input)

        self.search_button = QPushButton()
        self.search_button.setIcon(QIcon("lupa.png"))  # Usa ícono local
        self.search_button.setIconSize(QSize(16, 16))
        self.search_button.setFixedWidth(32)
        self.search_button.clicked.connect(self.buscar)
        self.search_layout.addWidget(self.search_button)

        self.reset_button = QPushButton("✖")  # También puede ser "🔄" o "⟳"
        self.reset_button.setToolTip("Restablecer búsqueda")
        self.reset_button.setFixedWidth(28)
        self.reset_button.clicked.connect(self.restablecer_busqueda)
        self.search_layout.addWidget(self.reset_button)

        self.layout.addLayout(self.search_layout)

        self.save_button = QPushButton("Guardar cambios")
        self.save_button.clicked.connect(self.guardar_cambios)
        self.layout.addWidget(self.save_button)

        # Cargar datos iniciales
        self.cargar_csv(CSV_PATH)

    def cargar_csv(self, archivo):
        """Carga y muestra el CSV en la tabla principal."""
        self.df = pd.read_csv(archivo, encoding="utf-8-sig", index_col=False)

        if "Compositor" in self.df.columns:
            self.df["Compositor"] = self.df["Compositor"].replace("", pd.NA)
            self.df["Compositor"] = self.df["Compositor"].ffill()
            self.df["Compositor"] = self.df["Compositor"].apply(normalizar_compositor)
            self.df = unificar_compositores(self.df)

        self.mostrar_tabla(self.df)

    def mostrar_tabla(self, df):
        """Muestra el DataFrame en la tabla, ocultando compositores repetidos."""
        self.table.setRowCount(len(df))
        self.table.setColumnCount(len(df.columns))
        self.table.setHorizontalHeaderLabels(df.columns)

        comp_anterior = None
        for i in range(len(df)):
            for j in range(len(df.columns)):
                valor = str(df.iat[i, j]) if not pd.isna(df.iat[i, j]) else ""

                if df.columns[j] == "Compositor":
                    if valor == comp_anterior:
                        valor = ""
                    else:
                        comp_anterior = valor

                item = QTableWidgetItem(valor)
                item.setFlags(item.flags() | Qt.ItemIsEditable)
                self.table.setItem(i, j, item)

    def agregar_fila(self):
        """Abre un cuadro para ingresar nueva obra. Se añade al final de la tabla y al DataFrame."""
        dialogo = DialogoAgregarObra(self.df.columns, self)
        if dialogo.exec_() == QDialog.Accepted:
            datos = dialogo.obtener_datos()
            fila_nueva = self.table.rowCount()
            self.table.insertRow(fila_nueva)
            for col, valor in enumerate(datos):
                item = QTableWidgetItem(valor)
                item.setFlags(item.flags() | Qt.ItemIsEditable)
                self.table.setItem(fila_nueva, col, item)
            nueva_fila_df = pd.DataFrame([datos], columns=self.df.columns)
            self.df = pd.concat([self.df, nueva_fila_df], ignore_index=True)

    def eliminar_fila(self):
        """Elimina la fila actualmente seleccionada de la tabla y del DataFrame."""
        fila = self.table.currentRow()
        if fila >= 0:
            confirmacion = QMessageBox.question(
                self,
                "Confirmar eliminación",
                "¿Estás seguro de que deseas eliminar esta obra?",
                QMessageBox.Yes | QMessageBox.No
            )
            if confirmacion == QMessageBox.Yes:
                self.table.removeRow(fila)
                self.df = self.df.drop(self.df.index[fila]).reset_index(drop=True)
        else:
            QMessageBox.warning(self, "Sin selección", "Selecciona una fila para eliminar.")

    def guardar_cambios(self):
        """Guarda los datos desde la tabla en el CSV, ordenados alfabéticamente por compositor."""
        datos_actualizados = []
        for i in range(self.table.rowCount()):
            fila = []
            for j in range(self.table.columnCount()):
                item = self.table.item(i, j)
                valor = item.text() if item else ""
                fila.append(valor)
            datos_actualizados.append(fila)

        try:
            columnas = [self.table.horizontalHeaderItem(i).text() for i in range(self.table.columnCount())]
            df_actualizado = pd.DataFrame(datos_actualizados, columns=columnas)

            # Limpieza y normalización
            df_actualizado["Compositor"] = df_actualizado["Compositor"].replace("", pd.NA)
            df_actualizado["Compositor"] = df_actualizado["Compositor"].ffill()
            df_actualizado["Compositor"] = df_actualizado["Compositor"].apply(normalizar_compositor)
            df_actualizado = unificar_compositores(df_actualizado)

            # Orden alfabético por compositor antes de guardar
            df_actualizado.sort_values(by="Compositor", inplace=True, ignore_index=True)

            # Visualización limpia: ocultar compositores repetidos
            df_visual = df_actualizado.copy()
            comp_anterior = None
            for i in range(len(df_visual)):
                comp_actual = df_visual.at[i, "Compositor"]
                if comp_actual == comp_anterior:
                    df_visual.at[i, "Compositor"] = ""
                else:
                    comp_anterior = comp_actual

            df_visual.to_csv(CSV_PATH, index=False, encoding="utf-8-sig")

            QMessageBox.information(self, "Éxito", "Archivo guardado correctamente.")
            self.df = df_actualizado

        except Exception as e:
            QMessageBox.critical(self, "Error", f"No se pudo guardar el archivo:\n{str(e)}")

    def buscar(self):
        """Filtra visualmente las filas que contengan el texto ingresado."""
        texto = self.search_input.text().strip().lower()
        for fila in range(self.table.rowCount()):
            visible = False
            for columna in range(self.table.columnCount()):
                item = self.table.item(fila, columna)
                if item and texto in item.text().lower():
                    visible = True
                    break
            self.table.setRowHidden(fila, not visible)

    def restablecer_busqueda(self):
        """Muestra todas las filas ocultas y borra el campo de búsqueda."""
        for fila in range(self.table.rowCount()):
            self.table.setRowHidden(fila, False)
        self.search_input.clear()

# Inicio de la aplicación
if __name__ == "__main__":
    app = QApplication(sys.argv)
    ventana = CatalogoEditor()
    ventana.show()
    sys.exit(app.exec_())