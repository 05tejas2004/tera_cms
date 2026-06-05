from app import app, db

with app.app_context():
    try:
        db.session.execute(db.text('CREATE TABLE IF NOT EXISTS notification (
            id INTEGER PRIMARY KEY,
            user_id INTEGER,
            complaint_id INTEGER,
            title VARCHAR(200),
            message TEXT,
            is_read BOOLEAN DEFAULT 0,
            created_at DATETIME
        )'))
        db.session.commit()
        print("Notification table created successfully!")
    except Exception as e:
        print(f"Error: {e}")
        