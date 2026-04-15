from moviepy import AudioFileClip

audio = AudioFileClip("audios/01.wav")
truncated = audio.subclipped(0, 15)
truncated.write_audiofile("audios/010.wav")

# uv run python truncate.py