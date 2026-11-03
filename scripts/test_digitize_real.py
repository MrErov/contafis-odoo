#!/usr/bin/env python3
"""Script aislado para probar el endpoint /digitize con la imagen real del talonario."""

import base64
import json
import os
import sys

import requests

# Configuración
BACKEND_URL = "http://127.0.0.1:8001/digitize"
IMAGE_PATH = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    "addons",
    "l10n_ve_compliance_manager",
    "tests",
    "fixtures",
    "talonario_factura_z_prueba.jpg"
)
# Token de API del usuario admin en Odoo (legacy X-User-Token)
USER_API_TOKEN = "b8b05ec5855f131cb43caece7818448441fe75e6"

def main():
    # Verificar que la imagen existe
    if not os.path.exists(IMAGE_PATH):
        print("Imagen no encontrada: " + IMAGE_PATH)
        return 1

    print("Imagen: " + IMAGE_PATH)
    print("Tamaño: " + str(os.path.getsize(IMAGE_PATH)) + " bytes")

    # Leer y codificar imagen
    with open(IMAGE_PATH, "rb") as f:
        img_b64 = base64.b64encode(f.read()).decode()

    print("Base64: " + str(len(img_b64)) + " caracteres")

    # Payload
    payload = {
        "image_base64": img_b64,
        "filename": "talonario_factura_z_prueba.jpg",
        "document_type": "auto"
    }

    print("\nEnviando POST a " + BACKEND_URL + "...")

    try:
        response = requests.post(
            BACKEND_URL,
            json=payload,
            timeout=180,  # 3 minutos para el modelo de visión
            headers={
                "Content-Type": "application/json",
                "X-User-Token": USER_API_TOKEN
            }
        )

        print("Status Code: " + str(response.status_code))

        if response.status_code == 200:
            data = response.json()
            print("\nRESPUESTA EXITOSA:")
            print(json.dumps(data, indent=2, ensure_ascii=False))

            # Análisis rápido
            extracted = data.get("extracted", {})
            print("\nCAMPOS EXTRAÍDOS:")
            for key, value in extracted.items():
                print("   " + key + ": " + str(value))

            print("\nConfianza: " + str(data.get("confidence", "N/A")))
            print("Tipo detectado: " + str(data.get("document_type", "N/A")))

            warnings = data.get("warnings", [])
            if warnings:
                print("\nAdvertencias (" + str(len(warnings)) + "):")
                for w in warnings:
                    print("   - [" + w.get("code", "") + "] " + w.get("message", "") + " (campo: " + str(w.get("field", "")) + ")")
            else:
                print("\nSin advertencias")

        else:
            print("\nERROR HTTP " + str(response.status_code) + ":")
            print(response.text)
            return 1

    except requests.exceptions.Timeout:
        print("\nTIMEOUT: El modelo de visión tardó demasiado (>180s)")
        return 1
    except requests.exceptions.ConnectionError:
        print("\nCONEXIÓN FALLIDA: No se puede conectar a " + BACKEND_URL + " (verifique que el backend esté corriendo en :8000)")
        return 1
    except Exception as e:
        print("\nERROR INESPERADO: " + str(e))
        return 1

    return 0

if __name__ == "__main__":
    sys.exit(main())
