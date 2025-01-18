from werkzeug.security import generate_password_hash, check_password_hash

def register_user(name, user_name, email, password, genres, user_collection):
    if user_collection.find_one({"email": email}):
        return {"status": "error", "message": "Korisnik već postoji."}
    if user_collection.find_one({"user_name": user_name}):
        return {"status": "error", "message": "Korisničko ime već postoji."}

    hashed_password = generate_password_hash(password)
    user_collection.insert_one({
        "name": name,
        "user_name": user_name,
        "email": email,
        "password": hashed_password,
        "genres": genres
    })
    return {"status": "success", "message": "Korisnik uspješno registriran."}


def login_user(user_name_or_email, password, user_collection):
    user = user_collection.find_one({
        "$or": [
            {"email": user_name_or_email},
            {"user_name": user_name_or_email}
        ]
    })
    if not user:
        return {"status": "error", "message": "Korisnik ne postoji."}

    if check_password_hash(user["password"], password):
        return {"status": "success", "message": "Prijava uspješna.", "user": user}
    else:
        return {"status": "error", "message": "Pogrešna lozinka."}
