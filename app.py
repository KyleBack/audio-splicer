import sys

from flask_cors import CORS

from splice_videos import *
from flask import Flask, request, jsonify, json
from werkzeug.exceptions import HTTPException, BadRequest

app = Flask(__name__)
CORS(app)

@app.errorhandler(BadRequest)
def handle_bad_request(e):
    return jsonify({
        'code': 400,
        'name:': 'Bad request!',
        'description': e.description
    }), 400

@app.errorhandler(HTTPException)
def handle_exception(e):
    response = e.get_response()
    response.data = json.dumps({
        "code": e.code,
        "name": e.name,
        "description": e.description,
    })
    response.content_type = "application/json"
    return response

@app.route("/")
def home_view():
        return "<h1>Welcome to Audio Splicer! Go to GitHub for more info: https://github.com/KyleBack/audio-splicer</h1>"

@app.route('/splice-videos', methods=['POST'])
def splice_videos():
    request_json = request.get_json()
    if request_json is None:
        raise BadRequest('Request body not included.')

    splice_videos_request = validate_request(request_json)

    return execute(splice_videos_request)

if __name__ == '__main__':
    sys.path.append(f'{os.getcwd()}/ffmpeg.exe')
    app.run()