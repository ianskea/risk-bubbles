"""
Sector Intelligence Configuration
Defines assets by sector, along with sector-specific thresholds and behaviors.
"""
# Date when the sector specifics were last reviewed
LAST_UPDATED = "2026-05-20"

# [NEW] Bitcoin On-Chain Floors (Based on Cowen/On-Chain Research)
# These are dynamic but updated here for current macro context.
BTC_ON_CHAIN_FLOORS = {
    "Realized Price": 55000,
    "Balance Price": 40000
}

SECTOR_INTELLIGENCE = {
    "Crypto": {
        "danger_zone_threshold": 0.85,
        "fetch_santiment": True,
        "sector_context": "High-beta digital assets. Highly sensitive to global liquidity and M2 expansion.",
        "assets": {
            "Bitcoin": "BTC-USD",
            "Ethereum": "ETH-USD",
            "Cardano": "ADA-USD"
        }
    },
    "Crypto_Rotations": {
        "danger_zone_threshold": 0.85,
        "fetch_santiment": False,
        "sector_context": "Crypto cross-pairs (Capital Waterfall). Tracks liquidity rotation from BTC into ETH and Alts. High risk means the altcoin cycle is exhausted against BTC.",
        "assets": {
            "ETH / BTC": "ETH-BTC",
            "ADA / BTC": "ADA-BTC",
            "ADA / ETH": "ADA-ETH"
        }
    },
    "Commodities": {
        "danger_zone_threshold": 0.75,
        "fetch_santiment": False,
        "sector_context": "Global hard assets. Driven by inflation expectations, real yields, and geopolitical risk.",
        "assets": {
            "Gold": "GC=F",
            "Silver": "SI=F"
        }
    },
    "ASX_Miners": {
        "danger_zone_threshold": 0.75,
        "fetch_santiment": False,
        "sector_context": "Australian Large-Cap Miners (ASX). Highly correlated to global copper/iron ore demand and Chinese economic data.",
        "assets": {
            "BHP Group": "BHP.AX",
            "Rio Tinto": "RIO.AX",
            "Fortescue": "FMG.AX",
            "Mineral Resources": "MIN.AX",
            "Pilbara Minerals": "PLS.AX",
            "South32": "S32.AX",
            "IGO Ltd": "IGO.AX"
        }
    },
    "ASX_Financials_Other": {
        "danger_zone_threshold": 0.80,
        "fetch_santiment": False,
        "sector_context": "Australian Financials and domestic Large Caps. Sensitive to RBA rates and domestic economic health.",
        "assets": {
            "Macquarie Group": "MQG.AX",
            "SiteMinder": "SDR.AX",
            "Telstra": "TLS.AX"
        }
    },
    "Global_Tech_ETFs": {
        "danger_zone_threshold": 0.80,
        "fetch_santiment": False,
        "sector_context": "Global Technology and Semiconductor equities. Sensitive to US Treasury yields and AI CapEx trends.",
        "assets": {
            "Global X Semi": "SEMI.AX",
            "Global X FANG+": "FANG.AX",
            "Global X Robots": "RBTZ.AX",
            "BetaShares NDQ": "NDQ.AX"
        }
    },
    "Regional_Equities_ETFs": {
        "danger_zone_threshold": 0.80,
        "fetch_santiment": False,
        "sector_context": "Broad regional equities (Asia/Europe). Driven by global growth and regional fiscal policies.",
        "assets": {
            "BetaShares Asia": "ASIA.AX",
            "Vanguard Europe": "VEQ.AX",
            "iShares Asia 50": "IAA.AX"
        }
    },
    "Thematic_Global_ETFs": {
        "danger_zone_threshold": 0.80,
        "fetch_santiment": False,
        "sector_context": "Global thematic equities (Healthcare, Energy, Infrastructure). Defensive or cyclical depending on the theme.",
        "assets": {
            "Battery Tech": "ACDC.AX",
            "Global Infrastructure": "IFRA.AX",
            "Global Healthcare": "IXJ.AX",
            "Global Energy": "FUEL.AX"
        }
    },
    "Aussie_Domestic_ETFs": {
        "danger_zone_threshold": 0.80,
        "fetch_santiment": False,
        "sector_context": "Australian domestic sector ETFs (Property, Resources). Heavily tied to domestic policy and RBA rates.",
        "assets": {
            "BetaShares Mining Resources": "QRE.AX",
            "Vanguard Prop": "VAP.AX"
        }
    }
}
