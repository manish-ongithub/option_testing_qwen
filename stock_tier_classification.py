# ==================== COMPREHENSIVE STOCK TIER CLASSIFICATION ====================
# Classification based on:
# - Average daily options volume
# - Market capitalization
# - Institutional holding
# - Liquidity in options chain

# TIER 1: Ultra High Liquidity (Top 30 stocks)
# Criteria: Avg daily volume > 100K contracts, Large cap, Very tight spreads
TIER_1_STOCKS = [
    # Large Cap Banks
    "HDFCBANK",
    "ICICIBANK", 
    "AXISBANK",
    "KOTAKBANK",
    "SBIN",
    
    # IT Giants
    "RELIANCE",
    "TCS",
    "INFY",
    "HCLTECH",
    "WIPRO",
    "TECHM",
    "LTI",  # LTIMindtree
    
    # Auto & Industrials
    "MARUTI",
    "M&M",  # Mahindra & Mahindra
    "LT",  # Larsen & Toubro
    "TATAMOTORS",
    
    # Pharma
    "SUNPHARMA",
    "DRREDDY",
    
    # Consumer
    "HINDUNILVR",
    "ITC",
    "BRITANNIA",
    "NESTLEIND",
    "TITAN",
    
    # Telecom & Energy
    "BHARTIARTL",
    "NTPC",
    "POWERGRID",
    "COALINDIA",
    
    # Finance
    "BAJFINANCE",
    "BAJAJFINSV",
    "HDFCLIFE"
]

# TIER 2: High Liquidity (60 stocks)
# Criteria: Avg daily volume 20K-100K contracts, Large/Mid cap
TIER_2_STOCKS = [
    # Banks & NBFCs
    "INDUSINDBK",
    "BANDHANBNK",
    "IDFCFIRSTB",
    "FEDERALBNK",
    "CANBK",  # Canara Bank
    "PNB",  # Punjab National Bank
    "BANKBARODA",
    "BANKINDIA",
    "UNIONBANK",
    "CHOLAFIN",  # Cholamandalam
    "LICHSGFIN",
    "PNBHOUSING",
    "LTFH",  # L&T Finance Holdings
    "MUTHOOTFIN",
    "MANAPPURAM",
    
    # IT & Tech
    "PERSISTENT",
    "COFORGE",
    "MPHASIS",
    "OFSS",  # Oracle Financial Services
    "LTTS",  # L&T Technology Services
    
    # Auto & Auto Components
    "TATASTEEL",
    "HEROMOTOCO",
    "EICHERMOT",
    "BAJAJ-AUTO",
    "TVSMOTOR",
    "ASHOKLEY",
    "APOLLOTYRE",
    "MRF",
    "MOTHERSON",  # Samvardhana Motherson
    "SONACOMS",  # Sona BLW
    
    # Pharma & Healthcare
    "CIPLA",
    "AUROPHARMA",
    "LUPIN",
    "BIOCON",
    "TORNTPHARM",
    "ALKEM",
    "LAURUSLABS",
    "DIVISLAB",
    "ZYDUSLIFE",
    "APOLLOHOSP",
    "MAXHEALTH",
    "FORTIS",
    
    # Industrials & Infra
    "ADANIPORTS",
    "ADANIENT",
    "ADANIGREEN",
    "ADANIENSOL",  # Adani Energy Solutions
    "JSWSTEEL",
    "HINDALCO",
    "VEDL",  # Vedanta
    "TATASTEEL",
    "JINDALSTEL",
    "SAIL",  # Steel Authority of India
    "BHEL",
    "BEL",  # Bharat Electronics
    "HAL",  # Hindustan Aeronautics
    "BHARATFORG",
    "CUMMINSIND",
    
    # Consumer & Retail
    "DABUR",
    "GODREJCP",
    "MARICO",
    "COLPAL",  # Colgate-Palmolive
    "PIDILITE",
    "ASIANPAINT",
    "BERGEPAINT",
    "BATAINDIA",
    "TATACONSUM",
    "DMART",  # Avenue Supermarts
    "TRENT",
    "JUBLFOOD",
    "VARUN",  # Varun Beverages
    
    # Energy & Utilities
    "ONGC",
    "BPCL",
    "IOC",  # Indian Oil
    "GAIL",
    "HINDPETRO",
    "TATAPOWER",
    "POWERGRID",
    "ADANIPOWER",
    "NTPC",
    "NHPC",
    
    # Financials & Insurance
    "SBILIFE",
    "SBICARD",
    "HDFCAMC",
    "ICICIGI",  # ICICI Lombard
    "ICICIPRULI",  # ICICI Pru Life
    "MAXFIN",  # Max Financial Services
    "POLICYBZR",  # PB Fintech
]

# TIER 3: Medium Liquidity (100+ stocks)
# Criteria: Avg daily volume 5K-20K contracts, Mid/Small cap
TIER_3_STOCKS = [
    # Banks & Finance
    "RBLBANK",
    "YESBANK",
    "INDIANB",  # Indian Bank
    "IIFL",  # IIFL Finance
    "JIOFIN",  # Jio Financial Services
    "ABCAPITAL",  # Aditya Birla Capital
    "ANGELONE",
    "MCX",  # Multi Commodity Exchange
    "CDSL",  # Central Depository Services
    "BSE",  # BSE Ltd
    "CAMS",  # Computer Age Management Services
    "KFINTECH",
    "NUVAMA",  # Nuvama Wealth Management
    
    # IT & Consulting
    "CYIENT",
    "KPITTECH",
    "MASTEK",
    
    # Auto Components
    "BOSCHLTD",
    "EXIDEIND",
    "AMARAJABAT",
    "BALKRISIND",
    "ESCORTS",
    "TIINDIA",  # Tube Investments
    "UNOMINDA",
    "KALYANKJIL",  # Kalyan Jewellers
    "KAYNES",  # Kaynes Technology
    
    # Pharma & Healthcare
    "GLENMARK",
    "MANKIND",
    "SYNGENE",
    "LALPATHLAB",
    "METROPOLIS",
    "PIRAMALPHAR",
    
    # Industrials & Manufacturing
    "ABB",
    "SIEMENS",
    "L&TFH",  # L&T Finance
    "VOLTAS",
    "BLUESTARCO",
    "HAVELLS",
    "CROMPTON",
    "POLYCAB",
    "KEI",  # KEI Industries
    "Dixon",  # Dixon Technologies
    "AMBER",  # Amber Enterprises
    "SOLARINDS",  # Solar Industries
    "TITAGARH",  # Titagarh Rail Systems
    "GRSE",  # Garden Reach Shipbuilders
    "MAZDA",  # Mazagon Dock Shipbuilders
    "COCHINSHIP",
    
    # Infrastructure & Real Estate
    "DLF",
    "GODREJPROP",
    "OBEROIRLTY",
    "PRESTIGE",
    "PHOENIXLTD",  # Phoenix Mills
    "LODHA",  # Lodha Developers
    "IRCON",  # IRCON International
    "IRFC",  # Indian Railway Finance Corp
    "RVNL",  # Rail Vikas Nigam
    "IRCTC",  # Indian Railway Catering
    "CONCOR",  # Container Corporation
    "HUDCO",  # Housing & Urban Development
    "NBCC",
    "NCC",
    "PFC",  # Power Finance Corporation
    "RECLTD",  # REC Ltd
    "IREDA",  # Indian Renewable Energy Development
    
    # Energy & Power
    "ADANIPOWER",
    "TORNTPOWER",  # Torrent Power
    "JSW",  # JSW Energy
    "TATAPOWER",
    "SUZLON",
    "JINDALSAW",
    "HINDZINC",  # Hindustan Zinc
    "NMDC",
    "NATIONALUM",  # National Aluminium
    
    # Consumer & Retail
    "IIFL",
    "GODREJIND",
    "COLGATE",
    "EMAMILTD",
    "JUBLPHARMA",
    "RADICO",
    "UNITED",  # United Spirits
    "VMART",
    "SHOPERSTOP",
    "NYKAA",  # FSN E-Commerce Ventures
    "ZOMATO",
    "PAYTM",  # One 97 Communications
    "DELHIVERY",
    "POLICYBZR",
    "INDIAMART",
    
    # Chemicals & Materials
    "UPL",
    "PIIND",  # PI Industries
    "SRF",
    "AARTI",  # Aarti Industries
    "DEEPAKNTR",  # Deepak Nitrite
    "GNFC",  # Gujarat Narmada Valley Fertilizers
    "CHAMBLFERT",  # Chambal Fertilizers
    "COROMANDEL",
    "TATACHEM",
    "GUJGASLTD",  # Gujarat Gas
    "IGL",  # Indraprastha Gas
    "MGL",  # Mahanagar Gas
    
    # Cement & Construction
    "ULTRACEMCO",
    "SHREECEM",
    "AMBUJACEM",
    "ACC",
    "JKCEMENT",
    "DALMIA",  # Dalmia Bharat
    "RAMCOCEM",
    "HEIDELBERG",
    "ORIENTCEM",
    "JKLAKSHMI",
    
    # Metals & Mining
    "APLAPOLLO",  # APL Apollo Tubes
    "JINDAL",
    "JSWENERGY",
    "MOIL",
    "GUJMIN",  # Gujarat Mineral Development
    
    # Telecom & Media
    "INDUSINF",  # Indus Towers
    "IDEA",  # Vodafone Idea
    "GMRINFRA",  # GMR Airports
    "EIDPARRY",
    
    # Diversified
    "IEX",  # Indian Energy Exchange
    "360ONE",  # 360 ONE WAM
    "CREDITACC",  # Creditaccess Grameen
    "AFFLE",
    "ZENSARTECH",
    "ROUTE",
    "EASEMYTRIP",
    "CMSINFO",
    "LTIM",  # LTIMindtree
    
    # Others
    "GLAND",  # Gland Pharma
    "ALEMBIC",
    "GLAXO",
    "PFIZER",
    "ABBOTINDIA",
    "SANOFI",
    "ERIS",
    "ASTRAL",
    "SUPREMEIND",
    "PAGEIND",  # Page Industries
    "RELAXO",
    "BATA",
    "VBL",  # Varun Beverages
    "INDHOTEL",  # Indian Hotels
    "LEMONTREE",
    "ATUL",
    "BALRAMCHIN",
    "NOCIL",
    "THERMAX",
    "CARBORUNIV",
    "GMMPFAUDLR",
    "INOXWIND",
    "PATANJALI",  # Patanjali Foods
    "KRBL",
    "AGRITECH",
    "ADANIENSOL",
    "AUBANK",  # AU Small Finance Bank
    "SAMMAAN",  # Sammaan Capital
    "TATATECH",  # Tata Technologies
    "TATAELXSI",
    "HFCL",
    "PGINVIT",  # PG Electroplast
    "ETERNAL",
    "PETRONET"
]

# ==================== MAPPING FUNCTION ====================

def get_stock_tier(symbol):
    """
    Return tier classification for a stock symbol
    
    Args:
        symbol: Stock symbol (e.g., 'RELIANCE', 'TCS')
        
    Returns:
        str: 'TIER_1', 'TIER_2', or 'TIER_3'
    """
    symbol_upper = symbol.upper()
    
    # Check Tier 1
    if symbol_upper in TIER_1_STOCKS:
        return 'TIER_1'
    
    # Check Tier 2
    if symbol_upper in TIER_2_STOCKS:
        return 'TIER_2'
    
    # Default to Tier 3 (includes all other F&O stocks)
    return 'TIER_3'


def get_thresholds_for_stock(symbol):
    """
    Get volume and OI thresholds based on stock tier
    
    Args:
        symbol: Stock symbol
        
    Returns:
        dict: {'tier': str, 'volume': int, 'oi_change': int}
    """
    tier = get_stock_tier(symbol)
    
    thresholds = {
        'TIER_1': {'volume': 800, 'oi_change': 150},
        'TIER_2': {'volume': 400, 'oi_change': 75},
        'TIER_3': {'volume': 200, 'oi_change': 30}
    }
    
    return {
        'tier': tier,
        'volume': thresholds[tier]['volume'],
        'oi_change': thresholds[tier]['oi_change']
    }


# ==================== STATISTICS ====================

def print_tier_statistics():
    """Print statistics about tier distribution"""
    print("=" * 60)
    print("STOCK TIER DISTRIBUTION")
    print("=" * 60)
    print(f"Tier 1 (Ultra High Liquidity): {len(TIER_1_STOCKS)} stocks")
    print(f"Tier 2 (High Liquidity):       {len(TIER_2_STOCKS)} stocks")
    print(f"Tier 3 (Medium Liquidity):     {len(TIER_3_STOCKS)} stocks")
    print(f"Total F&O Stocks:              {len(TIER_1_STOCKS) + len(TIER_2_STOCKS) + len(TIER_3_STOCKS)}")
    print("=" * 60)
    print()
    print("THRESHOLDS BY TIER:")
    print("-" * 60)
    print("Tier 1: Volume ≥ 800  | OI Change ≥ 150")
    print("Tier 2: Volume ≥ 400  | OI Change ≥ 75")
    print("Tier 3: Volume ≥ 200  | OI Change ≥ 30")
    print("=" * 60)


# ==================== EXAMPLE USAGE ====================

if __name__ == "__main__":
    # Print statistics
    print_tier_statistics()
    
    # Test some stocks
    test_symbols = ['RELIANCE', 'SBIN', 'DIXON', 'NIFTY', 'UNKNOWN']
    
    print("\nTEST CLASSIFICATIONS:")
    print("-" * 60)
    for symbol in test_symbols:
        tier_info = get_thresholds_for_stock(symbol)
        print(f"{symbol:15} | {tier_info['tier']:10} | Vol: {tier_info['volume']:4} | OI: {tier_info['oi_change']:3}")
    print("=" * 60)
    
    # Show Tier 1 stocks
    print("\nTIER 1 STOCKS (Ultra High Liquidity):")
    print("-" * 60)
    for i, stock in enumerate(sorted(TIER_1_STOCKS), 1):
        print(f"{i:2}. {stock}", end="   ")
        if i % 4 == 0:
            print()
    print()
    print("=" * 60)