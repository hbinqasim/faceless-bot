import os
import requests
from dotenv import load_dotenv

load_dotenv()

API_KEY = os.getenv("PIXABAY_API_KEY")

def search_and_download_video(query):

    url = "https://pixabay.com/api/videos/"

    params = {
        "key": API_KEY,
        "q": query,
        "per_page": 5
    }

    response = requests.get(url, params=params)
    data = response.json()

    if not data["hits"]:
        raise Exception(f"No videos found for {query}")

    video_url = data["hits"][0]["videos"]["medium"]["url"]

    video_data = requests.get(video_url)

    with open("assets/background.mp4", "wb") as file:
        file.write(video_data.content)

    return "assets/background.mp4"
