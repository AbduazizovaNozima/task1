from typing import Annotated

from fastapi import Depends, Request

from app.config import Settings
from app.container import Container
from app.services.ingestion import IngestionService
from app.services.search import SearchService


def get_container(request: Request) -> Container:
    container: Container = request.app.state.container
    return container


def get_settings(request: Request) -> Settings:
    settings: Settings = request.app.state.settings
    return settings


def get_search(container: Annotated[Container, Depends(get_container)]) -> SearchService:
    return container.search


def get_ingestion(container: Annotated[Container, Depends(get_container)]) -> IngestionService:
    return container.ingestion
