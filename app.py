from flask import Flask, request, jsonify, render_template, redirect, url_for
from flask_sqlalchemy import SQLAlchemy
from flask_migrate import Migrate
from sklearn.cluster import AgglomerativeClustering
import numpy as np
import os
from flask import Flask, session
from flask_session import Session
from flask_mail import Mail, Message
from werkzeug.security import generate_password_hash, check_password_hash
from itsdangerous import URLSafeTimedSerializer
from collections import defaultdict, deque
from werkzeug.utils import secure_filename

app = Flask(__name__)

app.config['SESSION_TYPE'] = 'filesystem'
app.secret_key = 'Maddy'
Session(app)

# Configurations
base_dir = os.path.abspath(os.path.dirname(__file__))
app.config['SQLALCHEMY_DATABASE_URI'] = f'sqlite:///{os.path.join(base_dir, "instance", "friends.db")}'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['MAIL_SERVER'] = 'smtp.gmail.com'  
app.config['MAIL_PORT'] = 587
app.config['MAIL_USE_TLS'] = True
app.config['MAIL_USERNAME'] = 'yalamarthi.sriram123@gmail.com' 
app.config['MAIL_PASSWORD'] = 'uwrh qgkr efjc kguo' 
app.config['UPLOAD_FOLDER'] = 'static/uploads'

# Ensure the upload folder exists
os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)
mail = Mail(app)

db = SQLAlchemy(app)
migrate = Migrate(app, db)

# Models
class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    username = db.Column(db.String(100), unique=True, nullable=False)
    email = db.Column(db.String(100), unique=True, nullable=False)
    password = db.Column(db.String(100), nullable=False)
    profile_picture = db.Column(db.String(120), nullable=True)  # Ensure this exists

UPLOAD_FOLDER = 'static/profile_pictures'
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif'}

class Interests(db.Model):
    __tablename__ = 'interests'
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    sports = db.Column(db.Integer, nullable=False)
    movies = db.Column(db.Integer, nullable=False)
    dance = db.Column(db.Integer, nullable=False)
    songs = db.Column(db.Integer, nullable=False)
    education = db.Column(db.Integer, nullable=False)
    travel = db.Column(db.Integer, nullable=False)
    books = db.Column(db.Integer, nullable=False)
    cooking = db.Column(db.Integer, nullable=False)
    art = db.Column(db.Integer, nullable=False)

class Friends(db.Model):
    __tablename__ = 'friends'
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    friend_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)

# Token Serializer
def generate_reset_token(email, expiration=3600):
    serializer = URLSafeTimedSerializer(app.secret_key)
    return serializer.dumps(email, salt='password-reset-salt')

def validate_reset_token(token):
    serializer = URLSafeTimedSerializer(app.secret_key)
    try:
        email = serializer.loads(token, salt='password-reset-salt', max_age=3600)
        return email
    except Exception:
        return None

# Initialize Database
with app.app_context():
    if not os.path.exists(os.path.join(base_dir, "instance", "friends.db")):
        os.makedirs(os.path.join(base_dir, "instance"), exist_ok=True)
        db.create_all()

# Routes
@app.route("/")
def home():
    return render_template('home.html')

import os

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        name = request.form['name']
        username = request.form['username']
        email = request.form['email']
        password = request.form['password']
        profile_picture = request.files['profile_picture']
        
        # Directory path for saving profile picture
        upload_folder = 'uploads/profile_pictures'
        if not os.path.exists(upload_folder):
            os.makedirs(upload_folder)
        
        if profile_picture:
            filename = secure_filename(profile_picture.filename)
            filepath = os.path.join(upload_folder, filename)
            profile_picture.save(filepath)
        else:
            filepath = None  # Default or null if no image is uploaded
        
        new_user = User(name=name, username=username, email=email, password=password, profile_picture=filepath)
        db.session.add(new_user)
        db.session.commit()
        return redirect('/login')
    
    return render_template('register.html')




@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']

        if not username or not password:
            return "Username and password are required", 400

        user = User.query.filter_by(username=username).first()

        if user and user.password == password:
            session['user_id'] = user.id
            session['username'] = user.username

            # Check if interests are already filled
            if Interests.query.filter_by(user_id=user.id).first():
                return redirect(url_for('profile', name=user.name))
            else:
                return redirect(url_for('interests', name=user.name))

        return "Invalid credentials", 401

    return render_template('login.html')

@app.route('/upload-profile-picture', methods=['POST'])
def upload_profile_picture():
    if 'user_id' not in session:
        return redirect(url_for('login'))

    if 'profile_pic' not in request.files:
        return "No file selected", 400

    file = request.files['profile_pic']
    if file.filename == '':
        return "No selected file", 400

    user_id = session['user_id']
    user = User.query.get(user_id)

    if file:
        filename = secure_filename(file.filename)
        filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
        file.save(filepath)

        # Update the user's profile picture path
        user.profile_pic = filepath
        db.session.commit()
        return redirect(url_for('profile', name=user.name))
    
@app.route('/interests', methods=['GET', 'POST'])
def interests():
    if 'user_id' not in session:
        return redirect(url_for('login'))

    if request.method == 'POST':
        try:
            data = request.form
            required_fields = ['sports', 'movies', 'dance', 'songs', 'education', 'travel', 'books', 'cooking', 'art']
            for field in required_fields:
                if field not in data or not data[field]:
                    return f"Missing field: {field}", 400

            user_id = session['user_id']
            user = User.query.get(user_id)
            if not user:
                return "User not found", 404

            new_interest = Interests(
                user_id=user.id,
                sports=int(data.get('sports', 0)),
                movies=int(data.get('movies', 0)),
                dance=int(data.get('dance', 0)),
                songs=int(data.get('songs', 0)),
                education=int(data.get('education', 0)),
                travel=int(data.get('travel', 0)),
                books=int(data.get('books', 0)),
                cooking=int(data.get('cooking', 0)),
                art=int(data.get('art', 0))
            )
            db.session.add(new_interest)
            db.session.commit()

            return redirect(url_for('profile', name=user.name))
        except Exception as e:
            db.session.rollback()
            app.logger.error(f"Error saving interests: {e}")
            return f"An error occurred: {str(e)}", 500

    name = User.query.get(session['user_id']).name if 'user_id' in session else ''
    return render_template('interests.html', name=name)

@app.route('/profile/<name>', methods=['GET', 'POST'])
def profile(name):
    user = User.query.filter_by(name=name).first()
    
    if not user:
        return "User not found", 404
    
    # Handle profile picture upload
    if request.method == 'POST':
        if 'profile_picture' in request.files:
            file = request.files['profile_picture']
            if file and allowed_file(file.filename):
                filename = secure_filename(file.filename)
                filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
                file.save(filepath)
                
                # Update the user's profile picture path in the database
                user.profile_picture = filename
                db.session.commit()  # Commit changes to the database

                # After saving, redirect to the profile page
                return redirect(url_for('profile', name=user.name))
    
    # Retrieve the user's profile picture path or use a default image if not available
    profile_picture_url = url_for('static', filename='profile_pictures/' + user.profile_picture) if user.profile_picture else url_for('static', filename='default_profile_picture.jpg')
    
    # Pass the user object to the template
    return render_template('profile.html', user=user, profile_picture_url=profile_picture_url)

@app.route('/add-friend/<friend_id>', methods=['POST'])
def add_friend(friend_id):
    if 'user_id' not in session:
        return redirect(url_for('login'))

    user_id = session['user_id']
    friendship = Friends(user_id=user_id, friend_id=friend_id)
    db.session.add(friendship)
    db.session.commit()
    return "Friend added successfully", 200

@app.route('/mutual-friends/<name>')
def mutual_friends(name):
    user = User.query.filter_by(name=name).first()
    if not user:
        return "User not found", 404

    user_friends = {f.friend_id for f in Friends.query.filter_by(user_id=user.id).all()}
    mutuals = defaultdict(list)

    for friend_id in user_friends:
        friend_friends = {f.friend_id for f in Friends.query.filter_by(user_id=friend_id).all()}
        mutuals[friend_id] = user_friends.intersection(friend_friends)

    return jsonify({str(f): [User.query.get(mid).name for mid in mids] for f, mids in mutuals.items()}), 200

@app.route('/logout', methods=['POST'])
def logout():
    # Clear the user session
    session.clear()
    # Redirect to the home page
    return redirect(url_for('home'))

@app.route('/forgot-password', methods=['GET', 'POST'])
def forgot_password():
    if request.method == 'POST':
        username = request.form['username']
        user = User.query.filter_by(username=username).first()

        if user:
            token = generate_reset_token(user.email)
            reset_link = url_for('reset_password', token=token, _external=True)

            # Send the email
            msg = Message("Password Reset Request",
                          sender=app.config['MAIL_USERNAME'],
                          recipients=[user.email])
            msg.body = f"Hi {user.name},\n\nPlease use the following link to reset your password:\n{reset_link}\n\nIf you did not request this, please ignore the email."
            mail.send(msg)
            return "An email has been sent to your registered email address.", 200
        else:
            return "Username not found!", 404

    return render_template('forgot-password.html')

@app.route('/reset-password/<token>', methods=['GET', 'POST'])
def reset_password(token):
    email = validate_reset_token(token)
    if not email:
        return "Invalid or expired reset link", 404

    user = User.query.filter_by(email=email).first()
    if not user:
        return "User not found", 404

    if request.method == 'POST':
        new_password = request.form.get('password')
        if not new_password:
            return "Password is required", 400

        user.password = new_password
        db.session.commit()

        return redirect(url_for('login'))

    return render_template('reset-password.html', token=token)

def recommend_friends(name):
    user = User.query.filter_by(name=name).first()
    if not user:
        return []

    user_interest = Interests.query.filter_by(user_id=user.id).first()
    if not user_interest:
        return []

    all_interests = Interests.query.all()

    data = np.array([
        [i.sports, i.movies, i.dance, i.songs, i.education, i.travel, i.books, i.cooking, i.art]
        for i in all_interests
    ])
    names = [User.query.get(i.user_id).name for i in all_interests]

    # If there's only one user, return an empty recommendation list
    if len(data) < 2:
        return []

    clustering = AgglomerativeClustering(n_clusters=min(len(data), 3), metric='euclidean', linkage='ward')
    clusters = clustering.fit_predict(data)

    user_cluster = clusters[names.index(name)]
    return [names[i] for i, cluster in enumerate(clusters) if cluster == user_cluster and names[i] != name]
# Check if the file extension is allowed
def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

if __name__ == '__main__':
    app.run(debug=True)
