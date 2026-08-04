# Vice Studio GTA 6 Pipeline

This folder contains separate runners for the GTA 6 Shorts and long-form pipelines.

## Shorts runner

```bash
/Users/hbinqasim/Projects/faceless-bot/venv/bin/python pipelines/gta6_pipeline.py
```

The runner uses `sys.executable`, so it executes every step with the same Python interpreter used to start the pipeline.

## Long-form runner

```bash
/Users/hbinqasim/Projects/faceless-bot/venv/bin/python pipelines/gta6_longform_pipeline.py
```

The long-form runner reuses the current agents with isolated configs under
`configs/gta6_longform/`. It produces a 16:9 video between 2 and 3 minutes,
downloads randomized horizontal Pixabay footage, avoids recently used Pixabay
IDs, builds a thumbnail from the video's own footage, and uploads it through
the existing YouTube account configuration.

To render without uploading:

```bash
/Users/hbinqasim/Projects/faceless-bot/venv/bin/python pipelines/gta6_longform_pipeline.py --no-upload
```

Long-form outputs are kept under `channels/gta6_longform/`, so the existing
`channels/gta6/` Shorts artifacts and configs are not overwritten.

## Order

1. `agents/research_agent/agent.py`
2. `agents/fact_checker/agent.py`
3. `agents/knowledge_agent/agent.py`
4. `agents/script_agent/agent.py`
5. `agents/storyboard_agent/agent.py`
6. `agents/cinematographer_agent/agent.py`
7. `agents/prompt_engineer_agent/agent.py`
8. `services/image_generation/service.py`
9. `services/animation/service.py`
10. `services/narration/service.py`
11. `services/video_composer/service.py`
12. `services/captions/service.py`

The pipeline stops at the first failed step because each step is run with `subprocess.run(..., check=True)`.

## Final Output

The completed captioned video is expected at:

```text
channels/gta6/videos/final/latest_video_captioned.mp4
```
