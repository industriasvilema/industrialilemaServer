# Parte Inicial, Configuración del servidor

## Activar entorno

Python 3.10.16

### En macOS/Linux

source .venv/bin/activate

### En Windows

.venv\Scripts\activate

## Instalar las dependencias

pip install -r requirements.txt

## Parte 1: Construir la Imagen Docker

docker build --platform linux/amd64 -t gcr.io/industrialvilemagc/industrialvilemagcdocker:latest .

## Parte 2: Subir la Imagen Docker a Google Container Registry (GCR)

gcloud auth login

gcloud auth configure-docker

## Parte 3: Empujar la imagen Docker al Container Registry

docker tag gcr.io/industrialvilemagc/industrialvilemagcdocker:latest gcr.io/industrialvilemagc/industrialvilemagcdocker:latest

docker push gcr.io/industrialvilemagc/industrialvilemagcdocker:latest

## Parte 4: Subir la Imagen Docker al Bucket de Google Cloud Storage

gsutil cp industrialvilemagcdocker.tar gs://industrialvilema-docker-images/

docker save industrialvilemagc/industrialvilemagcdocker:latest > industrialvilemagcdocker.tar

## Parte 5: Desplegar la Imagen Docker en Google Cloud

gcloud run deploy --image gcr.io/industrialvilemagc/industrialvilemagcdocker:latest --platform managed --region us-central1 --allow-unauthenticated

## Parte 6: Verificación

gcloud run services list

## PASOS CORTOS PARA ACTUALIZACIÓN EN EL SERVIDOR

## 1. Construir la imagen en amd64

docker buildx build --platform linux/amd64 -t gcr.io/industrialvilemagc/industrialvilemagcdocker:latest .

## 🔄 2. Empujar la imagen corregida a GCR

docker push gcr.io/industrialvilemagc/industrialvilemagcdocker:latest

## 🚀 3. Desplegar en Google Cloud Run

gcloud run deploy --image gcr.io/industrialvilemagc/industrialvilemagcdocker:latest --platform managed --region us-central1 --allow-unauthenticated

## Nombre para el servicio en Google Cloud Run

industrialvilemagcdocker

## Run Server

python app.py

## Add config switch

gcloud auth list

gcloud config get-value project
