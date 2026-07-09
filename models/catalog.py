from pydantic import BaseModel
from typing import Optional
from datetime import datetime
import uuid


class Loan(BaseModel):
    user: str
    checkout: str
    checkin: Optional[str] = None


class Book(BaseModel):
    id: str = ""
    title: str
    author: str = ""
    isbn: str = ""
    publisher: str = ""
    location_room: str = ""
    location_shelf: str = ""
    position: int = 0
    status: str = "available"
    verified: bool = False
    shelf_order: int = 0
    cover_url: str = ""
    snapped_cover: str = ""
    spine_crop: str = ""
    history: str = ""
    ocred_text: str = ""
    source_image: str = ""
    created_at: str = ""

    def model_post_init(self, __context):
        if not self.id:
            self.id = str(uuid.uuid4())
        if not self.created_at:
            self.created_at = datetime.now().isoformat()


class Shelf(BaseModel):
    name: str
    scan_images: list[str] = []


class Room(BaseModel):
    name: str
    shelves: dict[str, Shelf] = {}


class Catalog(BaseModel):
    rooms: dict[str, Room] = {}
    books: list[Book] = []
