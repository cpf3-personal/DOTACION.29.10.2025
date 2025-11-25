import streamlit as st
import polars as pl
import gspread
import gspread.utils 
import re 
import json 
import os 
import html 
from dotenv import load_dotenv
from datetime import datetime, time, date, timedelta

# --- IMPORTACIÓN DE CONFIGURACIÓN ---
try:
    from form_config import (
        GOOGLE_SHEET_ID,
        FORM_CONFIG, 
        validate_data,
        get_options_from_sheet
    )
except ImportError:
    st.error("Error crítico: No se pudo encontrar el archivo 'form_config.py'. Asegúrate de que esté en la misma carpeta.")
    st.stop()

# --- GESTIÓN DE ESTADO POR HOJA (NUEVO) ---
def init_sheet_state(sheet_name):
    """Inicializa el estado para una hoja específica si no existe."""
    mode_key = f"mode_{sheet_name}"
    data_key = f"edit_data_{sheet_name}"
    
    if mode_key not in st.session_state:
        st.session_state[mode_key] = "view" # Modos: 'view', 'add', 'edit'
    if data_key not in st.session_state:
        st.session_state[data_key] = None

def set_sheet_mode(sheet_name, mode, data=None):
    """Establece el modo (ver, agregar, editar) para una hoja específica."""
    st.session_state[f"mode_{sheet_name}"] = mode
    st.session_state[f"edit_data_{sheet_name}"] = data

def get_sheet_mode(sheet_name):
    """Obtiene el modo actual de una hoja."""
    return st.session_state.get(f"mode_{sheet_name}", "view")

def get_sheet_edit_data(sheet_name):
    """Obtiene los datos de la fila que se está editando en una hoja."""
    return st.session_state.get(f"edit_data_{sheet_name}", None)

# --- RENDERIZADO DE CAMPOS ---
def _render_form_fields(gc: gspread.Client, sheet_name: str, existing_data: dict = None):
    form_config = FORM_CONFIG.get(sheet_name, {})
    if not form_config:
        st.warning(f"No hay configuración de formulario definida para '{sheet_name}' en FORM_CONFIG.")
        return {}

    data_to_submit = {}
    cols = st.columns(3)
    col_index = 0

    for field_name, config in form_config.items():
        field_type = config.get("type", "text")
        default_value = existing_data.get(field_name) if existing_data else None
        current_col = cols[col_index]

        try:
            # Generamos una key única combinando el nombre de la hoja y el campo
            widget_key = f"{sheet_name}_{field_name}_input"

            if field_type == "select":
                options_source = config.get("options", [])
                options = []
                if callable(options_source):
                    options = options_source(gc)
                elif isinstance(options_source, list):
                    options = options_source
                
                default_index = options.index(default_value) if default_value and default_value in options else 0
                data_to_submit[field_name] = current_col.selectbox(field_name, options, index=default_index, key=widget_key)
            
            elif field_type == "date":
                min_year = config.get("min_year")
                min_date = date(min_year, 1, 1) if min_year else None
                
                date_value = None
                if isinstance(default_value, str) and default_value:
                    try:
                        date_value = datetime.strptime(default_value, "%Y-%m-%d").date()
                    except (ValueError, TypeError):
                        try:
                            date_value = datetime.strptime(default_value, "%d/%m/%Y").date()
                        except (ValueError, TypeError):
                            date_value = None
                elif isinstance(default_value, datetime):
                    date_value = default_value.date()
                
                # --- INICIO MODIFICACIÓN (Permitir fechas vacías) ---
                # Permitimos que el valor inicial sea None (vacío) en lugar de forzar date.today()
                st_date_value = date_value 
                
                # Solo verificamos el rango mínimo si existe una fecha seleccionada
                if st_date_value is not None and min_date and st_date_value < min_date:
                    st_date_value = min_date
                
                date_params = {"label": field_name, "value": st_date_value, "format": "DD/MM/YYYY", "key": widget_key}
                if min_date: date_params["min_value"] = min_date
                
                data_to_submit[field_name] = current_col.date_input(**date_params)
                # --- FIN MODIFICACIÓN ---

            elif field_type == "time":
                time_value = None
                if isinstance(default_value, str) and default_value:
                    try:
                        time_value = datetime.strptime(default_value, "%H:%M:%S").time()
                    except (ValueError, TypeError):
                        try:
                            time_value = datetime.strptime(default_value, "%H:%M").time()
                        except (ValueError, TypeError):
                            time_value = None
                
                data_to_submit[field_name] = current_col.time_input(field_name, value=time_value, key=widget_key)

            elif field_type == "text_area":
                data_to_submit[field_name] = current_col.text_area(field_name, value=str(default_value or ""), key=widget_key)
                
            else:
                max_chars = config.get("max_chars")
                data_to_submit[field_name] = current_col.text_input(field_name, value=str(default_value or ""), max_chars=max_chars, key=widget_key)

        except Exception as e:
            st.error(f"Error al renderizar '{field_name}': {e}")
            data_to_submit[field_name] = None

        col_index = (col_index + 1) % 3
        
    return data_to_submit

# --- FORMULARIOS ---
def show_add_form(gc: gspread.Client, selected_sheet: str, all_columns: list, clear_cache_func):
    st.markdown(f"#### ➕ Nuevo Registro en: {selected_sheet}")
    st.info("Completá los datos a continuación.")
    
    with st.form(key=f"add_form_{selected_sheet}"):
        data_to_submit = _render_form_fields(gc, selected_sheet)
        st.markdown("---")
        submitted = st.form_submit_button("Guardar Nuevo Registro")

    if submitted:
        is_valid, error_message = validate_data(selected_sheet, data_to_submit)
        if not is_valid:
            st.error(f"Error de validación: {error_message}")
            return

        try:
            with st.spinner("Guardando..."):
                sh = gc.open_by_key(GOOGLE_SHEET_ID)
                worksheet = sh.worksheet(selected_sheet)
                new_row = []
                for col_name in all_columns:
                    value = data_to_submit.get(col_name)
                    if isinstance(value, date): value = value.strftime("%d/%m/%Y")
                    elif isinstance(value, time): value = value.strftime("%H:%M:%S")
                    elif value is None: value = ""
                    new_row.append(str(value))
                
                worksheet.insert_row(new_row, index=2, value_input_option='USER_ENTERED')
            
            st.success("¡Guardado exitosamente!")
            clear_cache_func()
            set_sheet_mode(selected_sheet, "view") # Volver a modo vista
            st.rerun()

        except Exception as e:
            st.error(f"Error al guardar: {e}")

    if st.button("Cancelar", key=f"cancel_add_{selected_sheet}"):
        set_sheet_mode(selected_sheet, "view")
        st.rerun()

def show_edit_form(gc: gspread.Client, row_data: dict, selected_sheet: str, all_columns: list, clear_cache_func):
    st.markdown(f"#### ✏️ Editando Registro en: {selected_sheet}")
    id_column_name = all_columns[0]
    id_value = row_data.get(id_column_name)
    
    if not id_value:
        st.error("Error: Fila sin ID.")
        return

    with st.form(key=f"edit_form_{selected_sheet}_{id_value}"):
        data_to_submit = _render_form_fields(gc, selected_sheet, existing_data=row_data)
        st.markdown("---")
        col1, col2 = st.columns(2)
        with col1:
            submitted = st.form_submit_button("Actualizar Registro", type="primary")
        with col2:
            pass 

    if submitted:
        is_valid, error_message = validate_data(selected_sheet, data_to_submit)
        if not is_valid:
            st.error(f"Error: {error_message}")
            return

        try:
            with st.spinner("Actualizando..."):
                sh = gc.open_by_key(GOOGLE_SHEET_ID)
                worksheet = sh.worksheet(selected_sheet)
                cell = worksheet.find(id_value, in_column=1)
                if not cell:
                    st.error("No se encontró la fila original.")
                    return

                updated_row = []
                for col_name in all_columns:
                    value = data_to_submit.get(col_name)
                    if isinstance(value, date): value = value.strftime("%d/%m/%Y")
                    elif isinstance(value, time): value = value.strftime("%H:%M:%S")
                    elif value is None: value = ""
                    updated_row.append(str(value))
                
                range_to_update = f"A{cell.row}:{gspread.utils.rowcol_to_a1(cell.row, len(all_columns))}"
                worksheet.update(range_to_update, [updated_row], value_input_option='USER_ENTERED')
            
            st.success("¡Actualizado!")
            clear_cache_func()
            set_sheet_mode(selected_sheet, "view")
            st.rerun()

        except Exception as e:
            st.error(f"Error al actualizar: {e}")

    if st.button("Cancelar Edición", key=f"cancel_edit_{selected_sheet}"):
        set_sheet_mode(selected_sheet, "view")
        st.rerun()

# --- CONFIGURACIÓN Y CARGA ---
st.set_page_config(layout="wide") 
load_dotenv() 

SCOPES = ["https://www.googleapis.com/auth/spreadsheets", "https://www.googleapis.com/auth/drive.file"]

# (Aquí van tus diccionarios VISTA_COLUMNAS_POR_HOJA y BOTONES_COPIADO_POR_HOJA tal cual estaban)
VISTA_COLUMNAS_POR_HOJA = {
    "DOTACION": ["N°", "COD", "GRADO", "APELLIDOS", "NOMBRES","CRED.", "SITUACION", "MASC / FEM", "INGRESO", "DISP. ING.", "FECHA DISP. ING", "FECHA ING. C.P.F.NOA", "DISP.", "FECHA DE LA DISP.", "FECHA NAC.", "EDAD", "D.N.I.", "C.U.I.L.", "ESTADO CIVIL", "FECHA CASAM.", "JEFATURA / DIRECCION", "DEPARTAMENTO / DIVISION SECCION", "FUNCION", "ORDEN INTERNA", "A PARTIR DE", "EXPEDIENTE DE FUNCION", "DEST. ANT. UNIDAD", "ESCALAFON", "PROFESION", "DOMICILIO", "LOCALIDAD", "PROVINCIA", "TELEFONO", "USUARIO G.D.E.", "CORREO ELEC", "REPARTICIÓN", "SECTOR", "JERARQUIA"],
    "FUNCIONES": ["EXPEDIENTE", "GRADO", "NOMBRES Y APELLIDOS", "CRED.", "JEFATURA / DIRECCION", "DIVISION / DEPARTAMENTO", "SECCION", "CARGO", "FUNCION DEL B.P.N 700", "ORDEN INTERNA", "A PARTIR DE", "CAMBIO DE DEPENDENCIA", "TITULAR – INTERINO - A CARGO", "HORARIO", "TURNO"],
    "SANCION" : ["EXPEDIENTE", "GRADO", "NOMBRES Y APELLIDOS" , "CRED.", "FECHA DE LA FALTA", "FECHA DE NOTIFICACION", "ART.", "TIPO DE SANCION", "DIAS DE ARRESTO"],
    "DOMICILIOS" : ["EXPEDIENTE", "GRADO", "NOMBRES Y APELLIDOS" , "CRED.", "FECHA DE CAMBIO", "DOMICILIO", "LOCALIDAD", "PROVINCIA" ],
    "CURSOS" : ["EXPEDIENTE", "GRADO", "NOMBRES Y APELLIDOS" , "CRED.", "CURSO"],
    "SOLICITUD DE PASES" : ["EXPEDIENTE", "GRADO", "NOMBRES Y APELLIDOS" , "CRED.", "TIPO DE PASE", "NOMBRE DE LA PERMUTA", "DESTINO"], 
    "DISPONIBILIDAD" : ["EXPEDIENTE", "GRADO", "NOMBRES Y APELLIDOS" , "CRED.", "DESDE", "DIAS", "FINALIZACION"],
    "LICENCIAS": ["EXPEDIENTE", "GRADO", "NOMBRE Y APELLIDO", "CRED.", "TIPO DE LIC", "DIAS", "DESDE", "HASTA", "AÑO", "PASAJES" , "DIAS POR VIAJE", "LUGAR" ],
    "LACTANCIA": ["EXPEDIENTE", "GRADO", "NOMBRE Y APELLIDO", "CRED.", "NOMBRE COMPLETO HIJO/A", "FECHA DE NACIMIENTO", "EXPEDIENTE DONDE LO INFORMO", "FECHAS", "PRORROGA FECHA"],
    "PARTE DE ENFERMO" : ["EXPEDIENTE", "GRADO", "NOMBRE Y APELLIDO", "CRED.", "AÑO", "INICIO", "DESDE (ULTIMO CERTIFICADO)", "CANTIDAD DE DIAS (ULTIMO CERTIFICADO)", "HASTA (ULTIMO CERTIFICADO)", "FINALIZACION", "CUMPLE 1528??", "DIAS DE INASISTENCIA JUSTIFICADO", "DIAS DE INASISTENCIA A HOY", "CANTIDAD DE DIAS ANTERIORES AL TRAMITE", "CODIGO DE AFECC.", "DIVISION" ],
    "PARTE DE ASISTENCIA FAMILIAR" : ["EXPEDIENTE", "GRADO", "NOMBRE Y APELLIDO", "CRED.", "AÑO", "INICIO", "DESDE (ULTIMO CERTIFICADO)", "CANTIDAD DE DIAS (ULTIMO CERTIFICADO)", "HASTA (ULTIMO CERTIFICADO)", "FINALIZACION", "CUMPLE 1528??", "DIAS DE INASISTENCIA JUSTIFICADO", "DIAS DE INASISTENCIA A HOY", "CANTIDAD de DIAS ANTERIORES AL TRAMITE", "CODIGO DE AFECC.", "DIVISION" ],
    "ACCIDENTE DE SERVICIO" : ["EXPEDIENTE", "GRADO", "NOMBRE Y APELLIDO", "CRED.", "AÑO", "INICIO", "DESDE", "CANTIDAD DE DIAS (ULTIMO CERTIFICADO)", "HASTA", "FINALIZACION", "DIVISION", "OBSERVACION"],
    "CERTIFICADOS MEDICOS": ["GRADO", "Nombre y Apellido", "CREDENCIAL","SELECCIONA EL TIPO DE TRÁMITE", "CANTIDAD DE DIAS DE REPOSO", "INGRESA EL CERTIFICADO", "DIAGNOSTICO", "NOMBRE Y APELLIDO DEL MÉDICO", "ESPECIALIDAD DEL MÉDICO", "MATRÍCULA DEL MÉDICO", "N° de TELÉFONO DE CONTACTO", "PARENTESCO CON EL FAMILIAR", "NOMBRES Y APELLIDOS DEL FAMILIAR", "FECHA DE NACIMIENTO", "FECHA DE CASAMIENTO (solo para el personal casado)"], 
    "NOTA DE COMISION MEDICA" : ["NOTA DE D.RR.HH.", "FECHA DE NOTA D.RR.HH.", "TEXTO NOTIFICABLE DE la NOTA", "CRED.", "EXPEDIENTE", "RELACIONADO A . . .", "FECHA DE EVALUACION VIRTUAL", "FECHA DE EVALUACION PRESENCIAL", "FECHA DE REINTEGRO", "1° FECHA DE EVALUACION VIRTUAL", "2° FECHA DE EVALUACIÓN PRESENCIAL", "GRADO", "APELLIDO Y NOMBRE"],
    "IMPUNTUALIDADES": ["EXPEDIENTE", "GRADO", "NOMBRES Y APELLIDOS" , "CRED.", "FECHA", "HORA DE DEBIA INGRESAR", "HORA QUE INGRESO", "AÑO", "N° DE IMPUNTUALIDAD"],
    "COMPLEMENTO DE HABERES" : ["EXPEDIENTE", "GRADO", "NOMBRES Y APELLIDOS" , "CRED.", "TIPO"],
    "OFICIOS" : ["EXPEDIENTE", "GRADO", "NOMBRES Y APELLIDOS", "CRED.", "PICU_OFICIO", "FECHA del OFICIO"],
    "NOTAS DAI" : ["NOTA DAI", "GRADO", "NOMBRES Y APELLIDOS", "CRED.", "PICU_NOTA_DAI", "FECHA de NOTA DAI"],
    "INASISTENCIAS" : ["EXPEDIENTE", "GRADO", "NOMBRES Y APELLIDOS", "CRED.", "FECHA DE LA FALTA", "MOTIVO"],
    "MESA DE ENTRADA": ["Número Expediente", "Código Trámite", "Descripción del Trámite", "Motivo"],
}

BOTONES_COPIADO_POR_HOJA = {
    "DOTACION": { "RADIOGRAMA DE PRESENTACION (NOTA)": "RADIOGRAMA DE PRESENTACION (NOTA)", "ACTA DE NOTIFICACION POR TRASLADO (ACTFC)": "ACTA DE NOTIFICACION POR TRASLADO (ACTFC)", "RADIOGRAMA DE NOTIFICACION (NOTA)": "RADIOGRAMA DE NOTIFICACION (NOTA)", "REMISION DE D.L.P. (NOTA)": "REMISION DE D.L.P. (NOTA)" , "SITUACION DE REVISTA (SOLO WORD)": "SITUACION DE REVISTA (SOLO WORD)" },

    "FUNCIONES": { "ORDENATIVA (ORDEN)": "ORDENATIVA (ORDEN)", "ARTICULO": "ARTICULO", "ELEVACION (INFFC)": "ELEVACION (INFFC)",  "ARCHIVO": "ARCHIVO", "ANOTACION D.L.P." : "ANOTACION D.L.P."},

    "LICENCIAS": { "SITUACION DE REVISTA LICENCIA (INFFC)": "SITUACION DE REVISTA LICENCIA (INFFC)", "ORDENATIVA (ORDEN)": "ORDENATIVA (ORDEN)", "CONTROL DE DOCUMENTACION (INFFC)": "CONTROL DE DOCUMENTACION (INFFC)", "ARCHIVO (IF)": "ARCHIVO (IF)" },

    "PARTE DE ENFERMO": { "SITUACION DE REVISTA (INFFC)": "SITUACION DE REVISTA (INFFC)", "SOLICITUD DE CERTIFICADO (INFFC)": "SOLICITUD DE CERTIFICADO (INFFC)", "ORDENATIVA (ORDEN)": "ORDENATIVA (ORDEN)", "ARCHIVO (IF)": "ARCHIVO (IF)", "SITUACION DE REVISTA ELEVACION P.E.L.E. (INFFC)": "SITUACION DE REVISTA ELEVACION P.E.L.E. (INFFC)", "ELVACION P.E.L.E. (IF)": "ELVACION P.E.L.E. (IF)" },

    "PARTE DE ASISTENCIA FAMILIAR": { "SITUACION DE REVISTA (INFFC)": "SITUACION DE REVISTA (INFFC)", "INFORMAR FAMILIAR (INFFC)": "INFORMAR FAMILIAR (INFFC)","SOLICITUD DE CERTIFICADO (INFFC)": "SOLICITUD DE CERTIFICADO (INFFC)", "ORDENATIVA (ORDEN)": "ORDENATIVA (ORDEN)", "ARCHIVO (IF)": "ARCHIVO (IF)", "SITUACION DE REVISTA ELEVACION P.A.F. (INFFC)": "SITUACION DE REVISTA ELEVACION P.A.F. (INFFC)", "ELVACION P.A.F. (IF)": "ELVACION P.A.F. (IF)" },

    "ACCIDENTE DE SERVICIO": { "SITUACION DE REVISTA (INFFC)": "SITUACION DE REVISTA (INFFC)", "ELVACION ACCIDENTE (IF)": "ELVACION ACCIDENTE (IF)","SITUACION DE REVISTA AUDITORIA (INFFC)": "SITUACION DE REVISTA AUDITORIA (INFFC)", "PICU PARA D.L.P.": "PICU PARA D.L.P." },

    "IMPUNTUALIDADES": {"SITUACION DE REVISTA IMPUNTUALIDAD (INFFC)": "SITUACION DE REVISTA IMPUNTUALIDAD (INFFC)", "ORDENATIVA DE IMPUNTUALIDAD (ORDEN)": "ORDENATIVA DE IMPUNTUALIDAD (ORDEN)", "ARCHIVO DE IMPUNTUALIDAD (IF)": "ARCHIVO DE IMPUNTUALIDAD (IF)"},
    
    "OFICIOS": { "SITUACION DE REVISTA OFICIO (INFFC)": "SITUACION DE REVISTA OFICIO (INFFC)", "SOLICITUD DE NOTIFICACION (INFFC)": "SOLICITUD DE NOTIFICACION (INFFC)", "ELEVACION DE NOTIFICACION (INFFC)": "ELEVACION DE NOTIFICACION (INFFC)", "ARCHIVO IF": "ARCHIVO IF", "ANOTACION D.L.P." : "ANOTACION D.L.P."},

    "INASISTENCIAS": { "SITUACION DE REVISTA FALTA CON/SIN AVISO (INFFC)": "SITUACION DE REVISTA FALTA CON/SIN AVISO (INFFC)", "ORDENATIVA DE FALTACON/SIN AVISO (ORDEN)": "ORDENATIVA DE FALTACON/SIN AVISO (ORDEN)", "ARCHIVO (IF)": "ARCHIVO (IF)" }

}

# --- MODIFICACIÓN DE AUTENTICACIÓN ---
# Hacemos la autenticación "a prueba de fallos" de st.secrets
@st.cache_resource
def get_gspread_client():
    creds_data = None
    
    # 1. Intentamos obtener credenciales de st.secrets (falla si no existe el archivo)
    try:
        # Acceder a st.secrets puede lanzar FileNotFoundError o StreamlitSecretNotFoundError
        # si el archivo .streamlit/secrets.toml no existe.
        if "GCP_SA_CREDENTIALS" in st.secrets:
            creds_data = st.secrets["GCP_SA_CREDENTIALS"]
    except Exception:
        # Si falla, simplemente lo ignoramos y seguimos a la siguiente opción
        pass

    # 2. Si no funcionó, intentamos variables de entorno
    if not creds_data:
        creds_data = os.environ.get("GCP_SA_CREDENTIALS")
    
    # 3. Si aún no hay nada, mostramos error
    if not creds_data:
        st.error("Error: No se encontró 'GCP_SA_CREDENTIALS'.")
        st.info("Si estás ejecutando localmente, asegúrate de tener el archivo `.streamlit/secrets.toml` o la variable de entorno configurada.")
        st.stop()
        return None
    
    # Procesar credenciales
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

def _clean_headers(headers):
    counts = {}
    new_headers = []
    for header in map(str.strip, headers):
        counts[header] = counts.get(header, 0) + 1
        new_headers.append(f"{header}_{counts[header]}" if counts[header] > 1 else header)
    return new_headers

@st.cache_data(ttl=600)
def load_data_from_sheets(_gc: gspread.Client):
    try:
        sh = _gc.open_by_key(GOOGLE_SHEET_ID)
        worksheets = sh.worksheets()
        data_frames = {}
        for ws in worksheets:
            if ws.title == "LISTAS" or ws.title not in VISTA_COLUMNAS_POR_HOJA: continue
            data = ws.get_all_values()
            if not data: continue
            
            headers = _clean_headers(data[0])
            rows = data[1:]
            df_full = pl.DataFrame(rows, schema=headers, orient="row")
            
            col_vista = [c for c in VISTA_COLUMNAS_POR_HOJA.get(ws.title, []) if c in df_full.columns]
            data_frames[ws.title] = {"full": df_full, "view": df_full.select(col_vista)}
        return data_frames
    except Exception as e:
        st.error(f"Error al cargar datos: {e}")
        return None

# --- MAIN APP ---
def main():
    st.title("SECCION PERSONAL - CPF III")

    gc = get_gspread_client()
    if not gc: st.stop()

    sheet_data = load_data_from_sheets(gc)
    if not sheet_data:
        st.error("Fallo al cargar datos.")
        st.stop()

    sheet_names = list(sheet_data.keys())
    if not sheet_names:
        st.warning("No hay hojas disponibles.")
        return

    # --- NUEVO SELECTOR MULTIPLE ---
    st.markdown("### Selección de Hojas de Trabajo")
    selected_sheets = st.multiselect(
        "Selecciona hasta 2 hojas para visualizar simultáneamente:",
        options=sheet_names,
        default=[sheet_names[0]] if sheet_names else None,
        max_selections=2,
        key="multi_sheet_selector"
    )
    st.markdown("---")

    if not selected_sheets:
        st.info("👆 Por favor, selecciona al menos una hoja arriba.")
        return

    # --- BUCLE PRINCIPAL: Renderizar cada hoja seleccionada ---
    for sheet_name in selected_sheets:
        
        # Inicializar estado para esta hoja específica
        init_sheet_state(sheet_name)
        current_mode = get_sheet_mode(sheet_name)
        
        # Contenedor visual para separar las hojas
        with st.container():
            # Encabezado con color distintivo o separador
            st.markdown(f"## 📂 Hoja: `{sheet_name}`")
            
            df_full = sheet_data[sheet_name]["full"]
            df_view = sheet_data[sheet_name]["view"]
            all_columns = df_full.columns # Polars columns list
            
            # --- LÓGICA DE MODOS POR HOJA ---
            if current_mode == "add":
                show_add_form(gc, sheet_name, all_columns, load_data_from_sheets.clear)
            
            elif current_mode == "edit":
                row_data = get_sheet_edit_data(sheet_name)
                if row_data:
                    show_edit_form(gc, row_data, sheet_name, all_columns, load_data_from_sheets.clear)
                else:
                    st.error("Error de estado: No hay datos para editar.")
                    set_sheet_mode(sheet_name, "view")
                    st.rerun()
            
            else: # MODO VISTA (Tabla y Filtros)
                
                # Botonera de la hoja
                col_actions, col_reload = st.columns([0.8, 0.2])
                with col_actions:
                    if st.button(f"➕ Nuevo Registro en {sheet_name}", key=f"btn_add_{sheet_name}"):
                        set_sheet_mode(sheet_name, "add")
                        st.rerun()
                with col_reload:
                    if st.button("🔄 Recargar", key=f"btn_reload_{sheet_name}"):
                        load_data_from_sheets.clear()
                        st.rerun()

                # Filtros (Namespace único por hoja)
                df_filtered = df_view.clone()
                with st.expander(f"🔍 Filtros para {sheet_name}", expanded=False):
                    text_cols = [c for c in df_filtered.columns if df_filtered[c].dtype == pl.String]
                    
                    sel_cols = st.multiselect("Columnas:", text_cols, default=text_cols[:2] if len(text_cols)>1 else text_cols, key=f"cols_{sheet_name}")
                    cond = st.selectbox("Condición:", ["Contiene texto", "Celda Vacía", "Celda No Vacía"], key=f"cond_{sheet_name}")
                    
                    term = ""
                    if cond == "Contiene texto":
                        term = st.text_input("Buscar:", key=f"term_{sheet_name}")

                    if sel_cols:
                        if cond == "Celda Vacía":
                            expr = [(pl.col(c).is_null()) | (pl.col(c) == "") for c in sel_cols]
                            df_filtered = df_filtered.filter(pl.any_horizontal(expr))
                        elif cond == "Celda No Vacía":
                            expr = [(pl.col(c).is_not_null()) & (pl.col(c) != "") for c in sel_cols]
                            df_filtered = df_filtered.filter(pl.any_horizontal(expr))
                        elif term:
                            expr = [pl.col(c).fill_null("").str.contains(f"(?i){re.escape(term)}") for c in sel_cols]
                            df_filtered = df_filtered.filter(pl.any_horizontal(expr))

                # Estadísticas en Sidebar (Acumulativas)
                with st.sidebar:
                    st.markdown(f"**{sheet_name}**")
                    st.caption(f"Filas: {df_filtered.height} / {df_full.height}")
                    st.divider()

                # Tabla
                st.write(f"Mostrando **{df_filtered.height}** filas.")
                selection = st.dataframe(
                    df_filtered,
                    selection_mode="single-row",
                    on_select="rerun",
                    hide_index=True,
                    width='stretch',
                    key=f"grid_{sheet_name}"
                )

                # Acción de Selección
                if selection.selection["rows"]:
                    try:
                        sel_idx = selection.selection["rows"][0]
                        sel_row_view = df_filtered.row(sel_idx, named=True)
                        id_val = sel_row_view[df_view.columns[0]] # ID usando primera columna vista
                        
                        # Buscar en full
                        # Convertir a string para asegurar match
                        full_row = df_full.filter(pl.col(df_view.columns[0]).cast(pl.Utf8) == str(id_val))
                        
                        if not full_row.is_empty():
                            full_row_dict = full_row.row(0, named=True)
                            
                            st.info(f"Fila seleccionada: {id_val}")
                            if st.button(f"✏️ Editar este registro ({sheet_name})", key=f"btn_edit_sel_{sheet_name}"):
                                set_sheet_mode(sheet_name, "edit", full_row_dict)
                                st.rerun()

                            # Copiado Manual
                            if sheet_name in BOTONES_COPIADO_POR_HOJA:
                                st.caption("Datos para copiar:")
                                b_cols = st.columns(3)
                                idx = 0
                                for lbl, c_name in BOTONES_COPIADO_POR_HOJA[sheet_name].items():
                                    val = str(full_row_dict.get(c_name, ""))
                                    # Key única incluyendo ID y Sheet para refresco correcto
                                    b_cols[idx].text_input(lbl, value=val, key=f"copy_{sheet_name}_{c_name}_{id_val}")
                                    idx = (idx + 1) % 3

                    except Exception as e:
                        st.error(f"Error al seleccionar: {e}")

        st.divider() # Separador visual entre hojas

if __name__ == "__main__":
    main()
