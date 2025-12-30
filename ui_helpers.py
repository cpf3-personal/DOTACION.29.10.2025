import streamlit as st
import gspread
from datetime import datetime, time, date
from config import FORM_CONFIG, GOOGLE_SHEET_ID, validate_data # Importar la config

# --- FUNCIÓN DE AYUDA PARA INYECTAR CSS Y JS ---

def inject_clipboard_js():
    """
    Inyecta el CSS para los widgets de copiado y el JavaScript 
    para la funcionalidad de copiar al portapapeles.
    """
    st.markdown(
        """
        <style>
        .copy-widget {
            margin-bottom: 10px;
        }
        .copy-widget label {
            display: block;
            font-size: 0.9rem;
            color: #fafafa;
            margin-bottom: 4px;
        }
        .copy-group {
            display: flex;
        }
        .copy-text-display {
            flex-grow: 1;
            padding: 8px 12px;
            font-size: 14px;
            font-family: monospace;
            background-color: #0e1117; /* Fondo oscuro de Streamlit */
            color: #fafafa; /* Texto claro */
            border: 1px solid #31333F;
            border-radius: 8px 0 0 8px; /* Redondeo a la izquierda */
            margin: 0;
            box-sizing: border-box;
            overflow-x: auto; /* Scroll si el texto es muy largo */
            white-space: nowrap;
        }
        .copy-button {
            display: inline-block;
            padding: 8px 12px;
            font-size: 16px; /* Icono más grande */
            line-height: 1.5;
            text-align: center;
            cursor: pointer;
            user-select: none;
            background-color: #31333F; /* Gris oscuro */
            color: #fafafa;
            border: 1px solid #31333F;
            border-left: none; /* Sin borde izquierdo */
            border-radius: 0 8px 8px 0; /* Redondeo a la derecha */
            transition: background-color 0.2s ease, color 0.2s ease;
        }
        .copy-button:hover {
            background-color: #4A4C5A;
        }
        .copy-button:active {
            background-color: #5A5C6A;
        }
        .copy-button-copied {
            background-color: #00A67E; /* Verde éxito */
            color: white;
        }
        </style>
        """,
        unsafe_allow_html=True,
    )
    
    # --- Lógica de JavaScript ---
    # Define la función en la ventana principal para que los botones de markdown puedan llamarla
    st.components.v1.html(
        """
        <script>
        if (!parent.window.copyToClipboard) {
            parent.window.copyToClipboard = function(button, textToCopy) {
                // Usar la API de Portapapeles del Navegador
                navigator.clipboard.writeText(textToCopy).then(function() {
                    // Éxito
                    const originalText = button.innerHTML;
                    button.innerHTML = '✅';
                    button.classList.add('copy-button-copied');
                    
                    setTimeout(function() {
                        button.innerHTML = '📋';
                        button.classList.remove('copy-button-copied');
                    }, 1500);
                }, function(err) {
                    // Error
                    console.error('Error al copiar al portapapeles: ', err);
                    const originalText = button.innerHTML;
                    button.innerHTML = '❌';
                    setTimeout(function() {
                        button.innerHTML = '📋';
                    }, 1500);
                });
            }
        }
        </script>
        """,
        height=0, # No ocupa espacio visual
    )

# --- LÓGICA DE FORMULARIOS (EXTRAÍDA DE APP.PY) ---

def _render_form_fields(gc: gspread.Client, sheet_name: str, existing_data: dict = None):
    """
    Función interna para renderizar los campos de un formulario
    basado en FORM_CONFIG.
    """
    form_config = FORM_CONFIG.get(sheet_name, {})
    if not form_config:
        st.warning(f"No hay configuración de formulario definida para '{sheet_name}' en FORM_CONFIG.")
        return {}

    data_to_submit = {}
    
    # Agrupamos los campos en 3 columnas
    cols = st.columns(3)
    col_index = 0

    for field_name, config in form_config.items():
        field_type = config.get("type", "text")
        
        # Obtener el valor por defecto (si existe)
        default_value = None
        if existing_data:
            default_value = existing_data.get(field_name)

        current_col = cols[col_index]

        # --- Renderizar Widget ---
        try:
            if field_type == "select":
                options_source = config.get("options", [])
                options = []
                
                # Cargar opciones dinámicas desde Google Sheets
                if callable(options_source):
                    options = options_source(gc)
                # Usar opciones estáticas
                elif isinstance(options_source, list):
                    options = options_source
                
                # Manejar el valor por defecto para el selectbox
                default_index = 0
                if default_value and default_value in options:
                    default_index = options.index(default_value)
                
                data_to_submit[field_name] = current_col.selectbox(
                    field_name, 
                    options, 
                    index=default_index,
                    key=f"{sheet_name}_{field_name}"
                )
            
            elif field_type == "date":
                # Convertir string a objeto date si es necesario
                date_value = None
                if isinstance(default_value, str) and default_value:
                    try:
                        date_value = datetime.strptime(default_value, "%Y-%m-%d").date()
                    except (ValueError, TypeError):
                         try:
                             # Probar formato de Sheets DD/MM/YYYY
                             date_value = datetime.strptime(default_value, "%d/%m/%Y").date()
                         except (ValueError, TypeError):
                             date_value = None # Dejar que Streamlit maneje el error
                elif isinstance(default_value, datetime):
                     date_value = default_value.date()
                elif isinstance(default_value, date): # datetime maps to date, but pure date needs this
                     date_value = default_value
                
                if date_value is None:
                    # Usar None si no hay valor o el formato es incorrecto
                     data_to_submit[field_name] = current_col.date_input(
                        field_name, 
                        value=None,
                        key=f"{sheet_name}_{field_name}"
                    )
                else:
                    data_to_submit[field_name] = current_col.date_input(
                        field_name, 
                        value=date_value,
                        key=f"{sheet_name}_{field_name}"
                    )

            elif field_type == "time":
                # Convertir string a objeto time si es necesario
                time_value = None
                if isinstance(default_value, str) and default_value:
                    try:
                        time_value = datetime.strptime(default_value, "%H:%M:%S").time()
                    except (ValueError, TypeError):
                         try:
                             time_value = datetime.strptime(default_value, "%H:%M").time()
                         except (ValueError, TypeError):
                             time_value = None
                
                if time_value is None:
                    data_to_submit[field_name] = current_col.time_input(
                        field_name, 
                        value=None,
                        key=f"{sheet_name}_{field_name}"
                    )
                else:
                     data_to_submit[field_name] = current_col.time_input(
                        field_name, 
                        value=time_value,
                        key=f"{sheet_name}_{field_name}"
                    )

            elif field_type == "text_area":
                data_to_submit[field_name] = current_col.text_area(
                    field_name, 
                    value=str(default_value or ""), 
                    key=f"{sheet_name}_{field_name}"
                )
                
            else: # Default es "text"
                max_chars = config.get("max_chars")
                data_to_submit[field_name] = current_col.text_input(
                    field_name, 
                    value=str(default_value or ""), 
                    max_chars=max_chars,
                    key=f"{sheet_name}_{field_name}"
                )

        except Exception as e:
            st.error(f"Error al renderizar el campo '{field_name}': {e}")
            # Asegurarse de que la llave exista incluso si falla el renderizado
            data_to_submit[field_name] = None

        # Avanzar al siguiente índice de columna
        col_index = (col_index + 1) % 3
        
    return data_to_submit


def show_add_form(gc: gspread.Client, selected_sheet: str, all_columns: list, clear_cache_func):
    """
    Muestra el formulario para agregar un nuevo registro.
    """
    st.subheader(f"➕ Agregar Nuevo Registro a '{selected_sheet}'")
    
    with st.form(key=f"add_form_{selected_sheet}"):
        
        # Renderizar los campos del formulario
        data_to_submit = _render_form_fields(gc, selected_sheet)
        
        st.markdown("---")
        submitted = st.form_submit_button("Guardar Nuevo Registro")

    if submitted:
        # Validar los datos antes de enviar
        is_valid, error_message = validate_data(selected_sheet, data_to_submit)
        
        if not is_valid:
            st.error(f"Error de validación: {error_message}")
            return # Detener el envío

        try:
            with st.spinner("Guardando en Google Sheets..."):
                sh = gc.open_by_key(GOOGLE_SHEET_ID)
                worksheet = sh.worksheet(selected_sheet)
                
                # Convertir todos los valores a string para gspread
                # y asegurarse de que el orden coincide con las columnas
                new_row = []
                for col_name in all_columns:
                    value = data_to_submit.get(col_name)
                    
                    # Formatear fechas y horas a string
                    if isinstance(value, (datetime, time)):
                        value = value.isoformat()
                    elif value is None:
                        value = ""
                    
                    new_row.append(str(value))
                
                worksheet.append_row(new_row, value_input_option='USER_ENTERED')
            
            st.success("¡Registro guardado exitosamente!")
            
            # Limpiar el caché de datos para forzar la recarga
            clear_cache_func()
            
            # Ocultar el formulario
            st.session_state.show_add_form = False
            st.rerun()

        except Exception as e:
            st.error(f"No se pudo guardar el registro: {e}")

    # Botón para cancelar
    if st.button("Cancelar"):
        st.session_state.show_add_form = False
        st.rerun()


def show_edit_form(gc: gspread.Client, row_data: dict, selected_sheet: str, all_columns: list, clear_cache_func):
    """
    Muestra el formulario para editar un registro existente.
    """
    st.subheader(f"✏️ Editando Registro en '{selected_sheet}'")
    
    # Encontrar el índice de la fila (basado en la primera columna)
    id_column_name = all_columns[0]
    id_value = row_data.get(id_column_name)
    
    if not id_value:
        st.error("Error: No se pudo identificar la fila. Falta el valor de la primera columna.")
        return

    with st.form(key=f"edit_form_{selected_sheet}_{id_value}"):
        
        # Renderizar los campos con los datos existentes
        data_to_submit = _render_form_fields(gc, selected_sheet, existing_data=row_data)
        
        st.markdown("---")
        submitted = st.form_submit_button("Actualizar Registro")

    if submitted:
        # Validar los datos antes de enviar
        is_valid, error_message = validate_data(selected_sheet, data_to_submit)
        
        if not is_valid:
            st.error(f"Error de validación: {error_message}")
            return # Detener el envío

        try:
            with st.spinner("Actualizando en Google Sheets..."):
                sh = gc.open_by_key(GOOGLE_SHEET_ID)
                worksheet = sh.worksheet(selected_sheet)
                
                # Encontrar el número de la fila en la hoja
                cell = worksheet.find(id_value, in_column=1)
                if not cell:
                    st.error(f"Error: No se pudo encontrar la fila con el ID '{id_value}' para actualizar.")
                    return

                row_index = cell.row
                
                # Convertir todos los valores a string
                updated_row = []
                for col_name in all_columns:
                    value = data_to_submit.get(col_name)
                    
                    if isinstance(value, (datetime, time)):
                        value = value.isoformat()
                    elif value is None:
                        value = ""
                        
                    updated_row.append(str(value))
                
                # Actualizar la fila por índice
                # gspread usa 'range' A1-notation. Ej: 'A12:Z12'
                range_to_update = f"A{row_index}:{gspread.utils.rowcol_to_a1(row_index, len(all_columns))}"
                worksheet.update(
                    range_to_update, 
                    [updated_row], # Debe ser una lista de listas
                    value_input_option='USER_ENTERED'
                )
            
            st.success("¡Registro actualizado exitosamente!")
            
            # Limpiar el caché
            clear_cache_func()
            
            # Ocultar el formulario
            st.session_state.editing_row = None
            st.rerun()

        except Exception as e:
            st.error(f"No se pudo actualizar el registro: {e}")

    # Botón para cancelar
    if st.button("Cancelar"):
        st.session_state.editing_row = None
        st.rerun()

