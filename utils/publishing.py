import os
import pickle
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload
from typing import TypedDict
from utils.config import SCOPES, PICKLE_FILE, CLIENT_SECRET_FILE
import json
import streamlit as st


class metadataType(TypedDict):
    title: str
    description : str
    tags: list[str]
    categoryId: str

def get_metadata(id :str, output_file :str) -> metadataType:
    with open(output_file, "r") as f:
        data = json.load(f)
    for item in data :
        if item["clip_id"] == id:
            return {"title" : item["features"]["title"],
                    "description" : item["features"]["hook_text"]+"\n"+item["features"]["summary"],
                    "tags" : item["features"]["hashtags"],
                    "categoryId" : "1"}
        
    raise ValueError(f"{id} not found or name wrong")

def publish(short_path: str, metadata: metadataType)->None:
    """
    Uploads a video file to YouTube using the YouTube Data API.

    The function authenticates the user using OAuth2 credentials stored
    in `token.pickle`. If credentials are missing or expired, a new
    authentication flow is started using `client_secret.json`.

    The video is uploaded with resumable chunked uploading.

    Args:
        short_path (str):
            Path to the video file to upload.

        metadata (metadataType):
            Dictionary containing YouTube video metadata such as:
            - title
            - description
            - tags
            - categoryId

    Returns:
        None
    """

    credentials = None

    with st.spinner(f"Uploading {short_path}..."):

        if os.path.exists(PICKLE_FILE):
            with open(PICKLE_FILE, "rb") as token:
                credentials = pickle.load(token)

        if not credentials or not credentials.valid:
            if credentials and credentials.expired and credentials.refresh_token:
                credentials.refresh(Request())
            else:
                flow = InstalledAppFlow.from_client_secrets_file(
                    CLIENT_SECRET_FILE,
                    SCOPES
                )
                credentials = flow.run_local_server(port=8080)

            with open(PICKLE_FILE, "wb") as token:
                pickle.dump(credentials, token)

        youtube = build("youtube", "v3", credentials=credentials)
        request_body = {"snippet": metadata} # public video by default
        media_file = MediaFileUpload(short_path, chunksize= 2*1024*1024, resumable=True)
        request = youtube.videos().insert(part="snippet", body=request_body, media_body=media_file)

        response = request.execute()

    st.success(f"Video uploaded ID: {response['id']}")
