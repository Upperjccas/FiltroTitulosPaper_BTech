import streamlit as st
from PIL import Image
import pandas as pd
import rispy
import io
import re

# Diccionario para almacenar archivos por etiqueta
etiquetas_archivos = {}

# Función para limpiar títulos
def limpiar_titulo(titulo):
    titulo = str(titulo).strip().lower()
    titulo = re.sub(r'\s+', ' ', titulo)
    titulo = re.sub(r'[^\w\s]', '', titulo)
    return titulo

st.set_page_config(page_title="FiltroPapers - B-Tech", layout="wide")

# Logo y título
try:
    img = Image.open("logo.png")
    st.image(img, width=80)
except Exception as e:
    st.write(f"No se pudo cargar el logo: {e}")

st.title("Filtrado de papers por Título - B-Tech")

# Instrucciones
st.write("""
Esta herramienta te permite filtrar y procesar los resultados de búsqueda de bases de datos, eliminando artículos repetidos y permitiendo asignar etiquetas.
""")

# Agregar nueva etiqueta
nombre_etiqueta = st.text_input("Nombre de nueva etiqueta")
archivos_subidos = st.file_uploader(
    "Sube archivos (.ris o .csv) para esta etiqueta",
    type=["ris", "csv"],
    accept_multiple_files=True
)

if st.button("Agregar etiqueta y archivos"):
    if nombre_etiqueta and archivos_subidos:
        etiquetas_archivos[nombre_etiqueta] = archivos_subidos
        st.success(f"Etiqueta '{nombre_etiqueta}' agregada con {len(archivos_subidos)} archivos.")
    else:
        st.warning("Debes ingresar un nombre y subir al menos un archivo.")

# Mostrar etiquetas actuales
if etiquetas_archivos:
    st.subheader("Etiquetas actuales")
    for etq, files in etiquetas_archivos.items():
        st.write(f"**{etq}**: {len(files)} archivos")

# Procesar y generar Excel
if st.button("Procesar y generar Excel"):
    if not etiquetas_archivos:
        st.warning("No hay etiquetas para procesar.")
    else:
        articulos = []
        resumen_etiquetas = {}
        total_original = 0

        for etiqueta, archivos in etiquetas_archivos.items():
            encontrados = 0
            for archivo in archivos:
                if archivo.name.endswith(".ris"):
                    try:
                        entries = rispy.load(io.TextIOWrapper(archivo, encoding='utf-8'))
                        for entry in entries:
                            encontrados += 1
                            articulos.append({
                                'Titulo': entry.get('title', '').strip(),
                                'DOI': entry.get('doi', '').strip(),
                                'Fecha': entry.get('year', ''),
                                'Autores': '; '.join(entry.get('author', [])),
                                'Etiqueta': etiqueta,
                                'Titulo_limpio': limpiar_titulo(entry.get('title', ''))
                            })
                    except Exception as e:
                        st.error(f"Error leyendo {archivo.name}: {e}")

                elif archivo.name.endswith(".csv"):
                    try:
                        df = pd.read_csv(archivo)
                        titulo_col = next((col for col in df.columns if 'title' in col.lower()), None)
                        doi_col = next((col for col in df.columns if 'doi' in col.lower()), None)
                        fecha_col = next((col for col in df.columns if 'year' in col.lower() or 'date' in col.lower()), None)
                        autor_col = next((col for col in df.columns if 'author' in col.lower()), None)

                        for _, row in df.iterrows():
                            encontrados += 1
                            titulo = str(row.get(titulo_col, '')).strip()
                            articulos.append({
                                'Titulo': titulo,
                                'DOI': str(row.get(doi_col, '')).strip() if doi_col else '',
                                'Fecha': row.get(fecha_col, '') if fecha_col else '',
                                'Autores': str(row.get(autor_col, '')).strip() if autor_col else '',
                                'Etiqueta': etiqueta,
                                'Titulo_limpio': limpiar_titulo(titulo)
                            })
                    except Exception as e:
                        st.error(f"Error leyendo {archivo.name}: {e}")

            resumen_etiquetas[etiqueta] = encontrados
            total_original += encontrados

        # Quitar duplicados
        df = pd.DataFrame(articulos)
        num_antes = len(df)
        df_unique = df.drop_duplicates(subset='Titulo_limpio', keep='first').reset_index(drop=True)
        num_despues = len(df_unique)
        num_duplicados = num_antes - num_despues
        df_unique.insert(0, '#', range(1, len(df_unique) + 1))
        df_unique = df_unique.drop(columns=['Titulo_limpio'])

        # Resumen
        resumen_filas = [
            f"Número de etiquetas: {len(etiquetas_archivos)}",
            *[f"'{etq}': {cantidad} artículos" for etq, cantidad in resumen_etiquetas.items()],
            f"Total de artículos antes de filtrar: {total_original}",
            f"Artículos duplicados eliminados: {num_duplicados}",
            f"Total de artículos únicos: {num_despues}"
        ]

        reporte = pd.DataFrame({'Resumen': resumen_filas})

        # Guardar en memoria y ofrecer descarga
        output = io.BytesIO()
        with pd.ExcelWriter(output, engine="xlsxwriter") as writer:
            reporte.to_excel(writer, index=False, header=False, startrow=0)
            df_unique.to_excel(writer, index=False, startrow=len(resumen_filas) + 2)
        output.seek(0)

        st.download_button(
            label="Descargar Excel",
            data=output,
            file_name="reporte_filtrado.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        )
