import streamlit as st
import polars as pl
import gspread
import json # Para las credenciales de SA
import os # Para las variables de entorno
from dotenv import load_dotenv # Para cargar el .env local

# Cargar variables de entorno locales (del archivo .env)
load_dotenv()

# --- CONFIGURACIÓN ---
# st.set_page_config(layout="wide") # Streamlit maneja esto automáticamente en multi-page

# --- CAMBIO IMPORTANTE: Usar el ID de la Hoja ---
# Extraído de tu URL: https://docs.google.com/spreadsheets/d/1UOA2HhylbW2w5S5EyfAJ-OP0zzlcx7cbYVk1QJedit/...
GOOGLE_SHEET_ID = "1UOA2HHY1b2W56Ei4YG32sYVJ-0P0zzJcx1C7bBYVK1Q"
# --- FIN DEL CAMBIO ---

# --- ÁMBITOS (SCOPES) REQUERIDOS ---
SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive.file"
]

# --- NUEVA FUNCIÓN DE AUTENTICACIÓN SEGURA (CORREGIDA) ---
def get_gspread_client():
    """
    Autentica un cliente de gspread usando st.secrets (para Streamlit Cloud)
    o una variable de entorno (para local).
    """
    creds_json_str = None
    
    # Envolveremos el acceso a st.secrets en un try-except.
    # Si falla (porque .streamlit/secrets.toml no existe localmente),
    # simplemente pasará al 'else'.
    try:
        # Intenta leer desde Streamlit Secrets (ideal para despliegue)
        if "GCP_SA_CREDENTIALS" in st.secrets:
            creds_json_str = st.secrets["GCP_SA_CREDENTIALS"]
    except Exception:
        # Falla silenciosamente si st.secrets no está disponible (ej. local sin .toml)
        pass 

    # Si st.secrets no funcionó o no encontró la clave, usa el .env local
    if not creds_json_str:
        creds_json_str = os.environ.get("GCP_SA_CREDENTIALS")

    # Si AÚN no hay credenciales, entonces muestra el error
    if not creds_json_str:
        st.error("Error: No se encontró 'GCP_SA_CREDENTIALS'. Revisa tu .env local o los Secrets en Streamlit Cloud.")
        st.stop()
        return None

    try:
        # --- NUEVO: Limpieza de caracteres inválidos (MÁS ROBUSTA) ---
        # 1. Quita espacios/líneas nuevas al inicio/final
        # 2. Reemplaza espacios no separables (comunes al copiar/pegar)
        creds_json_str = creds_json_str.strip().replace('\u00a0', ' ')
        # --- FIN NUEVO ---
        
        # Convertir el string JSON a un diccionario de Python
        creds_dict = json.loads(creds_json_str)
        
        # --- CORRECCIÓN DE AUTENTICACIÓN ---
        # Los scopes se pasan como argumento, no con .with_scopes()
        client = gspread.service_account_from_dict(creds_dict, scopes=SCOPES)
        # --- FIN CORRECCIÓN ---
        
        return client
        
    except json.JSONDecodeError:
        st.error("Error: El contenido de 'GCP_SA_CREDENTIALS' no es un JSON válido.")
        st.stop()
        return None
    except Exception as e:
        st.error(f"Error al autenticar con gspread: {e}")
        st.stop()
        return None

# --- CONEXIÓN GLOBAL (MÁS EFICIENTE) ---
# Se define una sola vez y se cachea
@st.cache_resource
def get_spreadsheet_connection():
    """Crea y cachea la conexión al Google Sheet."""
    try:
        gc = get_gspread_client()
        if not gc:
            return None
        
        # --- CAMBIO IMPORTANTE: Abrir por ID ---
        sh = gc.open_by_key(GOOGLE_SHEET_ID)
        # --- FIN DEL CAMBIO ---
        
        return sh
    except gspread.exceptions.SpreadsheetNotFound:
        st.error(f"Error: No se encontró la hoja de cálculo con el ID: {GOOGLE_SHEET_ID}.")
        return None
    except Exception as e:
        st.error(f"Error al conectar con Google Sheets: {e}")
        return None

# --- FUNCIÓN DE CARGA DE DATOS (MÉTODO 1) ---
@st.cache_data(ttl=600)
def load_pivot_range(_sh, sheet_name, data_range): # <- CAMBIO AQUÍ
    """
    Lee un rango específico de una hoja de cálculo.
    '_sh' es la conexión ya abierta (Spreadsheet).
    Streamlit ignora los argumentos con '_' al cachear.
    """
    try:
        worksheet = _sh.worksheet(sheet_name) # <- CAMBIO AQUÍ
        data = worksheet.get_values(data_range)
        
        if not data:
            st.warning(f"No se encontraron datos en el rango {data_range} de la hoja {sheet_name}")
            return None
        
        # Convertir a Polars (la primera fila son los encabezados)
        df = pl.DataFrame(data[1:], schema=data[0], orient="row")
        return df

    except gspread.exceptions.WorksheetNotFound:
        st.error(f"Error: No se encontró la hoja llamada '{sheet_name}'. Revisa los nombres.")
        return None
    except Exception as e:
        st.error(f"Error al leer el rango '{data_range}': {e}")
        return None

# --- APLICACIÓN PRINCIPAL ---

st.title("Reporte - Parte Diario")
st.markdown("---")

# Botón de recarga
if st.button("Recargar Datos"):
    # Limpiar todos los cachés de datos y recursos
    st.cache_data.clear()
    st.cache_resource.clear()
    st.toast("Forzando recarga de datos...")
    st.rerun()

# Conectar a la hoja de cálculo
sh = get_spreadsheet_connection()

if sh:
    
    # --- 1. TABLA DE OFICIALES ---
    st.header("Resumen de Escalafones - Oficiales")
    
    # Define la hoja y rango para la primera tabla
    HOJA_OFICIALES = "Tabla dinámica 1"
    RANGO_OFICIALES = "A2:D11" # Ajusta este rango
    
    df_oficiales = load_pivot_range(sh, HOJA_OFICIALES, RANGO_OFICIALES)
    
    if df_oficiales is not None:
        st.dataframe(df_oficiales, hide_index=True, width='stretch')
    
    st.markdown("---") # Separador

    # --- 2. TABLA DE SUBOFICIALES ---
    st.header("Resumen de Escalafones - Suboficiales")
    
    # Define la hoja y rango para la segunda tabla
    HOJA_SUBOFICIALES = "Tabla dinámica 1"
    RANGO_SUBOFICIALES = "A19:D25" # ¡¡AJUSTA ESTE RANGO!!
    
    df_suboficiales = load_pivot_range(sh, HOJA_SUBOFICIALES, RANGO_SUBOFICIALES)
    
    if df_suboficiales is not None:
        st.dataframe(df_suboficiales, hide_index=True, width='stretch')

    st.markdown("---") # Separador

    # --- 3. PUEDES AGREGAR OTRA TABLA AQUÍ ---
    # st.header("Otra Tabla")
    # HOJA_OTRA = "Nombre de la Hoja"
    # RANGO_OTRO = "A1:C10"
    # df_otra = load_pivot_range(sh, HOJA_OTRA, RANGO_OTRO)
    # if df_otra is not None:
    #     st.dataframe(df_otra, hide_index=True, width='stretch')
else:
    st.error("No se pudo establecer la conexión con Google Sheets.")

