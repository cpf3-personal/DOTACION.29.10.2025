import streamlit as st
import polars as pl
import gspread
import os
import json
import sys
from dotenv import load_dotenv

# --- CONFIGURACIÓN DE IMPORTACIÓN ---
# Agregar el directorio padre al path para importar form_config
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

try:
    from form_config import GOOGLE_SHEET_ID
except ImportError:
    st.error("No se pudo encontrar 'form_config.py' en el directorio padre.")
    st.stop()

# --- CONFIGURACIÓN DE LA PÁGINA ---
st.set_page_config(
    page_title="Mesa de Entrada - Carga Masiva",
    page_icon="📥",
    layout="wide"  # Cambiado a 'wide' para mejor visualización de tablas grandes
)

# Cargar variables de entorno
load_dotenv()

# --- CONSTANTES ---
SCOPES = ["https://www.googleapis.com/auth/spreadsheets", "https://www.googleapis.com/auth/drive.file"]
SHEET_NAME = "MESA_ENTRADA"

# --- TÍTULO Y DESCRIPCIÓN ---
st.title("📥 Mesa de Entrada - Carga Masiva")
st.markdown(f"""
Subida de archivos Excel directamente a la hoja **'{SHEET_NAME}'** del sistema y visualización de registros.
""")

# --- FUNCIONES DE AUTENTICACIÓN ---
@st.cache_resource
def get_gspread_client():
    creds_data = None
    try:
        if "GCP_SA_CREDENTIALS" in st.secrets:
            creds_data = st.secrets["GCP_SA_CREDENTIALS"]
    except Exception:
        pass

    if not creds_data:
        creds_data = os.environ.get("GCP_SA_CREDENTIALS")
    
    if not creds_data:
        st.error("Error: No se encontró 'GCP_SA_CREDENTIALS'. Verifica tus secretos o archivo .env")
        st.stop()
        return None
    
    creds_dict = creds_data if isinstance(creds_data, dict) else None
    if creds_dict is None:
        try:
            creds_dict = json.loads(creds_data.strip())
        except json.JSONDecodeError:
            st.error("Error: 'GCP_SA_CREDENTIALS' no es un JSON válido.")
            st.stop()
            return None
    
    try:
        return gspread.service_account_from_dict(creds_dict, scopes=SCOPES)
    except Exception as e:
        st.error(f"Error de autenticación: {e}")
        st.stop()
        return None

def procesar_archivos(uploaded_files):
    """Lee los archivos subidos en memoria usando Polars."""
    lista_dfs = []
    log_errores = []

    progress_bar = st.progress(0)
    
    for i, uploaded_file in enumerate(uploaded_files):
        try:
            # Polars puede leer directamente el objeto bytes que entrega Streamlit
            # Usamos engine="xlsx2csv" explícitamente y read_options para manejar tipos
            df = pl.read_excel(
                uploaded_file, 
                engine="xlsx2csv",
                read_options={"infer_schema_length": 0}
            )
            
            # Convertir todo a String para máxima compatibilidad con Sheets
            df = df.select(pl.all().cast(pl.String))
            
            lista_dfs.append(df)
        except Exception as e:
            log_errores.append(f"Error en {uploaded_file.name}: {e}")
        
        # Actualizar barra de progreso
        progress_bar.progress((i + 1) / len(uploaded_files))

    return lista_dfs, log_errores

# --- INTERFAZ PRINCIPAL ---

# Subida de Archivos
uploaded_files = st.file_uploader("📂 Arrastra tus archivos Excel aquí", type=["xlsx", "xls"], accept_multiple_files=True)

# Botón de Acción
if st.button("🚀 Procesar y Subir a 'MESA_ENTRADA'", type="primary"):
    
    if not uploaded_files:
        st.warning("⚠️ Por favor, selecciona al menos un archivo Excel.")
    else:
        # INICIO DEL PROCESO
        gc = get_gspread_client()
        if not gc:
            st.stop()

        # A. Procesamiento Local
        with st.spinner('Leyendo archivos con Polars...'):
            lista_dfs, errores = procesar_archivos(uploaded_files)

        if errores:
            for err in errores:
                st.error(err)
        
        if lista_dfs:
            try:
                # Unir DataFrames
                df_final = pl.concat(lista_dfs, how="vertical")
                filas_nuevas = df_final.height
                
                # --- PREPARACIÓN DE GOOGLE SHEETS ---
                sh = gc.open_by_key(GOOGLE_SHEET_ID)
                
                try:
                    worksheet = sh.worksheet(SHEET_NAME)
                except gspread.WorksheetNotFound:
                    st.error(f"❌ No se encontró la hoja '{SHEET_NAME}'. Por favor créala en el Google Sheet.")
                    st.stop()

                st.info(f"✅ Se han procesado {filas_nuevas} filas correctamente. Subiendo a '{SHEET_NAME}'...")

                # Lógica Append - Siempre al final
                # Limpieza de Nulos
                df_final = df_final.fill_null("")
                
                # Preparar lista de listas
                datos = df_final.rows()
                datos_lista = [list(fila) for fila in datos]

                # Usamos append_rows para agregar al final
                with st.spinner("Subiendo datos a la nube..."):
                    worksheet.append_rows(datos_lista, value_input_option='USER_ENTERED')
                    
                st.success(f"✨ ¡Éxito! Se agregaron {filas_nuevas} filas a la hoja '{SHEET_NAME}'.")
                st.balloons() 

            except Exception as e:
                st.error(f"Ocurrió un error en la subida: {e}")

st.divider()

# --- SECCIÓN DE VISUALIZACIÓN ---
st.header("📋 Visualizar Registros Existentes")
st.markdown("Consulta los datos actuales de la hoja (**Columnas A hasta N**).")

if st.button("👁️ Cargar y Ver Datos de MESA_ENTRADA"):
    gc = get_gspread_client()
    if gc:
        try:
            with st.spinner("Descargando datos de Google Sheets..."):
                sh = gc.open_by_key(GOOGLE_SHEET_ID)
                try:
                    worksheet = sh.worksheet(SHEET_NAME)
                except gspread.WorksheetNotFound:
                    st.error(f"❌ No se encontró la hoja '{SHEET_NAME}'.")
                    st.stop()
                
                rows = worksheet.get_all_values()
            
            if rows and len(rows) > 1:
                df_sheet = pl.DataFrame(rows[1:], schema=rows[0], orient="row")
                
                # Seleccionar columnas A hasta N
                num_cols = min(14, len(df_sheet.columns))
                cols_to_select = df_sheet.columns[:num_cols]
                
                # Guardar en session_state para persistencia
                st.session_state["mesa_view_df"] = df_sheet.select(cols_to_select)
                
            else:
                st.info("La hoja está vacía o solo tiene encabezados.")
                
        except Exception as e:
            st.error(f"Error al cargar datos: {e}")

# Renderizar si existen datos en memoria (persiste tras interacción)
if "mesa_view_df" in st.session_state:
    df_view = st.session_state["mesa_view_df"]
    
    # --- FILTROS DE BÚSQUEDA ---
    st.markdown("### 🔎 Buscar en Registros")
    col_filtro1, col_filtro2 = st.columns([0.3, 0.7])
    
    with col_filtro1:
        # Aseguramos que la key sea única para no chocar con otros widgets
        columna_busqueda = st.selectbox("Buscar en columna:", df_view.columns, key="search_col_mesa_view")
    with col_filtro2:
        valor_busqueda = st.text_input("Escribe el dato a buscar:", key="search_val_mesa_view")

    if valor_busqueda:
        df_view_filtered = df_view.filter(
            pl.col(columna_busqueda).fill_null("").str.to_lowercase().str.contains(valor_busqueda.lower(), literal=True)
        )
        st.success(f"✅ Se encontraron {df_view_filtered.height} registros coincidentes.")
        st.dataframe(df_view_filtered, width='stretch', hide_index=True)
    else:
        st.info(f"Mostrando el total de {df_view.height} registros.")
        st.dataframe(df_view, width='stretch', hide_index=True)
