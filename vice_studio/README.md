# Vice Studio Core

**Vice Studio Core** is the central configuration and knowledge system for all Vice Studio AI agents. It serves as the single source of truth for visual identity, camera language, character consistency, branding, verified knowledge, and universal prompt rules.

---

## Purpose

Instead of each agent inventing its own styles, hardcoding values, or duplicating rules, all agents read from Vice Studio Core. This ensures:

- **Consistency**: All content shares unified visual and narrative language
- **Scalability**: New channels can be added without rewriting agent code
- **Maintainability**: Update styles, branding, or rules in one place
- **Quality**: Centralized expertise and best practices
- **Reusability**: Agents can adapt to new niches by reading different config files

---

## Directory Structure

```
vice_studio/
├── styles/
│   ├── gta6.json           # GTA 6 visual identity
│   ├── football.json       # Sports broadcast aesthetic
│   ├── hockey.json         # Fast-paced action sports
│   ├── marvel.json         # Superhero cinematic style
│   └── ai.json             # Technology/AI focused content
├── characters/
│   └── gta6.json           # Jason & Lucia character profiles
├── cameras/
│   └── default.json        # Camera presets (establishing, drone, dialogue, etc.)
├── motion/
│   └── default.json        # Motion presets (slow_push, dolly, orbit, etc.)
├── branding/
│   └── gta6.json           # Brand guidelines, voice, typography, CTA
├── knowledge/
│   └── gta6.md             # Verified GTA VI facts from official sources
├── prompts/
│   ├── image_rules.md      # Universal image generation rules
│   ├── script_rules.md     # Universal scriptwriting rules
│   └── README.md           # This file
```

---

## Detailed Folder Descriptions

### 1. `styles/`

Production configurations for each niche/channel. Each file contains:

- **channel**: Channel identifier
- **visual_style**: Description of visual aesthetic
- **aspect_ratio**: 9:16 for Shorts/Reels
- **camera**: Primary camera system (ARRI Alexa 65, etc.)
- **lens**: Lens specification (Anamorphic, Standard, etc.)
- **fps**: Frame rate (24, 30, 60, etc.)
- **lighting**: Lighting approach and mood
- **weather**: Typical weather/environmental conditions
- **color_grade**: Color grading approach (orange-teal, etc.)
- **rendering_style**: Photorealistic, CGI blend, minimalist, etc.
- **quality**: Resolution and quality target (4K, etc.)
- **atmosphere**: Overall mood and feeling
- **environment**: Setting and location types
- **negative_prompt**: What to avoid in generation

**Files**: `gta6.json`, `football.json`, `hockey.json`, `marvel.json`, `ai.json`

**Used by**: Image generation agents, prompt engineering agents, cinematographer agents

---

### 2. `characters/`

Character profiles for consistent appearances across content. Each file contains:

- **name**: Character name
- **age**: Character age
- **build**: Physical build (athletic, lean, muscular, etc.)
- **height**: Character height
- **hair**: Hair description and color
- **facial_hair**: Facial hair specifics (if applicable)
- **clothing**: Typical wardrobe and style
- **accessories**: Distinctive accessories
- **personality**: Personality traits
- **appearance_notes**: Additional appearance details
- **consistency_notes**: Guidelines for maintaining consistency

**Files**: `gta6.json` (Jason and Lucia profiles)

**Used by**: Image generation agents, animation agents, character consistency checks

---

### 3. `cameras/`

Reusable camera presets for different shot types. Each preset defines:

- **shot_type**: Type of shot (establishing, close-up, tracking, etc.)
- **camera**: Camera system to use
- **lens**: Specific lens recommendation
- **framing**: How to frame the subject
- **movement**: Camera movement description
- **duration**: Typical duration for this shot
- **stabilization**: How to stabilize the camera

**Presets included**:
- `establishing`: Wide establishing shots
- `drone`: Aerial perspective
- `dialogue`: Medium shots for conversation
- `action`: Dynamic action shots
- `tracking`: Following the subject
- `cinematic`: Master shots with compression
- `closeup`: Extreme close-up detail shots

**Files**: `default.json`

**Used by**: Cinematographer agents, director agents, shot composition agents

---

### 4. `motion/`

Reusable motion/animation presets. Each preset defines:

- **zoom**: Focal length or scale changes
- **rotation**: Rotational movement
- **movement**: Primary directional movement
- **easing**: Animation easing curve
- **duration**: How long the motion takes

**Presets included**:
- `slow_push`: Forward push with tension building
- `dolly`: Horizontal lateral tracking
- `orbit`: Circular motion around subject
- `drone_fly`: Aerial movement (up, down, lateral)
- `zoom`: Optical zoom without camera movement
- `handheld`: Handheld camera with subtle shake
- `whip_pan`: Rapid transition pan between subjects

**Files**: `default.json`

**Used by**: Animation agents, cinematographer agents, motion graphics agents

---

### 5. `branding/`

Channel and brand guidelines including:

- **channel_name**: Official channel name
- **channel_tagline**: Short tagline/description
- **voice_style**: Brand voice characteristics
- **narration_style**: How the narrator should sound
- **thumbnail_style**: Thumbnail design guidelines
- **intro_style**: Video introduction style
- **outro_style**: Video conclusion style and CTA
- **CTA**: Call-to-action script
- **color_palette**: Brand colors (hex codes)
- **logo_usage**: Where and how to use logo
- **typography**: Font recommendations
- **music_style**: Musical identity
- **editing_pace**: Editing speed and style
- **platform_priorities**: Which platforms to optimize for

**Files**: `gta6.json`

**Used by**: All agents for brand consistency, narrator agents, editor agents

---

### 6. `knowledge/`

Stable, verified information for each channel. Contains ONLY:

✅ **Official information**:
- Developer/publisher
- Official announcements
- Verified character names
- Official release information
- Published facts from Rockstar Newswire

❌ **Does NOT contain**:
- Rumors or leaks
- Speculation
- Community theories
- Unconfirmed information

**Files**: `gta6.md`

**Used by**: Script agents, fact-checker agents, knowledge agents for ground truth

---

### 7. `prompts/`

Universal rules shared by all content generation agents.

#### `image_rules.md`

Comprehensive guidelines for image generation including:
- Cinematic framing and composition
- Photorealism standards
- Lighting design principles
- Vertical 9:16 specifics
- Safety and compliance rules (no logos, UI, real celebrities)
- Character consistency requirements
- Environment authenticity
- Color grading and technical standards

**Used by**: Image director agents, cinematographer agents, prompt engineer agents

#### `script_rules.md`

Comprehensive guidelines for script writing including:
- Hook and opening strategies
- Factual accuracy requirements
- Concise narration (7-9 lines)
- Language and tone
- Content rules (no speculation presented as fact)
- Ending and CTA structure
- Platform optimization (YouTube Shorts, TikTok Reels, Instagram Reels)
- Common mistakes to avoid

**Used by**: Script agents, narrator agents, prompt engineers

---

## How Agents Should Use Vice Studio Core

### Image Generation Agent Example

```python
import json

# Load style configuration
config = json.load(open("vice_studio/styles/gta6.json"))

# Build prompt using style values
prompt = f"""
Create a photorealistic {config['visual_style']} scene 
shot with {config['camera']} using {config['lens']} lenses,
{config['lighting']}, with {config['color_grade']} color grading,
capturing the {config['atmosphere']} of {config['environment']}.
Avoid: {config['negative_prompt']}
"""
```

### Script Agent Example

```python
# Load knowledge for factual grounding
knowledge = open("vice_studio/knowledge/gta6.md").read()

# Use knowledge in script
script = f"""
{knowledge_based_hook}
[factual content from vice_studio/knowledge/gta6.md]
Follow for more GTA 6 breakdowns.
"""

# Follow script rules from vice_studio/prompts/script_rules.md
```

### Character Consistency Example

```python
import json

# Load character profile
characters = json.load(open("vice_studio/characters/gta6.json"))

for character in characters["characters"]:
    desc = f"{character['name']} is {character['age']}, "
    desc += f"{character['build']}, with {character['hair']} hair. "
    desc += f"Consistency notes: {character['consistency_notes']}"
```

### Camera Preset Example

```python
import json

# Load camera presets
cameras = json.load(open("vice_studio/cameras/default.json"))

# Get establishing shot preset
establishing = cameras["presets"]["establishing"]
prompt = f"Use {establishing['camera']} with {establishing['lens']}"
```

---

## Adding a New Channel

To add support for a new niche/channel:

1. **Create `styles/[channel].json`** with visual configuration
   - camera, lens, lighting, color_grade, atmosphere for the niche

2. **Create `characters/[channel].json`** (if character-driven content)
   - Character profiles with consistent appearance guidelines

3. **Create `branding/[channel].json`**
   - Voice, CTA, color palette, typography for the brand

4. **Create `knowledge/[channel].md`**
   - Verified facts and official information for the niche

5. **Update agent code** to read from these files:
   ```python
   style = json.load(open(f"vice_studio/styles/{channel}.json"))
   ```

---

## Scalability Benefits

### Before Vice Studio Core

- Each agent hardcoded values (ARRI Alexa, orange-teal grade, etc.)
- No character consistency across agents
- Duplicate rules in multiple agents
- Hard to maintain or update
- Agents weren't reusable across channels

### After Vice Studio Core

- All agents read from `vice_studio/styles/[channel].json`
- Characters stored in `vice_studio/characters/[channel].json`
- Rules centralized in `vice_studio/prompts/`
- One place to update entire channel
- Agents easily adapt to new channels by swapping config files

---

## Integration Checklist for New Agents

When developing a new Vice Studio agent, it should:

- [ ] Read from `vice_studio/styles/[channel].json` for visual config
- [ ] Reference `vice_studio/characters/[channel].json` for consistency
- [ ] Follow rules in `vice_studio/prompts/image_rules.md` (if image-related)
- [ ] Follow rules in `vice_studio/prompts/script_rules.md` (if script-related)
- [ ] Use verified information from `vice_studio/knowledge/[channel].md`
- [ ] Apply settings from `vice_studio/branding/[channel].json`
- [ ] Document which config files it depends on
- [ ] Allow channel selection via config or argument

---

## Maintenance & Updates

### Updating Styles

If color grading needs to change across all GTA content:

1. Edit `vice_studio/styles/gta6.json`
2. All agents reading this file automatically get the update
3. No need to modify individual agents

### Updating Knowledge

If official GTA VI information is released:

1. Add to `vice_studio/knowledge/gta6.md`
2. All agents using this knowledge automatically access it
3. No agent code changes needed

### Updating Rules

If script best practices evolve:

1. Update `vice_studio/prompts/script_rules.md`
2. Review agent code for rule compliance
3. Share update with team via PR or changelog

---

## Quick Reference: Config File Locations

| Purpose | Location | Used By |
|---------|----------|---------|
| Visual style | `styles/[channel].json` | Image, cinematographer, director agents |
| Characters | `characters/[channel].json` | Image, animation, consistency agents |
| Camera presets | `cameras/default.json` | Cinematographer, director agents |
| Motion presets | `motion/default.json` | Animation, motion graphics agents |
| Brand guidelines | `branding/[channel].json` | All agents for consistency |
| Verified facts | `knowledge/[channel].md` | Script, fact-checker agents |
| Image rules | `prompts/image_rules.md` | All image generation agents |
| Script rules | `prompts/script_rules.md` | All script/narration agents |

---

## Vision

Vice Studio Core is the foundation for scalable, consistent, high-quality content generation. Every Vice Studio agent should:

1. **Read from shared configuration** instead of inventing values
2. **Respect character consistency** using centralized profiles
3. **Follow universal rules** for quality and safety
4. **Use verified knowledge** for factual accuracy
5. **Maintain brand identity** through centralized branding

As Vice Studio grows to more channels and niches, the core system ensures consistency, quality, and maintainability across all content.
