from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select, update, func
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.categories import Category as CategoryModel
from app.models.products import Product as ProductModel
from app.models.reviews import Review as ReviewModel

from app.models.users import User as UserModel
from app.schemas import Review as ReviewSchema, ReviewCreate
from app.auth import get_current_buyer, get_current_admin
from app.db_depends import get_async_db

# Создаём маршрутизатор для товаров
router = APIRouter(
    prefix="/reviews",
    tags=["reviews"],
)


@router.get("/", response_model=list[ReviewSchema])
async def get_reviews(db: Annotated[AsyncSession, Depends(get_async_db)]):
    """
    Возвращает список всех отзывов.
    """
    reviews = await db.scalars(select(ReviewModel).
                               where(ReviewModel.is_active))
    return reviews.all()


@router.get("/products/{product_id}/reviews", response_model=list[ReviewSchema])
async def get_reviews_by_product(product_id: int,
                                 db: Annotated[AsyncSession, Depends(get_async_db)]):
    """
    Возвращает список отзывов по товарам.
    """
    product = await db.scalar(select(ProductModel)
                              .where(ProductModel.id == product_id,
                                     ProductModel.is_active))
    if product is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Product with id {product_id} does not exist."
        )

    reviews = await db.scalars(select(ReviewModel)
                               .where(ReviewModel.product_id == product_id,
                                      ReviewModel.is_active))
    return reviews.all()


@router.post("/", response_model=ReviewSchema,
             status_code=status.HTTP_201_CREATED)
async def create_review(review: ReviewCreate,
                        db: Annotated[AsyncSession, Depends(get_async_db)],
                        current_buyer: UserModel = Depends(get_current_buyer)):
    """
    Создаёт отзыв к товару и пересчитывает рейтинг продукта.
    """
    product = await db.scalar(select(ProductModel)
                              .where(ProductModel.id == review.product_id,
                                     ProductModel.is_active))
    if product is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Product with id {review.product_id} does not exist."
        )

    db_review = ReviewModel(**review.model_dump(), user_id=current_buyer.id)
    db.add(db_review)

    try:
        await db.commit()
    except IntegrityError as e:
        await db.rollback()
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Integrity Error: {str(e.orig)}"
        )

    avg_rating = await db.scalar(select(func.avg(ReviewModel.grade))
                                 .where(ReviewModel.is_active,
                                        ReviewModel.product_id == review.product_id)
    )
    await db.execute(update(ProductModel)
                     .where(ProductModel.id == review.product_id)
                     .values(rating=func.round(avg_rating, 2)))
    await db.commit()
    return db_review


@router.delete("/{review_id}",
               status_code=status.HTTP_200_OK)
async def delete_review(review_id: int,
                        db: Annotated[AsyncSession, Depends(get_async_db)],
                        current_admin: UserModel = Depends(get_current_admin)):
    """
    Логически удаляет отзыв и пересчитывает рейтинг продукта.
    """
    review = await db.scalar(select(ReviewModel)
                             .where(ReviewModel.is_active,
                                    ReviewModel.id == review_id))
    if review is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Review with id {review_id} does not exist."
        )

    await db.execute(update(ReviewModel)
                     .where(ReviewModel.id == review_id)
                     .values(is_active=False))
    await db.commit()

    avg_rating = await db.scalar(select(func.avg(ReviewModel.grade))
                                 .where(ReviewModel.is_active,
                                        ReviewModel.product_id == review.product_id))
    if avg_rating is None:
        avg_rating = 0

    await db.execute(update(ProductModel)
                     .where(ProductModel.id == review.product_id)
                     .values(rating=func.round(avg_rating, 2)))
    await db.commit()
    return {"message": "Review marked as inactive"}


