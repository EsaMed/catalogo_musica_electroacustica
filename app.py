# app.py
import sys
from PyQt5.QtWidgets import QApplication
from editor import CatalogoEditor
from storage import DriveStorage

FILE_ID = "1yu0nemxng0i4Qc_rlTnx7AackuJbebJX"  # <-- tu fileId de Drive

if __name__ == "__main__":
    app = QApplication(sys.argv)
    storage = DriveStorage(file_id=FILE_ID, credentials_path="credentials.json", token_path="token.json")
    ventana = CatalogoEditor(storage=storage, lupa_icon="lupa.png")
    ventana.show()
    sys.exit(app.exec_())
