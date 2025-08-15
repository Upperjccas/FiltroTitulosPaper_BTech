# app.py
# Requisitos: streamlit, pandas, rispy, xlsxwriter
import streamlit as st
import pandas as pd
import rispy
import re
from io import BytesIO
import io

# ---------- Inicializar estado ----------
if "etiquetas_archivos" not in st.session_state:
    # estructura: { etiqueta: [ { "name": filename, "data": bytes }, ... ] }
    st.session_state.etiquetas_archivos = {}

# ---------- Funciones ----------
def limpiar_titulo(titulo):
    titulo = str(titulo).strip().lower()
    titulo = re.sub(r'\s+', ' ', titulo)
    titulo = re.sub(r'[^\w\s]', '', titulo)
    return titulo

def agregar_etiqueta_con_archivos(nombre_etiqueta, archivos_subidos):
    if not nombre_etiqueta:
        st.warning("Ingrese un nombre de etiqueta.")
        return
    if not archivos_subidos:
        st.warning("Seleccione al menos un archivo para cargar.")
        return
    lista = []
    for f in archivos_subidos:
        try:
            b = f.read()
            lista.append({"name": f.name, "data": b})
        except Exception as e:
            st.error(f"Error leyendo {f.name}: {e}")
    if nombre_etiqueta in st.session_state.etiquetas_archivos:
        st.session_state.etiquetas_archivos[nombre_etiqueta].extend(lista)
    else:
        st.session_state.etiquetas_archivos[nombre_etiqueta] = lista
    st.success(f"Etiqueta '{nombre_etiqueta}' agregada/actualizada con {len(lista)} archivo(s).")

def agregar_archivos_a_etiqueta_existente(nombre_etiqueta, archivos_subidos):
    if not nombre_etiqueta:
        st.warning("Seleccione una etiqueta.")
        return
    if not archivos_subidos:
        st.warning("Seleccione al menos un archivo para agregar.")
        return
    lista = []
    for f in archivos_subidos:
        try:
            b = f.read()
            lista.append({"name": f.name, "data": b})
        except Exception as e:
            st.error(f"Error leyendo {f.name}: {e}")
    st.session_state.etiquetas_archivos.setdefault(nombre_etiqueta, []).extend(lista)
    st.success(f"Se agregaron {len(lista)} archivo(s) a '{nombre_etiqueta}'.")

def eliminar_etiqueta(nombre_etiqueta):
    if nombre_etiqueta in st.session_state.etiquetas_archivos:
        st.session_state.etiquetas_archivos.pop(nombre_etiqueta)
        st.success(f"Etiqueta '{nombre_etiqueta}' eliminada.")
    else:
        st.warning("Etiqueta no encontrada.")

def procesar_y_generar_excel():
    if not st.session_state.etiquetas_archivos:
        st.warning("Primero debes agregar al menos una etiqueta con archivos.")
        return

    articulos = []
    resumen_etiquetas = {}
    total_original = 0

    for etiqueta, archivos in st.session_state.etiquetas_archivos.items():
        encontrados = 0
        for archivo in archivos:
            name = archivo.get("name", "")
            data = archivo.get("data", b"")
            lower = name.lower()
            if lower.endswith(".ris"):
                try:
                    text = data.decode("utf-8", errors="ignore")
                    entries = rispy.loads(text)
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
                    st.error(f"Error leyendo RIS '{name}': {e}")
            elif lower.endswith(".csv"):
                try:
                    df = pd.read_csv(io.BytesIO(data))
                    titulo_col = next((col for col in df.columns if 'title' in col.lower()), None)
                    doi_col = next((col for col in df.columns if 'doi' in col.lower()), None)
                    fecha_col = next((col for col in df.columns if 'year' in col.lower() or 'date' in col.lower()), None)
                    autor_col = next((col for col in df.columns if 'author' in col.lower()), None)
                    for _, row in df.iterrows():
                        encontrados += 1
                        titulo = str(row.get(titulo_col, '')).strip() if titulo_col else str(row.iloc[0]) if len(row)>0 else ''
                        articulos.append({
                            'Titulo': titulo,
                            'DOI': str(row.get(doi_col, '')).strip() if doi_col else '',
                            'Fecha': row.get(fecha_col, '') if fecha_col else '',
                            'Autores': str(row.get(autor_col, '')).strip() if autor_col else '',
                            'Etiqueta': etiqueta,
                            'Titulo_limpio': limpiar_titulo(titulo)
                        })
                except Exception as e:
                    st.error(f"Error leyendo CSV '{name}': {e}")
            else:
                # Ignorar otros formatos
                st.warning(f"Ignorado (formato no soportado): {name}")
        resumen_etiquetas[etiqueta] = encontrados
        total_original += encontrados

    df = pd.DataFrame(articulos)
    num_antes = len(df)
    if num_antes == 0:
        st.info("No se encontraron artículos en los archivos cargados.")
        return
    df_unique = df.drop_duplicates(subset='Titulo_limpio', keep='first').reset_index(drop=True)
    num_despues = len(df_unique)
    num_duplicados = num_antes - num_despues
    df_unique.insert(0, '#', range(1, len(df_unique) + 1))
    df_unique = df_unique.drop(columns=['Titulo_limpio'])

    resumen_filas = [
        f"Número de etiquetas: {len(st.session_state.etiquetas_archivos)}",
        *[f"'{etq}': {cantidad} artículos" for etq, cantidad in resumen_etiquetas.items()],
        f"Total de artículos antes de filtrar: {total_original}",
        f"Artículos duplicados eliminados: {num_duplicados}",
        f"Total de artículos únicos: {num_despues}"
    ]
    reporte = pd.DataFrame({'Resumen': resumen_filas})

    # Generar Excel en memoria
    output = BytesIO()
    with pd.ExcelWriter(output, engine="xlsxwriter") as writer:
        reporte.to_excel(writer, index=False, header=False, startrow=0)
        df_unique.to_excel(writer, index=False, startrow=len(resumen_filas) + 2)
    output.seek(0)

    st.download_button(
        label="Descargar Excel",
        data=output.getvalue(),
        file_name="reporte_filtrado.xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    )
    # Mostrar resumen y tabla
    st.subheader("Resumen")
    for row in resumen_filas:
        st.write(row)
    st.subheader("Primeros 50 artículos únicos")
    st.dataframe(df_unique.head(50))

# ---------- Interfaz ----------
st.title("Filtrado de papers por Titulo - B-Tech")
st.markdown(
    "Herramienta para filtrar resultados (RIS/CSV), eliminar duplicados por título y exportar un Excel con etiquetas."
)

left, right = st.columns([2, 1])

with left:
    st.header("Instrucciones")
    st.markdown(
        "- Agrega etiquetas y carga archivos `.ris` o `.csv` asociándolos a una etiqueta.\n"
        "- Puedes agregar más archivos a una etiqueta existente.\n"
        "- El botón 'Procesar y generar Excel' creará y permitirá descargar el reporte.\n"
        "- Recomendado: preferir `.ris` cuando sea posible."
    )
    st.markdown("### Agregar nueva etiqueta con archivos")
    with st.form("form_nueva_etiqueta"):
        nombre = st.text_input("Nombre de la etiqueta")
        archivos = st.file_uploader("Selecciona archivos (.ris, .csv)", type=["ris", "csv"], accept_multiple_files=True)
        enviar = st.form_submit_button("Agregar etiqueta")
        if enviar:
            agregar_etiqueta_con_archivos(nombre, archivos)

    st.markdown("### Agregar archivos a etiqueta existente")
    if st.session_state.etiquetas_archivos:
        with st.form("form_agregar_a_existente"):
            etiqueta_sel = st.selectbox("Selecciona etiqueta", list(st.session_state.etiquetas_archivos.keys()))
            archivos2 = st.file_uploader("Archivos a agregar (.ris, .csv)", type=["ris", "csv"], accept_multiple_files=True, key="uploader2")
            enviar2 = st.form_submit_button("Agregar a etiqueta")
            if enviar2:
                agregar_archivos_a_etiqueta_existente(etiqueta_sel, archivos2)
    else:
        st.info("No hay etiquetas aún. Crea una nueva etiqueta arriba.")

    st.markdown("### Etiquetas actuales y gestión")
    if st.session_state.etiquetas_archivos:
        for etq, archivos in st.session_state.etiquetas_archivos.items():
            with st.expander(f"{etq} ({len(archivos)} archivos)"):
                nombres = [a["name"] for a in archivos]
                st.write("Archivos:")
                for n in nombres:
                    st.write(f"- {n}")
                btn_col1, btn_col2 = st.columns([1, 1])
                if btn_col1.button(f"Eliminar etiqueta '{etq}'", key=f"del_{etq}"):
                    eliminar_etiqueta(etq)
                # Nota: para simplificar no implementamos eliminar archivos individuales aquí (se puede añadir si se desea)

    st.markdown("---")
    if st.button("Procesar y generar Excel"):
        procesar_y_generar_excel()

with right:
    st.header("Acciones rápidas")
    if st.button("Limpiar todo (etiquetas y archivos)"):
        st.session_state.etiquetas_archivos = {}
        st.success("Estado limpiado.")
    st.markdown("**Créditos**\nDesarrollado por: Juan Carlos Cañon - Semillero B-Tech")

# Fin de app.py
