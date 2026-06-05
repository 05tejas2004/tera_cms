from app import app, db

with app.app_context():
    try:
        db.session.execute(db.text('ALTER TABLE complaint ADD COLUMN created_by INTEGER'))
        db.session.commit()
        print("Column created_by added!")
    except Exception as e:
        print(f"Error: {e}")