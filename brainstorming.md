# Idea 
- The idea is developing a tool to automate shorts creation from input videos , editing and publish on Youtube
# High Level pipeline

```mermaid
flowchart TD
    A(Ingestion) --> B(Content Understanding) --> C(Clipping) --> D(Editing) --> E(Metadata Generation) --> F(Publishing)

    linkStyle default stroke:#ffff,stroke-width:2px

```

- Based on my little research about the best length for Youtube shorts, I found the best duration is between **15s-30s**, so you can maximize the watching-time in order to get more viewers.

## Ingestion 
 
The input is a video file in mp4 format *(youtube video, TV show episode...)*

## Content understanding 

### First approach 
- Using a VLM that understand visual content and decide the epic moment(s) of the video. The most generous provider until now is Google Refer to [her](https://aistudio.google.com/rate-limit?timeRange=last-1-day&project=ai-shorts-tool-493100) for rate limits details.
- I tested **gemini-3-flash-preview** to summarize a 10 min interview video, and it performed very well. **gemini-3.1-flash-lite-preview** is also an option with high RPD **(of 500)**, but to be honest the summary of **gemini-3-flash-preview** is better.
- In the both previous models the context window is **250k** token. A video of 30 min consumed **172k** token, but the model hallucinate **( it repeated 4 same sentences hhh)** that was expected because of the huge context, so I think the **10 min** is suitable for the model capability.

#### First Workflow

```mermaid
flowchart TD
    A(Long Video Input) --> B(Split into 10 min segments)

    B --> C1(Segment 1)
    B --> C2(Segment 2)
    B --> C3(...)

    C1 --> D1(VLM Summarize)
    C2 --> D1(VLM Summarize)
    C3 --> D1(VLM Summarize)

    D1 --> E(Collect Summaries)

    E --> F(LLM Select Best Segment)

    F --> G(VLM Analyze Selected Segment)

    G --> H(Start, End, Why)

    linkStyle default stroke:#ffff,stroke-width:2px
    style A fill:#FEC671
    style H fill:#81C2E0
```

❌ Weak summary could hide an epic short.
❌ Summaries lack hook moments (emotions, surprise...)

#### Second Workflow

```mermaid
flowchart TD
    A(Long Video Input) --> B(Split into 10 min Segments)

    B --> C1(Segment 1)
    B --> C2(Segment 2)
    B --> C3(...)

    C1 --> D1(VLM Top-K Clips + Scoring)
    C2 --> D1(VLM Top-K Clips + Scoring)
    C3 --> D1(VLM Top-K Clips + Scoring)

    D1 --> E(LLM Global Ranking)

    E --> F(Final Top N Clips Output)


    linkStyle default stroke:#ffff,stroke-width:2px
    style A fill:#FEC671
    style F fill:#81C2E0
```
#### Video's quality

Higher resolutions improve the model's ability to read fine text or identify small details, but increase token usage and latency. [Blog](https://ai.google.dev/gemini-api/docs/tokens#media-resolutions)

I used the lowest quality for Gemini input *(divisions of original video)* to minimize the context length, which is about **55k** tokens including all input *(sys prompt, prompt, segment)* and for my case model's ability was not affected. 

The problem is we should not clip the final shorts from these segments because quality is low for Youtube or other platforms. 

The solution is **[Media_resolution](https://ai.google.dev/gemini-api/docs/media-resolution)** config parameter, that determines the maximum number of tokens allocated per video frame. Using that i can use hight resolution segments with low tokens allocations, but good quality shorts.

I mapped the extracted timestamps to values in the original video using the segment_rank and duration.

### Second approach 
- Speech extraction
- Speech to Text 
- LLM determines the epic moments.

#### Speech To text
- Choosing the right ASR model based on this [open_asr_leaderboard](https://huggingface.co/spaces/hf-audio/open_asr_leaderboard)
- The most accurate model regards to the leaderboard is [Cohere-transcribe](https://huggingface.co/CohereLabs/cohere-transcribe-03-2026), which has the lowest average WER *(Word error rate)*, and a good inference-speed (RTFx).
- This model on a CPU with an audion of **15s** it took **90s** to return the transcription. But with T4 it takes only **2s**, a 10 min audio took **25s**, regards accuracy the model done very well.

