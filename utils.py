from moviepy import VideoFileClip
from google import genai
from google.genai import types
from dotenv import load_dotenv
import os
import time
import json



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
        remained_segment.write_videofile(os.path.join(output_dir,f"{i+1}.mp4"))

load_dotenv()
client = genai.Client(api_key=os.getenv("GEMINI_API_KEY")) # Client object created once, when the module utils.py is loaded.
K_VALUE = 3
DURATION = 30
MODEL_NAME = "gemini-3-flash-preview" 
SYS_PROMPT = f"""
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
        "title": "short catchy title (max 12 words)",
        "summary": "1 sentence describing the clip",
        ,

        "hook_text": "first compelling sentence or phrase",
        "reason": "1 short sentence explaining why this clip is strong",
    
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


def parse_vlm_response(response_text: str) -> list[dict]:
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
            list[dict]: VLM structured response as a list of dictionaries.
        
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
                    },
                    
                    "hook_text": "first compelling sentence or phrase",
                    "reason": "Strong controversial claim with high emotional and viral potential",

                },
            ]  
    """

    video_file = client.files.upload(file= segment_path)

    while video_file.state.name == "PROCESSING":
        print('.', end='', flush=True)
        time.sleep(5)
        video_file = client.files.get(name=video_file.name)

    if video_file.state.name == "FAILED":
        raise ValueError(video_file.state.name)

    response = client.models.generate_content(
        model= MODEL_NAME,
        config=types.GenerateContentConfig(system_instruction= SYS_PROMPT),
        contents=[video_file],
    )
    return response.text



response = parse_vlm_response(vlm_top_clips("temp/0.mp4"))
print(len(response))
print(response[0])


# get_segments("videos/01.mp4", "temp")