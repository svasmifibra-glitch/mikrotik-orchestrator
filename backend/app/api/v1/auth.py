from fastapi import APIRouter, Depends, HTTPException, status, Request
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from sqlalchemy.orm import Session
from typing import Optional
from datetime import timedelta
from jose import JWTError, jwt

from app.core.database import get_db
from app.core.security import verify_password, get_password_hash, create_access_token, ALGORITHM
from app.core.config import settings
from app.models.models import User
from app.schemas.schemas import Token, UserCreate, UserOut, UserLogin

router = APIRouter(prefix="/auth", tags=["Auth"])
oauth2_scheme = OAuth2PasswordBearer(tokenUrl=f"{settings.API_V1_STR}/auth/token")

def get_current_user(token: str = Depends(oauth2_scheme), db: Session = Depends(get_db)) -> User:
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[ALGORITHM])
        email: str = payload.get("sub")
        if email is None:
            raise credentials_exception
    except JWTError:
        raise credentials_exception
    
    user = db.query(User).filter(User.email == email).first()
    if user is None:
        raise credentials_exception
    return user

def get_current_user_flexible(request: Request, token: Optional[str] = None, db: Session = Depends(get_db)) -> User:
    """Authenticates user via either Authorization Bearer header OR ?token= query parameter"""
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    auth_header = request.headers.get("Authorization")
    jwt_token = None
    if auth_header and auth_header.startswith("Bearer "):
        jwt_token = auth_header.split(" ", 1)[1].strip()
    elif token:
        jwt_token = token.strip()
    elif request.query_params.get("token"):
        jwt_token = request.query_params.get("token").strip()

    if not jwt_token:
        raise credentials_exception

    try:
        payload = jwt.decode(jwt_token, settings.SECRET_KEY, algorithms=[ALGORITHM])
        email: str = payload.get("sub")
        if email is None:
            raise credentials_exception
    except JWTError:
        raise credentials_exception

    user = db.query(User).filter(User.email == email).first()
    if user is None:
        raise credentials_exception
    return user

@router.post("/register", response_model=UserOut)
def register(user_in: UserCreate, db: Session = Depends(get_db)):
    db_user = db.query(User).filter(User.email == user_in.email).first()
    if db_user:
        raise HTTPException(status_code=400, detail="Email already registered")
    
    user = User(
        email=user_in.email,
        hashed_password=get_password_hash(user_in.password),
        full_name=user_in.full_name,
        role=user_in.role
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user

@router.post("/token", response_model=Token)
def login_for_access_token(form_data: OAuth2PasswordRequestForm = Depends(), db: Session = Depends(get_db)):
    user = db.query(User).filter(User.email == form_data.username).first()
    if not user or not verify_password(form_data.password, user.hashed_password):
        raise HTTPException(status_code=400, detail="Incorrect email or password")
    
    access_token = create_access_token(subject=user.email)
    return {"access_token": access_token, "token_type": "bearer"}

@router.get("/me", response_model=UserOut)
def read_users_me(current_user: User = Depends(get_current_user)):
    return current_user

@router.get("/users", response_model=list[UserOut])
def list_users(db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    """Lists all system users (requires admin role)"""
    if current_user.role != "admin":
        raise HTTPException(status_code=403, detail="Permisos insuficientes. Solo administradores pueden gestionar usuarios.")
    return db.query(User).order_by(User.id.asc()).all()

@router.post("/users", response_model=UserOut)
def create_user_by_admin(user_in: UserCreate, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    """Creates a new user account with specified role (requires admin)"""
    if current_user.role != "admin":
        raise HTTPException(status_code=403, detail="Permisos insuficientes. Solo administradores pueden crear usuarios.")
    
    existing = db.query(User).filter(User.email == user_in.email).first()
    if existing:
        raise HTTPException(status_code=400, detail="El correo ya se encuentra registrado.")

    user = User(
        email=user_in.email,
        hashed_password=get_password_hash(user_in.password),
        full_name=user_in.full_name or user_in.email.split("@")[0],
        role=user_in.role or "operator",
        is_active=True
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user

@router.put("/users/{user_id}", response_model=UserOut)
def update_user(user_id: int, payload: dict, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    """Updates user information, password or role (requires admin)"""
    if current_user.role != "admin":
        raise HTTPException(status_code=403, detail="Solo administradores pueden modificar usuarios.")
    
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="Usuario no encontrado.")

    if "full_name" in payload and payload["full_name"]:
        user.full_name = payload["full_name"]
    if "role" in payload and payload["role"]:
        user.role = payload["role"]
    if "is_active" in payload:
        user.is_active = bool(payload["is_active"])
    if "password" in payload and payload["password"]:
        user.hashed_password = get_password_hash(payload["password"])

    db.commit()
    db.refresh(user)
    return user

@router.delete("/users/{user_id}")
def delete_user(user_id: int, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    """Deletes a user account (cannot delete own admin account)"""
    if current_user.role != "admin":
        raise HTTPException(status_code=403, detail="Solo administradores pueden eliminar usuarios.")
    
    if current_user.id == user_id:
        raise HTTPException(status_code=400, detail="No puedes eliminar tu propia cuenta de administrador en sesión.")

    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="Usuario no encontrado.")

    db.delete(user)
    db.commit()
    return {"status": "deleted", "message": f"Usuario {user.email} eliminado con éxito."}

