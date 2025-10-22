# -*- coding: utf-8 -*-

from flask import Flask, request, jsonify
import hashlib
import hmac
import base64
import json
import os
from datetime import datetime

app = Flask(__name__)

# Configuración
SECRET_KEY = os.getenv('GOOGLE_WEBHOOK_SECRET', '')  # Vacío inicialmente
PORT = int(os.getenv('PORT', 5000))

# Logging
import logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def verify_signature(request_data, signature_header):
    """
    Verifica la firma de la solicitud de Google
    Solo se ejecuta si SECRET_KEY está configurado
    """
    # Si no hay secret configurado, permitir la solicitud (fase de validación)
    if not SECRET_KEY:
        logger.info("⚠️ SECRET_KEY no configurado - Modo validación")
        return True
    
    if not signature_header:
        logger.warning("❌ No se recibió header X-Goog-Signature")
        return False
    
    try:
        # Crear el hash HMAC
        expected_signature = hmac.new(
            SECRET_KEY.encode('utf-8'),
            request_data,
            hashlib.sha512
        ).digest()
        
        # Codificar en base64
        expected_signature_b64 = base64.encodebytes(expected_signature).decode('utf-8').strip()
        
        # Comparar de forma segura
        is_valid = hmac.compare_digest(expected_signature_b64, signature_header)
        
        if is_valid:
            logger.info("✅ Firma verificada correctamente")
        else:
            logger.warning("❌ Firma inválida")
        
        return is_valid
    
    except Exception as e:
        logger.error(f"❌ Error verificando firma: {e}")
        return False


@app.route('/', methods=['GET'])
def home():
    """
    Endpoint de información
    """
    return jsonify({
        'status': 'online',
        'service': 'Google RCS Business Messaging Webhook',
        'timestamp': datetime.utcnow().isoformat(),
        'validation_mode': not bool(SECRET_KEY),
        'endpoints': {
            'webhook': '/webhook',
            'health': '/health'
        }
    }), 200


@app.route('/webhook', methods=['POST'])
def webhook():
    """
    Endpoint principal para recibir mensajes de Google RCS.
    Maneja tanto mensajes directos como mensajes empaquetados (Pub/Sub).
    """
    try:
        logger.info("=" * 50)
        logger.info("📨 Nueva solicitud recibida")
        
        # Obtener el contenido de la solicitud
        request_data = request.get_data()
        signature = request.headers.get('X-Goog-Signature')
        
        logger.info(f"Signature recibida: {signature if signature else 'NINGUNA'}")
        logger.info(f"Tamaño del payload: {len(request_data)} bytes")
        
        # Verificar firma (solo si SECRET_KEY está configurado)
        if not verify_signature(request_data, signature):
            logger.warning("❌ Verificación de firma falló")
            return jsonify({'error': 'Invalid signature'}), 401
        
        # Parsear JSON
        data = request.get_json()
        
        if not data:
            logger.warning("❌ No se recibió data JSON")
            return jsonify({'error': 'No data received'}), 400
        
        # --- ESTA LÍNEA YA IMPRIME EL JSON COMPLETO PARA DEPURACIÓN ---
        logger.info(f"📦 Payload recibido:\n{json.dumps(data, indent=2)}")
        
        # =======================================================================
        # LÓGICA ACTUALIZADA PARA MANEJAR MENSAJES EMPAQUETADOS Y DIRECTOS
        # =======================================================================
        
        # Caso especial: Verificación inicial de Google
        if 'clientToken' in data and 'secret' in data:
            logger.info("🔑 Recibida petición de verificación especial.")
            verification_secret = data.get('secret')
            client_token = data.get('clientToken')
            logger.info(f"🔓 Respondiendo 200 OK con el secreto: {verification_secret} (para clientToken: {client_token})")
            return jsonify({'secret': verification_secret}), 200

        # Determinar si es un mensaje empaquetado (Pub/Sub) o directo
        message_data = data.get('message', {})
        attributes = message_data.get('attributes', {})

        if attributes and 'message_type' in attributes:
            # --- ES UN MENSAJE EMPAQUETADO (Pub/Sub) ---
            logger.info("📦 Mensaje detectado en formato Pub/Sub. Desempaquetando...")
            
            # 1. Decodificar el contenido
            encoded_data = message_data.get('data', '')
            decoded_bytes = base64.b64decode(encoded_data)
            real_data = json.loads(decoded_bytes.decode('utf-8'))
            
            logger.info("✅ Mensaje desempaquetado correctamente.")
            logger.info(f"📦 Contenido real:\n{json.dumps(real_data, indent=2)}")
            
            # 2. Obtener el tipo de mensaje real desde los atributos
            message_type = attributes.get('message_type')
            logger.info(f"📌 Tipo de evento real (desde atributos): {message_type}")
            
            
           # 3. Llamar al manejador correcto con los datos desempaquetados
            if message_type == 'SUGGESTION_RESPONSE':
                handle_suggestion_response(real_data)
            elif message_type == 'TEXT':  # <-- ¡AÑADE ESTA LÍNEA!
                handle_message(real_data)
            elif message_type == 'message': # Este se queda como fallback
                handle_message(real_data)
            else:
                logger.warning(f"⚠️ Tipo de mensaje no manejado: {message_type}")

        else:
            # --- ES UN MENSAJE DIRECTO (como el de curl o la verificación) ---
            logger.info("📬 Mensaje detectado en formato directo.")
            
            # Usar la lógica original para determinar el tipo de evento
            event_type = detect_event_type(data)
            logger.info(f"📌 Tipo de evento (directo): {event_type}")
            
            if event_type == 'message':
                handle_message(data)
            elif event_type == 'userStatus':
                handle_user_status(data)
            elif event_type == 'receipt':
                handle_receipt(data)
            else:
                logger.warning(f"⚠️ Tipo de evento desconocido: {list(data.keys())}")
        
        # =======================================================================
        # FIN DE LA LÓGICA ACTUALIZADA
        # =======================================================================
        
        # Responder con 200 OK (MUY IMPORTANTE para validación de Google)
        logger.info("✅ Respondiendo 200 OK")
        logger.info("=" * 50)
        return jsonify({'status': 'success'}), 200
    
    except json.JSONDecodeError as e:
        logger.error(f"❌ Error parseando JSON: {e}")
        return jsonify({'error': 'Invalid JSON'}), 400
    
    except Exception as e:
        logger.error(f"❌ Error procesando webhook: {e}", exc_info=True)
        return jsonify({'error': 'Internal server error'}), 500


def detect_event_type(data):
    """
    Detecta el tipo de evento recibido (para mensajes directos)
    """
    if 'message' in data:
        return 'message'
    elif 'userStatus' in data:
        return 'userStatus'
    elif 'receipt' in data:
        return 'receipt'
    elif 'suggestionResponse' in data:
        return 'suggestionResponse'
    else:
        return 'unknown'


# =============================================================================
# FUNCIÓN MEJORADA PARA MANEJAR MENSAJES (ahora recibe datos ya procesados)
# =============================================================================
def handle_message(data):
    """
    Procesa los mensajes de texto o con contenido rico.
    Ahora busca el texto en las claves correctas tanto para mensajes simples como complejos.
    """
    logger.info("🚀 Iniciando procesamiento de un nuevo mensaje...")
    
    # 1. Extraer información del remitente
    sender_phone = data.get('senderPhoneNumber', 'Desconocido')
    message_id = data.get('messageId', 'ID_No_Disponible')
    timestamp = data.get('sendTime', 'Timestamp_No_Disponible')

    # 2. Extraer el contenido del mensaje de forma flexible
    message_content = data.get('textEvent', {}) # Busca en el contenido del evento
    text_content = message_content.get('text') # Extrae el texto de ahí
    
    # Si no lo encontró, busca en la raíz del mensaje (para mensajes simples)
    if not text_content:
        text_content = data.get('text', 'Mensaje sin texto')

    # 3. Imprimir cabecera del mensaje procesado
    print("\n" + "="*50)
    print(f"💬 NUEVO MENSAJE RECIBIDO DE: {sender_phone}")
    print("="*50)
    print(f"📝 Tipo: Mensaje de Texto")
    print(f"   Contenido: '{text_content}'")
    print(f"🆔 ID del Mensaje: {message_id}")
    print(f"⏰ Enviado a las: {timestamp}")
    print("="*50 + "\n")

    # 4. Lógica de Negocio (Aquí es donde tú añadirías tu código)
    if "hola" in text_content.lower():
        print("🤖 Se detectó un saludo. Aquí podrías enviar una respuesta automática.")
    
    logger.info(f"✅ Mensaje de '{sender_phone}' procesado correctamente.")


# =============================================================================
# FUNCIÓN PARA MANEJAR RESPUESTAS A SUGERENCIAS
# =============================================================================
def handle_suggestion_response(data):
    """
    Maneja respuestas a sugerencias (botones, acciones sugeridas).
    Asume que 'data' es el JSON ya desempaquetado y limpio.
    """
    logger.info("🚀 Iniciando procesamiento de una respuesta a sugerencia...")
    
    sender_phone = data.get('senderPhoneNumber', 'Desconocido')
    message_id = data.get('messageId', 'ID_No_Disponible')
    
    suggestion_response = data.get('suggestionResponse', {})
    postback_data = suggestion_response.get('postbackData', '')
    text = suggestion_response.get('text', '')
    
    print("\n" + "="*50)
    print(f"🔘 RESPUESTA A SUGERENCIA RECIBIDA DE: {sender_phone}")
    print("="*50)
    print(f"   Texto: '{text}'")
    print(f"   Postback Data: '{postback_data}'")
    print("="*50 + "\n")

    # TODO: Implementar lógica según el postback
    logger.info(f"✅ Respuesta a sugerencia de '{sender_phone}' procesada correctamente.")


# =============================================================================
# FUNCIONES PARA OTROS EVENTOS (sin cambios)
# =============================================================================
def handle_user_status(data):
    """Maneja cambios de estado del usuario (typing indicators)."""
    user_status = data.get('userStatus', {})
    sender_id = data.get('senderPhoneNumber', 'Unknown')
    is_typing = user_status.get('isTyping', False)
    logger.info(f"⌨️ Estado de usuario: {sender_id} está {'escribiendo...' if is_typing else 'inactivo'}.")

def handle_receipt(data):
    """Maneja confirmaciones de entrega/lectura."""
    receipt = data.get('receipt', {})
    message_id = receipt.get('messageId', 'Unknown')
    receipt_type = receipt.get('receiptType', 'Unknown')
    logger.info(f"📧 Recibo: Mensaje {message_id} marcado como '{receipt_type}'.")


@app.route('/health', methods=['GET'])
def health():
    """Endpoint de health check para monitoreo."""
    return jsonify({
        'status': 'healthy',
        'timestamp': datetime.utcnow().isoformat(),
        'secret_configured': bool(SECRET_KEY)
    }), 200


if __name__ == '__main__':
    if not SECRET_KEY:
        logger.warning("⚠️" * 20)
        logger.warning("⚠️ MODO VALIDACIÓN: SECRET_KEY no configurado")
        logger.warning("⚠️ El webhook aceptará todas las solicitudes")
        logger.warning("⚠️ Configura GOOGLE_WEBHOOK_SECRET después de la validación")
        logger.warning("⚠️" * 20)
    
    app.run(
        host='0.0.0.0',
        port=PORT,
        debug=os.getenv('FLASK_ENV') == 'development'
    )