from flask import Blueprint, render_template, jsonify, request, session, redirect
from pymongo import MongoClient
from bson.objectid import ObjectId
from .authorization import register_user, login_user
from collections import defaultdict
from .recommendation import generate_recommendations, get_christmas_mov, model, normalized_data

main = Blueprint('main', __name__)
#povezivanje na bazu
try:
    client = MongoClient("mongodb://127.0.0.1:27017/")
    database = client["movies"]
    collection = database["movies"]
    user_collection = database["users"]
    print("Uspješno spajanje na MongoDB")
except Exception as e:
    print("Greška prilikom spajanja")


@main.route('/')
def home():
    return render_template('index.html')

# provjera sesije
@main.route('/session-status')
def session_status():
    is_logged_in = "user_id" in session
    user_id = session.get("user_id", None)

    if is_logged_in and user_id:
        user = user_collection.find_one({"_id": ObjectId(user_id)})
        if user:
            name = user.get("name", "")
            user_name = user.get("user_name", "")
            return jsonify({
                "isLoggedIn": is_logged_in,
                "userId": str(user_id),
                "name": name,
                "userName": user_name
            })

    return jsonify({
        "isLoggedIn": is_logged_in,
        "userId": None,
        "name": None,
        "userName": None
    })


# login
@main.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        try:
            data = request.get_json()
            user_name_or_email = data.get('user_name_or_email')
            password = data.get('password')

            if not user_name_or_email or not password: # provjera jesu li podaci uneseni
                return jsonify({"status": "error", "message": "Nedostaju podaci."}), 400

            # `login_user` funkciju za provjeru korisnika
            result = login_user(user_name_or_email, password, user_collection)
            if result["status"] == "error":
                return jsonify(result), 400

            # spremanje korisničkih podatka u sesiju
            user = result["user"]
            session["user_id"] = str(user["_id"])
            session["user_name"] = user["user_name"]
            return jsonify({"status": "success", "message": "Prijava uspješna!"})

        except Exception as e:
            return jsonify({"status": "error", "message": f"Došlo je do greške: {str(e)}"}), 500

    return render_template('login.html')


# registracija
@main.route('/signup', methods=['GET', 'POST'])
def signup():
    if request.method == 'POST':
        try:
            data = request.get_json()
            if not data:
                return jsonify({"status": "error", "message": "Podaci nisu poslani."}), 400

            name = data.get('name')
            user_name = data.get('user_name')
            email = data.get('email')
            password = data.get('password')
            genres = data.get('genres')

            if not name or not user_name or not email or not password:
                return jsonify({"status": "error", "message": "Nedostaju podaci."}), 400

            if not genres or len(genres) == 0:
                return jsonify({"status": "error", "message": "Morate odabrati barem jedan žanr."}), 400

            if len(genres) > 5:
                return jsonify({"status": "error", "message": "Možete odabrati najviše 5 žanrova."}), 400

            if user_collection.find_one({"user_name": user_name}): # je li korisnik već u bazi
                return jsonify({"status": "error", "message": "Zauzeto korisničko ime"}), 400

            result = register_user(name, user_name, email, password, genres, user_collection)

            if result["status"] == "success": # automatska prijava korisnika
                user = user_collection.find_one({"user_name": user_name})
                session["user_id"] = str(user["_id"])
                session["user_name"] = user["user_name"]
                session["name"] = user["name"]

                return jsonify({"status": "success", "message": "Registracija uspješna. Dobrodošli!"}), 200

            return jsonify(result)
        except Exception as e:
            print(f"Greška: {e}")
            return jsonify({"status": "error", "message": "Došlo je do greške."}), 500

    return render_template('signup.html')

# odjava
@main.route('/logout')
def logout():
    session.clear()
    #return jsonify({"status": "success", "message": "Odjava uspješna."})
    return redirect('/')

# ispis popularnih filmova *BEZ REGISTRACIJE*
@main.route('/movies/popular', methods=['GET'])
def popular_movies():
    try:
        # Dohvati 10 najbolje ocijenjenih filmova
        movies = list(collection.find({}).sort("score", -1).limit(10))
        for movie in movies:
            movie["_id"] = str(movie["_id"])
        return jsonify({"status": "success", "movies": movies})
    except Exception as e:
        print(f"Greška pri dohvaćanju popularnih filmova: {e}")
        return jsonify({"status": "error", "message": str(e)}), 500


# žanrovi
@main.route('/genres')
def genres_page():
    return render_template('genres.html')

@main.route('/movies/genres')
def movies_by_genre():
    genre = request.args.get('genre')
    page = int(request.args.get('page', 1))
    limit = int(request.args.get('limit', 20))

    if not genre:
        return jsonify({"status": "error", "message": "Žanr nije specificiran"}), 400

    skip = (page - 1) * limit

    movies = list(collection.find(
        {"genre":{"$regex":genre, "$options": "i"}}
    ).sort("year",-1).skip(skip).limit(limit))

    total_movies = collection.count_documents({"genre": {"$regex": genre, "$options": "i"}})
    for movie in movies:
        movie['_id'] = str(movie['_id'])

    return jsonify({
        "status": "success",
        "movies": movies,
        "total": total_movies,
        "page": page,
        "pages": (total_movies + limit - 1) // limit
    })


# pojedinačni filmovi prikaz
@main.route('/movie/<movie_id>', methods=['GET'])
def movie_details(movie_id):
    try:
        movie = collection.find_one({"_id": ObjectId(movie_id)})
        if not movie:
            return jsonify({"status":"error", "message":"Nije pronadjen film"}), 404

        movie['_id'] = str(movie['_id'])
        return jsonify({"status": "success", "movie": movie})
    except Exception as e:
        return jsonify({"status": "error", "message": str((e))}), 500

@main.route('/movie.html')
def movie_page():
    return render_template('movie.html')

# profil
@main.route('/profile', methods=['GET'])
def profile():
    return render_template('profile.html')

@main.route('/user/preferences', methods=['GET'])
def user_preferences():
    try:
        user_id = request.args.get('user_id')
        if not user_id:
            return jsonify({"status": "error", "message": "Nije proslijeđen ID"}), 400

        user = user_collection.find_one({"_id": ObjectId(user_id)})

        if not user:
            return jsonify({"status": "error", "message": "Nije pronađen korisnik"}), 404

        genres = user.get("genres", [])
        return jsonify({"status": "success", "genres": genres})
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500


@main.route('/user/watched-movies', methods=['POST'])
def add_watched_movie():
    try:
        data = request.get_json()  # Očekuje JSON tijelo zahtjeva
        user_name = data.get('user_name')
        movie_id = data.get('movie_id')

        if not user_name or not movie_id:
            return jsonify({"status": "error", "message": "Nedostaju podaci o korisniku ili filmu"}), 400

        user = user_collection.find_one({"user_name": user_name})
        if not user:
            return jsonify({"status": "error", "message": "Korisnik nije pronađen"}), 404

        watched_movies = user.get("watched_movies", [])
        if movie_id not in watched_movies: # dodaj film u watched listu ako već nije tamo
            watched_movies.append(movie_id)
            user_collection.update_one(
                {"user_name": user_name},
                {"$set": {"watched_movies": watched_movies}}
            )
            return jsonify({"status": "success", "message": "Film je dodan u gledane filmove"})

        return jsonify({"status": "error", "message": "Film je već u gledanim filmovima"})
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500


@main.route('/user/watched-movies', methods=['GET'])
def get_watched_movies():
    try:
        user_name = request.args.get('user_name')

        if not user_name:
            return jsonify({"status": "error", "message": "Nedostaju podaci o korisniku"}), 400

        user = user_collection.find_one({"user_name": user_name})
        if not user:
            return jsonify({"status": "error", "message": "Korisnik nije pronađen"}), 404

        watched_movies_ids = user.get("watched_movies", [])
        watched_movies = list(collection.find({"_id": {"$in": [ObjectId(id) for id in watched_movies_ids]}}))

        for movie in watched_movies:
            movie['_id'] = str(movie['_id'])

        return jsonify({"status": "success", "movies": watched_movies})
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500

@main.route('/user/is-watched', methods=['GET'])
def is_watched():
    try:
        user_name = request.args.get('user_name')
        movie_id = request.args.get('movie_id')

        if not user_name or not movie_id:
            return jsonify({"status":"error", "message": "Nedostaju podaci o korisniku ili filmu"}), 400

        user = user_collection.find_one({"user_name": user_name})
        if not user:
            return jsonify({"status": "error", "message": "Korisnik nije pronadjen"}), 404

        watched_movie = user.get("watched_movies", [])
        is_watched = movie_id in watched_movie

        return jsonify({"status":"success", "is_watched": is_watched})
    except Exception as e:
        return jsonify({"status":"error", "message":str((e))}), 500


@main.route('/user/watched-movies', methods=['DELETE'])
def remove_watched_movie():
    try:
        data = request.get_json()
        user_name = data.get('user_name')
        movie_id = data.get('movie_id')

        if not user_name or not movie_id:
            return jsonify({"status": "error", "message": "Nedostaju podaci o korisniku ili filmu"}), 400

        user = user_collection.find_one({"user_name": user_name})
        if not user:
            return jsonify({"status": "error", "message": "Korisnik nije pronađen"}), 404

        watched_movies = user.get("watched_movies", [])
        if movie_id in watched_movies:
            watched_movies.remove(movie_id)

            user_collection.update_one(
                {"user_name": user_name},
                {"$set": {"watched_movies": watched_movies}}
            )

            rated_movies = user.get("rated_movies", {}) # ak postoji i ocjena u gledanim filmovima i ukloni se film ukloni i ocjenu
            if movie_id in rated_movies:
                del rated_movies[movie_id]
                user_collection.update_one(
                    {"user_name": user_name},
                    {"$set": {"rated_movies": rated_movies}}
                )

            return jsonify({"status": "success", "message": "Film i ocjena su uspješno uklonjeni."})

        return jsonify({"status": "error", "message": "Film nije u gledanim filmovima"}), 404
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500


@main.route('/recommendations', methods=['GET'])
def recommendations():
    try:
        user_id = session.get("user_id")
        if not user_id:
            return jsonify({"status": "error", "message": "Korisnik nije prijavljen"}), 403

        user = user_collection.find_one({"_id": ObjectId(user_id)})
        if not user:
            return jsonify({"status": "error", "message": "Korisnik nije pronađen"}), 404

        movies = list(collection.find({}))
        for movie in movies:
            movie["_id"] = str(movie["_id"])

        recommended_movies = generate_recommendations(user, movies, model, normalized_data, max_per_genre=5)

        return jsonify({"status": "success", "movies": recommended_movies[:20]})
    except Exception as e:
        print(f"Error in /recommendations: {e}")
        return jsonify({"status": "error", "message": str(e)}), 500


@main.route('/christmas-recommendations', methods=['GET'])
def christmas_recommendations():
    try:
        movies = list(collection.find({}, {"name": 1, "keywords": 1, "score": 1, "poster_url": 1, "year": 1, "genre": 1}))

        for movie in movies:
            movie["_id"] = str(movie["_id"])

        recommended_movies = get_christmas_mov(movies=movies)
        return jsonify({
            "status": "success",
            "movies": recommended_movies
        }), 200
    except Exception as e:
        print("Greška:", e)
        return jsonify({
            "status": "error",
            "message": str(e)
        }), 500


@main.route('/personal-recommendations', methods=['GET'])
def personal_recommendations():
    try:
        user_id = session.get("user_id")
        if not user_id:
            return jsonify({"status": "error", "message": "Korisnik nije prijavljen"}), 403

        user = user_collection.find_one({"_id": ObjectId(user_id)})
        if not user:
            return jsonify({"status": "error", "message": "Korisnik nije pronađen"}), 404

        movies = list(collection.find({}))
        for movie in movies:
            movie["_id"] = str(movie["_id"])

        recommended_movies = generate_recommendations(user, movies, model, normalized_data)

        return jsonify({"status": "success", "movies": recommended_movies})
    except Exception as e:
        print(f"Greška u '/personal-recommendations': {e}")
        return jsonify({"status": "error", "message": str(e)}), 500


@main.route('/rate-movie', methods=['POST'])
def rate_movie():
    """
    Ruta za ocjenjivanje filma.
    Očekuje JSON tijelo zahtjeva sa `user_id`, `movie_id` i `rating`.
    """
    try:
        data = request.get_json()
        user_id = data.get('user_id')
        movie_id = data.get('movie_id')
        rating = data.get('rating')

        if not user_id or not movie_id or rating is None:
            return jsonify({"status": "error", "message": "Nedostaju podaci o korisniku, filmu ili ocjeni."}), 400

        if not (1 <= rating <= 10):
            return jsonify({"status": "error", "message": "Ocjena mora biti između 1 i 10."}), 400

        user = user_collection.find_one({"_id": ObjectId(user_id)})
        if not user:
            return jsonify({"status": "error", "message": "Korisnik nije pronađen."}), 404

        rated_movies = user.get("rated_movies", {})
        rated_movies[movie_id] = rating

        user_collection.update_one(
            {"_id": ObjectId(user_id)},
            {"$set": {"rated_movies": rated_movies}}
        )

        return jsonify({"status": "success", "message": "Film uspješno ocijenjen."})
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500


# sekija korisnicima se još svidja
def get_popular_movies(user_collection, movie_collection, min_ratings=3):
    movie_ratings = defaultdict(list)

    users = user_collection.find({}, {"rated_movies": 1}) # prikupi sve ocjene
    for user in users:
        rated_movies = user.get("rated_movies", {})
        for movie_id, rating in rated_movies.items():
            movie_ratings[movie_id].append(rating)

    avg_ratings = [] # prosječna ocjena za svaki film
    for movie_id, ratings in movie_ratings.items():
        if len(ratings) >= min_ratings:  # uvjet minimalnog broja ocjena = 3
            avg_score = sum(ratings) / len(ratings)
            avg_ratings.append((movie_id, avg_score, len(ratings)))

    avg_ratings = sorted(avg_ratings, key=lambda x: (-x[1], -x[2]))

    popular_movies = []
    for movie_id, avg_score, rating_count in avg_ratings:
        movie = movie_collection.find_one({"_id": ObjectId(movie_id)})
        if movie:
            movie["_id"] = str(movie["_id"])
            movie["avg_score"] = avg_score
            movie["rating_count"] = rating_count
            popular_movies.append(movie)

    return popular_movies


@main.route('/movies/similar-likes', methods=['GET'])
def similar_likes():
    try:
        user_id = session.get("user_id")
        if not user_id:
            return jsonify({"status": "error", "message": "Korisnik nije prijavljen"}), 403

        user = user_collection.find_one({"_id": ObjectId(user_id)})
        if not user:
            return jsonify({"status": "error", "message": "Korisnik nije pronađen"}), 404

        watched_movie_ids = set(user.get("watched_movies", []))

        all_users = list(user_collection.find({"rated_movies": {"$exists": True}}))
        movie_scores = defaultdict(list)

        for other_user in all_users:
            for movie_id, rating in other_user.get("rated_movies", {}).items():
                movie_scores[movie_id].append(rating)

        average_scores = { # prosječna ocjena za svaki film
            movie_id: sum(ratings) / len(ratings) for movie_id, ratings in movie_scores.items()
        }

        recommended_movies = [ # filtriranje filmova koje korisnik nije gledao; sortiranje prema prosj. ocjeni
            {"_id": movie_id, "average_score": avg_score}
            for movie_id, avg_score in average_scores.items()
            if movie_id not in watched_movie_ids
        ]
        recommended_movies = sorted(recommended_movies, key=lambda x: x["average_score"], reverse=True)[:5]

        movie_details = list(collection.find(
            {"_id": {"$in": [ObjectId(movie["_id"]) for movie in recommended_movies]}}
        ))

        for movie in movie_details:
            movie["_id"] = str(movie["_id"])
            movie["average_score"] = next(
                (rec["average_score"] for rec in recommended_movies if rec["_id"] == str(movie["_id"])), None
            )

        return jsonify({"status": "success", "movies": movie_details})
    except Exception as e:
        print(f"Greška u '/movies/similar-likes': {e}")
        return jsonify({"status": "error", "message": str(e)}), 500

