class BaseConfig:
    # Statement for enabling the development environment
    DEBUG = False

    # Define the application directory
    import os

    BASE_DIR = os.path.abspath(os.path.dirname(__file__))

    # Define the database - we are working with
    # SQLite for this example
    SQLALCHEMY_DATABASE_URI = os.environ.get(
        "DATABASE_URL", "sqlite:///" + os.path.join(BASE_DIR, "blog.db")
    )

    SQLALCHEMY_TRACK_MODIFICATIONS = True
    DATABASE_CONNECT_OPTIONS = {}

    # Enable protection agains *Cross-site Request Forgery (CSRF)*
    CSRF_ENABLED = True

    # Use a secure, unique and absolutely secret key for
    # signing the data.
    CSRF_SESSION_KEY = "secret"

    # Secret key for signing cookies
    SECRET_KEY = "secret"

    JWT_TOKEN_LOCATION = ["headers"]
    JWT_SECRET_KEY = "super secret"
    JWT_CSRF_METHODS = ["GET", "POST", "PUT", "PATCH", "DELETE"]

    CORS_HEADERS = "Content-Type"

    WTF_CSRF_ENABLED = False
