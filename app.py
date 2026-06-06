import base64
from pathlib import Path
from urllib.parse import parse_qs, quote_plus, urlparse

import requests
import streamlit as st

from src.analysis_service import analyze_coin, ask_agent, find_coins, scan_coins, scan_market
from src.config import settings
from src.journal import recent_entries
from src.models import AnalysisRequest, AssistantRequest, MarketScanRequest, ScanRequest


st.set_page_config(page_title="CoinPilot AI", layout="wide")

st.markdown(
    """
    <style>
    :root {
        --primary-navy: #0F172A;
        --signal-green: #10B981;
        --insight-blue: #3B82F6;
        --alert-amber: #F59E0B;
        --surface-light: #F8FAFC;
        --slate-gray: #64748B;
    }
    .stApp {background: #F8FAFC;}
    .block-container {padding-top: 1.1rem; max-width: 1180px;}
    section[data-testid="stSidebar"] {
        background: #0F172A;
        border-right: 1px solid rgba(255,255,255,0.08);
    }
    section[data-testid="stSidebar"] h1,
    section[data-testid="stSidebar"] h2,
    section[data-testid="stSidebar"] h3,
    section[data-testid="stSidebar"] p,
    section[data-testid="stSidebar"] span {color: #E5EDF7;}
    section[data-testid="stSidebar"] label {color: #D5E0EC !important; font-weight: 700;}
    section[data-testid="stSidebar"] input,
    section[data-testid="stSidebar"] textarea {
        color: #0F172A !important;
        background: #FFFFFF !important;
        caret-color: #0F172A !important;
    }
    section[data-testid="stSidebar"] input::placeholder,
    section[data-testid="stSidebar"] textarea::placeholder {color: #64748B !important;}
    section[data-testid="stSidebar"] div[data-baseweb="input"] {
        background: #FFFFFF;
        border: 1px solid #CBD5E1;
        border-radius: 8px;
    }
    section[data-testid="stSidebar"] div[data-baseweb="select"] > div {
        background: #FFFFFF;
        border: 1px solid #CBD5E1;
        border-radius: 8px;
    }
    section[data-testid="stSidebar"] div[data-baseweb="select"] span {color: #0F172A !important;}
    section[data-testid="stSidebar"] [role="radio"] span {color: #E5EDF7 !important;}
    section[data-testid="stSidebar"] .stSlider [data-testid="stThumbValue"] {color: #E5EDF7 !important;}
    section[data-testid="stSidebar"] .stSlider div[role="slider"] {background-color: #10B981 !important;}
    .app-header {
        background: linear-gradient(135deg, #0F172A 0%, #18233B 58%, #0B6B5B 100%);
        color: white;
        border-radius: 12px;
        padding: 1rem 1.15rem;
        margin: 0.2rem 0 1rem 0;
        box-shadow: 0 14px 30px rgba(15,23,42,0.12);
    }
    .brand-row {
        display: flex;
        align-items: center;
        gap: 1rem;
    }
    .brand-logo {
        width: 54px;
        height: 54px;
        border-radius: 12px;
        object-fit: cover;
        box-shadow: 0 10px 24px rgba(0,0,0,0.22);
    }
    .app-header h1 {margin: 0; font-size: 2rem; letter-spacing: 0;}
    .brand-ai {color: #10B981;}
    .muted {color: #dbe7ef; font-size: 0.95rem;}
    .tagline {
        color: #BAC7D9;
        font-weight: 800;
        letter-spacing: 0.18rem;
        margin-top: 0.2rem;
        text-transform: uppercase;
        font-size: 0.72rem;
    }
    .section-note {
        background: #FFFFFF;
        border: 1px solid #e2e8f0;
        border-radius: 8px;
        padding: 0.9rem 1rem;
        margin: 0.5rem 0 1rem 0;
    }
    .feature-strip {
        display: grid;
        grid-template-columns: repeat(5, minmax(0, 1fr));
        gap: 0;
        margin: 1rem 0;
        background: #FFFFFF;
        border: 1px solid #E2E8F0;
        border-radius: 10px;
        overflow: hidden;
        box-shadow: 0 10px 24px rgba(15,23,42,0.055);
    }
    .feature-card {
        background: transparent;
        border-right: 1px solid #E2E8F0;
        border-radius: 0;
        padding: 0.95rem 1rem;
        min-height: 102px;
        box-shadow: none;
    }
    .feature-card:last-child {border-right: none;}
    .feature-card:nth-child(2) .feature-icon {color: #10B981;}
    .feature-card:nth-child(4) .feature-icon {color: #F59E0B;}
    .feature-card:nth-child(5) .feature-icon {color: #64748B;}
    .feature-card:nth-child(3) .feature-icon {color: #3B82F6;}
    .feature-card:nth-child(1) .feature-icon {color: #0F172A;}
    .metric-band {
        display: grid;
        grid-template-columns: repeat(3, minmax(0, 1fr));
        gap: 0.85rem;
        margin-top: 1rem;
    }
    .feature-icon {
        font-size: 1.5rem;
        font-weight: 900;
        color: #3B82F6;
        margin-bottom: 0.3rem;
    }
    .feature-title {
        color: #0F172A;
        font-size: 0.84rem;
        font-weight: 900;
        text-transform: uppercase;
        margin-bottom: 0.2rem;
    }
    .feature-copy {color: #64748B; font-size: 0.86rem;}
    .scanner-hero {
        background: #FFFFFF;
        border: 1px solid #DDE6F2;
        border-radius: 12px;
        padding: 1rem 1.1rem;
        box-shadow: 0 10px 24px rgba(15,23,42,0.055);
        margin-bottom: 1rem;
    }
    .scanner-title {
        color: #0F172A;
        font-weight: 900;
        font-size: 1.1rem;
        margin-bottom: 0.25rem;
    }
    .scanner-copy {color: #64748B; font-size: 0.94rem;}
    .pill {
        display: inline-block;
        border-radius: 999px;
        padding: 0.25rem 0.65rem;
        font-size: 0.8rem;
        font-weight: 700;
        border: 1px solid #d8dee8;
        background: #f7f9fc;
        color: #253044;
    }
    .pill-buy {background: #eaf7ef; color: #17633a; border-color: #bfe7ce;}
    .pill-hold {background: #fff7e6; color: #7a4b00; border-color: #f2d39b;}
    .pill-avoid {background: #fdecec; color: #8c1d18; border-color: #f2b8b5;}
    h2, h3 {color: #0F172A;}
    div[data-testid="stAlert"] {
        border-radius: 8px;
    }
    div[data-testid="stAlert"] p {line-height: 1.45;}
    div[data-testid="stMetric"] {
        background: #ffffff;
        border: 1px solid #e6eaf0;
        border-radius: 8px;
        padding: 14px 16px;
        box-shadow: 0 6px 14px rgba(15,23,42,0.035);
    }
    div[data-testid="stTabs"] button p {
        color: #0F172A;
        font-weight: 800;
    }
    @media (max-width: 900px) {
        .feature-strip {grid-template-columns: 1fr;}
        .feature-card {border-right: none; border-bottom: 1px solid #E2E8F0;}
        .feature-card:last-child {border-bottom: none;}
        .app-header h1 {font-size: 1.7rem;}
        .brand-row {align-items: flex-start;}
    }
    </style>
    """,
    unsafe_allow_html=True,
)


COIN_CHOICES = {
    "BTC": "bitcoin",
    "ETH": "ethereum",
    "SOL": "solana",
    "Custom": "",
}


APP_DIR = Path(__file__).resolve().parent
BACKEND_NOTICE = (
    "The live app is running in dashboard-only mode. It can still analyze coins, "
    "scan the market, save journal entries, and use AI explanations."
)


def image_data_uri(path: str | Path) -> str:
    image_path = Path(path)
    encoded = base64.b64encode(image_path.read_bytes()).decode("utf-8")
    return f"data:image/png;base64,{encoded}"


def recommendation_class(recommendation: str) -> str:
    if recommendation == "Buy Setup":
        return "pill-buy"
    if recommendation == "Sell / Avoid":
        return "pill-avoid"
    return "pill-hold"


def recommendation_badge(recommendation: str) -> None:
    css_class = recommendation_class(recommendation)
    st.markdown(f"<span class='pill {css_class}'>{recommendation}</span>", unsafe_allow_html=True)



def model_to_dict(value):
    if hasattr(value, "model_dump"):
        return value.model_dump()
    return value


def local_post(path: str, payload: dict) -> dict:
    if path == "/analyze":
        return model_to_dict(analyze_coin(AnalysisRequest(**payload)))
    if path == "/scan":
        return model_to_dict(scan_coins(ScanRequest(**payload)))
    if path == "/scan/market":
        return model_to_dict(scan_market(MarketScanRequest(**payload)))
    if path == "/agent/chat":
        return model_to_dict(ask_agent(AssistantRequest(**payload)))
    raise RuntimeError("This dashboard action is not available.")


def local_get(path: str) -> dict | list:
    parsed_path = urlparse(path)
    if parsed_path.path == "/coins/search":
        query = parse_qs(parsed_path.query).get("q", [""])[0]
        return [coin.model_dump() for coin in find_coins(query)]
    if parsed_path.path == "/journal":
        return recent_entries().to_dict(orient="records")
    raise RuntimeError("This dashboard action is not available.")

def api_post(path: str, payload: dict, timeout: int) -> dict:
    try:
        response = requests.post(f"{settings.backend_url}{path}", json=payload, timeout=timeout)
    except requests.RequestException:
        st.caption(BACKEND_NOTICE)
        return local_post(path, payload)

    if response.status_code >= 400:
        try:
            detail = response.json().get("detail", "The backend could not complete the request.")
        except ValueError:
            detail = "The backend returned an unexpected error."
        if isinstance(detail, list):
            detail = "Please check your inputs and try again."
        if isinstance(detail, dict):
            detail = "; ".join(f"{key}: {value}" for key, value in detail.items())
        raise RuntimeError(str(detail))

    return response.json()


def api_get(path: str, timeout: int) -> dict | list:
    try:
        response = requests.get(f"{settings.backend_url}{path}", timeout=timeout)
    except requests.RequestException:
        st.caption(BACKEND_NOTICE)
        return local_get(path)

    if response.status_code >= 400:
        try:
            detail = response.json().get("detail", "The backend could not complete the request.")
        except ValueError:
            detail = "The backend returned an unexpected error."
        raise RuntimeError(str(detail))
    return response.json()


def get_journal() -> list[dict]:
    try:
        response = requests.get(f"{settings.backend_url}/journal", timeout=10)
        response.raise_for_status()
        return response.json()
    except requests.RequestException:
        return recent_entries().to_dict(orient="records")


def show_decision_summary(analysis: dict) -> None:
    st.subheader("Decision")
    left, right = st.columns([0.7, 0.3])
    with left:
        st.markdown(f"### {analysis['coin_id'].upper()}")
        recommendation_badge(analysis["recommendation"])
        st.write("")
        if analysis["decision"] == "Trade":
            st.success(analysis["explanation"])
        elif analysis["recommendation"] == "Sell / Avoid":
            st.warning(analysis["explanation"])
        else:
            st.info(analysis["explanation"])
    with right:
        st.metric("Decision", analysis["decision"])
        st.metric("Confidence", f"{analysis['confidence']}%")


def show_market_metrics(analysis: dict) -> None:
    price_col, ma20_col, ma50_col, rsi_col = st.columns(4)
    price_col.metric("Current Price", f"${analysis['current_price']:,.2f}")
    ma20_col.metric("20 MA", f"${analysis['ma_20']:,.2f}")
    ma50_col.metric("50 MA", f"${analysis['ma_50']:,.2f}")
    rsi_col.metric("RSI", f"{analysis['rsi']:.1f}")

    bias_col, volume_col, support_col, resistance_col = st.columns(4)
    bias_col.metric("Market Bias", analysis["market_bias"])
    volume_col.metric("Volume vs 20 Avg", f"{analysis['volume_vs_average']:.1f}%")
    support_col.metric("Support", f"${analysis['support']:,.2f}")
    resistance_col.metric("Resistance", f"${analysis['resistance']:,.2f}")


def show_trade_plan(analysis: dict) -> None:
    if analysis["decision"] == "No Trade":
        st.write("No trade plan is shown because the safety rules did not pass.")
        st.write(f"Reason: {analysis['reason']}")
        if analysis["recommendation"] == "Sell / Avoid":
            st.info("This is a risk warning, not an order. Review any current holding manually.")
        return

    entry_col, stop_col, target_col = st.columns(3)
    entry_col.metric("Entry Zone", analysis["entry_zone"])
    stop_col.metric("Stop-Loss", f"${analysis['stop_loss']:,.2f}")
    target_col.metric("Take-Profit", f"${analysis['take_profit']:,.2f}")

    rr_col, size_col, invalid_col = st.columns(3)
    rr_col.metric("Risk / Reward", f"1:{analysis['risk_reward_ratio']:.2f}")
    size_col.metric("Position Size", f"{analysis['position_size']:.6f}")
    invalid_col.metric("Invalidation", f"${analysis['invalidation_point']:,.2f}")


def show_analysis_details(analysis: dict) -> None:
    market_tab, plan_tab, rules_tab = st.tabs(["Market", "Plan", "Safety"])

    with market_tab:
        show_market_metrics(analysis)
        with st.expander("Key Levels"):
            for level in analysis["key_levels"]:
                st.write(f"- {level}")

    with plan_tab:
        show_trade_plan(analysis)

    with rules_tab:
        for rule in analysis["safety_rules"]:
            st.write(f"- {rule}")


def scan_table_rows(results: list[dict]) -> list[dict]:
    rows = []
    for item in results:
        rows.append(
            {
                "coin": item["coin_id"],
                "recommendation": item["recommendation"],
                "decision": item["decision"],
                "confidence": item["confidence"],
                "price": round(item["current_price"], 6),
                "rsi": round(item["rsi"], 1),
                "volume_vs_20_avg": round(item["volume_vs_average"], 1),
                "risk_reward": item["risk_reward_ratio"],
                "reason": item["reason"],
            }
        )
    return rows


def show_alerts(alerts: list[dict]) -> None:
    if not alerts:
        st.info("No urgent scanner alerts right now.")
        return

    for alert in alerts:
        if alert["severity"] == "opportunity":
            st.success(alert["message"])
        elif alert["severity"] == "risk":
            st.warning(alert["message"])
        else:
            st.info(alert["message"])


def current_agent_context() -> list[dict]:
    if st.session_state.scan and st.session_state.scan.get("results"):
        return st.session_state.scan["results"]
    if st.session_state.analysis:
        return [st.session_state.analysis]
    return []


if "analysis" not in st.session_state:
    st.session_state.analysis = None
if "scan" not in st.session_state:
    st.session_state.scan = None
if "agent_messages" not in st.session_state:
    st.session_state.agent_messages = [
        {
            "role": "assistant",
            "content": "Run a scan or analysis, then ask me what looks strongest, what to avoid, or what level to watch.",
        }
    ]


LOGO_PATH = APP_DIR / "assets" / "coinpilot_icon.png"

logo_uri = image_data_uri(LOGO_PATH)

st.markdown(
    f"""
    <div class="app-header">
        <div class="brand-row">
            <img class="brand-logo" src="{logo_uri}" alt="CoinPilot AI logo" />
            <div>
                <h1>CoinPilot <span class="brand-ai">AI</span></h1>
                <div class="tagline">Smarter insights. Better trades.</div>
                <p class="muted">Market scanner, AI coach, and risk-first crypto decision support.</p>
            </div>
        </div>
    </div>
    """,
    unsafe_allow_html=True,
)

st.warning(
    "This is not financial advice. CoinPilot AI is for paper analysis only. "
    "It does not connect to an exchange, use leverage, auto-buy, or auto-sell."
)


with st.sidebar:
    st.header("Trading Plan")
    account_size = st.number_input(
        "Account Size ($)",
        min_value=100.0,
        value=1000.0,
        step=100.0,
        key="account_size",
    )
    risk_percent = st.number_input(
        "Max Risk Per Trade (%)",
        min_value=0.1,
        max_value=5.0,
        value=1.0,
        step=0.1,
        key="risk_percent",
    )

    st.divider()
    page = st.radio(
        "Workspace",
        ["Market Radar", "Coin Deep Dive", "AI Coach", "Journal"],
        key="workspace",
    )

    st.divider()
    st.header("Market Radar")
    scanner_mode = st.radio(
        "Scan",
        ["Market Top 10", "Custom Watchlist"],
        key="scanner_mode",
    )
    universe_limit = st.slider(
        "Market universe",
        min_value=10,
        max_value=100,
        value=50,
        step=10,
        help="Top market-cap coins to consider.",
        key="universe_limit",
    )
    deep_scan_limit = st.slider(
        "Deep scan",
        min_value=5,
        max_value=30,
        value=15,
        step=5,
        help="Coins to analyze deeply. Higher values may use more API calls.",
        key="deep_scan_limit",
    )
    watchlist_text = st.text_area(
        "Watchlist",
        value="bitcoin, ethereum, solana, shib, avax, pepe",
        help="Use tickers, names, or CoinGecko IDs.",
        key="watchlist_text",
    )

    st.divider()
    st.header("Deep Dive")
    selected_coin = st.selectbox("Coin", list(COIN_CHOICES.keys()), key="selected_coin")
    custom_coin = st.text_input(
        "Symbol, name, or CoinGecko ID",
        value="bitcoin",
        help="Examples: shib, avax, pepe, shiba inu, avalanche-2",
        key="custom_coin",
    )
    coin_id = COIN_CHOICES[selected_coin] or custom_coin.strip().lower()
    if selected_coin == "Custom":
        if st.button("Find Coin ID", width="stretch", key="find_coin_id"):
            try:
                st.session_state.coin_search = api_get(f"/coins/search?q={quote_plus(custom_coin.strip())}", timeout=20)
            except RuntimeError as error:
                st.session_state.coin_search = []
                st.error(str(error))
        if st.session_state.get("coin_search"):
            top_match = st.session_state.coin_search[0]
            st.caption(f"Top match: {top_match['name']} ({top_match['symbol'].upper()}) -> {top_match['id']}")


def run_market_scan() -> None:
    try:
        if scanner_mode == "Market Top 10":
            with st.spinner("Scanning the market and ranking short-term setups..."):
                st.session_state.scan = api_post(
                    "/scan/market",
                    {
                        "account_size": account_size,
                        "risk_percent": risk_percent,
                        "universe_limit": universe_limit,
                        "deep_scan_limit": deep_scan_limit,
                        "top_n": 10,
                    },
                    timeout=180,
                )
        else:
            coin_ids = [coin.strip().lower() for coin in watchlist_text.split(",") if coin.strip()]
            if len(coin_ids) > 30:
                st.warning("Custom watchlist scans are capped at 30 coins. Scanning the first 30.")
                coin_ids = coin_ids[:30]
            with st.spinner("Scanning your watchlist..."):
                st.session_state.scan = api_post(
                    "/scan",
                    {
                        "coin_ids": coin_ids,
                        "account_size": account_size,
                        "risk_percent": risk_percent,
                    },
                    timeout=120,
                )
    except RuntimeError as error:
        st.error(str(error))


def render_signal_card(title: str, value: str, caption: str) -> None:
    st.markdown(
        f"""
        <div class="section-note">
            <div class="feature-title">{title}</div>
            <h2 style="margin:0;color:#0F172A;">{value}</h2>
            <div class="feature-copy">{caption}</div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def render_scan_summary(scan: dict) -> None:
    results = scan.get("results", [])
    alerts = scan.get("alerts", [])
    errors = scan.get("errors", {})

    buy_count = len([item for item in results if item["recommendation"] == "Buy Setup"])
    hold_count = len([item for item in results if item["recommendation"] == "Hold"])
    avoid_count = len([item for item in results if item["recommendation"] == "Sell / Avoid"])

    metric_1, metric_2, metric_3, metric_4 = st.columns(4)
    metric_1.metric("Buy Setups", buy_count)
    metric_2.metric("Watch / Hold", hold_count)
    metric_3.metric("Sell / Avoid", avoid_count)
    metric_4.metric("Scanned", scan.get("scanned_count", 0))

    if not results:
        st.warning("No usable market results yet. Try a smaller deep scan or run again later.")
        return

    st.subheader("Action Alerts")
    show_alerts(alerts)

    top_pick = results[0]
    st.subheader("Best Current Candidate")
    top_left, top_right = st.columns([0.62, 0.38])
    with top_left:
        st.markdown(f"### {top_pick['coin_id'].upper()}")
        recommendation_badge(top_pick["recommendation"])
        st.write("")
        if top_pick["recommendation"] == "Buy Setup":
            st.success(top_pick["explanation"])
        elif top_pick["recommendation"] == "Sell / Avoid":
            st.warning(top_pick["explanation"])
        else:
            st.info(top_pick["explanation"])
    with top_right:
        st.metric("Decision", top_pick["decision"])
        st.metric("Confidence", f"{top_pick['confidence']}%")
        st.metric("Price", f"${top_pick['current_price']:,.2f}")

    if top_pick["decision"] == "Trade":
        entry_col, stop_col, target_col, rr_col = st.columns(4)
        entry_col.metric("Entry Zone", top_pick["entry_zone"])
        stop_col.metric("Stop-Loss", f"${top_pick['stop_loss']:,.2f}")
        target_col.metric("Take-Profit", f"${top_pick['take_profit']:,.2f}")
        rr_col.metric("Risk / Reward", f"1:{top_pick['risk_reward_ratio']:.2f}")
    else:
        st.info(f"No trade plan shown. Reason: {top_pick['reason']}")

    st.subheader("Top 10 Short-Term Watchlist")
    st.dataframe(scan_table_rows(results), width="stretch", hide_index=True)

    with st.expander("Full details for best candidate"):
        show_analysis_details(top_pick)

    if errors:
        with st.expander("Skipped coins"):
            for coin, error in errors.items():
                st.write(f"- {coin}: {error}")


if page == "Market Radar":
    st.markdown(
        """
        <div class="scanner-hero">
            <div class="scanner-title">Market Radar</div>
            <div class="scanner-copy">
                Find the strongest short-term coins to review right now. CoinPilot ranks opportunities,
                rejects weak setups, and keeps every decision inside your risk limit.
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    action_col, note_col = st.columns([0.7, 0.3])
    with action_col:
        if st.button("Scan Market Now", type="primary", width="stretch", key="scan_market_now"):
            run_market_scan()
    with note_col:
        render_signal_card("Risk Mode", f"{risk_percent:.1f}%", "Max risk per trade")

    if st.session_state.scan:
        render_scan_summary(st.session_state.scan)
    else:
        st.info("Click Scan Market Now to generate your top 10 short-term watchlist.")

elif page == "Coin Deep Dive":
    st.markdown(
        """
        <div class="scanner-hero">
            <div class="scanner-title">Coin Deep Dive</div>
            <div class="scanner-copy">
                Use this when you already have a coin in mind and want a focused Buy Setup, Hold,
                or Sell / Avoid review.
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )
    if st.button("Analyze Selected Coin", type="primary", width="stretch", key="run_analysis"):
        try:
            st.session_state.analysis = api_post(
                "/analyze",
                {
                    "coin_id": coin_id,
                    "account_size": account_size,
                    "risk_percent": risk_percent,
                },
                timeout=45,
            )
        except RuntimeError as error:
            st.error(str(error))

    if st.session_state.analysis:
        show_decision_summary(st.session_state.analysis)
        show_analysis_details(st.session_state.analysis)
        st.success("Saved to the local trade journal.")
    else:
        st.info("Choose a coin in the sidebar, then run a deep dive.")

elif page == "AI Coach":
    st.subheader("AI Coach")
    st.write(
        "Ask about your latest scan or coin analysis. The coach can compare setups, explain risk, "
        "and help you decide what to review next. It cannot trade for you."
    )

    context = current_agent_context()
    if context:
        context_col_1, context_col_2 = st.columns(2)
        context_col_1.metric("Market Context", len(context))
        context_col_2.metric("Best Signal", context[0]["recommendation"])
    else:
        st.info("Run Market Radar or Coin Deep Dive first so the coach has context.")

    for message in st.session_state.agent_messages:
        with st.chat_message(message["role"]):
            st.write(message["content"])

    prompt = st.chat_input("Ask what to buy, hold, sell/avoid, or watch next...")
    if prompt:
        st.session_state.agent_messages.append({"role": "user", "content": prompt})
        try:
            reply = api_post(
                "/agent/chat",
                {
                    "message": prompt,
                    "context": context,
                },
                timeout=45,
            )
            answer = f"{reply['answer']}\n\n{reply['safety_note']}"
        except RuntimeError as error:
            answer = str(error)
        st.session_state.agent_messages.append({"role": "assistant", "content": answer})
        st.rerun()

elif page == "Journal":
    st.subheader("Trade Journal")
    st.write("Review recent decisions and learn from the setups CoinPilot accepted or rejected.")
    try:
        st.dataframe(get_journal(), width="stretch", hide_index=True)
    except Exception:
        st.caption("No journal entries yet.")
