# -*- coding: utf-8 -*-

import streamlit as st
import uuid
import os
import requests
import google.oauth2.credentials
import google_auth_oauthlib.flow

# --- CONFIGURACIÓN DE LA PÁGINA ---
st.set_page_config(
    page_title="RCS - Envío de Mensajes",
    page_icon="📤",
    layout="centered"
)

st.title("📤 Envío de Mensajes con Google RCS")
st.write("Usa este formulario para enviar un mensaje a un usuario a través de la API de Google RCS.")

# --- LÓGICA DE AUTENTICACIÓN ---

def load_credentials():
    """Carga las credenciales desde el archivo JSON o desde las variables de entorno de Render."""
    # En producción (Render), las credenciales están en una variable de entorno.
    credentials_json = os.environ.get("GOOGLE_APPLICATION_CREDENTIALS")
    if credentials_json:
        return google.oauth2.credentials.Credentials.from_authorized_user_info(
            info=eval(credentials_json)
        )
    # En desarrollo local, las cargamos desde el archivo credentials.json.
    else:
        flow = google_auth_oauthlib.flow.InstalledAppFlow.from_client_secrets_file(
            "credentials.json",
            scopes=["https://www.googleapis.com/auth/businessmessages"]
        )
        credentials = flow.run_local_server(port=8501)
        return credentials

def get_access_token():
    """Obtiene un token de acceso válido."""
    credentials = load_credentials()
    if not credentials or not credentials.valid:
        st.error("❌ No se pudieron cargar las credenciales. Revisa el archivo credentials.json o las variables de entorno.")
        return None
    credentials.refresh(google.auth.transport.requests.Request())
    return credentials.token

# --- LÓGICA DE ENVÍO A LA API ---

def send_message_via_api(recipient_phone, message_text, transaction_id):
    """
    Envía un mensaje real a través de la API de Google RCS.
    """
    access_token = get_access_token()
    if not access_token:
        return None, "No se pudo obtener el token de acceso."

    # URL del endpoint de la API de Google para enviar mensajes
    url=f"https://businessmessages.googleapis.com/v1/agents/orange_empresas_uonv4h9f_agent@rbm.oog/messages:send"

    # Cabeceras de la petición
    headers = {
        "Authorization": f"Bearer {access_token}",
        "Content-Type": "application/json"
    }

    # Cuerpo (payload) del mensaje
    payload = {
        "messageId": transaction_id,
        "contentMessage": {
            "text": {
                "text": message_text
            }
        },
        "phoneNumber": recipient_phone
    }

    try:
        response = requests.post(url, headers=headers, json=payload)
        
        if response.status_code == 200:
            return response.json(), "Mensaje enviado con éxito."
        else:
            return response.json(), f"Error en la API: {response.status_code} - {response.text}"
    except Exception as e:
        return None, f"Error de conexión: {e}"

# --- INTERFAZ DE USUARIO (STREAMLIT) ---

# Usamos st.session_state para guardar las credenciales y no tener que loguearse cada vez
if "credentials" not in st.session_state:
    st.session_state["credentials"] = load_credentials()

if st.session_state["credentials"] and st.session_state["credentials"].valid:
    st.success("✅ Autenticado correctamente en la API de Google.")
else:
    st.warning("⚠️ No estás autenticado. Por favor, haz clic en el botón de abajo para autenticarte.")
    if st.button("Autenticar con Google"):
        # Inicia el flujo de autenticación de OAuth 2.0
        flow = google_auth_oauthlib.flow.InstalledAppFlow.from_client_secrets_file(
            "credentials.json",
            scopes=["https://www.googleapis.com/auth/businessmessages"],
            redirect_uri="http://localhost:8501"
        )
        authorization_url, state = flow.authorization_url()
        st.info(f"Por favor, ve a esta URL para autorizar la aplicación: [Autorizar]({authorization_url})")
        st.info(f"Luego, pega el código de autorización aquí:")
        authorization_code = st.text_input("Código de autorización")
        if st.button("Enviar"):
            flow.fetch_token(authorization_url=authorization_url)
            st.session_state["credentials"] = flow.credentials
            st.rerun()

# --- FORMULARIO DE ENVÍO ---

with st.form("message_form"):
    recipient_phone = st.text_input("📞 Número de Teléfono del Destinatario", placeholder="+34123456789")
    message_text = st.text_area("💬 Mensaje", placeholder="Escribe tu mensaje aquí...", height=150)
    submitted = st.form_submit_button("Enviar Mensaje", type="primary")

if submitted:
    if not recipient_phone or not message_text:
        st.error("❌ Por favor, rellena todos los campos.")
    else:
        transaction_id = str(uuid.uuid4())
        with st.spinner("Enviando mensaje..."):
            result, message = send_message_via_api(recipient_phone, message_text, transaction_id)
        
        if result:
            st.success(f"✅ {message}")
            st.json(result) # Muestra la respuesta de la API para depuración
        else:
            st.error(f"❌ {message}")

# --- PIE DE PÁGINA ---
st.markdown("---")
st.caption("Desarrollado por ti con Streamlit y la API de Google RCS.")