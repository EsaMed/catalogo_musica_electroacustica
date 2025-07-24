# Catálogo de Música Electroacústica en Chile

Este proyecto es una herramienta interactiva para visualizar, editar y actualizar un catálogo de obras de música electroacústica producidas en Chile. 
La aplicación permite agregar, eliminar y guardar obras directamente desde una interfaz gráfica.

## Características principales

- Visualización de un catálogo en formato de tabla editable.
- Añadir nuevas obras mediante un formulario emergente.
- Eliminar entradas seleccionadas.
- Búsqueda por compositor, título de obra, año, etc.
- Guarda los cambios en un archivo CSV.
- Normalización automática de nombres de compositores.


## Ejecución

### 1. Requisitos

- Python 3.12.3
- PyQt5
- pandas

Instalación:

pip install PyQt5 pandas

### 2. Ejecutar

python interf.py


## Funcionalidad del buscador

El campo de búsqueda permite filtrar rápidamente entradas por cualquiera de los campos (compositor, obra, año, etc.). Se puede activar presionando `Enter` o haciendo clic en el ícono de buscar.

El botón ✖ permite restablecer el catálogo completo tras una búsqueda.


## Próximas mejoras

- Mejoras gráficas en interfaz
- Versión Standalone (.exe)
- Versión web sincronizada con la base de datos remota.
- Control de versiones de cambios en el catálogo.
- Cambio a estructura modular


## Autor

Esaú Medina Lucero  
https://github.com/EsaMed

---

Este trabajo es parte del proyecto Fondecyt de Iniciación 11241059

"Establishing foundations for the implementation of neutral level analysis of the spatial composition of acousmatic works"

<img width="1352" height="642" alt="imagen" src="https://github.com/user-attachments/assets/48f0834f-db3e-438d-ae56-b8241c5f8e8c" />
