import streamlit as st
import pandas as pd
import rispy
import re
from io import BytesIO

# Diccionario para almacenar archivos por etiqueta
etiquetas_archivos = {}

# Función para limpiar títulos
def limpiar_titulo(titulo):
    titulo = str(titulo).strip().lower()
    titulo = re.sub(r'\s+', ' ', titulo)
    titulo = re.sub(r'[^\w\s]', '', titulo)
    return titulo

st.title("Filtrado de papers por Titulo - B-Tech")

st.markdown("""
Esta herramienta permite filtrar y procesar resultados de búsqueda de diferentes bases de datos,
eliminando artículos repetidos y asignando etiquetas a los resultados.
""")

# Formulario para agregar etiqueta y archivos
with st.form("agregar_etiqueta"):
    nombre_etiqueta = st.text_input("Nombre del tema o etiqueta")
    archivos = st.file_uploader(
        "Selecciona archivos (.ris o .csv)",
        type=["ris", "csv"],
        accept_multiple_files=True
    )
    submitted = st.form_submit_button("Agregar")
    if submitted and nombre_etiqueta and archivos:
        etiquetas_archivos[nombre_etiqueta] = archivos
        st.success(f"Etiqueta '{nombre_etiqueta}' agregada con {len(archivos)} archivos.")

# Mostrar etiquetas actuales
if etiquetas_archivos:
    st.subheader("Etiquetas actuales")
    for etq, archivos in etiquetas_archivos.items():
        st.write(f"**{etq}** ({len(archivos)} archivos)")

# Procesar y generar Excel
if st.button("Procesar y generar Excel"):
    if not etiquetas_archivos:
        st.warning("Primero debes agregar al menos una etiqueta.")
    else:
        articulos = []
        resumen_etiquetas = {}
        total_original = 0

        for etiqueta, archivos in etiquetas_archivos.items():
            encontrados = 0
            for archivo in archivos:
                if archivo.name.endswith(".ris"):
                    try:
                        entries = rispy.load(fileobj=archivo)
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

        df = pd.DataFrame(articulos)
        num_antes = len(df)
        df_unique = df.drop_duplicates(subset='Titulo_limpio', keep='first').reset_index(drop=True)
        num_despues = len(df_unique)
        num_duplicados = num_antes - num_despues
        df_unique.insert(0, '#', range(1, len(df_unique) + 1))
        df_unique = df_unique.drop(columns=['Titulo_limpio'])

        resumen_filas = [
            f"Número de etiquetas: {len(etiquetas_archivos)}",
            *[f"'{etq}': {cantidad} artículos" for etq, cantidad in resumen_etiquetas.items()],
            f"Total de artículos antes de filtrar: {total_original}",
            f"Artículos duplicados eliminados: {num_duplicados}",
            f"Total de artículos únicos: {num_despues}"
        ]

        reporte = pd.DataFrame({'Resumen': resumen_filas})

        # Guardar en memoria para descarga
        output = BytesIO()
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

        st.success("Reporte generado con éxito.")
