from datetime import timedelta
from flask import Flask, request, jsonify, render_template, redirect, url_for, flash
from flask_sqlalchemy import SQLAlchemy
from flask_migrate import Migrate
from sklearn.cluster import KMeans
import numpy as np
import os
from flask import Flask, session
from flask_session import Session
from flask_mail import Mail, Message
from werkzeug.security import generate_password_hash, check_password_hash
from itsdangerous import URLSafeTimedSerializer
from collections import defaultdict, deque
from werkzeug.utils import secure_filename
from sklearn.metrics.pairwise import cosine_similarity
from flask_socketio import SocketIO, emit, join_room, leave_room
import sqlalchemy


app = Flask(__name__)

app.config['SESSION_TYPE'] = 'filesystem'
app.secret_key = 'Maddy'
Session(app)
socketio = SocketIO(app)
app.permanent_session_lifetime = timedelta(days=7) 

app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///friends.db'  # Replace with your database URI
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

# Configurations
base_dir = os.path.abspath(os.path.dirname(__file__))
app.config['SQLALCHEMY_DATABASE_URI'] = f'sqlite:///{os.path.join(base_dir, "instance", "friends.db")}'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['MAIL_SERVER'] = 'smtp.gmail.com'  
app.config['MAIL_PORT'] = 587
app.config['MAIL_USE_TLS'] = True
app.config['MAIL_USERNAME'] = 'yalamarthi.sriram123@gmail.com' 
app.config['MAIL_PASSWORD'] = 'uwrh qgkr efjc kguo' 
app.config['UPLOAD_FOLDER'] = 'E:\\Fundamentals of AI\\Friend Recommendation system\\static\\profile_pictures\\uploads'

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

UPLOAD_FOLDER = 'static\\profile_pictures\\uploads'
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

class FriendRequest(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    sender_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    receiver_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    status = db.Column(db.String(10), default='pending')  # 'pending', 'accepted', 'rejected'


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


@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        # Get form data
        name = request.form['name']
        username = request.form['username']
        email = request.form['email']
        password = request.form['password']
        profile_picture = request.files['profile_picture']
        
        # Validate input (e.g., check for empty fields)
        if not name or not username or not email or not password:
            flash('All fields are required.')
            return render_template('register.html')
        
        # Directory path for saving profile picture
        upload_folder = 'static/profile_pictures/uploads'
        if not os.path.exists(upload_folder):
            os.makedirs(upload_folder)
        
        # Handle profile picture upload
        if profile_picture:
            filename = secure_filename(profile_picture.filename)
            filepath = os.path.join(upload_folder, filename)
            profile_picture.save(filepath)
        else:
            filepath = None  # Default or null if no image is uploaded
        
        # Check if the email already exists
        existing_user = User.query.filter_by(email=email).first()
        if existing_user:
            flash('This email is already registered. Please use a different email or log in.')
            return render_template('register.html')
        
        # Add the new user to the database
        new_user = User(name=name, username=username, email=email, password=password, profile_picture=filepath)
        try:
            db.session.add(new_user)
            db.session.commit()
            flash('Registration successful! Please log in.')
            return redirect('/login')
        except sqlalchemy.exc.IntegrityError:
            db.session.rollback()
            flash('An error occurred while registering. Please try again.')
            return render_template('register.html')
    
    # Render the registration form for GET requests
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

    # Retrieve Profile Picture URL
    profile_picture_url = url_for('static', filename=user.profile_picture) if user.profile_picture else url_for(
        'static', filename='profile_pictures/default_profile_picture.jpg')

    # Followers and Following Queries
    followers = [
        follower_user.name
        for f in Friends.query.filter_by(friend_id=user.id).all()
        if (follower_user := User.query.get(f.user_id))
    ]
    following = [
        following_user.name
        for f in Friends.query.filter_by(user_id=user.id).all()
        if (following_user := User.query.get(f.friend_id))
    ]

    # Fetch Recommended Friends
    recommendations = recommend_friends(name)

    # Check if the user already added each recommended friend
    already_added = {f.friend_id for f in Friends.query.filter_by(user_id=user.id).all()}
    recommendations_status = [
        {
            "name": friend,
            "friend_id": User.query.filter_by(name=friend).first().id,
            "added": User.query.filter_by(name=friend).first().id in already_added
        }
        for friend in recommendations
    ]

    return render_template('profile.html',
                           user=user,
                           profile_picture_url=profile_picture_url,
                           followers=followers,
                           following=following,
                           follower_count=len(followers),
                           following_count=len(following),
                           recommendations=recommendations_status)


@app.route('/chat/<friend_id>', methods=['GET'])
def chat(friend_id):
    if 'user_id' not in session:
        return redirect(url_for('login'))

    friend = User.query.get(friend_id)
    if not friend:
        return "User not found", 404

    room_id = "_".join(sorted([str(session['user_id']), str(friend_id)]))
    return render_template('chat.html', friend=friend, room_id=room_id, messages=messages.get(room_id, []))

@app.route('/add-friend/<friend_username>', methods=['POST'])
def add_friend(friend_username):
    # Retrieve the username of the logged-in user from the session
    username = session.get('username')  # Use session.get to avoid KeyError
    if not username:
        return "User not logged in", 403  # Handle case where session is not set

    # Query the logged-in user by username
    user = User.query.filter_by(username=username).first()
    if not user:
        return "Logged-in user not found", 404

    # Query the friend to be added
    friend = User.query.filter_by(name=friend_username).first()
    if not friend:
        return "Friend not found", 404

    # Check if the friend relationship already exists
    existing_friendship = Friends.query.filter_by(user_id=user.id, friend_id=friend.id).first()
    if existing_friendship:
        return "You are already friends with this user", 400

    # Add the new friend relationship
    new_friend = Friends(user_id=user.id, friend_id=friend.id)
    db.session.add(new_friend)
    db.session.commit()

    return "Friend added successfully"


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

@app.route('/send_request/<receiver_id>', methods=['POST'])
def send_request(receiver_id):
    if 'user_id' not in session:
        return redirect(url_for('login'))

    existing_request = FriendRequest.query.filter_by(
        sender_id=session['user_id'], receiver_id=receiver_id
    ).first()

    if not existing_request:
        new_request = FriendRequest(sender_id=session['user_id'], receiver_id=receiver_id)
        db.session.add(new_request)
        db.session.commit()
    return redirect(url_for('profile', name=User.query.get(receiver_id).name))

@app.route('/accept_request/<request_id>', methods=['POST'])
def accept_request(request_id):
    friend_request = FriendRequest.query.get(request_id)
    if friend_request and friend_request.receiver_id == session['user_id']:
        friend_request.status = 'accepted'
        
        # Add to friends table
        db.session.add(Friends(user_id=friend_request.sender_id, friend_id=friend_request.receiver_id))
        db.session.add(Friends(user_id=friend_request.receiver_id, friend_id=friend_request.sender_id))
        db.session.commit()
    return redirect(url_for('profile', name=User.query.get(session['user_id']).name))


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

@app.route('/explore', methods=['GET'])
def explore_recommendations():
    if 'user_id' not in session:
        return redirect(url_for('login'))
    user = User.query.get(session['user_id'])
    return render_template('explore.html', user=user)

# Chat Messages
messages = defaultdict(list)  # Stores messages {room_id: [(sender, message)]
@socketio.on('send_message')
def handle_send_message(data):
    room_id = data['room_id']
    message = data['message']
    sender = session['user_id']

    # Store Message
    messages[room_id].append((sender, message))
    emit('receive_message', {'sender': sender, 'message': message}, room=room_id)

@socketio.on('join')
def handle_join(data):
    room_id = data['room_id']
    join_room(room_id)

@socketio.on('leave')
def handle_leave(data):
    room_id = data['room_id']
    leave_room(room_id)

    
@app.route('/filtered_recommendations', methods=['GET'])
def filtered_recommendations():
    if 'user_id' not in session:
        return redirect(url_for('login'))

    user = User.query.get(session['user_id'])
    if not user:
        return "User not found", 404

    category = request.args.get('category', 'sports')  # Default to 'sports'
    recommendations = recommend_friends(user.name, category)

    return render_template(
        'explore.html',
        recommendations=recommendations,
        category=category
    )
@app.route('/follow/<friend_id>', methods=['POST'])
def follow(friend_id):
    if 'user_id' not in session:
        return redirect(url_for('login'))

    user_id = session['user_id']
    if Friends.query.filter_by(user_id=user_id, friend_id=friend_id).first():
        return "Already following", 400

    new_follow = Friends(user_id=user_id, friend_id=friend_id)
    db.session.add(new_follow)
    db.session.commit()
    return redirect(url_for('profile', name=User.query.get(user_id).name))

def recommend_friends(name, category=None):
    # Retrieve the user based on their name
    user = User.query.filter_by(name=name).first()
    if not user:
        print("User not found")
        return []

    # Fetch the interests of the user
    user_interest = Interests.query.filter_by(user_id=user.id).first()
    if not user_interest:
        print("No interests found for user")
        return []

    # Retrieve interests of all users
    all_interests = Interests.query.all()

    # Create a data array of interests for similarity and clustering
    data = np.array([
        [i.sports, i.movies, i.dance, i.songs, i.education, i.travel, i.books, i.cooking, i.art]
        for i in all_interests
    ])
    names = [User.query.get(i.user_id).name for i in all_interests]

    # Debugging
    print("Interest Data:", data)
    print("User Names:", names)

    # Ensure the target user exists in names
    if name not in names:
        print(f"{name} not found in the user names")
        return []

    # Index of the target user
    user_index = names.index(name)

    # If the dataset is small, use cosine similarity
    if len(data) <= 30:
        print("Using Cosine Similarity")
        # Calculate cosine similarity
        similarity_scores = cosine_similarity([data[user_index]], data)[0]

        # Recommend users with the highest similarity, excluding the target user
        recommended_indices = np.argsort(similarity_scores)[::-1][1:20]
        recommended_friends = [
            names[i] for i in recommended_indices if names[i] != name
        ]
    else:
        # Use KMeans clustering for larger datasets
        print("Using KMeans Clustering")
        n_clusters = min(len(data), 3)  # Adjust the number of clusters based on available data
        kmeans = KMeans(n_clusters=n_clusters, random_state=42, n_init=10)
        clusters = kmeans.fit_predict(data)

        # Identify the cluster of the target user
        user_cluster = clusters[user_index]

        # Find all users in the same cluster, excluding the target user
        recommended_friends = [
            names[i] for i, cluster in enumerate(clusters)
            if cluster == user_cluster and names[i] != name
        ]

    # Apply the category filter if selected
    if category:
        category_index = {
            "sports": 0, "movies": 1, "dance": 2, "songs": 3, 
            "education": 4, "travel": 5, "books": 6, "cooking": 7, "art": 8
        }.get(category)

        recommended_friends = [
            friend for friend in recommended_friends
            if data[names.index(friend)][category_index] == 1
        ]

    print("Recommended Friends:", recommended_friends)
    return recommended_friends

# Check if the file extension is allowed
def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

if __name__ == "__main__":
    socketio.run(app, host="0.0.0.0", port=3000)


