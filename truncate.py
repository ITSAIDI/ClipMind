from moviepy import AudioFileClip, VideoFileClip


def trucate_audio(input_path: str, output_path: str, start: int, end : int):
    audio = AudioFileClip(input_path)
    truncated = audio.subclipped(start, end)
    truncated.write_audiofile(output_path)

def truncate_video(input_path: str, output_path: str, start: int, end: int):
    video = VideoFileClip(input_path)
    truncated = video.subclipped(start, end)
    truncated.write_videofile(output_path)

 
# trucate_audio("audios/01.wav", "audios/011.wav", 0, 10)
truncate_video("videos/01.mp4", "videos/010.mp4", 20*60, 30*60)


# uv run python truncate.py