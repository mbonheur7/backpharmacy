"""add medicine comments

Revision ID: 40d4399fe5b5
Revises: 0003
Create Date: 2026-09-08 16:32:43.725297

"""

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "40d4399fe5b5"
down_revision = "0003"
branch_labels = None
depends_on = None


def upgrade() -> None:

    op.create_table(
        "medicine_comments",

        sa.Column(
            "id",
            sa.Integer(),
            nullable=False,
        ),

        sa.Column(
            "medicine_id",
            sa.Integer(),
            nullable=False,
        ),

        sa.Column(
            "user_id",
            sa.Integer(),
            nullable=False,
        ),

        sa.Column(
            "comment",
            sa.Text(),
            nullable=False,
        ),

        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),

        sa.ForeignKeyConstraint(
            ["medicine_id"],
            ["medicines.id"],
            ondelete="CASCADE",
        ),

        sa.ForeignKeyConstraint(
            ["user_id"],
            ["users.id"],
            ondelete="RESTRICT",
        ),

        sa.PrimaryKeyConstraint(
            "id",
        ),
    )


def downgrade() -> None:

    op.drop_table(
        "medicine_comments"
    )