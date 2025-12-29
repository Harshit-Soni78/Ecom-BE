# BharatBazaar API

A FastAPI-based e-commerce backend API for BharatBazaar, built with SQLAlchemy and supporting MySQL/PostgreSQL databases.

## Features

- **User Authentication & Authorization**: JWT-based auth with secure password hashing
- **Product Management**: CRUD operations for products, categories, inventory
- **Order Management**: Complete order lifecycle with status tracking
- **File Upload**: Image and document upload capabilities
- **Email Integration**: SMTP-based email notifications
- **Courier Integration**: Delhivery API integration for shipping
- **Admin Dashboard**: Analytics and management endpoints
- **CORS Enabled**: Configured for frontend integration

## Tech Stack

- **Framework**: FastAPI
- **Database**: SQLAlchemy with MySQL/PostgreSQL support
- **Authentication**: JWT tokens with bcrypt hashing
- **File Storage**: Local storage (configurable for cloud)
- **Email**: SMTP integration
- **Deployment**: Vercel-ready serverless functions

## Quick Start

### Prerequisites

- Python 3.12
- MySQL or PostgreSQL database
- Conda environment (recommended)

### Local Development Setup

1. **Clone the repository**

   ```bash
   git clone https://github.com/Harshit-Soni78/Ecom-BE.git
   cd ecom-be
   ```

2. **Create and activate conda environment**

   ```bash
   conda create -n ecom python=3.12
   conda activate ecom
   ```

3. **Install dependencies**

   ```bash
   pip install -r requirements.txt
   ```

4. **Set up environment variables**

   ```bash
   cp .env.example .env
   # Edit .env with your actual values
   ```

5. **Run database migrations**

   ```bash
   python -c "from app.db.base import Base; from app.db.session import engine; Base.metadata.create_all(bind=engine)"
   ```

6. **Start the server**

   ```bash
   python -m app.main
   ```

The API will be available at `http://127.0.0.1:8000`

## Environment Variables

Copy `.env.example` to `.env` and configure:

```env
# JWT Configuration
JWT_SECRET=your-jwt-secret-key-here

# Database Configuration
DB_USER=your-db-username
DB_PASSWORD=your-db-password
DB_HOST=your-db-host
DB_PORT=3306
DB_NAME=your-db-name
USE_SQLITE=False

# Email Configuration
SMTP_HOST=smtp.gmail.com
SMTP_PORT=587
SMTP_USERNAME=your-email@gmail.com
SMTP_PASSWORD=your-app-password
SMTP_FROM_EMAIL=your-email@gmail.com
SMTP_FROM_NAME=BharatBazaar
EMAIL_ENABLED=true

# API Keys
DELHIVERY_TOKEN=your-delhivery-api-token
```

## API Documentation

Once running, visit:

- **Swagger UI**: `http://127.0.0.1:8000/docs`
- **ReDoc**: `http://127.0.0.1:8000/redoc`
- **OpenAPI Schema**: `http://127.0.0.1:8000/openapi.json`

## Deployment to Vercel

### Prerequisites

- Vercel account
- Cloud database (MySQL/PostgreSQL)

### Steps

1. **Push code to GitHub**

2. **Connect to Vercel**

   - Import project from GitHub
   - Set build command: `pip install -r reduced-requirements.txt`
   - Set install command: (leave default)

3. **Configure Environment Variables**
   In Vercel dashboard > Project Settings > Environment Variables:

   - Add all variables from `.env.example`
   - Set `USE_SQLITE=False`
   - Configure your cloud database credentials

4. **Deploy**
   - Vercel will automatically deploy on push
   - Monitor build logs for any issues

### Vercel Configuration

The `vercel.json` is configured for:

- Python runtime
- Custom requirements file (`reduced-requirements.txt`)
- Route handling for FastAPI

## Project Structure

```bash
ecom-be/
├── app/
│   ├── main.py              # FastAPI application entry point
│   ├── api/
│   │   └── v1/
│   │       ├── api.py       # API router configuration
│   │       └── endpoints/   # API endpoint modules
│   ├── core/
│   │   ├── config.py        # Application configuration
│   │   └── security.py      # Security utilities
│   ├── db/
│   │   ├── base.py          # Database base configuration
│   │   └── session.py       # Database session management
│   ├── models/              # SQLAlchemy models
│   ├── schemas/             # Pydantic schemas
│   ├── services/            # Business logic services
│   └── utils/               # Utility functions
├── uploads/                 # File upload directory
├── requirements.txt         # Full dependencies
├── reduced-requirements.txt # Minimal dependencies for deployment
├── vercel.json              # Vercel deployment config
├── .env.example             # Environment variables template
└── README.md               # This file
```

## Key Endpoints

- `GET /` - Health check
- `POST /api/auth/login` - User login
- `GET /api/products` - List products
- `POST /api/orders` - Create order
- `GET /api/categories` - List categories
- `POST /api/upload` - File upload

## Development

### Running Tests

```bash
pytest
```

### Code Formatting

```bash
black .
isort .
```

### Linting

```bash
flake8 .
```

## Contributing

1. Fork the repository
2. Create a feature branch
3. Make changes
4. Run tests
5. Submit a pull request

## License

This project is licensed under the MIT License.
