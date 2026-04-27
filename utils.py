from moviepy import VideoFileClip
from google import genai
from google.genai import types
from dotenv import load_dotenv
import os
import time
import json
import uuid
from pathlib import Path


load_dotenv()
client = genai.Client(api_key=os.getenv("GEMINI_API_KEY")) # Client object created once, when the module utils.py is loaded.
K_VALUE = 3
N_VALUE = 3
DURATION = 30
MODEL_NAME = "gemini-3-flash-preview" 
VLM_SYS_PROMPT = f"""
    You are an expert video content analyst specialized in identifying highly engaging short-form clips from long videos.

    Your task is to analyze a video segment and extract the TOP-{K_VALUE} most engaging short clips suitable for short-form platforms (e.g., Shorts, Reels, TikTok).

    You must return ONLY a valid JSON array of clip objects. No explanations, no extra text.

    ----------------------------------------
    OBJECTIVE
    ----------------------------------------
    From the given video segment:

    1. Identify the most engaging, high-retention, and potentially viral moments.
    2. Each selected clip must:
    - Be understandable without external context (standalone).
    - Contain a strong hook within the first few seconds.
    - Have clear boundaries (do not cut mid-sentence or mid-thought).
    - Duration **{DURATION} seconds** .

    3. Return the TOP-{K_VALUE} clips ranked by overall quality.

    ----------------------------------------
    OUTPUT FORMAT (STRICT)
    ----------------------------------------
    Return a JSON array:

    [
    
        "start": "MM:SS",
        "end": "MM:SS",
        "reason": "1 short sentence explaining why this clip is strong",

        "scores": 
            "hook": number (0-10),
            "engagement": number (0-10),
            "emotion": number (0-10),
        ,

        "features": 
            "has_question": boolean,
            "has_surprise": boolean,
            "has_contrast": boolean,
            "speaker_energy": "low" | "medium" | "high",
            "hook_text": "first compelling sentence or phrase",
            "title": "short catchy title (max 12 words)",
            "summary": "1 sentence describing the clip",
            "hashtags": List of strong hashtags good for SEO starting always by #Shorts ,
         
    ]

    ----------------------------------------
    SCORING GUIDELINES
    ----------------------------------------
    - hook: Strength of the first 3 seconds
    - engagement: Likelihood to retain viewer attention
    - emotion: Emotional intensity (surprise, excitement, fear, etc.)

    ----------------------------------------
    SELECTION RULES
    ----------------------------------------
    - Avoid overlapping clips unless absolutely necessary
    - Prefer diverse topics if multiple good clips exist
    - Do not select redundant clips
    - If unsure, include 1 “underrated” clip with high potential
    - Avoid clustering all scores in 7–9.

    ----------------------------------------
    CRITICAL CONSTRAINTS
    ----------------------------------------
    - Output ONLY JSON
    - No trailing commas
    - No comments
    - No markdown
    - No explanations

    ----------------------------------------
    FAILURE CONDITIONS (AVOID)
    ----------------------------------------
    - Do not return fewer than {K_VALUE} clips unless no valid clips exist
    - Do not include vague summaries
    - Do not give identical scores to all clips
    - Do not exceed {DURATION} seconds per clip
"""

LLM_SYS_PROMPT = f"""
    You are an expert content strategist specializing in short-form video optimization.

    Your task is to rank and select the best clips for short-form content (Shorts, Reels, TikTok) from a list of candidate clips.

    ----------------------------------------
    OBJECTIVE
    ----------------------------------------
    Select the TOP-{N_VALUE} clips that:
    - Maximize virality and engagement
    - Have strong hooks in the first seconds
    - Are diverse in topic (avoid redundancy)

    ----------------------------------------
    INPUT DESCRIPTION
    ----------------------------------------
    Each clip contains:
    - clip_id: unique identifier
    - start, end: timestamps
    - title: short hook/title
    - summary: short description
    - scores: numeric signals (0–10) from a prior model:
    - hook: strength of first seconds
    - engagement: retention potential
    - emotion: emotional intensity

    You must use these signals but NOT copy them directly.

    ----------------------------------------
    SELECTION RULES
    ----------------------------------------
    - Prioritize: hook > engagement > standalone
    - Prefer clips with strong emotional or surprising elements
    - Avoid selecting clips with similar topics
    - Avoid overlapping timestamps
    - If two clips are similar, select the stronger one
    - Penalize weak hooks and low standalone clarity

    ----------------------------------------
    OUTPUT FORMAT (STRICT JSON)
    ----------------------------------------
    Return a JSON array of selected clips:

    [
    
        "clip_id": "string",
        "rank": number,
        "score": number,
        "reason": "string"
    
    ]

    ----------------------------------------
    FIELD DEFINITIONS
    ----------------------------------------

    clip_id:
    - Must exactly match one of the input clip IDs
    - Used to reference the selected clip

    rank:
    - Integer starting from 1
    - 1 = best clip
    - Must be unique and sequential

    score:
    - A NEW overall score (0–10)
    - Represents final global quality after comparing all clips
    - Must NOT be copied directly from input scores
    - Should reflect:
    - hook strength
    - engagement
    - standalone 
    - overall appeal
    - Use full range (avoid clustering all scores between 8–10)

    reason:
    - Short explanation (max 15 words)
    - Explain WHY the clip ranks highly

    ----------------------------------------
    CONSTRAINTS
    ----------------------------------------
    - Output ONLY valid JSON
    - No markdown
    - No explanations outside JSON
    - No trailing commas
    - Do not include clips not present in input
    - Do not return more than {N_VALUE} clips

    ----------------------------------------
    FAILURE CONDITIONS (AVOID)
    ----------------------------------------
    - Do not assign identical scores to all clips
    - Do not ignore diversity
    - Do not select overlapping clips
    - Do not produce vague reasons
"""

def get_segments(input_path: str, output_dir: str, segment_length: int = 600):
    """ 
        This function divides an input long video into 10 min segments,
        saved then temporary into a diractory.

        Args:
            input_path (str): long video file sytem path
            output_dir (str):  diractory for the segments
            segment_length (int) : segment duration in seconds
    """
    
    with VideoFileClip(input_path) as video:
        duration = video.end # Duration in seconds
        num_segments = int(duration//segment_length)

        for i in range(num_segments):
            segment = video.subclipped(i*segment_length, (i+1)*segment_length)
            segment_path = os.path.join(output_dir,f"{i}.mp4")
            segment.write_videofile(segment_path)

        remained_segment = video.subclipped(num_segments*segment_length, duration)
        remained_segment.write_videofile(os.path.join(output_dir,f"{i+1}.mp4")) # type: ignore

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

def clip_segment(segment_path: str, start_timestamp: str, end_timestamp: str, output_path: str) -> None:
    """
    Clip a segment file between two timestamp strings and save it to the given output file path.

    Args:
        segment_path (str): Path to the input segment video file.
        start_timestamp (str): Start time as a string like "MM:SS".
        end_timestamp (str): End time as a string like "MM:SS".
        output_path (str): Full file path where the clipped video is saved.
    """
    
    start_seconds = parse_timestamp(start_timestamp)
    end_seconds = parse_timestamp(end_timestamp)

    if end_seconds <= start_seconds:
        raise ValueError("end_timestamp must be greater than start_timestamp")

    output_file = Path(output_path)
    output_file.parent.mkdir(parents=True, exist_ok=True)

    with VideoFileClip(segment_path) as video:
        clip = video.subclipped(start_seconds, end_seconds)
        clip.write_videofile(str(output_file))

    print(f"Saved clipped video to {output_file}")

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

    video_file = client.files.upload(file= segment_path)

    while video_file.state.name == "PROCESSING": # type: ignore
        print('.', end='', flush=True)
        time.sleep(5)
        video_file = client.files.get(name=video_file.name) # type: ignore

    if video_file.state.name == "FAILED": # type: ignore
        raise ValueError(video_file.state.name) # type: ignore

    response = client.models.generate_content(
        model= MODEL_NAME,
        config=types.GenerateContentConfig(system_instruction= VLM_SYS_PROMPT),
        contents=[video_file],
    )
    return response.text # type: ignore

def llm_ranking(candidates_path: str, output_path: str):
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

    print("\n LLM is ranking...")
    response = client.models.generate_content(
        model= MODEL_NAME,
        config=types.GenerateContentConfig(system_instruction= LLM_SYS_PROMPT),
        contents=[json_part],
    )
    if response.text:
        parsed_data = parse_response(response.text)
        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(parsed_data, f, indent=2)
            print(f"\n {output_path} saved")
    else :
        print("No response from LLM")

def get_all_candidates(segments_dir: str, video_path: str, output_path: str):
    segments = os.listdir(segments_dir)
    all_candidates = []

    for segment_name in segments:
        segment_path =  str(Path(segments_dir) / segment_name) 
        print(f"\n VLM processing segment: {segment_name}")
        parsed_data = parse_response(vlm_top_clips(segment_path))
        
        for item in parsed_data:
            item["video_path"] = video_path
            item["segment_path"] = segment_path
            item["clip_id"] = str(uuid.uuid4().hex[:8])

        all_candidates.extend(parsed_data)
        print(f"\n Total number of candidates: {len(all_candidates)}")
 
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(all_candidates, f, indent=2)
        print(f"\n {output_path} saved")

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

    print(f"Deleted {deleted_files} files from {directory_path}")



