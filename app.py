from flask import Flask, render_template, redirect, url_for, request, flash
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager, UserMixin, login_user, login_required, logout_user, current_user
from flask import Flask, render_template, request, redirect, url_for, flash, Response
from datetime import datetime
from fpdf import FPDF
import os
from sqlalchemy import func
import pandas as pd
from werkzeug.utils import secure_filename
from flask_login import login_user
from datetime import timedelta
import uuid
import json
from flask import jsonify

app = Flask(__name__)
app.config['SECRET_KEY'] = 'tera-secret-key'
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///cms.db'
app.config['UPLOAD_FOLDER'] = 'static/uploads'

db = SQLAlchemy(app)
login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'login'

# Add this temporarily to your app.py and run once


# --- Models ---
class User(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100))
    username = db.Column(db.String(100), unique=True)
    password = db.Column(db.String(100))
    role = db.Column(db.String(20))
    is_approved = db.Column(db.Boolean, default=False)
    device_token = db.Column(db.String(100), nullable=True)  # ✅ Add this

class Complaint(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    complaint_id = db.Column(db.String(20), unique=True)
    title = db.Column(db.String(200))
    description = db.Column(db.Text)
    category = db.Column(db.String(50))
    priority = db.Column(db.String(20))
    location = db.Column(db.String(200))
    status = db.Column(db.String(20), default='Pending')
    created_at = db.Column(db.DateTime, default=datetime.now)
    assigned_to = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=True)
    accepted_at = db.Column(db.DateTime, nullable=True)  # Add THIS line
    assigned_at = db.Column(db.DateTime, nullable=True)
    resolved_at = db.Column(db.DateTime, nullable=True)
    resolution_remarks = db.Column(db.Text, nullable=True)
    worker_location = db.Column(db.String(100), nullable=True)
    created_by = db.Column(db.Integer, db.ForeignKey('user.id'))

class ComplaintImage(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    complaint_id = db.Column(db.Integer, db.ForeignKey('complaint.id'))
    filename = db.Column(db.String(200))

class Notification(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'))
    complaint_id = db.Column(db.Integer, db.ForeignKey('complaint.id'))
    title = db.Column(db.String(200))
    message = db.Column(db.Text)
    is_read = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.DateTime, default=datetime.now)

@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

# --- Helper Functions ---
def get_resolution_time(created_at, resolved_at):
    if created_at and resolved_at:
        diff = resolved_at - created_at
        hours = diff.total_seconds() / 3600
        if hours < 1:
            return f"{int(diff.total_seconds() / 60)} min"
        elif hours < 24:
            return f"{int(hours)} hrs"
        return f"{int(hours / 24)} days"
    return "-"

# --- Routes ---
# Add this somewhere in your app (like after db.create_all())

@app.route('/')
def home():
    return redirect(url_for('login'))

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        new_user = User(
            name=request.form['name'],
            username=request.form['username'],
            password=request.form['password'],
            role=request.form['role']
        )
        db.session.add(new_user)
        db.session.commit()
        flash('Registration submitted! Waiting for Admin approval.')
        return redirect(url_for('login'))
    return render_template('register.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    # Handle AJAX login (from JavaScript)
    if request.is_json:
        data = request.get_json()
        user = User.query.filter_by(username=data.get('username')).first()
        if user and user.password == data.get('password'):
            if not user.is_approved:
                return jsonify({'success': False, 'message': 'Account pending approval'}), 401
            
            remember_me = data.get('remember_me', False)
            login_user(user, remember=remember_me)
            
            if remember_me:
                if not user.device_token:
                    user.device_token = str(uuid.uuid4())
                    db.session.commit()
            
            return jsonify({'success': True, 'role': user.role})
        return jsonify({'success': False, 'message': 'Invalid credentials'}), 401
    
    # Handle FORM submission (HTML form)
    if request.method == 'POST':
        user = User.query.filter_by(username=request.form['username']).first()
        if user and user.password == request.form['password']:
            if not user.is_approved:
                flash('Account pending approval by Admin.')
                return redirect(url_for('login'))
            
            remember_me = request.form.get('remember_me', False)
            login_user(user, remember=remember_me)
            
            # ✅ If remember me, generate device token
            if remember_me:
                if not user.device_token:
                    user.device_token = str(uuid.uuid4())
                    db.session.commit()
            
            # ✅ FIX: Redirect to dashboard based on role (NOT JSON!)
            if user.role == 'Admin':
                return redirect(url_for('admin_dashboard'))
            elif user.role == 'Operator':
                return redirect(url_for('operator_dashboard'))
            elif user.role == 'HelpDesk':
                return redirect(url_for('helpdesk_dashboard'))
            elif user.role == 'FieldEngineer':
                return redirect(url_for('worker_dashboard'))
            else:
                return redirect(url_for('dashboard'))
        
        flash('Invalid credentials')
        return redirect(url_for('login'))
    
    return render_template('login.html')

@app.route('/auto_login', methods=['POST'])
def auto_login():
    """Auto login using device token"""
    data = request.get_json()
    device_token = data.get('device_token')
    
    if device_token:
        user = User.query.filter_by(device_token=device_token, is_approved=True).first()
        if user:
            login_user(user, remember=True)
            return jsonify({'success': True, 'role': user.role})
    
    return jsonify({'success': False}), 401

@app.route('/dashboard')
@login_required
def dashboard():
    if current_user.role == 'Admin': return redirect(url_for('admin_dashboard'))
    if current_user.role == 'Operator': return redirect(url_for('operator_dashboard'))
    if current_user.role == 'HelpDesk': return redirect(url_for('helpdesk_dashboard'))
    if current_user.role == 'FieldEngineer': return redirect(url_for('worker_dashboard'))
    return "Role not defined"

@app.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect(url_for('login'))

# ============================================
# ADMIN DASHBOARD
# ============================================

@app.route('/admin')
@login_required
def admin_dashboard():
    if current_user.role != 'Admin':
        return redirect(url_for('dashboard'))
    
    # Get all users
    all_users = User.query.all()
    
    # Get complaints
    complaints = Complaint.query.filter(
        Complaint.status.in_(['Pending', 'Active', 'Closed'])
    ).order_by(Complaint.created_at.desc()).all()
    
    # Stats
    total = len(complaints)
    pending = len([c for c in complaints if c.status == 'Pending'])
    active = len([c for c in complaints if c.status == 'Active'])
    closed = len([c for c in complaints if c.status == 'Closed'])
    
    # Pending users
    pending_users = User.query.filter_by(is_approved=False).all()
    
    # Filter by status
    filter_status = request.args.get('status')
    if filter_status:
        filtered_complaints = [c for c in complaints if c.status == filter_status]
    else:
        filtered_complaints = complaints
    
    return render_template('admin_dashboard.html',
                          total=total,
                          pending=pending,
                          active=active,
                          closed=closed,
                          all_users=all_users,
                          pending_users=pending_users,
                          complaints=complaints,
                          filtered_complaints=filtered_complaints,
                          current_time=datetime.now())
# ============================================
# ADMIN - USER MANAGEMENT
# ============================================

@app.route('/admin/users')
@login_required
def user_management():
    if current_user.role != 'Admin': return redirect(url_for('dashboard'))
    
    all_users = User.query.all()
    pending_users = User.query.filter_by(is_approved=False).all()
    approved_users = User.query.filter_by(is_approved=True).all()
    
    # Count users by role
    admin_count = User.query.filter_by(role='Admin', is_approved=True).count()
    operator_count = User.query.filter_by(role='Operator', is_approved=True).count()
    helpdesk_count = User.query.filter_by(role='HelpDesk', is_approved=True).count()
    engineer_count = User.query.filter_by(role='FieldEngineer', is_approved=True).count()
    
    return render_template('user_management.html', 
                         all_users=all_users,
                         pending_users=pending_users,
                         approved_users=approved_users,
                         admin_count=admin_count,
                         operator_count=operator_count,
                         helpdesk_count=helpdesk_count,
                         engineer_count=engineer_count)

@app.route('/admin/delete_user/<int:user_id>')
@login_required
def admin_delete_user(user_id):
    if current_user.role != 'Admin': return redirect(url_for('dashboard'))
    
    user = User.query.get(user_id)
    if user:
        # Don't delete admin
        if user.role == 'Admin':
            flash('Cannot delete Admin user!', 'error')
        else:
            db.session.delete(user)
            db.session.commit()
            flash(f'User {user.username} deleted successfully!', 'success')
    
    return redirect(url_for('user_management'))

@app.route('/admin/toggle_user_status/<int:user_id>')
@login_required
def toggle_user_status(user_id):
    if current_user.role != 'Admin': return redirect(url_for('dashboard'))
    
    user = User.query.get(user_id)
    if user and user.role != 'Admin':
        user.is_approved = not user.is_approved
        db.session.commit()
        status = "approved" if user.is_approved else "deactivated"
        flash(f'User {user.username} {status}!', 'success')
    
    return redirect(url_for('user_management'))

@app.route('/admin/approve_user/<int:user_id>')
@login_required
def approve_user(user_id):
    if current_user.role != 'Admin': return redirect(url_for('dashboard'))
    user = User.query.get(user_id)
    user.is_approved = True
    db.session.commit()
    return redirect(url_for('admin_dashboard'))

@app.route('/admin/reject_user/<int:user_id>')
@login_required
def reject_user(user_id):
    if current_user.role != 'Admin': return redirect(url_for('dashboard'))
    user = User.query.get(user_id)
    db.session.delete(user)
    db.session.commit()
    return redirect(url_for('admin_dashboard'))

@app.route('/admin/delete_user/<int:user_id>')
@login_required
def delete_user(user_id):
    if current_user.role != 'Admin': return redirect(url_for('dashboard'))
    user = User.query.get(user_id)
    db.session.delete(user)
    db.session.commit()
    return redirect(url_for('admin_dashboard'))

# ============================================
# GENERATE PDF REPORT
# ============================================

@app.route('/generate_report')
@login_required
def generate_report():
    if current_user.role != 'Admin':
        return redirect(url_for('dashboard'))
    
    # Get complaints
    complaints = Complaint.query.filter(
        db.or_(
            Complaint.status == 'Pending',
            Complaint.status == 'Active',
            Complaint.status == 'Closed'
        )
    ).order_by(Complaint.created_at.desc()).all()
    
    # Get all users for role lookup
    all_users = User.query.all()
    user_dict = {u.id: u for u in all_users}
    
    # Create PDF
    pdf = FPDF('P', 'mm', 'A4')
    pdf.add_page()
    pdf.set_auto_page_break(True, 10)
    
    # Title
    pdf.set_font('Arial', 'B', 16)
    pdf.cell(0, 10, 'Complaint Management System - Report', 0, 1, 'C')
    
    # Date
    pdf.set_font('Arial', '', 10)
    pdf.cell(0, 8, f'Generated: {datetime.now().strftime("%Y-%m-%d %H:%M")}', 0, 1, 'C')
    pdf.ln(5)
    
    # Summary
    pdf.set_font('Arial', 'B', 12)
    pdf.cell(0, 10, 'Summary', 0, 1, 'L')
    
    pdf.set_font('Arial', '', 10)
    total = len(complaints)
    pending = len([c for c in complaints if c.status == 'Pending'])
    active = len([c for c in complaints if c.status == 'Active'])
    closed = len([c for c in complaints if c.status == 'Closed'])
    
    pdf.cell(50, 8, f'Total: {total}', 0, 0, 'L')
    pdf.cell(50, 8, f'Pending: {pending}', 0, 0, 'L')
    pdf.cell(50, 8, f'Active: {active}', 0, 0, 'L')
    pdf.cell(50, 8, f'Closed: {closed}', 0, 1, 'L')
    pdf.ln(5)
    
    # Table Header
    pdf.set_font('Arial', 'B', 7)
    pdf.set_fill_color(200, 200, 200)
    
    # Columns with Role (total ~195mm)
    pdf.cell(18, 10, 'Complaint ID', 1, 0, 'C', 1)
    pdf.cell(25, 10, 'Title', 1, 0, 'C', 1)
    pdf.cell(20, 10, 'Category', 1, 0, 'C', 1)
    pdf.cell(25, 10, 'Location', 1, 0, 'C', 1)
    pdf.cell(15, 10, 'Status', 1, 0, 'C', 1)
    pdf.cell(22, 10, 'Resolved By', 1, 0, 'C', 1)
    pdf.cell(18, 10, 'Role', 1, 0, 'C', 1)
    pdf.cell(20, 10, 'Created', 1, 0, 'C', 1)
    pdf.cell(20, 10, 'Accepted', 1, 0, 'C', 1)
    pdf.cell(12, 10, 'Time', 1, 1, 'C', 1)
    
    # Table Data
    pdf.set_font('Arial', '', 6)
    
    for i, comp in enumerate(complaints):
        # Alternate row colors
        if i % 2 == 0:
            pdf.set_fill_color(245, 245, 245)
        else:
            pdf.set_fill_color(255, 255, 255)
        
        # Complaint ID
        pdf.cell(18, 7, str(comp.complaint_id)[:10], 1, 0, 'C', 1)
        
        # Title
        pdf.cell(25, 7, str(comp.title)[:14], 1, 0, 'L', 1)
        
        # Category
        pdf.cell(20, 7, str(comp.category)[:12], 1, 0, 'L', 1)
        
        # Location
        pdf.cell(25, 7, str(comp.location)[:14], 1, 0, 'L', 1)
        
        # Status
        pdf.cell(15, 7, comp.status, 1, 0, 'C', 1)
        
        # Resolved By
        resolved_name = '-'
        resolved_role = '-'
        if comp.assigned_to and comp.assigned_to in user_dict:
            resolved_name = user_dict[comp.assigned_to].name[:12]
            resolved_role = user_dict[comp.assigned_to].role[:10]
        
        pdf.cell(22, 7, resolved_name, 1, 0, 'L', 1)
        pdf.cell(18, 7, resolved_role, 1, 0, 'L', 1)
        
        # Created
        created = comp.created_at.strftime('%Y-%m-%d') if comp.created_at else '-'
        pdf.cell(20, 7, created, 1, 0, 'C', 1)
        
        # Accepted
        accepted = comp.assigned_at.strftime('%Y-%m-%d') if comp.assigned_at else '-'
        pdf.cell(20, 7, accepted, 1, 0, 'C', 1)
        
        # Time Difference
        if comp.created_at and comp.assigned_at:
            diff = comp.assigned_at - comp.created_at
            hours = diff.total_seconds() / 3600
            if hours < 1:
                time_diff = f"{int(diff.total_seconds() // 60)}m"
            elif hours < 24:
                time_diff = f"{int(hours)}h"
            else:
                time_diff = f"{int(hours // 24)}d"
        elif comp.created_at:
            diff = datetime.now() - comp.created_at
            hours = diff.total_seconds() / 3600
            if hours < 1:
                time_diff = f"{int(diff.total_seconds() // 60)}m"
            elif hours < 24:
                time_diff = f"{int(hours)}h"
            else:
                time_diff = f"{int(hours // 24)}d"
        else:
            time_diff = '-'
        
        pdf.cell(12, 7, time_diff, 1, 1, 'C', 1)
    
    # Footer
    pdf.ln(10)
    pdf.set_font('Arial', 'I', 8)
    pdf.cell(0, 5, 'Page 1/1', 0, 0, 'R')
    
    # Return PDF
    from flask import make_response
    response = make_response(pdf.output(dest='S').encode('latin-1'))
    response.headers['Content-Type'] = 'application/pdf'
    response.headers['Content-Disposition'] = 'attachment; filename=complaint_report.pdf'
    return response
# ============================================
# ADMIN - STATISTICS
# ============================================
ALLOWED_EXTENSIONS = {'xlsx', 'xls'}

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS


# ============================================
# THEN, ADD THE ROUTE AFTER ALL OTHER ROUTES
# ============================================

@app.route('/admin/upload_users', methods=['GET', 'POST'])
@login_required
def upload_users():
    if current_user.role != 'Admin':
        return redirect(url_for('dashboard'))
    
    if request.method == 'POST':
        if 'file' not in request.files:
            flash('No file selected!', 'error')
            return redirect(request.url)
        
        file = request.files['file']
        
        if file.filename == '':
            flash('No file selected!', 'error')
            return redirect(request.url)
        
        if file and allowed_file(file.filename):
            filename = secure_filename(file.filename)
            filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
            os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)
            file.save(filepath)
            
            try:
                # Read Excel file
                df = pd.read_excel(filepath)
                
                # Required columns
                required_cols = ['name', 'username', 'password', 'role']
                
                # Check if columns exist
                missing_cols = [col for col in required_cols if col not in df.columns]
                if missing_cols:
                    flash(f'Missing columns: {missing_cols}', 'error')
                    return redirect(request.url)
                
                # Create/Update users
                created_count = 0
                updated_count = 0
                skipped_count = 0
                
                for index, row in df.iterrows():
                    name = str(row['name']).strip()
                    username = str(row['username']).strip()
                    password = str(row['password']).strip()
                    role = str(row['role']).strip()
                    
                    # Validate role
                    if role not in ['Admin', 'Operator', 'HelpDesk', 'FieldEngineer']:
                        skipped_count += 1
                        continue
                    
                    # Check if user exists
                    existing_user = User.query.filter_by(username=username).first()
                    
                    if existing_user:
                        # Update existing user (only name and role)
                        existing_user.name = name
                        existing_user.role = role
                        updated_count += 1
                    else:
                        # Create new user - use password directly
                        new_user = User(
                            name=name,
                            username=username,
                            password=password,  # Direct assignment
                            role=role,
                            is_approved=True
                        )
                        db.session.add(new_user)
                        created_count += 1
                
                db.session.commit()
                os.remove(filepath)
                
                flash(f'Successfully! Created: {created_count}, Updated: {updated_count}, Skipped: {skipped_count}', 'success')
                return redirect(url_for('admin_dashboard'))
            
            except Exception as e:
                flash(f'Error reading file: {str(e)}', 'error')
                return redirect(request.url)
    
    return render_template('upload_users.html')
# ============================================
# ADMIN - STATISTICS
# ============================================

@app.route('/admin/statistics')
@login_required
def admin_statistics():
    if current_user.role != 'Admin':
        return redirect(url_for('dashboard'))
    
    # === User Statistics ===
    total_users = User.query.count()
    approved_users = User.query.filter_by(is_approved=True).count()
    pending_users = User.query.filter_by(is_approved=False).count()
    engineers = User.query.filter_by(role='FieldEngineer', is_approved=True).count()
    operators = User.query.filter_by(role='Operator', is_approved=True).count()
    helpdesk = User.query.filter_by(role='HelpDesk', is_approved=True).count()
    admins = User.query.filter_by(role='Admin', is_approved=True).count()
    
    # === Complaint Statistics - ONLY Pending, Active, Closed ===
    total_complaints = Complaint.query.filter(
        Complaint.status.in_(['Pending', 'Active', 'Closed'])
    ).count()
    
    pending = Complaint.query.filter_by(status='Pending').count()
    active = Complaint.query.filter_by(status='Active').count()
    closed = Complaint.query.filter_by(status='Closed').count()
    resolved = 0  # Not showing Resolved
    rejected = 0  # Not showing Rejected
    
    # === Category Statistics - ONLY Pending, Active, Closed ===
    category_counts = {}
    valid_complaints = Complaint.query.filter(
        Complaint.status.in_(['Pending', 'Active', 'Closed'])
    ).all()
    
    for c in valid_complaints:
        if c.category:
            cat = c.category
            if cat in category_counts:
                category_counts[cat] += 1
            else:
                category_counts[cat] = 1
    
    # === Priority Statistics - ONLY Pending, Active, Closed ===
    high_priority = Complaint.query.filter(
        Complaint.status.in_(['Pending', 'Active', 'Closed']),
        Complaint.priority == 'High'
    ).count()
    
    medium_priority = Complaint.query.filter(
        Complaint.status.in_(['Pending', 'Active', 'Closed']),
        Complaint.priority == 'Medium'
    ).count()
    
    low_priority = Complaint.query.filter(
        Complaint.status.in_(['Pending', 'Active', 'Closed']),
        Complaint.priority == 'Low'
    ).count()
    
    # === Engineer Performance - ONLY Pending, Active, Closed ===
    engineer_list = []
    engineers_users = User.query.filter_by(role='FieldEngineer', is_approved=True).all()
    
    for eng in engineers_users:
        # Count only Pending, Active, Closed
        assigned_count = Complaint.query.filter(
            Complaint.assigned_to == eng.id,
            Complaint.status.in_(['Pending', 'Active', 'Closed'])
        ).count()
        
        closed_count = Complaint.query.filter_by(
            assigned_to=eng.id, 
            status='Closed'
        ).count()
        
        active_count = Complaint.query.filter_by(
            assigned_to=eng.id, 
            status='Active'
        ).count()
        
        engineer_list.append({
            'name': eng.name,
            'assigned': assigned_count,
            'resolved': closed_count,
            'active': active_count
        })
    
    return render_template('admin_statistics.html',
                         total_users=total_users,
                         approved_users=approved_users,
                         pending_users=pending_users,
                         engineers=engineers,
                         operators=operators,
                         helpdesk=helpdesk,
                         admins=admins,
                         total_complaints=total_complaints,
                         pending=pending,
                         active=active,
                         resolved=resolved,
                         closed=closed,
                         rejected=rejected,
                         category_counts=category_counts,
                         high_priority=high_priority,
                         medium_priority=medium_priority,
                         low_priority=low_priority,
                         engineer_performance=engineer_list)

# ============================================
# ADMIN - UPDATE COMPLAINT STATUS
# ============================================

@app.route('/admin/update_status/<int:comp_id>', methods=['POST'])
@login_required
def admin_update_status(comp_id):
    if current_user.role != 'Admin': 
        return redirect(url_for('dashboard'))
    
    complaint = Complaint.query.get(comp_id)
    if not complaint:
        flash('Complaint not found!', 'error')
        return redirect(url_for('admin_dashboard'))
    
    new_status = request.form.get('status', '').strip()
    
    if new_status:
        old_status = complaint.status
        complaint.status = new_status
        
        if new_status == 'Closed':
            complaint.resolved_at = datetime.now()
        
        db.session.commit()
        flash(f'Complaint {complaint.complaint_id} status updated from {old_status} to {new_status}!', 'success')
    
    return redirect(url_for('admin_dashboard'))
# ============================================
# ADMIN - DOWNLOAD ALL USERS EXCEL
# ============================================


@app.route('/admin/download_users_excel')
@login_required
def download_users_excel():
    if current_user.role != 'Admin':
        return redirect(url_for('dashboard'))
    
    # Get all users
    users = User.query.all()
    
    # Create DataFrame
    data = []
    for user in users:
        data.append({
            'name': user.name,
            'username': user.username,
            'password': user.password,  # Note: This shows hashed password
            'role': user.role
        })
    
    df = pd.DataFrame(data)
    
    # Create Excel file
    filepath = os.path.join(app.config['UPLOAD_FOLDER'], 'all_users.xlsx')
    os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)
    
    df.to_excel(filepath, index=False)
    
    # Return file for download
    from flask import send_file
    
    return send_file(
        filepath,
        as_attachment=True,
        download_name='all_users.xlsx',
        mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
    )

# ============================================
# ADMIN - VIEW COMPLAINT DETAILS
# ============================================

@app.route('/admin/view_complaint/<int:comp_id>')
@login_required
def admin_view_complaint(comp_id):
    if current_user.role != 'Admin': return redirect(url_for('dashboard'))
    
    complaint = Complaint.query.get(comp_id)
    all_users = User.query.all()
    images = ComplaintImage.query.filter_by(complaint_id=complaint.id).all()
    
    return render_template('admin_view_complaint.html', 
                         complaint=complaint,
                         all_users=all_users,
                         images=images)
# ============================================
# OPERATOR DASHBOARD
# ============================================

@app.route('/operator')
@login_required
def operator_dashboard():
    if current_user.role != 'Operator': return redirect(url_for('dashboard'))
    
    complaints = Complaint.query.all()
    resolved_complaints = Complaint.query.filter_by(status='Resolved').all()
    all_users = User.query.all()  # Add this - get all users
    
    complaint_images = {}
    for c in resolved_complaints:
        images = ComplaintImage.query.filter_by(complaint_id=c.id).all()
        complaint_images[c.id] = images
    
    return render_template('operator_dashboard.html', 
                         complaints=complaints,
                         resolved_complaints=resolved_complaints,
                         all_users=all_users,
                         complaint_images=complaint_images,
                         get_resolution_time=get_resolution_time)

# ============================================
# OPERATOR - VERIFY COMPLAINT (Separate Page)
# ============================================

@app.route('/operator/verify/<int:comp_id>')
@login_required
def verify_complaint(comp_id):
    if current_user.role != 'Operator': return redirect(url_for('dashboard'))
    
    complaint = Complaint.query.get(comp_id)
    if not complaint:
        flash('Complaint not found!', 'error')
        return redirect(url_for('operator_dashboard'))
    
    # Get assigned user details
    assigned_user = User.query.get(complaint.assigned_to) if complaint.assigned_to else None
    
    # Get resolution images
    images = ComplaintImage.query.filter_by(complaint_id=complaint.id).all()
    
    # Get all users for display
    all_users = User.query.all()
    
    return render_template('verify_complaint.html', 
                         complaint=complaint,
                         assigned_user=assigned_user,
                         images=images,
                         all_users=all_users,
                         get_resolution_time=get_resolution_time)

# ============================================
# OPERATOR - PHOTO VIEWER (Full Screen)
# ============================================

@app.route('/operator/photos/<int:comp_id>')
@login_required
def photo_viewer(comp_id):
    if current_user.role not in ['Operator', 'HelpDesk', 'Admin']:
        return redirect(url_for('dashboard'))
    
    complaint = Complaint.query.get(comp_id)
    if not complaint:
        flash('Complaint not found!', 'error')
        return redirect(url_for('operator_dashboard'))
    
    images = ComplaintImage.query.filter_by(complaint_id=complaint.id).all()
    all_complaints = Complaint.query.filter(Complaint.id != complaint.id).order_by(Complaint.id.desc()).all()
    
    # Fix: Convert SQLAlchemy objects to list of filenames (strings)
    image_list = [img.filename for img in images]
    
    return render_template('photo_viewer.html', 
                         complaint=complaint,
                         image_list=image_list,  # Use this instead of images
                         all_complaints=all_complaints)
# ============================================
# HELP DESK DASHBOARD
# ============================================

@app.route('/helpdesk')
@login_required
def helpdesk_dashboard():
    if current_user.role != 'HelpDesk': return redirect(url_for('dashboard'))
    
    complaints = Complaint.query.all()
    engineers = User.query.filter_by(role='FieldEngineer', is_approved=True).all()
    
    # Get filter status from URL
    filter_status = request.args.get('status')
    
    if filter_status:
        filtered_complaints = [c for c in complaints if c.status == filter_status]
    else:
        filtered_complaints = complaints
    
    return render_template('helpdesk_dashboard.html', 
                         complaints=complaints, 
                         engineers=engineers,
                         filtered_complaints=filtered_complaints)
# ============================================
# FIELD ENGINEER DASHBOARD
# ============================================

@app.route('/worker')
@login_required
def worker_dashboard():
    if current_user.role != 'FieldEngineer': 
        return redirect(url_for('dashboard'))
    
    # Get all engineers for display
    engineers = User.query.filter_by(role='FieldEngineer', is_approved=True).all()
    
    # Get filter status
    filter_status = request.args.get('status')
    
    # All pending (available)
    pending_complaints = Complaint.query.filter_by(status='Pending').all()
    
    # My complaints
    my_complaints = Complaint.query.filter_by(assigned_to=current_user.id).all()
    my_pending = [c for c in my_complaints if c.status == 'Pending']
    my_active = [c for c in my_complaints if c.status == 'Active']
    my_resolved = [c for c in my_complaints if c.status == 'Resolved']
    my_history = [c for c in my_complaints if c.status in ['Closed', 'Rejected']]
    
    return render_template('worker_dashboard.html',
                         pending_complaints=pending_complaints,
                         my_complaints=my_complaints,
                         my_pending=my_pending,
                         my_active=my_active,
                         my_resolved=my_resolved,
                         my_history=my_history,
                         engineers=engineers)

# ============================================
# WORKER - GENERATE REPORT
# ============================================

@app.route('/worker/report')
@login_required
def worker_generate_report():
    if current_user.role != 'FieldEngineer': 
        return redirect(url_for('dashboard'))
    
    # Get only this worker's complaints
    complaints = Complaint.query.filter_by(assigned_to=current_user.id).order_by(Complaint.created_at.desc()).all()
    
    class PDF(FPDF):
        def header(self):
            self.set_font('Arial', 'B', 16)
            self.cell(0, 10, 'Field Engineer - Complaint Report', 0, 1, 'C')
            self.set_font('Arial', 'I', 10)
            self.cell(0, 8, f'Engineer: {current_user.name}', 0, 1, 'C')
            self.ln(3)
        
        def footer(self):
            self.set_y(-15)
            self.set_font('Arial', 'I', 8)
            self.cell(0, 10, f'Generated on: {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}', 0, 0, 'C')
    
    pdf = PDF(orientation='L', unit='mm', format='A4')
    pdf.add_page()
    pdf.set_auto_page_break(auto=True, margin=15)
    
    # Column widths
    col_widths = [30, 50, 30, 40, 25, 32, 32, 25]
    headers = ['ID', 'Title', 'Category', 'Location', 'Status', 'Accepted', 'Resolved', 'Time Taken']
    
    # Table Header
    pdf.set_font('Arial', 'B', 9)
    pdf.set_fill_color(40, 44, 52)
    pdf.set_text_color(255, 255, 255)
    
    for i, header in enumerate(headers):
        pdf.cell(col_widths[i], 8, header, 1, 0, 'C', True)
    pdf.ln()
    
    # Table Data
    pdf.set_font('Arial', '', 8)
    pdf.set_text_color(0, 0, 0)
    
    for idx, c in enumerate(complaints):
        if idx % 2 == 0:
            pdf.set_fill_color(240, 240, 240)
        else:
            pdf.set_fill_color(255, 255, 255)
        
        # Time taken
        time_taken = "-"
        if c.resolved_at and c.created_at:
            diff = c.resolved_at - c.created_at
            total_minutes = int(diff.total_seconds() / 60)
            if total_minutes < 60:
                time_taken = f"{total_minutes} min"
            elif total_minutes < 1440:
                hours = total_minutes // 60
                time_taken = f"{hours} hr" if hours == 1 else f"{hours} hrs"
            else:
                days = total_minutes // 1440
                time_taken = f"{days} day" if days == 1 else f"{days} days"
        elif c.status == 'Active':
            time_taken = "In Progress"
        
        accepted_date = c.assigned_at.strftime('%Y-%m-%d %H:%M') if c.assigned_at else '-'
        resolved_date = c.resolved_at.strftime('%Y-%m-%d %H:%M') if c.resolved_at else '-'
        
        pdf.cell(col_widths[0], 7, str(c.complaint_id), 1, 0, 'L', True)
        pdf.cell(col_widths[1], 7, str(c.title)[:22], 1, 0, 'L', True)
        pdf.cell(col_widths[2], 7, str(c.category)[:12], 1, 0, 'L', True)
        pdf.cell(col_widths[3], 7, str(c.location)[:18], 1, 0, 'L', True)
        pdf.cell(col_widths[4], 7, str(c.status), 1, 0, 'C', True)
        pdf.cell(col_widths[5], 7, accepted_date[:14], 1, 0, 'C', True)
        pdf.cell(col_widths[6], 7, resolved_date[:14], 1, 0, 'C', True)
        pdf.cell(col_widths[7], 7, time_taken, 1, 1, 'C', True)
    
    pdf.ln(10)
    
    # Summary
    pdf.set_font('Arial', 'B', 12)
    pdf.cell(0, 10, 'MY SUMMARY', 0, 1, 'L')
    pdf.ln(3)
    
    pdf.set_font('Arial', '', 10)
    total = len(complaints)
    active = len([c for c in complaints if c.status == 'Active'])
    resolved = len([c for c in complaints if c.status == 'Resolved'])
    closed = len([c for c in complaints if c.status == 'Closed'])
    rejected = len([c for c in complaints if c.status == 'Rejected'])
    
    summary_data = [
        ('Total Complaints', str(total)),
        ('Active', str(active)),
        ('Resolved (Waiting)', str(resolved)),
        ('Closed (Approved)', str(closed)),
        ('Rejected', str(rejected))
    ]
    
    pdf.set_fill_color(220, 220, 220)
    for label, value in summary_data:
        pdf.cell(50, 8, label, 1, 0, 'L', True)
        pdf.cell(30, 8, value, 1, 1, 'C', True)
    
    # Output PDF
    from flask import make_response
    pdf_output = pdf.output(dest='S').encode('latin-1')
    
    response = make_response(pdf_output)
    response.headers['Content-Type'] = 'application/pdf'
    response.headers['Content-Disposition'] = f'attachment; filename=my_report_{datetime.now().strftime("%Y%m%d_%H%M%S")}.pdf'
    
    return response
# ============================================
# NOTIFICATIONS
# ============================================

@app.route('/notifications')
@login_required
def notifications():
    notifs = Notification.query.filter_by(user_id=current_user.id).order_by(Notification.created_at.desc()).all()
    return render_template('notifications.html', notifications=notifs)

@app.route('/mark_notif_read/<int:notif_id>')
@login_required
def mark_notif_read(notif_id):
    notif = Notification.query.get(notif_id)
    if notif and notif.user_id == current_user.id:
        notif.is_read = True
        db.session.commit()
    return redirect(url_for('notifications'))

# ============================================
# REGISTER COMPLAINT
# ============================================

# ============================================
# REGISTER COMPLAINT
# ============================================

@app.route('/register_complaint', methods=['GET', 'POST'])
@login_required
def register_complaint():
    if current_user.role not in ['HelpDesk', 'Operator']:
        return redirect(url_for('dashboard'))
    
    if request.method == 'POST':
        new_comp = Complaint(
            complaint_id=f"CMP-{datetime.now().strftime('%Y%m%d%H%M%S')}",
            title=request.form['title'],
            description=request.form['description'],
            category=request.form['category'],
            priority=request.form['priority'],
            location=request.form['location'],
            created_by=current_user.id,
            status='Pending'
        )
        db.session.add(new_comp)
        db.session.flush()
        
        # Notify ALL field engineers
        engineers = User.query.filter_by(role='FieldEngineer', is_approved=True).all()
        for engineer in engineers:
            notif = Notification(
                user_id=engineer.id,
                complaint_id=new_comp.id,
                title="New Complaint Available",
                message=f"New complaint: {new_comp.title} at {new_comp.location}. Category: {new_comp.category}"
            )
            db.session.add(notif)
        
        db.session.commit()
        
        if engineers:
            flash(f'Complaint registered! All {len(engineers)} engineers notified.')
        else:
            flash('Complaint registered! No engineers available.')
        
        # Simple redirect - just go back to helpdesk dashboard
        if current_user.role == 'Operator':
            return redirect(url_for('operator_dashboard'))
        else:
            return redirect(url_for('helpdesk_dashboard'))
    
    return render_template('register_complaint.html')

# ============================================
# FIELD ENGINEER - ACCEPT COMPLAINT
# ============================================

@app.route('/worker/accept/<int:comp_id>')
@login_required
def accept_complaint(comp_id):
    if current_user.role != 'FieldEngineer': 
        return redirect(url_for('dashboard'))
    
    complaint = Complaint.query.get(comp_id)
    if not complaint:
        flash('Complaint not found!', 'error')
        return redirect(url_for('worker_dashboard'))
    
    if complaint.status != 'Pending':
        flash('Complaint is not available!', 'error')
        return redirect(url_for('worker_dashboard'))
    
    # Set the accepted_at time
    complaint.assigned_to = current_user.id
    complaint.status = 'Active'
    complaint.accepted_at = datetime.now()
    complaint.assigned_at = datetime.now()
    
    db.session.commit()
    flash(f'You accepted complaint {complaint.complaint_id}!', 'success')
    
    return redirect(url_for('worker_dashboard'))

# ============================================
# FIELD ENGINEER - RESOLVE COMPLAINT
# ============================================

@app.route('/worker/resolve/<int:comp_id>', methods=['GET', 'POST'])
@login_required
def resolve_complaint(comp_id):
    if current_user.role != 'FieldEngineer': return redirect(url_for('dashboard'))
    comp = Complaint.query.get(comp_id)
    
    if request.method == 'POST':
        file = request.files.get('image')
        if file and file.filename:
            filename = f"{comp.complaint_id}_{file.filename}"
            file.save(os.path.join(app.config['UPLOAD_FOLDER'], filename))
            img = ComplaintImage(complaint_id=comp.id, filename=filename)
            db.session.add(img)
        
        comp.resolution_remarks = request.form['remarks']
        comp.worker_location = request.form['gps_loc']
        comp.status = 'Resolved'
        comp.resolved_at = datetime.now()
        
        # Notify HelpDesk and Operator for approval
        users = User.query.filter(User.role.in_(['HelpDesk', 'Operator'])).all()
        for user in users:
            notif = Notification(
                user_id=user.id,
                complaint_id=comp.id,
                title="Complaint Resolved - Awaiting Approval",
                message=f"{comp.complaint_id} resolved by {current_user.name}. Please approve closure."
            )
            db.session.add(notif)
        
        db.session.commit()
        flash('Complaint resolved! Waiting for approval.')
        return redirect(url_for('worker_dashboard'))
    
    return render_template('worker_resolve.html', complaint=comp)

# ============================================
# APPROVE CLOSURE (Operator & HelpDesk) - Continued
# ============================================

@app.route('/approve_close/<int:comp_id>', methods=['POST'])
@login_required
def approve_close(comp_id):
    if current_user.role not in ['Operator', 'HelpDesk']:
        return redirect(url_for('dashboard'))
    
    comp = Complaint.query.get(comp_id)
    
    # HelpDesk can only close Power Supply complaints
    if current_user.role == 'HelpDesk' and comp.category != 'Power Supply':
        flash('HelpDesk can only close Power Supply complaints!', 'error')
        return redirect(url_for('helpdesk_dashboard'))
    
    if comp and comp.status == 'Resolved':
        comp.status = 'Closed'
        comp.resolved_at = datetime.now()
        
        # Notify Field Engineer
        if comp.assigned_to:
            notif = Notification(
                user_id=comp.assigned_to,
                complaint_id=comp.id,
                title="Complaint Closed",
                message=f"Your complaint {comp.complaint_id} has been approved and closed."
            )
            db.session.add(notif)
        
        db.session.commit()
        flash(f'Complaint {comp.complaint_id} has been closed!')
    
    if current_user.role == 'Operator':
        return redirect(url_for('operator_dashboard'))
    return redirect(url_for('helpdesk_dashboard'))

# ============================================
# REJECT CLOSURE (Send back to Field Engineer)
# ============================================

@app.route('/reject_close/<int:comp_id>', methods=['POST'])
@login_required
def reject_close(comp_id):
    if current_user.role not in ['Operator', 'HelpDesk']:
        return redirect(url_for('dashboard'))
    
    comp = Complaint.query.get(comp_id)
    reason = request.form.get('reason', '')
    
    if comp and comp.status == 'Resolved':
        comp.status = 'Active'  # Send back to Field Engineer
        comp.resolved_at = None
        
        # Notify Field Engineer
        if comp.assigned_to:
            notif = Notification(
                user_id=comp.assigned_to,
                complaint_id=comp.id,
                title="Closure Rejected",
                message=f"Your complaint {comp.complaint_id} was rejected. Reason: {reason}"
            )
            db.session.add(notif)
        
        db.session.commit()
        flash(f'Complaint {comp.complaint_id} sent back to engineer!')
    
    if current_user.role == 'Operator':
        return redirect(url_for('operator_dashboard'))
    return redirect(url_for('helpdesk_dashboard'))

# ============================================
# HELPDESK - UPDATE COMPLAINT STATUS
# ============================================

@app.route('/helpdesk_update_complaint/<int:comp_id>', methods=['POST'])
@login_required
def helpdesk_update_complaint(comp_id):
    if current_user.role != 'HelpDesk':
        return redirect(url_for('dashboard'))
    
    complaint = Complaint.query.get_or_404(comp_id)
    new_status = request.form.get('status')
    
    # HelpDesk can change status to Closed for ANY complaint
    if new_status == 'Closed':
        complaint.status = new_status
        complaint.closed_at = datetime.now()
        complaint.resolved_by = current_user.id
        complaint.assigned_to = current_user.id
    elif new_status == 'Pending':
        complaint.status = new_status
    elif new_status == 'Active':
        complaint.status = new_status
    
    db.session.commit()
    flash(f'Complaint {complaint.complaint_id} updated to {new_status}!', 'success')
    
    return redirect(url_for('helpdesk_dashboard'))


# ============================================
# HELPDESK - CLOSE BUTTON (Simple)
# ============================================

@app.route('/helpdesk_close/<int:comp_id>', methods=['POST'])
@login_required
def helpdesk_close(comp_id):
    if current_user.role != 'HelpDesk':
        return redirect(url_for('dashboard'))
    
    complaint = Complaint.query.get_or_404(comp_id)
    
    # HelpDesk can ONLY close Power Supply complaints
    if complaint.category != 'Power Supply':
        flash(f'You can only close Power Supply complaints!', 'error')
        return redirect(url_for('helpdesk_dashboard'))
    
    # Update to Closed
    complaint.status = 'Closed'
    complaint.closed_at = datetime.now()
    complaint.resolved_by = current_user.id
    complaint.assigned_to = current_user.id
    
    db.session.commit()
    flash(f'Complaint {complaint.complaint_id} closed by {current_user.name}!', 'success')
    
    return redirect(url_for('helpdesk_dashboard'))

if __name__ == '__main__':
    # Initialize database
    with app.app_context():
        # ✅ Add missing column to existing database
        try:
            db.session.execute(db.text('ALTER TABLE user ADD COLUMN device_token VARCHAR(100)'))
            db.session.commit()
            print("Column added successfully!")
        except Exception as e:
            print(f"Column already exists or error: {e}")
        
        db.create_all()
        print("Database created!")

        if not User.query.filter_by(username='admin').first():
            admin = User(
                name='System Admin',
                username='admin',
                password='ICTadmin@123',
                role='Admin',
                is_approved=True
            )
            db.session.add(admin)
            db.session.commit()

    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
