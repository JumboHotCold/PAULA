# PauliBot - PostgreSQL Migration & Hybrid Access System 🎓

## Project Overview

Current runtime and release instructions: [MVP operations checklist](PAULA_MVP_OPERATIONS.md) and [stabilization evidence](PAULA_MVP_STABILIZATION_REPORT.md). The older migration/setup sections below are historical. Use Docker PostgreSQL on port 8080 with Vite on 5173; public deployment is pending the supported-framework compatibility pass.

**PauliBot** is a university chatbot system for Saint Paul University Surigao, now featuring:
- ✅ **PostgreSQL Database** (migrated from SQLite3)
- ✅ **Docker Containerization** (production-ready deployment)
- ✅ **Hybrid Access System** (authenticated students + guest visitors)
- ✅ **Secure Authentication** (PBKDF2 password hashing)

---

## What's New in This Version

### 1. Database Migration: SQLite3 → PostgreSQL

**Before:**
```python
DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.sqlite3',
        'NAME': BASE_DIR / 'db.sqlite3',
    }
}
```

**After:**
```python
DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.postgresql',
        'NAME': os.getenv('POSTGRES_DB'),
        'USER': os.getenv('POSTGRES_USER'),
        'PASSWORD': os.getenv('POSTGRES_PASSWORD'),
        'HOST': os.getenv('POSTGRES_HOST'),
        'PORT': os.getenv('POSTGRES_PORT'),
    }
}
```

**Benefits:**
- Production-grade RDBMS (handles concurrent connections)
- Better data integrity and ACID compliance
- Scalable for campus-wide deployment

---

### 2. New Database Models

#### CustomUser Model
```python
class CustomUser(AbstractUser):
    student_id = models.CharField(max_length=20, unique=True)
    # Inherits: username, password (hashed), email, first_name, last_name
```

#### ChatHistory Model
```python
class ChatHistory(models.Model):
    user = models.ForeignKey(CustomUser, on_delete=models.CASCADE)
    message = models.TextField()  # User's question
    response = models.TextField()  # Bot's answer
    timestamp = models.DateTimeField(auto_now_add=True)
```

**Key Features:**
- Foreign key relationship with CASCADE delete
- Indexed on `user` and `timestamp` for fast queries
- Automatic timestamp for conversation ordering

---

### 3. Hybrid Access System

#### Authenticated Students (Login Required)
- **Flow**: Register → Login → Chat → View History
- **Benefit**: Conversation history persists across sessions
- **Implementation**:
  ```python
  if request.user.is_authenticated:
      ChatHistory.objects.create(
          user=request.user,
          message=user_message,
          response=bot_response
      )
      return {'response': bot_response, 'saved': True}
  ```

#### Guest Visitors (No Login)
- **Flow**: Click "Guest Mode" → Chat (transient session)
- **Benefit**: Privacy-conscious (no data collection)
- **Implementation**:
  ```python
  else:  # Guest user
      # Process query but DO NOT save to database
      return {'response': bot_response, 'saved': False}
  ```

---

### 4. New API Endpoints

| Endpoint | Method | Auth Required | Description |
|----------|--------|---------------|-------------|
| `/api/register` | POST | No | Create new student account |
| `/api/login` | POST | No | Authenticate and start session |
| `/api/logout` | POST | Yes | End session |
| `/api/chat` | POST | No | Send message (hybrid logic) |
| `/api/history` | GET | Yes | Retrieve past conversations |

**Example: User Registration**
```bash
curl -X POST http://localhost:8000/api/register \
  -H "Content-Type: application/json" \
  -d '{
    "student_id": "2024-00001",
    "username": "juandelacruz",
    "password": "SecurePass123!",
    "email": "juan@spus.edu.ph"
  }'
```

**Response:**
```json
{
  "id": 1,
  "student_id": "2024-00001",
  "username": "juandelacruz",
  "email": "juan@spus.edu.ph",
  "message": "User registered successfully"
}
```

---

### 5. Docker Deployment

#### Architecture
```
┌─────────────────────────────────────┐
│       Docker Compose                │
│                                     │
│  ┌─────────────┐   ┌─────────────┐ │
│  │   Django    │   │ PostgreSQL  │ │
│  │     App     │◄──┤  Database   │ │
│  │  (Port 8000)│   │ (Port 5432) │ │
│  └─────────────┘   └─────────────┘ │
│                                     │
│  Network: paulibot_network          │
│  Volume: postgres_data (persistent) │
└─────────────────────────────────────┘
```

#### Quick Start
```powershell
# 1. Start containers
docker compose up -d --build

# 2. Create admin account
docker compose exec web python manage.py createsuperuser

# 3. Access application
# Open browser: http://localhost:8000
```

---

## Security Features

### Password Hashing

**Django's PBKDF2 Algorithm:**
- 600,000 iterations (Django 4.2+)
- SHA256 hash function
- Random salt per user

**Example Hashed Password in Database:**
```
pbkdf2_sha256$600000$abcdefghijklmnopqrstuvwxyz123456$7k2x8v9m...
```

### Environment Variables

Sensitive credentials stored in `.env` file:
```env
POSTGRES_PASSWORD=SecurePassword123!
DJANGO_SECRET_KEY=randomly-generated-secret-key
DEBUG=False
```

**Important**: `.env` is excluded from version control via `.gitignore`

---

## File Structure

```
paulibot/
├── chatbot/
│   ├── models.py           ← CustomUser + ChatHistory models
│   ├── serializers.py      ← API request/response validators
│   ├── views.py            ← Authentication + hybrid chat logic
│   ├── urls.py             ← API endpoint routes
│   ├── logic.py            ← Bot intelligence (unchanged)
│   └── data.py             ← Knowledge base (unchanged)
├── paulibot/
│   └── settings.py         ← PostgreSQL config + security settings
├── docker-compose.yml      ← Container orchestration
├── Dockerfile              ← Django app container build
├── requirements.txt        ← Python dependencies
├── .env                    ← Environment variables (SECRET!)
├── .gitignore              ← Exclude sensitive files
├── SETUP_GUIDE.md          ← Deployment instructions
└── manage.py               ← Django management script
```

---

## Database Schema

```sql
-- Users Table (chatbot_customuser)
CREATE TABLE chatbot_customuser (
    id SERIAL PRIMARY KEY,
    student_id VARCHAR(20) UNIQUE NOT NULL,
    username VARCHAR(150) UNIQUE NOT NULL,
    password VARCHAR(128) NOT NULL,  -- Hashed with PBKDF2
    email VARCHAR(254),
    first_name VARCHAR(150),
    last_name VARCHAR(150),
    date_joined TIMESTAMP NOT NULL DEFAULT NOW()
);

-- Chat History Table (chatbot_chathistory)
CREATE TABLE chatbot_chathistory (
    id SERIAL PRIMARY KEY,
    user_id INTEGER REFERENCES chatbot_customuser(id) ON DELETE CASCADE,
    message TEXT NOT NULL,
    response TEXT NOT NULL,
    timestamp TIMESTAMP NOT NULL DEFAULT NOW()
);

-- Index for fast queries
CREATE INDEX idx_user_timestamp ON chatbot_chathistory(user_id, timestamp DESC);
```

---

## Testing the Hybrid Access System

### Test 1: Authenticated User (Chat History Saved)

```bash
# 1. Register
curl -X POST http://localhost:8000/api/register \
  -H "Content-Type: application/json" \
  -d '{"student_id":"2024-00001","username":"test1","password":"Pass123!","email":"test1@spus.edu.ph"}'

# 2. Login (save cookies)
curl -X POST http://localhost:8000/api/login \
  -H "Content-Type: application/json" \
  -c cookies.txt \
  -d '{"username":"test1","password":"Pass123!"}'

# 3. Send chat message
curl -X POST http://localhost:8000/api/chat \
  -H "Content-Type: application/json" \
  -b cookies.txt \
  -d '{"message":"Where is the library?"}'

# Response:
# {"response":"LOCATION:...", "saved":true, "user":"test1"}

# 4. View history
curl -X GET http://localhost:8000/api/history \
  -H "Content-Type: application/json" \
  -b cookies.txt

# Response: Array of past messages
```

**Database Verification:**
```sql
SELECT message, response FROM chatbot_chathistory WHERE user_id=1;
-- Expected: Shows the "Where is the library?" message
```

---

### Test 2: Guest User (Chat History NOT Saved)

```bash
# Send chat message (no login, no cookies)
curl -X POST http://localhost:8000/api/chat \
  -H "Content-Type: application/json" \
  -d '{"message":"What courses do you offer?"}'

# Response:
# {"response":"GENERAL INFORMATION:...", "saved":false, "user":"guest"}
```

**Database Verification:**
```sql
SELECT COUNT(*) FROM chatbot_chathistory;
-- Expected: Count should NOT increase (guest chats not saved)
```

---

## Thesis Defense Checklist

- [x] Migrate database from SQLite3 to PostgreSQL
- [x] Implement user authentication with hashed passwords
- [x] Create hybrid access system (authenticated + guest)
- [x] Dockerize application for production deployment
- [x] Separate sensitive configuration into `.env` file
- [x] Add comprehensive code documentation
- [x] Create setup and deployment guide
- [x] Design database schema with foreign keys and indexes
- [ ] **Install Docker Desktop** (prerequisite for testing)
- [ ] **Test authenticated user flow** (register, login, chat, history)
- [ ] **Test guest user flow** (chat without login, verify no DB save)
- [ ] **Verify password hashing in database** (show pbkdf2 hash)
- [ ] **Prepare demo script** for live demonstration

---

## Key Deliverables for Defense

### 1. Database Schema Documentation
- **File**: This README (see "Database Schema" section above)
- **Contents**: SQL table definitions, foreign keys, indexes

### 2. Backend Logic (Controller/Route)
- **File**: [`chatbot/views.py`](chatbot/views.py)
- **Key Function**: `chat_api()` with hybrid access logic (lines 213-280)

### 3. Docker Setup
- **Files**: 
  - [`docker-compose.yml`](docker-compose.yml) - Container orchestration
  - [`Dockerfile`](Dockerfile) - Django app container
  - [`.env`](.env) - Environment variables
  - [`requirements.txt`](requirements.txt) - Python dependencies

### 4. Setup Guide
- **File**: [`SETUP_GUIDE.md`](SETUP_GUIDE.md)
- **Contents**: Step-by-step deployment instructions

---

## Technologies Used

| Component | Technology | Version |
|-----------|------------|---------|
| **Backend Framework** | Django | 4.2.10 |
| **API Framework** | Django REST Framework | 3.14.0 |
| **Database** | PostgreSQL | 16 (Alpine) |
| **Database Adapter** | psycopg2-binary | 2.9.9 |
| **WSGI Server** | Gunicorn | 21.2.0 |
| **Containerization** | Docker + Docker Compose | Latest |
| **Password Hashing** | PBKDF2 (Django built-in) | 600,000 iterations |
| **Python** | 3.11 | - |

---

## Contact & Support

**Developer**: Senior Full-Stack Developer & DevOps Engineer  
**Project**: PauliBot Capstone Thesis  
**University**: Saint Paul University Surigao  
**Year**: 2024

For questions or issues:
1. Review [`SETUP_GUIDE.md`](SETUP_GUIDE.md) for troubleshooting
2. Check Docker logs: `docker compose logs -f`
3. Verify environment variables in `.env`

---

## License

This project is developed as part of a university capstone thesis.

---

**Good luck with your thesis defense!** 🚀🎓
