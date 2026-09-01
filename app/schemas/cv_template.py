import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, HttpUrl

from app.models.cv_template import CVTemplateLayoutKey


class CVTemplateSummary(BaseModel):
    id: uuid.UUID
    name: str
    layout_key: CVTemplateLayoutKey

    model_config = ConfigDict(from_attributes=True)


class CVTemplatePublic(CVTemplateSummary):
    description: str | None
    thumbnail_url: HttpUrl | None
    is_featured: bool


class CVTemplateCatalogResponse(BaseModel):
    items: list[CVTemplatePublic]

