"""Nested folder operations scoped to a photographer event."""

from __future__ import annotations

from uuid import UUID

from sqlalchemy import delete, func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import ConflictError, NotFoundError
from app.models.folder import Folder
from app.models.photo import Photo
from app.schemas.folder import (
    CreateFolderRequest,
    FolderNode,
    FolderTreeResponse,
    UpdateFolderRequest,
)

MAX_FOLDER_DEPTH = 10


class FolderService:
    """Create, list, update, and delete folders for an event."""

    def __init__(self, db: AsyncSession) -> None:
        """Initialize with a database session."""
        self.db = db

    async def list_tree(self, event_id: UUID) -> FolderTreeResponse:
        """Return nested folders for an event."""
        result = await self.db.execute(select(Folder).where(Folder.event_id == event_id))
        folders = list(result.scalars().all())
        photo_counts = await self._photo_counts(event_id)
        nodes = {
            folder.id: FolderNode(
                id=folder.id,
                event_id=folder.event_id,
                parent_id=folder.parent_id,
                name=folder.name,
                sort_order=folder.sort_order,
                photo_count=photo_counts.get(folder.id, 0),
                created_at=folder.created_at,
                updated_at=folder.updated_at,
                children=[],
            )
            for folder in folders
        }
        roots: list[FolderNode] = []
        for folder in folders:
            node = nodes[folder.id]
            if folder.parent_id is None or folder.parent_id not in nodes:
                roots.append(node)
            else:
                nodes[folder.parent_id].children.append(node)
        for node in nodes.values():
            node.children.sort(key=lambda child: (child.sort_order, child.name))
        roots.sort(key=lambda child: (child.sort_order, child.name))
        return FolderTreeResponse(folders=roots)

    async def create_folder(self, event_id: UUID, request: CreateFolderRequest) -> FolderNode:
        """Create a folder under an optional parent."""
        if request.parent_id is not None:
            parent = await self._get_folder(event_id, request.parent_id)
            depth = await self._depth(parent) + 1
            if depth > MAX_FOLDER_DEPTH:
                raise ConflictError(f"Folder depth cannot exceed {MAX_FOLDER_DEPTH}")
        folder = Folder(
            event_id=event_id,
            parent_id=request.parent_id,
            name=request.name.strip(),
        )
        self.db.add(folder)
        try:
            await self.db.flush()
        except IntegrityError as exc:
            raise ConflictError("A folder with this name already exists at this level") from exc
        return FolderNode(
            id=folder.id,
            event_id=folder.event_id,
            parent_id=folder.parent_id,
            name=folder.name,
            sort_order=folder.sort_order,
            photo_count=0,
            created_at=folder.created_at,
            updated_at=folder.updated_at,
            children=[],
        )

    async def update_folder(
        self,
        event_id: UUID,
        folder_id: UUID,
        request: UpdateFolderRequest,
    ) -> FolderNode:
        """Rename, reorder, or reparent a folder without creating cycles."""
        folder = await self._get_folder(event_id, folder_id)
        if "parent_id" in request.model_fields_set:
            new_parent_id = request.parent_id
            if new_parent_id == folder.id:
                raise ConflictError("A folder cannot be its own parent")
            if new_parent_id is not None:
                await self._ensure_not_descendant(event_id, folder.id, new_parent_id)
                parent = await self._get_folder(event_id, new_parent_id)
                if await self._depth(parent) + 1 > MAX_FOLDER_DEPTH:
                    raise ConflictError(f"Folder depth cannot exceed {MAX_FOLDER_DEPTH}")
            folder.parent_id = new_parent_id
        if request.name is not None:
            folder.name = request.name.strip()
        if request.sort_order is not None:
            folder.sort_order = request.sort_order
        try:
            await self.db.flush()
        except IntegrityError as exc:
            raise ConflictError("A folder with this name already exists at this level") from exc
        counts = await self._photo_counts(event_id)
        return FolderNode(
            id=folder.id,
            event_id=folder.event_id,
            parent_id=folder.parent_id,
            name=folder.name,
            sort_order=folder.sort_order,
            photo_count=counts.get(folder.id, 0),
            created_at=folder.created_at,
            updated_at=folder.updated_at,
            children=[],
        )

    async def delete_folder(
        self, event_id: UUID, folder_id: UUID, delete_photos: bool = False
    ) -> None:
        """Delete a folder; photos are set NULL via FK, or deleted if requested."""
        folder = await self._get_folder(event_id, folder_id)

        if delete_photos:
            descendants_cte = (
                select(Folder.id)
                .where(Folder.id == folder_id)
                .cte(name="descendants", recursive=True)
            )
            descendants_cte = descendants_cte.union_all(
                select(Folder.id).where(Folder.parent_id == descendants_cte.c.id)
            )
            stmt = delete(Photo).where(Photo.folder_id.in_(select(descendants_cte.c.id)))
            await self.db.execute(stmt)

        await self.db.delete(folder)
        await self.db.flush()

    async def _get_folder(self, event_id: UUID, folder_id: UUID) -> Folder:
        folder = await self.db.get(Folder, folder_id)
        if folder is None or folder.event_id != event_id:
            raise NotFoundError("Folder")
        return folder

    async def _depth(self, folder: Folder) -> int:
        depth = 1
        current = folder
        seen: set[UUID] = set()
        while current.parent_id is not None:
            if current.id in seen or depth >= MAX_FOLDER_DEPTH:
                break
            seen.add(current.id)
            parent = await self.db.get(Folder, current.parent_id)
            if parent is None:
                break
            current = parent
            depth += 1
        return depth

    async def _ensure_not_descendant(
        self,
        event_id: UUID,
        folder_id: UUID,
        new_parent_id: UUID,
    ) -> None:
        """Reject moving a folder under one of its descendants."""
        current_id: UUID | None = new_parent_id
        while current_id is not None:
            if current_id == folder_id:
                raise ConflictError("Cannot move a folder under its own descendant")
            parent = await self.db.get(Folder, current_id)
            if parent is None or parent.event_id != event_id:
                break
            current_id = parent.parent_id

    async def _photo_counts(self, event_id: UUID) -> dict[UUID, int]:
        result = await self.db.execute(
            select(Photo.folder_id, func.count())
            .where(Photo.event_id == event_id, Photo.folder_id.is_not(None))
            .group_by(Photo.folder_id)
        )
        return {folder_id: int(count) for folder_id, count in result.all() if folder_id is not None}
