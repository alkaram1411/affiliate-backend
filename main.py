import os
from flask import Flask, send_from_directory
from flask_cors import CORS

from models.user import db
from routes.auth import auth_bp
from routes.products import products_bp
from routes.orders import orders_bp
from routes.notifications import notifications_bp
from routes.admin import admin_bp

app = Flask(__name__, static_folder=os.path.join(os.path.dirname(__file__), 'static'))
app.config['SECRET_KEY'] = 'asdf#FGSgvasgf$5$WGT'

# CORS للسماح للفرونت اند يتواصل مع الباك
CORS(app, supports_credentials=True)

# قاعدة البيانات SQLite
BASE_DIR = os.path.abspath(os.path.dirname(__file__))
db_path = os.path.join(BASE_DIR, 'app.db')
app.config['SQLALCHEMY_DATABASE_URI'] = f'sqlite:///{db_path}'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db.init_app(app)

# إنشاء الجداول
with app.app_context():
    db.create_all()

# مسارات API
app.register_blueprint(auth_bp, url_prefix='/api/auth')
app.register_blueprint(products_bp, url_prefix='/api/products')
app.register_blueprint(orders_bp, url_prefix='/api/orders')
app.register_blueprint(notifications_bp, url_prefix='/api/notifications')
app.register_blueprint(admin_bp, url_prefix='/api/admin')

# مسار للتحقق من الصحة
@app.route('/api/health', methods=['GET'])
def health_check():
    return {'status': 'ok', 'message': 'خادم منصة الأفلييت العربية يعمل بنجاح'}, 200

# مسار عرض ملفات React
@app.route('/', defaults={'path': ''})
@app.route('/<path:path>')
def serve(path):
    static_folder_path = app.static_folder
    if path != "" and os.path.exists(os.path.join(static_folder_path, path)):
        return send_from_directory(static_folder_path, path)
    else:
        index_path = os.path.join(static_folder_path, 'index.html')
        if os.path.exists(index_path):
            return send_from_directory(static_folder_path, 'index.html')
        else:
            return "index.html not found", 404

# نقطة التشغيل
if __name__ == '__main__':
    port = int(os.environ.get("PORT", 10000))  # Render يستخدم PORT من environment
    app.run(host='0.0.0.0', port=port)
