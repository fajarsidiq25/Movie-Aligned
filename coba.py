from flask import Flask, make_response, jsonify, render_template, session,Response, json
import requests
from flask_restx import Resource, Api, reqparse
from flask_sqlalchemy import SQLAlchemy
from flask_cors import CORS
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime, timedelta
import jwt, os, random
from flask_mail import Mail, Message
import cv2
import numpy as np
import pymysql
pymysql.install_as_MySQLdb()
from tensorflow.keras.models import model_from_json  
from tensorflow.keras.preprocessing import image 
from keras.models import load_model
from tensorflow.keras.utils import img_to_array
from collections import defaultdict
import time

app = Flask(__name__) 
api = Api(app)        
CORS(app)

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
    id = db.Column(db.Integer, primary_key=True)
    emotion_label = db.Column(db.String(50))
    count = db.Column(db.Integer)
    timestamp = db.Column(db.DateTime, default=datetime.utcnow)


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
       
# ============================================================================== #

# Create a connection to the MySQL database
dba = pymysql.connect(
    host="localhost",
    user="root",
    password="",
    database="flask_capstone"
)

# Create a cursor object to execute SQL queries
cursor = dba.cursor()

face_classifier = cv2.CascadeClassifier('haarcascade_frontalface_default.xml')
classifier = load_model('model.h5')
emotion_labels = ['Angry', 'Disgust', 'Fear', 'Happy', 'Neutral', 'Sad', 'Surprise']

cap = cv2.VideoCapture(2)


@app.before_request
def before_request():
    db.session.rollback()  # Rollback sesi sebelum setiap permintaan
    app.logger.debug('Request context initialized.')


def gen_frames():
    counter = 0
    emotions_count = defaultdict(int)

    while True:
        _, frame = cap.read()
        labels = []
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        faces = face_classifier.detectMultiScale(gray)

        for (x, y, w, h) in faces:
            cv2.rectangle(frame, (x, y), (x + w, y + h), (0, 255, 255), 2)
            roi_gray = gray[y:y + h, x:x + w]
            roi_gray = cv2.resize(roi_gray, (48, 48), interpolation=cv2.INTER_AREA)

            if np.sum([roi_gray]) != 0:
                roi = roi_gray.astype('float') / 255.0
                roi = img_to_array(roi)
                roi = np.expand_dims(roi, axis=0)

                prediction = classifier.predict(roi)[0]
                label = emotion_labels[prediction.argmax()]
                label_position = (x, y)
                cv2.putText(frame, label, label_position, cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 255, 0), 2)

                emotions_count[label] += 1

                history_data = History(emotion_label=label, count=emotions_count[label])
                with app.app_context():
                    db.session.add(history_data)
                    db.session.commit()

                yield f"data: {json.dumps(emotions_count)}\n\n"
            else:
                cv2.putText(frame, 'No Faces', (30, 80), cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 255, 0), 2)

        _, jpeg = cv2.imencode('.jpg', frame)
        frame_bytes = jpeg.tobytes()

        yield (b'--frame\r\n'
               b'Content-Type: image/jpeg\r\n\r\n' + frame_bytes + b'\r\n\r\n')
        time.sleep(0.1)

        if counter % 200 == 0:
            print(f'Emotion Count: {emotions_count}')
        counter += 1




@app.route('/video_feed')
def video_feed():
    # Video streaming route. Put this in the src attribute of an img tag
    return Response(gen_frames(), mimetype='multipart/x-mixed-replace; boundary=frame')


@app.route('/realtime')
def real():
    return render_template('index.html')


@api.route('/history')
class get_movies(Resource):
    def get(self):
        cursor = dba.cursor()
        query = "SELECT id, emotion_label, count, timestamp FROM history"
        cursor.execute(query)
        movies = cursor.fetchall()

        movie_data = []
        for movie in movies:
            emotion_id, emotion_label, count, timestamp = movie
            movie_data.append({
                'id': emotion_id,
                'emotion_label': emotion_label,
                'count': str(count),
                'timestamp': str(timestamp)
            })

        cursor.close()
        return movie_data


if __name__ == '__main__':
    app.run(host='0.0.0.0', debug=True)