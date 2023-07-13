import cv2
import time
import numpy as np
import pymysql
import jwt, os, random
from flask import Flask, make_response, jsonify, render_template, session,Response, json
from flask_restx import Resource, Api, reqparse
from flask_sqlalchemy import SQLAlchemy
from flask_cors import CORS
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime, timedelta
from collections import defaultdict
from flask_mail import Mail, Message
from tensorflow.keras.models import model_from_json  
from tensorflow.keras.utils import img_to_array
from tensorflow.keras.preprocessing import image 
from keras.models import load_model
from pymongo import MongoClient

pymysql.install_as_MySQLdb()

app = Flask(__name__)
api = Api(app)
CORS(app)

cluster = MongoClient('mongodb://localhost:27017')
mongo_db = cluster['capstone']
col = mongo_db['history']

app.config["SQLALCHEMY_DATABASE_URI"] = "mysql://root:@127.0.0.1:3306/flask_capstone"
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['SECRET_KEY'] = 'WhatEverYouWant'
app.config['MAIL_SERVER'] = 'smtp.gmail.com' 
app.config['MAIL_PORT'] = 465
app.config['MAIL_USE_SSL'] = True
app.config['MAIL_USERNAME'] = os.environ.get("MAIL_USERNAME")
app.config['MAIL_PASSWORD'] = os.environ.get("MAIL_PASSWORD")
mail = Mail(app)
db = SQLAlchemy(app) 

class Users(db.Model):
    id          = db.Column(db.Integer(), primary_key=True, nullable=False)
    firstname   = db.Column(db.String(35), nullable=False)
    email       = db.Column(db.String(65), unique=True, nullable=False)
    password    = db.Column(db.String(123), nullable=False)
    is_verified = db.Column(db.Boolean(1),nullable=False)
    createdAt   = db.Column(db.Date)
    updatedAt   = db.Column(db.Date)

class History(db.Model):
    id = db.Column(db.Integer(), primary_key=True, nullable=False)
    label = db.Column(db.String(15), nullable=False)
    count = db.Column(db.Integer(), nullable=False)
    created_at = db.Column(db.DateTime(), nullable=False, default=db.func.now())
    updated_at = db.Column(
        db.DateTime(), nullable=False, default=db.func.now(), onupdate=db.func.now())


#Registrasi
regParser = reqparse.RequestParser()
regParser.add_argument('firstname', type=str, help='firstname', location='json', required=True)
regParser.add_argument('email', type=str, help='Email', location='json', required=True)
regParser.add_argument('password', type=str, help='Password', location='json', required=True)
regParser.add_argument('confirm_password', type=str, help='confirm password', location='json', required=True)

@api.route('/register')
class Regis(Resource):
    @api.expect(regParser)
    def post(self):
        
        args        = regParser.parse_args()
        firstname   = args['firstname']
        email       = args['email']
        password    = args['password']
        password2  = args['confirm_password']
        is_verified = False
    
        if password != password2:
            return {
                'messege': 'Password tidak cocok'
            }, 400

        user = db.session.execute(db.select(Users).filter_by(email=email)).first()
        if user:
            return "Email sudah terpakai silahkan coba lagi menggunakan email lain"
        # END: Check email existance.

        # BEGIN: Insert new user.
        user          = Users() # Instantiate User object.
        user.firstname = firstname
        user.email    = email
        user.password = generate_password_hash(password)
        user.is_verified = is_verified
        db.session.add(user)
        msg = Message(subject='Verification OTP',sender=os.environ.get("MAIL_USERNAME"),recipients=[user.email])
        token =  random.randrange(10000,99999)
        session['email'] = user.email
        session['token'] = str(token)
        msg.html=render_template(
        'reset_email_template.html', token=token)
        mail.send(msg)
        db.session.commit()
        # END: Insert new user.
        return {'messege': 'Registrasi Berhasil, Cek email anda untuk verifikasi!'}, 201


#Verifikasi
otpparser = reqparse.RequestParser()
otpparser.add_argument('otp', type=str, help='otp', location='json', required=True)
@api.route('/verifikasi')
class Verifikasi(Resource):
    @api.expect(otpparser)
    def post(self):
        args = otpparser.parse_args()
        otp = args['otp']
        if 'token' in session:
            sesion = session['token']
            if otp == sesion:
                email = session['email']
                user = Users.query.filter_by(email=email).first()
                user.is_verified = True
                db.session.commit()
                session.pop('token',None)
                return {'message' : 'Email berhasil diverifikasi'}
            else:
                return {'message' : 'Kode Otp tidak sesuai'}
        else:
            return {'message' : 'Kode Otp tidak sesuai'}

#login
logParser = reqparse.RequestParser()
logParser.add_argument('email', type=str, help='Email', location='json', required=True)
logParser.add_argument('password', type=str, help='Password', location='json', required=True)

SECRET_KEY      = "WhatEverYouWant"
ISSUER          = "myFlaskWebservice"
AUDIENCE_MOBILE = "myMobileApp"

@api.route('/login')
class LogIn(Resource):
    @api.expect(logParser)
    def post(self):
        # BEGIN: Get request parameters.
        args        = logParser.parse_args()
        email       = args['email']
        password    = args['password']
        # END: Get request parameters.

        if not email or not password:
            return {
                'message': 'Silakan isi email dan kata sandi Anda'
            }, 400

        # BEGIN: Check email existance.
        user = db.session.execute(
            db.select(Users).filter_by(email=email)).first()

        if not user:
            return {
                'message': 'Email atau kata sandi salah'
            }, 400
        else:
            user = user[0] # Unpack the array.
        # END: Check email existance.

        # BEGIN: Check password hash.
        if check_password_hash(user.password, password):
            payload = {
                'user_id': user.id,
                'email': user.email,
                'aud': AUDIENCE_MOBILE, # AUDIENCE_WEB
                'iss': ISSUER,
                'iat': datetime.utcnow(),
                'exp': datetime.utcnow() + timedelta(hours = 4)
            }
            token = jwt.encode(payload, SECRET_KEY)
            return {
                'token': token
            }, 200
        else:
            return {
                'message': 'Email atau password salah'
            }, 400
        # END: Check password hash.
def decodetoken(jwtToken):
    decode_result = jwt.decode(
               jwtToken,
               SECRET_KEY,
               audience = [AUDIENCE_MOBILE],
			   issuer = ISSUER,
			   algorithms = ['HS256'],
			   options = {"require":["aud", "iss", "iat", "exp"]}
            )
    return decode_result

authParser = reqparse.RequestParser()
authParser.add_argument('Authorization', type=str, help='Authorization', location='headers', required=True)

@api.route('/user')
class DetailUser(Resource):
       @api.expect(authParser)
       def get(self):
        args = authParser.parse_args()
        bearerAuth  = args['Authorization']
        try:
            jwtToken    = bearerAuth[7:]
            token = decodetoken(jwtToken)
            user =  db.session.execute(db.select(Users).filter_by(email=token['email'])).first()
            user = user[0]
            data = {
                'firstname' : user.firstname,
                'email' : user.email
            }
        except:
            return {
                'message' : 'Token Tidak valid, Silahkan Login Terlebih Dahulu'
            }, 401

        return data, 200
#editpassword
editPasswordParser =  reqparse.RequestParser()
editPasswordParser.add_argument('current_password', type=str, help='current_password',location='json', required=True)
editPasswordParser.add_argument('new_password', type=str, help='new_password',location='json', required=True)
@api.route('/editpassword')
class EditPassword(Resource):
    @api.expect(authParser, editPasswordParser)
    def put(self):
        args = editPasswordParser.parse_args()
        argss = authParser.parse_args()
        bearerAuth  = argss['Authorization']
        cu_password = args['current_password']
        newpassword = args['new_password']
        try:
            jwtToken    = bearerAuth[7:]
            token = decodetoken(jwtToken)
            user = Users.query.filter_by(id=token.get('user_id')).first()
            if check_password_hash(user.password, cu_password):
                user.password = generate_password_hash(newpassword)
                db.session.commit()
            else:
                return {'message' : 'Password Lama Salah'},400
        except:
            return {
                'message' : 'Token Tidak valid, Silahkan Login Terlebih Dahulu'
            }, 401
        return {'message' : 'Password Berhasil Diubah'}, 200

#Edit Users
editParser = reqparse.RequestParser()
editParser.add_argument('firstname', type=str, help='Firstname', location='json', required=True)
editParser.add_argument('Authorization', type=str, help='Authorization', location='headers', required=True)
@api.route('/edituser')
class EditUser(Resource):
       @api.expect(editParser)
       def put(self):
        args = editParser.parse_args()
        bearerAuth  = args['Authorization']
        firstname = args['firstname']
        datenow =  datetime.today().strftime('%Y-%m-%d %H:%M:%S')
        try:
            jwtToken    = bearerAuth[7:]
            token = decodetoken(jwtToken)
            user = Users.query.filter_by(email=token.get('email')).first()
            user.firstname = firstname
            user.updatedAt = datenow
            db.session.commit()
        except:
            return {
                'message' : 'Token Tidak valid, Silahkan Login Terlebih Dahulu'
            }, 401
        return {'message' : 'Update User Suksess'}, 200



face_classifier = cv2.CascadeClassifier('haarcascade_frontalface_default.xml')
classifier = load_model('model.h5')
emotion_labels = ['Angry', 'Disgust', 'Fear', 'Happy', 'Neutral', 'Sad', 'Surprise']

cap = cv2.VideoCapture(1)

running = True

def stop_detection():
    global running
    running = False

def gen_frames():
    counter = 0
    emotions_count = defaultdict(int)  # Menyimpan jumlah deteksi emosi

    while running:
        _, frame = cap.read()
        labels = []
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        faces = face_classifier.detectMultiScale(gray)

        for (x, y, w, h) in faces:
            cv2.rectangle(frame, (x, y), (x+w, y+h), (0, 255, 255), 2)
            roi_gray = gray[y:y+h, x:x+w]
            roi_gray = cv2.resize(roi_gray, (48, 48), interpolation=cv2.INTER_AREA)

            if np.sum([roi_gray]) != 0:
                roi = roi_gray.astype('float') / 255.0
                roi = img_to_array(roi)
                roi = np.expand_dims(roi, axis=0)

                prediction = classifier.predict(roi)[0]
                label = emotion_labels[prediction.argmax()]
                label_position = (x, y)
                cv2.putText(frame, label, label_position, cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 255, 0), 2)

                # ========================================
                # total = History.query.filter_by(label).first()
                # total.count += 1
                # db.session.commit()
                col.insert_one({
                    "label": label,
                })

                # Menghitung jumlah deteksi emosi
                emotions_count[label] += 1

                # Kirim data ke klien melalui server-sent events
                yield f"data: {json.dumps(emotions_count)}\n\n"

            else:
                cv2.putText(frame, 'No Faces', (30, 80), cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 255, 0), 2)

        _, jpeg = cv2.imencode('.jpg', frame)
        frame_bytes = jpeg.tobytes()

        # Simpan gambar setiap 2 detik
        if counter % 20 == 0:
            filename = f'frame_{counter}.jpg'
            path = f'history/{filename}'  # Ganti dengan path folder Anda
            with open(path, 'wb') as f:
                f.write(frame_bytes)

        counter += 1
        yield (b'--frame\r\n'
               b'Content-Type: image/jpeg\r\n\r\n' + frame_bytes + b'\r\n\r\n')
        time.sleep(0.1)  # Tunggu 0.1 detik sebelum mengambil frame berikutnya

        # Print jumlah deteksi emosi setiap 10 detik
        if counter % 200 == 0:
            print(f'Emotion Count: {emotions_count}')



@app.route('/video_feed')
def video_feed():
    #Video streaming route. Put this in the src attribute of an img tag
    return Response(gen_frames(), mimetype='multipart/x-mixed-replace; boundary=frame')

@app.route('/api/history')
def history_count():
    histories = col.find()
    history_list = []
    angry = 0
    disgust = 0
    fear = 0
    happy = 0
    neutral = 0
    sad = 0
    surprise = 0
    for history in histories:
        if history['label'] == "Angry":
            angry += 1
        elif history['label'] == "Disgust":
            disgust += 1
        elif history['label'] == "Fear":
            fear += 1
        elif history['label'] == "Happy":
            happy += 1
        elif history['label'] == "Neutral":
            neutral += 1
        elif history['label'] == "Sad":
            sad += 1
        elif history['label'] == "Surprise":
            surprise += 1

    # angry = col.find({"label": "Angry"})
    # disgust = col.find({"label": "Disgust"})
    # fear = col.find({"label": "Fear"})
    # happy = col.find({"label": "Happy"})
    # neutral = col.find({"label": "Neutral"})
    # sad = col.find({"label": "Sad"})
    # surprise = col.find({"label": "Surprise"})
    # return json.dumps({
    #     "Angry": angry,
    #     "Disgust": disgust,
    #     "Fear": fear,
    #     "Happy": happy,
    #     "Neutral": neutral,
    #     "Sad": sad,
    #     "Surprise": surprise,
    # })
    return {
        "Angry": angry,
        "Disgust": disgust,
        "Fear": fear,
        "Happy": happy,
        "Neutral": neutral,
        "Sad": sad,
        "Surprise": surprise,
    }, 200

@app.route('/realtime')
def real():
    return render_template('index.html')


@app.route('/stop_detection', methods=['POST'])
def handle_stop_detection():
    stop_detection()
    return "Detection stopped"


@app.route('/history')
def history():
    # emotions_count = defaultdict(int)  # Menyimpan jumlah deteksi emosi

    # def update_emotion_count():
    #     while True:
    #         # Dapatkan jumlah deteksi emosi dari generator frames
    #         time.sleep(10)
    #         yield f"data: {json.dumps(emotions_count)}\n\n"

    return Response(gen_frames(), mimetype='text/event-stream')


if __name__ == '__main__':
    # app.run(ssl_context='adhoc', debug=True)
    app.run(host='0.0.0.0' , debug=True)