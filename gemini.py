from google import genai
from dotenv import load_dotenv
import os
import time

load_dotenv()

client = genai.Client(api_key=os.getenv("GEMINI_API_KEY"))

video_file = client.files.upload(file="videos/010.mp4")

while video_file.state.name == "PROCESSING":
    print('.', end='', flush=True)
    time.sleep(5)
    
    # refresh file status
    video_file = client.files.get(name=video_file.name)

if video_file.state.name == "FAILED":
    raise ValueError(video_file.state.name)

response = client.models.generate_content(
    model="gemini-3-flash-preview",
    contents=[
        video_file,
        "Select the epic **30** seconds of the video, best for Youtube shorts, it catches the eye and attention. Your response should include the start and the end of the segment besides to explaining why."
    ]
)

print(response.text)