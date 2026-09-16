from extensions import db_session
from models import ChatGroup


GROUPS = [
    "Admin Group",
    "Management & Pharmacy",
]


def seed_chats():
    for group_name in GROUPS:
        existing = (
            db_session.query(ChatGroup)
            .filter(ChatGroup.name == group_name)
            .first()
        )

        if existing:
            print(f"Chat group already exists: {group_name}")
            continue

        group = ChatGroup(name=group_name)
        db_session.add(group)
        print(f"Created chat group: {group_name}")

    db_session.commit()


if __name__ == "__main__":
    seed_chats()