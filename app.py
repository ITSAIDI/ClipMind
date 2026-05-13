import streamlit as st
import uuid 


UPLOAD_DIR = "data/videos"

st.title("ClipMind Tool")

uploaded_file = st.file_uploader(
    "Upload a video",
    type=["mp4"]
)

if uploaded_file is not None:
    unique_filename = f"{uuid.uuid4().hex[:3]}.mp4"
    file_path = UPLOAD_DIR + f"/{unique_filename}"
    with open(file_path, "wb") as f:
        while chunk := uploaded_file.read(1024 * 1024): # This writes the file in 1MB chunks and is much better for huge uploads
            f.write(chunk)

    st.success(f"Video saved successfully to {file_path}")
        

