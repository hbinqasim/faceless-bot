import os
import requests
from dotenv import load_dotenv

load_dotenv()

API_KEY = os.getenv("PIXABAY_API_KEY")

url = "https://pixabay.com/api/videos/"

params = {
    "key": API_KEY,
    "q": "nature",
    "per_page": 3
}

response = requests.get(url, params=params)

data = response.json()

print("Total videos found:", len(data["hits"]))

for video in data["hits"]:
    print(video["id"])
