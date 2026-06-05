from app import app, db, User

with app.app_context():
    User.query.filter_by(role='FieldWorker').update({'role': 'FieldEngineer'})
    db.session.commit()
    print("Updated successfully!")