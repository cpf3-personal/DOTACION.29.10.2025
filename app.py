import streamlit as st
import polars as pl
import gspread
import gspread.utils # Necesario para la actualización de celdas
import re # Importar regex para filtros
import json # Para las credenciales de SA
import os # Para las variables de entorno
from dotenv import load_dotenv # Para cargar el .env local

# Cargar variables de entorno locales (del archivo .env)
# Esto solo se usa para pruebas locales, Streamlit Cloud usa st.secrets
load_dotenv()

# --- CONFIGURACIÓN ---
st.set_page_config(layout="wide") # Poner layout ancho

# --- CAMBIO IMPORTANTE: Usar el ID de la Hoja ---
# Extraído de tu URL: https://docs.google.com/spreadsheets/d/1UOA2HhylbW2w5S5EyfAJ-OP0zzlcx7cbYVk1QJedit/...
GOOGLE_SHEET_ID = "1UOA2HHY1b2W56Ei4YG32sYVJ-0P0zzJcx1C7bBYVK1Q"
# --- FIN DEL CAMBIO ---

# --- ÁMBITOS (SCOPES) REQUERIDOS ---
SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive.file"
]

# --- DICCIONARIOS (sin cambios) ---
VISTA_COLUMNAS_POR_HOJA = {
    "DOTACION": ["N°", "COD", "GRADO", "APELLIDOS", "NOMBRES","CED.", "SITUACION", "MASC / FEM", "INGRESO", "DISP. ING.", "FECHA DISP. ING.", "FECHA ING. C.P.F.NOA", "DISP.", "FECHA DE LA DISP.", "FECHA NAC.", "EDAD", "D.N.I.", "C.U.I.L.", "ESTADO CIVIL", "FECHA CASAM.", "JEFATURA / DIRECCION", "DEPARTAMENTO / DIVISION SECCION", "FUNCION", "ORDEN INTERNA", "A PARTIR DE", "EXPEDIENTE DE FUNCION", "DEST. ANT. UNIDAD", "ESCALAFON", "PROFESION", "DOMICILIO", "LOCALIDAD", "PROVINCIA", "TELEFONO", "USUARIO G.D.E.", "CORREO ELEC", "REPARTICIÓN", "SECTOR", "JERARQUIA"],
    "FUNCIONES": ["EXPEDIENTE", "GRADO", "NOMBRES Y APELLIDOS", "CRED.", "JEFATURA / DIRECCION", "DIVISION / DEPARTAMENTO", "SECCION", "CARGO", "FUNCION DEL B.P.N 700", "ORDEN INTERNA", "A PARTIR DE", "CAMBIO DE DEPENDENCIA (SI o NO)", "TITULAR – INTERINO - A CARGO", "HORARIO Y TURNO"],
    "SANCION" : ["EXPEDIENTE", "GRADO", "NOMBRES Y APELLIDOS" , "CRED.", "FECHA DE LA FALTA", "FECHA DE NOTIFICACION", "ART.", "TIPO DE SANCION", "DIAS DE ARRESTO"],
    "DOMICILIOS" : ["EXPEDIENTE", "GRADO", "NOMBRES Y APELLIDOS" , "CRED.", "FECHA DE CAMBIO", "DOMICILIO", "LOCALIDAD", "PROVINCIA" ],
    "CURSOS" : ["EXPEDIENTE", "GRADO", "NOMBRES Y APELLIDOS" , "CRED.", "CURSO"],
    "SOLICITUD DE PASES" : ["EXPEDIENTE", "GRADO", "NOMBRES Y APELLIDOS" , "CRED.", "TIPO DE PASE", "NOMBRE DE LA PERMUTA", "DESTINO"], 
    "DISPONIBILidad" : ["EXPEDIENTE", "GRADO", "NOMBRES Y APELLIDOS" , "CRED.",  "DESDE", "DIAS", "FINALIZACION"],     
    "LICENCIAS": ["EXPEDIENTE",  "GRADO", "NOMBRE Y APELLIDO", "CRED.", "TIPO DE LIC", "DIAS", "DESDE", "HASTA", "AÑO", "PASAJES" , "DIAS POR VIAJE", "REINTEGRO", "LUGAR" ],
    "LACTANCIA": ["EXPEDIENTE", "GRADO", "NOMBRE Y APELLIDO", "CRED.", "NOMBRE COMPLETO HIJO/A", "FECHA DE NACIMIENTO", "EXPEDIENTE DONDE LO INFORMO", "FECHAS", "PRORROGA FECHA"],
    "PARTE DE ENFERMO" : ["EXPEDIENTE", "GRADO", "NOMBRE Y APELLIDO", "CRED.", "AÑO", "INICIO", "DESDE (ULTIMO CERTIFICADO)", "CANTIDAD DE DIAS (ULTIMO CERTIFICADO)", "HASTA (ULTIMO CERTIFICADO)", "FINALIZACION", "CUMPLE 1528??", "DIAS DE INASISTENCIA JUSTIFICADO", "DIAS DE INASISTENCIAS A HOY", "CANTIDAD DE DIAS ANTERIORES AL TRAMITE", "CODIGO DE AFECC.", "DIVISION" ],
    "PARTE DE ASISTENCIA FAMILIAR" : ["EXPEDIENTE", "GRADO", "NOMBRE Y APELLIDO", "CRED.", "AÑO", "INICIO", "DESDE (ULTIMO CERTIFICADO)", "CANTIDAD DE DIAS (ULTIMO CERTIFICADO)", "HASTA (ULTIMO CERTIFICADO)", "FINALIZACION", "CUMPLE 1528??", "DIAS DE INASISTENCIA JUSTIFICADO", "DIAS DE INASISTENCIAS A HOY", "CANTIDAD DE DIAS ANTERIORES AL TRAMITE", "CODIGO DE AFECC.", "DIVISION" ],
    "ACCIDENTE DE SERVICIO" : ["EXPEDIENTE", "GRADO", "NOMBRE Y APELLIDO", "CRED.", "AÑO", "INICIO", "DESDE", "CANTIDAD DE DIAS (ULTIMO CERTIFICADO)", "HASTA", "FINALIZACION", "DIVISION", "OBSERVACION"],
    "CERTIFICADOS MEDICOS": ["GRADO", "Nombre y Apellido", "CREDENCIAL","SELECCIONA EL TIPO DE TRÁMITE", "CANTIDAD DE DIAS DE REPOSO", "INGRESA EL CERTIFICADO", "DIAGNOSTICO", "NOMBRE Y APELLIDO DEL MÉDICO", "ESPECIALIDAD DEL MÉDICO", "MATRÍCULA DEL MÉDICO", "N° de TELÉFONO DE CONTACTO", "PARENTESCO CON EL FAMILIAR", "NOMBRES Y APELLIDOS DEL FAMILIAR", "FECHA DE NACIMIENTO", "FECHA DE CASAMIENTO (solo para el personal casado)"], 
    "NOTA DE COMISION MEDICA" : ["NOTA DE D.RR.HH.", "FECHA DE NOTA DE D.RR.HH.", "TEXTO NOTIFICABLE DE LA NOTA", "CREDENCIAL", "EXPEDIENTE", "RELACIONADO A . . .", "FECHA DE EVALUACION VIRTUAL", "FECHA DE EVALUACION PRESENCIAL", "FECHA DE REINTEGRO", "1° FECHA DE EVALUACION VIRTUAL", "2° FECHA DE EVALUACIÓN PRESENCIAL", "GRADO", "APELLIDO Y NOMBRE"],
    "IMPUNTUALIDADES": ["EXPEDIENTE", "GRADO", "NOMBRES Y APELLIDOS" , "CRED.", "FECHA", "HORA DE DEBIA INGRESAR", "HORA QUE INGRESO", "AÑO", "N° DE IMPUNTUALIDAD"],
    "COMPLEMENTO DE HABERES" : ["EXPEDIENTE", "GRADO", "NOMBRES Y APELLIDOS" , "CRED.", "TIPO"],
    "OFICIOS" : ["EXPEDIENTE", "GRADO", "NOMBRES Y APELLIDOS", "CRED.", "PICU_OFICIO", "FECHA del OFICIO"],
    "NOTAS DAI" : ["NOTA DAI", "GRADO", "NOMBRES Y APELLIDOS", "CRED.", "PICU_NOTA_DAI", "FECHA de NOTA DAI"],
    "INASISTENCIAS" : ["EXPEDIENTE", "GRADO", "NOMBRES Y APELLIDOS", "CRED.", "FECHA DE LA FALTA", "MOTIVO"],
    "MESA DE ENTRADA": ["Número Expediente", "Código Trámite", "Descripción del Trámite", "Motivo"],
}
BOTONES_COPIADO_POR_HOJA = {
    "DOTACION": { "Copiar Apellido": "APELLIDOS", "Copiar Nombre": "NOMBRES", "Copiar Grado": "GRADO" }, # Corregido APELLIDO->APELLIDOS, NOMBRE->NOMBRES
    "LICENCIAS": { "EXPEDIENTE": "EXPEDIENTE","Copiar Expediente": "EXPEDIENTE", "Copiar Nombre y Apellido": "NOMBRE Y APELLIDO", "Copiar Días": "DIAS" },
    "IMPUNTUALIDADES": {"EXPEDIENTE": "EXPEDiente", "SITUACION DE REVISTA IMPUNTUALIDAD": "SITUACION DE REVISTA IMPUNTUALIDAD", "ORDENATIVA DE IMPUNTUALIDAD": "ORDENATIVA DE IMPUNTUALIDAD", "ARCHIVO DE IMPUNTUALIDAD": "ARCHIVO DE IMPUNTUALIDAD" },
    "FUNCIONES": { "EXPEDIENTE": "EXPEDIENTE", "ORDENATIVA": "ORDENATIVA", "ARTICULO": "ARTICULO", "ELEVACION": "ELEVACION", "ARCHIVO": "ARCHIVO", "ANOTACION D.L.P." : "ANOTACION D.L.P." },
    "OFICIOS": { "EXPEDIENTE": "EXPEDIENTE", "SITUACION DE REVISTA OFICIO": "SITUACION DE REVISTA OFICIO", "SOLICITUD DE NOTIFICACION": "SOLICITUD DE NOTIFICACION", "ELEVACION DE NOTIFICACION": "ELEVACION DE NOTIFICACION", "ARCHIVO": "ARCHIVO", "ANOTACION D.L.P." : "ANOTACION D.L.P." }
}
# --- FIN DICCIONARIOS ---


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
        # Convertir el string JSON a un diccionario de Python
        creds_dict = json.loads(creds_json_str)
        
        # --- CAMBIO 1: Cartel de autenticación eliminado ---
        # st.info(f"Intentando autenticar con la cuenta de servicio: {creds_dict.get('client_email')}")
        # --- FIN CAMBIO 1 ---

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

# --- FUNCIÓN AUXILIAR (sin cambios) ---
def _clean_headers(headers):
    """Limpia los encabezados duplicados añadiendo sufijos."""
    counts = {}
    new_headers = []
    for header in headers:
        if not header: # Si el encabezado está vacío
            header = "COLUMNA_VACIA"
            
        if header in counts:
            counts[header] += 1
            new_headers.append(f"{header}_{counts[header]}")
        else:
            counts[header] = 1
            new_headers.append(header)
    return new_headers

# --- FUNCIÓN PRINCIPAL DE CARGA DE DATOS (Actualizada) ---
@st.cache_data(ttl=600)  # Caching para evitar recargar cada 10 minutos
def load_data_from_sheets():
    """
    Autentica la cuenta de servicio, se conecta a la hoja de cálculo
    y lee SOLAMENTE las pestañas definidas en VISTA_COLUMNAS_POR_HOJA.
    
    Devuelve un dict donde cada clave es el nombre de la hoja,
    y el valor es otro dict: {"full": df_full, "view": df_view}
    """
    try:
        # --- CAMBIO DE AUTENTICACIÓN ---
        # Autenticación segura usando la nueva función
        gc = get_gspread_client()
        if not gc:
             st.stop() # Detener si la autenticación falló
        # --- FIN CAMBIO ---
        
        # --- CAMBIO IMPORTANTE: Abrir por ID ---
        # Abrir el libro de Sheets por su ID único
        sh = gc.open_by_key(GOOGLE_SHEET_ID)
        # --- FIN DEL CAMBIO ---
        
        # Obtener todas las hojas (worksheets)
        worksheets = sh.worksheets()
        
        # Diccionario para almacenar los DataFrames de Polars
        data_frames = {}
        
        # Iterar sobre cada hoja y convertirla a Polars DataFrame
        for ws in worksheets:
            
            # --- ¡NUEVO FILTRO! ---
            # Si el título de la hoja no está en nuestro diccionario, la ignoramos
            if ws.title not in VISTA_COLUMNAS_POR_HOJA:
                continue # Saltar a la siguiente hoja
            # --- FIN DEL FILTRO ---
            
            # Obtener todos los valores como lista de listas
            data = ws.get_all_values()
            
            if not data:
                st.warning(f"La hoja '{ws.title}' está vacía. Omitiendo.")
                continue

            # La primera fila son los encabezados
            headers = _clean_headers(data[0]) # Limpiar encabezados
            rows = data[1:]
            
            # Crear el DataFrame de Polars
            df_full = pl.DataFrame(rows, schema=headers, orient="row")
            
            # --- Lógica de Vistas de Columnas ---
            # Ahora sabemos que la clave existe en el diccionario
            columnas_vista = VISTA_COLUMNAS_POR_HOJA[ws.title]
            
            # Filtrar solo las columnas que existen en el df_full
            columnas_existentes = [col for col in columnas_vista if col in df_full.columns]
            df_view = df_full.select(columnas_existentes)
                
            data_frames[ws.title] = {
                "full": df_full, # El DataFrame con todos los datos
                "view": df_view  # El DataFrame solo con columnas seleccionadas
            }
            
        return data_frames
        
    except gspread.exceptions.SpreadsheetNotFound:
        st.error(f"Error: No se encontró la hoja de cálculo con el ID: {GOOGLE_SHEET_ID}. Revisa el ID y que la Service Account tenga permisos.")
        return None
    except Exception as e:
        # Captura el error específico de Polars u otros
        st.error(f"Ocurrió un error al cargar los datos: {e}")
        return None

# --- FUNCIÓN PARA EL FORMULARIO DE EDICIÓN (Actualizada) ---
def _show_edit_form(row_data, sheet_name, columns):
    """
    Muestra un formulario pre-llenado para editar una fila seleccionada.
    'row_data' es un dict de la fila completa.
    'columns' es la lista de todas las columnas (para mantener el orden).
    """
    st.subheader(f"Editando Fila en: {sheet_name}")
    
    # Asumir que la primera columna es el ID único
    if not columns:
        st.error("No se pueden editar filas, no se detectaron columnas.")
        return
        
    id_column_name = columns[0]
    id_value = row_data.get(id_column_name, "ID_NO_ENCONTRADO")
    st.info(f"Editando registro con **{id_column_name}**: {id_value}")
    
    with st.form(key=f"edit_form_{sheet_name}"):
        edited_data = {}
        # Crear un campo de texto para cada columna
        for col in columns:
            default_value = str(row_data.get(col, ""))
            edited_data[col] = st.text_input(f"{col}", value=default_value, key=f"edit_{col}")
        
        submitted = st.form_submit_button("Guardar Cambios en Google Sheets")

    if submitted:
        try:
            with st.spinner("Conectando y guardando en Google Sheets..."):
                # 1. Preparar los datos actualizados (lista en el orden correcto)
                updated_row_list = [edited_data[col] for col in columns]
                
                # 2. --- CAMBIO DE AUTENTICACIÓN ---
                gc = get_gspread_client()
                if not gc:
                    st.stop()
                # --- FIN CAMBIO ---

                # --- CAMBIO IMPORTANTE: Abrir por ID ---
                sh = gc.open_by_key(GOOGLE_SHEET_ID)
                # --- FIN DEL CAMBIO ---
                worksheet = sh.worksheet(sheet_name)
                
                # 3. Encontrar la fila por el ID (valor de la primera columna)
                cell = worksheet.find(id_value, in_column=1) # Buscar en columna A
                
                if not cell:
                    st.error(f"Error: No se encontró la fila con ID {id_value} para actualizar.")
                    return

                # 4. Actualizar la fila
                start_cell = gspread.utils.rowcol_to_a1(cell.row, 1)
                end_cell = gspread.utils.rowcol_to_a1(cell.row, len(updated_row_list))
                range_to_update = f"{start_cell}:{end_cell}"
                
                worksheet.update(range_to_update, [updated_row_list], value_input_option='USER_ENTERED')

            st.success(f"¡Fila (ID: {id_value}) actualizada exitosamente!")
            
            # 5. Limpiar el caché y el estado
            load_data_from_sheets.clear()
            st.session_state.form_submitted_successfully = sheet_name
            
            # 6. Forzar recarga de la página
            st.rerun()

        except Exception as e:
            st.error(f"Error al guardar los cambios: {e}")

# --- FUNCIÓN PARA AGREGAR REGISTROS (Actualizada) ---
def _show_add_form(sheet_name, all_columns):
    """Muestra un formulario para agregar un nuevo registro a la hoja."""
    st.subheader(f"Agregar Nuevo Registro a: {sheet_name}")
    
    with st.form(key=f"add_form_{sheet_name}", clear_on_submit=True):
        new_record_data = {}
        # Crear un campo de texto para cada columna
        for col in all_columns:
            new_record_data[col] = st.text_input(f"{col}", key=f"add_{col}")
        
        submitted = st.form_submit_button("Guardar Nuevo Registro")

        if submitted:
            try:
                with st.spinner("Agregando registro a Google Sheets..."):
                    # 1. --- CAMBIO DE AUTENTICACIÓN ---
                    gc = get_gspread_client()
                    if not gc:
                        st.stop()
                    # --- FIN CAMBIO ---
                    
                    # --- CAMBIO IMPORTANTE: Abrir por ID ---
                    sh = gc.open_by_key(GOOGLE_SHEET_ID)
                    # --- FIN DEL CAMBIO ---
                    worksheet = sh.worksheet(sheet_name)
                    
                    # 2. Convertir el dict a una lista en el orden correcto
                    new_row_list = [new_record_data[col] for col in all_columns]
                    
                    # 3. Añadir la fila
                    worksheet.append_row(new_row_list, value_input_option='USER_ENTERED')
                    
                st.success(f"¡Registro agregado a '{sheet_name}' exitosamente!")
                
                # 4. Limpiar caché y resetear estado
                load_data_from_sheets.clear()
                if "show_add_form" in st.session_state:
                     del st.session_state.show_add_form # Ocultar el formulario
                
                # 5. Forzar recarga de la página
                st.rerun()

            except Exception as e:
                st.error(f"Error al agregar el registro: {e}")

# --- ESTRUCTURA DE LA APP STREAMLIT (Actualizada) ---
def main():
    st.title("SECCION PERSONAL - DEPARTEMENTE SECRETARIA CPF III")
    
    # Cargar los datos (con spinner para mejor feedback)
    # --- CAMBIO: Mensajes de carga eliminados ---
    sheet_data = load_data_from_sheets()
    # --- FIN CAMBIO ---
    
    if sheet_data is None:
        st.error("Fallo al cargar los datos iniciales. Revisa la conexión o las credenciales.")
        st.stop() # Detener la ejecución si hay un error
    
    # Selector para elegir la hoja a visualizar
    sheet_names = list(sheet_data.keys())
    
    if not sheet_names:
        st.warning("El libro de Sheets está vacío o hubo un problema al leer las hojas.")
        return
        
    # --- CAMBIO 2: Botón "Agregar" movido a columnas ---
    col_select, col_add_btn = st.columns([0.7, 0.3]) # 70% para el selector, 30% para el botón
    
    with col_select:
        selected_sheet = st.selectbox("Selecciona la hoja a visualizar:", sheet_names)
    
    with col_add_btn:
        # CSS para alinear el botón a la derecha
        st.markdown("""
            <style>
            div[data-testid="stVerticalBlock"] > div:has(div[data-testid="stColumns"]) > div[data-testid="stVerticalBlock"] > div[data-testid="stButton"] button {
                float: right;
                width: 100%;
            }
            </style>
        """, unsafe_allow_html=True)
        if st.button(f"➕ Agregar Nuevo Registro", key=f"add_new_{selected_sheet}"):
            st.session_state.show_add_form = True # Activa el modo "Agregar"
            st.rerun() # Rerun para mostrar el formulario inmediatamente
    # --- FIN CAMBIO 2 ---
        
    st.markdown("---")

    # Lógica para mostrar el formulario de "Agregar"
    if "show_add_form" in st.session_state and st.session_state.show_add_form:
        if selected_sheet in sheet_data:
            df_full = sheet_data[selected_sheet]["full"]
            _show_add_form(selected_sheet, df_full.columns)
    
    # La vista principal (tabla, filtros, edición) solo se muestra si NO estamos agregando
    else:
        # --- Limpiar selección después de editar ---
        if "form_submitted_successfully" in st.session_state and st.session_state.form_submitted_successfully == selected_sheet:
            selection_key = f"df_select_{selected_sheet}"
            if selection_key in st.session_state:
                del st.session_state[selection_key]
            del st.session_state.form_submitted_successfully # Resetear la bandera

        # Mostrar el DataFrame de Polars
        if selected_sheet in sheet_data:
            
            # Obtener los dataframes full y view del dict
            df_full = sheet_data[selected_sheet]["full"]
            df_view = sheet_data[selected_sheet]["view"]
            
            # Clonar para no modificar el caché
            df_filtered = df_view.clone()
            
            st.header(f"Datos de la Hoja: **{selected_sheet}**")
            st.write(f"Mostrando {df_filtered.height} de {df_full.height} filas.")
            
            # --- CAMBIO 3: Botón de Recarga y Filtros REORDENADOS ---
            if st.button("Recargar Datos"):
                load_data_from_sheets.clear()
                st.toast("Forzando recarga de datos...")
                st.rerun()

            # Los filtros ahora están DESPUÉS del botón de recarga
            with st.expander("Filtros de Búsqueda"):
                # Obtener solo columnas de texto (String) para filtrar
                text_columns = [col for col in df_filtered.columns if df_filtered[col].dtype == pl.String]
                
                selected_filter_columns = st.multiselect(
                    "Selecciona columnas para filtrar:",
                    options=text_columns,
                    default=text_columns[:3] # Default a las primeras 3
                )
                
                filter_expressions = []
                
                if selected_filter_columns:
                    # Usamos regex para que sea insensible a mayúsculas
                    search_term = st.text_input(f"Buscar en columnas seleccionadas (contiene):", key=f"filter_{selected_sheet}_all")
                    if search_term:
                        # Crear una expresión de filtro (OR) para cada columna seleccionada
                        col_expressions = []
                        for col in selected_filter_columns:
                            col_expressions.append(
                                pl.col(col).fill_null("").str.contains(f"(?i){re.escape(search_term)}")
                            )
                        # Combinar las expresiones con OR (pl.any_horizontal)
                        filter_expressions.append(pl.any_horizontal(col_expressions))

                
                if filter_expressions:
                    # Aplicar todos los filtros (AND)
                    df_filtered = df_filtered.filter(pl.all_horizontal(filter_expressions))
            # --- FIN CAMBIO 3 ---

            # Habilitar selección en el DataFrame
            selection_key = f"df_select_{selected_sheet}"
            
            st.dataframe(
                df_filtered,
                width='stretch', # Usar todo el ancho
                hide_index=True,
                # Configuración para la selección
                on_select="rerun",
                selection_mode="single-row",
                key=selection_key
            )
            
            # Lógica para mostrar el formulario de edición
            if selection_key in st.session_state and st.session_state[selection_key].selection.rows:
                
                # Obtener el índice de la fila seleccionada (del dataframe filtrado)
                selected_index = st.session_state[selection_key].selection.rows[0]
                
                # Obtener los datos de esa fila (solo columnas visibles)
                selected_row_data_filtered = df_filtered.row(selected_index, named=True)
                
                # LÓGICA PARA OBTENER DATOS COMPLETOS
                if not df_filtered.columns:
                    st.error("Error: No hay columnas para obtener ID.")
                    return

                unique_id_col_visible = df_filtered.columns[0]
                unique_id_val = selected_row_data_filtered[unique_id_col_visible]
                
                # Encontrar la fila completa en el DataFrame original (df_full)
                full_row_data_list = df_full.filter(pl.col(unique_id_col_visible) == unique_id_val)
                
                if full_row_data_list.height == 0:
                    st.error(f"Error: No se pudo encontrar la fila completa con ID {unique_id_val} para editar.")
                    return
                
                selected_row_data_full = full_row_data_list.row(0, named=True)
                
                # Lógica para mostrar botones de copiado
                buttons_config = BOTONES_COPIADO_POR_HOJA.get(selected_sheet)
                
                if buttons_config:
                    st.subheader("Copiar Contenido de Fila")
                    st.markdown("---")
                    
                    max_cols = 3
                    cols = st.columns(max_cols)
                    col_index = 0
                    
                    for button_label, column_name in buttons_config.items():
                        
                        current_col = cols[col_index]
                        
                        if column_name not in selected_row_data_full:
                            with current_col:
                                st.warning(f"No se encontró la columna '{column_name}' (Botón: '{button_label}'). Revisa los diccionarios.")
                        else:
                            value_to_copy = selected_row_data_full[column_name]
                            
                            with current_col:
                                st.caption(f"{button_label}:")
                                st.code(value_to_copy if value_to_copy else " ", language=None)
                        
                        col_index = (col_index + 1) % max_cols

                    st.markdown("---")
                
                # Llamar a la función que muestra el formulario de edición
                _show_edit_form(
                    selected_row_data_full,
                    selected_sheet, 
                    df_full.columns
                )
    
if __name__ == "__main__":
    main()


