import requests

url = "https://8000-01kp3d2w8xvgd8t73ff8ebgdj5.cloudspaces.litng.ai/transcribe"

file_path = "audios/010.wav"

with open(file_path, "rb") as f:
    files = {"file": (file_path, f, "audio/wav")}
    response = requests.post(url, files=files)

print(response.json())