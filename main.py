from utils import get_segments, get_all_candidates, llm_ranking, clean_directory, clip_shorts, merge_results


# get_segments(input_path="videos/03.mp4", output_dir= "segments")
get_all_candidates(segments_dir= "segments", video_path= "videos/03.mp4", output_path= "jsons/all_candidates.json")
llm_ranking(candidates_path= "jsons/all_candidates.json", output_path= "jsons/output.json")
merge_results(llm_output_path= "jsons/output.json", vlm_output_path= "jsons/all_candidates.json")
clip_shorts(output_path= "jsons/output.json", shorts_dir= "shorts")

# clean_directory(directory_path= "segments")
# clean_directory(directory_path= "shorts")


