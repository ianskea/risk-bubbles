
def generate_regime_card(breadth_status, btc_spx, btc_gold, vol_val, vol_status):
    """
    Generates the "Market Regime (Cowen)" card based on inputs.
    """
    
    # --- 1. Header Logic ---
    # Determine Regime Label
    # Logic: 
    #   Narrow Breadth -> "Mixed" or "Transition"
    #   Inflation Hedge (High Gold corr) -> "Macro-Driven"
    #   Crypto-Native (Low Corrs) -> "Crypto-Native"
    
    regime_label = "Mixed" # Default
    if abs(btc_spx) < 0.3 and abs(btc_gold) < 0.3:
        regime_label = "Crypto-Native"
    elif btc_gold > 0.5:
        regime_label = "Macro-Driven (Defensive)"
    elif btc_spx > 0.5:
        regime_label = "Risk-On (Liquidity)"
        
    # If Narrow Breadth, append/modify
    is_narrow = "Narrow" in breadth_status or "Weak" in breadth_status or "CONTRACTING" in breadth_status
    if is_narrow:
        if regime_label == "Risk-On (Liquidity)":
            regime_label = "Mixed (Narrow Liquidity)"
        elif regime_label == "Crypto-Native":
            regime_label = "Crypto-Native (Narrow)"

    # Confidence
    confidence = "Med" # Default
    # Downgrade if conflicting signals (e.g. Risk On but High Vol + Narrow)
    # Upgrade if everything aligns (e.g. Broad Breadth + Risk On + Low Vol)
    
    # Stance
    stance = "Hold Risk" # Default
    if "COMPRESSION" in vol_status:
        stance = "Wait for Breakout"
    elif is_narrow and "Rise" in breadth_status: # e.g. Price rise but narrow
        stance = "Scale / Risk-controlled"
    elif is_narrow:
        stance = "De-risk / Consolidation"

    header = f"Mode: ⚠️ {regime_label} | Confidence: {confidence} | Stance: {stance}"
    
    # --- 2. Breadth Block ---
    # Badge
    b_badge = "🟡"
    if "EXPANDING" in breadth_status: b_badge = "🟢"
    elif is_narrow: b_badge = "🟠"
    
    # Meaning
    b_meaning = "Participation is average."
    if is_narrow: b_meaning = "rally held up by fewer names → fragile risk-on"
    elif "EXPANDING" in breadth_status: b_meaning = "Broad participation confirms trend strength"
    
    # Do
    b_do = "Monitor specific sectors."
    if is_narrow: b_do = "avoid broad risk adds; prefer highest-conviction only"
    elif "EXPANDING" in breadth_status: b_do = "Scale into strength; look for laggards"
    
    breadth_block = (
        f"Breadth: {b_badge} {breadth_status.split('(')[0].strip()}\n"
        f"Meaning: {b_meaning}\n"
        f"Do: {b_do}"
    )

    # --- 3. Correlations Block ---
    # Logic
    c_badge = "🟣" # Default Crypto-Native
    c_desc = "Crypto-Native (decoupled)"
    c_meaning = "crypto driven by crypto flows; macro hedges unreliable"
    c_do = "follow crypto signals; don't assume stock moves predict BTC"
    
    if btc_spx > 0.5:
        c_badge = "🟢"
        c_desc = "Risk-On Proxy"
        c_meaning = "BTC moving with liquidity conditions"
        c_do = "Monitor S&P 500 levels for confluence"
    elif btc_gold > 0.5:
        c_badge = "🟡"
        c_desc = "Digital Gold Proxy"
        c_meaning = "BTC acting as inflation hedge / defensive"
        c_do = "Monitor Real Yields and DXY"
    elif btc_spx < -0.5:
        c_badge = "🟠" # Inverse risk?
        c_desc = "Inverse Risk (Hedge?)"
        c_meaning = "BTC moving opposite to equities (Rare)"
        c_do = "Treat as non-correlated diversifier"

    correlations_block = (
        f"Correlations: {c_badge} {c_desc}\n"
        f"BTC↔S&P: {btc_spx:.2f}\n"
        f"BTC↔Gold: {btc_gold:.2f}\n"
        f"Meaning: {c_meaning}\n"
        f"Do: {c_do}"
    )

    # --- 4. Volatility Block ---
    # Logic
    v_badge = "🟡"
    if "COMPRESSION" in vol_status: v_badge = "🔥"
    elif "ELEVATED" in vol_status or "High" in vol_status: v_badge = "🟠"
    
    v_label = "Normal"
    if "COMPRESSION" in vol_status: v_label = "Squeeze (big move likely)"
    elif "ELEVATED" in vol_status: v_label = "Elevated Risk"
    
    v_meaning = "Volatility is within normal bounds"
    v_do = "Standard risk management"
    
    if "COMPRESSION" in vol_status:
        v_meaning = "probability of sharp move rising (direction unknown)"
        v_do = "reduce leverage; scale entries; respect stops / max loss"
        
    vol_block = (
        f"Volatility: {v_badge} {v_label} | 180d vol: {vol_val:.1%}\n"
        f"Meaning: {v_meaning}\n"
        f"Do: {v_do}"
    )

    # --- 5. Footer ---
    # Implies
    implies = []
    if is_narrow and "COMPRESSION" in vol_status:
        implies.append("- Expect sharp move; participation may stay narrow")
    elif is_narrow:
        implies.append("- Rally is fragile; breadth needs to expand")
    
    if "Crypto-Native" in c_desc:
        implies.append("- Macro signals less predictive for BTC/ETH")
        
    implies_text = "What this implies\n" + "\n".join(implies) if implies else "What this implies\n- Standard market conditions"

    # What to do
    todos = []
    if "COMPRESSION" in vol_status:
        todos.append("- Avoid leverage; set hard max drawdown")
    if is_narrow:
        todos.append("- Prefer highest conviction; avoid broad adds")
    if not todos:
        todos.append("- Trade standard setup")
        
    todo_text = "What to do now\n" + "\n".join(todos)

    # Final Assembly
    card = f"""
MARKET REGIME (Cowen Model) — Operating mode for the next 1–4 weeks
{header}
==================================================
{breadth_block}
--------------------------------------------------
{correlations_block}
--------------------------------------------------
{vol_block}
==================================================
{implies_text}

{todo_text}
"""
    return card

# Test Cases matching User Data
print(generate_regime_card(
    breadth_status="NEUTRAL (Rally is Narrow)", # Simulated from logic
    btc_spx=-0.52,
    btc_gold=-0.73,
    vol_val=0.432,
    vol_status="EXTREME COMPRESSION"
))
