from fastapi import FastAPI, HTTPException, Depends, Form
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from motor.motor_asyncio import AsyncIOMotorClient
from passlib.context import CryptContext
from jose import JWTError, jwt
from pydantic import BaseModel
from typing import Optional, List
from datetime import datetime, timedelta
import secrets
from fastapi import Request, HTTPException
from bson import ObjectId


# MongoDB Settings
MONGO_URI = "mongodb://localhost:27017"
MONGO_DB = "book-store"

# Connect to MongoDB


async def get_database():
    client = AsyncIOMotorClient(MONGO_URI)
    database = client[MONGO_DB]
    return database


app = FastAPI()


class User(BaseModel):
    email: str
    first_name: str
    last_name: str
    password: str
    is_admin: Optional[bool] = False


class UserResponse(BaseModel):
    email: str
    first_name: str
    last_name: str
    password: str


# MongoDB Collection
client = AsyncIOMotorClient(MONGO_URI)
db = client[MONGO_DB]
users_collection = db["users"]
SECRET_KEY = "WQSjPTqb-Kyfd4u-G0SHMSaJhf0_-O-ham0PQoftOwMz-q2baAcmN8wt3xsrujonBLyrixZmFJgGV5lacFmysA"

# OAuth2PasswordBearer for token authentication
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="token")

# Password Hashing
password_hasher = CryptContext(schemes=["bcrypt"], deprecated="auto")


async def get_current_user_and_admin(token: str = Depends(oauth2_scheme)):
    user = await get_current_user(token)

    if not user.get("is_admin"):
        raise HTTPException(status_code=403, detail=f"Permission denied for {user}")

    return user


async def create_user(user: User, password: str, is_admin: Optional[bool] = False):
    hashed_password = password_hasher.hash(password)
    user_doc = {
        "email": user.email,
        "first_name": user.first_name,
        "last_name": user.last_name,
        "password": hashed_password,
        "is_admin": is_admin,
    }
    result = await users_collection.insert_one(user_doc)
    return result


async def get_user(email: str):
    user = await users_collection.find_one({"email": email})
    return user


def verify_password(plain_password, hashed_password):
    return password_hasher.verify(plain_password, hashed_password)


def create_tokens(data: dict, expires_delta: timedelta):
    to_encode = data.copy()
    expire = datetime.utcnow() + timedelta(minutes=30)

    to_encode.update({"exp": expire})
    access_token = jwt.encode(to_encode, SECRET_KEY, algorithm="HS256")

    refresh_expire = datetime.utcnow() + timedelta(days=7)
    to_encode.update({"exp": refresh_expire})
    refresh_token = jwt.encode(to_encode, SECRET_KEY, algorithm="HS256")

    return access_token, refresh_token


async def get_current_user(token: str = Depends(oauth2_scheme)):
    credentials_exception = HTTPException(
        status_code=401,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=["HS256"])
        email: str = payload.get("sub")
        if email is None:
            raise credentials_exception
    except jwt.JWTError as e:
        print("JWT Error:", e)
        raise credentials_exception
    user = await get_user(email)
    if user is None:
        raise credentials_exception
    return user


@app.post("/login")
async def login_user(request: Request, db: AsyncIOMotorClient = Depends(get_database)):
    try:
        payload = await request.json()
        email = payload.get("email")
        password = payload.get("password")
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid JSON payload")

    user = await get_user(email)
    if not user or not verify_password(password, user["password"]):
        raise HTTPException(
            status_code=401,
            detail="Incorrect email or password",
            headers={"WWW-Authenticate": "Bearer"},
        )

    access_token_expires = timedelta(minutes=30)
    access_token, refresh_token = create_tokens(
        data={"sub": user["email"]}, expires_delta=access_token_expires
    )
    return {
        "access_token": access_token,
        "refresh_token": refresh_token,
        "token_type": "bearer",
    }


@app.post("/register", response_model=UserResponse)
async def register_user(
    request: Request, db: AsyncIOMotorClient = Depends(get_database)
):
    try:
        payload = await request.json()
        user = User(**payload)
        password = payload.get("password")
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid JSON payload")

    existing_user = await db.users.find_one({"email": user.email})
    if existing_user:
        raise HTTPException(status_code=400, detail="Email already registered")

    hashed_password = password_hasher.hash(password)
    data = {
        "email": user.email,
        "first_name": user.first_name,
        "last_name": user.last_name,
        "password": hashed_password,
    }

    result = await db.users.insert_one(data)
    inserted_id = result.inserted_id
    created_user = await db.users.find_one({"_id": inserted_id})

    return UserResponse(
        email=created_user["email"],
        first_name=created_user["first_name"],
        last_name=created_user["last_name"],
        password=created_user["password"],
    )


async def is_admin(current_user: dict = Depends(get_current_user)):
    if current_user.get("is_admin"):
        return True
    else:
        raise HTTPException(status_code=403, detail="Permission denied")


async def get_database():
    client = AsyncIOMotorClient("mongodb://localhost:27017")
    try:
        db = client["book-store"]
        yield db
    finally:
        client.close()


# CRUD operations for the Book model

# ================================================ Book =========================================================


class BookCreate(BaseModel):
    title: str
    author: str
    price: float
    stock: int
    image: str
    discount_price: float
    description: str


class BookUpdate(BaseModel):
    title: str
    author: str
    price: float
    stock: int
    image: str
    discount_price: float
    description: str


async def get_current_user_and_admin(token: str = Depends(oauth2_scheme)):
    user = await get_current_user(token)

    if not user.get("is_admin"):
        raise HTTPException(
            status_code=403, detail=f"Permission denied to user :- {user.get('email')}"
        )
    return user


@app.post(
    "/books",
    response_model=BookUpdate,
    dependencies=[Depends(get_current_user_and_admin)],
)
async def create_book(book: BookCreate, db: AsyncIOMotorClient = Depends(get_database)):
    result = await db.books.insert_one(book.dict())
    return BookUpdate(id=str(result.inserted_id), **book.dict())


@app.put(
    "/books/{book_id}", response_model=BookUpdate, dependencies=[Depends(is_admin)]
)
async def update_book(
    book_id: str, book: BookUpdate, db: AsyncIOMotorClient = Depends(get_database)
):
    await db.books.update_one({"_id": ObjectId(book_id)}, {"$set": book.dict()})
    return BookUpdate(**book.dict())


@app.get(
    "/books/{book_id}", response_model=BookUpdate, dependencies=[Depends(oauth2_scheme)]
)
async def get_book(book_id: str, db: AsyncIOMotorClient = Depends(get_database)):
    book_collection = db["books"]  # Access the "books" collection
    book = await book_collection.find_one({"_id": ObjectId(book_id)})

    if book:
        return BookUpdate(**book)
    else:
        raise HTTPException(status_code=404, detail="Book not found")


@app.get(
    "/books", response_model=List[BookUpdate], dependencies=[Depends(oauth2_scheme)]
)
async def list_books(db: AsyncIOMotorClient = Depends(get_database)):
    books = await db.books.find().to_list(length=100)
    return [BookUpdate(**book) for book in books]


@app.delete(
    "/books/{book_id}",
    response_model=BookUpdate,
    dependencies=[Depends(get_current_user_and_admin)],
)
async def delete_book(book_id: str, db: AsyncIOMotorClient = Depends(get_database)):
    object_id = ObjectId(book_id)
    book = await db.books.find_one_and_delete({"_id": object_id})

    if book:
        BookUpdate(**book)
        return UserResponse(status_code=200, detail="Book deleted successfully")
    else:
        raise HTTPException(status_code=404, detail="Book not found")


# ===================================================== Order ===========================================================================
