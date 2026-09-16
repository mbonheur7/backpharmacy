"""update user roles

Revision ID: 0002
Revises: 0001
"""

from alembic import op


revision = "0002"
down_revision = "0001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Remove the old role constraint first so existing
    # "Admin" users can be converted safely.
    op.drop_constraint(
        "ck_users_role",
        "users",
        type_="check",
    )

    # Convert the existing Admin role to the new Super Admin role.
    op.execute(
        "UPDATE users "
        "SET role = 'Super Admin' "
        "WHERE role = 'Admin'"
    )

    # Enforce the new three-role system.
    op.create_check_constraint(
        "ck_users_role",
        "users",
        "role IN ('Super Admin', 'Admin Viewer', 'Pharmacist')",
    )


def downgrade() -> None:
    # Remove the new role constraint first.
    op.drop_constraint(
        "ck_users_role",
        "users",
        type_="check",
    )

    # Convert Super Admin back to the old Admin role.
    op.execute(
        "UPDATE users "
        "SET role = 'Admin' "
        "WHERE role = 'Super Admin'"
    )

    # Restore the original role constraint.
    op.create_check_constraint(
        "ck_users_role",
        "users",
        "role IN ('Admin', 'Pharmacist')",
    )