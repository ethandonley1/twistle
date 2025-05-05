from flask_sqlalchemy import SQLAlchemy
from flask_login import UserMixin
from datetime import datetime
from sqlalchemy.orm import validates

db = SQLAlchemy()

class User(UserMixin, db.Model):
    id = db.Column(db.String(120), primary_key=True)
    name = db.Column(db.String(120), nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    profile_pic = db.Column(db.String(500))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    stats = db.relationship('UserStats', backref='user', uselist=False)
    games = db.relationship('GameResult', backref='user', lazy=True)
    devices = db.relationship('UserDevice', backref='user', lazy=True)

    @classmethod
    def create(cls, id_, name, email, profile_pic):
        user = cls(id=id_, name=name, email=email, profile_pic=profile_pic)
        db.session.add(user)
        db.session.commit()
        return user

    @validates('name')
    def validate_name(self, key, name):
        if not name or len(name.strip()) < 1:
            raise ValueError("Name cannot be empty")
        if len(name) > 20:
            raise ValueError("Name cannot be longer than 20 characters")
        return name.strip()

class UserStats(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.String(120), db.ForeignKey('user.id'), nullable=False)
    games_played = db.Column(db.Integer, default=0, nullable=False)
    total_score = db.Column(db.Integer, default=0, nullable=False)
    total_words_solved = db.Column(db.Integer, default=0, nullable=False)
    best_score = db.Column(db.Integer, default=0, nullable=False)
    avg_score = db.Column(db.Float, default=0.0, nullable=False)
    total_anagrams_found = db.Column(db.Integer, default=0, nullable=False)
    streak = db.Column(db.Integer, default=0, nullable=False)
    last_played = db.Column(db.DateTime, nullable=True)

class GameResult(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.String(120), db.ForeignKey('user.id'), nullable=False)
    game_date = db.Column(db.DateTime, default=datetime.utcnow)
    score = db.Column(db.Integer, nullable=False)
    words_solved = db.Column(db.Integer, nullable=False)
    total_words = db.Column(db.Integer, nullable=False)
    theme = db.Column(db.String(120))
    share_id = db.Column(db.String(8), unique=True)
    time_taken = db.Column(db.Integer)  # Total time in seconds
    anagrams_found = db.Column(db.Integer, default=0)

class UserDevice(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.String(120), db.ForeignKey('user.id'), nullable=False)
    ip_address = db.Column(db.String(45))  # IPv6 addresses can be up to 45 chars
    device_type = db.Column(db.String(20))  # mobile, desktop, tablet
    browser_type = db.Column(db.String(50))  # Chrome, Firefox, Safari, etc.
    last_login = db.Column(db.DateTime, default=datetime.utcnow)
    country = db.Column(db.String(2))  # ISO country code
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    @classmethod
    def create_or_update(cls, user_id, ip_address, device_type, browser_type, country):
        device = cls.query.filter_by(
            user_id=user_id,
            ip_address=ip_address,
            device_type=device_type,
            browser_type=browser_type
        ).first()
        
        if device:
            device.last_login = datetime.utcnow()
        else:
            device = cls(
                user_id=user_id,
                ip_address=ip_address,
                device_type=device_type,
                browser_type=browser_type,
                country=country
            )
            db.session.add(device)
            
        db.session.commit()
        return device
