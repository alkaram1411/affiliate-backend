from flask import Blueprint, request, jsonify, session
from src.models.user import db, User, UserProfile, Product, Order, Notification, UserType, OrderStatus, PaymentStatus, NotificationType, SubscriptionStatus
from datetime import datetime, timedelta
from sqlalchemy import and_, or_

orders_bp = Blueprint('orders', __name__)

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

@orders_bp.route('/create', methods=['POST'])
def create_order():
    try:
        auth_result, error_response, status_code = require_auth()
        if error_response:
            return error_response, status_code
        
        user = auth_result['user']
        profile = auth_result['profile']
        
        # التحقق من أن المستخدم مسوق
        if profile.user_type != UserType.MARKETER:
            return jsonify({'error': 'هذه الخدمة للمسوقين فقط'}), 403
        
        if profile.subscription_status != SubscriptionStatus.ACTIVE:
            return jsonify({'error': 'يجب تفعيل الاشتراك أولاً'}), 403
        
        data = request.get_json()
        
        # التحقق من البيانات المطلوبة
        required_fields = ['product_id', 'customer_name', 'customer_phone', 'sale_price', 'quantity']
        for field in required_fields:
            if field not in data or not data[field]:
                return jsonify({'error': f'حقل {field} مطلوب'}), 400
        
        product_id = int(data['product_id'])
        customer_name = data['customer_name'].strip()
        customer_phone = data['customer_phone'].strip()
        sale_price = float(data['sale_price'])
        quantity = int(data['quantity'])
        
        # التحقق من صحة البيانات
        if quantity <= 0:
            return jsonify({'error': 'الكمية يجب أن تكون أكبر من صفر'}), 400
        
        if sale_price <= 0:
            return jsonify({'error': 'سعر البيع يجب أن يكون أكبر من صفر'}), 400
        
        # الحصول على المنتج
        product = Product.query.get(product_id)
        if not product:
            return jsonify({'error': 'المنتج غير موجود'}), 404
        
        if not product.is_active:
            return jsonify({'error': 'المنتج غير مفعل'}), 400
        
        # حساب ربح المسوق
        total_sale_price = sale_price * quantity
        total_base_price = product.base_price * quantity
        marketer_profit = total_sale_price - total_base_price
        
        # التحقق من أن الربح لا يقل عن الحد الأدنى
        min_total_profit = product.min_marketer_profit * quantity
        if marketer_profit < min_total_profit:
            return jsonify({'error': f'الربح يجب أن لا يقل عن {min_total_profit} دينار'}), 400
        
        # إنشاء الطلب
        order = Order(
            product_id=product_id,
            merchant_id=product.merchant_id,
            marketer_id=user.id,
            customer_name=customer_name,
            customer_phone=customer_phone,
            sale_price=sale_price,
            quantity=quantity,
            marketer_profit=marketer_profit,
            status=OrderStatus.PENDING,
            payment_status=PaymentStatus.PENDING
        )
        
        db.session.add(order)
        db.session.flush()  # للحصول على معرف الطلب
        
        # إرسال إشعار للتاجر
        notification = Notification(
            user_id=product.merchant_id,
            title='طلب جديد',
            message=f'لديك طلب جديد على منتج: {product.name}',
            type=NotificationType.NEW_ORDER,
            is_read=False,
            related_order_id=order.id
        )
        
        db.session.add(notification)
        db.session.commit()
        
        return jsonify({
            'message': 'تم إنشاء الطلب بنجاح',
            'order_id': order.id
        }), 201
        
    except ValueError as e:
        return jsonify({'error': 'البيانات المدخلة غير صحيحة'}), 400
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': f'خطأ في إنشاء الطلب: {str(e)}'}), 500

@orders_bp.route('/marketer', methods=['GET'])
def get_marketer_orders():
    try:
        auth_result, error_response, status_code = require_auth()
        if error_response:
            return error_response, status_code
        
        user = auth_result['user']
        
        orders = Order.query.filter_by(marketer_id=user.id).order_by(Order.created_at.desc()).all()
        
        orders_data = []
        for order in orders:
            product = Product.query.get(order.product_id)
            orders_data.append({
                'id': order.id,
                'product': {
                    'id': product.id if product else None,
                    'name': product.name if product else 'منتج محذوف'
                },
                'customer_name': order.customer_name,
                'customer_phone': order.customer_phone,
                'sale_price': order.sale_price,
                'quantity': order.quantity,
                'marketer_profit': order.marketer_profit,
                'status': order.status.value,
                'payment_status': order.payment_status.value,
                'delivery_date': order.delivery_date.isoformat() if order.delivery_date else None,
                'payment_due_date': order.payment_due_date.isoformat() if order.payment_due_date else None,
                'created_at': order.created_at.isoformat(),
                'updated_at': order.updated_at.isoformat()
            })
        
        return jsonify({'orders': orders_data}), 200
        
    except Exception as e:
        return jsonify({'error': f'خطأ في جلب الطلبات: {str(e)}'}), 500

@orders_bp.route('/merchant', methods=['GET'])
def get_merchant_orders():
    try:
        auth_result, error_response, status_code = require_auth()
        if error_response:
            return error_response, status_code
        
        user = auth_result['user']
        
        orders = Order.query.filter_by(merchant_id=user.id).order_by(Order.created_at.desc()).all()
        
        orders_data = []
        for order in orders:
            product = Product.query.get(order.product_id)
            marketer_profile = UserProfile.query.filter_by(user_id=order.marketer_id).first()
            
            orders_data.append({
                'id': order.id,
                'product': {
                    'id': product.id if product else None,
                    'name': product.name if product else 'منتج محذوف'
                },
                'customer_name': order.customer_name,
                'customer_phone': order.customer_phone,
                'sale_price': order.sale_price,
                'quantity': order.quantity,
                'marketer_profit': order.marketer_profit,
                'status': order.status.value,
                'payment_status': order.payment_status.value,
                'marketer_payment_method': marketer_profile.payment_method if marketer_profile else None,
                'marketer_payment_details': marketer_profile.payment_details if marketer_profile else None,
                'delivery_date': order.delivery_date.isoformat() if order.delivery_date else None,
                'payment_due_date': order.payment_due_date.isoformat() if order.payment_due_date else None,
                'created_at': order.created_at.isoformat(),
                'updated_at': order.updated_at.isoformat()
            })
        
        return jsonify({'orders': orders_data}), 200
        
    except Exception as e:
        return jsonify({'error': f'خطأ في جلب الطلبات: {str(e)}'}), 500

@orders_bp.route('/<int:order_id>/status', methods=['PUT'])
def update_order_status(order_id):
    try:
        auth_result, error_response, status_code = require_auth()
        if error_response:
            return error_response, status_code
        
        user = auth_result['user']
        
        data = request.get_json()
        status = data.get('status')
        
        if status not in ['in_progress', 'completed', 'rejected', 'not_serious']:
            return jsonify({'error': 'حالة الطلب غير صحيحة'}), 400
        
        order = Order.query.get(order_id)
        if not order:
            return jsonify({'error': 'الطلب غير موجود'}), 404
        
        if order.merchant_id != user.id:
            return jsonify({'error': 'غير مسموح لك بتعديل هذا الطلب'}), 403
        
        order.status = OrderStatus(status)
        order.updated_at = datetime.utcnow()
        
        # إذا تم إكمال الطلب، تحديد تاريخ التوصيل وموعد الدفع
        if status == 'completed':
            order.delivery_date = datetime.utcnow()
            order.payment_due_date = datetime.utcnow() + timedelta(days=5)  # 5 أيام عمل
        
        # إرسال إشعار للمسوق
        status_messages = {
            'in_progress': 'قيد التنفيذ',
            'completed': 'تم التوصيل',
            'rejected': 'مرفوض',
            'not_serious': 'غير جدي'
        }
        
        notification = Notification(
            user_id=order.marketer_id,
            title='تحديث حالة الطلب',
            message=f'تم تحديث حالة طلبك إلى: {status_messages[status]}',
            type=NotificationType.ORDER_UPDATE,
            is_read=False,
            related_order_id=order_id
        )
        
        db.session.add(notification)
        db.session.commit()
        
        return jsonify({'message': 'تم تحديث حالة الطلب بنجاح'}), 200
        
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': f'خطأ في تحديث حالة الطلب: {str(e)}'}), 500

@orders_bp.route('/<int:order_id>/confirm-payment', methods=['PUT'])
def confirm_payment_received(order_id):
    try:
        auth_result, error_response, status_code = require_auth()
        if error_response:
            return error_response, status_code
        
        user = auth_result['user']
        
        order = Order.query.get(order_id)
        if not order:
            return jsonify({'error': 'الطلب غير موجود'}), 404
        
        if order.marketer_id != user.id:
            return jsonify({'error': 'غير مسموح لك بتعديل هذا الطلب'}), 403
        
        if order.status != OrderStatus.COMPLETED:
            return jsonify({'error': 'الطلب يجب أن يكون مكتملاً أولاً'}), 400
        
        order.payment_status = PaymentStatus.PAID
        order.updated_at = datetime.utcnow()
        
        # تحديث عدد الطلبات المكتملة للمسوق والتاجر
        marketer_profile = UserProfile.query.filter_by(user_id=order.marketer_id).first()
        merchant_profile = UserProfile.query.filter_by(user_id=order.merchant_id).first()
        
        if marketer_profile:
            marketer_profile.completed_orders += 1
            if marketer_profile.completed_orders >= 5:
                marketer_profile.is_verified = True
        
        if merchant_profile:
            merchant_profile.completed_orders += 1
            if merchant_profile.completed_orders >= 3:
                merchant_profile.is_verified = True
        
        db.session.commit()
        
        return jsonify({'message': 'تم تأكيد استلام الدفع بنجاح'}), 200
        
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': f'خطأ في تأكيد الدفع: {str(e)}'}), 500

@orders_bp.route('/<int:order_id>/report-delay', methods=['PUT'])
def report_payment_delay(order_id):
    try:
        auth_result, error_response, status_code = require_auth()
        if error_response:
            return error_response, status_code
        
        user = auth_result['user']
        
        order = Order.query.get(order_id)
        if not order:
            return jsonify({'error': 'الطلب غير موجود'}), 404
        
        if order.marketer_id != user.id:
            return jsonify({'error': 'غير مسموح لك بالإبلاغ عن هذا الطلب'}), 403
        
        order.payment_status = PaymentStatus.DELAYED
        order.updated_at = datetime.utcnow()
        
        # إرسال إشعار للتاجر
        notification = Notification(
            user_id=order.merchant_id,
            title='تأخير في الدفع',
            message='تم الإبلاغ عن تأخير في دفع ربح المسوق',
            type=NotificationType.PAYMENT,
            is_read=False,
            related_order_id=order_id
        )
        
        db.session.add(notification)
        db.session.commit()
        
        return jsonify({'message': 'تم الإبلاغ عن تأخير الدفع بنجاح'}), 200
        
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': f'خطأ في الإبلاغ عن التأخير: {str(e)}'}), 500

@orders_bp.route('/marketer/stats', methods=['GET'])
def get_marketer_stats():
    try:
        auth_result, error_response, status_code = require_auth()
        if error_response:
            return error_response, status_code
        
        user = auth_result['user']
        
        orders = Order.query.filter_by(marketer_id=user.id).all()
        
        total_orders = len(orders)
        completed_orders = len([o for o in orders if o.status == OrderStatus.COMPLETED])
        total_profit = sum([o.marketer_profit for o in orders if o.payment_status == PaymentStatus.PAID])
        pending_profit = sum([o.marketer_profit for o in orders if o.status == OrderStatus.COMPLETED and o.payment_status == PaymentStatus.PENDING])
        
        success_rate = (completed_orders / total_orders * 100) if total_orders > 0 else 0
        
        return jsonify({
            'total_orders': total_orders,
            'completed_orders': completed_orders,
            'success_rate': success_rate,
            'total_profit': total_profit,
            'pending_profit': pending_profit
        }), 200
        
    except Exception as e:
        return jsonify({'error': f'خطأ في جلب الإحصائيات: {str(e)}'}), 500

@orders_bp.route('/merchant/stats', methods=['GET'])
def get_merchant_stats():
    try:
        auth_result, error_response, status_code = require_auth()
        if error_response:
            return error_response, status_code
        
        user = auth_result['user']
        
        orders = Order.query.filter_by(merchant_id=user.id).all()
        
        total_orders = len(orders)
        completed_orders = len([o for o in orders if o.status == OrderStatus.COMPLETED])
        total_owed_to_marketers = sum([o.marketer_profit for o in orders if o.status == OrderStatus.COMPLETED and o.payment_status == PaymentStatus.PENDING])
        
        success_rate = (completed_orders / total_orders * 100) if total_orders > 0 else 0
        
        # حساب المبالغ المستحقة لكل مسوق
        marketer_debts = {}
        for order in orders:
            if order.status == OrderStatus.COMPLETED and order.payment_status == PaymentStatus.PENDING:
                if order.marketer_id not in marketer_debts:
                    marketer_debts[order.marketer_id] = 0
                marketer_debts[order.marketer_id] += order.marketer_profit
        
        return jsonify({
            'total_orders': total_orders,
            'completed_orders': completed_orders,
            'success_rate': success_rate,
            'total_owed_to_marketers': total_owed_to_marketers,
            'marketer_debts': marketer_debts
        }), 200
        
    except Exception as e:
        return jsonify({'error': f'خطأ في جلب الإحصائيات: {str(e)}'}), 500


