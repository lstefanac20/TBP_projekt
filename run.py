from app import create_app
import os

app = create_app()

if __name__ == '__main__':
    environment = os.getenv('FLASK_ENV', 'development')  

    if environment == 'development':
        app.run(debug=True)
    else:
        app.run(debug=False, host='0.0.0.0', port=int(os.getenv('PORT', 5000)))
