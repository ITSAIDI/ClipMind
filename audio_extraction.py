from moviepy import VideoFileClip

def extract_audio(video_path : str, audio_path: str):
    """
    Extracts and saves an audio file from the given video
    """
    
    with  VideoFileClip(filename= video_path) as video:
        if video.audio:
            video.audio.write_audiofile(filename = audio_path)
            
            
# extract_audio(video_path= "videos/01.mp4", audio_path="audios/01.wav" )