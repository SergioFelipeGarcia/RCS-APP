# -*- coding: utf-8 -*-

# =============================================================================
# IMPORTACIONES
# =============================================================================
# Importamos las librerías necesarias para que nuestra aplicación funcione.

import os
# 'os' nos permite acceder a las variables de entorno del sistema, como los secretos.
# Es la forma segura de manejar credenciales sin escribirlas directamente en el código.

import hmac
import hashlib
# 'hmac' y 'hashlib' son librerías criptográficas estándar de Python.
# Las usamos para verificar la firma digital (HMAC) que envía Google,
# asegurando que los mensajes provienen realmente de ellos y no de un tercero.

from flask import Flask, request, jsonify
# 'Flask' es el framework web que usamos para crear nuestro servidor y rutas.
# 'request' nos permite acceder a los detalles de la petición entrante (cuerpo, cabeceras, etc.).
# 'jsonify' nos ayuda a crear respuestas en formato JSON de manera sencilla.


# =============================================================================
# INICIALIZACIÓN DE LA APLICACIÓN FLASK
# =============================================================================

app = Flask(__name__)
# Creamos una instancia de nuestra aplicación Flask.
# '__name__' es una variable especial de Python que le dice a Flask dónde encontrar
# los archivos de la aplicación (como plantillas o archivos estáticos), aunque para esta API no es crucial.


# =============================================================================
# FUNCIÓN AUXILIAR PARA VERIFICAR FIRMA HMAC
# =============================================================================

def is_valid_signature(request_body, secret, signature_to_verify):
    """
    Verifica si la firma HMAC recibida de Google es auténtica.

    ¿Por qué es necesaria esta función?
    Google firma cada mensaje con un secreto compartido. Al calcular la misma firma
    en nuestro servidor y compararla, podemos estar seguros de que el mensaje no ha
    sido manipulado y que proviene de Google.

    Args:
        request_body (str): El cuerpo crudo de la petición HTTP en formato string.
        secret (str): El secreto compartido que nos dio Google (RBM_WEBHOOK_SECRET).
        signature_to_verify (str): La firma que viene en la cabecera 'X-Goog-Signature'.

    Returns:
        bool: True si la firma es válida, False si no lo es.
    """
    # Si no tenemos secreto o firma, no podemos verificar, así que devolvemos False.
    if not secret or not signature_to_verify:
        return False

    # La firma se calcula sobre bytes, no sobre strings. Convertimos todo a bytes.
    request_body_bytes = request_body.encode('utf-8')
    secret_bytes = secret.encode('utf-8')

    # Calculamos la firma HMAC-SHA256 usando nuestro secreto y el cuerpo de la petición.
    calculated_signature = hmac.new(
        secret_bytes,
        request_body_bytes,
        hashlib.sha256  # Especificamos el algoritmo de hash que Google usa (SHA256).
    ).hexdigest()

    # Comparamos la firma que calculamos con la que recibimos.
    # Usamos 'hmac.compare_digest' porque es una función segura que previene
    # "timing attacks", un tipo de ataque que intenta adivinar secretos midiendo
    # el tiempo que tarda la comparación.
    return hmac.compare_digest(calculated_signature, signature_to_verify)


# =============================================================================
# RUTA PRINCIPAL DEL WEBHOOK
# =============================================================================

@app.route('/', methods=['POST'])
def webhook_receiver():
    """
    Esta es la función principal que recibe TODAS las peticiones de Google RCS.
    Actúa como un "controlador" que decide qué hacer con cada petición.
    """
    # Obtenemos los datos JSON de la petición. Si no es JSON, 'data' será None.
    data = request.get_json()

    # --------------------------------------------------------------------------
    # CASO 1: VERIFICACIÓN INICIAL (One-time setup)
    # --------------------------------------------------------------------------
    # Cuando registras el webhook por primera vez en la consola de Google,
    # Google envía UNA ÚNICA petición con un 'clientToken' para confirmar
    # que eres el dueño de la URL.
    if data and 'clientToken' in data:
        print("INFO: Recibida petición de verificación inicial (clientToken). Respondiendo 200 OK.")
        # Para esta verificación, no necesitamos comprobar ningún secreto.
        # La única tarea es responder con un código de estado 200 (OK) para que
        # Google sepa que el endpoint está activo y bajo nuestro control.
        return jsonify({"status": "Webhook recibido para verificación"}), 200

    # --------------------------------------------------------------------------
    # CASO 2: MENSAJES CONTINUOS (todos los demás mensajes)
    # --------------------------------------------------------------------------
    # Si la petición no contiene 'clientToken', asumimos que es un mensaje real
    # de un usuario, una confirmación de entrega, etc. Estos mensajes deben
    # estar firmados criptográficamente.
    print("INFO: Recibida petición de mensaje continuo. Verificando firma...")

    # 1. Leemos nuestro secreto desde las variables de entorno de Render.
    #    Usar .get() es más seguro que os.environ['...'] porque no lanza un error
    #    si la variable no existe, en su lugar devuelve None.
    webhook_secret = os.environ.get('RBM_WEBHOOK_SECRET')

    # 2. Verificamos si el secreto fue configurado correctamente en Render.
    #    Si no está, la aplicación no puede funcionar de forma segura.
    if not webhook_secret:
        print("ERROR: La variable de entorno RBM_WEBHOOK_SECRET no está configurada.")
        # Devolvemos un error 500 (Internal Server Error) indicando un problema de configuración.
        return jsonify({"error": "Configuración del servidor incompleta"}), 500

    # 3. Obtenemos la firma que Google nos envía en la cabecera HTTP.
    #    Esta es la firma que tenemos que verificar.
    signature = request.headers.get('X-Goog-Signature')
    if not signature:
        print("ERROR: Falta la cabecera 'X-Goog-Signature'. Petición no es de Google.")
        # Si no hay firma, la petición es sospechosa. La rechazamos con un 403 (Forbidden).
        return jsonify({"error": "Firma no proporcionada"}), 403

    # 4. Obtenemos el cuerpo CRUDO de la petición.
    #    ¡MUY IMPORTANTE! La firma se calcula sobre el string original del JSON,
    #    no sobre el diccionario de Python que crea request.get_json().
    request_body = request.data.decode('utf-8')

    # 5. Usamos nuestra función auxiliar para verificar si la firma es válida.
    if is_valid_signature(request_body, webhook_secret, signature):
        print("ÉXITO: Firma HMAC verificada correctamente. Mensaje auténtico.")

        # --- AQUÍ VA TU LÓGICA DE NEGOCIO ---
        # Aquí es donde procesarías el contenido del mensaje.
        # Por ejemplo: guardar en la base de datos, enviar una respuesta automática, etc.
        # print(f"DEBUG: Contenido del mensaje recibido: {data}")
        # procesar_mensaje(data)

        # Respondemos con 200 OK para hacerle saber a Google que hemos recibido
        # y procesado el mensaje correctamente. Esto evita que Google nos reenvíe el mismo mensaje.
        return jsonify({"status": "Mensaje recibido y procesado"}), 200
    else:
        # Si la firma no es válida, es un intento de acceso no autorizado.
        print("ADVERTENCIA: La firma HMAC no es válida. Petición rechazada.")
        # Rechazamos la petición con un 403 (Forbidden).
        return jsonify({"error": "Firma inválida. Petición no autorizada"}), 403


# =============================================================================
# BLOQUE DE EJECUCIÓN LOCAL
# =============================================================================
# Este bloque solo se ejecuta cuando corres el script directamente con `python server_flask.py`.
# Es muy útil para pruebas locales, pero es IGNORADO por el servidor de producción (Gunicorn).

if __name__ == '__main__':
    # Iniciamos el servidor de desarrollo de Flask.
    # 'debug=True' recarga automáticamente el servidor si haces cambios en el código.
    # 'port=5000' especifica el puerto en el que se ejecutará localmente.
    app.run(debug=True, port=5000)
