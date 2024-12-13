from flask_migrate import Migrate
from app import db, app  # Import your db and app

# Initialize Flask-Migrate
migrate = Migrate(app, db)

if __name__ == "__main__":
    with app.app_context():
        print("Database setup ready for migrations!")
