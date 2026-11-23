import os
from datetime import datetime, timedelta, timezone

import jwt
from jwt import InvalidTokenError
from dotenv import load_dotenv
from pwdlib import PasswordHash

# Load settings from the .env file
load_dotenv()

# Read security settings
SECRET_KEY = os.getenv("SECRET_KEY")
ALGORITHM = os.getenv("JWT_ALGORITHM", "HS256")

ACCESS_TOKEN_EXPIRE_MINUTES = int(
    os.getenv("ACCESS_TOKEN_EXPIRE_MINUTES", "30")
)

# Make sure the secret key exists
if not SECRET_KEY:
    raise ValueError("SECRET_KEY is not configured in .env")

# Create password hashing tool
password_hash = PasswordHash.recommended()


# 1. Hash a user's password before saving it
def get_password_hash(password: str) -> str:
    return password_hash.hash(password)


# 2. Verify a password during login
def verify_password(
    plain_password: str,
    hashed_password: str
) -> bool:
    return password_hash.verify(plain_password, hashed_password)


# 3. Create a JWT access token
def create_access_token(data: dict) -> str:
    to_encode = data.copy()

    expire = datetime.now(timezone.utc) + timedelta(
        minutes=ACCESS_TOKEN_EXPIRE_MINUTES
    )

    to_encode.update({"exp": expire})

    return jwt.encode(
        to_encode,
        SECRET_KEY,
        algorithm=ALGORITHM
    )


# 4. Decode and validate an access token
def decode_access_token(token: str) -> dict:
    try:
        return jwt.decode(
            token,
            SECRET_KEY,
            algorithms=[ALGORITHM]
        )
    except InvalidTokenError as exc:
        raise ValueError("Invalid or expired access token") from exc
