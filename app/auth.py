from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from datetime import datetime, timezone

from app import models, schemas
from app.database import get_db
from app.dependencies.auth import get_current_user
from app.security import (
    get_password_hash,
    verify_password,
    create_access_token
)

router = APIRouter(
    prefix="/auth",
    tags=["Authentication"]
)


# CUSTOMER REGISTRATION
@router.post(
    "/register",
    response_model=schemas.UserResponse,
    status_code=status.HTTP_201_CREATED
)
def register_user(user: schemas.UserCreate, db: Session = Depends(get_db)):

    # Check whether the email already exists
    existing_user = db.query(models.User).filter(
        models.User.email == user.email
    ).first()

    if existing_user:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Email is already registered"
        )

    # Hash the user's password
    hashed_password = get_password_hash(user.password)

    # Create a new customer
    new_user = models.User(
        full_name=user.full_name,
        email=user.email,
        hashed_password=hashed_password,
        role="customer"
    )

    # Save the customer in the database
    db.add(new_user)
    db.commit()
    db.refresh(new_user)

    return new_user


# CUSTOMER LOGIN
@router.post("/login", response_model=schemas.Token)
def login_user(
    user_credentials: schemas.UserLogin,
    db: Session = Depends(get_db)
):

    # Find the user by email
    user = db.query(models.User).filter(
        models.User.email == user_credentials.email
    ).first()

    # Check whether the user exists
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password"
        )

    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password",
        )

    # Verify the password
    if not verify_password(
        user_credentials.password,
        user.hashed_password
    ):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password"
        )

    # Create an access token
    access_token = create_access_token(
        data={"sub": str(user.id)}
    )

    # Return the token
    return {
        "access_token": access_token,
        "token_type": "bearer"
    }


# CURRENT AUTHENTICATED USER
@router.get("/me", response_model=schemas.UserResponse)
def get_me(current_user: models.User = Depends(get_current_user)):
    return current_user


@router.patch("/me", response_model=schemas.UserResponse)
def update_me(
    updates: schemas.UserProfileUpdate,
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    fields = updates.model_dump(exclude_unset=True)
    if not fields:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Provide at least one profile update",
        )

    new_password = fields.get("new_password")
    current_password = fields.get("current_password")
    if new_password is not None:
        if not current_password or not verify_password(
            current_password, current_user.hashed_password
        ):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Current password is incorrect",
            )
        current_user.hashed_password = get_password_hash(new_password)
    elif current_password is not None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Provide a new password with the current password",
        )

    if fields.get("full_name") is not None:
        current_user.full_name = fields["full_name"]
    db.commit()
    db.refresh(current_user)
    return current_user


# VENDOR APPLICATION
@router.post(
    "/vendor-register",
    response_model=schemas.VendorApplicationResponse,
    status_code=status.HTTP_201_CREATED,
)
def apply_to_become_vendor(
    application: schemas.VendorApplicationCreate,
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    current_user = db.query(models.User).filter(
        models.User.id == current_user.id
    ).with_for_update().first()
    if current_user is None or not current_user.is_active:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User account is unavailable",
        )

    if current_user.role != "customer":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only customer accounts can apply to become vendors",
        )

    existing_application = db.query(models.VendorApplication).filter(
        models.VendorApplication.user_id == current_user.id
    ).first()
    if existing_application and existing_application.status != "rejected":
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"A vendor application already exists with status '{existing_application.status}'",
        )

    if existing_application:
        existing_application.business_name = application.business_name
        existing_application.business_description = application.business_description
        existing_application.contact_phone = application.contact_phone
        existing_application.status = "pending"
        existing_application.review_note = None
        existing_application.reviewed_by_id = None
        existing_application.reviewed_at = None
        existing_application.submitted_at = datetime.now(timezone.utc)
        db.commit()
        db.refresh(existing_application)
        return existing_application

    new_application = models.VendorApplication(
        user_id=current_user.id,
        business_name=application.business_name,
        business_description=application.business_description,
        contact_phone=application.contact_phone,
    )
    db.add(new_application)
    db.commit()
    db.refresh(new_application)
    return new_application


@router.get(
    "/vendor-register",
    response_model=schemas.VendorApplicationResponse,
)
def get_my_vendor_application(
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    application = db.query(models.VendorApplication).filter(
        models.VendorApplication.user_id == current_user.id
    ).first()
    if application is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No vendor application found",
        )
    return application
