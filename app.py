from flask import Flask, request, jsonify, session, redirect, url_for
from pymongo import MongoClient
from dotenv import load_dotenv
import os
from flask import render_template
from datetime import datetime
from bson.objectid import ObjectId
from flask_session import Session
from flask_bcrypt import Bcrypt
import json
import bleach

load_dotenv()

# Use environment variables
mongo_uri = os.getenv('MONGO_URI')
db_name = os.getenv('DATABASE_NAME')
prompts_collection_name = os.getenv('PROMPTS_COLLECTION')
users_collection_name = os.getenv('USERS_COLLECTION')
functions_collection_name = os.getenv('FUNCTIONS_COLLECTION')
secret_key = os.getenv('SECRET_KEY')

# Clients
app = Flask(__name__)
bcrypt = Bcrypt(app)
client = MongoClient(mongo_uri)

# Database and collections
db = client[db_name]
prompts_collection = db[prompts_collection_name]
users_collection = db[users_collection_name]
functions_collection = db[functions_collection_name]


# Secret key for sessions (use a secure, random value in production)
app.config['SECRET_KEY'] = secret_key
app.config['SESSION_TYPE'] = 'filesystem'
Session(app)

ALLOWED_TAGS = [
    'a', 'abbr', 'b', 'blockquote', 'br', 'caption', 'code', 'col', 'colgroup', 
    'div', 'em', 'h1', 'h2', 'h3', 'h4', 'h5', 'h6', 'hr', 'i', 'img', 'li', 
    'ol', 'p', 'pre', 'q', 'small', 'span', 'strike', 'strong', 'sub', 'sup', 
    'table', 'tbody', 'td', 'tfoot', 'th', 'thead', 'tr', 'u', 'ul'
]

@app.route('/api/prompt', methods=['POST'])
def post_prompt():
    if 'username' not in session:
        return jsonify({'error': 'User not authenticated'}), 401

    data = request.json
    username = session['username']

    # Check if prompt name already exists for the user
    existing_prompt = prompts_collection.find_one({'user': username, 'name': data.get('name')})
    if existing_prompt:
        return jsonify({'error': 'Prompt name already exists, please use a unique name'}), 409

    sanitized_content = bleach.clean(data.get('content'), tags=ALLOWED_TAGS, strip=True)
    sanitized_description = bleach.clean(data.get('description'), tags=ALLOWED_TAGS, strip=True)

    prompt_data = {
        'user': username,
        'name': data.get('name'),
        'content': sanitized_content,
        'description': sanitized_description,
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
        
        sanitized_content = bleach.clean(data.get('content'), tags=ALLOWED_TAGS, strip=True)
        sanitized_description = bleach.clean(data.get('description'), tags=ALLOWED_TAGS, strip=True)


        # Find the prompt to ensure it belongs to the logged-in user
        existing_prompt = prompts_collection.find_one({'_id': ObjectId(prompt_id), 'user': session['username']})
        if not existing_prompt:
            return jsonify({'error': 'Prompt not found or access denied'}), 403

        # Proceed to update the prompt
        result = prompts_collection.update_one(
            {'_id': ObjectId(prompt_id)},
            {'$set': {'description': sanitized_description , 'content': sanitized_content}}
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
    prompt_content = prompt.get('content', '')
    # remove all html tags
    prompt_content = bleach.clean(prompt_content, tags=[], strip=True)

    if not prompt:
        return jsonify({'error': 'Prompt not found'}), 404

    # Include the description in the response
    return jsonify({'name': prompt['name'], 'content': prompt_content, 'description': prompt.get('description', 'No description provided')}), 200



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

@app.route('/functions')
def functions():
    if 'username' not in session:
        return redirect(url_for('login'))  # Redirect to login if not authenticated
    return render_template('functions.html')  # Show functions page if authenticated

@app.route('/api/function', methods=['POST'])
def post_function():
    if 'username' not in session:
        return jsonify({'error': 'User not authenticated'}), 401

    data = request.json
    username = session['username']

    # Check if function name already exists for the user
    existing_function = functions_collection.find_one({'user': username, 'name': data.get('name')})
    if existing_function:
        return jsonify({'error': 'Function name already exists, please use a unique name'}), 409

    function_data = {
        'user': username,
        'name': data.get('name'),
        'description': data.get('description'),
        'parameterType': data.get('parameterType'),
        'properties': data.get('properties', []),
        'timestamp': datetime.utcnow()
    }
    functions_collection.insert_one(function_data)
    return jsonify({'message': 'Function saved'}), 200



@app.route('/api/functions', methods=['GET'])
def get_functions():
    if 'username' not in session:
        return jsonify({'error': 'User not authenticated'}), 401

    username = session['username']
    all_functions = functions_collection.find({'user': username}).sort("timestamp", -1)
    return jsonify([{
        '_id': str(function['_id']),
        'name': function['name'],
        'description': function.get('description', ''),
        'parameterType': function.get('parameterType', ''),
        'properties': function.get('properties', [])
    } for function in all_functions])


@app.route('/api/function/<function_id>', methods=['DELETE'])
def delete_function(function_id):
    try:
        result = functions_collection.delete_one({'_id': ObjectId(function_id)})
        if result.deleted_count > 0:
            return jsonify({'message': 'Function deleted'}), 200
        else:
            return jsonify({'error': 'Function not found'}), 404
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/api/function-by-name', methods=['GET'])
def get_function_by_name():
    key = request.args.get('key')
    function_name = request.args.get('name')

    print(f"Received API Key: {key}")  # Debug print
    print(f"Received Function Name: {function_name}")  # Debug print

    if not key or not function_name:
        return jsonify({'error': 'Missing API key or function name'}), 400

    # Check if the API key is valid
    user = users_collection.find_one({'api_key': key})

    if not user:
        return jsonify({'error': 'Invalid API key'}), 401

    function = functions_collection.find_one({'name': function_name, 'user': user['username']})

    if not function:
        return jsonify({'error': 'Function not found'}), 404

    properties = function.get('properties', [])
    properties_str = ", ".join(
        f'"{prop["name"]}": {{"type": "{prop["type"]}", "description": "{prop["description"]}"}}'
        for prop in properties
    )

    required = [prop['name'] for prop in properties if prop.get('required')]
    required_str = json.dumps(required)

    response_str = f'{{"name": "{function["name"]}", "description": "{function.get("description", "")}", "parameters": {{"type": "{function.get("parameterType", "object")}", "properties": {{{properties_str}}}, "required": {required_str}}}}}'

    return response_str, 200, {'ContentType':'application/json'}


if __name__ == '__main__':
    app.run(debug=False)
