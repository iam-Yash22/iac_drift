import argparse

from core.config import settings
from db.init_db import init_db
from db.session import SessionLocal


def _build_parser():
    parser = argparse.ArgumentParser(description="Create the initial superuser account.")
    parser.add_argument("--email", required=True, help="gemini13082000@gmail.com")
    parser.add_argument("--password", required=True, help="Gemini@13082000#")
    parser.add_argument("--first-name", default="Admin", help="Administrator")
    parser.add_argument("--last-name", default="User", help="test")
    return parser


def create_superuser(email: str, password: str, first_name: str, last_name: str):
    init_db()

    with SessionLocal() as session:
        from app.models.user import User

        existing = session.query(User).filter(User.email == email).first()
        if existing is not None:
            raise ValueError(f"User with email '{email}' already exists")

        user = User(
            email=email,
            password=password,
            first_name=first_name,
            last_name=last_name,
            is_superuser=True,
            is_active=True,
        )
        session.add(user)
        session.commit()
        return user


def main():
    parser = _build_parser()
    args = parser.parse_args()

    try:
        user = create_superuser(
            email=args.email,
            password=args.password,
            first_name=args.first_name,
            last_name=args.last_name,
        )
        print(f"Created superuser: {user.email}")
    except Exception as exc:
        raise SystemExit(str(exc))


if __name__ == "__main__":
    main()
