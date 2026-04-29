from google import genai
from google.genai import types
from dotenv import load_dotenv
import os
import time
import json
import uuid
from pathlib import Path
import subprocess

load_dotenv()
client = genai.Client(api_key=os.getenv("GEMINI_API_KEY")) # Client object created once, when the module utils.py is loaded.
K_VALUE = 2
N_VALUE = 3
SEGMENT_DURATION = 600 # seconds
SHORT_DURATION = 30 # seconds
VLM_MEDIA_RESOLUTION = types.MediaResolution.MEDIA_RESOLUTION_LOW
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
    - Duration **{SHORT_DURATION} seconds** .

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
    - Do not exceed {SHORT_DURATION} seconds per clip
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

def get_segments(input_path: str, output_dir: str, segment_length: int = SEGMENT_DURATION):
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
        "-i", input_path,
        "-c", "copy",
        "-map", "0",
        "-f", "segment",
        "-segment_time", str(segment_length),
        "-reset_timestamps", "1",
        output_pattern
    ]

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

def clip_shorts(output_path: str, shorts_dir: str) -> None:
    """
    Clip and save the selected N shorts.

    Args:
        output_path (str): json file system path of the final selected shorts
        shorts_dir (str): Where to save the shorts
    """

    # We have to map these timestamps to values in the original video 
    # stimestamp = 02:23 in segment 1 <=> timestamp = 12:23 in original video, means + segment_rank*SEGMENT_DURATION
        
    # match= re.search(r"segments\\(\d+)\.mp4$", item["segment_path"])
    # segment_rank= int(match.group(1)) #type:ignore
    # start_seconds+= segment_rank*SEGMENT_DURATION
    # end_seconds+= segment_rank*SEGMENT_DURATION

    os.makedirs(shorts_dir, exist_ok=True)

    with open(output_path, "r") as f:
        output = json.load(f)

    for item in output:
        start_seconds = parse_timestamp(item["start"])
        end_seconds = parse_timestamp(item["end"])

        if end_seconds <= start_seconds:
            raise ValueError("end_timestamp must be greater than start_timestamp")

        duration = end_seconds - start_seconds
        clip_path = os.path.join(shorts_dir, f"{item['clip_id']}.mp4")

        command = [
            "ffmpeg",
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
        config=types.GenerateContentConfig(system_instruction= VLM_SYS_PROMPT, media_resolution= VLM_MEDIA_RESOLUTION),
        contents=[video_file],
    )

    end = time.time()
    print(f"\n {segment_path} proceeded in {(end - start):.2f} seconds")
    # print(response)
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

def merge_results(llm_output_path : str, vlm_output_path: str):
    """Merge ranking results with vlm data and overwrite the final result file.
    Args:
        llm_output_path (str): Path to the JSON file containing ranked clip results.
        vlm_output_path (str): Path to the JSON file containing VLM clip metadata.
    """

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
        print(f"{llm_output_path} saved")