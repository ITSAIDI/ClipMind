import os
import pickle
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload
from typing import TypedDict

class metadataType(TypedDict):
    title: str
    description : str
    tags: list[str]
    categoryId: str


SCOPES = ["https://www.googleapis.com/auth/youtube.upload"]


def publishing(short_path: str, metadata: metadataType)->None:
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

    if os.path.exists("token.pickle"):
        with open("token.pickle", "rb") as token:
            credentials = pickle.load(token)

    if not credentials or not credentials.valid:
        if credentials and credentials.expired and credentials.refresh_token:
            credentials.refresh(Request())
        else:
            flow = InstalledAppFlow.from_client_secrets_file(
                "client_secret.json",
                SCOPES
            )
            credentials = flow.run_local_server(port=8080)

        with open("token.pickle", "wb") as token:
            pickle.dump(credentials, token)

    youtube = build("youtube", "v3", credentials=credentials)
    request_body = {"snippet": metadata} # public video by default
    media_file = MediaFileUpload(short_path, chunksize= 2*1024*1024, resumable=True)
    request = youtube.videos().insert(part="snippet", body=request_body, media_body=media_file)

    response = request.execute()

    print("Video uploaded ID:", response["id"])