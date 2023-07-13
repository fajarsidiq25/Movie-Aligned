# from flask import Flask, json, make_response, jsonify, render_template, session,Response
# from flask_restx import Resource, Api, reqparse
# from flask_sqlalchemy import SQLAlchemy
# from flask_cors import CORS
# from werkzeug.security import generate_password_hash, check_password_hash
# from datetime import datetime, timedelta
# import jwt, os, random
# from flask_mail import Mail, Message
# import cv2
# import numpy as np
# from tensorflow.keras.models import model_from_json  
# from tensorflow.keras.preprocessing import image 
# from keras.models import load_model
# from tensorflow.keras.utils import img_to_array
# from collections import defaultdict
# import time


# app = Flask(__name__) 

# face_classifier = cv2.CascadeClassifier('haarcascade_frontalface_default.xml')
# classifier = load_model('model.h5')
# emotion_labels = ['Angry', 'Disgust', 'Fear', 'Happy', 'Neutral', 'Sad', 'Surprise']

# cap = cv2.VideoCapture(1)

# def gen_frames():  # generate frame by frame from camera
#     counter = 0
#     emotions_count = defaultdict(int)  # Menyimpan jumlah deteksi emosi

#     while True:
#         _, frame = cap.read()
#         labels = []
#         gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
#         faces = face_classifier.detectMultiScale(gray)

#         for (x, y, w, h) in faces:
#             cv2.rectangle(frame, (x, y), (x+w, y+h), (0, 255, 255), 2)
#             roi_gray = gray[y:y+h, x:x+w]
#             roi_gray = cv2.resize(roi_gray, (48, 48), interpolation=cv2.INTER_AREA)

#             if np.sum([roi_gray]) != 0:
#                 roi = roi_gray.astype('float') / 255.0
#                 roi = img_to_array(roi)
#                 roi = np.expand_dims(roi, axis=0)

#                 prediction = classifier.predict(roi)[0]
#                 label = emotion_labels[prediction.argmax()]
#                 label_position = (x, y)
#                 cv2.putText(frame, label, label_position, cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 255, 0), 2)

#                 # Menghitung jumlah deteksi emosi
#                 emotions_count[label] += 1

#                 # Kirim data ke klien melalui server-sent events
#                 yield f"data: {json.dumps(emotions_count)}\n\n"

#             else:
#                 cv2.putText(frame, 'No Faces', (30, 80), cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 255, 0), 2)

#         _, jpeg = cv2.imencode('.jpg', frame)
#         frame_bytes = jpeg.tobytes()

#         # Simpan gambar setiap 2 detik
#         if counter % 20 == 0:
#             filename = f'frame_{counter}.jpg'
#             path = f'history/{filename}'  # Ganti dengan path folder Anda
#             with open(path, 'wb') as f:
#                 f.write(frame_bytes)

#         counter += 1
#         yield (b'--frame\r\n'
#                b'Content-Type: image/jpeg\r\n\r\n' + frame_bytes + b'\r\n\r\n')
#         time.sleep(0.1)  # Tunggu 0.1 detik sebelum mengambil frame berikutnya

#         # Print jumlah deteksi emosi setiap 10 detik
#         if counter % 200 == 0:
#             print(f'Emotion Count: {emotions_count}')


# @app.route('/video_feed')
# def video_feed():
#     #Video streaming route. Put this in the src attribute of an img tag
#     return Response(gen_frames(), mimetype='multipart/x-mixed-replace; boundary=frame')


# @app.route('/realtime')
# def real():
#     return render_template('index.html')

# @app.route('/history')
# def history():
#     # emotions_count = defaultdict(int)  # Menyimpan jumlah deteksi emosi

#     # def update_emotion_count():
#     #     while True:
#     #         # Dapatkan jumlah deteksi emosi dari generator frames
#     #         time.sleep(10)
#     #         yield f"data: {json.dumps(emotions_count)}\n\n"

#     return Response(gen_frames(), mimetype='text/event-stream')


    
# # @app.route('/real')
# # def real():
# #     return render_template('index.html')
    
# if __name__ == '__main__':
#     # app.run(ssl_context='adhoc', debug=True)
#     app.run(host='0.0.0.0' , debug=True)


from flask import Flask, json, make_response, jsonify, render_template, session, Response, current_app
from flask_restx import Resource, Api, reqparse
from flask_sqlalchemy import SQLAlchemy
from flask_cors import CORS
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime, timedelta
import jwt
import os
import random
from flask_mail import Mail, Message
import cv2
import numpy as np
from tensorflow.keras.models import model_from_json
from tensorflow.keras.preprocessing import image
from keras.models import load_model
from tensorflow.keras.utils import img_to_array
from collections import defaultdict
import time
import pymysql
pymysql.install_as_MySQLdb()


app = Flask(__name__)
app.config['SQLALCHEMY_DATABASE_URI'] = "mysql://root:@127.0.0.1:3306/flask_capstone"  # Ganti 'database_uri' dengan URI database Anda
db = SQLAlchemy(app)
face_classifier = cv2.CascadeClassifier('haarcascade_frontalface_default.xml')
classifier = load_model('model.h5')
emotion_labels = ['Angry', 'Disgust', 'Fear', 'Happy', 'Neutral', 'Sad', 'Surprise']

cap = cv2.VideoCapture(1)


class History(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    emotion_label = db.Column(db.String(50))
    count = db.Column(db.Integer)
    timestamp = db.Column(db.DateTime, default=datetime.utcnow)


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
    return Response(gen_frames(), mimetype='multipart/x-mixed-replace; boundary=frame')


@app.route('/realtime')
def real():
    return render_template('index.html')


@app.route('/history')
def history():
    return Response(gen_frames(), mimetype='text/event-stream')


if __name__ == '__main__':
    app.run(host='0.0.0.0', debug=True)
