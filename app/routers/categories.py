from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select, update
from sqlalchemy.orm import Session
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.categories import Category as CategoryModel
from app.schemas import Category as CategorySchema, CategoryCreate
from app.db_depends import get_db
from app.db_depends import get_async_db


# Создаём маршрутизатор с префиксом и тегом
router = APIRouter(
    prefix="/categories",
    tags=["categories"],
)


@router.get("/", response_model=list[CategorySchema])
async def get_all_categories(db: AsyncSession = Depends(get_async_db)):
    """
    Возвращает список всех категорий товаров.
    """
    stmt = (select(CategoryModel)
            .where(CategoryModel.is_active))
    categories = await db.scalars(stmt)
    categories = categories.all()
    return categories


@router.post("/", response_model=CategorySchema,
             status_code=status.HTTP_201_CREATED)
async def create_category(category: CategoryCreate,
                          db: AsyncSession = Depends(get_async_db)):
    """
    Создаёт новую категорию.
    """
    # проверка существования parent_id, если указан
    if category.parent_id is not None:
        stmt = (select(CategoryModel)
                .where(CategoryModel.id == category.parent_id,
                       CategoryModel.is_active))
        result = await db.scalar(stmt)
        #parent = result.first()

        if result is None:
            raise HTTPException(status_code=400, detail="Parent category not found")

    # создание новой категории
    db_category = CategoryModel(**category.model_dump())
    db.add(db_category)
    await db.commit()
    await db.refresh(db_category)
    return db_category


@router.put("/{category_id}", response_model=CategorySchema)
async def update_category(category_id: int, category: CategoryCreate,
                          db: Annotated[AsyncSession, Depends(get_async_db)]):
    """
    Обновляет категорию по её ID.
    """
    # Проверка существования категории
    stmt = (select(CategoryModel)
            .where(CategoryModel.id == category_id,
                   CategoryModel.is_active))
    db_category = await db.scalar(stmt)
    #db_category = db_category.first()
    if db_category is None:
        raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Category not found",
            )

    # Проверка существования parent_id, если указан
    if category.parent_id is not None:
        parent_stmt = (select(CategoryModel)
                       .where(CategoryModel.id == category.parent_id))
        parent = await db.scalar(parent_stmt)
        #parent = parent.first()
        if parent is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Parent category not found",
            )
        if parent.id == category_id:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Category cannot be its own parent")

    # Обновление категории
    updated_category = category.model_dump(exclude_unset=True)
    await db.execute(
        update(CategoryModel)
        .where(CategoryModel.id == category_id)
        .values(**updated_category))
    await db.commit()
    return db_category


@router.delete("/{category_id}", status_code=status.HTTP_200_OK)
async def delete_category(category_id: int,
                          db: Annotated[AsyncSession, Depends(get_async_db)]):
    """
    Логически удаляет категорию по её ID, устанавливая is_active=False.
    """
    stmt = (select(CategoryModel)
            .where(CategoryModel.id == category_id,
                   CategoryModel.is_active))
    category = await db.scalar(stmt)
    if category is None:
        raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Category not found",
            )

    # Логическое удаление категории (установка is_active=False)
    await db.execute(update(CategoryModel)
                     .where(CategoryModel.id == category_id)
                     .values(is_active=False))
    await db.commit()

    return {
        "status": "success",
        "message": f"Category with ID {category_id} marked as inactive"
    }

