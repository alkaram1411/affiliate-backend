from flask import Blueprint, request, jsonify, session
from src.models.user import db, User, UserProfile, Product, Order, Notification, UserType, SubscriptionStatus, NotificationType
from sqlalchemy import func, and_
from datetime import datetime, timedelta

admin_bp = Blueprint('admin', __name__)

def require_admin():
    user_id = session.get('user_id')
    if not user_id:
        return None, jsonify({'error': 'غير مسجل الدخول'}), 401
    
    user = User.query.get(user_id)
    if not user:
        return None, jsonify({'error': 'المستخدم غير موجود'}), 404
    
    profile = UserProfile.query.filter_by(user_id=user_id).first()
    if not profile:
        return None, jsonify({'error': 'الملف الشخصي غير موجود'}), 404
    
    if profile.user_type != UserType.ADMIN:
        return None, jsonify({'error': 'هذه الخدمة للمديرين فقط'}), 403
    
    return {'user': user, 'profile': profile}, None, None

@admin_bp.route('/dashboard', methods=['GET'])
def get_admin_dashboard():
    try:
        auth_result, error_response, status_code = require_admin()
        if error_response:
            return error_response, status_code
        
        # إحصائيات عامة
        total_users = User.query.count()
        total_merchants = UserProfile.query.filter_by(user_type=UserType.MERCHANT).count()
        total_marketers = UserProfile.query.filter_by(user_type=UserType.MARKETER).count()
        total_products = Product.query.count()
        active_products = Product.query.filter_by(is_active=True).count()
        total_orders = Order.query.count()
        
        # إحصائيات الطلبات حسب الحالة
        orders_by_status = db.session.query(
            Order.status, func.count(Order.id)
        ).group_by(Order.status).all()
        
        # إحصائيات الاشتراكات
        active_subscriptions = UserProfile.query.filter_by(subscription_status=SubscriptionStatus.ACTIVE).count()
        inactive_subscriptions = UserProfile.query.filter_by(subscription_status=SubscriptionStatus.INACTIVE).count()
        
        # المستخدمون الجدد في آخر 30 يوم
        thirty_days_ago = datetime.utcnow() - timedelta(days=30)
        new_users_last_month = User.query.filter(User.created_at >= thirty_days_ago).count()
        
        # الطلبات في آخر 30 يوم
        new_orders_last_month = Order.query.filter(Order.created_at >= thirty_days_ago).count()
        
        return jsonify({
            'total_users': total_users,
            'total_merchants': total_merchants,
            'total_marketers': total_marketers,
            'total_products': total_products,
            'active_products': active_products,
            'total_orders': total_orders,
            'orders_by_status': {status.value: count for status, count in orders_by_status},
            'active_subscriptions': active_subscriptions,
            'inactive_subscriptions': inactive_subscriptions,
            'new_users_last_month': new_users_last_month,
            'new_orders_last_month': new_orders_last_month
        }), 200
        
    except Exception as e:
        return jsonify({'error': f'خطأ في جلب لوحة التحكم: {str(e)}'}), 500

@admin_bp.route('/users', methods=['GET'])
def get_all_users():
    try:
        auth_result, error_response, status_code = require_admin()
        if error_response:
            return error_response, status_code
        
        page = request.args.get('page', 1, type=int)
        per_page = request.args.get('per_page', 20, type=int)
        user_type = request.args.get('user_type')
        search = request.args.get('search', '').strip()
        
        # بناء الاستعلام
        query = db.session.query(User, UserProfile).join(
            UserProfile, User.id == UserProfile.user_id
        )
        
        # تصفية حسب نوع المستخدم
        if user_type and user_type in ['merchant', 'marketer', 'admin']:
            query = query.filter(UserProfile.user_type == UserType(user_type))
        
        # البحث في الاسم أو البريد الإلكتروني
        if search:
            query = query.filter(
                User.name.contains(search) | User.email.contains(search)
            )
        
        # ترقيم الصفحات
        users = query.order_by(User.created_at.desc()).paginate(
            page=page, per_page=per_page, error_out=False
        )
        
        users_data = []
        for user, profile in users.items:
            users_data.append({
                'id': user.id,
                'email': user.email,
                'name': user.name,
                'phone': user.phone,
                'user_type': profile.user_type.value,
                'business_name': profile.business_name,
                'business_type': profile.business_type,
                'is_verified': profile.is_verified,
                'completed_orders': profile.completed_orders,
                'subscription_status': profile.subscription_status.value,
                'is_banned': profile.is_banned,
                'created_at': user.created_at.isoformat()
            })
        
        return jsonify({
            'users': users_data,
            'pagination': {
                'page': users.page,
                'pages': users.pages,
                'per_page': users.per_page,
                'total': users.total,
                'has_next': users.has_next,
                'has_prev': users.has_prev
            }
        }), 200
        
    except Exception as e:
        return jsonify({'error': f'خطأ في جلب المستخدمين: {str(e)}'}), 500

@admin_bp.route('/users/<int:user_id>/ban', methods=['PUT'])
def ban_user(user_id):
    try:
        auth_result, error_response, status_code = require_admin()
        if error_response:
            return error_response, status_code
        
        profile = UserProfile.query.filter_by(user_id=user_id).first()
        if not profile:
            return jsonify({'error': 'المستخدم غير موجود'}), 404
        
        if profile.user_type == UserType.ADMIN:
            return jsonify({'error': 'لا يمكن حظر المديرين'}), 400
        
        profile.is_banned = True
        profile.subscription_status = SubscriptionStatus.INACTIVE
        
        # إرسال إشعار للمستخدم
        notification = Notification(
            user_id=user_id,
            title='تم حظر الحساب',
            message='تم حظر حسابك من قبل الإدارة',
            type=NotificationType.GENERAL,
            is_read=False
        )
        
        db.session.add(notification)
        db.session.commit()
        
        return jsonify({'message': 'تم حظر المستخدم بنجاح'}), 200
        
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': f'خطأ في حظر المستخدم: {str(e)}'}), 500

@admin_bp.route('/users/<int:user_id>/unban', methods=['PUT'])
def unban_user(user_id):
    try:
        auth_result, error_response, status_code = require_admin()
        if error_response:
            return error_response, status_code
        
        profile = UserProfile.query.filter_by(user_id=user_id).first()
        if not profile:
            return jsonify({'error': 'المستخدم غير موجود'}), 404
        
        profile.is_banned = False
        
        # إرسال إشعار للمستخدم
        notification = Notification(
            user_id=user_id,
            title='تم إلغاء حظر الحساب',
            message='تم إلغاء حظر حسابك من قبل الإدارة',
            type=NotificationType.GENERAL,
            is_read=False
        )
        
        db.session.add(notification)
        db.session.commit()
        
        return jsonify({'message': 'تم إلغاء حظر المستخدم بنجاح'}), 200
        
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': f'خطأ في إلغاء حظر المستخدم: {str(e)}'}), 500

@admin_bp.route('/users/<int:user_id>/verify', methods=['PUT'])
def verify_user(user_id):
    try:
        auth_result, error_response, status_code = require_admin()
        if error_response:
            return error_response, status_code
        
        profile = UserProfile.query.filter_by(user_id=user_id).first()
        if not profile:
            return jsonify({'error': 'المستخدم غير موجود'}), 404
        
        profile.is_verified = True
        
        # إرسال إشعار للمستخدم
        notification = Notification(
            user_id=user_id,
            title='تم توثيق الحساب',
            message='تم توثيق حسابك من قبل الإدارة',
            type=NotificationType.GENERAL,
            is_read=False
        )
        
        db.session.add(notification)
        db.session.commit()
        
        return jsonify({'message': 'تم توثيق المستخدم بنجاح'}), 200
        
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': f'خطأ في توثيق المستخدم: {str(e)}'}), 500

@admin_bp.route('/users/<int:user_id>/subscription', methods=['PUT'])
def update_user_subscription(user_id):
    try:
        auth_result, error_response, status_code = require_admin()
        if error_response:
            return error_response, status_code
        
        data = request.get_json()
        status = data.get('status')
        
        if status not in ['active', 'inactive', 'expired', 'cancelled']:
            return jsonify({'error': 'حالة الاشتراك غير صحيحة'}), 400
        
        profile = UserProfile.query.filter_by(user_id=user_id).first()
        if not profile:
            return jsonify({'error': 'المستخدم غير موجود'}), 404
        
        profile.subscription_status = SubscriptionStatus(status)
        
        # تحديد تاريخ انتهاء الاشتراك إذا كان مفعل
        if status == 'active':
            expiry_days = data.get('expiry_days', 30)
            profile.subscription_expiry = datetime.utcnow() + timedelta(days=expiry_days)
        
        # إرسال إشعار للمستخدم
        status_messages = {
            'active': 'تم تفعيل اشتراكك',
            'inactive': 'تم إلغاء تفعيل اشتراكك',
            'expired': 'انتهت صلاحية اشتراكك',
            'cancelled': 'تم إلغاء اشتراكك'
        }
        
        notification = Notification(
            user_id=user_id,
            title='تحديث الاشتراك',
            message=status_messages[status],
            type=NotificationType.GENERAL,
            is_read=False
        )
        
        db.session.add(notification)
        db.session.commit()
        
        return jsonify({'message': 'تم تحديث حالة الاشتراك بنجاح'}), 200
        
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': f'خطأ في تحديث الاشتراك: {str(e)}'}), 500

@admin_bp.route('/products', methods=['GET'])
def get_all_products():
    try:
        auth_result, error_response, status_code = require_admin()
        if error_response:
            return error_response, status_code
        
        page = request.args.get('page', 1, type=int)
        per_page = request.args.get('per_page', 20, type=int)
        search = request.args.get('search', '').strip()
        
        # بناء الاستعلام
        query = db.session.query(Product, UserProfile).join(
            UserProfile, Product.merchant_id == UserProfile.user_id
        )
        
        # البحث في اسم المنتج أو اسم التاجر
        if search:
            query = query.join(User, UserProfile.user_id == User.id).filter(
                Product.name.contains(search) | User.name.contains(search)
            )
        
        # ترقيم الصفحات
        products = query.order_by(Product.created_at.desc()).paginate(
            page=page, per_page=per_page, error_out=False
        )
        
        products_data = []
        for product, merchant_profile in products.items:
            merchant = User.query.get(merchant_profile.user_id)
            products_data.append({
                'id': product.id,
                'name': product.name,
                'description': product.description,
                'image_url': product.image_url,
                'base_price': product.base_price,
                'min_marketer_profit': product.min_marketer_profit,
                'suggested_price': product.suggested_price,
                'category': product.category,
                'is_active': product.is_active,
                'merchant': {
                    'id': merchant.id,
                    'name': merchant.name,
                    'business_name': merchant_profile.business_name,
                    'is_verified': merchant_profile.is_verified
                },
                'created_at': product.created_at.isoformat()
            })
        
        return jsonify({
            'products': products_data,
            'pagination': {
                'page': products.page,
                'pages': products.pages,
                'per_page': products.per_page,
                'total': products.total,
                'has_next': products.has_next,
                'has_prev': products.has_prev
            }
        }), 200
        
    except Exception as e:
        return jsonify({'error': f'خطأ في جلب المنتجات: {str(e)}'}), 500

@admin_bp.route('/orders', methods=['GET'])
def get_all_orders():
    try:
        auth_result, error_response, status_code = require_admin()
        if error_response:
            return error_response, status_code
        
        page = request.args.get('page', 1, type=int)
        per_page = request.args.get('per_page', 20, type=int)
        status = request.args.get('status')
        
        # بناء الاستعلام
        query = db.session.query(Order, Product, UserProfile, UserProfile).join(
            Product, Order.product_id == Product.id
        ).join(
            UserProfile, Order.merchant_id == UserProfile.user_id
        ).join(
            UserProfile, Order.marketer_id == UserProfile.user_id
        )
        
        # تصفية حسب الحالة
        if status:
            query = query.filter(Order.status == status)
        
        # ترقيم الصفحات
        orders = query.order_by(Order.created_at.desc()).paginate(
            page=page, per_page=per_page, error_out=False
        )
        
        orders_data = []
        for order, product, merchant_profile, marketer_profile in orders.items:
            merchant = User.query.get(merchant_profile.user_id)
            marketer = User.query.get(marketer_profile.user_id)
            
            orders_data.append({
                'id': order.id,
                'product': {
                    'id': product.id,
                    'name': product.name
                },
                'merchant': {
                    'id': merchant.id,
                    'name': merchant.name,
                    'business_name': merchant_profile.business_name
                },
                'marketer': {
                    'id': marketer.id,
                    'name': marketer.name
                },
                'customer_name': order.customer_name,
                'customer_phone': order.customer_phone,
                'sale_price': order.sale_price,
                'quantity': order.quantity,
                'marketer_profit': order.marketer_profit,
                'status': order.status.value,
                'payment_status': order.payment_status.value,
                'created_at': order.created_at.isoformat()
            })
        
        return jsonify({
            'orders': orders_data,
            'pagination': {
                'page': orders.page,
                'pages': orders.pages,
                'per_page': orders.per_page,
                'total': orders.total,
                'has_next': orders.has_next,
                'has_prev': orders.has_prev
            }
        }), 200
        
    except Exception as e:
        return jsonify({'error': f'خطأ في جلب الطلبات: {str(e)}'}), 500

@admin_bp.route('/broadcast', methods=['POST'])
def broadcast_notification():
    try:
        auth_result, error_response, status_code = require_admin()
        if error_response:
            return error_response, status_code
        
        data = request.get_json()
        
        title = data.get('title', '').strip()
        message = data.get('message', '').strip()
        user_type = data.get('user_type')  # all, merchant, marketer
        
        if not title or not message:
            return jsonify({'error': 'العنوان والرسالة مطلوبان'}), 400
        
        # تحديد المستخدمين المستهدفين
        if user_type == 'all':
            users = User.query.all()
        elif user_type in ['merchant', 'marketer']:
            user_profiles = UserProfile.query.filter_by(user_type=UserType(user_type)).all()
            users = [User.query.get(profile.user_id) for profile in user_profiles]
        else:
            return jsonify({'error': 'نوع المستخدم غير صحيح'}), 400
        
        # إرسال الإشعار لجميع المستخدمين المستهدفين
        notifications = []
        for user in users:
            notification = Notification(
                user_id=user.id,
                title=title,
                message=message,
                type=NotificationType.GENERAL,
                is_read=False
            )
            notifications.append(notification)
        
        db.session.add_all(notifications)
        db.session.commit()
        
        return jsonify({
            'message': f'تم إرسال الإشعار إلى {len(notifications)} مستخدم'
        }), 200
        
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': f'خطأ في إرسال الإشعار: {str(e)}'}), 500

