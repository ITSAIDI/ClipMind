from utils import get_segments, get_all_candidates, llm_ranking, clean_directory, parse_timestamp


get_segments(input_path="videos/03.mp4", output_dir= "segments")
# get_all_candidates(segments_dir= "segments", video_path= "videos/03.mp4", output_path= "jsons/all_candidates.json")
# llm_ranking(candidates_path= "jsons/all_candidates.json", output_path= "jsons/output.json")
# clean_directory(directory_path= "segments")

# print(parse_timestamp(timestamp="01:30"))