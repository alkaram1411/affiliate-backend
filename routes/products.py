from flask import Blueprint, request, jsonify, session
from src.models.user import db, User, UserProfile, Product, UserType, SubscriptionStatus
from sqlalchemy import and_

products_bp = Blueprint('products', __name__)

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

@products_bp.route('/create', methods=['POST'])
def create_product():
    try:
        auth_result, error_response, status_code = require_auth()
        if error_response:
            return error_response, status_code
        
        user = auth_result['user']
        profile = auth_result['profile']
        
        # التحقق من أن المستخدم تاجر
        if profile.user_type != UserType.MERCHANT:
            return jsonify({'error': 'هذه الخدمة للتجار فقط'}), 403
        
        if profile.subscription_status != SubscriptionStatus.ACTIVE:
            return jsonify({'error': 'يجب تفعيل الاشتراك أولاً'}), 403
        
        data = request.get_json()
        
        # التحقق من البيانات المطلوبة
        required_fields = ['name', 'description', 'base_price', 'min_marketer_profit']
        for field in required_fields:
            if field not in data or not data[field]:
                return jsonify({'error': f'حقل {field} مطلوب'}), 400
        
        name = data['name'].strip()
        description = data['description'].strip()
        base_price = float(data['base_price'])
        min_marketer_profit = float(data['min_marketer_profit'])
        suggested_price = data.get('suggested_price')
        category = data.get('category', '').strip()
        image_url = data.get('image_url', '').strip()
        
        # التحقق من صحة الأسعار
        if base_price <= 0 or min_marketer_profit <= 0:
            return jsonify({'error': 'الأسعار يجب أن تكون أكبر من صفر'}), 400
        
        if suggested_price:
            suggested_price = float(suggested_price)
            if suggested_price < base_price + min_marketer_profit:
                return jsonify({'error': 'السعر المقترح يجب أن يكون أكبر من السعر الأساسي + أقل ربح للمسوق'}), 400
        
        # إنشاء المنتج
        product = Product(
            merchant_id=user.id,
            name=name,
            description=description,
            image_url=image_url if image_url else None,
            base_price=base_price,
            min_marketer_profit=min_marketer_profit,
            suggested_price=suggested_price,
            category=category if category else None,
            is_active=True
        )
        
        db.session.add(product)
        db.session.commit()
        
        return jsonify({
            'message': 'تم إنشاء المنتج بنجاح',
            'product': {
                'id': product.id,
                'name': product.name,
                'description': product.description,
                'image_url': product.image_url,
                'base_price': product.base_price,
                'min_marketer_profit': product.min_marketer_profit,
                'suggested_price': product.suggested_price,
                'category': product.category,
                'is_active': product.is_active
            }
        }), 201
        
    except ValueError:
        return jsonify({'error': 'الأسعار يجب أن تكون أرقام صحيحة'}), 400
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': f'خطأ في إنشاء المنتج: {str(e)}'}), 500

@products_bp.route('/my-products', methods=['GET'])
def get_merchant_products():
    try:
        auth_result, error_response, status_code = require_auth()
        if error_response:
            return error_response, status_code
        
        user = auth_result['user']
        profile = auth_result['profile']
        
        if profile.user_type != UserType.MERCHANT:
            return jsonify({'error': 'هذه الخدمة للتجار فقط'}), 403
        
        products = Product.query.filter_by(merchant_id=user.id).order_by(Product.created_at.desc()).all()
        
        products_data = []
        for product in products:
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
                'created_at': product.created_at.isoformat()
            })
        
        return jsonify({'products': products_data}), 200
        
    except Exception as e:
        return jsonify({'error': f'خطأ في جلب المنتجات: {str(e)}'}), 500

@products_bp.route('/active', methods=['GET'])
def get_active_products():
    try:
        auth_result, error_response, status_code = require_auth()
        if error_response:
            return error_response, status_code
        
        profile = auth_result['profile']
        
        if profile.user_type != UserType.MARKETER:
            return jsonify({'error': 'هذه الخدمة للمسوقين فقط'}), 403
        
        # جلب المنتجات المفعلة مع معلومات التاجر
        products = db.session.query(Product, UserProfile).join(
            UserProfile, Product.merchant_id == UserProfile.user_id
        ).filter(
            and_(Product.is_active == True, UserProfile.subscription_status == SubscriptionStatus.ACTIVE)
        ).order_by(Product.created_at.desc()).all()
        
        products_data = []
        for product, merchant_profile in products:
            products_data.append({
                'id': product.id,
                'name': product.name,
                'description': product.description,
                'image_url': product.image_url,
                'base_price': product.base_price,
                'min_marketer_profit': product.min_marketer_profit,
                'suggested_price': product.suggested_price,
                'category': product.category,
                'merchant_verified': merchant_profile.is_verified,
                'merchant_completed_orders': merchant_profile.completed_orders,
                'merchant_business_name': merchant_profile.business_name,
                'created_at': product.created_at.isoformat()
            })
        
        return jsonify({'products': products_data}), 200
        
    except Exception as e:
        return jsonify({'error': f'خطأ في جلب المنتجات: {str(e)}'}), 500

@products_bp.route('/<int:product_id>/toggle-status', methods=['PUT'])
def toggle_product_status(product_id):
    try:
        auth_result, error_response, status_code = require_auth()
        if error_response:
            return error_response, status_code
        
        user = auth_result['user']
        
        product = Product.query.get(product_id)
        if not product:
            return jsonify({'error': 'المنتج غير موجود'}), 404
        
        if product.merchant_id != user.id:
            return jsonify({'error': 'غير مسموح لك بتعديل هذا المنتج'}), 403
        
        product.is_active = not product.is_active
        db.session.commit()
        
        status_text = 'مفعل' if product.is_active else 'معطل'
        return jsonify({
            'message': f'تم تحديث حالة المنتج إلى {status_text}',
            'is_active': product.is_active
        }), 200
        
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': f'خطأ في تحديث حالة المنتج: {str(e)}'}), 500

@products_bp.route('/<int:product_id>', methods=['PUT'])
def update_product(product_id):
    try:
        auth_result, error_response, status_code = require_auth()
        if error_response:
            return error_response, status_code
        
        user = auth_result['user']
        
        product = Product.query.get(product_id)
        if not product:
            return jsonify({'error': 'المنتج غير موجود'}), 404
        
        if product.merchant_id != user.id:
            return jsonify({'error': 'غير مسموح لك بتعديل هذا المنتج'}), 403
        
        data = request.get_json()
        
        # تحديث البيانات
        if 'name' in data:
            product.name = data['name'].strip()
        if 'description' in data:
            product.description = data['description'].strip()
        if 'base_price' in data:
            product.base_price = float(data['base_price'])
        if 'min_marketer_profit' in data:
            product.min_marketer_profit = float(data['min_marketer_profit'])
        if 'suggested_price' in data:
            product.suggested_price = float(data['suggested_price']) if data['suggested_price'] else None
        if 'category' in data:
            product.category = data['category'].strip() if data['category'] else None
        if 'image_url' in data:
            product.image_url = data['image_url'].strip() if data['image_url'] else None
        
        # التحقق من صحة الأسعار
        if product.base_price <= 0 or product.min_marketer_profit <= 0:
            return jsonify({'error': 'الأسعار يجب أن تكون أكبر من صفر'}), 400
        
        if product.suggested_price and product.suggested_price < product.base_price + product.min_marketer_profit:
            return jsonify({'error': 'السعر المقترح يجب أن يكون أكبر من السعر الأساسي + أقل ربح للمسوق'}), 400
        
        db.session.commit()
        
        return jsonify({'message': 'تم تحديث المنتج بنجاح'}), 200
        
    except ValueError:
        return jsonify({'error': 'الأسعار يجب أن تكون أرقام صحيحة'}), 400
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': f'خطأ في تحديث المنتج: {str(e)}'}), 500

@products_bp.route('/<int:product_id>', methods=['DELETE'])
def delete_product(product_id):
    try:
        auth_result, error_response, status_code = require_auth()
        if error_response:
            return error_response, status_code
        
        user = auth_result['user']
        
        product = Product.query.get(product_id)
        if not product:
            return jsonify({'error': 'المنتج غير موجود'}), 404
        
        if product.merchant_id != user.id:
            return jsonify({'error': 'غير مسموح لك بحذف هذا المنتج'}), 403
        
        # التحقق من عدم وجود طلبات مرتبطة
        if product.orders:
            return jsonify({'error': 'لا يمكن حذف المنتج لوجود طلبات مرتبطة به'}), 400
        
        db.session.delete(product)
        db.session.commit()
        
        return jsonify({'message': 'تم حذف المنتج بنجاح'}), 200
        
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': f'خطأ في حذف المنتج: {str(e)}'}), 500

@products_bp.route('/<int:product_id>', methods=['GET'])
def get_product(product_id):
    try:
        product = Product.query.get(product_id)
        if not product:
            return jsonify({'error': 'المنتج غير موجود'}), 404
        
        # جلب معلومات التاجر
        merchant_profile = UserProfile.query.filter_by(user_id=product.merchant_id).first()
        
        product_data = {
            'id': product.id,
            'name': product.name,
            'description': product.description,
            'image_url': product.image_url,
            'base_price': product.base_price,
            'min_marketer_profit': product.min_marketer_profit,
            'suggested_price': product.suggested_price,
            'category': product.category,
            'is_active': product.is_active,
            'merchant_verified': merchant_profile.is_verified if merchant_profile else False,
            'merchant_completed_orders': merchant_profile.completed_orders if merchant_profile else 0,
            'merchant_business_name': merchant_profile.business_name if merchant_profile else None,
            'created_at': product.created_at.isoformat()
        }
        
        return jsonify({'product': product_data}), 200
        
    except Exception as e:
        return jsonify({'error': f'خطأ في جلب المنتج: {str(e)}'}), 500

