# ============================================================
#  recommender.py  –  Hệ thống gợi ý sản phẩm (FIXED)
# ============================================================
import csv
import os
from collections import Counter, defaultdict
from config import CUSTOMER_CSV, TRANSACTION_CSV, PRODUCT_RULES, PROMOTIONS

# ── CACHE ─────────────────────────────────────────────────
_cached_products   = None
_cached_promotions = None
_cached_stats      = None
_product_shelf_map = None
_transactions_raw  = None
_customers_raw     = None


def _ensure_cache():
    """Đảm bảo cache đã được khởi tạo"""
    global _cached_products
    if _cached_products is None:
        refresh_cache()


# ── DATA LOADERS ──────────────────────────────────────────

def _load_customers():
    global _customers_raw
    if _customers_raw is not None:
        return _customers_raw
    
    if not os.path.exists(CUSTOMER_CSV):
        print(f"[Recommender] ⚠️ {CUSTOMER_CSV} không tìm thấy")
        _customers_raw = []
        return _customers_raw
    
    try:
        # Thử nhiều encoding khác nhau
        encodings = ['utf-8-sig', 'utf-8', 'latin-1']
        rows = None
        
        for enc in encodings:
            try:
                with open(CUSTOMER_CSV, encoding=enc) as f:
                    rows = list(csv.DictReader(f))
                print(f"[Recommender] ✅ Đọc file với encoding: {enc}")
                break
            except UnicodeDecodeError:
                continue
        
        if rows is None:
            print(f"[Recommender] ❌ Không thể đọc file với bất kỳ encoding nào")
            _customers_raw = []
            return _customers_raw
            
        _customers_raw = []
        for r in rows:
            raw = r.get("Recommended_Products", "")
            _customers_raw.append({
                "customer_id": r.get("Customer_ID", ""),
                "age_group":   r.get("Age_Group",   ""),
                "gender":      r.get("Gender",       ""),
                "products":    [p.strip() for p in raw.split(",") if p.strip()],
                "promotion":   r.get("Promotion_Applied", ""),
            })
        print(f"[Recommender] ✅ {len(_customers_raw)} khách từ {CUSTOMER_CSV}")
    except Exception as e:
        print(f"[Recommender] ❌ Lỗi đọc CSV: {e}")
        _customers_raw = []
    return _customers_raw


def _load_transactions():
    global _transactions_raw, _product_shelf_map
    if _transactions_raw is not None:
        return _transactions_raw
    
    if not os.path.exists(TRANSACTION_CSV):
        print(f"[Recommender] ⚠️ {TRANSACTION_CSV} không tìm thấy")
        _transactions_raw = []
        _product_shelf_map = {}
        return _transactions_raw
    
    try:
        # Thử nhiều encoding khác nhau
        encodings = ['utf-8-sig', 'utf-8', 'latin-1']
        rows = None
        
        for enc in encodings:
            try:
                with open(TRANSACTION_CSV, encoding=enc) as f:
                    rows = list(csv.DictReader(f))
                print(f"[Recommender] ✅ Đọc transactions với encoding: {enc}")
                break
            except UnicodeDecodeError:
                continue
        
        if rows is None:
            print(f"[Recommender] ❌ Không thể đọc transactions")
            _transactions_raw = []
            _product_shelf_map = {}
            return _transactions_raw
            
        _transactions_raw = []
        _product_shelf_map = {}
        for r in rows:
            name = r.get("Product_Name", "")
            shelf = r.get("Shelf_Location", "Kệ A1")
            _transactions_raw.append({
                "transaction_id": r.get("Transaction_ID", ""),
                "customer_id":    r.get("Customer_ID", ""),
                "product_name":   name,
                "shelf_location": shelf,
            })
            if name and name not in _product_shelf_map:
                _product_shelf_map[name] = shelf
        print(f"[Recommender] ✅ {len(_transactions_raw)} giao dịch từ {TRANSACTION_CSV}")
        print(f"[Recommender] ✅ {len(_product_shelf_map)} sản phẩm có vị trí kệ")
    except Exception as e:
        print(f"[Recommender] ❌ Lỗi đọc CSV: {e}")
        _transactions_raw = []
        _product_shelf_map = {}
    return _transactions_raw


def find_shelf_location(product_name):
    """Tìm vị trí kệ"""
    _ensure_cache()
    _load_transactions()
    return (_product_shelf_map or {}).get(product_name, "Kệ A1")


def refresh_cache():
    """Load lại toàn bộ dữ liệu CSV - FIXED"""
    global _cached_products, _cached_promotions, _cached_stats
    global _customers_raw, _transactions_raw, _product_shelf_map

    print("[Recommender] 🔄 Đang refresh cache...")
    _customers_raw = None
    _transactions_raw = None
    _product_shelf_map = None

    customers = _load_customers()
    _load_transactions()

    stats = defaultdict(lambda: {"products": [], "promotions": []})
    for c in customers:
        key = (c["age_group"], c["gender"])
        for p in c["products"]:
            if p:
                stats[key]["products"].append(p)
        if c["promotion"]:
            stats[key]["promotions"].append(c["promotion"])

    _cached_products = {}
    _cached_promotions = {}
    _cached_stats = stats

    for key, data in stats.items():
        if data["products"]:
            top = Counter(data["products"]).most_common(3)
            _cached_products[key] = [(p, find_shelf_location(p), cnt) for p, cnt in top]
        else:
            _cached_products[key] = []

        if data["promotions"]:
            _cached_promotions[key] = Counter(data["promotions"]).most_common(1)[0][0]

    total = sum(len(v) for v in _cached_products.values())
    print(f"[Recommender] ✅ Cache: {len(_cached_products)} nhóm, {total} gợi ý")
    
    # Log chi tiết để debug
    for key, products in _cached_products.items():
        if products:
            print(f"  📊 {key}: {products[:2]}")


def _similar_group(age_group, gender):
    """Tìm nhóm tương tự"""
    similar_map = {
        "Trẻ em (0–12)":     ["Thiếu niên (13–18)"],
        "Thiếu niên (13–18)": ["Thanh niên (19-30)", "Trẻ em (0–12)"],
        "Thanh niên (19-30)": ["Thiếu niên (13-18)", "Trung niên (31-50)"],
        "Trung niên (31-50)": ["Thanh niên (19-30)", "Cao tuổi (>50)"],
        "Cao tuổi (>50)":    ["Trung niên (31-50)"],
    }
    for sim_age in similar_map.get(age_group, []):
        key = (sim_age, gender)
        if key in _cached_products and _cached_products[key]:
            return key
    for key in _cached_products:
        if key[1] == gender and _cached_products[key]:
            return key
    return None


def recommend_from_csv(age_group, gender):
    _ensure_cache()
    key = (age_group, gender)
    products = _cached_products.get(key, [])
    promo = _cached_promotions.get(key)

    if products:
        return {
            "products": [(p[0], p[1]) for p in products],
            "promotion": promo or PROMOTIONS.get(age_group, "Chào mừng đến siêu thị!"),
            "source": "📊 Dữ liệu lịch sử",
            "level": 1,
        }

    sim = _similar_group(age_group, gender)
    if sim:
        products = _cached_products[sim]
        promo = _cached_promotions.get(sim)
        return {
            "products": [(p[0], p[1]) for p in products],
            "promotion": promo or PROMOTIONS.get(age_group, "Chào mừng đến siêu thị!"),
            "source": f"📊 Nhóm tương tự ({sim[0]})",
            "level": 1,
        }
    return None


def recommend_by_popular(age_group, gender):
    _ensure_cache()
    customers = _load_customers()
    trans = _load_transactions()
    if not trans:
        return None

    cust_ids = {c["customer_id"] for c in customers if c["age_group"] == age_group}
    counts = Counter(t["product_name"] for t in trans if t["customer_id"] in cust_ids)

    if not counts:
        counts = Counter(t["product_name"] for t in trans)

    top = counts.most_common(3)
    if not top:
        return None

    return {
        "products": [(p, find_shelf_location(p)) for p, _ in top],
        "promotion": PROMOTIONS.get(age_group, "Chào mừng đến siêu thị!"),
        "source": "🔥 Sản phẩm phổ biến",
        "level": 2,
    }


def recommend(age_group, gender):
    """Hàm gợi ý chính - FIXED"""
    _ensure_cache()

    # Debug log
    print(f"[Recommender] Gợi ý cho {age_group}/{gender}")
    
    result = recommend_from_csv(age_group, gender)
    if result and result["products"]:
        print(f"[Recommender] ✅ Dùng CSV: {result['source']} - {len(result['products'])} sản phẩm")
        return result

    result = recommend_by_popular(age_group, gender)
    if result and result["products"]:
        print(f"[Recommender] ✅ Dùng Popular: {result['source']} - {len(result['products'])} sản phẩm")
        return result

    products = PRODUCT_RULES.get((age_group, gender), [])
    if not products:
        for k, v in PRODUCT_RULES.items():
            if k[1] == gender:
                products = v
                break
    products = products or [("Sản phẩm phổ thông", "Kệ A")]
    
    print(f"[Recommender] ⚠️ Dùng Rule-based: {len(products)} sản phẩm")
    return {
        "products": products,
        "promotion": PROMOTIONS.get(age_group, "Chào mừng đến siêu thị!"),
        "level": 3,
        "source": "📋 Rule-based",
    }