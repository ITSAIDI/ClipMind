import streamlit as st
import uuid 
from utils.extracting import clean_directory, segmenting, extracting, ranking, trimming
from utils.editing import apply_edits
from utils.publishing import *
from pathlib import Path


UPLOAD_DIR = "data/videos"
SEGMENTS_DIR = "data/segments"
SHORTS_DIR = "data/shorts"
CANDIDATES_FILE = "data/jsons/all_candidates.json"
OUTPUT_FILE  = "data/jsons/output.json"


st.set_page_config(layout="wide")
st.title("ClipMind Tool")

clean_directory(UPLOAD_DIR)

uploaded_file = st.file_uploader(
    "Upload a video",
    type=["mp4"]
)

if uploaded_file:
    unique_filename = f"{uuid.uuid4().hex[:3]}.mp4"
    file_path = UPLOAD_DIR + f"/{unique_filename}"
    with open(file_path, "wb") as f:
        while chunk := uploaded_file.read(1024 * 1024): # This writes the file in 1MB chunks and is much better for huge uploads
            f.write(chunk)

    st.success(f"Video saved successfully to {file_path}")
    
    st.header("1. Content understanding")

    st.subheader("1.1 Segmenting video")
    # clean_directory(SEGMENTS_DIR)    
    # segmenting(input_path = file_path, output_dir= SEGMENTS_DIR)
    st.success("Segmenting complete")
    
    st.subheader("1.2 Extracting candidates")
    # extracting(segments_dir= SEGMENTS_DIR, video_path= file_path, output_path= CANDIDATES_FILE)
    st.success("Extracting complete")

    st.subheader("1.3 Ranking candidates")
    # ranking(candidates_path= CANDIDATES_FILE, output_path= OUTPUT_FILE)
    st.success("Ranking complete")

    st.subheader("1.4 Trimming")
    # clean_directory(SHORTS_DIR)
    # trimming(output_path= OUTPUT_FILE, shorts_dir= SHORTS_DIR)
    st.success("Trimming complete")

    st.header("2. Editing")
    
    shorts = list(Path(SHORTS_DIR).glob("*.mp4"))

    with st.form("editing_form"):
        selected = st.selectbox("Select short", shorts, format_func=lambda x: x.name, width= 200)

        col1, col2, col3, col4 = st.columns(4)

        with col1:
            do_reframing = st.checkbox("Reframing", value=True)

        with col2:
            do_captioning = st.checkbox("Captioning", value=True)

        with col3:
            do_audio = st.checkbox("Audio Mixing", value=True)

        with col4:
            do_enhancing = st.checkbox("Enhancing", value=True)

        btn1, btn2, spacer = st.columns([1, 1, 7])

        with btn1:
            edit_clicked = st.form_submit_button("✏️ Edit")

        with btn2:
            publish_clicked = st.form_submit_button("🚀 Publish")

    if edit_clicked:
        apply_edits(
            str(selected),
            do_reframing,
            do_captioning,
            do_audio,
            do_enhancing
        )
    if publish_clicked:
        short_metadata = get_metadata(id= selected.stem, output_file= OUTPUT_FILE)
        publish(short_path= str(selected), metadata= short_metadata)

    shorts_per_row = 3
    for i in range(0, len(shorts), shorts_per_row):
        cols = st.columns(shorts_per_row)
        row_shorts = shorts[i:i + shorts_per_row]

        for col, video in zip(cols, row_shorts):
            with col:
                st.caption(video.name)
                st.video(str(video))              




    