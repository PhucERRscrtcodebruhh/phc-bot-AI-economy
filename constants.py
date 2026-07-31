# constants.py
# ==========================================
# FILE ĐỊNH NGHĨA HỆ THỐNG KINH TẾ (METADATA)
# ==========================================

KESLING_ICON = "<:kesling:1434181800539979848>" 


price['kesling_stone'] = 250 


emoji_icon['kesling_stone'] = '<:keslings_stone:1433843943405125725>'

# Định nghĩa cửa hàng Thú Cưng
PET_SHOP = {
    "meo_than_tai": {
        "name": "Mèo Thần Tài",
        "emoji": "🐱",
        "price": 50000,
        "description": "Tự động nhặt 1-2 Kesling Coin mỗi 5 phút."
    },
    "ca_kesling": {
        "name": "Cá Kesling",
        "emoji": "🐟✨",
        "price": 200000,
        "description": "Mỗi 1 tiếng đào 1 quặng ngẫu nhiên (10% ra 20~100 Kesling Stone)."
    }
}


FISH_POOL = {
    "common": {
        "ca_ro": {"price": 15, "emoji": "🐟", "name": "Cá Rô"},
        "ca_chep": {"price": 25, "emoji": "🐠", "name": "Cá Chép"},
        "ca_qua": {"price": 35, "emoji": "🐡", "name": "Cá Quả"},
        "ca_me": {"price": 10, "emoji": "🐟", "name": "Cá Mè"},
        "ca_diec": {"price": 18, "emoji": "🐟", "name": "Cá Diếc"}
    },
    "special": {
        "ca_hoi": {"price": 120, "emoji": "🍣", "name": "Cá Hồi"},
        "ca_ngu": {"price": 250, "emoji": "🦈", "name": "Cá Ngừ"},
        "ca_map_con": {"price": 500, "emoji": "🦈✨", "name": "Cá Mập Con"},
        "ca_rong_vang": {"price": 1000, "emoji": "🐉", "name": "Cá Rồng Vàng"},
        "ca_koi": {"price": 350, "emoji": "🎏", "name": "Cá Koi"},
        "ca_he": {"price": 80, "emoji": "🐠", "name": "Cá Hề"},
        "ca_kiem": {"price": 400, "emoji": "⚔️", "name": "Cá Kiếm"},
        "ca_duoi": {"price": 300, "emoji": "🐙", "name": "Cá Đuối"},
        "ca_ngua": {"price": 450, "emoji": "🐴", "name": "Cá Ngựa"},
        "ca_voi_xanh": {"price": 1500, "emoji": "🐳", "name": "Cá Voi Xanh"}
    }
}

# Tỷ lệ xuất hiện của các loại quặng (Trọng số đào mỏ)
ore = {
    'dirt': 1000, 'stone': 4000, 'calcite': 500, 'bauxile': 12, 'iron': 100,
    'copper': 5, 'sliver': 3, 'gold_ore': 1, 'coal': 300, 'quartz': 25,
    'feldspar': 20, 'gypsum': 18, 'halite': 15, 'fluorite': 12, 'apatite': 10,
    'magnetite': 8, 'hematite': 7, 'galena': 6, 'sphalerite': 5, 'chalcopyrite': 4,
    'cassiterite': 4, 'bauxite': 3, 'ilmenite': 3, 'rutile': 3, 'molybdenite': 2,
    'cinnabar': 2, 'pyrite': 2, 'talc': 2, 'graphite': 2, 'chromite': 2,
    'uraninite': 1, 'pitchblende': 1, 'columbite': 1, 'tantalite': 1, 'wolframite': 1,
    'scheelite': 1, 'zircon': 1, 'barite': 1, 'spodumene': 1, 'lepidolite': 1,
    'beryl': 1, 'tourmaline': 1, 'corundum': 1, 'diamond': 1
}

# Giá bán cơ bản của các loại vật phẩm (Quặng, Thỏi kim loại, Phế liệu)
price = {
    'dirt': 1, 'stone': 2, 'calcite': 3, 'coal': 4, 'bauxile': 8, 'iron': 10,
    'copper': 15, 'silver': 30, 'gold': 50, 'gold_ore': 12, 'quartz': 6,
    'feldspar': 5, 'gypsum': 4, 'halite': 3, 'fluorite': 8, 'apatite': 7,
    'magnetite': 12, 'hematite': 10, 'galena': 15, 'sphalerite': 14, 'chalcopyrite': 16,
    'cassiterite': 20, 'bauxite': 8, 'ilmenite': 18, 'rutile': 22, 'molybdenite': 25,
    'cinnabar': 28, 'pyrite': 6, 'talc': 3, 'graphite': 5, 'chromite': 20,
    'uraninite': 40, 'pitchblende': 42, 'columbite': 35, 'tantalite': 38,
    'wolframite': 30, 'scheelite': 28, 'zircon': 25, 'barite': 6, 'spodumene': 32,
    'lepidolite': 30, 'beryl': 35, 'tourmaline': 40, 'corundum': 45, 'diamond': 100,
    'iron_ingot': 25, 'copper_ingot': 20, 'gold_ingot': 80, 'silver_ingot': 40,
    'stone_brick': 5, 'clay': 2, 'slag': 0,
    # Đồ nghề phụ trợ nông nghiệp/công việc trong shop
    'ruong': 50000,
    'giao_an': 15000,
    'bo_dung_cu': 20000,
    'tui_y_te': 35000
}

# Icon hiển thị của từng loại quặng & đồ nghề
emoji_icon = {
    'dirt': '<:dirt:1425134897282027533>', 'stone': '<:stoness:1425135738134990869>',
    'calcite': '<:calcite:1425860868041736382>', 'bauxile': '<:bauxile:1425860810843885618>',
    'iron': '<:iron:1425860778124382400>', 'copper': '🧱', 'sliver': '<:iron:1425860778124382400>',
    'gold': '<:gold:1426776771335815220>', 'quartz': '<:Quartz:1425864050037887106>',
    'feldspar': '<:feldspar:1426776743158743060>', 'gypsum': '<:calcite:1425860868041736382>',
    'halite': '<:halite:1426776827044696115>', 'fluorite': '<:fluorite:1425869841927245914>',
    'apatite': '<:Apatite:1426778037390934058>', 'magnetite': '<:Magnetite:1425869000776220763>',
    'hematite': '<:hematite:1425860840841547898>', 'galena': '<:galena:1426816156655943701>',
    'sphalerite': '<:sphalerite:1426816178596216944>', 'chalcopyrite': '<:Chalcopyrite:1425868680495108137>',
    'cassiterite': '<:Cassiterite:1426813557533573140>', 'bauxite': '<:bauxile:1425860810843885618>',
    'ilmenite': '<:Ilmenite:1425869295681802372>', 'rutile': '<:rutite:1426817592194236506>',
    'molybdenite': '<:Molybdenite:1426817671097357357>', 'cinnabar': '<:cinnabar:1434922309554012180>',
    'pyrite': '<:pyrite:1426817047760998481>', 'talc': '<:talc:1434922300997636136>',
    'graphite': '<:graphite:1434560758628225206>', 'coal': '<:coal:1434560760930893845>',
    'chromite': '⚫', 'uraninite': '<:uranite:1434922298795888791>', 'pitchblende': '<:uranite:1434922298795888791>',
    'columbite': '🪨', 'tantalite': '🪨', 'wolframite': '🪨', 'scheelite': '🪨', 'zircon': '💎',
    'barite': '🪨', 'spodumene': '💎', 'lepidolite': '💎', 'beryl': '<:beryl:1434922296505532496>',
    'tourmaline': '💎', 'corundum': '💎', 'diamond': '💎',
    'iron_ingot': '<:iron_ingot:1434922305703907492>', 'copper_ingot': '<:copper_ingot:1434922303782785157>',
    'gold_ingot': '<:gold_bar:1434922294261715034>', 'silver_ingot': '🥈',
    'stone_brick': '<:brick:1427000000000000000>', 'clay': '🧱', 'slag': '<:slag:1434922307846934579>',
    'default_pickaxe': '🪨', 'wood_pickaxe': '<:Wooden_Pickaxe:1434556115655594126>',
    'stone_pickaxe': '<:Stone_Pickaxe:1434556117773451365>', 'iron_pickaxe': '<:Iron_Pickaxe:1434556113147269302>',
    'gold_pickaxe': '<:Golden_Pickaxe:1434556111209631917>', 'diamond_pickaxe': '<:Diamond_Pickaxe:1434556109053497486>',
    'ruong': '🚜', 'giao_an': '📚', 'bo_dung_cu': '🔧', 'tui_y_te': '🩺'
}

# Các loại cuốc trong shop đào mỏ
PICKAXES = {
    'default_pickaxe': {'min_multiplier': 1.0, 'max_multiplier': 1.0, 'emoji': '🪨','price': 0},
    'wood_pickaxe': {'min_multiplier': 1.1, 'max_multiplier': 1.5, 'emoji': '<:Wooden_Pickaxe:1434556115655594126>','price': 10000},
    'stone_pickaxe': {'min_multiplier': 1.5, 'max_multiplier': 2.3, 'emoji': '<:Stone_Pickaxe:1434556117773451365>','price': 50000},
    'iron_pickaxe': {'min_multiplier': 2.4, 'max_multiplier': 3.6, 'emoji': '<:Iron_Pickaxe:1434556113147269302>','price': 150000},
    'gold_pickaxe': {'min_multiplier': 3.7, 'max_multiplier': 4.2, 'emoji': '<:Golden_Pickaxe:1434556111209631917>','price': 2000000},
    'diamond_pickaxe': {'min_multiplier': 4.8, 'max_multiplier': 6.9, 'emoji': '<:Diamond_Pickaxe:1434556109053497486>','price': 15000000},
}

# Tên viết tắt tiếng Việt không dấu để gõ lệnh `shop buy` cho nhanh
PICKAXE_ALIASES = {
    'wood_pickaxe': 'cupgo', 
    'stone_pickaxe': 'cupda', 
    'iron_pickaxe': 'cupsat',
    'gold_pickaxe': 'cupvang', 
    'diamond_pickaxe': 'cupkimcuong',
    'ruong': 'ruong',
    'giao_an': 'giaoan',
    'bo_dung_cu': 'bodungcu',
    'tui_y_te': 'tuiyte'
}

# Danh sách nông sản
crops = {
    'wheat':     {'grow_time': 180, 'base_yield': 3, 'price': 15, 'emoji': '🌾'},
    'carrot':    {'grow_time': 240, 'base_yield': 2, 'price': 25, 'emoji': '🥕'},
    'potato':    {'grow_time': 300, 'base_yield': 4, 'price': 20, 'emoji': '🥔'},
    'tomato':    {'grow_time': 360, 'base_yield': 3, 'price': 35, 'emoji': '🍅'},
    'corn':      {'grow_time': 420, 'base_yield': 2, 'price': 50, 'emoji': '🌽'},
}

DICE_EMOJIS = {
    1: '<:1_:1519595163607891978>',
    2: '<:2_:1519595165356920912>',
    3: '<:3_:1519595167139500032>',
    4: '<:4_:1519595170155462676>',
    5: '<:5_:1519595172080390154>',
    6: '<:6_:1519595174081200188>'
}

BAUCUA_MAP = {
    'nai': {'name': 'Nai', 'emoji': '🦌'},
    'bau': {'name': 'Bầu', 'emoji': '🧉'},
    'ga': {'name': 'Gà', 'emoji': '🐓'},
    'tom': {'name': 'Tôm', 'emoji': '🦐'},
    'ca': {'name': 'Cá', 'emoji': '🐟'},
    'cua': {'name': 'Cua', 'emoji': '🦀'}
}




# Nhóm các danh mục trong Help menu
HELP_CATEGORIES = {
    "⛏️ Khai Thác & Chế Tạo": ["mine", "bag", "sell", "listore", "checkgia", "luyenkim", "taiche", "shop"],
    "🎲 Trò Chơi giải trí": ["taixiu", "trieuphu", "cf", "cauca"],
    "👤 Tài Khoản & Tiền Tệ": ["me", "acc", "give", "daily", "tktocoin", "lb"],
    "🏭 Kinh Tế Vi Mô": ["pwork"],
    "🧬 Giả Lập Số Phận": ["cuocdoi"],
    "⚙️ Hệ Thống & Admin": ["ping", "quang"]
}

# =======================================================
# LOGIC TỰ ĐỘNG CẬP NHẬT (Không cần chỉnh sửa phần dưới này)
# =======================================================

# Tự động gộp giá bán & emoji nông sản vào danh sách chung
for crop_name, data in crops.items():
    price[crop_name] = data['price']
    emoji_icon[crop_name] = data['emoji']

# Tự động gộp giá bán & emoji cá vào danh sách chung
for category, fish_list in FISH_POOL.items():
    for fish_id, info in fish_list.items():
        price[fish_id] = info["price"]
        emoji_icon[fish_id] = info["emoji"]