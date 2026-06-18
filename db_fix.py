from app import app, db  # Import your Flask app instance and SQLAlchemy db object

def reset_database():
    with app.app_context():
        print("⚠️ Warning: Dropping all database tables...")
        db.drop_all()  # Permanently destroys all tables, columns, and data
        
        print("✅ Creating clean table schemas...")
        db.create_all()  # Re-creates empty tables based on your SQLAlchemy models
        
        print("🚀 Database reset complete!")

if __name__ == '__main__':
    reset_database()