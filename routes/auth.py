from flask import Blueprint, request, jsonify, session
from src.models.user import db, User, UserProfile, UserType, SubscriptionStatus
from werkzeug.security import generate_password_hash, check_password_hash
import re

auth_bp = Blueprint('auth', __name__)

def validate_email(email):
    pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
    return re.match(pattern, email) is not None

def validate_phone(phone):
    # التحقق من رقم الهاتف العراقي
    pattern = r'^(07[3-9]|075)\d{8}$'
    return re.match(pattern, phone) is not None

@auth_bp.route('/register', methods=['POST'])
def register():
    try:
        data = request.get_json()
        
        # التحقق من البيانات المطلوبة
        required_fields = ['email', 'name', 'user_type']
        for field in required_fields:
            if field not in data or not data[field]:
                return jsonify({'error': f'حقل {field} مطلوب'}), 400
        
        email = data['email'].lower().strip()
        name = data['name'].strip()
        user_type = data['user_type']
        phone = data.get('phone', '').strip()
        
        # التحقق من صحة البيانات
        if not validate_email(email):
            return jsonify({'error': 'البريد الإلكتروني غير صحيح'}), 400
        
        if len(name) < 2:
            return jsonify({'error': 'الاسم يجب أن يكون أكثر من حرفين'}), 400
        
        if user_type not in ['merchant', 'marketer', 'admin']:
            return jsonify({'error': 'نوع المستخدم غير صحيح'}), 400
        
        if phone and not validate_phone(phone):
            return jsonify({'error': 'رقم الهاتف غير صحيح'}), 400
        
        # التحقق من عدم وجود المستخدم
        existing_user = User.query.filter_by(email=email).first()
        if existing_user:
            return jsonify({'error': 'البريد الإلكتروني مستخدم بالفعل'}), 400
        
        # إنشاء المستخدم
        user = User(
            email=email,
            name=name,
            phone=phone
        )
        
        db.session.add(user)
        db.session.flush()  # للحصول على معرف المستخدم
        
        # إنشاء الملف الشخصي
        profile_data = {
            'user_id': user.id,
            'user_type': UserType(user_type),
            'is_verified': user_type == 'admin',
            'subscription_status': SubscriptionStatus.ACTIVE if user_type == 'admin' else SubscriptionStatus.INACTIVE
        }
        
        # إضافة البيانات الإضافية للتاجر
        if user_type == 'merchant':
            profile_data['business_name'] = data.get('business_name', '').strip()
            profile_data['business_type'] = data.get('business_type', '').strip()
        
        # إضافة بيانات الدفع للمسوق
        elif user_type == 'marketer':
            profile_data['payment_method'] = data.get('payment_method', '').strip()
            profile_data['payment_details'] = data.get('payment_details', '').strip()
        
        profile = UserProfile(**profile_data)
        db.session.add(profile)
        
        db.session.commit()
        
        # تسجيل الدخول
        session['user_id'] = user.id
        
        return jsonify({
            'message': 'تم إنشاء الحساب بنجاح',
            'user': {
                'id': user.id,
                'email': user.email,
                'name': user.name,
                'phone': user.phone,
                'user_type': user_type,
                'is_verified': profile.is_verified,
                'subscription_status': profile.subscription_status.value
            }
        }), 201
        
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': f'خطأ في إنشاء الحساب: {str(e)}'}), 500

@auth_bp.route('/login', methods=['POST'])
def login():
    try:
        data = request.get_json()
        
        email = data.get('email', '').lower().strip()
        
        if not email:
            return jsonify({'error': 'البريد الإلكتروني مطلوب'}), 400
        
        user = User.query.filter_by(email=email).first()
        if not user:
            return jsonify({'error': 'المستخدم غير موجود'}), 404
        
        profile = UserProfile.query.filter_by(user_id=user.id).first()
        if not profile:
            return jsonify({'error': 'الملف الشخصي غير موجود'}), 404
        
        if profile.is_banned:
            return jsonify({'error': 'الحساب محظور'}), 403
        
        # تسجيل الدخول
        session['user_id'] = user.id
        
        return jsonify({
            'message': 'تم تسجيل الدخول بنجاح',
            'user': {
                'id': user.id,
                'email': user.email,
                'name': user.name,
                'phone': user.phone,
                'user_type': profile.user_type.value,
                'is_verified': profile.is_verified,
                'subscription_status': profile.subscription_status.value,
                'business_name': profile.business_name,
                'business_type': profile.business_type,
                'payment_method': profile.payment_method,
                'payment_details': profile.payment_details
            }
        }), 200
        
    except Exception as e:
        return jsonify({'error': f'خطأ في تسجيل الدخول: {str(e)}'}), 500

@auth_bp.route('/logout', methods=['POST'])
def logout():
    session.pop('user_id', None)
    return jsonify({'message': 'تم تسجيل الخروج بنجاح'}), 200

@auth_bp.route('/me', methods=['GET'])
def get_current_user():
    try:
        user_id = session.get('user_id')
        if not user_id:
            return jsonify({'error': 'غير مسجل الدخول'}), 401
        
        user = User.query.get(user_id)
        if not user:
            return jsonify({'error': 'المستخدم غير موجود'}), 404
        
        profile = UserProfile.query.filter_by(user_id=user.id).first()
        if not profile:
            return jsonify({'error': 'الملف الشخصي غير موجود'}), 404
        
        return jsonify({
            'user': {
                'id': user.id,
                'email': user.email,
                'name': user.name,
                'phone': user.phone,
                'user_type': profile.user_type.value,
                'is_verified': profile.is_verified,
                'subscription_status': profile.subscription_status.value,
                'business_name': profile.business_name,
                'business_type': profile.business_type,
                'payment_method': profile.payment_method,
                'payment_details': profile.payment_details,
                'completed_orders': profile.completed_orders
            }
        }), 200
        
    except Exception as e:
        return jsonify({'error': f'خطأ في جلب بيانات المستخدم: {str(e)}'}), 500

@auth_bp.route('/update-profile', methods=['PUT'])
def update_profile():
    try:
        user_id = session.get('user_id')
        if not user_id:
            return jsonify({'error': 'غير مسجل الدخول'}), 401
        
        data = request.get_json()
        
        user = User.query.get(user_id)
        profile = UserProfile.query.filter_by(user_id=user_id).first()
        
        if not user or not profile:
            return jsonify({'error': 'المستخدم غير موجود'}), 404
        
        # تحديث بيانات المستخدم
        if 'name' in data:
            user.name = data['name'].strip()
        if 'phone' in data:
            phone = data['phone'].strip()
            if phone and not validate_phone(phone):
                return jsonify({'error': 'رقم الهاتف غير صحيح'}), 400
            user.phone = phone
        
        # تحديث بيانات الملف الشخصي
        if profile.user_type == UserType.MERCHANT:
            if 'business_name' in data:
                profile.business_name = data['business_name'].strip()
            if 'business_type' in data:
                profile.business_type = data['business_type'].strip()
        
        elif profile.user_type == UserType.MARKETER:
            if 'payment_method' in data:
                profile.payment_method = data['payment_method'].strip()
            if 'payment_details' in data:
                profile.payment_details = data['payment_details'].strip()
        
        db.session.commit()
        
        return jsonify({'message': 'تم تحديث الملف الشخصي بنجاح'}), 200
        
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': f'خطأ في تحديث الملف الشخصي: {str(e)}'}), 500

