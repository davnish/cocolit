from dataclasses import dataclass, field
from pathlib import Path
import streamlit as st
import numpy as np
from src.utils.download import TMStoGeoTIFF
from src.dal.feedback import FeedbackDAO
from PIL import Image, ImageDraw


@dataclass
class FeedBox:
    pos: str
    id_bounds: list = field(default_factory=list)

    def __post_init__(self) -> None:
        self.id = self.id_bounds[0]
        self.bounds = self.id_bounds[1]
        self.dir: Path = Path("data/feedback")
        self.dir.mkdir(parents=True, exist_ok=True)
        self.image_path = self.dir / f"{self.id}.tiff"

    def update_value(self, col: str) -> None:
        FeedbackDAO().update_by_id(self.id, col)

    def download(self) -> Image.Image:
        return TMStoGeoTIFF(self.image_path, bbox=self.bounds, return_image=True)

    def make_feedbox(self) -> None:
        """This makes the feedback boxes, shown the main."""
        if not self.image_path.exists():
            img = self.download()
        else:
            img = Image.open(self.image_path).convert("RGB")

        img_np = np.asarray(img)

        width, height = img_np.shape[:2]
        centroid = (width // 2, height // 2)

        draw = ImageDraw.Draw(img)
        draw.circle(centroid, radius=16, fill=None, outline=(255, 255, 0), width=1)

        st.image(img, use_container_width=True)

        yes_key = f"{self.pos}_yes"
        no_key = f"{self.pos}_no"
        bcol = st.columns(2)

        with bcol[0]:
            if st.button("Yes", key=yes_key, use_container_width=True, type="primary"):
                self.update_value("yes")

        with bcol[1]:
            if st.button("No", key=no_key, use_container_width=True):
                self.update_value("no")
