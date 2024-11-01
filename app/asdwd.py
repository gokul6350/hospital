import base64
import requests

# Function to convert WAV file to Base64

def wav_to_base64(file_path):
    with open(file_path, 'rb') as wav_file:
        audio_data = wav_file.read()
    return base64.b64encode(audio_data).decode('utf-8')

# Convert your local audio file to Base64
base64_string = wav_to_base64("C:/Users/PLC/Downloads/123.wav")

# Prepare the request payload
payload = {
    "modelName": "parakeet",
    "file": base64_string
}

# Set the headers
headers = {
    "content-type": "application/json",
    "Host": "parakeet-batch-new-isvc.stable-diffusion.krutrim.com",
    "Authorization": "TbHFitCF_jWL945NJ19fcY1nzO"
}

# Set the API endpoint
url = "http://cloud.olakrutrim.com/v1/audio/transcriptions"

# Make the request
response = requests.post(url=url, json=payload, headers=headers)

# Print the response
print(response.text)