from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select, update
from sqlalchemy.orm import Session
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.categories import Category as CategoryModel
from app.models.products import Product as ProductModel
from app.models.users import User as UserModel
from app.schemas import Product as ProductSchema, ProductCreate
from app.auth import get_current_seller
from app.db_depends import get_db
from app.db_depends import get_async_db

# Создаём маршрутизатор для товаров
router = APIRouter(
    prefix="/products",
    tags=["products"],
)


@router.get("/", response_model=list[ProductSchema])
async def get_all_products(db: Annotated[AsyncSession, Depends(get_async_db)]):
    """
    Возвращает список всех товаров.
    """
    stmt = (select(ProductModel)
            .where(ProductModel.is_active))
    products = await db.scalars(stmt)
    return products.all()


@router.post("/", response_model=ProductSchema,
             status_code=status.HTTP_201_CREATED)
async def create_product(product: ProductCreate,
                         db: Annotated[AsyncSession, Depends(get_async_db)],
                         current_user: UserModel = Depends(get_current_seller)):
    """
    Создаёт новый товар.
    """
    if product.category_id is not None:
        stmt = (select(CategoryModel)
                .where(CategoryModel.id == product.category_id,
                       CategoryModel.is_active))
        categorie = await db.scalar(stmt)

        if categorie is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Category not found",
            )

    db_product = ProductModel(**product.model_dump(), seller_id=current_user.id)
    db.add(db_product)
    await db.commit()
    # await db.refresh(db_product)
    return db_product


@router.get("/category/{category_id}",
            response_model=list[ProductSchema])
async def get_products_by_category(category_id: int,
                                   db: Annotated[AsyncSession, Depends(get_async_db)]):
    """
    Возвращает список товаров в указанной категории по её ID.
    """
    stmt_category = (select(CategoryModel)
                     .where(CategoryModel.id == category_id,
                            CategoryModel.is_active))
    category = await db.scalar(stmt_category)
    if category is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Category not found",
        )

    stmt_category_child = (select(CategoryModel.id)
                           .where(CategoryModel.parent_id == category_id,
                                  CategoryModel.is_active))
    child_ids = await db.scalars(stmt_category_child)
    child_ids = child_ids.all()
    if child_ids is None:
        stmt_products = (select(ProductModel)
                         .where(ProductModel.category_id == category_id,
                                ProductModel.is_active))
    else:
        category_ids = [category_id] + child_ids
        stmt_products = (select(ProductModel)
                         .where(ProductModel.category_id.in_(category_ids)))

    products = await db.scalars(stmt_products)
    products = products.all()
    return products


@router.get("/{product_id}", response_model=ProductSchema)
async def get_product(product_id: int,
                      db: Annotated[AsyncSession, Depends(get_async_db)]):
    """
    Возвращает детальную информацию о товаре по его ID.
    """
    stmt = (select(ProductModel)
            .where(ProductModel.id == product_id,
                   ProductModel.is_active))

    product = await db.scalar(stmt)
    if product is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Product not found",
        )

    return product


@router.put("/{product_id}", response_model=ProductSchema)
async def update_product(product_id: int,
                         product_update: ProductCreate,
                         db: Annotated[AsyncSession, Depends(get_async_db)],
                         current_user: UserModel = Depends(get_current_seller)):
    """
    Обновляет товар по его ID.
    """
    stmt = (select(ProductModel)
            .where(ProductModel.id == product_id))

    product = await db.scalar(stmt)
    if product is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Product not found",
        )
    if product.seller_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You can only update your products",
        )
    if product_update.category_id is not None:
        stmt_category = (select(CategoryModel)
                         .where(CategoryModel.id == product_update.category_id,
                                CategoryModel.is_active))
        category = await db.scalar(stmt_category)
        if category is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Category not found",
            )

    updated_product = product_update.model_dump(exclude_unset=True)
    await db.execute(update(ProductModel)
                     .where(ProductModel.id == product_id)
                     .values(**updated_product))
    await db.commit()
    # await db.refresh(product)
    return product


@router.delete("/{product_id}",
               status_code=status.HTTP_200_OK)
async def delete_product(product_id: int,
                         db: Annotated[AsyncSession, Depends(get_async_db)],
                         current_user: UserModel = Depends(get_current_seller)):
    """
    Логически удаляет товар по его ID, устанавливая is_active=False.
    """
    stmt = (select(ProductModel)
            .where(ProductModel.id == product_id,
                   ProductModel.is_active))
    product = await db.scalar(stmt)
    if product is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Product not found",
        )
    if product.seller_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You can only delete your products",
        )

    await db.execute(update(ProductModel)
                     .where(ProductModel.id == product_id)
                     .values(is_active=False))
    await db.commit()

    return {"status": "success",
            "message": "Product marked as inactive"}
