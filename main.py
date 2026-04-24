from utils import get_all_candidates, llm_ranking

get_all_candidates(segments_dir= "temp", video_path= "videos/01.mp4", output_path= "jsons/all_candidates.json")
llm_ranking(candidates_path= "jsons/all_candidates.json", output_path= "jsons/output.json")





