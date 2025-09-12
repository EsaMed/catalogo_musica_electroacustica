# editor.py
import pandas as pd
from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QTableWidget, QTableWidgetItem, QPushButton,
    QMessageBox, QLineEdit, QHBoxLayout, QDialog, QFormLayout, QLabel,
    QDialogButtonBox, QHeaderView
)
from PyQt5.QtCore import Qt, QSize
from PyQt5.QtGui import QIcon, QPen, QPainter, QColor

from data_utils import (
    cargar_catalogo, preparar_para_guardar,
    normalizar_compositor, unificar_compositores
)
import unicodedata
import re
# ---------------------------
# Diálogo para agregar obra
# ---------------------------

class ColoredHeader(QHeaderView):
    """
    QHeaderView personalizado que pinta cada sección (columna) con un color pastel.
    """
    def __init__(self, colors, orientation=Qt.Horizontal, parent=None):
        super().__init__(orientation, parent)
        self.colors = colors
        # Altura un poco mayor para que respire
        self.setFixedHeight(28)
        # Texto centrado por defecto
        self.setDefaultAlignment(Qt.AlignCenter)

    def paintSection(self, painter, rect, logicalIndex):
        if not rect.isValid():
            return super().paintSection(painter, rect, logicalIndex)

        # Color pastel para esta columna
        color = self.colors[logicalIndex % len(self.colors)]

        painter.save()
        # Fondo pastel
        painter.fillRect(rect, QColor(color))

        # Borde inferior sutil
        pen = QPen(QColor("#e5e7eb"))
        painter.setPen(pen)
        painter.drawLine(rect.bottomLeft(), rect.bottomRight())

        # Texto del header (lo trae el modelo)
        text = self.model().headerData(logicalIndex, self.orientation(), Qt.DisplayRole)
        painter.setPen(QColor("#222222"))  # color de texto oscuro
        painter.drawText(rect, Qt.AlignCenter, str(text) if text is not None else "")

        painter.restore()

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

# ---------------------------
# Ventana principal
# ---------------------------
class CatalogoEditor(QWidget):
    def __init__(self, csv_path="catalogo_inicial.csv", lupa_icon="lupa.png"):
        super().__init__()
        self.csv_path = csv_path
        self.lupa_icon = lupa_icon

        self.setWindowTitle("Editor de Catálogo Electroacústico")
        self.resize(1350, 600)

        self.layout = QVBoxLayout(self)

        # Tabla
        self.table = QTableWidget()
        self.layout.addWidget(self.table)

        # Botones principales
        self.add_button = QPushButton("Agregar nueva obra")
        self.add_button.clicked.connect(self.agregar_fila)
        self.layout.addWidget(self.add_button)

        self.delete_button = QPushButton("Eliminar obra seleccionada")
        self.delete_button.clicked.connect(self.eliminar_fila)
        self.layout.addWidget(self.delete_button)

        # Buscador
        self.search_layout = QHBoxLayout()
        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText("Buscar por compositor, obra, año...")
        self.search_input.returnPressed.connect(self.buscar)  # Enter dispara buscar
        self.search_layout.addWidget(self.search_input)

        self.search_button = QPushButton()
        self.search_button.setIcon(QIcon(self.lupa_icon))  # ícono local si existe
        self.search_button.setIconSize(QSize(16, 16))
        self.search_button.setFixedWidth(32)
        self.search_button.clicked.connect(self.buscar)
        self.search_layout.addWidget(self.search_button)

        self.reset_button = QPushButton("✖")
        self.reset_button.setToolTip("Restablecer búsqueda")
        self.reset_button.setFixedWidth(28)
        self.reset_button.clicked.connect(self.restablecer_busqueda)
        self.search_layout.addWidget(self.reset_button)

        self.layout.addLayout(self.search_layout)

        self.save_button = QPushButton("Guardar cambios")
        self.save_button.clicked.connect(self.guardar_cambios)
        self.layout.addWidget(self.save_button)

        # Carga inicial
        self.df = cargar_catalogo(self.csv_path)
        self.mostrar_tabla(self.df)

    # ---------------------------
    # Render de tabla
    # ---------------------------
    def mostrar_tabla(self, df):
        """Muestra el DataFrame en la tabla, ocultando compositores repetidos."""
        self.table.setRowCount(len(df))
        self.table.setColumnCount(len(df.columns))
        self.table.setHorizontalHeaderLabels(df.columns)

        # Colorear encabezados después de definir los labels
        # Paleta pastel
        colores_pastel = [
            "#F9E2E7", "#E1F0FF", "#E6F5D6", "#FFF4C2", "#E8D5F7",
            "#D1F2EB", "#FDE2E2", "#DBEAFE", "#FEF9C3", "#E0F7FA",
            "#F3E8FF", "#E8F5E9", "#FFF9E6", "#EDE7F6", "#E0F2F1"
        ]

        # Sustituye el header horizontal por uno coloreado
        header = ColoredHeader(colores_pastel, Qt.Horizontal, self.table)
        self.table.setHorizontalHeader(header)

        # (Opcional) Estilo fino para el header (bordes, padding)
        self.table.horizontalHeader().setStyleSheet("""
            QHeaderView::section {
                border: 0px;
                padding: 6px;
            }
        """)


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
    # ---------------------------
    # Acciones
    # ---------------------------
    def agregar_fila(self):
        dialogo = DialogoAgregarObra(self.df.columns, self)
        if dialogo.exec_() == dialogo.Accepted:
            datos = dialogo.obtener_datos()

            # En la tabla (al final)
            fila_nueva = self.table.rowCount()
            self.table.insertRow(fila_nueva)
            for col, valor in enumerate(datos):
                self.table.setItem(fila_nueva, col, QTableWidgetItem(valor))

            # En el DataFrame
            nueva_fila_df = pd.DataFrame([datos], columns=self.df.columns)
            self.df = pd.concat([self.df, nueva_fila_df], ignore_index=True)

    def eliminar_fila(self):
        fila = self.table.currentRow()
        if fila < 0:
            QMessageBox.warning(self, "Sin selección", "Selecciona una fila para eliminar.")
            return
        if QMessageBox.question(self, "Confirmar eliminación",
                                "¿Eliminar la obra seleccionada?",
                                QMessageBox.Yes | QMessageBox.No) == QMessageBox.Yes:
            # En la tabla
            self.table.removeRow(fila)
            # En el DataFrame
            self.df = self.df.drop(self.df.index[fila]).reset_index(drop=True)

    def guardar_cambios(self):
        """
        Sincroniza la tabla -> DataFrame, normaliza y guarda CSV 'visual':
        - Ordena por Compositor
        - Deja en blanco repetidos (solo visual para CSV)
        """
        # Tabla -> lista de filas
        datos = []
        for i in range(self.table.rowCount()):
            fila = []
            for j in range(self.table.columnCount()):
                item = self.table.item(i, j)
                fila.append(item.text() if item else "")
            datos.append(fila)

        try:
            # Construir DataFrame final desde la tabla
            columnas = [self.table.horizontalHeaderItem(i).text() for i in range(self.table.columnCount())]
            df_actualizado = pd.DataFrame(datos, columns=columnas)

            # Normalización y unificación
            if "Compositor" in df_actualizado.columns:
                df_actualizado["Compositor"] = df_actualizado["Compositor"].replace("", pd.NA).ffill()
                df_actualizado["Compositor"] = df_actualizado["Compositor"].apply(normalizar_compositor)
                df_actualizado = unificar_compositores(df_actualizado)

            # Preparar versión visual para CSV y guardar
            df_visual = preparar_para_guardar(df_actualizado)
            df_visual.to_csv(self.csv_path, index=False, encoding="utf-8-sig")

            QMessageBox.information(self, "Éxito", "Archivo guardado correctamente.")
            self.df = df_actualizado  # estado interno actualizado

        except Exception as e:
            QMessageBox.critical(self, "Error", f"No se pudo guardar el archivo:\n{str(e)}")

    # ---------------------------
    # Búsqueda
    # ---------------------------

    def _normalize(self, s: str) -> str:
        """Minúsculas + sin tildes/diacríticos."""
        if not s:
            return ""
        s = str(s).lower().strip()
        # Eliminar tildes usando NFD
        s = unicodedata.normalize("NFD", s)
        s = "".join(ch for ch in s if unicodedata.category(ch) != "Mn")
        # Colapsar espacios
        s = " ".join(s.split())
            
        return s

    def _sin_parentesis(self, s: str) -> str:
        """Quita todo lo que esté entre paréntesis (p.ej. fechas)."""
        if not s:
            return ""
        return re.sub(r"\([^)]*\)", "", s).strip()


    def buscar(self):
        """
        Filtra filas de forma insensible a tildes y al orden nombre/apellido.
        Para 'Compositor', usa el valor REAL de self.df (puede estar oculto en la vista),
        y genera variantes sin paréntesis para que 'Alejandro Albornoz' matchee
        aunque el dato sea 'Albornoz, Alejandro (1970–)'.
        """
        query = self._normalize(self.search_input.text())
        if not query:
            self.restablecer_busqueda()
            return

        # Mapa de headers (por si cambiaste el orden de columnas)
        headers = [self.table.horizontalHeaderItem(i).text() for i in range(self.table.columnCount())]
        try:
            col_compositor = headers.index("Compositor")
        except ValueError:
            col_compositor = -1

        for fila in range(self.table.rowCount()):
            visible = False

            # 1) Búsqueda general: cualquier columna (lo que se ve en la tabla)
            fila_texto_norm = []
            for col in range(self.table.columnCount()):
                item = self.table.item(fila, col)
                texto_celda = item.text() if item else ""
                norm = self._normalize(texto_celda)
                fila_texto_norm.append(norm)
                if query in norm:
                    visible = True
                    break

            # 2) Tratamiento especial para 'Compositor' usando el valor real del DF
            if not visible and col_compositor != -1:
                try:
                    comp_full = str(self.df.at[fila, "Compositor"])
                except Exception:
                    comp_full = self.table.item(fila, col_compositor).text() if self.table.item(fila, col_compositor) else ""

                comp_full = comp_full.strip()

                # versión sin paréntesis (p.ej. quitar fechas)
                comp_sin_paren = self._sin_parentesis(comp_full)

                variantes = set()

                # Base: tal cual y sin paréntesis
                variantes.add(self._normalize(comp_full))
                variantes.add(self._normalize(comp_sin_paren))

                # Sin coma (y colapsando espacios)
                sin_coma_full = " ".join(comp_full.replace(",", " ").split())
                sin_coma_sin_paren = " ".join(comp_sin_paren.replace(",", " ").split())
                variantes.add(self._normalize(sin_coma_full))
                variantes.add(self._normalize(sin_coma_sin_paren))

                # Si viene como "Apellido, Nombre (...)"
                fuente = comp_sin_paren if comp_sin_paren else comp_full
                if "," in fuente:
                    ap, nom = [p.strip() for p in fuente.split(",", 1)]
                    # "Nombre Apellido" y "Apellido Nombre"
                    variantes.add(self._normalize(f"{nom} {ap}"))
                    variantes.add(self._normalize(f"{ap} {nom}"))
                    # También sus versiones sin espacios extra
                    variantes.add(self._normalize(f"{nom}{ap}"))
                    variantes.add(self._normalize(f"{ap}{nom}"))
                    # Solo nombre / solo apellido
                    variantes.add(self._normalize(nom))
                    variantes.add(self._normalize(ap))
                else:
                    # Si no hay coma, intenta partir por espacios y permutar
                    trozos = fuente.split()
                    if len(trozos) >= 2:
                        ap = trozos[-1]
                        nom = " ".join(trozos[:-1])
                        variantes.add(self._normalize(f"{nom} {ap}"))
                        variantes.add(self._normalize(f"{ap} {nom}"))

                if any(query in v for v in variantes):
                    visible = True

            self.table.setRowHidden(fila, not visible)

    def restablecer_busqueda(self):
        for fila in range(self.table.rowCount()):
            self.table.setRowHidden(fila, False)
        self.search_input.clear()
