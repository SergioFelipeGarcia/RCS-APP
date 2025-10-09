import os
from flask import Flask, request, jsonify

app = Flask(__name__)

@app.route('/', methods=['POST'])
def webhook_receiver():
    """
    Recibe las peticiones POST del webhook de Google RCS.
    Verifica el clientToken para asegurar que la petición es legítima.
    """
    
    # 1. Leer el secreto desde las variables de entorno
    webhook_secret = os.environ.get('RBM_WEBHOOK_SECRET')

    # 2. Verificar si el secreto está configurado
    if not webhook_secret:
        print("ERROR: La variable de entorno RBM_WEBHOOK_SECRET no está configurada.")
        return jsonify({"error": "Configuración del servidor incompleta"}), 500

    # 3. Obtener los datos JSON de la petición entrante
    data = request.get_json()

    # 4. Verificar si se recibió JSON y si contiene la clave 'clientToken'
    if not data or 'clientToken' not in data:
        print("ERROR: Petición inválida, no se encontró 'clientToken' en el JSON.")
        return jsonify({"error": "Petición incorrecta"}), 400

    # 5. Comparar el token recibido con el secreto almacenado
    received_token = data['clientToken']
    
    if received_token == webhook_secret:
        # 6. Si coinciden, la petición es legítima
        print("Webhook verificado correctamente.")
        return jsonify({"secret": webhook_secret}), 200
    else:
        # 7. Si no coinciden, la petición no es de confianza
        print(f"ADVERTENCIA: Token recibido no coincide. Recibido: {received_token}")
        return jsonify({"error": "No autorizado"}), 401
    
if __name__ == '__main__':
    app.run(debug=True, port=5000)