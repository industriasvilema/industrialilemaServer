gcloud iam service-accounts create docai-service-account   --display-name="Document AI Service Account"
# Asigna permisos:
gcloud projects add-iam-policy-binding industrialvilemagc   --member="serviceAccount:docai-service@industrialvilemagc.iam.gserviceaccount.com"   --role="roles/documentai.user"
gcloud projects add-iam-policy-binding industrialvilemagc   --member="serviceAccount:docai-service@industrialvilemagc.iam.gserviceaccount.com"   --role="roles/documentai.apiUser"
gcloud iam service-accounts list
gcloud projects add-iam-policy-binding industrialvilemagc   --member="serviceAccount:docai-service-account@industrialvilemagc.iam.gserviceaccount.com"   --role="roles/documentai.apiUser"
gcloud iam service-accounts keys create ~/docai-key.json   --iam-account=docai-service-account@industrialvilemagc.iam.gserviceaccount.com
gcloud documentai processors list   --project=industrialvilemagc   --location=us
gcloud iam service-accounts keys create credentials.json   --iam-account=docai-service-account@industrialvilemagc.iam.gserviceaccount.com
gcloud components install beta
gcloud beta documentai processors list   --project=industrialvilemagc   --location=us
gcloud services enable documentai.googleapis.com
gcloud documentai processors list --location=us
sudo apt-get install google-cloud-cli-documentai
credentials.json
industriasvilema@cloudshell:~ (industrialvilemagc)$ credentials.json
-bash: credentials.json: command not found
industriasvilema@cloudshell:~ (industrialvilemagc)$ 
ls -l credentials.json
credentials.json
industriasvilema@cloudshell:~ (industrialvilemagc)$ ls -l credentials.json
-rw------- 1 industriasvilema industriasvilema 2390 Jun  2 16:03 credentials.json
ls -l credentials.json
