import os
from flask import Flask, send_from_directory, request, jsonify, Response
import binascii
import re
import firebase_admin
from firebase_admin import db
import time
import config

app = Flask(__name__)
app.config.from_object(config.ProductionConfig)
if app.config['APP_ENV'] == 'gcp':
    default_app = firebase_admin.initialize_app(options={
        'databaseURL': app.config['DATABASE_URL']
    })
else:
    # We need credentials for running locally.
    creds = firebase_admin.credentials.Certificate(app.config['CREDS_FILE'])
    default_app = firebase_admin.initialize_app(creds, {
        'databaseURL': app.config['DATABASE_URL']
    })

ref = db.reference(app.config['DB_REFERENCE'])


@app.route('/')
def serve_index():
    return send_from_directory('static', 'index.html')


@app.route('/<name>')
def serve_files(name):
    return send_from_directory('static', 'index.html')


@app.route('/documents', methods=["POST"])
def handle_docs():
    paste_id = str(binascii.b2a_hex(os.urandom(int(app.config['PASTE_LENGTH']/2))), 'UTF-8')
    paste_content = request.get_data().decode('UTF-8')
    forwarded = request.environ.get('HTTP_X_FORWARDED_FOR')
    req_ip = forwarded if forwarded is not None else request.remote_addr
    curr_time = int(time.time())

    data = {
        paste_id:
            {
                "content": paste_content,
                "user_ip": req_ip,
                "creation_time": curr_time
            }
    }
    ref.set(data)
    return jsonify(
        key=paste_id
    )


@app.route('/documents/<docid>')
def find_docs(docid):
    success, data = get_paste(docid)
    if not success:
        if data == "BAD_REQUEST":
            return "Bad Request", 400
        elif data == "NOT_FOUND":
            return "Not Found", 404
        else:
            return "An error occurred while processing your request.", 500
    return jsonify(
        data=data,
        key=docid
    )


def get_paste(key):
    try:
        pattern = re.compile("^[a-f0-9]{6,32}$")  # 6-32 hex
        if pattern.fullmatch(key) is None:
            return False, "BAD_REQUEST"
        try:
            data = ref.get(key)
            return True, data[0][key]["content"]
        except:
            return False, "NOT_FOUND"
    except:
        return False, "INTERNAL_ERROR"


@app.route('/raw/<docid>')
def get_raw(docid):
    success, data = get_paste(docid)
    if not success:
        if data == "BAD_REQUEST":
            return "Bad Request", 400
        elif data == "NOT_FOUND":
            return "Document Not Found", 404
        else:
            return "An error occurred while processing your request.", 500
    res = Response(data, mimetype='text/plain')
    res.headers["Cache-Control"] = 'public, max-age=86400'
    # chrome keeps trying to want to translate this!
    res.headers["Content-Language"] = 'en-US'
    return res


@app.errorhandler(404)
def fallback(e):
    return 'The requested URL "' + request.url + '" was not found on this server.', 404


@app.after_request
def after_req(response):
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Powered-By"] = "April's Tears"
    return response


port = int(os.environ.get('PORT', 8080))
if __name__ == '__main__':
    app.run(threaded=True, host='0.0.0.0', port=port)
