from google import genai
from google.genai import types
from dotenv import load_dotenv
import os
import time
import json
import uuid
from pathlib import Path
import subprocess
from utils.config import *
import streamlit as st


load_dotenv(dotenv_path= DOT_ENV_FILE)
client = genai.Client(api_key=os.getenv("GEMINI_API_KEY")) # Client object created once, when the module utils.py is loaded.

def segmenting(input_path: str, output_dir: str, segment_length: int = SEGMENT_DURATION):
    """
    This function divides an input long video into segments
    and saves them temporarily into a directory.

    Args:
        input_path (str): long video file system path
        output_dir (str): directory for the segments to be saved
        segment_length (int): segment duration in seconds
    """

    os.makedirs(output_dir, exist_ok=True)

    output_pattern = os.path.join(output_dir, "%d.mp4")

    command = [
        "ffmpeg",
        "-hide_banner",
        "-loglevel", "error",
        "-i", input_path,
        "-c", "copy",
        "-map", "0",
        "-f", "segment",
        "-segment_time", str(segment_length),
        "-reset_timestamps", "1",
        output_pattern
    ]
    with st.spinner("ffmpeg is segmenting..."):
        subprocess.run(command, check=True)

def parse_timestamp(timestamp: str) -> int:

    parts = [part for part in timestamp.split(":") if part != ""]
    if len(parts) != 2:
        raise ValueError(f"Invalid timestamp format: {timestamp}. Expected MM:SS")

    minutes, seconds = parts
    try:
        minutes = int(minutes)
        seconds = int(seconds)
    except ValueError:
        raise ValueError(f"Invalid timestamp format: {timestamp}. Expected MM:SS")

    if minutes < 0 or seconds < 0 or seconds >= 60:
        raise ValueError(f"Invalid timestamp value: {timestamp}. Seconds must be 0-59")

    return minutes * 60 + seconds

def trimming(output_path: str, shorts_dir: str) -> None:
    """
    Clip and save the selected N shorts.

    Args:
        output_path (str): json file system path of the final selected shorts
        shorts_dir (str): Where to save the shorts
    """
    os.makedirs(shorts_dir, exist_ok=True)

    with open(output_path, "r") as f:
        output = json.load(f)

    with st.spinner("ffmpeg is trimming..."):
        for item in output:
            start_seconds = parse_timestamp(item["start"])
            end_seconds = parse_timestamp(item["end"])

            if end_seconds <= start_seconds:
                raise ValueError("end_timestamp must be greater than start_timestamp")

            duration = end_seconds - start_seconds
            clip_path = os.path.join(shorts_dir, f"{item['clip_id']}.mp4")

            command = [
                "ffmpeg",
                "-hide_banner",
                "-loglevel", "error",
                "-ss", str(start_seconds),
                "-i", item["segment_path"],
                "-t", str(duration),
                "-c", "copy",
                clip_path
            ]

            subprocess.run(command, check=True)
            print(f"{clip_path} saved")
        
def parse_response(response_text: str) -> list[dict]:
    try:
        return json.loads(response_text)
    except json.JSONDecodeError as e:
        raise ValueError("Parsing failed ", e)

def vlm_top_clips(segment_path: str) -> str:
    """ 
        VLM determines the top k clips from a segment of the long video.
        Besides to scoring the engagement and other metrics for each clip.

        Args:
            segment_path (str): The segment file system path

        Returns:
            str : VLM structured response as a list of dictionaries inside a string.
        
        Example:
            >>> vlm_top_clips("temp/0.mp4", k=1)
            [
                {
                    "start": "00:45",
                    "end": "01:30",

                "scores": {
                    "hook": 8.5,
                    "emotion": 7.5,
                    "engagement": 9.0,
                    },

                "features": {
                        "has_question": false,
                        "has_surprise": true,
                        "has_contrast": true,
                        "speaker_energy": "high",
                        "title": "AI will replace most jobs",
                        "summary": "Speaker claims AI will eliminate many jobs in the next decade",
                        "hashtags": ["#Shorts", "#AI", "#Tech"],
                    },
                    
                    "hook_text": "first compelling sentence or phrase",
                    "reason": "Strong controversial claim with high emotional and viral potential",

                },
            ]  
    """
    
    start = time.time()
    video_file = client.files.upload(file= segment_path)

    while video_file.state.name == "PROCESSING": # type: ignore
        print('.', end='', flush=True)
        time.sleep(5)
        video_file = client.files.get(name=video_file.name) # type: ignore

    if video_file.state.name == "FAILED": # type: ignore
        raise ValueError(video_file.state.name) # type: ignore
    
    response = client.models.generate_content(
        model= MODEL_NAME,
        config=types.GenerateContentConfig(system_instruction= VLM_SYS_PROMPT, media_resolution= VLM_MEDIA_RESOLUTION), #type:ignore
        contents=[video_file],
    )

    end = time.time()
    print(f"\n {segment_path} proceeded in {(end - start):.2f} seconds")
    return response.text # type: ignore

def ranking(candidates_path: str, output_path: str):
    """
        An LLM model ranks all candidates (clips) and determines the top-n shorts. The result then saved localy.

        Args:
            candidates_path (str): file system path of the candidates (json file).
            output_path (str): file system path of the ranking result (json file).

        Example:
            >>> llm_ranking(candidates_path= "jsons/all_candidates.json", output_path= "jsons/output.json")
            [
                {
                    "clip_id": "f08592df",
                    "rank": 1,
                    "score": 9.8,
                    "reason": "Blunt 'No' response creates an instant, high-retention hook for viewers."
                }
            ]
    """
    
    json_part = types.Part.from_bytes(
    data= open(candidates_path, "rb").read(),
    mime_type= "application/json")

    with st.spinner("LLM is ranking..."):
        response = client.models.generate_content(
            model= MODEL_NAME,
            config=types.GenerateContentConfig(system_instruction= LLM_SYS_PROMPT),
            contents=[json_part],
        )
    if response.text:
        parsed_data = parse_response(response.text)
        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(parsed_data, f, indent=2)
            st.write(f"\n {output_path} saved")
            
        adding_keys(llm_output_path= output_path, vlm_output_path= candidates_path)
    else :
        st.error("No response from LLM")

def extracting(segments_dir: str, video_path: str, output_path: str):
    """
    This function iterates through all video segments in a directory, sends each to a VLM model
    for clip extraction, enriches the results with metadata, and saves all candidates to a JSON file.

    Args:
        segments_dir (str): Directory containing video segments files (.mp4).
        video_path (str): File system path of the original long-form video.
        output_path (str): File system path where the JSON file with all candidates will be saved.

    Returns:
        None. Saves the results to output_path as a JSON file containing a list of candidate clips
        with VLM scores, features, metadata, and unique clip IDs.

    Example:
        >>> get_all_candidates("temp/segments", "video.mp4", "jsons/all_candidates.json")
    """
    segments = os.listdir(segments_dir)
    all_candidates = []
    progress_bar = st.progress(0)
    status_text = st.empty()

    for idx, segment_name in enumerate(segments):
        segment_path =  str(Path(segments_dir) / segment_name) 
        parsed_data = parse_response(vlm_top_clips(segment_path))
        # print(parsed_data)
        for item in parsed_data:
            item["video_path"] = video_path
            item["segment_path"] = segment_path
            item["clip_id"] = str(uuid.uuid4().hex[:4])

        all_candidates.extend(parsed_data)

        progress =  (idx + 1) / len(segments)
        progress_bar.progress(progress)
        status_text.text(f"Processing segment {segment_name} : {progress*100:.2f} %")

    st.write(f"Total number of candidates: {len(all_candidates)}")

    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(all_candidates, f, indent=2)

    st.write(f"{output_path} get saved")

def clean_directory(directory_path: str) -> None:
    """
    Delete all files directly inside the given directory.

    Args:
        directory_path (str): Path to the directory to clean.

    Raises:
        FileNotFoundError: If the directory does not exist.
        NotADirectoryError: If the path is not a directory.
    """
    directory = Path(directory_path)

    if not directory.exists():
        raise FileNotFoundError(f"Directory not found: {directory_path}")
    if not directory.is_dir():
        raise NotADirectoryError(f"Not a directory: {directory_path}")

    deleted_files = 0

    for path in directory.iterdir():
        if path.is_file():
            path.unlink()
            deleted_files += 1

    st.write(f"Deleted {deleted_files} files from {directory_path}")

def adding_keys(llm_output_path : str, vlm_output_path: str):
    """Merge ranking results with some extracting data and overwrite the final result file.
    Args:
        llm_output_path (str): Path to the JSON file containing ranked clip results.
        vlm_output_path (str): Path to the JSON file containing VLM clip metadata.
    """
    st.write(f"Updating {llm_output_path}")

    with open(llm_output_path, "r") as f:
        llm_output = json.load(f)    

    with open(vlm_output_path, "r") as f:
        vlm_output = json.load(f)  
    
    results = []
    selected_keys = {"start", "end", "features", "video_path", "segment_path"}

    for a in llm_output:    
        for b in vlm_output:
            if a["clip_id"] == b["clip_id"]:
                break
        a.update({k: v for k, v in b.items() if k in selected_keys}) #type:ignore
        results.append(a)

    with open(llm_output_path, "w") as f:
        json.dump(results, f, indent= 2)
        st.write(f"{llm_output_path} saved")

# def display_shorts(shorts_dir :str):
#     videos = list(Path(shorts_dir).glob("*.mp4"))
#     videos_per_row = 3

#     for i in range(0, len(videos), videos_per_row):
#         cols = st.columns(videos_per_row)

#         row_videos = videos[i:i + videos_per_row]

#         for col, video in zip(cols, row_videos):
#             with col:
#                 st.video(str(video))
#                 st.caption(video.name)