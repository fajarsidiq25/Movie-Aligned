from main import db, History
from main import emotion_labels

def db_init():
    for label in emotion_labels:
        print(label)
        history = History()
        history.label = label
        history.count = 0
        db.session.add(history)
        db.session.commit()

if __name__ == "__main__":
    db.drop_all()
    db.create_all()
    db_init()
    db.session.close()
