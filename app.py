# app.py
import sys
from PyQt5.QtWidgets import QApplication
from editor import CatalogoEditor

if __name__ == "__main__":
    app = QApplication(sys.argv)
    # Puedes cambiar el nombre/ruta del CSV o del ícono aquí si hace falta
    ventana = CatalogoEditor(csv_path="catalogo_inicial.csv", lupa_icon="lupa.png")
    ventana.show()
    sys.exit(app.exec_())
