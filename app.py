from flask import Flask, request, jsonify, session, redirect, url_for
from pymongo import MongoClient
from dotenv import load_dotenv
import os
from flask import render_template
from datetime import datetime
from bson.objectid import ObjectId
from flask_session import Session
from flask_bcrypt import Bcrypt

load_dotenv()

# Use environment variables
mongo_uri = os.getenv('MONGO_URI')
db_name = os.getenv('DATABASE_NAME')
prompt_collection_name = os.getenv('PROMPTS_COLLECTION')
users_collection_name = os.getenv('USERS_COLLECTION')
secret_key = os.getenv('SECRET_KEY')

# Clients
app = Flask(__name__)
bcrypt = Bcrypt(app)
client = MongoClient(mongo_uri)

# Database and collections
db = client[db_name]
prompts_collection = db[prompt_collection_name]
users_collection = db[users_collection_name]


# Secret key for sessions (use a secure, random value in production)
app.config['SECRET_KEY'] = secret_key

# Configure session to use filesystem (instead of signed cookies)
app.config['SESSION_TYPE'] = 'filesystem'
Session(app)

@app.route('/api/prompt', methods=['POST'])
def post_prompt():
    if 'username' not in session:
        return jsonify({'error': 'User not authenticated'}), 401

    data = request.json
    # Use the username from the session
    username = session['username']

    # Save the prompt with the username from the session
    prompt_data = {
        'user': username,
        'name': data.get('name'),
        'content': data.get('content'),
        'description': data.get('description'),
        'timestamp': datetime.utcnow()
    }
    prompts_collection.insert_one(prompt_data)
    return jsonify({'message': 'Prompt saved'}), 200


@app.route('/api/prompts', methods=['GET'])
def get_prompts():
    if 'username' not in session:
        return jsonify({'error': 'User not authenticated'}), 401

    username = session['username']

    all_prompts = prompts_collection.find({'user': username}).sort("timestamp", -1)
    return jsonify([{'_id': str(prompt['_id']), 'name': prompt['name'], 'description': prompt.get('description', ''), 'content': prompt['content']} for prompt in all_prompts])


@app.route('/api/prompt/<prompt_id>', methods=['DELETE'])
def delete_prompt(prompt_id):
    try:
        result = prompts_collection.delete_one({'_id': ObjectId(prompt_id)})
        if result.deleted_count > 0:
            return jsonify({'message': 'Prompt deleted'}), 200
        else:
            return jsonify({'error': 'Prompt not found'}), 404
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/api/prompt/<prompt_id>', methods=['PUT'])
def edit_prompt(prompt_id):
    if 'username' not in session:
        return jsonify({'error': 'User not authenticated'}), 401

    try:
        data = request.json
        if not all(key in data for key in ['content', 'description']):
            return jsonify({'error': 'Missing data in request'}), 400

        # Find the prompt to ensure it belongs to the logged-in user
        existing_prompt = prompts_collection.find_one({'_id': ObjectId(prompt_id), 'user': session['username']})
        if not existing_prompt:
            return jsonify({'error': 'Prompt not found or access denied'}), 403

        # Proceed to update the prompt
        result = prompts_collection.update_one(
            {'_id': ObjectId(prompt_id)},
            {'$set': {'description': data['description'], 'content': data['content']}}
        )

        if result.modified_count > 0:
            return jsonify({'message': 'Prompt updated'}), 200
        else:
            return jsonify({'error': 'Prompt not found or not modified'}), 404
    except Exception as e:
        app.logger.error(f"Error in edit_prompt: {e}")  # Log the exception
        return jsonify({'error': str(e)}), 500



@app.route('/api/prompt-by-name', methods=['GET'])
def get_prompt_by_name():
    key = request.args.get('key')
    prompt_name = request.args.get('name')

    print(f"Received API Key: {key}")  # Debug print
    print(f"Received Prompt Name: {prompt_name}")  # Debug print

    if not key or not prompt_name:
        return jsonify({'error': 'Missing API key or prompt name'}), 400

    # Check if the API key is valid
    user = users_collection.find_one({'api_key': key})

    if not user:
        return jsonify({'error': 'Invalid API key'}), 401

    # Find the prompt by name and user
    prompt = prompts_collection.find_one({'name': prompt_name, 'user': user['username']})

    if not prompt:
        return jsonify({'error': 'Prompt not found'}), 404

    # Include the description in the response
    return jsonify({'name': prompt['name'], 'content': prompt['content'], 'description': prompt.get('description', 'No description provided')}), 200



@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        try:
            data = request.json
            username = data.get('username')
            password = data.get('password')
            
            print(f"Attempting to log in user: {username}")

            user = users_collection.find_one({'username': username})

            if user:
                print(f"User found in DB: {user}")
                if user and bcrypt.check_password_hash(user['password'], password):
                    session['username'] = user['username']
                    print("Login successful")
                    return jsonify({'message': 'Logged in successfully'}), 200
                else:
                    print("Login failed: Invalid password")
                    return jsonify({'error': 'Invalid credentials'}), 401
            else:
                print("Login failed: User not found")
                return jsonify({'error': 'User not found'}), 404
        except Exception as e:
            print(f"Error during login: {e}")
            return jsonify({'error': str(e)}), 500
    else:
        if 'username' in session:
            return redirect(url_for('index'))
        return render_template('login.html')


@app.route('/logout')
def logout():
    session.pop('username', None)  # Remove username from session
    return redirect(url_for('login'))

@app.route('/')
def index():
    if 'username' not in session:
        return redirect(url_for('login'))  # Redirect to login if not authenticated
    return render_template('home.html')  # Show home page if authenticated


if __name__ == '__main__':
    app.run(debug=False)
