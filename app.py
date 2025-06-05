import os
import sys
import json
import logging
import tempfile
import threading
import uuid
from flask import Flask, request, jsonify, render_template_string, send_file
from dotenv import load_dotenv
from test_documentai import (
    setup_environment,
    cargar_etiquetas,
    process_document,
    preparar_datos_para_bd
)

app = Flask(__name__)

# Cargar variables de entorno
load_dotenv()

# Configuración de logger
logger = logging.getLogger('documentai_invoice')
logger.setLevel(logging.DEBUG)
handler = logging.StreamHandler(sys.stdout)
formatter = logging.Formatter('[%(levelname)s] %(message)s')
handler.setFormatter(formatter)
logger.addHandler(handler)

# Diccionario para almacenar datos de sesión
session_data = {}


@app.route('/')
def index():
    html_content = """
    <!DOCTYPE html>
    <html lang="es">
    <head>
        <meta charset="UTF-8">
        <title>Subir Factura - IEVM</title>
        <style>
            body {
                background-color: #F3ECE7;
                font-family: Arial, sans-serif;
                display: flex;
                flex-direction: column;
                align-items: center;
                justify-content: center;
                height: 100vh;
                margin: 0;
            }
            h1 {
                color: #2c3e50;
            }
            form {
                background: #fff;
                padding: 20px;
                border-radius: 10px;
                box-shadow: 0 0 10px rgba(0,0,0,0.1);
            }
            button {
                background-color: #2c3e50;
                color: white;
                padding: 10px 20px;
                border: none;
                border-radius: 5px;
                cursor: pointer;
                margin-top: 10px;
            }
        </style>
    </head>
    <body>
        <h1>Subir Factura para Procesar</h1>
        <form action="/upload" method="POST" enctype="multipart/form-data">
            <input type="file" name="file" accept="image/*" required />
            <br/>
            <button type="submit">Procesar</button>
        </form>
    </body>
    </html>
    """
    return render_template_string(html_content)


@app.route('/upload', methods=['POST'])
def upload_and_redirect():
    if 'file' not in request.files:
        return "Archivo no enviado", 400

    file = request.files['file']
    if file.filename == '':
        return "Nombre de archivo vacío", 400

    with tempfile.NamedTemporaryFile(delete=False, suffix='.jpg') as temp_file:
        file.save(temp_file.name)
        filename = os.path.basename(temp_file.name)

    return f"""
    <script>
        window.location.href = "/predict/{filename}";
    </script>
    """


@app.route('/predict/<filename>', methods=['GET'])
def predict_with_file(filename):
    temp_path = os.path.join(tempfile.gettempdir(), filename)
    if not os.path.exists(temp_path):
        return jsonify({'error': 'Archivo no encontrado'}), 404

    try:
        config = setup_environment()
        etiquetas = cargar_etiquetas()

        resultado = process_document(temp_path, config, etiquetas)
        datos_bd = preparar_datos_para_bd(resultado)

        # Generar un ID único para estos datos
        data_id = str(uuid.uuid4())

        # Almacenar datos en memoria (no en disco)
        session_data[data_id] = datos_bd

        os.unlink(temp_path)

        return render_template_string("""
            <!DOCTYPE html>
            <html lang="es">
            <head>
                <meta charset="UTF-8">
                <title>Resultado del Análisis</title>
                <style>
                    body {
                        background-color: #F9F9F9;
                        font-family: Arial, sans-serif;
                        padding: 30px;
                    }
                    pre {
                        background-color: #fff;
                        border: 1px solid #ccc;
                        padding: 20px;
                        border-radius: 10px;
                        white-space: pre-wrap;
                        word-wrap: break-word;
                    }
                    .button-container {
                        display: flex;
                        gap: 10px;
                        margin-top: 20px;
                        flex-wrap: wrap;
                    }
                    a {
                        display: inline-block;
                        padding: 10px 15px;
                        background-color: #2c3e50;
                        color: white;
                        text-decoration: none;
                        border-radius: 5px;
                        text-align: center;
                    }
                    .gui-link {
                        background-color: #27ae60;
                    }
                    .download-link {
                        background-color: #2980b9;
                    }
                </style>
            </head>
            <body>
                <h2>Resultado del Análisis</h2>
                <pre>{{ resultado }}</pre>
                
                <div class="button-container">
                    <a href="/">🔙 Subir otro archivo</a>
                    <a href="/gui/{{ data_id }}" class="gui-link">📊 Abrir GUI de Facturación</a>
                    <a href="/download/{{ data_id }}" class="download-link">💾 Descargar Datos (JSON)</a>
                </div>
            </body>
            </html>
        """, resultado=json.dumps(datos_bd, indent=4, ensure_ascii=False), data_id=data_id)

    except Exception as e:
        logger.exception("Error en el procesamiento")
        return jsonify({'error': 'Error interno', 'detalle': str(e)}), 500


@app.route('/download/<data_id>', methods=['GET'])
def download_json(data_id):
    datos_bd = session_data.get(data_id)
    if not datos_bd:
        return "Datos no encontrados o expirados", 404

    # Crear un archivo JSON temporal
    nombre_archivo = f"factura_{data_id}.json"
    temp_path = os.path.join(tempfile.gettempdir(), nombre_archivo)

    with open(temp_path, 'w', encoding='utf-8') as f:
        json.dump(datos_bd, f, ensure_ascii=False, indent=4)

    return send_file(
        temp_path,
        as_attachment=True,
        download_name=nombre_archivo,
        mimetype='application/json'
    )


@app.route('/gui/<data_id>', methods=['GET'])
def mostrar_gui_factura(data_id):
    datos_bd = session_data.get(data_id)
    if not datos_bd:
        return "Datos no encontrados o expirados", 404

    # Función para convertir saltos de línea en <br>
    def format_value(value):
        if isinstance(value, str):
            return value.replace('\n', '<br>')
        return value

    # Construir tabla de cliente
    tabla_cliente = """
    <table class="data-table">
        <tr><th colspan="2">Datos del Cliente</th></tr>
    """
    for campo, valor in datos_bd.get('cliente', {}).items():
        valor_formateado = format_value(valor)
        tabla_cliente += f"""
        <tr>
            <td class="field-name">{campo.replace('_', ' ').title()}</td>
            <td>{valor_formateado}</td>
        </tr>
        """
    tabla_cliente += "</table>"

    # Construir tabla de contrato
    tabla_contrato = """
    <table class="data-table">
        <tr><th colspan="2">Detalles del Contrato</th></tr>
    """
    for campo, valor in datos_bd.get('contrato', {}).items():
        valor_formateado = format_value(valor)
        tabla_contrato += f"""
        <tr>
            <td class="field-name">{campo.replace('_', ' ').title()}</td>
            <td>{valor_formateado}</td>
        </tr>
        """
    tabla_contrato += "</table>"

    # Construir tablas de facturación, pago y responsables
    tablas_adicionales = ""
    secciones = [
        ('facturacion', 'Facturación'),
        ('pago', 'Información de Pago'),
        ('responsables', 'Responsables')
    ]

    for seccion, titulo in secciones:
        if seccion in datos_bd:
            tabla_html = f"""
            <table class="data-table">
                <tr><th colspan="2">{titulo}</th></tr>
            """
            for campo, valor in datos_bd[seccion].items():
                valor_formateado = format_value(
                    valor) if valor is not None else "N/A"
                tabla_html += f"""
                <tr>
                    <td class="field-name">{campo.replace('_', ' ').title()}</td>
                    <td>{valor_formateado}</td>
                </tr>
                """
            tabla_html += "</table>"
            tablas_adicionales += tabla_html

    # Construir tabla de productos
    tabla_productos = """
    <table class="data-table">
        <tr>
            <th>Cantidad</th>
            <th>Código</th>
            <th>Detalle</th>
            <th>Valor Unitario</th>
            <th>Valor Total</th>
        </tr>
    """
    for producto in datos_bd.get('productos', []):
        cantidad = format_value(producto.get('cantidad', 'N/A'))
        codigo = format_value(producto.get('codigo', 'N/A'))
        detalle = format_value(producto.get('detalle', 'N/A'))
        valor_unitario = format_value(producto.get('valor_unitario', 'N/A'))
        valor_total = format_value(producto.get('valor_total', 'N/A'))

        tabla_productos += f"""
        <tr>
            <td>{cantidad}</td>
            <td>{codigo}</td>
            <td>{detalle}</td>
            <td>{valor_unitario}</td>
            <td>{valor_total}</td>
        </tr>
        """
    tabla_productos += "</table>"

    # Construir sección de validación
    tabla_validacion = ""
    if 'validacion' in datos_bd:
        validacion = datos_bd['validacion']
        tabla_validacion = """
        <div class="validation-section">
            <h3>Validación y Advertencias</h3>
            <div class="validation-grid">
        """

        # Advertencias
        if validacion.get('advertencias'):
            tabla_validacion += """
            <div class="validation-card">
                <h4>Advertencias</h4>
                <ul>
            """
            for advertencia in validacion['advertencias']:
                tabla_validacion += f"<li>{advertencia}</li>"
            tabla_validacion += """
                </ul>
            </div>
            """

        # Campos faltantes
        if validacion.get('campos_faltantes'):
            tabla_validacion += """
            <div class="validation-card">
                <h4>Campos Faltantes</h4>
                <ul>
            """
            for campo in validacion['campos_faltantes']:
                tabla_validacion += f"<li>{campo}</li>"
            tabla_validacion += """
                </ul>
            </div>
            """

        tabla_validacion += "</div></div>"

    # HTML completo con estilos
    return render_template_string(f"""
    <!DOCTYPE html>
    <html lang="es">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>Visualizador de Factura - IEVM</title>
        <style>
            * {{
                box-sizing: border-box;
                margin: 0;
                padding: 0;
                font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
            }}
            body {{
                background-color: #f5f7fa;
                color: #333;
                line-height: 1.6;
                padding: 20px;
            }}
            .container {{
                max-width: 1200px;
                margin: 0 auto;
                background: white;
                border-radius: 10px;
                box-shadow: 0 0 20px rgba(0,0,0,0.1);
                overflow: hidden;
            }}
            header {{
                background: linear-gradient(135deg, #2c3e50, #4a6491);
                color: white;
                padding: 30px 40px;
                text-align: center;
            }}
            header h1 {{
                margin-bottom: 10px;
                font-size: 2.2rem;
            }}
            .content {{
                padding: 30px;
            }}
            .section {{
                margin-bottom: 30px;
                padding-bottom: 20px;
                border-bottom: 1px solid #eaeaea;
            }}
            .section:last-child {{
                border-bottom: none;
            }}
            .section-title {{
                color: #2c3e50;
                margin-bottom: 20px;
                padding-bottom: 10px;
                border-bottom: 2px solid #3498db;
                font-size: 1.6rem;
            }}
            .data-grid {{
                display: grid;
                grid-template-columns: repeat(auto-fit, minmax(300px, 1fr));
                gap: 20px;
                margin-bottom: 30px;
            }}
            .data-table {{
                width: 100%;
                border-collapse: collapse;
                border-radius: 8px;
                overflow: hidden;
                box-shadow: 0 2px 10px rgba(0,0,0,0.05);
            }}
            .data-table th {{
                background-color: #3498db;
                color: white;
                padding: 15px;
                text-align: left;
                font-weight: 600;
            }}
            .data-table td {{
                padding: 12px 15px;
                border-bottom: 1px solid #eee;
            }}
            .data-table tr:nth-child(even) {{
                background-color: #f8f9fa;
            }}
            .field-name {{
                font-weight: 600;
                color: #2c3e50;
                width: 40%;
            }}
            .validation-section {{
                background-color: #fff8e1;
                border-radius: 8px;
                padding: 20px;
                margin-top: 20px;
                border-left: 4px solid #ffc107;
            }}
            .validation-grid {{
                display: grid;
                grid-template-columns: repeat(auto-fit, minmax(300px, 1fr));
                gap: 20px;
                margin-top: 15px;
            }}
            .validation-card {{
                background-color: white;
                padding: 15px;
                border-radius: 6px;
                box-shadow: 0 2px 5px rgba(0,0,0,0.05);
            }}
            .validation-card h4 {{
                color: #d32f2f;
                margin-bottom: 10px;
            }}
            .validation-card ul {{
                padding-left: 20px;
            }}
            .validation-card li {{
                margin-bottom: 8px;
            }}
            .actions {{
                display: flex;
                justify-content: center;
                gap: 15px;
                margin-top: 30px;
                flex-wrap: wrap;
            }}
            .btn {{
                display: inline-block;
                padding: 12px 25px;
                background: #3498db;
                color: white;
                text-decoration: none;
                border-radius: 5px;
                font-weight: 600;
                transition: all 0.3s ease;
                border: none;
                cursor: pointer;
                font-size: 1rem;
            }}
            .btn:hover {{
                transform: translateY(-2px);
                box-shadow: 0 4px 8px rgba(0,0,0,0.1);
            }}
            .btn-download {{
                background: #27ae60;
            }}
            .btn-download:hover {{
                background: #219653;
            }}
            .btn-back {{
                background: #95a5a6;
            }}
            .btn-back:hover {{
                background: #7f8c8d;
            }}
            @media (max-width: 768px) {{
                .data-table {{
                    display: block;
                    overflow-x: auto;
                }}
                .actions {{
                    flex-direction: column;
                    align-items: center;
                }}
                .btn {{
                    width: 100%;
                    max-width: 300px;
                    text-align: center;
                }}
            }}
        </style>
    </head>
    <body>
        <div class="container">
            <header>
                <h1>Visualizador de Contrato</h1>
                <p>IEVM - Información detallada del documento</p>
            </header>
            <div class="content">
                <div class="section">
                    <h2 class="section-title">Información Básica</h2>
                    <div class="data-grid">
                        {tabla_cliente}
                        {tabla_contrato}
                    </div>
                </div>
                <div class="section">
                    <h2 class="section-title">Detalles Adicionales</h2>
                    <div class="data-grid">
                        {tablas_adicionales}
                    </div>
                </div>
                <div class="section">
                    <h2 class="section-title">Productos/Servicios</h2>
                    {tabla_productos}
                </div>
                <div class="section">
                    {tabla_validacion}
                </div>
                <div class="actions">
                    <a href="/" class="btn btn-back">Volver al Inicio</a>
                    <a href="/download/{data_id}" class="btn btn-download">Descargar JSON</a>
                </div>
            </div>
        </div>
    </body>
    </html>
    """)


@app.route('/download-app', methods=['GET'])
def download_app():
    # Esta ruta debería servir el ejecutable de la aplicación
    # En un entorno real, esto apuntaría al archivo compilado
    return "La aplicación de escritorio está en desarrollo. Por favor, descargue los datos JSON y ejecute factura_gui_v2.py localmente.", 200


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8080, debug=True)
