import sys
import os
import re
import json
import argparse
import logging
from typing import Dict, Any, List, Tuple
from difflib import get_close_matches
from datetime import datetime
from datetime import datetime
from typing import Tuple

# Validación de importaciones necesarias
try:
    from google.cloud import documentai_v1 as documentai
    from google.api_core.client_options import ClientOptions
    from google.api_core.retry import Retry
    from dotenv import load_dotenv
except ImportError as e:
    print(
        f"Error de importación: {e}. Asegúrate de haber instalado todas las dependencias necesarias.")
    sys.exit(1)

# Configuración de logger
logger = logging.getLogger('documentai_invoice')
logger.setLevel(logging.DEBUG)
handler = logging.StreamHandler(sys.stdout)
formatter = logging.Formatter('[%(levelname)s] %(message)s')
handler.setFormatter(formatter)
logger.addHandler(handler)

# Cargar archivo .env si existe
load_dotenv()

# Dominios de correo comunes en Ecuador (para matching difuso)
DOMINIOS_VALIDOS = {
    # Freemail internacionales
    'gmail.com', 'hotmail.com', 'outlook.com', 'yahoo.com',
    'icloud.com', 'protonmail.com', 'yandex.com', 'live.com',
    'aol.com', 'zoho.com', 'mail.com', 'gmx.com', 'msn.com',

    # Educación general y universidades en Ecuador
    'edu.ec', 'ueb.edu.ec', 'espol.edu.ec', 'usfq.edu.ec',
    'uide.edu.ec', 'ucuenca.edu.ec', 'utpl.edu.ec', 'epn.edu.ec',
    'uees.edu.ec', 'uta.edu.ec', 'espe.edu.ec', 'unl.edu.ec',
    'ug.edu.ec', 'unemi.edu.ec', 'puce.edu.ec', 'ups.edu.ec',
    'unach.edu.ec', 'uazuay.edu.ec', 'utn.edu.ec', 'utm.edu.ec',
    'ute.edu.ec', 'utepsa.edu.ec', 'ulvr.edu.ec', 'uisrael.edu.ec',

    # Colegios y centros educativos particulares
    'colegioamericanguayaquil.edu.ec', 'nsc.edu.ec', 'lemans.edu.ec',
    'delta.edu.ec',

    # Gobierno y entidades públicas de Ecuador
    'gob.ec', 'judicatura.gob.ec', 'cne.gob.ec', 'defensa.gob.ec',
    'ministeriodefinanzas.gob.ec', 'educacion.gob.ec', 'salud.gob.ec',
    'ambiente.gob.ec', 'presidencia.gob.ec', 'miduvi.gob.ec',
    'ant.gob.ec'
}


def setup_environment() -> Dict[str, str]:
    logger.info("Validando configuración del entorno...")

    os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = os.path.join(
        os.path.dirname(__file__), "credentials.json"
    )

    creds = os.getenv("GOOGLE_APPLICATION_CREDENTIALS")
    if not creds or not os.path.isfile(creds):
        logger.error(f"Archivo de credenciales no encontrado: {creds}")
        raise EnvironmentError("GOOGLE_APPLICATION_CREDENTIALS no válido.")

    required_vars = ['PROJECT_ID', 'LOCATION',
                     'PROCESSOR_ID', 'PROCESSOR_VERSION_ID']
    config = {}
    for var in required_vars:
        val = os.getenv(var)
        if not val:
            logger.error(f"Variable de entorno faltante: {var}")
            raise EnvironmentError(f"Falta variable: {var}")
        config[var.lower()] = val.strip()

    logger.info("Entorno validado correctamente.")
    return config


def cargar_etiquetas() -> set:
    etiquetas = {
        'Nombrecliente', 'Ruc', 'Direccion_factura', 'direccioninstalacion', 'Ciudad', 'Correo', 'Telefono',
        'Fecha_contrato', 'Fecha_entrega', 'codigocontrato', 'observacion', 'Operario', 'Resp_Medicion',
        'subtotal', 'total_impuestos', 'total_final', 'abono', 'saldo_pendiente', 'Banco', 'Numerocheque'
    }
    for i in range(1, 21):
        for campo in ('cantidad', 'codigo', 'detalle', 'valor_unitario', 'valor_total'):
            etiquetas.add(f'producto{i}_{campo}')
    return etiquetas


def validar_telefono_ecuador(texto: str) -> Tuple[str, bool]:
    """
    Valida y formatea números de teléfono ecuatorianos.
    Extrae todos los bloques de 10 dígitos que comiencen con '09' (celulares),
    los concatena separados por '/', y retorna si son válidos.
    """
    # Extrae solo los dígitos
    numeros = re.findall(r'\d{10}', re.sub(r'\D', '', texto))

    # Filtra solo los que comienzan con '09'
    celulares_validos = [n for n in numeros if n.startswith('09')]

    if celulares_validos:
        valor = '/'.join(celulares_validos)
        return valor, True

    # Si no hay celulares válidos, retorna el texto limpio original y False
    return texto.strip(), False


INVALID_EMAIL_MESSAGE = "Extracción de dato incorrecta"


def validar_cedula_ruc(texto: str) -> Tuple[str, bool]:
    """
    Valida y limpia una cédula o RUC ecuatoriano extraído por OCR.
    - Cédula: 10 dígitos
    - RUC: 13 dígitos
    Si no cumple, retorna mensaje de error y False.
    """
    # Extrae solo dígitos (ignorando cualquier signo, espacio, letra)
    numeros = re.sub(r"[^\d]", "", texto)

    if len(numeros) == 10:
        return f"Cédula:{numeros}", True
    elif len(numeros) == 13:
        return f"RUC:{numeros}", True
    else:
        return INVALID_EMAIL_MESSAGE, False


INVALID_EMAIL_MESSAGE = "Extracción incorrecta"
EMAIL_FULL_REGEX = re.compile(
    r"^[a-zA-Z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}$")


def normalizar_correo(texto: str) -> Tuple[str, bool]:
    """
    Intenta normalizar un correo electrónico extraído por OCR:
    1. Reemplaza '(at)', '[at]', 'arroba' → '@'
    2. Limpia caracteres no válidos
    3. Si hay '@', separa local y dominio directamente
    4. Si no hay '@', asume último token como dominio y concatena el resto como local
    5. Corrige dominio por similitud contra DOMINIOS_VALIDOS
    6. Valida forma final con regex
    """
    # 1. Sustituir variantes de "at" que OCR suele generar
    texto = texto.strip().lower()
    texto = re.sub(r'\(at\)|\[at\]|arroba', '@', texto)

    # 2. Sustituir cualquier caracter que NO sea alfanumérico, '@', '.', '_', '-', '+' por espacio
    texto = re.sub(r'[^a-z0-9@._\-+]', ' ', texto)

    # 3. Si aparece '@', separar local y dominio tal cual
    if '@' in texto:
        # Tomar la primera aparición de local@dominio
        match = re.search(r'([a-z0-9._%+\-]+)@([a-z0-9.\-]+)', texto)
        if not match:
            return INVALID_EMAIL_MESSAGE, False
        local_part, domain_candidate = match.groups()
    else:
        # 4. No hay '@': dividir en tokens y asumir último token como dominio
        tokens = texto.split()
        if len(tokens) < 2:
            return INVALID_EMAIL_MESSAGE, False
        # último token = candidato a dominio
        domain_candidate = tokens[-1]
        # juntar todo lo anterior como local
        local_part = ''.join(tokens[:-1])

    # 5. Corregir dominio por similitud contra DOMINIOS_VALIDOS
    posibles = get_close_matches(
        domain_candidate, DOMINIOS_VALIDOS, n=1, cutoff=0.6)
    if not posibles:
        return INVALID_EMAIL_MESSAGE, False
    domain = posibles[0]

    # 6. Formar y validar estructura completa
    correo_normalizado = f"{local_part}@{domain}"
    if EMAIL_FULL_REGEX.match(correo_normalizado):
        return correo_normalizado, True

    return INVALID_EMAIL_MESSAGE, False


def formatear_monto(texto: str) -> str:
    try:
        # Manejar diferentes formatos numéricos
        texto_limpio = re.sub(r"[^\d,\.]", "", texto)
        texto_limpio = texto_limpio.replace(",", ".")

        # Manejar casos con múltiples puntos
        if texto_limpio.count(".") > 1:
            partes = texto_limpio.split(".")
            texto_limpio = f"{''.join(partes[:-1])}.{partes[-1]}"

        val = float(texto_limpio)
        return f"{val:,.2f}"
    except ValueError:
        return texto.strip()


def validar_fecha(texto: str) -> Tuple[str, bool]:
    """
    Valida y formatea fechas en formato dd/mm/yyyy.
    Soporta entradas especiales como '12 dia/08 mes 2024. año' o similares.
    """
    try:
        # 1. Formato especial tipo OCR: '12 dia/08 mes 2024. año'
        patron_especial = r'(\d{1,2})\s*(?:dia)?[^\d]*(\d{1,2})\s*(?:mes)?[^\d]*(\d{4})(?:\s*año)?'
        match = re.search(patron_especial, texto, re.IGNORECASE)
        if match:
            dia, mes, anio = match.groups()
            fecha = datetime(int(anio), int(mes), int(dia))
            return fecha.strftime('%d/%m/%Y'), True

        # 2. Formatos comunes
        formatos_comunes = ['%d/%m/%Y', '%d-%m-%Y', '%Y-%m-%d', '%d/%m/%y']
        texto_limpio = texto.strip()

        for fmt in formatos_comunes:
            try:
                fecha = datetime.strptime(texto_limpio, fmt)
                return fecha.strftime('%d/%m/%Y'), True
            except ValueError:
                continue

        # 3. Extrae solo números y barras (para OCR con mucho ruido)
        solo_numeros = re.sub(r'[^\d/]', '', texto)
        for fmt in formatos_comunes:
            try:
                fecha = datetime.strptime(solo_numeros, fmt)
                return fecha.strftime('%d/%m/%Y'), True
            except ValueError:
                continue

        return texto.strip(), False

    except Exception as e:
        logger.debug(f"Error al validar fecha '{texto}': {e}")
        return texto.strip(), False


def process_document(file_path: str, config: Dict[str, str], etiquetas_validas: set) -> Dict[str, Any]:
    if not os.path.isfile(file_path):
        raise FileNotFoundError(f"El archivo {file_path} no existe.")

    logger.info("Inicializando cliente de Document AI...")
    try:
        opts = ClientOptions(
            api_endpoint=f"{config['location']}-documentai.googleapis.com")
        client = documentai.DocumentProcessorServiceClient(client_options=opts)
        name = client.processor_version_path(
            config['project_id'], config['location'], config['processor_id'], config['processor_version_id']
        )
    except Exception as e:
        logger.exception("Error al crear cliente de Document AI")
        raise e

    logger.info("Procesando documento...")
    try:
        with open(file_path, 'rb') as f:
            raw = documentai.RawDocument(
                content=f.read(), mime_type="image/jpeg")
        request = documentai.ProcessRequest(name=name, raw_document=raw)
        result = client.process_document(request=request, timeout=120.0)
    except Exception as e:
        logger.exception("Error durante el procesamiento del documento")
        raise e

    datos: Dict[str, Any] = {}
    advertencias: List[str] = []

    for ent in result.document.entities:
        key = ent.type_
        text = ent.mention_text or ''

        if key in etiquetas_validas and text.strip():
            if key == 'Telefono':
                valor, valido = validar_telefono_ecuador(text)
                datos[key] = valor
                if not valido:
                    advertencias.append(
                        f"Teléfono '{valor}' no tiene formato ecuatoriano válido (09XXXXXXXX)")

            elif key == 'Ruc':
                valor, valido = validar_cedula_ruc(text)
                datos[key] = valor
                if not valido:
                    advertencias.append(
                        f"Identificación '{valor}' no es cédula (10 dígitos) ni RUC (13 dígitos) válido")

            elif key == 'Correo':
                valor, valido = normalizar_correo(text)
                datos[key] = valor
                if not valido:
                    advertencias.append(
                        f"Correo '{valor}' podría ser inválido o dominio no reconocido")

            elif key in {'subtotal', 'total_impuestos', 'total_final', 'abono', 'saldo_pendiente'} or \
                    (key.startswith('producto') and key.endswith(('valor_total', 'valor_unitario'))):
                datos[key] = formatear_monto(text)

            elif key in {'Fecha_contrato', 'Fecha_entrega'}:
                datos[key], valido = validar_fecha(text)
                if not valido:
                    advertencias.append(
                        f"Fecha '{text}' tiene un formato inválido, se esperaba dd/mm/yyyy")

            else:
                datos[key] = text.strip()

    productos: List[Dict[str, Any]] = []
    for i in range(1, 21):
        campos = {
            'cantidad': datos.get(f'producto{i}_cantidad'),
            'codigo': datos.get(f'producto{i}_codigo'),
            'detalle': datos.get(f'producto{i}_detalle'),
            'valor_unitario': datos.get(f'producto{i}_valor_unitario'),
            'valor_total': datos.get(f'producto{i}_valor_total'),
        }
        if any(campos.values()):
            productos.append(campos)
            for k in campos:
                datos.pop(f'producto{i}_{k}', None)

    faltantes = sorted(
        etiquetas_validas - set(datos.keys()) -
        {f'producto{i}_{c}' for i in range(1, 21) for c in [
            'cantidad', 'codigo', 'detalle', 'valor_unitario', 'valor_total']}
    )

    return {
        'datos_generales': datos,
        'productos': productos,
        'faltantes': faltantes,
        'advertencias': advertencias
    }


def imprimir_factura(resultado: Dict[str, Any]):
    d = resultado['datos_generales']
    logger.info('===== FACTURA EXTRAÍDA =====\n')
    # Aquí se imprime literalmente lo que contenga d['Ruc'] y d['Correo'],
    # que ahora sólo será "Cédula:<números>" o "RUC:<números>" o bien "Extracción de dato incorrecta"
    logger.info(f"Cliente: {d.get('Nombrecliente','')}    {d.get('Ruc','')}")
    logger.info(f"Dirección Factura: {d.get('Direccion_factura','')}")
    logger.info(
        f"Instalación: {d.get('direccioninstalacion','')}, Ciudad: {d.get('Ciudad','')}")
    logger.info(
        f"Correo: {d.get('Correo','')}    Teléfono: {d.get('Telefono','')}\n")
    logger.info(
        f"Contrato N°: {d.get('codigocontrato','')}    Fecha Contrato: {d.get('Fecha_contrato','')}    Fecha Entrega: {d.get('Fecha_entrega','')}\n")
    if d.get('observacion'):
        logger.info(f"Observación: {d['observacion']}\n")

    # Imprimir tabla de productos
    logger.info(
        f"{'Cant':<5} {'Código':<15} {'Detalle':<40} {'V.Unit':>10} {'V.Total':>10}")
    logger.info('-' * 85)
    for p in resultado['productos']:
        cantidad = str(p.get('cantidad', ''))
        codigo = str(p.get('codigo', ''))
        detalle = str(p.get('detalle', ''))
        valor_unitario = str(p.get('valor_unitario', ''))
        valor_total = str(p.get('valor_total', ''))
        logger.info(
            f"{cantidad:<5} {codigo:<15} {detalle:<40} {valor_unitario:>10} {valor_total:>10}")
    logger.info('-' * 85)

    # Imprimir totales
    logger.info(
        f"SUBTOTAL: {d.get('subtotal','')}    IVA: {d.get('total_impuestos','')}    TOTAL: {d.get('total_final','')}")
    if d.get('abono'):
        logger.info(
            f"ABONO: {d['abono']}    SALDO PENDIENTE: {d.get('saldo_pendiente','')}")
    if d.get('Banco'):
        logger.info(
            f"Banco: {d.get('Banco','')}    N° Cheque: {d.get('Numerocheque','')}\n")

    # Imprimir firmas
    if d.get('Operario'):
        logger.info(f"Operario: {d['Operario']}")
    if d.get('Resp_Medicion'):
        logger.info(f"Responsable Medición: {d['Resp_Medicion']}")

    # Imprimir advertencias y campos faltantes
    if resultado['advertencias']:
        logger.info('\n===== ADVERTENCIAS DE VALIDACIÓN =====')
        for advertencia in resultado['advertencias']:
            logger.warning(f"- {advertencia}")

    logger.info('\n===== Campos no encontrados =====')
    for tag in resultado['faltantes']:
        logger.info(f"- {tag}")


def probar_correo():
    """Función de prueba para verificar la corrección de correos con el nuevo método."""
    ejemplos = [
        "usuario@hotmai.com",
        "test@hotmal.com",
        "ejemplo@hotmial.com",
        "prueba@hotmail.co",
        "test@hotmail.con",
        "correo@gmail.con",
        "usuario@gmai.com",
    ]

    logger.info("\n===== PRUEBA DE CORRECCIÓN DE CORREOS =====")
    for correo in ejemplos:
        corregido, valido = normalizar_correo(correo)
        logger.info(f"Original: {correo}")
        logger.info(f"Corregido: {corregido} {'✓' if valido else '✗'}\n")


def preparar_datos_para_bd(resultado: Dict[str, Any]) -> Dict[str, Any]:
    """Prepara los datos extraídos en formato adecuado para BD."""
    datos_bd = {
        # Datos del cliente
        'cliente': {
            'nombre': resultado['datos_generales'].get('Nombrecliente'),
            'ruc_cedula': resultado['datos_generales'].get('Ruc'),
            'direccion': resultado['datos_generales'].get('Direccion_factura'),
            'direccion_instalacion': resultado['datos_generales'].get('direccioninstalacion'),
            'ciudad': resultado['datos_generales'].get('Ciudad'),
            'correo': resultado['datos_generales'].get('Correo'),
            'telefono': resultado['datos_generales'].get('Telefono')
        },
        # Datos del contrato
        'contrato': {
            'codigo': resultado['datos_generales'].get('codigocontrato'),
            'fecha_contrato': resultado['datos_generales'].get('Fecha_contrato'),
            'fecha_entrega': resultado['datos_generales'].get('Fecha_entrega'),
            'observacion': resultado['datos_generales'].get('observacion')
        },
        # Datos de facturación
        'facturacion': {
            'subtotal': resultado['datos_generales'].get('subtotal'),
            'iva': resultado['datos_generales'].get('total_impuestos'),
            'total': resultado['datos_generales'].get('total_final'),
            'abono': resultado['datos_generales'].get('abono'),
            'saldo_pendiente': resultado['datos_generales'].get('saldo_pendiente')
        },
        # Datos de pago
        'pago': {
            'banco': resultado['datos_generales'].get('Banco'),
            'numero_cheque': resultado['datos_generales'].get('Numerocheque')
        },
        # Datos de responsables
        'responsables': {
            'operario': resultado['datos_generales'].get('Operario'),
            'responsable_medicion': resultado['datos_generales'].get('Resp_Medicion')
        },
        # Lista de productos
        'productos': resultado['productos'],
        # Validaciones y advertencias
        'validacion': {
            'advertencias': resultado['advertencias'],
            'campos_faltantes': resultado['faltantes']
        }
    }

    return datos_bd


def mostrar_datos_bd(datos_bd: Dict[str, Any]):
    """Muestra los datos estructurados listos para BD."""
    logger.info('\n===== DATOS ESTRUCTURADOS PARA BD =====\n')

    # Cliente
    logger.info('=== TABLA: clientes ===')
    for k, v in datos_bd['cliente'].items():
        logger.info(f"{k}: {v}")

    # Contrato
    logger.info('\n=== TABLA: contratos ===')
    for k, v in datos_bd['contrato'].items():
        logger.info(f"{k}: {v}")

    # Facturación
    logger.info('\n=== TABLA: facturacion ===')
    for k, v in datos_bd['facturacion'].items():
        logger.info(f"{k}: {v}")

    # Pago
    logger.info('\n=== TABLA: pagos ===')
    for k, v in datos_bd['pago'].items():
        logger.info(f"{k}: {v}")

    # Responsables
    logger.info('\n=== TABLA: responsables ===')
    for k, v in datos_bd['responsables'].items():
        logger.info(f"{k}: {v}")

    # Productos
    logger.info('\n=== TABLA: productos ===')
    for i, producto in enumerate(datos_bd['productos'], 1):
        logger.info(f"\nProducto {i}:")
        for k, v in producto.items():
            logger.info(f"  {k}: {v}")

    # Validación
    if datos_bd['validacion']['advertencias']:
        logger.info('\n=== Advertencias de validación ===')
        for adv in datos_bd['validacion']['advertencias']:
            logger.warning(f"- {adv}")


def guardar_datos_json(datos: Dict[str, Any], nombre_archivo: str):
    """Guarda los datos estructurados en un archivo JSON."""
    try:
        # Asegurar que el nombre del archivo termine en .json
        if not nombre_archivo.endswith('.json'):
            nombre_archivo += '.json'

        with open(nombre_archivo, 'w', encoding='utf-8') as f:
            json.dump(datos, f, indent=2, ensure_ascii=False)
        logger.info(f"\nDatos guardados exitosamente en: {nombre_archivo}")
    except Exception as e:
        logger.error(f"Error al guardar datos en JSON: {e}")


def test_validar_fecha():
    """Pruebas para la función validar_fecha."""
    casos_prueba = [
        ("12 dia/08 mes 2024. año", "12/08/2024"),
        ("12/08 mes 2024 año", "12/08/2024"),
        ("12/08/2024", "12/08/2024"),
        ("2024-08-12", "12/08/2024"),
        ("texto inválido", "texto inválido"),
    ]

    for entrada, esperado in casos_prueba:
        resultado, es_valido = validar_fecha(entrada)
        if resultado != esperado:
            print(
                f"Error en caso '{entrada}': esperado '{esperado}', obtenido '{resultado}'")
        else:
            print(f"✓ Caso '{entrada}' validado correctamente")


def main():
    parser = argparse.ArgumentParser(
        description='Extrae datos de una imagen de factura usando Google Document AI.')
    parser.add_argument(
        'file', help='Ruta al archivo de imagen (jpeg) de la factura')
    parser.add_argument(
        '--output', '-o', help='Archivo de salida para guardar los datos en formato JSON')
    parser.add_argument('--format', '-f', choices=['text', 'json', 'both'], default='both',
                        help='Formato de salida: text (solo texto), json (solo JSON), both (ambos)')
    args = parser.parse_args()

    # Validar que el archivo de entrada tenga una extensión de imagen válida
    if not args.file.lower().endswith(('.jpg', '.jpeg', '.png')):
        logger.error(
            "Error: El archivo debe ser una imagen (jpg, jpeg, o png)")
        sys.exit(1)

    # Validar coherencia entre argumentos
    if args.format == 'json' and not args.output:
        # Si el formato es json, asignar un nombre de archivo por defecto
        args.output = f"factura_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        logger.info(f"Se guardará el resultado en: {args.output}")

    try:
        config = setup_environment()
        etiquetas = cargar_etiquetas()
        resultado = process_document(args.file, config, etiquetas)

        # Preparar datos para BD
        datos_bd = preparar_datos_para_bd(resultado)

        # Mostrar resultados según el formato especificado
        if args.format in ['text', 'both']:
            imprimir_factura(resultado)
            mostrar_datos_bd(datos_bd)

        # Guardar en JSON si se especificó un archivo de salida o si el formato es json
        if args.output or args.format == 'json':
            nombre_archivo = args.output or f"factura_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
            guardar_datos_json(datos_bd, nombre_archivo)

    except FileNotFoundError as e:
        logger.error(f"Error: No se encontró el archivo: {e}")
        sys.exit(1)
    except EnvironmentError as e:
        logger.error(f"Error de configuración: {e}")
        sys.exit(1)
    except Exception as e:
        logger.exception("Error al ejecutar el procesamiento de la factura")
        sys.exit(1)


if __name__ == '__main__':
    # Modos de prueba
    if len(sys.argv) > 1:
        if sys.argv[1] == '--test-email':
            logger.info("Ejecutando pruebas de validación de correos...")
            probar_correo()
            sys.exit(0)
        elif sys.argv[1] == '--test':
            logger.info("Ejecutando pruebas de validación de fechas...")
            test_validar_fecha()
            sys.exit(0)
        elif sys.argv[1].startswith('--test'):
            logger.error(f"Modo de prueba no reconocido: {sys.argv[1]}")
            sys.exit(1)

    # Modo normal de operación
    main()
