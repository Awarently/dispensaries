"""Trulieve: uses the site's own storefront GraphQL endpoint (/api/graphql), which robots.txt explicitly allows."""
from datetime import date

BASE = "https://www.trulieve.com"
API = BASE + "/api/graphql"
FLOWER_CATEGORY_UID = "MjA3"  # category "flower" (from the page's own data)
PAGE_SIZE = 50
FORMATS = {"Whole Flower", "Minis", "Ground", "Pre-Rolls"}

STORE_QUERY = """query getPickupStores($zipCode:String=""$pageSize:Int=10$radius:String=""){
pickupstores(filter:{zipcode:{eq:$zipCode}radius:{eq:$radius}non_shop_store:{eq:"false"}}pageSize:$pageSize currentPage:1){
storeList{name code storecode state address city zipCode approximateDistance is_active}}}"""

PRODUCT_QUERY = """query products($searchCriteria:[SearchCriteriaInput!]!,$pageSize:Int=10,$currentPage:Int=1){
products(searchCriteria:$searchCriteria pageSize:$pageSize currentPage:$currentPage){
total_count page_info{total_pages current_page}
items{__typename id name sku url_key stock_status
custom_attributes_product{code value}
categories{name}
price_range{minimum_price{regular_price{value} final_price{value}}}
... on ConfigurableProduct{variants{attributes{code label}
product{sku stock_status total_terpene_percentage price_range{minimum_price{regular_price{value} final_price{value}}}}}}}}}"""


def _gql(sess, query, variables, store=None):
    headers = {"x-pylot-backend": "trulieve_prod", "Content-Type": "application/json"}
    if store:
        headers["Store"] = store
    r = sess.request("POST", API, json={"query": query, "variables": variables}, headers=headers)
    j = r.json()
    if j.get("errors"):
        raise RuntimeError(f"Trulieve GraphQL error: {j['errors'][0].get('message')}")
    return j["data"]


def nearest_store(sess, zip_code):
    d = _gql(sess, STORE_QUERY, {"zipCode": zip_code, "pageSize": 10, "radius": "100"})
    stores = [s for s in d["pickupstores"]["storeList"] if s.get("is_active") and s.get("state") == "FL"]
    if not stores:
        raise RuntimeError("No Trulieve stores returned for ZIP " + zip_code)
    stores.sort(key=lambda s: float(s.get("approximateDistance") or 1e9))
    return stores[0]


def _num(x):
    try:
        return float(x)
    except (TypeError, ValueError):
        return None


def collect(sess, zip_code):
    store = nearest_store(sess, zip_code)
    code = store["storecode"] or store["code"]
    location = f"{store['name']} - {store['address']}, {store['city']}, FL {store['zipCode']}"
    crit = [{"attribute_code": "category_uid", "filter_action": "EQ", "filter_value": FLOWER_CATEGORY_UID}]
    rows, skipped, seen, page, total_pages = [], 0, set(), 1, 1
    today = date.today().isoformat()
    while page <= total_pages:
        d = _gql(sess, PRODUCT_QUERY, {"searchCriteria": crit, "pageSize": PAGE_SIZE, "currentPage": page}, store=code)
        prods = d["products"]
        total_pages = prods["page_info"]["total_pages"]
        for it in prods["items"]:
            if it["id"] in seen:
                continue
            seen.add(it["id"])
            attrs = {c["code"]: c["value"] for c in it.get("custom_attributes_product") or []}
            variants = it.get("variants") or []
            # Tile shows the first variant (a batch); prefer the first one in stock that has terpene data.
            variants.sort(key=lambda v: (v["product"]["stock_status"] != "IN_STOCK",
                                         _num(v["product"].get("total_terpene_percentage")) is None))
            v = variants[0] if variants else None
            terps = _num(v["product"].get("total_terpene_percentage")) if v else None
            if not terps:
                skipped += 1
                continue
            thc = None
            for a in v.get("attributes") or []:
                if a["code"] == "thc_percentage":
                    thc = _num(a["label"])
            if thc is None:
                thc = _num(attrs.get("thc_percentage"))
            pr = (v["product"].get("price_range") or it["price_range"])["minimum_price"]
            reg, fin = pr["regular_price"]["value"], pr["final_price"]["value"]
            cats = [c["name"] for c in it.get("categories") or [] if c["name"] in FORMATS]
            rows.append({
                "dispensary": "Trulieve", "store_location": location,
                "brand": attrs.get("brand", ""), "product_name": attrs.get("product_display_name") or it["name"],
                "subcategory": ", ".join(cats), "strain_type": attrs.get("strain_type", ""),
                "weight": attrs.get("units", ""), "price": reg,
                "sale_price": fin if fin is not None and reg is not None and fin < reg else None,
                "thc_pct": thc, "terpene_pct": terps,
                "in_stock": (v["product"]["stock_status"] == "IN_STOCK"),
                "url": f"{BASE}/product/{it['url_key']}", "date_collected": today,
            })
        page += 1
    return rows, skipped, location
