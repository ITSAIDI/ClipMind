from moviepy import AudioFileClip

audio = AudioFileClip("audios/01.wav")
truncated = audio.subclipped(0, 600)
truncated.write_audiofile("audios/020.wav")

# uv run python truncate.py