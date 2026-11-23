import argparse
from getpass import getpass

from pydantic import ValidationError

from app import models
from app.database import SessionLocal
from app.schemas import UserCreate
from app.security import get_password_hash


def main() -> None:
    parser = argparse.ArgumentParser(description="Create the first AMIPerfumeHub administrator")
    parser.add_argument("--email", required=True)
    parser.add_argument("--full-name", required=True)
    args = parser.parse_args()

    password = getpass("Administrator password (minimum 8 characters): ")
    if len(password) < 8:
        parser.error("Password must be at least 8 characters long")
    confirmation = getpass("Confirm password: ")
    if password != confirmation:
        parser.error("Passwords do not match")
    try:
        identity = UserCreate(full_name=args.full_name, email=args.email, password=password)
    except ValidationError as exc:
        parser.error(f"Invalid administrator details: {exc}")

    db = SessionLocal()
    try:
        user = db.query(models.User).filter(models.User.email == identity.email).first()
        if user is not None:
            if not user.is_active:
                parser.error("The matching account is inactive; activate it before promotion")
            user.role = "admin"
            user.full_name = args.full_name
            user.hashed_password = get_password_hash(password)
        else:
            user = models.User(
                full_name=args.full_name,
                email=args.email,
                hashed_password=get_password_hash(password),
                role="admin",
                is_active=True,
            )
            db.add(user)
        db.commit()
        print(f"Administrator account ready: {identity.email}")
    finally:
        db.close()


if __name__ == "__main__":
    main()
