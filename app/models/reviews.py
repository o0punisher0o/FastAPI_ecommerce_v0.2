from typing import Optional

from sqlalchemy import String, Boolean, ForeignKey, Text, DateTime, Enum, CheckConstraint, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class Review(Base):
    __tablename__ = "reviews"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"),
                                         nullable=False)
    product_id: Mapped[int] = mapped_column(ForeignKey("products.id"),
                                            nullable=False)

    comment: Mapped[str] = mapped_column(Text, nullable=False)
    comment_date: Mapped[DateTime] = mapped_column(DateTime,
                                                   nullable=False,
                                                   default=func.now())
    grade: Mapped[int] = mapped_column(nullable=False)
    # Enum(1, 2, 3, 4, 5, name="grade_enum")

    is_active: Mapped[bool] = mapped_column(Boolean, default=True)

    __table_args__ = (
        CheckConstraint('grade >= 1 AND grade <= 5',
                        name='check_grade_range'),
    )


# if __name__ == "__main__":
#     from sqlalchemy.schema import CreateTable
#     from app.models.products import Product
#     print(CreateTable(Category.__table__))
#     print(CreateTable(Product.__table__))
