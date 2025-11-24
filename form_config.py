import streamlit as st
import gspread
import re
from datetime import datetime

# --- CONFIGURACIÓN CENTRALIZADA ---
# ID de tu Google Sheet (movido aquí para evitar importaciones circulares)
GOOGLE_SHEET_ID = "1UOA2HHY1b2W56Ei4YG32sYVJ-0P0zzJcx1C7bBYVK1Q"

# --- CARGA DE LISTAS DESPLEGABLES ---
@st.cache_data(ttl=600)
def get_options_from_sheet(_conn: gspread.Client, range_name: str):
    """
    Busca una lista de opciones en la hoja 'LISTAS'.
    El argumento '_conn' tiene un guion bajo para que st.cache_data lo ignore.
    """
    try:
        # Abre la hoja "LISTAS" usando el ID
        sh = _conn.open_by_key(GOOGLE_SHEET_ID)
        sheet = sh.worksheet("LISTAS")
        
        # .get() devuelve una lista de listas, ej: [['GRADO 1'], ['GRADO 2']]
        values = sheet.get(range_name)
        
        # Convertimos a una lista simple: ['GRADO 1', 'GRADO 2']
        # Nos aseguramos de filtrar valores vacíos
        options = [item[0] for item in values if item and item[0]]
        
        if not options:
            st.warning(f"La lista {range_name} se cargó vacía desde Google Sheets.")
            return []
            
        return options
        
    except gspread.exceptions.WorksheetNotFound:
        st.error("Error crítico: No se encontró la hoja 'LISTAS'.")
        return []
    except Exception as e:
        # Mostramos un error más detallado
        st.error(f"Error al cargar la lista {range_name}: {e}")
        st.error(f"Detalle: {type(e).__name__} - {e}")
        return []

# --- VALIDACIÓN DE DATOS ---
def validate_data(sheet_name: str, data: dict):
    """
    Revisa los datos del formulario contra las reglas de FORM_CONFIG.
    Devuelve (True, "") si es válido, o (False, "mensaje de error") si no.
    """
    fields = FORM_CONFIG.get(sheet_name, {})
    
    for field_name, value in data.items():
        config = fields.get(field_name, {})
        validation_rule = config.get("validate")
        
        # --- Reglas de validación personalizadas ---
        
        if validation_rule == "cedula": # "CED." y "CRED." de 5 cifras
            if value and (not value.isdigit() or len(value) != 5):
                return False, f"El campo '{field_name}' debe ser un número de 5 cifras."

        if validation_rule == "dni": # "D.N.I." de 8 cifras
            if value and (not value.isdigit() or len(value) != 8):
                return False, f"El campo '{field_name}' debe ser un número de 8 cifras."

        if validation_rule == "cuil": # "C.U.I.L."
            cuil_pattern = re.compile(r'^\d{2}-\d{8}-\d{1}$')
            if value and not cuil_pattern.match(value):
                return False, f"El formato de '{field_name}' debe ser xx-xxxxxxxx-x."
        
        if validation_rule == "numeric":
            if value and not str(value).isdigit(): # Convertir a str por si es un int
                return False, f"El campo '{field_name}' debe ser solo numérico."
        
        if validation_rule == "max_30":
            if value and (not str(value).isdigit() or int(value) > 30):
                return False, f"El campo '{field_name}' debe ser un número no mayor a 30."

        if validation_rule == "rango_1_4":
            if value and (not str(value).isdigit() or not 1 <= int(value) <= 4):
                return False, f"El campo '{field_name}' debe ser un número entre 1 y 4."

        # TODO: Agregar más reglas (ej: email, no vacío, etc.)

    # Si pasó todas las validaciones
    return True, ""

# --- ESTRUCTURA DE TODOS LOS FORMULARIOS ---
# Basado en la lista que proporcionaste.
# 'type' define el widget de Streamlit.
# 'options' define las opciones estáticas o dinámicas (con lambda).
# 'validate' apunta a una regla en la función validate_data.

FORM_CONFIG = {
    "DOTACION": {
        "GRADO": {"type": "select", "options": lambda conn: get_options_from_sheet(conn, "K1:K17")},
        "APELLIDOS": {"type": "text"},
        "NOMBRES": {"type": "text"},
        "CRED.": {"type": "text", "validate": "cedula"},
        "SITUACION": {"type": "select", "options": ["PRESENTE", "EGRESADO", "PENDIENTE DE PRESENTACION", "PENDIENTE DE NOTIFICACION"]},
        "MASC / FEM": {"type": "select", "options": ["MASCULINO", "FEMENINO"]},
        "INGRESO": {"type": "date", "min_year": 1993},
        "DISP. ING.": {"type": "text"},
        "FECHA DISP. ING": {"type": "date", "min_year": 1993},
        "FECHA ING. C.P.F.NOA": {"type": "date", "min_year": 2011},
        "DISP.": {"type": "text"},
        "FECHA DE LA DISP.": {"type": "date", "min_year": 2011},
        # --- ¡CAMBIO AQUÍ! ---
        # Se quitó "min_year": 1993 de este campo.
        # No podemos limitar la fecha de nacimiento, ¡la gente nacía antes de 1993!
        "FECHA NAC.": {"type": "date"},
        # --- FIN DEL CAMBIO ---
        "D.N.I.": {"type": "text", "validate": "dni"},
        "C.U.I.L.": {"type": "text", "validate": "cuil"},
        "ESTADO CIVIL": {"type": "select", "options": ["SOLTERO", "CASADO", "UNION CONVIVENCIAL", "DIVORCIADO/A", "VIUDO/A"]},
        # --- ¡CAMBIO AQUÍ! ---
        # Se quitó "min_year": 1993. La fecha de casamiento también puede ser antigua.
        "FECHA CASAM.": {"type": "date"},
        # --- FIN DEL CAMBIO ---
        "DEST. ANT. UNIDAD": {"type": "text"},
        "ESCALAFON": {"type": "select", "options": lambda conn: get_options_from_sheet(conn, "N1:N13")},
        "PROFESION": {"type": "text"},
        "DOMICILIO": {"type": "text"},
        "LOCALIDAD": {"type": "text"},
        "PROVINCIA": {"type": "text"},
        "TELEFONO": {"type": "text", "validate": "numeric"},
        "USUARIO G.D.E.": {"type": "text"},
        "CORREO ELEC": {"type": "text"}, # Podríamos agregar validación "email"
    },
    "FUNCIONES": {
        "EXPEDIENTE": {"type": "text", "max_chars": 40},
        "CRED.": {"type": "text", "validate": "cedula"},
        "JEFATURA / DIRECCION": {"type": "select", "options": lambda conn: get_options_from_sheet(conn, "A1:A89")},
        "DIVISION / DEPARTAMENTO": {"type": "select", "options": lambda conn: get_options_from_sheet(conn, "B1:B89")},
        "SECCION": {"type": "text"},
        "CARGO": {"type": "select", "options": lambda conn: get_options_from_sheet(conn, "C1:C89")},
        "FUNCION DEL B.P.N 700": {"type": "text"},
        "ORDEN INTERNA": {"type": "text"},
        "A PARTIR DE": {"type": "date"},
        "CAMBIO DE DEPENDENCIA": {"type": "select", "options": ["SI", "NO"]}, # Corregido
        "TITULAR – INTERINO - A CARGO": {"type": "select", "options": ["TITULAR", "INTERINO", "A CARGO"]},
        "HORARIO": {"type": "time"}, # 'time' usa formato HH:MM
        "TURNO": {"type": "select", "options": ["A", "B", "C", "D", "NINGUNO"]},
    },
    "SANCION": {
        "EXPEDIENTE": {"type": "text", "max_chars": 40},
        "CRED.": {"type": "text", "validate": "cedula"},
        "FECHA DE LA FALTA": {"type": "date"},
        "FECHA DE NOTIFICACION": {"type": "date"},
        "ART.": {"type": "text"},
        "TIPO DE SANCION": {"type": "select", "options": ["APERCIBIMIENTO", "ARRESTO", "SUSPENCION", "BAJA"]},
        "DIAS DE ARRESTO": {"type": "text", "validate": "numeric"}, # Asumo numérico
    },
    "DOMICILIOS": {
        "EXPEDIENTE": {"type": "text", "max_chars": 40},
        "CRED.": {"type": "text", "validate": "cedula"},
        "FECHA DE CAMBIO": {"type": "date"},
        "DOMICILIO": {"type": "text"},
        "LOCALIDAD": {"type": "text"},
        "PROVINCIA": {"type": "text"},
    },
    "CURSOS": {
        "EXPEDIENTE": {"type": "text", "max_chars": 40},
        "CRED.": {"type": "text", "validate": "cedula"},
        "CURSO": {"type": "text"},
    },
    "SOLICITUD DE PASES": {
        "EXPEDIENTE": {"type": "text", "max_chars": 40},
        "CRED.": {"type": "text", "validate": "cedula"},
        "TIPO DE PASE": {"type": "select", "options": ["PASE", "PERMUTA", "ADSCRIPCION"]},
        "NOMBRE DE LA PERMUTA": {"type": "text"},
        "DESTINO": {"type": "text"},
    },
    "DISPONIBILIDAD": { # "DISPONIBILidad" corregido a "DISPONIBILIDAD"
        "EXPEDIENTE": {"type": "text", "max_chars": 40},
        "CRED.": {"type": "text", "validate": "cedula"},
        "DESDE": {"type": "date"},
        "DIAS": {"type": "text", "validate": "numeric"},
        "FINALIZACION": {"type": "date"},
    },
    "LICENCIAS": {
        "EXPEDIENTE": {"type": "text", "max_chars": 40},
        "CRED.": {"type": "text", "validate": "cedula"},
        "TIPO DE LIC": {"type": "select", "options": lambda conn: get_options_from_sheet(conn, "E1:E30")},
        "DIAS": {"type": "text", "validate": "numeric"},
        "DESDE": {"type": "date"},
        # --- ¡CAMBIO AQUÍ! ---
        # Los campos "HASTA" y "REINTEGRO" han sido eliminados de la configuración
        # para que no aparezcan en el formulario.
        "AÑO": {"type": "text", "validate": "numeric"}, # Asumo numérico
        "PASAJES": {"type": "select", "options": ["SI", "NO"]},
        "DIAS POR VIAJE": {"type": "text", "validate": "numeric"}, # Asumo numérico
        "LUGAR": {"type": "text"},
    },
    "LACTANCIA": {
        "EXPEDIENTE": {"type": "text", "max_chars": 40},
        "CRED.": {"type": "text", "validate": "cedula"},
        "NOMBRE COMPLETO HIJO/A": {"type": "text"},
        "FECHA DE NACIMIENTO": {"type": "date"},
        "EXPEDIENTE DONDE LO INFORMO": {"type": "text"},
        "FECHAS": {"type": "date"},
        "PRORROGA FECHA": {"type": "date"},
    },
    "PARTE DE ENFERMO": {
        "EXPEDIENTE": {"type": "text", "max_chars": 40},
        "CRED.": {"type": "text", "validate": "cedula"},
        "INICIO": {"type": "date"},
        "DESDE (ULTIMO CERTIFICADO)": {"type": "date"}, # Corregido
        "CANTIDAD DE DIAS (ULTIMO CERTIFICADO)": {"type": "text", "validate": "max_30"},
        "FINALIZACION": {"type": "date"},
        "CUMPLE 1528??": {"type": "select", "options": ["SI", "NO"]},
        "CODIGO DE AFECC.": {"type": "text"},
    },
    "PARTE DE ASISTENCIA FAMILIAR": {
        "EXPEDIENTE": {"type": "text", "max_chars": 40},
        "CRED.": {"type": "text", "validate": "cedula"},
        "INICIO": {"type": "date"},
        "DESDE (ULTIMO CERTIFICADO)": {"type": "date"},
        "CANTIDAD DE DIAS (ULTIMO CERTIFICADO)": {"type": "text", "validate": "max_30"},
        "FINALIZACION": {"type": "date"},
        "CUMPLE 1528??": {"type": "select", "options": ["SI", "NO"]},
        "CODIGO DE AFECC.": {"type": "text"},
    },
    "ACCIDENTE DE SERVICIO": {
        "EXPEDIENTE": {"type": "text", "max_chars": 40},
        "CRED.": {"type": "text", "validate": "cedula"},
        "INICIO": {"type": "date"},
        "DESDE (ULTIMO CERTIFICADO)": {"type": "date"},
        "CANTIDAD DE DIAS (ULTIMO CERTIFICADO)": {"type": "text", "validate": "max_30"},
        "FINALIZACION": {"type": "date"},
        "OBSERVACION": {"type": "text_area"}, # Mejor para texto largo
    },
    "CERTIFICADOS MEDICOS": {
        "EXPEDIENTE": {"type": "text", "max_chars": 40},
        # Faltaban los otros campos en tu lista, pero el diccionario VISTA_COLUMNAS... los tenía
    },
    "NOTA DE COMISION MEDICA": {
        "NOTA DE D.RR.HH.": {"type": "text"},
        "FECHA DE NOTA D.RR.HH.": {"type": "date"},
        "TEXTO NOTIFICABLE DE LA NOTA": {"type": "text_area"},
        "CRED.": {"type": "text", "validate": "cedula"}, # Corregido, estaba anidado
        "EXPEDIENTE": {"type": "text"},
        "FECHA DE EVALUACION VIRTUAL": {"type": "date"},
        "FECHA DE EVALUACION PRESENCIAL": {"type": "date"},
        "FECHA DE REINTEGRO": {"type": "date"},
        "1° FECHA DE EVALUACION VIRTUAL": {"type": "date"},
        "2° FECHA DE EVALUACIÓN PRESENCIAL": {"type": "date"},
    },
    "IMPUNTUALIDADES": {
        "EXPEDIENTE": {"type": "text", "max_chars": 40},
        "CRED.": {"type": "text", "validate": "cedula"},
        "FECHA": {"type": "date"},
        "HORA DE DEBIA INGRESAR": {"type": "time"},
        "HORA QUE INGRESO": {"type": "time"},
        "N° DE IMPUNTUALIDAD": {"type": "select", "options": lambda conn: get_options_from_sheet(conn, "I2:I16")},
    },
    "COMPLEMENTO DE HABERES": {
        "EXPEDIENTE": {"type": "text", "max_chars": 40},
        "CRED.": {"type": "text", "validate": "cedula"},
        "TIPO": {"type": "select", "options": ["VARIABILIDAD DE VIVIENDA", "FIJACION DE DOMICILIO", "BONIFICACION POR TITULO"]},
    },
    "OFICIOS": {
        "EXPEDIENTE": {"type": "text", "max_chars": 40},
        "CRED.": {"type": "text", "validate": "cedula"},
        "PICU_OFICIO": {"type": "text_area"},
        "FECHA del OFICIO": {"type": "date"},
    },
    "NOTAS DAI": {
        "NOTA DAI": {"type": "text", "max_chars": 40},
        "CRED.": {"type": "text", "validate": "cedula"},
        "PICU_NOTA_DAI": {"type": "text_area"},
        "FECHA de NOTA DAI": {"type": "date"},
    },
    "INASISTENCIAS": {
        "EXPEDIENTE": {"type": "text", "max_chars": 40},
        "CRED.": {"type": "text", "validate": "cedula"},
        "FECHA DE LA FALTA": {"type": "date"}, # Asumo fecha
        "MOTIVO": {"type": "select", "options": ["FALTA CON AVISO", "FALTA SIN AVISO"]},
    },
    "MESA DE ENTRADA": {
        # Esta hoja no estaba en tu lista de CAMPOS_DE_FORMULARIOS
    },
}