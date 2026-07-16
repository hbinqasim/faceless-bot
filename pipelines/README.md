# Vice Studio GTA 6 Pipeline

This folder contains a single runner for the GTA 6 production pipeline.

## Runner

```bash
/Users/hbinqasim/Projects/faceless-bot/venv/bin/python pipelines/gta6_pipeline.py
```

The runner uses `sys.executable`, so it executes every step with the same Python interpreter used to start the pipeline.

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
