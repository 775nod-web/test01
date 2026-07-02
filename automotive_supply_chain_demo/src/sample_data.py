"""
自動車サプライチェーンのサンプルデータ生成ロジック

- 部品メーカー（Tier2 / Tier1）
- 港湾（チョークポイントを含む）
- 完成車組立工場・車種
- 物流ルート（Scope3 排出量つき）
- 車種 ↔ 部品カテゴリのマッピング
- 在庫データ（CRUD デモ用）

このモジュールは Pandas のみに依存する（PySpark には依存しない）。
`data_setup.py`（Databricks 上で Spark DataFrame に変換して Delta 保存）と
`src/db.py` のローカルデモモード（SQLite）の両方から共有して利用する。
"""

import random
from datetime import date, datetime, timedelta

import pandas as pd

RANDOM_SEED = 42


# ──────────────────────────────────────────────
# マスターデータ定義
# ──────────────────────────────────────────────

# (supplier_id, supplier_name, tier, country, region, city, lat, lon, component_category)
_SUPPLIER_MASTER = [
    ("SUP001", "Taiwan Silicon Foundry",       "Tier2", "Taiwan",       "APAC",   "Hsinchu",     24.8138, 120.9675, "半導体/ECU"),
    ("SUP002", "Korea Advanced Semicon",       "Tier2", "South Korea",  "APAC",   "Icheon",      37.2795, 127.4425, "半導体/ECU"),
    ("SUP003", "Nippon Rare Earth Materials",  "Tier2", "Japan",        "APAC",   "Toyama",      36.6953, 137.2113, "モーター/磁石"),
    ("SUP004", "China Baosteel Group",         "Tier2", "China",        "APAC",   "Shanghai",    31.2304, 121.4737, "鋼材/ボディ"),
    ("SUP005", "Guangxi Rubber Industries",    "Tier2", "China",        "APAC",   "Guangzhou",   23.1291, 113.2644, "タイヤ/ゴム"),
    ("SUP006", "Chile Lithium Mining Co.",     "Tier2", "Chile",        "LATAM",  "Antofagasta", -23.6509, -70.3975, "バッテリー原料"),
    ("SUP007", "DR Congo Cobalt Resources",    "Tier2", "DR Congo",     "EMEA",   "Kolwezi",     -10.7167, 25.4667, "バッテリー原料"),
    ("SUP008", "Indonesia Nickel Corp",        "Tier2", "Indonesia",    "APAC",   "Sulawesi",    -1.4300, 121.4456, "バッテリー原料"),
    ("SUP009", "German Precision Alloys",      "Tier2", "Germany",      "EMEA",   "Essen",       51.4556, 7.0116, "鋼材/ボディ"),
    ("SUP010", "India Wiring Components",      "Tier2", "India",        "EMEA",   "Chennai",     13.0827, 80.2707, "ワイヤーハーネス素材"),
    ("SUP011", "Vietnam Electronics Parts",    "Tier2", "Vietnam",      "APAC",   "Hanoi",       21.0278, 105.8342, "半導体/ECU"),
    ("SUP012", "Thailand Rubber Exports",      "Tier2", "Thailand",     "APAC",   "Rayong",      12.6807, 101.2816, "タイヤ/ゴム"),
    ("SUP013", "Denso-style Engine Systems",   "Tier1", "Japan",        "APAC",   "Kariya",      34.9857, 137.0022, "エンジン部品"),
    ("SUP014", "Aisin-style Transmission Co.", "Tier1", "Japan",        "APAC",   "Kariya",      34.9833, 137.0000, "トランスミッション"),
    ("SUP015", "Bosch-style ECU Systems",      "Tier1", "Germany",      "EMEA",   "Stuttgart",   48.7758, 9.1829, "半導体/ECU"),
    ("SUP016", "Continental-style Brake Sys.", "Tier1", "Germany",      "EMEA",   "Hanover",     52.3759, 9.7320, "ブレーキシステム"),
    ("SUP017", "Yazaki-style Wiring Harness",  "Tier1", "Mexico",       "LATAM",  "Ciudad Juarez", 31.6904, -106.4245, "ワイヤーハーネス"),
    ("SUP018", "Panasonic-style EV Battery",   "Tier1", "Japan",        "APAC",   "Osaka",       34.6937, 135.5023, "EVバッテリー"),
    ("SUP019", "LG-style Battery Solutions",   "Tier1", "South Korea",  "APAC",   "Ochang",      36.7355, 127.4425, "EVバッテリー"),
    ("SUP020", "Michelin-style Tire Mfg.",     "Tier1", "Thailand",     "APAC",   "Laem Chabang", 13.0827, 100.8833, "タイヤ"),
    ("SUP021", "Magna-style Body Panels",      "Tier1", "Poland",       "EMEA",   "Gliwice",     50.2945, 18.6714, "ボディパネル"),
    ("SUP022", "ZF-style Steering Systems",    "Tier1", "USA",          "NA",     "Detroit",     42.3314, -83.0458, "ステアリングシステム"),
    ("SUP023", "Denso-style Cooling Systems",  "Tier1", "Thailand",     "APAC",   "Bangkok",     13.7563, 100.5018, "冷却システム"),
    ("SUP024", "Bridgestone-style Tire Mfg.",  "Tier1", "Japan",        "APAC",   "Kurume",      33.3167, 130.5167, "タイヤ"),
    ("SUP025", "Valeo-style Lighting Systems", "Tier1", "France",       "EMEA",   "Paris",       48.8566, 2.3522, "灯火システム"),
    ("SUP026", "Aptiv-style Wiring Harness",   "Tier1", "Morocco",      "EMEA",   "Tangier",     35.7595, -5.8340, "ワイヤーハーネス"),
    ("SUP027", "Samsung SDI-style Battery",    "Tier1", "Hungary",      "EMEA",   "God",         47.6833, 19.1333, "EVバッテリー"),
    ("SUP028", "CATL-style EV Battery",        "Tier1", "China",        "APAC",   "Ningde",      26.6656, 119.5470, "EVバッテリー"),
]

# (port_id, port_name, country, lat, lon, congestion_level, is_chokepoint)
_PORT_MASTER = [
    ("PRT001", "上海港 (Shanghai)",       "China",       31.2304,  121.4737, "Medium", False),
    ("PRT002", "寧波舟山港 (Ningbo)",      "China",       29.8683,  121.5440, "Medium", False),
    ("PRT003", "横浜港 (Yokohama)",       "Japan",       35.4437,  139.6380, "Low",    False),
    ("PRT004", "神戸港 (Kobe)",           "Japan",       34.6901,  135.1955, "Low",    False),
    ("PRT005", "釜山港 (Busan)",          "South Korea", 35.1796,  129.0756, "Low",    False),
    ("PRT006", "シンガポール港",          "Singapore",   1.2655,   103.8201, "Medium", False),
    ("PRT007", "スエズ運河 (Suez Canal)", "Egypt",       30.5852,  32.2654,  "High",   True),
    ("PRT008", "ロッテルダム港",          "Netherlands", 51.9496,  4.1453,   "Low",    False),
    ("PRT009", "ロサンゼルス/ロングビーチ港", "USA",      33.7405,  -118.2668, "Medium", False),
    ("PRT010", "ハンブルク港",            "Germany",     53.5459,  9.9695,   "Low",    False),
    ("PRT011", "レムチャバン港 (Thailand)", "Thailand",   13.0827,  100.8833, "Low",    False),
    ("PRT012", "パナマ運河 (Panama Canal)", "Panama",     9.0800,   -79.6800, "High",   True),
    ("PRT013", "マラッカ海峡 (Malacca Strait)", "Malaysia", 2.5000, 101.8000, "Medium", True),
    ("PRT014", "タンジール・メド港",      "Morocco",     35.8833,  -5.5000,  "Low",    False),
]

# (plant_id, plant_name, oem, country, city, lat, lon, monthly_capacity)
_PLANT_MASTER = [
    ("PLT001", "Toyota Motomachi Plant",     "Toyota",   "Japan",     "Toyota City",   35.0844, 137.1561, 45000),
    ("PLT002", "Toyota Georgetown Plant",    "Toyota",   "USA",       "Georgetown",    38.2098, -84.5588, 55000),
    ("PLT003", "Toyota Tianjin Plant",       "Toyota",   "China",     "Tianjin",       39.0842, 117.2009, 40000),
    ("PLT004", "VW Wolfsburg Plant",         "VW",       "Germany",   "Wolfsburg",     52.4227, 10.7865, 60000),
    ("PLT005", "Honda Marysville Plant",     "Honda",    "USA",       "Marysville",    40.2362, -83.3671, 42000),
    ("PLT006", "Nissan Sunderland Plant",    "Nissan",   "UK",        "Sunderland",    54.9061, -1.3813, 35000),
    ("PLT007", "Hyundai Ulsan Plant",        "Hyundai",  "South Korea","Ulsan",        35.5384, 129.3114, 50000),
    ("PLT008", "Stellantis Melfi Plant",     "Stellantis","Italy",    "Melfi",         40.9967, 15.6522, 25000),
    ("PLT009", "Ford Kentucky Truck Plant",  "Ford",     "USA",       "Louisville",    38.2527, -85.7585, 38000),
    ("PLT010", "BMW Spartanburg Plant",      "BMW",      "USA",       "Spartanburg",   34.9496, -81.9320, 30000),
]

# (model_id, model_name, oem, plant_id)
_VEHICLE_MODEL_MASTER = [
    ("MDL001", "Corolla",       "Toyota",    "PLT001"),
    ("MDL002", "RAV4",          "Toyota",    "PLT002"),
    ("MDL003", "Camry",         "Toyota",    "PLT002"),
    ("MDL004", "bZ4X (EV)",     "Toyota",    "PLT003"),
    ("MDL005", "Golf",          "VW",        "PLT004"),
    ("MDL006", "ID.4 (EV)",     "VW",        "PLT004"),
    ("MDL007", "Civic",         "Honda",     "PLT005"),
    ("MDL008", "CR-V",          "Honda",     "PLT005"),
    ("MDL009", "Qashqai",       "Nissan",    "PLT006"),
    ("MDL010", "Leaf (EV)",     "Nissan",    "PLT006"),
    ("MDL011", "Elantra",       "Hyundai",   "PLT007"),
    ("MDL012", "Ioniq 5 (EV)",  "Hyundai",   "PLT007"),
    ("MDL013", "Jeep Compass",  "Stellantis","PLT008"),
    ("MDL014", "F-150",         "Ford",      "PLT009"),
    ("MDL015", "F-150 Lightning (EV)", "Ford","PLT009"),
    ("MDL016", "X5",            "BMW",       "PLT010"),
]

COMPONENT_CATEGORIES = [
    "半導体/ECU", "エンジン部品", "トランスミッション", "ブレーキシステム",
    "ワイヤーハーネス", "EVバッテリー", "タイヤ", "ボディパネル",
    "ステアリングシステム", "冷却システム", "灯火システム", "モーター/磁石",
]

TRANSPORT_MODES = ["海上輸送", "航空輸送", "陸上輸送(トラック)", "鉄道輸送"]

WAREHOUSE_LOCATIONS = [
    "名古屋DC", "ケンタッキーDC", "シュツットガルトDC", "上海DC",
    "バンコクDC", "メキシコシティDC", "蔚山DC", "ウルフスブルクDC",
]


def _rng() -> random.Random:
    return random.Random(RANDOM_SEED)


def generate_suppliers() -> pd.DataFrame:
    rng = _rng()
    rows = []
    for sid, name, tier, country, region, city, lat, lon, category in _SUPPLIER_MASTER:
        risk_score = rng.randint(10, 90)
        risk_level = "High" if risk_score >= 65 else ("Medium" if risk_score >= 35 else "Low")
        rows.append({
            "supplier_id": sid,
            "supplier_name": name,
            "tier": tier,
            "country": country,
            "region": region,
            "city": city,
            "lat": lat,
            "lon": lon,
            "component_category": category,
            "risk_score": risk_score,
            "risk_level": risk_level,
        })
    return pd.DataFrame(rows)


def generate_ports() -> pd.DataFrame:
    rows = []
    for pid, name, country, lat, lon, congestion, is_chokepoint in _PORT_MASTER:
        rows.append({
            "port_id": pid,
            "port_name": name,
            "country": country,
            "lat": lat,
            "lon": lon,
            "congestion_level": congestion,
            "is_chokepoint": is_chokepoint,
        })
    return pd.DataFrame(rows)


def generate_assembly_plants() -> pd.DataFrame:
    rows = []
    for plid, name, oem, country, city, lat, lon, capacity in _PLANT_MASTER:
        rows.append({
            "plant_id": plid,
            "plant_name": name,
            "oem": oem,
            "country": country,
            "city": city,
            "lat": lat,
            "lon": lon,
            "monthly_capacity_units": capacity,
        })
    return pd.DataFrame(rows)


def generate_vehicle_models() -> pd.DataFrame:
    rows = []
    for mid, name, oem, plid in _VEHICLE_MODEL_MASTER:
        rows.append({
            "model_id": mid,
            "model_name": name,
            "oem": oem,
            "plant_id": plid,
        })
    return pd.DataFrame(rows)


def generate_logistics_routes(suppliers: pd.DataFrame, ports: pd.DataFrame,
                                plants: pd.DataFrame) -> pd.DataFrame:
    """サプライヤー → (チョークポイント経由の港湾) → 組立工場 の物流ルートを生成する"""
    rng = _rng()
    rows = []
    route_seq = 1

    # サプライヤーの地域とチョークポイント経由の傾向をシンプルにマッピング
    chokepoints = ports[ports["is_chokepoint"]]["port_id"].tolist()
    normal_ports = ports[~ports["is_chokepoint"]]["port_id"].tolist()
    port_lookup = ports.set_index("port_id").to_dict("index")
    plant_lookup = plants.set_index("plant_id").to_dict("index")

    for _, sup in suppliers.iterrows():
        # 各サプライヤーから 1〜3 の組立工場向けにルートを生成
        n_routes = rng.randint(1, 3)
        target_plants = rng.sample(list(plant_lookup.keys()), k=n_routes)
        for plant_id in target_plants:
            plant = plant_lookup[plant_id]
            mode = rng.choice(TRANSPORT_MODES)

            via_chokepoint = None
            via_port_id = None
            if mode == "海上輸送":
                # アジア→欧州/米州の場合、スエズ運河・パナマ運河・マラッカ海峡を経由する確率を上げる
                if sup["region"] in ("APAC",) and plant["country"] in ("Germany", "UK", "Italy", "France", "Netherlands"):
                    via_port_id = "PRT007"  # スエズ運河
                elif sup["region"] in ("APAC",) and plant["country"] in ("USA",):
                    via_port_id = rng.choice(["PRT012", "PRT013"])  # パナマ運河 or マラッカ海峡
                else:
                    via_port_id = rng.choice(normal_ports)
                via_chokepoint = via_port_id in chokepoints

            distance_km = round(rng.uniform(500, 20000), 0)
            transit_days = max(1, round(distance_km / rng.uniform(400, 900)))
            # 輸送モードごとの CO2 排出係数 (kg-CO2 / km / 出荷ロット、簡易シミュレーション値)
            emission_factor = {
                "海上輸送": 0.015, "航空輸送": 0.5, "陸上輸送(トラック)": 0.12, "鉄道輸送": 0.03,
            }[mode]
            carbon_emissions = round(distance_km * emission_factor * rng.uniform(0.8, 1.3), 1)

            rows.append({
                "route_id": f"RT{route_seq:04d}",
                "supplier_id": sup["supplier_id"],
                "supplier_name": sup["supplier_name"],
                "origin_lat": sup["lat"],
                "origin_lon": sup["lon"],
                "plant_id": plant_id,
                "plant_name": plant["plant_name"],
                "dest_lat": plant["lat"],
                "dest_lon": plant["lon"],
                "transport_mode": mode,
                "via_port_id": via_port_id,
                "via_port_name": port_lookup[via_port_id]["port_name"] if via_port_id else None,
                "via_chokepoint": bool(via_chokepoint),
                "distance_km": distance_km,
                "transit_days": int(transit_days),
                "carbon_emissions_scope3_kg": carbon_emissions,
            })
            route_seq += 1

    return pd.DataFrame(rows)


def generate_vehicle_component_map(vehicle_models: pd.DataFrame,
                                     suppliers: pd.DataFrame) -> pd.DataFrame:
    """車種ごとに、どのサプライヤー／部品カテゴリに依存しているかをマッピングする"""
    rng = _rng()
    rows = []
    seq = 1
    for _, model in vehicle_models.iterrows():
        # EV 車種はバッテリー系サプライヤーを優先的に含める
        is_ev = "EV" in model["model_name"]
        candidate_categories = COMPONENT_CATEGORIES.copy()
        n_components = rng.randint(4, 6)
        chosen_categories = rng.sample(candidate_categories, k=n_components)
        if is_ev and "EVバッテリー" not in chosen_categories:
            chosen_categories[0] = "EVバッテリー"

        for category in chosen_categories:
            candidates = suppliers[suppliers["component_category"] == category]
            if candidates.empty:
                continue
            supplier = candidates.sample(n=1, random_state=seq).iloc[0]
            criticality = rng.choice(["Critical", "High", "Medium"])
            rows.append({
                "map_id": f"MAP{seq:04d}",
                "model_id": model["model_id"],
                "model_name": model["model_name"],
                "oem": model["oem"],
                "component_category": category,
                "supplier_id": supplier["supplier_id"],
                "supplier_name": supplier["supplier_name"],
                "criticality": criticality,
            })
            seq += 1
    return pd.DataFrame(rows)


def generate_inventory(suppliers: pd.DataFrame) -> pd.DataFrame:
    """在庫データ（CRUD 管理画面のデモ対象テーブル）"""
    rng = _rng()
    rows = []
    seq = 1
    base_date = date(2026, 6, 1)
    for _, sup in suppliers.iterrows():
        n_items = rng.randint(1, 3)
        for _ in range(n_items):
            qty = rng.randint(500, 50000)
            reorder_point = int(qty * rng.uniform(0.1, 0.35))
            unit_cost = round(rng.uniform(2.5, 850.0), 2)
            last_updated = base_date - timedelta(days=rng.randint(0, 45))
            rows.append({
                "inventory_id": f"INV{seq:04d}",
                "supplier_id": sup["supplier_id"],
                "supplier_name": sup["supplier_name"],
                "component_category": sup["component_category"],
                "component_name": f"{sup['component_category']} - Lot{seq:03d}",
                "warehouse_location": rng.choice(WAREHOUSE_LOCATIONS),
                "quantity_on_hand": qty,
                "reorder_point": reorder_point,
                "unit_cost_usd": unit_cost,
                "last_updated": last_updated.isoformat(),
            })
            seq += 1
    return pd.DataFrame(rows)


def generate_all() -> dict:
    """全テーブルを生成し、テーブル名 → DataFrame の辞書で返す"""
    suppliers = generate_suppliers()
    ports = generate_ports()
    plants = generate_assembly_plants()
    vehicle_models = generate_vehicle_models()
    routes = generate_logistics_routes(suppliers, ports, plants)
    component_map = generate_vehicle_component_map(vehicle_models, suppliers)
    inventory = generate_inventory(suppliers)

    return {
        "suppliers": suppliers,
        "ports": ports,
        "assembly_plants": plants,
        "vehicle_models": vehicle_models,
        "logistics_routes": routes,
        "vehicle_component_map": component_map,
        "inventory": inventory,
    }


if __name__ == "__main__":
    tables = generate_all()
    for name, df in tables.items():
        print(f"=== {name}: {len(df)} 件 ===")
        print(df.head(3))
        print()
