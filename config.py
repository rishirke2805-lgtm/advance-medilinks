import os

class Config:
    """Base application configuration."""
    SECRET_KEY = os.environ.get("SECRET_KEY", "dev-secret-key-change-in-production")
    DATABASE_PATH = os.environ.get(
        "DATABASE_PATH",
        os.path.join(os.path.dirname(__file__), "data", "registrations.db")
    )
