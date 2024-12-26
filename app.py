from datetime import timedelta
from flask import Flask, request, jsonify, render_template, redirect, url_for, flash,session
from flask_sqlalchemy import SQLAlchemy
from flask_migrate import Migrate
from sklearn.cluster import KMeans
import numpy as np
import os
from flask_session import Session
from flask_mail import Mail, Message
from itsdangerous import URLSafeTimedSerializer
from collections import defaultdict
from werkzeug.utils import secure_filename
from sklearn.metrics.pairwise import cosine_similarity
from flask_socketio import SocketIO, emit, join_room, leave_room
import sqlalchemy
from sqlalchemy.orm import Session
from sklearn.neighbors import NearestNeighbors


app = Flask(__name__, static_folder='static')


app.config['SESSION_TYPE'] = 'filesystem'
app.secret_key = 'Maddy'
Session(app)
socketio = SocketIO(app)
app.permanent_session_lifetime = timedelta(days=7) 


# Configurations
base_dir = os.path.abspath(os.path.dirname(__file__))
app.config['SESSION_PERMANENT'] = False
app.config['SESSION_USE_SIGNER'] = True
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
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif'}

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
    profile_picture = db.Column(db.String(120), nullable=True)


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
    status = db.Column(db.String(10), default='pending')


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

@app.errorhandler(500)
def internal_error(error):
    return "Internal Server Error", 500

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        name = request.form['name']
        username = request.form['username']
        email = request.form['email']
        password = request.form['password']
        profile_picture = request.files['profile_picture']

        if not name or not username or not email or not password:
            flash('All fields are required.')
            return render_template('register.html')
        upload_folder = app.config['UPLOAD_FOLDER']
        if profile_picture:
            filename = secure_filename(profile_picture.filename)
            filepath = os.path.join(upload_folder, filename)
            profile_picture.save(filepath)
        else:
            filepath = None  # Default image
        # Checking email
        existing_user = User.query.filter_by(email=email).first()
        if existing_user:
            flash('This email is already registered. Please use a different email or log in.')
            return render_template('register.html')
        # new user
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
    #registration form for GET requests
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
#for the first time login users
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
        user.profile_picture = filepath
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
    
    profile_picture_url = (
        url_for('static', filename=f"profile_pictures/uploads/{user.profile_picture}")
        if user.profile_picture
        else url_for('static', filename='profile_pictures/default_profile_picture.jpg')
    )
    followers = [
        {"id": follower_user.id, "name": follower_user.name}
        for f in Friends.query.filter_by(friend_id=user.id).all()
        if (follower_user := User.query.get(f.user_id))
    ]
    following = [
        {"id": following_user.id, "name": following_user.name}
        for f in Friends.query.filter_by(user_id=user.id).all()
        if (following_user := User.query.get(f.friend_id))
    ]
    recommendations = recommend_friends(name)
    already_added = {f.friend_id for f in Friends.query.filter_by(user_id=user.id).all()}
    recommendations_status = []
    for friend_name in recommendations:
        friend = User.query.filter_by(name=friend_name).first()
        if friend:
            recommendations_status.append({
                "name": friend.name,
                "id": friend.id,
                "added": friend.id in already_added
            })
    mutual_interest_recommendations = suggest_friends(user.id, method="mutual_interest")
    return render_template(
        'profile.html',
        user=user,
        profile_picture_url=profile_picture_url,
        followers=followers,
        following=following,
        follower_count=len(followers),
        following_count=len(following),
        recommendations=recommendations_status,
        mutual_friends=mutual_interest_recommendations
    )
@app.route('/chat/<int:friend_id>', methods=['GET'])
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
    username = session.get('username')
    if not username:
        return "User not logged in", 403
    user = User.query.filter_by(username=username).first()
    if not user:
        return "Logged-in user not found", 404
    friend = User.query.filter_by(name=friend_username).first()
    if not friend:
        return "Friend not found", 404
    existing_friendship = Friends.query.filter_by(user_id=user.id, friend_id=friend.id).first()
    if existing_friendship:
        return "You are already friends with this user", 400
    new_friend = Friends(user_id=user.id, friend_id=friend.id)
    db.session.add(new_friend)
    db.session.commit()
    return "Friend added successfully"

@app.route('/mutual-friends/<string:name>', methods=['GET'])
def mutual_friends(name):
    user = User.query.filter_by(name=name).first()
    if not user:
        return jsonify({"error": "User not found"}), 404
    user_friends = {f.friend_id for f in Friends.query.filter_by(user_id=user.id).all()}
    mutuals = {
        User.query.get(friend_id).name: [
            User.query.get(mid).name for mid in user_friends.intersection(
                {f.friend_id for f in Friends.query.filter_by(user_id=friend_id).all()}
            )
        ]
        for friend_id in user_friends
    }
    return jsonify({"user": user.name, "mutual_friends": mutuals}), 200

@app.route('/send-request/<int:receiver_id>', methods=['POST'])
def send_request(receiver_id):
    if 'user_id' not in session:
        return redirect(url_for('login'))
    if not FriendRequest.query.filter_by(sender_id=session['user_id'], receiver_id=receiver_id).first():
        db.session.add(FriendRequest(sender_id=session['user_id'], receiver_id=receiver_id))
        db.session.commit()
    return redirect(url_for('profile', name=User.query.get(receiver_id).name))

@app.route('/accept-request/<int:request_id>', methods=['POST'])
def accept_request(request_id):
    friend_request = FriendRequest.query.get(request_id)
    if friend_request and friend_request.receiver_id == session['user_id']:
        db.session.add(Friends(user_id=friend_request.sender_id, friend_id=friend_request.receiver_id))
        db.session.add(Friends(user_id=friend_request.receiver_id, friend_id=friend_request.sender_id))
        db.session.delete(friend_request)
        db.session.commit()
    return redirect(url_for('profile', name=User.query.get(session['user_id']).name))

@app.route('/logout', methods=['POST'])
def logout():
    session.clear()
    return redirect(url_for('home'))

@app.route('/forgot-password', methods=['GET', 'POST'])
def forgot_password():
    if request.method == 'POST':
        username = request.form['username']
        user = User.query.filter_by(username=username).first()
        if user:
            token = generate_reset_token(user.email)
            reset_link = url_for('reset_password', token=token, _external=True)

            msg = Message(
                "Password Reset Request",
                sender=app.config['MAIL_USERNAME'],
                recipients=[user.email]
            )
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
messages = defaultdict(list)  # Stores messages 
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
    
@app.route('/filtered-recommendations', methods=['GET'])
def filtered_recommendations():
    if 'user_id' not in session:
        return redirect(url_for('login'))
    user_id = session['user_id']
    user = User.query.get(user_id)
    if not user:
        return "User not found", 404

    valid_categories = [
        'sports', 'dance', 'education', 'songs', 'movies', 
        'books', 'travel', 'art', 'photography', 'fitness', 
        'technology', 'gaming', 'health', 'food', 'fashion', 
        'music', 'history', 'science', 'theatre', 'nature'
    ]
    category = request.args.get('category', 'sports').lower()

    if category not in valid_categories:
        return "Invalid category selected", 400

    recommendations = suggest_friends(user_id, method="dijkstra", category=category)

    if request.accept_mimetypes.best == 'application/json':
        return jsonify({"recommendations": recommendations})
    return render_template(
        'explore.html',
        user=user,
        category=category,
        recommendations=recommendations
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

@app.route('/explore_mutuals', methods=['GET'])
def explore_mutuals():
    if 'user_id' not in session:
        return redirect(url_for('login'))
    user_id = session['user_id']
    user = User.query.get(user_id)
#greedy
    mutuals_greedy = suggest_friends(user_id, method="greedy")
#filtered mutuals using the Dijkstra method
    category = request.args.get('category', 'sports').lower()
    mutuals_dijkstra = suggest_friends(user_id, method="dijkstra", category=category)
    return render_template(
        'explore_mutuals.html',
        user=user,
        mutuals_greedy=mutuals_greedy,
        mutuals_dijkstra=mutuals_dijkstra,
        category=category
    )
def recommend_friends(name, category=None):
    """
    Recommend friends based on user interests and an optional category filter.

    Args:
        name (str): The name of the user.
        category (str, optional): Specific interest category to filter recommendations.

    Returns:
        list: Recommended friends' names.
    """
    user = User.query.filter_by(name=name).first()
    if not user:
        print("User not found")
        return []
    
    user_interest = Interests.query.filter_by(user_id=user.id).first()
    if not user_interest:
        print("No interests found for user")
        return []

    all_interests = Interests.query.all()

    data = np.array([
        [i.sports, i.movies, i.dance, i.songs, i.education, i.travel, i.books, i.cooking, i.art]
        for i in all_interests
    ])
    names = [User.query.get(i.user_id).name for i in all_interests]
#Debugging
    print("Interest Data:", data)
    print("User Names:", names)

#checking
    if name not in names:
        print(f"{name} not found in the user names")
        return []
#index fetching for user
    user_index = names.index(name)

# Use cosine similarity(<30)
    if len(data) <= 30:
        print("Using Cosine Similarity")
        similarity_scores = cosine_similarity([data[user_index]], data)[0]
        recommended_indices = np.argsort(similarity_scores)[::-1][1:20]
        recommended_friends = [names[i] for i in recommended_indices if names[i] != name]
    else:
# Use KMeans clustering(>30)
        print("Using KMeans Clustering")
        n_clusters = min(len(data), 3)
        kmeans = KMeans(n_clusters=n_clusters, random_state=42, n_init=10)
        clusters = kmeans.fit_predict(data)
#cluster identification
        user_cluster = clusters[user_index]
        recommended_friends = [
            names[i] for i, cluster in enumerate(clusters)
            if cluster == user_cluster and names[i] != name
        ]

#category filter if selected
    if category:
        category_index = {
            "sports": 0, "movies": 1, "dance": 2, "songs": 3,
            "education": 4, "travel": 5, "books": 6, "cooking": 7, "art": 8
        }.get(category)
        if category_index is None:
            print(f"Invalid category: {category}")
            return []
#Filter users
        category_users = np.where(data[:, category_index] == 1)[0]
        if len(category_users) == 0:
            print(f"No users found with interest in {category}")
            return []
        
#Using Nearest Neighbors to find similar users within the category
        nn = NearestNeighbors(n_neighbors=min(len(category_users), 10), metric="cosine")
        nn.fit(data[category_users])
        distances, indices = nn.kneighbors([data[user_index]])

#Get the indices of recommended friends
        recommended_indices = [category_users[i] for i in indices[0] if category_users[i] != user_index]
        recommended_friends = [names[i] for i in recommended_indices]
    print("Recommended Friends:", recommended_friends)
    return recommended_friends

def suggest_friends(user_id, method="greedy", category=None):
    """
    Suggest friends for a user based on the selected method.

    Args:
        user_id (int): The ID of the user for whom suggestions are being made.
        method (str): The recommendation method, "greedy", "dijkstra", or "mutual_interest".
        category (str, optional): The category for similarity (used only in "dijkstra" and "mutual_interest").

    Returns:
        list[dict]: A list of suggested friends with their IDs, names, and scores.
    """
    valid_categories = ["sports", "movies", "dance", "songs", "education", "travel", "books", "cooking", "art"]

    if method not in ["greedy", "dijkstra", "mutual_interest"]:
        raise ValueError("Invalid method. Choose 'greedy', 'dijkstra', or 'mutual_interest'.")
    
    if method == "dijkstra" and (not category or category not in valid_categories):
        raise ValueError(f"Invalid or missing category. Valid categories are: {', '.join(valid_categories)}")
#Method 1:Greedy Recommendation
    if method == "greedy":
        user_friends = {f.friend_id for f in Friends.query.filter_by(user_id=user_id).all()}
        mutual_counts = defaultdict(int)

        for friend_id in user_friends:
            friend_friends = {f.friend_id for f in Friends.query.filter_by(user_id=friend_id).all()}
            for mutual in friend_friends - user_friends - {user_id}:
                mutual_counts[mutual] += 1

        sorted_mutuals = sorted(mutual_counts.items(), key=lambda x: -x[1])
        return [
            {"id": mutual_id, "name": User.query.get(mutual_id).name, "score": count}
            for mutual_id, count in sorted_mutuals if User.query.get(mutual_id)
        ]
#Method2:=Dijkstra's Algorithm for Similarity
    elif method == "dijkstra":
        user_interests = Interests.query.filter_by(user_id=user_id).first()
        if not user_interests:
            return []
        users = Interests.query.all()
        graph = defaultdict(list)
        for u in users:
            if u.user_id != user_id:
                similarity = abs(getattr(user_interests, category) - getattr(u, category))
                graph[user_id].append((u.user_id, similarity))
        import heapq
        pq = [(0, user_id)]
        distances = {user_id: 0}
        previous = {}
        while pq:
            current_distance, current_user = heapq.heappop(pq)
            for neighbor, weight in graph[current_user]:
                distance = current_distance + weight
                if neighbor not in distances or distance < distances[neighbor]:
                    distances[neighbor] = distance
                    previous[neighbor] = current_user
                    heapq.heappush(pq, (distance, neighbor))
        return [
            {"id": uid, "name": User.query.get(uid).name, "score": distances[uid]}
            for uid in distances if uid != user_id
        ]
#Method 3:Mutual Interest(collabarative filtering)
    elif  "mutual_interest":
        user_interests = Interests.query.filter_by(user_id=user_id).first()
        if not user_interests:
            return []
# IDs of the user's current friends
        user_friends = {f.friend_id for f in Friends.query.filter_by(user_id=user_id).all()}
# Calculate similarity scores
        friend_scores = defaultdict(float)
        for friend_id in user_friends:
            mutual_friends = {f.friend_id for f in Friends.query.filter_by(user_id=friend_id).all()}
            for mutual_friend_id in mutual_friends:
                if mutual_friend_id != user_id and mutual_friend_id not in user_friends:
                    mutual_friend_interests = Interests.query.filter_by(user_id=mutual_friend_id).first()
                    if mutual_friend_interests:
                        if category:
                            if category not in valid_categories:
                                raise ValueError(f"Invalid category. Valid categories are: {', '.join(valid_categories)}")
                            similarity = abs(getattr(user_interests, category) - getattr(mutual_friend_interests, category))
                            friend_scores[mutual_friend_id] += 1 / (1 + similarity)
                        else:  # Use all categories
                            total_similarity = sum(
                                abs(getattr(user_interests, cat) - getattr(mutual_friend_interests, cat))
                                for cat in valid_categories
                            )
                            friend_scores[mutual_friend_id] += 1 / (1 + total_similarity)
#Sort friends by score in descending order
        sorted_scores = sorted(friend_scores.items(), key=lambda x: -x[1])
        suggestions = [
            {"id": friend_id, "name": User.query.get(friend_id).name, "score": score}
            for friend_id, score in sorted_scores if User.query.get(friend_id)
        ]
        return suggestions
    raise ValueError("Invalid method.")

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

if __name__ == "__main__":
    port = int(os.environ.get('PORT', 3000))
    app.run(host="0.0.0.0", port=port)
