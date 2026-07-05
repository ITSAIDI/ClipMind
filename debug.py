from utils.extracting import vlm_top_clips, parse_response

response = vlm_top_clips("./data/segments/4.mp4")
print(response)
print(parse_response(response))