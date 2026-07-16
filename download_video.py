import os
import requests
from dotenv import load_dotenv

load_dotenv()

API_KEY = os.getenv("PIXABAY_API_KEY")

search_url = "https://pixabay.com/api/videos/"

params = {
    "key": API_KEY,
    "q": "nature",
    "per_page": 3,
    "orientation": "vertical"
}

response = requests.get(search_url, params=params)
data = response.json()

video = data["hits"][0]
video_url = video["videos"]["medium"]["url"]

print("Downloading:", video_url)

video_data = requests.get(video_url)

with open("assets/background.mp4", "wb") as file:
    file.write(video_data.content)

print("Downloaded to assets/background.mp4")
