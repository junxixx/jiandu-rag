from datetime import date, datetime
from werkzeug.security import generate_password_hash, check_password_hash

from app.extensions import db


class User(db.Model):
    __tablename__ = "users"

    id = db.Column(db.BigInteger, primary_key=True, autoincrement=True)
    username = db.Column(db.String(64), unique=True, nullable=False, index=True)
    email = db.Column(db.String(128), unique=True, nullable=False)
    password_hash = db.Column(db.String(256), nullable=False)
    nickname = db.Column(db.String(64), nullable=False, default="青声同好")
    avatar_url = db.Column(db.String(512), nullable=True)
    points = db.Column(db.Integer, nullable=False, default=0)
    invite_code = db.Column(db.String(16), unique=True, nullable=True, index=True)
    referred_by_user_id = db.Column(db.BigInteger, db.ForeignKey("users.id"), nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    def set_password(self, raw: str) -> None:
        self.password_hash = generate_password_hash(raw)

    def check_password(self, raw: str) -> bool:
        return check_password_hash(self.password_hash, raw)


class Topic(db.Model):
    __tablename__ = "topics"

    id = db.Column(db.BigInteger, primary_key=True, autoincrement=True)
    name = db.Column(db.String(64), unique=True, nullable=False)
    description = db.Column(db.String(512), nullable=True)
    post_count = db.Column(db.Integer, nullable=False, default=0)
    hot = db.Column(db.Integer, nullable=False, default=0)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)


class BambooSlip(db.Model):
    __tablename__ = "bamboo_slips"

    id = db.Column(db.BigInteger, primary_key=True, autoincrement=True)
    code = db.Column(db.String(32), unique=True, nullable=False)
    title = db.Column(db.String(256), nullable=False)
    image_url = db.Column(db.String(512), nullable=True)
    transcription = db.Column(db.Text, nullable=False)
    vernacular = db.Column(db.Text, nullable=False)
    site_name = db.Column(db.String(128), nullable=True)
    era = db.Column(db.String(64), nullable=True)
    tags = db.Column(db.String(512), nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)


class DailySlip(db.Model):
    __tablename__ = "daily_slips"

    id = db.Column(db.BigInteger, primary_key=True, autoincrement=True)
    slip_id = db.Column(db.BigInteger, db.ForeignKey("bamboo_slips.id"), nullable=False)
    feature_date = db.Column(db.Date, nullable=False, index=True)
    quiz_question = db.Column(db.String(512), nullable=False)
    quiz_options = db.Column(db.JSON, nullable=False)
    correct_index = db.Column(db.SmallInteger, nullable=False)
    fun_fact = db.Column(db.Text, nullable=True)
    quizzes_json = db.Column(db.JSON, nullable=True)

    slip = db.relationship("BambooSlip", backref="daily_entries")


class UserQuizAttempt(db.Model):
    __tablename__ = "user_quiz_attempts"

    id = db.Column(db.BigInteger, primary_key=True, autoincrement=True)
    user_id = db.Column(db.BigInteger, db.ForeignKey("users.id"), nullable=False)
    daily_slip_id = db.Column(db.BigInteger, db.ForeignKey("daily_slips.id"), nullable=False)
    choice_index = db.Column(db.SmallInteger, nullable=False)
    quiz_index = db.Column(db.SmallInteger, nullable=False, default=0)
    is_correct = db.Column(db.Boolean, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)


class UserCheckin(db.Model):
    __tablename__ = "user_checkins"

    id = db.Column(db.BigInteger, primary_key=True, autoincrement=True)
    user_id = db.Column(db.BigInteger, db.ForeignKey("users.id"), nullable=False)
    checkin_date = db.Column(db.Date, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    __table_args__ = (db.UniqueConstraint("user_id", "checkin_date", name="uq_user_checkin_day"),)


class UserSlipProgress(db.Model):
    __tablename__ = "user_slip_progress"

    id = db.Column(db.BigInteger, primary_key=True, autoincrement=True)
    user_id = db.Column(db.BigInteger, db.ForeignKey("users.id"), nullable=False)
    slip_id = db.Column(db.BigInteger, db.ForeignKey("bamboo_slips.id"), nullable=False)
    read_at = db.Column(db.DateTime, default=datetime.utcnow)


class Post(db.Model):
    __tablename__ = "posts"

    id = db.Column(db.BigInteger, primary_key=True, autoincrement=True)
    user_id = db.Column(db.BigInteger, db.ForeignKey("users.id"), nullable=False)
    topic_id = db.Column(db.BigInteger, db.ForeignKey("topics.id"), nullable=True, index=True)
    title = db.Column(db.String(256), nullable=False)
    content = db.Column(db.Text, nullable=False)
    ai_summary = db.Column(db.Text, nullable=True)
    likes_count = db.Column(db.Integer, nullable=False, default=0)
    status = db.Column(db.String(16), nullable=False, default="published", index=True)
    risk_score = db.Column(db.Float, nullable=True)
    moderation_labels = db.Column(db.JSON, nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, index=True)

    author = db.relationship("User", backref="posts")
    topic = db.relationship("Topic", backref="posts")


class Comment(db.Model):
    __tablename__ = "comments"

    id = db.Column(db.BigInteger, primary_key=True, autoincrement=True)
    post_id = db.Column(db.BigInteger, db.ForeignKey("posts.id"), nullable=False)
    user_id = db.Column(db.BigInteger, db.ForeignKey("users.id"), nullable=False)
    content = db.Column(db.Text, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    author = db.relationship("User", backref="comments")


class PostLike(db.Model):
    __tablename__ = "post_likes"

    id = db.Column(db.BigInteger, primary_key=True, autoincrement=True)
    post_id = db.Column(db.BigInteger, db.ForeignKey("posts.id"), nullable=False)
    user_id = db.Column(db.BigInteger, db.ForeignKey("users.id"), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    __table_args__ = (db.UniqueConstraint("post_id", "user_id", name="uq_post_user_like"),)


class TaskTemplate(db.Model):
    __tablename__ = "task_templates"

    id = db.Column(db.BigInteger, primary_key=True, autoincrement=True)
    code = db.Column(db.String(64), unique=True, nullable=False)
    title = db.Column(db.String(128), nullable=False)
    points_reward = db.Column(db.Integer, nullable=False, default=5)


class UserTaskLog(db.Model):
    __tablename__ = "user_task_logs"

    id = db.Column(db.BigInteger, primary_key=True, autoincrement=True)
    user_id = db.Column(db.BigInteger, db.ForeignKey("users.id"), nullable=False)
    task_code = db.Column(db.String(64), nullable=False)
    log_date = db.Column(db.Date, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    __table_args__ = (db.UniqueConstraint("user_id", "task_code", "log_date", name="uq_user_task_day"),)


class ChatSession(db.Model):
    __tablename__ = "chat_sessions"

    id = db.Column(db.BigInteger, primary_key=True, autoincrement=True)
    user_id = db.Column(db.BigInteger, db.ForeignKey("users.id"), nullable=False)
    role_key = db.Column(db.String(64), nullable=False, default="li_gan")
    title = db.Column(db.String(128), nullable=True)
    chat_mode = db.Column(db.String(16), nullable=False, default="single")
    group_roles_json = db.Column(db.JSON, nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)


class ChatMessage(db.Model):
    __tablename__ = "chat_messages"

    id = db.Column(db.BigInteger, primary_key=True, autoincrement=True)
    session_id = db.Column(db.BigInteger, db.ForeignKey("chat_sessions.id"), nullable=False)
    role = db.Column(db.String(16), nullable=False)
    content = db.Column(db.Text, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)


class Badge(db.Model):
    __tablename__ = "badges"

    id = db.Column(db.BigInteger, primary_key=True, autoincrement=True)
    code = db.Column(db.String(64), unique=True, nullable=False)
    title = db.Column(db.String(128), nullable=False)
    description = db.Column(db.String(512), nullable=False)
    icon = db.Column(db.String(64), nullable=True)


class UserBadge(db.Model):
    __tablename__ = "user_badges"

    id = db.Column(db.BigInteger, primary_key=True, autoincrement=True)
    user_id = db.Column(db.BigInteger, db.ForeignKey("users.id"), nullable=False)
    badge_id = db.Column(db.BigInteger, db.ForeignKey("badges.id"), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    badge = db.relationship("Badge", backref="holders")

    __table_args__ = (db.UniqueConstraint("user_id", "badge_id", name="uq_user_badge"),)


class SiteKV(db.Model):
    __tablename__ = "site_kv"

    key = db.Column(db.String(64), primary_key=True)
    value = db.Column(db.Text, nullable=False)


class AnalyticsEvent(db.Model):
    __tablename__ = "analytics_events"

    id = db.Column(db.BigInteger, primary_key=True, autoincrement=True)
    event_type = db.Column(db.String(64), nullable=False, index=True)
    user_id = db.Column(db.BigInteger, nullable=True, index=True)
    path = db.Column(db.String(512), nullable=True)
    meta = db.Column(db.JSON, nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
