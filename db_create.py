from app import app, db, User

with app.app_context():
    db.create_all()
    print("Database created!")
    
    # Create admin user
    if not User.query.filter_by(username='admin').first():
        admin = User(
            name='System Admin',
            username='admin',
            password='admin123',
            role='Admin',
            is_approved=True
        )
        db.session.add(admin)
        db.session.commit()
        print("Admin user created!")
        print("Login: admin / admin123")