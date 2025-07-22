import sys
import pandas as pd
from PyQt5.QtWidgets import QWidget, QVBoxLayout, QTableWidget, QPushButton, QTableWidgetItem, QMessageBox, QApplication
from PyQt5.QtCore import Qt
from PyQt5.QtWidgets import QDialog, QLabel, QLineEdit, QDialogButtonBox, QFormLayout


CSV_PATH = "catalogo_inicial.csv"  # Archivo que se cargará por defecto

def normalizar_compositor(nombre):

    """Normaliza el nombre del compositor, elimina paréntesis y espacios"""

    if pd.isna(nombre):
        return ""
    nombre = str(nombre).strip()
    if nombre.startswith("(") and nombre.endswith(")"):
        return nombre[1:-1].strip()
    return nombre

def unificar_compositores(df):
    """Reemplaza variantes de nombres por la versión más completa, puede ser con o sin fechas."""
    candidatos = df["Compositor"].dropna().unique()

    mapa_unificado = {}

    for nombre in candidatos:
        if "(" in nombre and ")" in nombre:
            # Extraer el nombre base sin las fechas
            base = nombre.split("(")[0].strip().rstrip(",")
            base = base.replace("  ", " ")
            # Mapear el nombre base a la versión con fechas
            mapa_unificado[base] = nombre

    def reemplazar(nombre):
        if not isinstance(nombre, str):
            return nombre
        base = nombre.strip().split("(")[0].strip().rstrip(",")
        return mapa_unificado.get(base, nombre.strip())

    df["Compositor"] = df["Compositor"].apply(reemplazar)
    return df


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

class CatalogoEditor(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Editor de Catálogo Electroacústico")
        self.resize(1220, 600)

        self.layout = QVBoxLayout()
        self.setLayout(self.layout)

        self.table = QTableWidget()
        self.layout.addWidget(self.table)

        self.save_button = QPushButton("Guardar cambios")
        self.add_button = QPushButton("Agregar nueva obra")
        self.add_button.clicked.connect(self.agregar_fila)
        self.layout.addWidget(self.add_button)
        self.delete_button = QPushButton("Eliminar obra seleccionada")
        self.delete_button.clicked.connect(self.eliminar_fila)
        self.layout.addWidget(self.delete_button)


        self.save_button.clicked.connect(self.guardar_cambios)
        self.layout.addWidget(self.save_button)

        self.cargar_csv(CSV_PATH)

    def cargar_csv(self, archivo):
        self.df = pd.read_csv(archivo, encoding="utf-8-sig", index_col=False)       
        if "Compositor" in self.df.columns:
            self.df["Compositor"].replace("", pd.NA)
            self.df["Compositor"] = self.df["Compositor"].ffill()
            self.df["Compositor"] = self.df["Compositor"].apply(normalizar_compositor)
            self.df = unificar_compositores(self.df)
        self.table.setRowCount(len(self.df))
        self.table.setColumnCount(len(self.df.columns))
        self.table.setHorizontalHeaderLabels(self.df.columns)

        comp_anterior = None  # Variable para recordar el compositor anterior

        for i in range(len(self.df)):
            for j in range(len(self.df.columns)):
                valor = str(self.df.iat[i, j]) if not pd.isna(self.df.iat[i, j]) else ""

                # Solo mostrar el compositor en la primera aparición visual
                if self.df.columns[j] == "Compositor":
                    if valor == comp_anterior:
                        valor = ""  # Ocultar nombre repetido visualmente
                    else:
                        comp_anterior = valor  # Actualizar referencia

                item = QTableWidgetItem(valor)
                item.setFlags(item.flags() | Qt.ItemIsEditable)
                self.table.setItem(i, j, item)

    def agregar_fila(self):
        dialogo = DialogoAgregarObra(self.df.columns, self)
        if dialogo.exec_() == QDialog.Accepted:
            datos = dialogo.obtener_datos()
            fila_nueva = self.table.rowCount()
            self.table.insertRow(fila_nueva)
            for col, valor in enumerate(datos):
                item = QTableWidgetItem(valor)
                item.setFlags(item.flags() | Qt.ItemIsEditable)
                self.table.setItem(fila_nueva, col, item)


    def eliminar_fila(self):
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
        else:
            QMessageBox.warning(self, "Sin selección", "Selecciona una fila para eliminar.")

    
    def guardar_cambios(self):
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
            df_actualizado.to_csv(CSV_PATH, index=False, encoding="utf-8-sig")
            
            # 💡 Rellenar internamente compositores vacíos antes de normalizar
            df_actualizado["Compositor"].replace("", pd.NA, inplace=True)
            df_actualizado["Compositor"] = df_actualizado["Compositor"].fillna(method="ffill")
            df_actualizado["Compositor"] = df_actualizado["Compositor"].apply(normalizar_compositor)
            df_actualizado = unificar_compositores(df_actualizado)
            
             # ✅ Guardar CSV con primera celda y las siguientes en blanco
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
            self.df = df_actualizado  # Actualiza el DataFrame interno
        except Exception as e:
            QMessageBox.critical(self, "Error", f"No se pudo guardar el archivo:\n{str(e)}")

if __name__ == "__main__":
    app = QApplication(sys.argv)
    ventana = CatalogoEditor()
    ventana.show()
    sys.exit(app.exec_())

