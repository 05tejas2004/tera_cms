users = User.query.filter_by(role='Operator').all()

for u in users:
    u.role = 'TechnicalSupport'

db.session.commit()