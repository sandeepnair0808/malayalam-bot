"""Data model for a generated reel story."""

from __future__ import annotations

from typing import List, Literal, Optional

from pydantic import BaseModel, Field

CameraMove = Literal["zoom_in", "zoom_out", "pan_left", "pan_right", "still"]


class Character(BaseModel):
    id: str = Field(description="short ascii id, e.g. 'ammachi', 'kid'")
    name_ml: str = Field(description="what the character is called in Malayalam, e.g. 'അമ്മൂമ്മ'")
    look: str = Field(
        description=(
            "fixed visual design in English used for every scene: age, skin tone, hair, "
            "clothes with exact colours, accessories (e.g. round glasses, gold bangle)"
        )
    )


class Scene(BaseModel):
    narration_ml: str = Field(description="voice-over line in natural spoken Malayalam (1-2 short sentences)")
    subtitle_ml: str = Field(description="on-screen Malayalam subtitle, max ~32 characters per line, max 2 lines")
    visual: str = Field(description="English description of what the illustration shows: who, pose, expression, setting")
    characters: List[str] = Field(description="ids of characters visible in the scene")
    action: str = Field(
        default="",
        description="English: how the characters move in this shot, e.g. 'walking left to right', "
        "'grandmother waves', 'boy jumps with joy', 'sitting still, breathing'",
    )
    speaker: Optional[str] = Field(
        default=None,
        description="id of the on-screen character whose words are spoken in this scene (their mouth "
        "moves with the voice); null when it is the off-screen narrator",
    )
    camera: CameraMove


class Story(BaseModel):
    title_ml: str
    title_en: str
    theme: str = Field(description="one-line English summary of the story's theme")
    setting: str = Field(description="English description of the recurring background/location and palette")
    characters: List[Character]
    scenes: List[Scene]
    caption_ml: str = Field(description="Instagram caption in Malayalam, 1-3 lines, emotional hook")
    hashtags: List[str] = Field(description="10-15 hashtags without the # sign, mix Malayalam-community and generic")

    def instagram_caption(self) -> str:
        tags = " ".join("#" + t.lstrip("#").replace(" ", "") for t in self.hashtags)
        return f"{self.caption_ml}\n\n{tags}".strip()
