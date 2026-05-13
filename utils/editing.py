from google import genai
from google.genai import types
from dotenv import load_dotenv
import os
import time
import json
import subprocess
import tempfile
import random 
from config import *

load_dotenv(dotenv_path= DOT_ENV_FILE)
client = genai.Client(api_key=os.getenv("GEMINI_API_KEY"))


def get_video_resolution(video_path):
    """Return the width and height of a video file.

    Args:
        video_path (str): Path to the input video file.

    Returns:
        tuple[int, int]: The video width and height in pixels.

    Raises:
        ValueError: If the ffprobe output cannot be parsed or the expected
            stream data is missing.
    """

    command = [
        "ffprobe",
        "-v", "error",
        "-select_streams", "v:0",
        "-show_entries", "stream=width,height",
        "-of", "json",
        video_path
    ]

    result = subprocess.run(
        command,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True
    )

    data = json.loads(result.stdout)

    width = data["streams"][0]["width"]
    height = data["streams"][0]["height"]

    return width, height

def apply_reframing(input_file : str, save_path : str, x_list : list, new_width: int, new_height: int, fps : int ) -> None:
    """Create a vertically cropped video using a second-by-second crop path.

    This function generates a temporary segment for each second of the input video,
    applies a horizontal crop that transitions smoothly between consecutive x
    coordinates, and then concatenates the segments into a single output file.

    Args:
        input_file (str): Path to the source video file.
        save_path (str): Path where the final cropped output video will be saved.
        x_list (list): List of per-second x coordinates for the crop window.
        new_width (int): Width of the output crop window.
        new_height (int): Height of the output crop window.
        fps (int, optional): Frame rate to apply to each cropped segment. Defaults to 29.

    Returns:
        None
    """
    
    with tempfile.TemporaryDirectory() as tmpdir:
        segments = []

        for i in range(len(x_list) - 1):
            x0 = x_list[i]
            x1 = x_list[i + 1]

            seg_path = os.path.join(tmpdir, f"seg_{i:03d}.mp4")
            segments.append(seg_path)

            # build smooth expression for this second
            x_interpolated = f"{x0}+({x1}-{x0})*(t-{i})"
            subprocess.run([
                "ffmpeg",
                "-y",
                "-hide_banner",
                "-loglevel", "error",
                "-i", input_file,
                "-ss", str(i),
                "-t", "1",
                "-vf", f"crop={new_width}:{new_height}:{x_interpolated}:0,fps={fps}",
                seg_path
            ])

        list_file = os.path.join(tmpdir, "list.txt")

        with open(list_file, "w") as f:
            for seg in segments:
                f.write(f"file '{seg}'\n")
        # concatination 
        subprocess.run([
            "ffmpeg",
            "-y",
            "-hide_banner",
            "-loglevel", "error",
            "-f", "concat",
            "-safe", "0",
            "-i", list_file,
            "-c:v", "libx264",
            "-crf", "18",
            "-preset", "ultrafast",
            "-c:a", "aac",
            save_path
        ])    

def apply_captioning(input_file : str, save_path : str, captions_path: str)-> None:
    """Burn an ASS subtitle file into a video using ffmpeg.

    Args:
        input_file (str): Path to the source video file.
        save_path (str): Path where the final video with burned-in captions will be saved.
        captions_path (str): Path to the `.ass` subtitle file to apply.

    Returns:
        None
    """

    ffmpeg_command = [
        "ffmpeg",
        "-hide_banner",
        "-loglevel", "error",
        "-i", input_file,
        "-vf", f"ass={captions_path}",
        "-c:v", "libx264",
        "-crf", "18",
        "-preset", "ultrafast",
        "-c:a", "copy",
        "-y",
        save_path
    ]

    subprocess.run(ffmpeg_command)

def enhancing(short_path : str, output_path : str)-> None:
    """Apply brightness, contrast, and sharpness adjustments to a video.

    This function applies a series of video enhancement filters to improve
    visual quality, including brightness/contrast correction, saturation boost,
    sharpening, and noise reduction.

    Args:
        input_file (str): Path to the source video file.
        save_path (str): Path where the enhanced output video will be saved.

    Returns:
        None
    """
    start = time.time()
    print("Apply visual enhancements")

    cmd = [
        "ffmpeg",
        "-hide_banner",
        "-loglevel", "error",
        "-i", short_path,
        "-vf", "eq=brightness=0.05:contrast=1.2:saturation=1.3:gamma=1.05,unsharp=5:5:1.0,hqdn3d",
        "-c:v", "libx264",
        "-crf", "18",
        "-preset", "ultrafast",
        "-c:a", "copy",
        "-y",
        output_path
    ]
    subprocess.run(cmd)

    end = time.time()
    print(f"\n {output_path} saved, reframing time (s) : {(end-start):.2f}")

def reframing(short_path : str, output_path: str, ratio : float = 9/16, fps : int = 25 ) -> None:
    """Generate a horizontal crop path and apply vertical reframing to a video.

    This function uploads the source video to a VLM, requests a smooth
    horizontal crop path for a vertical target aspect ratio, get the
    coordinates from the model, and then applies the crop to produce a vertically
    reframed output video.

    Args:
        short_path (str): Path to the source horizontal video.
        output_path (str): Path where the reframed vertical video will be saved.
        ratio (float, optional): Target aspect ratio width/height for the cropped
            vertical video. Defaults to 9/16.
        fps (int, optional): Frame rate for the generated output video. Defaults
            to 25.

    Returns:
        None
    """
    start = time.time()

    width, height = get_video_resolution(short_path)

    print("\n VLM is searching for best reframing path...")
    video_file = client.files.upload(file= short_path)
    
    while video_file.state.name == "PROCESSING": # type: ignore
        print('.', end='', flush=True)
        time.sleep(5)
        video_file = client.files.get(name=video_file.name) # type: ignore

    if video_file.state.name == "FAILED": # type: ignore
        raise ValueError(video_file.state.name) # type: ignore
    
    response = client.models.generate_content(
        model= MODEL_NAME,
        config=types.GenerateContentConfig(
            system_instruction= REFRAMING_SYS_PROMPT.format(
                original_width= width, 
                original_height= height, 
                target_width= int(height*ratio),
                target_height= height,
                duration_seconds= SHORT_DURATION ), 
    
            media_resolution= VLM_MEDIA_RESOLUTION), #type:ignore
        contents=[video_file],
    )
    x_coordinates = json.loads(response.text) #type:ignore

    print("\n apply reframing...")
    apply_reframing(input_file= short_path, save_path= output_path, x_list= x_coordinates, 
                   new_height= height, new_width= int(height*ratio), fps= fps)
    
    end = time.time()
    print(f"\n {output_path} saved, reframing time (s) : {(end-start):.2f}")
    
def captioning(short_path : str, output_path: str, ass_path: str = "captions.ass") -> None:
    """Generate captions for a video and burn them into the output file.

    This function uploads the source video to the VLM, requests a styled ASS
    subtitle script, saves the returned subtitle text to disk, then applies the
    ASS file to the video using ffmpeg.

    Args:
        short_path (str): Path to the source video file.
        output_path (str): Path where the final video with burned-in captions will be saved.
        ass_path (str, optional): Path where the generated `.ass` subtitle file will be written.
            Defaults to "captions.ass".

    Returns:
        None
    """
    start = time.time()

    print("\n VLM is generating styled captions...")
    video_file = client.files.upload(file= short_path)

    while video_file.state.name == "PROCESSING": # type: ignore
        print('.', end='', flush=True)
        time.sleep(5)
        video_file = client.files.get(name=video_file.name) # type: ignore

    if video_file.state.name == "FAILED": # type: ignore
        raise ValueError(video_file.state.name) # type: ignore
    
    response = client.models.generate_content(
        model= MODEL_NAME,
        config=types.GenerateContentConfig(system_instruction= CAPTIONING_SYS_PROMPT, 
                                           media_resolution= VLM_MEDIA_RESOLUTION), #type:ignore
        contents=[video_file],
    )

    if not response.text:
        raise ValueError("Caption model returned empty response")

    with open(ass_path, "w", encoding="utf-8") as f:
        f.write(response.text)

    print("\n apply captioning...")
    apply_captioning(input_file= short_path, save_path= output_path, captions_path= ass_path)

    end = time.time()
    print(f"\n {output_path} saved, captioning time (s) : {(end-start):.2f}")

def audio_mixing(short_path : str, output_path : str, music_dir: str = "music")-> None:

    start = time.time()

    files = [
        os.path.join(music_dir, f)
        for f in os.listdir(music_dir)
        if os.path.isfile(os.path.join(music_dir, f))
    ]

    music_file = random.choice(files)

    print(f"\n Adding {music_file}...")

    cmd = [
            "ffmpeg",
            "-hide_banner",
            "-loglevel", "error",
            "-i", short_path,
            "-i", music_file,
            "-filter_complex",
            "[1:a]volume=0.04[a1];[0:a][a1]amix=inputs=2:duration=first:dropout_transition=2",
            "-c:v", "copy",
            "-c:a", "aac",
            "-y",
            output_path
        ]
    subprocess.run(cmd, check=True)

    end = time.time()
    print(f"\n {output_path} saved, audio_mixing time (s) : {(end-start):.2f}")

    

