import tensorflow as tf
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.model_selection import train_test_split
import numpy as np
from pymongo import MongoClient
from collections import defaultdict
from keras.layers import Dropout, BatchNormalization

# Spajanje na bazu
client = MongoClient("mongodb://127.0.0.1:27017/")
database = client["movies"]
collection = database["movies"]

def load_movie_data():
    movies = list(collection.find({}, {"_id": 1, "name": 1, "year": 1, "score": 1, "votes": 1, "genre": 1, "poster_url": 1, "keywords": 1, "director": 1, "star": 1}))
    for movie in movies:
        movie['_id'] = str(movie['_id'])  # pretvaranje ObjectId u string
    return movies

def prepare_data(movies): # priprema za normalizaiju s tensorflowom + kombinacija svih tekstualnih podataka
    all_text = [
        " ".join([movie.get("genre", ""), ", ".join(movie.get("keywords", [])), ", ".join(movie.get("director", [])), ", ".join(movie.get("star", []))])
        for movie in movies
    ]

    # Tfidf vektorizacija
    vectorizer = TfidfVectorizer(stop_words="english")
    X_text = vectorizer.fit_transform(all_text).toarray()

    scores = [movie['score'] for movie in movies]
    votes = [movie['votes'] for movie in movies]

    # kombiniraj sve ulazne podatke
    X_numerical = np.array(list(zip(scores, votes)))
    X = np.hstack((X_text, X_numerical))  # spajanje numeričkih i tekstualnih podatka

    # normalizacija s TensorFlowom
    normalizer = tf.keras.layers.Normalization(axis=-1)
    normalizer.adapt(X)
    normalized_data = normalizer(X)

    return normalized_data, movies

def train(data, labels): # treniranje modela s tensorflowom
    data_np = data.numpy()
    labels_np = np.array(labels)

    X_train, X_val, y_train, y_val = train_test_split(data_np, labels_np, test_size=0.2, random_state=42)

    model = tf.keras.Sequential([
        tf.keras.layers.Dense(128, activation='relu', input_dim=X_train.shape[1]),
        BatchNormalization(),
        Dropout(0.2),
        tf.keras.layers.Dense(64, activation='relu'),
        BatchNormalization(),
        Dropout(0.2),
        tf.keras.layers.Dense(32, activation='relu'),
        tf.keras.layers.Dense(1)  # predviđa ocjenu
    ])

    model.compile(optimizer='adam', loss='mean_squared_error', metrics=['mae', tf.keras.metrics.RootMeanSquaredError()])
    model.fit(X_train, y_train, epochs=10, batch_size=32, validation_data=(X_val, y_val), verbose=1)
    return model

def get_recommendations(model, data, movies):
    """Vrati preporučene filmove sortirane po score-u predikcije."""
    predictions = model.predict(data)

    recommended_movies = sorted(zip(predictions, movies), key=lambda x: x[0], reverse=True)

    result = []
    for _, movie in recommended_movies[:20]:
        result.append({
            "_id": movie["_id"],
            "name": movie["name"],
            "year": movie["year"],
            "genre": movie["genre"],
            "poster_url": movie["poster_url"],
            "score": movie["score"]
        })
    return result


def get_christmas_mov(movies, top_n=10):
    christmas_keywords = {"christmas", "holiday", "santa claus", "xmas"}

    christmas_mov = [
        movie for movie in movies
        if movie.get("keywords") and set(movie["keywords"]).intersection(christmas_keywords)
    ]

    for movie in christmas_mov:
        movie["_id"] = str(movie["_id"])

    # sortiranje prema score i vraćanje top_n rezultata
    return sorted(christmas_mov, key=lambda x: x["score"], reverse=True)[:top_n]

def generate_recommendations(user, movies, model, normalized_data, max_per_genre=5, top_n=20): # glavni algporitam za preporuke filmova

    if user is None:
        print("Korisnik nije prijavljen, prikaz top 10 filmova.")
        return sorted(movies, key=lambda x: x["score"], reverse=True)[:10]

    preferred_genres = user.get("genres", [])
    watched_movie_ids = set(user.get("watched_movies", []))

    directors = set()
    stars = set()
    watched_genres = set()

    watched_movies = [movie for movie in movies if str(movie["_id"]) in watched_movie_ids]

    for movie in watched_movies:
        directors.update(movie.get("director", []))
        stars.update(movie.get("stars", []))
        watched_genres.update(movie.get("genre", "").split(", "))

    combined_genres = set(preferred_genres) | watched_genres

    predictions = model.predict(normalized_data)
    for i, movie in enumerate(movies):
        movie['predicted_score'] = float(predictions[i][0])

        if movie["year"] > 2000:
            movie['predicted_score'] += 5.0

        if any(genre in combined_genres for genre in movie.get("genre", "").split(", ")):
            movie['predicted_score'] += 3.0

        if any(d in directors for d in movie.get("director", [])):
            movie['predicted_score'] += 2.0

        if any(a in stars for a in movie.get("stars", [])):
            movie['predicted_score'] += 2.0

    filtered_movies = [movie for movie in movies if str(movie["_id"]) not in watched_movie_ids]

    # grupiraj po žanru i sortiraj
    genre_to_movies = defaultdict(list)
    for movie in filtered_movies:
        if movie["predicted_score"] > 6 and movie["score"] > 6.2:
            genre_to_movies[movie["genre"]].append(movie)

    recommended_movies = []
    seen_movies = set()

    for genre in preferred_genres:
        genre_movies = genre_to_movies.get(genre, [])
        count = 0
        for movie in genre_movies:
            if movie['name'] not in seen_movies and count < max_per_genre:
                recommended_movies.append(movie)
                seen_movies.add(movie['name'])
                count += 1

    for genre, movies_in_genre in genre_to_movies.items():
        if genre not in preferred_genres:
            count = 0
            for movie in sorted(movies_in_genre, key=lambda x: x["predicted_score"], reverse=True):
                if movie['name'] not in seen_movies and count < max_per_genre:
                    recommended_movies.append(movie)
                    seen_movies.add(movie['name'])
                    count += 1

    return sorted(recommended_movies, key=lambda x: x["predicted_score"], reverse=True)[:top_n]


movies = load_movie_data()# treniranje modela

normalized_data, movies = prepare_data(movies)

labels = np.array([movie['score'] for movie in movies])
model = train(normalized_data, labels)

recommendations = get_recommendations(model, normalized_data, movies) # Dobivanje preporuka
