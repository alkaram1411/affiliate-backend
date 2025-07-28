from flask import Blueprint, request, jsonify, session
from src.models.user import db, User, UserProfile, Notification, Order, Product
from sqlalchemy import and_

notifications_bp = Blueprint('notifications', __name__)

def require_auth():
    user_id = session.get('user_id')
    if not user_id:
        return None, jsonify({'error': 'غير مسجل الدخول'}), 401
    
    user = User.query.get(user_id)
    if not user:
        return None, jsonify({'error': 'المستخدم غير موجود'}), 404
    
    profile = UserProfile.query.filter_by(user_id=user_id).first()
    if not profile:
        return None, jsonify({'error': 'الملف الشخصي غير موجود'}), 404
    
    return {'user': user, 'profile': profile}, None, None

@notifications_bp.route('/', methods=['GET'])
def get_notifications():
    try:
        auth_result, error_response, status_code = require_auth()
        if error_response:
            return error_response, status_code
        
        user = auth_result['user']
        
        # جلب الإشعارات مع معلومات الطلب المرتبط إن وجد
        notifications = db.session.query(Notification).outerjoin(
            Order, Notification.related_order_id == Order.id
        ).outerjoin(
            Product, Order.product_id == Product.id
        ).filter(Notification.user_id == user.id).order_by(
            Notification.created_at.desc()
        ).all()
        
        notifications_data = []
        for notification in notifications:
            notification_data = {
                'id': notification.id,
                'title': notification.title,
                'message': notification.message,
                'type': notification.type.value,
                'is_read': notification.is_read,
                'created_at': notification.created_at.isoformat(),
                'related_order': None
            }
            
            # إضافة معلومات الطلب المرتبط إن وجد
            if notification.related_order_id:
                order = Order.query.get(notification.related_order_id)
                if order:
                    product = Product.query.get(order.product_id)
                    notification_data['related_order'] = {
                        'id': order.id,
                        'product_name': product.name if product else 'منتج محذوف',
                        'customer_name': order.customer_name,
                        'status': order.status.value,
                        'payment_status': order.payment_status.value
                    }
            
            notifications_data.append(notification_data)
        
        return jsonify({'notifications': notifications_data}), 200
        
    except Exception as e:
        return jsonify({'error': f'خطأ في جلب الإشعارات: {str(e)}'}), 500

@notifications_bp.route('/unread-count', methods=['GET'])
def get_unread_count():
    try:
        auth_result, error_response, status_code = require_auth()
        if error_response:
            return error_response, status_code
        
        user = auth_result['user']
        
        unread_count = Notification.query.filter(
            and_(Notification.user_id == user.id, Notification.is_read == False)
        ).count()
        
        return jsonify({'unread_count': unread_count}), 200
        
    except Exception as e:
        return jsonify({'error': f'خطأ في جلب عدد الإشعارات غير المقروءة: {str(e)}'}), 500

@notifications_bp.route('/<int:notification_id>/mark-read', methods=['PUT'])
def mark_notification_read(notification_id):
    try:
        auth_result, error_response, status_code = require_auth()
        if error_response:
            return error_response, status_code
        
        user = auth_result['user']
        
        notification = Notification.query.get(notification_id)
        if not notification:
            return jsonify({'error': 'الإشعار غير موجود'}), 404
        
        if notification.user_id != user.id:
            return jsonify({'error': 'غير مسموح لك بتعديل هذا الإشعار'}), 403
        
        notification.is_read = True
        db.session.commit()
        
        return jsonify({'message': 'تم تحديد الإشعار كمقروء'}), 200
        
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': f'خطأ في تحديث الإشعار: {str(e)}'}), 500

@notifications_bp.route('/mark-all-read', methods=['PUT'])
def mark_all_notifications_read():
    try:
        auth_result, error_response, status_code = require_auth()
        if error_response:
            return error_response, status_code
        
        user = auth_result['user']
        
        # تحديث جميع الإشعارات غير المقروءة
        Notification.query.filter(
            and_(Notification.user_id == user.id, Notification.is_read == False)
        ).update({'is_read': True})
        
        db.session.commit()
        
        return jsonify({'message': 'تم تحديد جميع الإشعارات كمقروءة'}), 200
        
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': f'خطأ في تحديث الإشعارات: {str(e)}'}), 500

@notifications_bp.route('/<int:notification_id>', methods=['DELETE'])
def delete_notification(notification_id):
    try:
        auth_result, error_response, status_code = require_auth()
        if error_response:
            return error_response, status_code
        
        user = auth_result['user']
        
        notification = Notification.query.get(notification_id)
        if not notification:
            return jsonify({'error': 'الإشعار غير موجود'}), 404
        
        if notification.user_id != user.id:
            return jsonify({'error': 'غير مسموح لك بحذف هذا الإشعار'}), 403
        
        db.session.delete(notification)
        db.session.commit()
        
        return jsonify({'message': 'تم حذف الإشعار بنجاح'}), 200
        
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': f'خطأ في حذف الإشعار: {str(e)}'}), 500

@notifications_bp.route('/clear-all', methods=['DELETE'])
def clear_all_notifications():
    try:
        auth_result, error_response, status_code = require_auth()
        if error_response:
            return error_response, status_code
        
        user = auth_result['user']
        
        # حذف جميع الإشعارات للمستخدم
        Notification.query.filter_by(user_id=user.id).delete()
        db.session.commit()
        
        return jsonify({'message': 'تم حذف جميع الإشعارات بنجاح'}), 200
        
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': f'خطأ في حذف الإشعارات: {str(e)}'}), 500

