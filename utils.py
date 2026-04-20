from moviepy import VideoFileClip
import os

def get_segments(input_path: str, output_dir: str, segment_length: int = 600):
    """ This function divides an input long video into 10 min segments,
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


# get_segments("videos/01.mp4", "temp")