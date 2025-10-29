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
        # --- NUEVO: Limpiar caracteres inválidos ---
        # Reemplaza espacios no separables (comunes al copiar/pegar) por espacios normales
        creds_json_str = creds_json_str.replace('\u00a0', ' ')
        # --- FIN NUEVO ---

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
    new_headers = []
    counts = {}
    for header in headers:
        counts[header] = counts.get(header, 0) + 1
        if counts[header] > 1:
            new_headers.append(f"{header}_{counts[header]}")
        else:
            new_headers.append(header)
    return new_headers

# --- FUNCIÓN PRINCIPAL DE CARGA DE DATOS (Actualizada) ---
@st.cache_data(ttl=600)  # Caching para evitar recargar cada 10 minutos
def load_data_from_sheets():
    """
    Se conecta a Google Sheets y carga todas las hojas (worksheets)
    en un diccionario de DataFrames de Polars.
    """
    try:
        gc = get_gspread_client()
        if not gc:
            return None # Fallo en la autenticación
            
        # --- CAMBIO IMPORTANTE: Abrir por ID ---
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
                continue # Saltar esta hoja
            # --- FIN DEL FILTRO ---

            data = ws.get_all_values()
            
            if not data:
                # st.warning(f"La hoja '{ws.title}' está vacía. Omitiendo.")
                continue

            # La primera fila son los encabezados (limpiados)
            headers = _clean_headers(data[0])
            rows = data[1:]
            
            # Crear el DataFrame de Polars
            df_full = pl.DataFrame(rows, schema=headers, orient="row")
            
            # Crear la vista filtrada (si existe en el diccionario)
            columnas_vista = VISTA_COLUMNAS_POR_HOJA.get(ws.title)
            
            # Verificar que todas las columnas de la vista existan en el df_full
            columnas_validas = [col for col in columnas_vista if col in df_full.columns]
            
            df_view = df_full.select(columnas_validas)
            
            # Guardar ambos dataframes
            data_frames[ws.title] = {
                "full": df_full,
                "view": df_view
            }
            
        return data_frames
        
    except gspread.exceptions.SpreadsheetNotFound:
        st.error(f"Error: No se encontró la hoja de cálculo con el ID: {GOOGLE_SHEET_ID}. Revisa el ID y que la Service Account tenga permisos.")
        return None
    except Exception as e:
        st.error(f"Ocurrió un error al cargar los datos: {e}")
        return None

# --- FUNCIÓN PARA EL FORMULARIO DE EDICIÓN (Actualizada) ---
def _show_edit_form(row_data, sheet_name, columns):
    """
    Muestra un formulario de edición para la fila seleccionada.
    'row_data' es un diccionario de la fila (de Polars).
    'columns' son todas las columnas del DataFrame 'full'.
    """
    st.header(f"✏️ Editando Registro en: {sheet_name}")
    
    # Usar 'st.session_state' para mantener los cambios del formulario
    if 'form_data' not in st.session_state:
        st.session_state.form_data = row_data
    
    # Crear un formulario
    with st.form(key=f"edit_form_{sheet_name}"):
        form_data_actualizado = {}
        
        # Mostrar un campo de texto para cada columna
        for col in columns:
            valor_actual = st.session_state.form_data.get(col, "")
            # Convertir None a string vacío para st.text_input
            if valor_actual is None:
                valor_actual = ""
            form_data_actualizado[col] = st.text_input(f"**{col}**", value=valor_actual)
            
        submitted = st.form_submit_button("Guardar Cambios en Google Sheets")
        
        if submitted:
            try:
                # Conectar a la hoja específica
                gc = get_gspread_client()
                sh = gc.open_by_key(GOOGLE_SHEET_ID)
                worksheet = sh.worksheet(sheet_name)
                
                # Encontrar la fila que coincida con el ID (primera columna)
                id_column_name = columns[0]
                id_value = form_data_actualizado[id_column_name]
                
                # .find() puede ser lento en hojas grandes, pero es robusto
                cell = worksheet.find(id_value, in_column=1) 
                
                if not cell:
                    st.error(f"Error: No se encontró la fila con ID '{id_value}' para actualizar.")
                    return

                # Convertir el diccionario de datos a una lista en el orden correcto
                row_values = [form_data_actualizado.get(col, "") for col in columns]
                
                # Actualizar la fila completa en Google Sheets
                # Usamos gspread.utils para obtener el rango A1 (ej. "A10:Z10")
                range_to_update = gspread.utils.rowcol_to_a1(cell.row, 1) + ":" + gspread.utils.rowcol_to_a1(cell.row, len(columns))
                worksheet.update(range_to_update, [row_values])
                
                st.success(f"¡Fila (ID: {id_value}) actualizada exitosamente!")
                
                # 1. Limpiar el caché de datos
                load_data_from_sheets.clear()
                # 2. Salir del modo edición
                st.session_state.editing_row = None
                # 3. Limpiar los datos del formulario
                if 'form_data' in st.session_state:
                    del st.session_state.form_data
                # 4. Resetear la selección del dataframe (si existe)
                selection_key = f"df_select_{sheet_name}"
                if selection_key in st.session_state:
                    del st.session_state[selection_key] # Borrar la clave para resetear
                
                # 5. Forzar recarga de la página
                st.rerun()

            except Exception as e:
                st.error(f"Error al guardar los cambios: {e}")

# --- FUNCIÓN PARA AGREGAR REGISTROS (Actualizada) ---
def _show_add_form(sheet_name, all_columns):
    """
    Muestra un formulario para agregar un nuevo registro.
    'all_columns' son todas las columnas del DataFrame 'full'.
    """
    st.header(f"➕ Agregando Nuevo Registro a: {sheet_name}")

    with st.form(key=f"add_form_{sheet_name}"):
        new_row_data = {}
        for col in all_columns:
            new_row_data[col] = st.text_input(f"**{col}**", key=f"add_{col}")

        submitted = st.form_submit_button("Guardar Nuevo Registro")

        if submitted:
            try:
                gc = get_gspread_client()
                sh = gc.open_by_key(GOOGLE_SHEET_ID)
                worksheet = sh.worksheet(sheet_name)

                # Convertir el diccionario a una lista en el orden correcto
                row_values = [new_row_data.get(col, "") for col in all_columns]

                # Agregar la nueva fila al final de la hoja
                worksheet.append_row(row_values)
                
                st.success("¡Nuevo registro agregado exitosamente!")
                
                # 1. Limpiar el caché
                load_data_from_sheets.clear()
                # 2. Salir del modo "Agregar"
                st.session_state.show_add_form = False
                # 3. Forzar recarga
                st.rerun()

            except Exception as e:
                st.error(f"Error al agregar el registro: {e}")

# --- ESTRUCTURA DE LA APP STREAMLIT (Actualizada) ---
def main():
    
    st.title("SECCION PERSONAL - DEPARTEMENTE SECRETARIA CPF III") # Título actualizado

    # Inicializar estado de sesión
    if 'editing_row' not in st.session_state:
        st.session_state.editing_row = None
    if 'show_add_form' not in st.session_state:
        st.session_state.show_add_form = False

    # Cargar los datos (desde el caché o desde Sheets)
    sheet_data = load_data_from_sheets()
    
    # Manejo de error si la carga falla
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
            st.session_state.editing_row = None # Asegurarse de no estar editando
            st.rerun() # Rerun para mostrar el formulario inmediatamente
    # --- FIN CAMBIO 2 ---
        
    st.markdown("---")

    # Lógica para mostrar el formulario de "Agregar"
    if st.session_state.show_add_form:
        all_columns = sheet_data[selected_sheet]["full"].columns
        _show_add_form(selected_sheet, all_columns)
    
    # Lógica para mostrar el formulario de "Editar"
    elif st.session_state.editing_row is not None:
        all_columns = sheet_data[selected_sheet]["full"].columns
        _show_edit_form(st.session_state.editing_row, selected_sheet, all_columns)

    # Vista principal (mostrar la tabla)
    else:
        if selected_sheet in sheet_data:
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
            selection = st.dataframe(
                df_filtered,
                on_select="rerun",
                selection_mode="single-row",
                hide_index=True,
                width='stretch',
                key=selection_key
            )

            # --- LÓGICA DE SELECCIÓN (Editar y Copiar) ---
            if selection.selection["rows"]:
                selected_row_index = selection.selection["rows"][0]
                
                # Obtener la fila seleccionada del dataframe filtrado
                selected_row_view = df_filtered.row(selected_row_index, named=True)
                
                # --- Encontrar la fila completa (full) correspondiente ---
                # Asumimos que la primera columna de la vista es un ID único
                id_column_name = df_view.columns[0]
                id_value = selected_row_view[id_column_name]
                
                # Buscar en el dataframe completo (df_full)
                selected_row_full = df_full.filter(pl.col(id_column_name) == id_value)
                
                if not selected_row_full.is_empty():
                    selected_row_full_dict = selected_row_full.row(0, named=True)

                    # --- ZONA DE BOTONES DE ACCIÓN ---
                    st.markdown("---")
                    
                    # --- 1. Botón de Edición ---
                    if st.button("✏️ Editar Fila Seleccionada"):
                        st.session_state.editing_row = selected_row_full_dict
                        st.rerun()
                    
                    # --- 2. Botones de Copiado (si existen) ---
                    if selected_sheet in BOTONES_COPIADO_POR_HOJA:
                        st.subheader("Copiar Contenido de Fila")
                        
                        botones_config = BOTONES_COPIADO_POR_HOJA[selected_sheet]
                        max_cols = 3 # Máximo de botones por fila
                        cols = st.columns(max_cols)
                        col_index = 0
                        
                        for label, col_name in botones_config.items():
                            if col_name in selected_row_full_dict:
                                valor = selected_row_full_dict[col_name]
                                # Convertir None a string vacío
                                if valor is None:
                                    valor = ""
                                
                                # Usar 'st.text_area' como un "copy box"
                                cols[col_index].text_area(label, value=valor, height=50, key=f"copy_{label}_{selected_row_index}")
                                
                                # Moverse a la siguiente columna del layout
                                col_index = (col_index + 1) % max_cols
                            
                            else:
                                st.warning(f"La columna '{col_name}' (para el botón '{label}') no se encontró en la hoja '{selected_sheet}'.")

                else:
                    st.warning("No se pudo encontrar la fila completa para editar. Revisa que la primera columna sea un ID único.")
            
if __name__ == "__main__":
    main()

