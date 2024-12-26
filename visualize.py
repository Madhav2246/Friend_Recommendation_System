import os
import sqlite3
import numpy as np
import matplotlib.pyplot as plt
import seaborn as sns
from sklearn.metrics.pairwise import cosine_similarity
from sklearn.cluster import KMeans

def retrieve_data_from_db(db_path):
    """
    Retrieve user interests data and user names from the database.

    Args:
        db_path (str): Path to the SQLite database.

    Returns:
        tuple: (data, names) where data is a numpy array of interests, and names is a list of user names.
    """
    # Ensure the database path exists
    if not os.path.exists(db_path):
        print(f"Database not found at {db_path}")
        return None, None

    # Connect to the SQLite database
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    # Query to retrieve interests and user names
    query = """
        SELECT u.name, i.sports, i.movies, i.dance, i.songs, i.education, 
               i.travel, i.books, i.cooking, i.art
        FROM Interests i
        JOIN Users u ON i.user_id = u.id
    """
    cursor.execute(query)
    rows = cursor.fetchall()
    conn.close()

    # Extract names and interest data
    if rows:
        names = [row[0] for row in rows]
        data = np.array([row[1:] for row in rows])
        return data, names
    else:
        print("No data found in the database.")
        return None, None

def visualize_recommendation(name, db_path, recommended_friends=[], category=None):
    """
    Visualize the recommendation algorithm with data from a SQLite database.

    Args:
        name (str): Name of the target user.
        db_path (str): Path to the SQLite database.
        recommended_friends (list): List of recommended friends.
        category (str, optional): Specific category filter applied.
    """
    # Retrieve data from the database
    data, names = retrieve_data_from_db(db_path)
    
    if data is None or names is None:
        return
    
    sns.set(style="whitegrid")
    
    # Ensure the user exists in the names
    if name not in names:
        print(f"User '{name}' not found in the dataset.")
        return
    
    user_index = names.index(name)
    user_data = data[user_index]
    
    # Plot 1: Interest Distribution of the User
    categories = ["sports", "movies", "dance", "songs", "education", 
                  "travel", "books", "cooking", "art"]
    plt.figure(figsize=(12, 6))
    plt.bar(categories, user_data, color="blue", alpha=0.7, label=f"{name}'s Interests")
    plt.xticks(rotation=45)
    plt.title(f"Interest Distribution for {name}")
    plt.ylabel("Interest Level")
    plt.legend()
    plt.show()
    
    # Plot 2: Cosine Similarity Scores (if data size <= 30)
    if len(data) <= 30:
        similarity_scores = cosine_similarity([data[user_index]], data)[0]
        sorted_indices = np.argsort(similarity_scores)[::-1]
        sorted_names = [names[i] for i in sorted_indices if names[i] != name]
        sorted_scores = [similarity_scores[i] for i in sorted_indices if names[i] != name]
        
        plt.figure(figsize=(12, 6))
        sns.barplot(x=sorted_names[:10], y=sorted_scores[:10], palette="viridis")
        plt.xticks(rotation=45)
        plt.title(f"Top 10 Similar Users to {name}")
        plt.ylabel("Cosine Similarity Score")
        plt.xlabel("Users")
        plt.show()
    else:
        # Plot 3: KMeans Clustering (if data size > 30)
        n_clusters = min(len(data), 3)
        kmeans = KMeans(n_clusters=n_clusters, random_state=42, n_init=10)
        clusters = kmeans.fit_predict(data)
        
        plt.figure(figsize=(10, 8))
        scatter = plt.scatter(data[:, 0], data[:, 1], c=clusters, cmap='viridis', alpha=0.7)
        plt.scatter(data[user_index, 0], data[user_index, 1], color="red", s=100, label=f"{name} (Target User)")
        plt.title("KMeans Clustering of Users")
        plt.xlabel("Feature 1 (e.g., sports)")
        plt.ylabel("Feature 2 (e.g., movies)")
        plt.legend()
        plt.colorbar(scatter, label="Cluster")
        plt.show()
    
    # Plot 4: Category-Specific Recommendations (if a category is provided)
    if category:
        category_index = {
            "sports": 0, "movies": 1, "dance": 2, "songs": 3, 
            "education": 4, "travel": 5, "books": 6, "cooking": 7, "art": 8
        }.get(category)
        
        if category_index is not None:
            category_data = data[:, category_index]
            plt.figure(figsize=(12, 6))
            sns.barplot(x=names, y=category_data, palette="coolwarm")
            plt.xticks(rotation=45)
            plt.title(f"Interest Levels in '{category}' for All Users")
            plt.ylabel("Interest Level")
            plt.xlabel("Users")
            plt.axvline(x=names.index(name), color="red", linestyle="--", label=f"{name}")
            plt.legend()
            plt.show()

# Example Usage
db_path = "instance/friends.db"
name = "Maddy"
recommended_friends = ["Jane", "Doe", "Alice"]  # Replace with actual recommendations
visualize_recommendation(name, db_path, recommended_friends, category="sports")
