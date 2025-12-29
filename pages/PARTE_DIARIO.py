import streamlit as st
import polars as pl
import gspread
import json # Para las credenciales de SA
import os # Para las variables de entorno
from dotenv import load_dotenv # Para cargar el .env local
import xlsxwriter
from io import BytesIO
import datetime

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
        # --- NUEVO: Limpiar caracteres inválidos ---
        # Reemplaza espacios no separables (comunes al copiar/pegar) por espacios normales
        creds_json_str = creds_json_str.replace('\u00a0', ' ')
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

def generate_excel_report(recuento_df, oficiales_df, suboficiales_df, pendiente_de_presentacion_df, pendiente_de_notificacion_df, recuento_de_inasistencias_df,parte_de_enfermo_df,parte_de_asistencia_familiar_df, accidente_de_servicio_df, capacidad_laboral_df, disponibilidad_df, renuncia_df, fallecimiento_df, suspension_preventiva_df, inasistencia_injustificada_df):
    output = BytesIO()
    workbook = xlsxwriter.Workbook(output, {'in_memory': True})
    worksheet = workbook.add_worksheet('Reporte Parte Diario')

    # Styles
    title_format = workbook.add_format({'bold': True, 'font_size': 14})
    header_format = workbook.add_format({'bold': True, 'bg_color': '#D3D3D3', 'border': 1})
    cell_format = workbook.add_format({'border': 1})
    centered_cell_format = workbook.add_format({'border': 1, 'align': 'center'})
    date_format = workbook.add_format({'italic': True})

    # Title and Date (Moved to Column B)
    worksheet.write('B1', 'Reporte - Parte Diario', title_format)
    worksheet.write('B2', f"Fecha de generación: {datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}", date_format)
    
    current_row = 4

    def write_df_to_excel(df, title, start_row):
        if df is not None:
            # Title in Column B
            worksheet.write(start_row, 1, title, title_format)
            start_row += 1
            
            # Write header
            # Other columns starting from A
            for col_idx, col_name in enumerate(df.columns):
                worksheet.write(start_row, col_idx, str(col_name), header_format)
            
            # Write data
            for row_idx, row in enumerate(df.iter_rows()):
                for col_idx, val in enumerate(row):
                    # Handle potential None values
                    val_str = str(val) if val is not None else ""
                    worksheet.write(start_row + 1 + row_idx, col_idx, val_str, cell_format)
            
            # Return next available row (header + data + spacing)
            return start_row + 1 + len(df) + 2
        return start_row

    current_row = write_df_to_excel(recuento_df, 'RECUENTO GENERAL', current_row)
    current_row = write_df_to_excel(oficiales_df, 'Oficiales', current_row)
    current_row = write_df_to_excel(suboficiales_df, 'Suboficiales', current_row)
    current_row = write_df_to_excel(pendiente_de_presentacion_df, 'Pendientes de Presentación', current_row)
    current_row = write_df_to_excel(pendiente_de_notificacion_df, 'Pendientes de Notificación', current_row)
    current_row = write_df_to_excel(recuento_de_inasistencias_df, 'Recuento de Inasistencias', current_row)
    current_row = write_df_to_excel(parte_de_enfermo_df, 'Parte de Enfermo', current_row)
    current_row = write_df_to_excel(parte_de_asistencia_familiar_df, 'Parte de Asistencia Familiar', current_row)
    current_row = write_df_to_excel(accidente_de_servicio_df, 'Accidente de Servicio', current_row)
    current_row = write_df_to_excel(capacidad_laboral_df, 'Capacidad Laboral', current_row)
    current_row = write_df_to_excel(disponibilidad_df, 'Disponibilidad', current_row)
    current_row = write_df_to_excel(renuncia_df, 'Renuncia', current_row)
    current_row = write_df_to_excel(fallecimiento_df, 'Fallecimiento', current_row)
    current_row = write_df_to_excel(suspension_preventiva_df, 'Suspensión Preventiva', current_row)
    current_row = write_df_to_excel(inasistencia_injustificada_df, 'Inasistencia Injustificada', current_row)
    
    

    # Column widths
    worksheet.set_column(0, 0, 5)  # Column A width (small for numbering)
    worksheet.set_column(1, 6, 20) # Other columns width

    workbook.close()
    output.seek(0)
    return output

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
    st.header("RECUENTO GENERAL")
    
    # Define la hoja y rango para la primera tabla
    HOJA_RECUENTO = "Tabla dinámica 1"
    RANGO_RECUENTO = "A2:E5" # Ajusta este rango
    
    df_recuento = load_pivot_range(sh, HOJA_RECUENTO, RANGO_RECUENTO)
    
    if df_recuento is not None:
        st.dataframe(df_recuento, hide_index=True, width='stretch')
    
    
    # --- 2. TABLA DE Oficiales ---
    st.header("Oficiales")
    
    # Define la hoja y rango para la segunda tabla
    HOJA_OFICIALES = "Tabla dinámica 1"
    RANGO_OFICIALES = "A7:E22" # ¡¡AJUSTA ESTE RANGO!!
    
    df_oficiales = load_pivot_range(sh, HOJA_OFICIALES, RANGO_OFICIALES)
    
    if df_oficiales is not None:
        st.dataframe(df_oficiales, hide_index=True, width='stretch')

        
    # --- 3. PUEDES AGREGAR OTRA TABLA AQUÍ ---
    st.header("Suboficiales")
    HOJA_SUBOFICIALES = "Tabla dinámica 1"
    RANGO_SUBOFICIALES = "A25:E32"
    df_suboficiales = load_pivot_range(sh, HOJA_SUBOFICIALES, RANGO_SUBOFICIALES)
    if df_suboficiales is not None:
        st.dataframe(df_suboficiales, hide_index=True, width='stretch')
    
    # --- 4. PENDIENTES DE PRESENTACION ---
    st.header("Pendientes de Presentación")
    HOJA_PENDIENTE_DE_PRESENTACION = "Tabla dinámica 1"
    RANGO_PENDIENTE_DE_PRESENTACION = "G2:L"
    df_pendient_de_presentacion = load_pivot_range(sh, HOJA_PENDIENTE_DE_PRESENTACION, RANGO_PENDIENTE_DE_PRESENTACION)
    if df_pendient_de_presentacion is not None:
        st.dataframe(df_pendient_de_presentacion, hide_index=True, width='stretch')

    # --- 5. PENDIENTES DE NOTIFICACION ---
    st.header("Pendientes de Notificacón")
    HOJA_PENDIENTE_DE_NOTIFICACION = "Tabla dinámica 1"
    RANGO_PENDIENTE_DE_NOTIFICACION = "M2:R"
    df_pendient_de_notificacion = load_pivot_range(sh, HOJA_PENDIENTE_DE_NOTIFICACION, RANGO_PENDIENTE_DE_NOTIFICACION)
    if df_pendient_de_notificacion is not None:
        st.dataframe(df_pendient_de_notificacion, hide_index=True, width='stretch')


    # --- 6. RECUENTTO DE INASITENCIAS ---
    st.header("Recuento de Inasistencias")
    HOJA_RECUENTO_DE_INASISTENCIAS = "Tabla dinámica 1"
    RANGO_RECUENTO_DE_INASISTENCIAS = "T2:V"
    df_recuento_de_inasistencias = load_pivot_range(sh, HOJA_RECUENTO_DE_INASISTENCIAS, RANGO_RECUENTO_DE_INASISTENCIAS)
    if df_recuento_de_inasistencias is not None:
        st.dataframe(df_recuento_de_inasistencias, hide_index=True, width='stretch')


    # --- 7. PARTE DE ENFERMO ---
    st.header("Parte de Enfermo")
    HOJA_PARTE_DE_ENFERMO = "Tabla dinámica 1"
    RANGO_PARTE_DE_ENFERMO = "Y2:AF"
    df_parte_de_enfermo = load_pivot_range(sh, HOJA_PARTE_DE_ENFERMO, RANGO_PARTE_DE_ENFERMO)
    if df_parte_de_enfermo is not None:
        st.dataframe(df_parte_de_enfermo, hide_index=True, width='stretch')


    # --- 8. PARTE DE ASISTENCIA FAMILIAR ---
    st.header("Parte de Asistencia Familiar")
    HOJA_PARTE_DE_ASISTENCIA_FAMILIAR = "Tabla dinámica 1"
    RANGO_PARTE_DE_ASISTENCIA_FAMILIAR = "AJ2:AP"
    df_parte_de_asistencia_familiar = load_pivot_range(sh, HOJA_PARTE_DE_ASISTENCIA_FAMILIAR, RANGO_PARTE_DE_ASISTENCIA_FAMILIAR)
    if df_parte_de_asistencia_familiar is not None:
        st.dataframe(df_parte_de_asistencia_familiar, hide_index=True, width='stretch')

    # --- 9. ACCIDENTE DE SERVICIO ---
    st.header("Accidente de Servicio")
    HOJA_ACCIDENTE_DE_SERVICIO = "Tabla dinámica 1"
    RANGO_ACCIDENTE_DE_SERVICIO = "AS2:AZ"
    df_accidente_de_servicio = load_pivot_range(sh, HOJA_ACCIDENTE_DE_SERVICIO, RANGO_ACCIDENTE_DE_SERVICIO)
    if df_accidente_de_servicio is not None:
        st.dataframe(df_accidente_de_servicio, hide_index=True, width='stretch')

    # --- 10. CAPACIDAD LABORAL ---
    st.header("Capacidad Laboral")
    HOJA_CAPACIDAD_LABORAL = "Tabla dinámica 1"
    RANGO_CAPACIDAD_LABORAL = "BC2:BJ"
    df_capacidad_laboral = load_pivot_range(sh, HOJA_CAPACIDAD_LABORAL, RANGO_CAPACIDAD_LABORAL)
    if df_capacidad_laboral is not None:
        st.dataframe(df_capacidad_laboral, hide_index=True, width='stretch')

    # --- 11. DISPONIBILIDAD ---
    st.header("Disponibilidad")
    HOJA_DISPONIBILIDAD = "Tabla dinámica 1"
    RANGO_DISPONIBILIDAD = "BN2:BU"
    df_disponibilidad = load_pivot_range(sh, HOJA_DISPONIBILIDAD, RANGO_DISPONIBILIDAD)
    if df_disponibilidad is not None:
        st.dataframe(df_disponibilidad, hide_index=True, width='stretch')

    # --- 12. RENUNCIA ---
    st.header("Renuncia")
    HOJA_RENUNCIA = "Tabla dinámica 1"
    RANGO_RENUNCIA = "BZ2:CF"
    df_renuncia = load_pivot_range(sh, HOJA_RENUNCIA, RANGO_RENUNCIA)
    if df_renuncia is not None:
        st.dataframe(df_renuncia, hide_index=True, width='stretch')

    # --- 13. FALLECIMIENTO ---
    st.header("Fallecimiento")
    HOJA_FALLECIMIENTO = "Tabla dinámica 1"
    RANGO_FALLECIMIENTO = "CK2:CQ"
    df_fallecimiento = load_pivot_range(sh, HOJA_FALLECIMIENTO, RANGO_FALLECIMIENTO)
    if df_fallecimiento is not None:
        st.dataframe(df_fallecimiento, hide_index=True, width='stretch')

    # --- 14. SUSPENSIÓN PREVENTIVA ---
    st.header("Suspensión Preventiva")
    HOJA_SUSPENSION_PREVENTIVA = "Tabla dinámica 1"
    RANGO_SUSPENSION_PREVENTIVA = "CV2:DA"
    df_suspension_preventiva = load_pivot_range(sh, HOJA_SUSPENSION_PREVENTIVA, RANGO_SUSPENSION_PREVENTIVA)
    if df_suspension_preventiva is not None:
        st.dataframe(df_suspension_preventiva, hide_index=True, width='stretch')

    # --- 15. INASISTENCIA INJUSTIFICADA ---
    st.header("Inasistencia Injustificada")
    HOJA_INASISTENCIA_INJUSTIFICADA = "Tabla dinámica 1"
    RANGO_INASISTENCIA_INJUSTIFICADA = "DG2:DL"
    df_inasistencia_injustificada = load_pivot_range(sh, HOJA_INASISTENCIA_INJUSTIFICADA, RANGO_INASISTENCIA_INJUSTIFICADA)
    if df_inasistencia_injustificada is not None:
        st.dataframe(df_inasistencia_injustificada, hide_index=True, width='stretch')

    # --- BOTÓN DE DESCARGA ---
    st.markdown("### Descargar Informe")
    # Generamos el archivo en memoria
    # Pasamos los dataframes, si alguno no se cargó (es None), la función lo maneja
    excel_bio = generate_excel_report(df_recuento, df_oficiales, df_suboficiales, df_pendient_de_presentacion, df_pendient_de_notificacion, df_recuento_de_inasistencias, df_parte_de_enfermo, df_parte_de_asistencia_familiar, df_accidente_de_servicio, df_capacidad_laboral, df_disponibilidad, df_renuncia, df_fallecimiento, df_suspension_preventiva, df_inasistencia_injustificada )
    
    st.download_button(
        label="� Descargar como Excel",
        data=excel_bio.getvalue(),
        file_name=f"Parte_Diario_{datetime.date.today()}.xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    )
else:
    st.error("No se pudo establecer la conexión con Google Sheets.")

