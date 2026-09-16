from extensions import db_session
from models import User, ChatGroup, ChatMember


def add_member(group, user):
    existing = (
        db_session.query(ChatMember)
        .filter(
            ChatMember.group_id == group.id,
            ChatMember.user_id == user.id,
        )
        .first()
    )

    if existing:
        print(
            f"Already a member: {user.username} -> {group.name}"
        )
        return

    member = ChatMember(
        group_id=group.id,
        user_id=user.id,
    )

    db_session.add(member)

    print(
        f"Added: {user.username} -> {group.name}"
    )


def seed_members():
    admin_group = (
        db_session.query(ChatGroup)
        .filter(ChatGroup.name == "Admin Group")
        .first()
    )

    management_group = (
        db_session.query(ChatGroup)
        .filter(
            ChatGroup.name == "Management & Pharmacy"
        )
        .first()
    )

    if not admin_group or not management_group:
        print("Chat groups not found. Run seed_chats.py first.")
        return

    admin_users = (
        db_session.query(User)
        .filter(
            User.role.in_(("Super Admin", "Admin Viewer"))
        )
        .all()
    )

    pharmacists = (
        db_session.query(User)
        .filter(User.role == "Pharmacist")
        .all()
    )

    # Admin Group:
    # Super Admins + Admin Viewers
    for user in admin_users:
        add_member(admin_group, user)

    # Management & Pharmacy:
    # Super Admins + Pharmacists
    super_admins = (
        db_session.query(User)
        .filter(User.role == "Super Admin")
        .all()
    )

    for user in super_admins:
        add_member(management_group, user)

    for user in pharmacists:
        add_member(management_group, user)

    db_session.commit()


if __name__ == "__main__":
    seed_members()