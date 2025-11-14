from fastapi.exceptions import RequestValidationError
from starlette.exceptions import HTTPException as StarletteHTTPException
from fastapi import FastAPI, Request, Form, HTTPException
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from fastapi.staticfiles import StaticFiles
from datetime import timedelta, datetime
import uuid
import time
from datetime import datetime
import pandas as pd
import os
import hashlib
from functools import wraps
from cryptography import x509
from cryptography.x509.oid import NameOID
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import rsa



import os
from tempfile import NamedTemporaryFile

async def sertificate(path: str, data: bytes, mode: int = 0o600) -> None:
    dirpath = os.path.dirname(os.path.abspath(path)) or "."
    with NamedTemporaryFile(dir=dirpath, delete=False) as tmp:
        tmp.write(data); tmp.flush(); os.fsync(tmp.fileno())
        tmpname = tmp.name
    os.chmod(tmpname, mode); os.replace(tmpname, path)

key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
subject = issuer = x509.Name([
    x509.NameAttribute(NameOID.COUNTRY_NAME, "BY"),
    x509.NameAttribute(NameOID.STATE_OR_PROVINCE_NAME, "Minsk"),
    x509.NameAttribute(NameOID.LOCALITY_NAME, "Minsk"),
    x509.NameAttribute(NameOID.ORGANIZATION_NAME, "MyCompany"),
    x509.NameAttribute(NameOID.COMMON_NAME, "localhost"),
])
cert = (x509.CertificateBuilder()
    .subject_name(subject).issuer_name(issuer)
    .public_key(key.public_key())
    .serial_number(x509.random_serial_number())
    .not_valid_before(datetime.utcnow())
    .not_valid_after(datetime.utcnow() + timedelta(days=365))
    .add_extension(x509.SubjectAlternativeName([x509.DNSName("localhost")]), critical=False)
    .sign(key, hashes.SHA256())
)

cert_bytes = cert.public_bytes(serialization.Encoding.PEM)
key_bytes  = key.private_bytes(
    encoding=serialization.Encoding.PEM,
    format=serialization.PrivateFormat.PKCS8,
    encryption_algorithm=serialization.NoEncryption(),
)

if not cert_bytes or not key_bytes:
    raise RuntimeError("cert_bytes или key_bytes пустые")

sertificate(os.path.abspath("cert.pem"), cert_bytes, mode=0o644)
sertificate(os.path.abspath("key.pem"),  key_bytes,  mode=0o600)

print("Wrote:", os.path.getsize("cert.pem"), "bytes cert.pem;", os.path.getsize("key.pem"), "bytes key.pem")




templates = Jinja2Templates(directory='templates')
app = FastAPI()
app.mount('/static', StaticFiles(directory='static'), name='static')

USERS = 'users.csv'
sessions = {}
SESSION_TIME = timedelta(minutes=10)
white_urls = ['/', '/login', '/logout','/reg']

def logger():
    def decorator(func):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            start_time = time.time()
            result = await func(*args, **kwargs)
            end_time = time.time()
            work_time = round(end_time - start_time, 4)
            if os.path.exists('log.csv'):
                df = pd.read_csv('log.csv')
            else:
                df = pd.DataFrame(columns=["func_name", "work_time", "date_time"])

            data = {
                "func_name": func.__name__,
                "work_time": work_time,
                "date_time": pd.Timestamp.now()
            }
            df = pd.concat([df, pd.DataFrame([data])], ignore_index=True)
            df.to_csv("log.csv", index=False, encoding="utf-8")

            return result
        return wrapper
    return decorator

def hashing_password(password : str) -> str:
    return hashlib.sha256(password.encode()).hexdigest()



@app.middleware('http')
async def check_session(request: Request, call_next):
    if request.url.path in white_urls or request.url.path.startswith('/static'):
        return await call_next(request)
    session_id = request.cookies.get('session_id')
    if not session_id or session_id not in sessions:
        return RedirectResponse(url='/login')
    if datetime.now() - sessions[session_id] > SESSION_TIME:
        del sessions[session_id]
        return RedirectResponse(url='/login')
    return await call_next(request)

@app.get("/", response_class=HTMLResponse)
@logger()
async def root(request: Request):
    return templates.TemplateResponse("login.html", {"request": request})

@app.get("/login", response_class=HTMLResponse)
@logger()
async def get_login_page(request: Request):
    return templates.TemplateResponse('login.html', {'request': request})

@app.post('/login')
@logger()
async def login(request: Request, username: str = Form(...), password: str = Form(...)):
    users = pd.read_csv(USERS)
    entered_hash = hashing_password(password)
    if ((users['user'] == username) & (users['hash_pass'] == entered_hash)).any():
        session_id = str(uuid.uuid4())
        sessions[session_id] = datetime.now()
        response = RedirectResponse(url=f'/home/{username}', status_code=303)
        response.set_cookie(key='session_id', value=session_id)
        return response

    return templates.TemplateResponse(
        'login.html',
        {'request': request, 'error': 'Неверный логин или пароль'}
    )


@app.get("/logout", response_class=HTMLResponse)
@logger()
async def logout(request : Request):
    session_id = request.cookies.get('session_id')
    print(session_id)
    del sessions[session_id]
    return templates.TemplateResponse('login.html', {'request' : request, 
                                    'message' : 'Вы были выброшены из сессии'})

@app.get('/home/{username}', response_class=HTMLResponse)
@logger()
async def get_home_page(request: Request, username: str):
    users = pd.read_csv(USERS)
    return templates.TemplateResponse('home.html', {'request': request, 'username': username})

@app.get('/reg', response_class=HTMLResponse)
@logger()
async def get_registration_page(request : Request):
    return templates.TemplateResponse("reg.html", {"request": request})

@app.post("/reg")
@logger()
async def registration(request: Request, username: str = Form(...),
                        password: str = Form(...), 
                        password_confirm: str = Form(...)):
    users = pd.read_csv(USERS)

    if password != password_confirm: 
        return templates.TemplateResponse(
            'reg.html', 
            {'request': request, 'error': 'Пароли не совпадают'}
        )

    elif username in users['user'].values:
        return templates.TemplateResponse(
            'reg.html', 
            {'request': request, 'error': 'Имя пользователя занято'}
        )

    elif username.lower() == 'admin':
        return templates.TemplateResponse(
            'reg.html',
            {'request': request, 'error': 'Имя admin зарезервировано'}
        )

    else:
        hash_pass = hashing_password(password)
        new_user = pd.DataFrame([{
            "user": username,
            "pass": password,
            "hash_pass": hash_pass,
            "role": "user"
        }])
        users = pd.concat([users, new_user], ignore_index=True)
        users.to_csv(USERS, index=False, encoding="utf-8")
        session_id = str(uuid.uuid4())
        sessions[session_id] = datetime.now()
        response = RedirectResponse(url=f'/home/{username}', status_code=303)
        response.set_cookie(key='session_id', value=session_id)
        return response



@app.exception_handler(StarletteHTTPException)
@logger()
async def http_exception_handler(request: Request, exc: StarletteHTTPException):
    if exc.status_code == 404:
        return templates.TemplateResponse(
            "404.html",
            {"request": request, "error": "Страница не найдена"},
            status_code=404
        )
    return HTMLResponse(content=str(exc.detail), status_code=exc.status_code)

@app.exception_handler(HTTPException)
@logger()
async def custom_http_exception_handler(request: Request, exc: HTTPException):
    if exc.status_code == 403:
        return templates.TemplateResponse(
            "403.html",
            {"request": request, "error": "Доступ запрещён"},
            status_code=403
        )
    return HTMLResponse(content=str(exc.detail), status_code=exc.status_code)

@app.get("/admin")
@logger()
async def admin_panel(request: Request):
    raise HTTPException(status_code=403, detail="Вы не админ")


@app.get("/admin", response_class=HTMLResponse)
async def admin_panel(request: Request):
    session_id = request.cookies.get("session_id")
    if not session_id or session_id not in sessions:
        raise HTTPException(status_code=403, detail="Нет доступа")
    users = pd.read_csv(USERS)
    username = "admin"
    role = users.loc[users["user"] == username, "role"].values[0]
    if role != "admin":
        raise HTTPException(status_code=403, detail="Доступ запрещён")
    return templates.TemplateResponse("admin.html", {"request": request, "username": username})


