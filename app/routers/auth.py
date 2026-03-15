from fastapi import APIRouter, HTTPException, Depends
from sqlmodel import select
from app.database import SessionDep
from app.models import *
from app.auth import encrypt_password, verify_password, create_access_token, AuthDep
from fastapi.security import OAuth2PasswordRequestForm
from typing import Annotated
from fastapi import status

auth_router = APIRouter(tags=["Authentication"])

@auth_router.post("/token")
async def login_for_access_token(
    form_data: Annotated[OAuth2PasswordRequestForm, Depends()],
    db: SessionDep
) -> Token:
    user = db.exec(select(RegularUser).where(RegularUser.username == form_data.username)).one_or_none()
    if not user or not verify_password(plaintext_password=form_data.password, encrypted_password=user.password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
        
    access_token = create_access_token(data={"sub": f"{user.id}", "role": user.role},)

    return Token(access_token=access_token, token_type="bearer")

@auth_router.get("/identify", response_model=UserResponse)
def get_user_by_id(db: SessionDep, user:AuthDep):
    return user



@auth_router.post('/signup', response_model=UserResponse, status_code=status.HTTP_201_CREATED)
def signup_user(user_data: UserCreate, db:SessionDep):
  try:
    new_user = RegularUser(
        username=user_data.username, 
        email=user_data.email, 
        password=encrypt_password(user_data.password)
    )
    db.add(new_user)
    db.commit()
    return new_user
  except Exception:
    db.rollback()
    raise HTTPException(
                status_code=400,
                detail="Username or email already exists",
                headers={"WWW-Authenticate": "Bearer"},
            )
  
@auth_router.post('/category', status_code=status.HTTP_201_CREATED )
def create_category(category: Category, db: SessionDep, current_user: User = AuthDep):
    # This user is guaranteed to exist if this line runs
    category.user_id = current_user.id
    db.add(category)
    db.commit()
    return "Category created successfully"

@auth_router.post('/todo/{todo_id}/category/{cat_id}', status_code=status.HTTP_201_CREATED)
def add_category_to_todo(todo_id: int, cat_id: int, db: SessionDep, current_user: User = AuthDep):
    todo = db.get(Todo, todo_id)
    category = db.get(Category, cat_id)

    if not todo or not category:
        raise HTTPException(status_code=404, detail="Todo or Category not found")
    
    if todo.user_id != current_user.id or category.user_id != current_user.id:
        raise HTTPException(status_code=403, detail="Not authorized to modify this todo or category")

    todo.categories.append(category)
    db.add(todo)
    db.commit()
    return "Category added to todo successfully"

@auth_router.delete('/todo/{todo_id}/category/{cat_id}', status_code=status.HTTP_200_OK)
def remove_category_from_todo(todo_id: int, cat_id: int, db: SessionDep, current_user: User = AuthDep):
    todo = db.get(Todo, todo_id)
    category = db.get(Category, cat_id)

    if not todo or not category:
        raise HTTPException(status_code=404, detail="Todo or Category not found")
    
    if todo.user_id != current_user.id or category.user_id != current_user.id:
        raise HTTPException(status_code=403, detail="Not authorized to modify this todo or category")

    if category in todo.categories:
        todo.categories.remove(category)
        db.add(todo)
        db.commit()
        return "Category removed from todo successfully"
    else:
        raise HTTPException(status_code=404, detail="Category not associated with this todo")
    
auth_router.get('/category/{cat_id}/todos', response_model=list[Todo])
def get_todos_by_category(cat_id: int, db: SessionDep, current_user: User = AuthDep):
    category = db.get(Category, cat_id)

    if not category:
        raise HTTPException(status_code=404, detail="Category not found")
    
    if category.user_id != current_user.id:
        raise HTTPException(status_code=403, detail="Not authorized to view todos for this category")

    return category.todos