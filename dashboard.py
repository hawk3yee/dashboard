import streamlit as st
import pandas as pd
import numpy as np
from sklearn.linear_model import LinearRegression
import warnings
import io
import matplotlib.pyplot as plt
import matplotlib.ticker as mtick
from datetime import datetime
import os
import re # Pour le parsing (bien que nous le remplacions)

# --- NOUVEAU: Import de Scipy pour l'optimisation ---
try:
    import scipy.optimize as sco
    SCIPY_AVAILABLE = True
except ImportError:
    SCIPY_AVAILABLE = False
    st.warning("Module 'scipy' non trouvé. L'optimisation automatique est désactivée. Passage en mode manuel.")
# --- FIN NOUVEAU ---


# --- Configuration & CSS ---
st.set_page_config(layout="wide", page_title="M2 MBFA Terminal", page_icon="📊", initial_sidebar_state="expanded")

# --- Constantes (Mises à jour avec les règles du mandat) ---
EXCEL_URL = "https://docs.google.com/spreadsheets/d/1VqgRMRJJ3DaCYKJ1OT77LFn9ExUUifO7x3Zzqq6fmwQ/export?format=xlsx"
MANAGEMENT_FEE_ANNUAL = 0.01 # 1% [Source: PDF page 3]
CASH_RATE_ANNUAL = 0.015 # 1.5% [Source: PDF page 3]
TRANSACTION_FEE_RATE = 0.001 # 0.10% [Source: PDF page 3]
RISK_FREE_RATE_ANNUAL = 0.015 # Supposons égal au taux cash pour Sharpe
TRADING_DAYS = 252 # Pour annualisation du risque (Vol, Sharpe, TE)
CALENDAR_DAYS = 365 # Pour annualisation/journalisation des frais et taux cash
BENCHMARK_WEIGHTS = {'Action': 0.60, 'Gov bond': 0.20, 'Commodities': 0.15, 'Cash': 0.05} # [Source: PDF page 2]
START_DATE_SIMULATION = pd.to_datetime('2025-10-06') # [Source: PDF page 4]
INITIAL_NAV_EUR = 100_000_000 # 100M € [Source: PDF page 1]
CASH_TICKER_NAME = "CASH EUR" # [Source: PDF page 2]
ASSET_WEIGHT_LIMIT = 0.10 # Limite de 10% par actif

# Palette Bloomberg authentique
COLORS = {
    'bg_dark': '#0A0E27', 'bg_secondary': '#0F1630', 'bg_panel': '#141B3D',
    'accent_orange': '#fb8b1e', 'accent_yellow': '#FFB81C', 'text_primary': '#E8F0FF',
    'text_secondary': '#8B9DC3', 'success': '#4af6c3', 'danger': '#ff433d',
    'border': '#1F2A5C', 'grid': '#1A2347', 'blue_bright': '#0068ff'
}

# --- CSS REFONTE PROFESSIONNELLE FRANÇAISE ---
custom_css = f"""
<style>
    @import url('https://fonts.googleapis.com/css2?family=Roboto+Mono:wght@400;500;600;700&family=Inter:wght@300;400;500;600;700;800&display=swap');
    
    /* === GLOBAL === */
    .main {{ 
        background: linear-gradient(135deg, {COLORS['bg_dark']} 0%, #050A1E 100%);
        color: {COLORS['text_primary']}; 
        font-family: 'Inter', sans-serif;
    }}
    .block-container {{ 
        padding: 1rem 3rem 3rem 3rem; 
        max-width: 100%; 
    }}
    
    /* === HEADER PROFESSIONNEL === */
    .bloomberg-header {{
        background: linear-gradient(90deg, rgba(251,139,30,0.15) 0%, rgba(0,104,255,0.1) 50%, rgba(251,139,30,0.15) 100%);
        border: 2px solid {COLORS['accent_orange']};
        border-left: 6px solid {COLORS['accent_orange']};
        padding: 2rem 3rem;
        margin-bottom: 2rem;
        box-shadow: 0 4px 30px rgba(251, 139, 30, 0.4), inset 0 1px 0 rgba(255,255,255,0.1);
        position: relative;
        overflow: hidden;
    }}
    .bloomberg-header::before {{
        content: '';
        position: absolute;
        top: 0; left: 0;
        width: 100%; height: 100%;
        background: repeating-linear-gradient(
            0deg,
            transparent,
            transparent 2px,
            rgba(251,139,30,0.03) 2px,
            rgba(251,139,30,0.03) 4px
        );
        pointer-events: none;
    }}
    .bloomberg-header h1 {{
        color: {COLORS['accent_orange']};
        font-family: 'Roboto Mono', monospace;
        font-weight: 800;
        font-size: 2.8rem;
        margin: 0;
        letter-spacing: 0.2em;
        text-transform: uppercase;
        text-shadow: 0 0 20px rgba(251, 139, 30, 0.6), 0 0 40px rgba(251, 139, 30, 0.3);
        line-height: 1.1;
    }}
    .bloomberg-header .subtitle {{
        color: {COLORS['text_secondary']};
        font-size: 0.95rem;
        margin-top: 1rem;
        letter-spacing: 0.15em;
        font-weight: 500;
        text-transform: uppercase;
    }}
    .bloomberg-header .session-info {{
        position: absolute;
        top: 1.5rem;
        right: 2rem;
        background: rgba(0,0,0,0.4);
        padding: 0.5rem 1rem;
        border-radius: 4px;
        border: 1px solid {COLORS['border']};
    }}
    .session-info .live-indicator {{
        display: inline-block;
        width: 8px;
        height: 8px;
        background: {COLORS['success']};
        border-radius: 50%;
        margin-right: 0.5rem;
        animation: pulse 2s infinite;
    }}
    @keyframes pulse {{
        0%, 100% {{ opacity: 1; }}
        50% {{ opacity: 0.3; }}
    }}

    /* === MARKET TICKER AMÉLIORÉ === */
    .market-ticker {{
        background: linear-gradient(90deg, {COLORS['bg_panel']} 0%, {COLORS['bg_secondary']} 50%, {COLORS['bg_panel']} 100%);
        border: 2px solid {COLORS['border']};
        border-left: 4px solid {COLORS['success']};
        padding: 1rem 1.5rem;
        margin-bottom: 2rem;
        box-shadow: 0 2px 15px rgba(0,0,0,0.5);
        position: relative;
        overflow: hidden;
    }}
    .ticker-label {{
        color: {COLORS['accent_yellow']};
        font-size: 0.7rem;
        font-weight: 700;
        letter-spacing: 0.15em;
        margin-bottom: 0.7rem;
        display: block;
        font-family: 'Roboto Mono', monospace;
    }}
    .ticker-wrap {{
        overflow: hidden;
        position: relative;
        width: 100%;
        height: 35px;
    }}
    .ticker-content {{
        display: flex;
        white-space: nowrap;
        animation: scroll-ticker 45s linear infinite;
    }}
    .ticker-item {{
        display: inline-flex;
        align-items: center;
        flex-shrink: 0;
    }}
    .ticker-content .ticker {{
        background: {COLORS['bg_dark']};
        color: {COLORS['accent_yellow']};
        padding: 0.3rem 0.7rem;
        margin: 0 0.5rem;
        border: 1px solid {COLORS['accent_yellow']};
        font-family: 'Roboto Mono', monospace;
        font-weight: 700;
        font-size: 0.8rem;
        display: inline-block;
        box-shadow: 0 0 10px rgba(255,184,28,0.3);
    }}
    .price-up {{ 
        color: {COLORS['success']}; 
        font-weight: 700;
        font-size: 0.9rem;
        text-shadow: 0 0 5px {COLORS['success']};
        margin-right: 1.5rem;
    }}
    .price-down {{ 
        color: {COLORS['danger']}; 
        font-weight: 700;
        font-size: 0.9rem;
        text-shadow: 0 0 5px {COLORS['danger']};
        margin-right: 1.5rem;
    }}
    @keyframes scroll-ticker {{ 
        0% {{ transform: translateX(0); }} 
        100% {{ transform: translateX(-50%); }} 
    }}

    /* === TABS STYLE BLOOMBERG === */
    [data-baseweb="tab-list"] {{
        background: {COLORS['bg_dark']};
        border-bottom: 3px solid {COLORS['accent_orange']};
        padding: 0;
        gap: 0;
        margin-bottom: 2.5rem;
        box-shadow: 0 2px 10px rgba(0,0,0,0.5);
    }}
    button[data-baseweb="tab"] {{
        background: linear-gradient(180deg, {COLORS['bg_secondary']} 0%, {COLORS['bg_dark']} 100%);
        border: none;
        border-right: 1px solid {COLORS['border']};
        color: {COLORS['text_secondary']};
        font-family: 'Roboto Mono', monospace;
        font-weight: 600;
        font-size: 0.85rem;
        letter-spacing: 0.15em;
        text-transform: uppercase;
        padding: 1.5rem 3rem;
        transition: all 0.3s ease;
        position: relative;
    }}
    button[data-baseweb="tab"]::before {{
        content: '';
        position: absolute;
        bottom: 0;
        left: 0;
        width: 0;
        height: 3px;
        background: {COLORS['accent_orange']};
        transition: width 0.3s ease;
    }}
    button[data-baseweb="tab"][aria-selected="true"] {{
        background: linear-gradient(180deg, {COLORS['accent_orange']} 0%, rgba(251,139,30,0.8) 100%);
        color: {COLORS['bg_dark']};
        font-weight: 800;
        box-shadow: 0 0 30px rgba(251, 139, 30, 0.6);
        border-bottom: none;
    }}
    button[data-baseweb="tab"][aria-selected="true"]::before {{
        width: 100%;
    }}
    button[data-baseweb="tab"]:hover:not([aria-selected="true"]) {{
        background: {COLORS['bg_panel']};
        color: {COLORS['text_primary']};
        transform: translateY(-2px);
    }}

    /* === METRICS CARDS PREMIUM === */
    [data-testid="stMetric"] {{
        background: linear-gradient(135deg, {COLORS['bg_panel']} 0%, {COLORS['bg_secondary']} 100%);
        padding: 1.5rem 2rem;
        border: 2px solid {COLORS['border']};
        border-left: 5px solid {COLORS['accent_orange']};
        border-radius: 8px;
        box-shadow: 0 4px 20px rgba(0,0,0,0.6), inset 0 1px 0 rgba(255,255,255,0.05);
        transition: all 0.3s cubic-bezier(0.4, 0, 0.2, 1);
        position: relative;
        overflow: hidden;
    }}
    [data-testid="stMetric"]::after {{
        content: '';
        position: absolute;
        top: -50%;
        right: -50%;
        width: 200%;
        height: 200%;
        background: radial-gradient(circle, rgba(251,139,30,0.1) 0%, transparent 70%);
        opacity: 0;
        transition: opacity 0.3s ease;
    }}
    [data-testid="stMetric"]:hover {{
        border-left-width: 8px;
        border-left-color: {COLORS['success']};
        transform: translateX(5px) scale(1.02);
        box-shadow: 0 6px 30px rgba(251, 139, 30, 0.5);
    }}
    [data-testid="stMetric"]:hover::after {{
        opacity: 1;
    }}
    [data-testid="stMetric"] > label {{
        color: {COLORS['accent_yellow']} !important;
        font-family: 'Roboto Mono', monospace;
        font-weight: 700;
        font-size: 0.7rem;
        text-transform: uppercase;
        letter-spacing: 0.2em;
        margin-bottom: 1rem;
        display: block;
        text-align: center;
    }}
    [data-testid="stMetric"] [data-testid="stMetricValue"] {{
        color: {COLORS['text_primary']} !important;
        font-family: 'Roboto Mono', monospace;
        font-weight: 800;
        font-size: 2.2rem;
        text-shadow: 0 0 10px rgba(255,255,255,0.3);
        text-align: center;
        display: block;
        letter-spacing: 0.05em;
    }}
    [data-testid="stMetric"] [data-testid="stMetricDelta"] {{
        font-size: 0.95rem;
        font-weight: 600;
        text-align: center;
        display: block;
        margin-top: 0.5rem;
    }}

    /* === SECTION HEADERS === */
    h2 {{
        color: {COLORS['accent_orange']};
        font-family: 'Roboto Mono', monospace;
        font-weight: 800;
        font-size: 1.8rem;
        text-transform: uppercase;
        letter-spacing: 0.15em;
        text-align: center;
        border-bottom: 3px solid {COLORS['accent_orange']};
        padding-bottom: 1rem;
        margin: 3.5rem 0 2.5rem 0;
        text-shadow: 0 0 15px rgba(251, 139, 30, 0.5);
        position: relative;
    }}
    h2::before {{
        content: '◆';
        position: absolute;
        left: 50%;
        bottom: -1.2rem;
        transform: translateX(-50%);
        color: {COLORS['accent_orange']};
        font-size: 1.2rem;
    }}
    h3 {{
        color: {COLORS['blue_bright']};
        font-family: 'Roboto Mono', monospace;
        font-weight: 700;
        font-size: 1.4rem;
        text-align: center;
        margin: 2.5rem 0 1.5rem 0;
        padding-bottom: 0.8rem;
        border-bottom: 2px solid {COLORS['blue_bright']};
        letter-spacing: 0.1em;
        text-shadow: 0 0 10px rgba(0, 104, 255, 0.4);
    }}
    h4 {{
        color: {COLORS['accent_yellow']};
        font-family: 'Roboto Mono', monospace;
        font-weight: 600;
        font-size: 0.95rem;
        text-transform: uppercase;
        letter-spacing: 0.12em;
        text-align: center;
        margin: 1.5rem 0 1rem 0;
        padding: 0.5rem 1rem;
        background: rgba(255,184,28,0.1);
        border-left: 3px solid {COLORS['accent_yellow']};
    }}

    /* === SIDEBAR PREMIUM === */
    [data-testid="stSidebar"] {{
        background: linear-gradient(180deg, {COLORS['bg_secondary']} 0%, {COLORS['bg_dark']} 100%);
        border-right: 3px solid {COLORS['border']};
        box-shadow: 3px 0 20px rgba(0,0,0,0.5);
    }}
    [data-testid="stSidebar"] h3 {{
        color: {COLORS['accent_orange']};
        font-size: 1rem;
        border-bottom: 2px solid {COLORS['accent_orange']};
        padding-bottom: 0.8rem;
        margin: 1.5rem 0 1rem 0;
        text-align: left;
        text-shadow: none;
    }}
    [data-testid="stSidebar"] h3::before {{
        content: '▸ ';
        color: {COLORS['success']};
    }}

    /* === EXPANDERS === */
    [data-testid="stExpander"] {{
        background: {COLORS['bg_panel']};
        border: 2px solid {COLORS['border']};
        border-left: 4px solid {COLORS['blue_bright']};
        border-radius: 6px;
        margin-bottom: 1rem;
        box-shadow: 0 2px 10px rgba(0,0,0,0.4);
    }}
    [data-testid="stExpander"] summary {{
        color: {COLORS['text_primary']};
        font-family: 'Roboto Mono', monospace;
        font-weight: 700;
        font-size: 0.8rem;
        text-transform: uppercase;
        letter-spacing: 0.1em;
        padding: 1rem 1.5rem;
        background: rgba(0,104,255,0.1);
    }}
    [data-testid="stExpander"] summary:hover {{
        background: rgba(0,104,255,0.2);
    }}

    /* === DATAFRAMES === */
    [data-testid="stDataFrame"] {{
        border: 2px solid {COLORS['border']};
        border-radius: 8px;
        overflow: hidden;
        box-shadow: 0 4px 20px rgba(0,0,0,0.5);
    }}
    [data-testid="stDataFrame"] table thead tr th {{
        background: linear-gradient(180deg, {COLORS['bg_dark']} 0%, {COLORS['bg_secondary']} 100%) !important;
        color: {COLORS['accent_orange']} !important;
        font-weight: 800;
        font-size: 0.75rem;
        text-transform: uppercase;
        letter-spacing: 0.1em;
        border-bottom: 3px solid {COLORS['accent_orange']};
        padding: 1rem 0.8rem !important;
        font-family: 'Roboto Mono', monospace;
    }}
    [data-testid="stDataFrame"] table tbody tr {{
        transition: all 0.2s ease;
    }}
    [data-testid="stDataFrame"] table tbody tr:hover {{
        background: {COLORS['bg_secondary']} !important;
        transform: scale(1.01);
    }}
    [data-testid="stDataFrame"] table tbody tr td {{
        padding: 0.8rem !important;
        font-family: 'Roboto Mono', monospace;
        font-size: 0.85rem;
    }}

    /* === PANEL BLOOMBERG === */
    .bloomberg-panel {{
        background: linear-gradient(135deg, {COLORS['bg_panel']} 0%, {COLORS['bg_secondary']} 100%);
        border: 2px solid {COLORS['border']};
        border-left: 5px solid {COLORS['blue_bright']};
        padding: 2rem;
        margin-bottom: 2rem;
        box-shadow: 0 4px 25px rgba(0,0,0,0.6);
        border-radius: 8px;
    }}
    .bloomberg-panel h4 {{
        color: {COLORS['accent_orange']};
        font-size: 1.1rem;
        font-weight: 700;
        margin-bottom: 1.5rem;
        text-align: left;
        border-bottom: 2px solid {COLORS['accent_orange']};
        padding-bottom: 0.8rem;
    }}
    .bloomberg-panel ul {{
        list-style: none;
        padding-left: 0;
    }}
    .bloomberg-panel ul li {{
        padding: 0.6rem 0;
        border-bottom: 1px solid {COLORS['border']};
        font-size: 0.9rem;
        line-height: 1.6;
    }}
    .bloomberg-panel ul li:last-child {{
        border-bottom: none;
    }}
    .bloomberg-panel ul li strong {{
        color: {COLORS['accent_yellow']};
        font-weight: 700;
    }}

    /* === PROGRESS BAR === */
    .progress-container {{
        margin-bottom: 1rem;
    }}
    .progress-label {{
        display: flex;
        justify-content: space-between;
        margin-bottom: 0.5rem;
        font-family: 'Roboto Mono', monospace;
    }}
    .progress-label-text {{
        color: {COLORS['text_secondary']};
        font-size: 0.75rem;
        font-weight: 700;
        letter-spacing: 0.15em;
    }}
    .progress-value {{
        font-size: 0.85rem;
        font-weight: 800;
    }}
    .progress-bar-bg {{
        background: rgba(10,14,39,0.8);
        height: 10px;
        border: 1px solid {COLORS['border']};
        border-radius: 5px;
        overflow: hidden;
        box-shadow: inset 0 2px 5px rgba(0,0,0,0.5);
    }}
    .progress-bar-fill {{
        height: 100%;
        transition: width 0.5s ease, background 0.3s ease;
        box-shadow: 0 0 10px currentColor;
    }}

    /* === BUTTONS === */
    .stDownloadButton button {{
        background: linear-gradient(135deg, {COLORS['blue_bright']} 0%, {COLORS['accent_orange']} 100%);
        color: white;
        font-family: 'Roboto Mono', monospace;
        font-weight: 700;
        font-size: 0.85rem;
        letter-spacing: 0.1em;
        text-transform: uppercase;
        padding: 0.8rem 2rem;
        border: 2px solid {COLORS['blue_bright']};
        border-radius: 6px;
        transition: all 0.3s ease;
        box-shadow: 0 4px 15px rgba(0,104,255,0.4);
    }}
    .stDownloadButton button:hover {{
        transform: translateY(-3px);
        box-shadow: 0 6px 25px rgba(251,139,30,0.6);
        background: linear-gradient(135deg, {COLORS['accent_orange']} 0%, {COLORS['blue_bright']} 100%);
    }}

    /* === GRAPHIQUES === */
    .stpyplot {{
        margin-bottom: 2.5rem;
        padding: 1rem;
        background: {COLORS['bg_panel']};
        border: 2px solid {COLORS['border']};
        border-radius: 8px;
        box-shadow: 0 4px 20px rgba(0,0,0,0.5);
    }}

    /* === FOOTER === */
    .footer-terminal {{
        border-top: 2px solid {COLORS['border']};
        padding-top: 2rem;
        margin-top: 4rem;
        text-align: center;
        font-family: 'Roboto Mono', monospace;
        font-size: 0.75rem;
        color: {COLORS['text_secondary']};
        letter-spacing: 0.1em;
    }}
    .footer-terminal strong {{
        color: {COLORS['accent_orange']};
        font-weight: 700;
    }}

    /* === ANIMATIONS === */
    @keyframes fadeIn {{
        from {{ opacity: 0; transform: translateY(20px); }}
        to {{ opacity: 1; transform: translateY(0); }}
    }}
    .animate-in {{
        animation: fadeIn 0.5s ease-out;
    }}

    /* === SCROLLBAR === */
    ::-webkit-scrollbar {{
        width: 12px;
        height: 12px;
    }}
    ::-webkit-scrollbar-track {{
        background: {COLORS['bg_dark']};
        border: 1px solid {COLORS['border']};
    }}
    ::-webkit-scrollbar-thumb {{
        background: linear-gradient(180deg, {COLORS['accent_orange']} 0%, {COLORS['blue_bright']} 100%);
        border-radius: 6px;
        border: 2px solid {COLORS['bg_dark']};
    }}
    ::-webkit-scrollbar-thumb:hover {{
        background: linear-gradient(180deg, {COLORS['blue_bright']} 0%, {COLORS['accent_orange']} 100%);
    }}

    /* === RESPONSIVE === */
    @media (max-width: 768px) {{
        .bloomberg-header h1 {{ font-size: 1.8rem; }}
        button[data-baseweb="tab"] {{ padding: 1rem 1.5rem; font-size: 0.75rem; }}
        [data-testid="stMetric"] {{ padding: 1rem; }}
    }}
</style>
"""
st.markdown(custom_css, unsafe_allow_html=True)

# --- Fonctions Utilitaires ---

def calculate_daily_rates():
    """Calcule les taux journaliers en base 365."""
    cash_daily = (1 + CASH_RATE_ANNUAL) ** (1/CALENDAR_DAYS) - 1
    rf_daily = (1 + RISK_FREE_RATE_ANNUAL) ** (1/CALENDAR_DAYS) - 1
    mgmt_fee_daily = MANAGEMENT_FEE_ANNUAL / CALENDAR_DAYS
    return cash_daily, rf_daily, mgmt_fee_daily

def get_tickers_by_class(benchmark_df, available_columns):
    """Retourne les tickers par classe d'actif."""
    if 'BBG Ticker' not in benchmark_df.columns or 'Asset Class' not in benchmark_df.columns:
        st.error("Colonnes 'BBG Ticker' ou 'Asset Class' manquantes dans 'Benchmark'.")
        return {'action': [], 'bond': [], 'commodity': []}
    benchmark_df['BBG Ticker'] = benchmark_df['BBG Ticker'].astype(str).str.strip()
    asset_class_map = benchmark_df.set_index('BBG Ticker').loc[:, 'Asset Class']
    available_columns_str = [str(col).strip() for col in available_columns]
    return {
        'action': [t for t in asset_class_map[asset_class_map == 'Action'].index if t in available_columns_str],
        'bond': [t for t in asset_class_map[asset_class_map == 'Gov bond'].index if t in available_columns_str],
        'commodity': [t for t in asset_class_map[asset_class_map == 'Commodities'].index if t in available_columns_str]
    }

def calculate_indicators(returns, rf_daily_for_sharpe):
    """Calcule volatilité (annu TRADING_DAYS), Sharpe (annu TRADING_DAYS) et VaR."""
    if returns is None or returns.empty or len(returns) < 2: return {'Volatilité': np.nan, 'Sharpe': np.nan, 'VaR 99%': np.nan}
    vol = returns.std() * np.sqrt(TRADING_DAYS)
    var = returns.quantile(0.01); sharpe = np.nan
    std_dev = returns.std()
    if std_dev != 0 and np.isfinite(std_dev):
        excess = returns - rf_daily_for_sharpe
        sharpe = (excess.mean() / std_dev) * np.sqrt(TRADING_DAYS)
    return {'Volatilité': vol, 'Sharpe': sharpe, 'VaR 99%': var}

def calculate_benchmark_returns(returns_period, tickers, cash_daily_rate):
    """Calcule les rendements BRUTS quotidiens du benchmark."""
    returns_by_class = {
        'Action': returns_period[tickers['action']].mean(axis=1) if tickers['action'] else pd.Series(0, index=returns_period.index),
        'Gov bond': returns_period[tickers['bond']].mean(axis=1) if tickers['bond'] else pd.Series(0, index=returns_period.index),
        'Commodities': returns_period[tickers['commodity']].mean(axis=1) if tickers['commodity'] else pd.Series(0, index=returns_period.index),
        'Cash': pd.Series(cash_daily_rate, index=returns_period.index)
    }
    common_index = returns_period.index; weighted_sum = pd.Series(0.0, index=common_index)
    for k, weight in BENCHMARK_WEIGHTS.items():
         if k in returns_by_class and not returns_by_class[k].empty: weighted_sum = weighted_sum.add(returns_by_class[k].reindex(common_index).fillna(0) * weight, fill_value=0)
    return weighted_sum

# --- Barre de progression HTML personnalisée ---
def create_progress_bar(label, value, color):
    """Crée une barre de progression HTML premium."""
    value = max(0.0, min(1.0, value))
    return f"""
    <div class='progress-container'>
        <div class='progress-label'>
            <span class='progress-label-text'>{label}</span>
            <span class='progress-value' style='color: {color};'>{value:.1%}</span>
        </div>
        <div class='progress-bar-bg'>
            <div class='progress-bar-fill' style='width: {value*100}%; background: {color};'></div>
        </div>
    </div>
    """

# --- Fonctions de Chargement --- (Inchangées)
@st.cache_data(ttl=3600)
def load_data():
    """Charge les données depuis Google Drive."""
    try:
        benchmark_df = pd.read_excel(EXCEL_URL, sheet_name="Benchmark"); required_cols = ['BBG Ticker', 'Asset Class']
        if not all(col in benchmark_df.columns for col in required_cols): st.error(f"Colonnes manquantes dans 'Benchmark': {required_cols}"); return None, None, None
        benchmark_df['BBG Ticker'] = benchmark_df['BBG Ticker'].astype(str).str.strip(); benchmark_df = benchmark_df.dropna(subset=['BBG Ticker'])

        prices_df_raw = pd.read_excel(EXCEL_URL, sheet_name="Historique Prix", header=3)

        portfolio_df = pd.read_excel(EXCEL_URL, sheet_name="Portefeuille", skiprows=1)
        if len(portfolio_df.columns) < 6: st.error("'Portefeuille' sheet must have >= 6 columns."); return None, None, None
        ticker_col = portfolio_df.columns[2]; weight_col = portfolio_df.columns[5] # Col C, Col F
        portfolio_df = portfolio_df[[ticker_col, weight_col]].copy(); portfolio_df.columns = ['BBG Ticker', 'Weight']
        portfolio_df['BBG Ticker'] = portfolio_df['BBG Ticker'].astype(str).str.strip(); portfolio_df = portfolio_df.dropna(subset=['BBG Ticker'])
        portfolio_df['Weight'] = pd.to_numeric(portfolio_df['Weight'], errors='coerce'); portfolio_df = portfolio_df.dropna(subset=['Weight'])

        total = portfolio_df['Weight'].sum()
        if total <= 0: st.error("Sum of portfolio weights <= 0."); return None, None, None

        if np.isclose(total, 100.0, atol=1.0): portfolio_df['Weight'] /= 100.0
        elif not np.isclose(total, 1.0, atol=0.01): st.warning(f"Sum of weights ({total:.2f}) != 1 or 100. Normalizing..."); portfolio_df['Weight'] /= total

        final_sum = portfolio_df['Weight'].sum()
        if not np.isclose(final_sum, 1.0, atol=0.01): st.error(f"Weight normalization failed. Sum: {final_sum:.4f}"); return None, None, None

        return benchmark_df, prices_df_raw, portfolio_df

    except Exception as e: st.error(f"Error loading data: {e}"); return None, None, None

@st.cache_data
def process_prices(prices_df_raw):
    """Traite les données de prix."""
    if prices_df_raw is None: return None, None
    original_cols = prices_df_raw.columns.tolist(); date_col = original_cols[0]
    if len(prices_df_raw.index) > 1 and not pd.isna(prices_df_raw.iloc[1, 0]):
        candidate = prices_df_raw.iloc[1, 0]
        if isinstance(candidate, str) and 'date' in candidate.lower(): date_col = candidate; new_cols = original_cols.copy(); new_cols[0] = date_col; prices_df_raw.columns = new_cols
    prices_df = prices_df_raw.iloc[2:].copy()
    try: prices_df[date_col] = pd.to_datetime(prices_df[date_col]); prices_df = prices_df.set_index(date_col)
    except Exception as e: st.error(f"Date conversion error: {e}"); return None, None
    prices_numeric = prices_df.apply(pd.to_numeric, errors='coerce'); prices_clean = prices_numeric.copy().ffill().bfill()
    prices_clean.columns = prices_clean.columns.astype(str).str.strip()
    returns = prices_clean.pct_change().iloc[1:]
    return prices_clean, returns

# --- MODIFIED: Ajout Optimisation ---
@st.cache_data
def calculate_full_period_indicators(benchmark_df, prices_hist, returns_full):
    """Calcule les indicateurs sur toute la période et effectue l'optimisation."""
    optimal_weights = None # Initialiser
    if benchmark_df is None or prices_hist is None or returns_full is None: return None, None, None, None, None, None, None
    if returns_full.empty: st.error("No return data."); return None, None, None, None, None, None, None

    cash_daily_365, rf_daily_365, _ = calculate_daily_rates()
    tickers = get_tickers_by_class(benchmark_df, prices_hist.columns)
    all_tickers = tickers['action'] + tickers['bond'] + tickers['commodity']
    if not all_tickers: st.error("No valid asset tickers found."); return None, None, None, None, None, None, None

    try:
        benchmark_df_indexed = benchmark_df.set_index(benchmark_df['BBG Ticker'].astype(str))
        asset_class_map = benchmark_df_indexed['Asset Class']
    except Exception as e:
        st.error(f"Error creating asset class map: {e}")
        return None, None, None, None, None, None, None

    bench_returns = calculate_benchmark_returns(returns_full, tickers, cash_daily_365).fillna(0)
    bench_returns.name = "Benchmark_Returns"
    if bench_returns.empty: st.error("Benchmark returns calculation failed."); return None, None, None, None, None, None, None

    bench_ind_calc = calculate_indicators(bench_returns, rf_daily_365)
    bench_indicators_full = {
        'Volatilité Annuelle': bench_ind_calc['Volatilité'],
        'Ratio de Sharpe Annuel': bench_ind_calc['Sharpe'],
        'VaR 99% (1 jour)': bench_ind_calc['VaR 99%']
    }

    # --- Préparation des données pour optimisation ---
    returns_universe_opt = returns_full[[col for col in all_tickers if col in returns_full.columns]].copy()
    if not returns_universe_opt.empty:
        if CASH_TICKER_NAME not in returns_universe_opt.columns:
            returns_universe_opt[CASH_TICKER_NAME] = cash_daily_365
        else:
             returns_universe_opt[CASH_TICKER_NAME] = cash_daily_365

        mean_daily_returns_opt = returns_universe_opt.mean()
        cov_matrix_opt = returns_universe_opt.cov()
    else:
        st.warning("No asset returns found for optimization data.")
        mean_daily_returns_opt = None
        cov_matrix_opt = None
    # --- FIN Préparation ---

    # --- NOUVEAU: Exécution de l'optimisation ---
    if SCIPY_AVAILABLE and mean_daily_returns_opt is not None and cov_matrix_opt is not None:
        try:
            # Fonction objectif: -Sharpe Ratio
            def negative_sharpe_ratio(weights, mu, S, rf):
                portfolio_return = np.sum(mu * weights)
                portfolio_volatility = np.sqrt(np.dot(weights.T, np.dot(S, weights)))
                if portfolio_volatility == 0:
                    return 0 # Éviter division par zéro
                sharpe = (portfolio_return - rf) / portfolio_volatility
                return -sharpe # On minimise le négatif du Sharpe

            num_assets = len(mean_daily_returns_opt)
            # Contraintes
            constraints = ({'type': 'eq', 'fun': lambda w: np.sum(w) - 1}) # Sum(w) = 1
            # Bornes: 0 <= w <= 0.10 pour TOUS les actifs (y compris cash)
            bounds = tuple((0.0, ASSET_WEIGHT_LIMIT) for _ in range(num_assets))
            
            # Vérification de faisabilité des contraintes
            max_possible = ASSET_WEIGHT_LIMIT * num_assets
            if max_possible + 1e-12 < 1.0:
                st.session_state['optim_success'] = False
                st.session_state['optim_error'] = f"Constraints infeasible: {num_assets} assets × {ASSET_WEIGHT_LIMIT:.0%} = {max_possible:.1%} < 100%. Please adjust ASSET_WEIGHT_LIMIT or reduce universe size."
                optimal_weights = None
            else:
                # Construction d'un initial guess valide et faisable
                init_guess = np.zeros(num_assets)
                remaining = 1.0
                for i in range(num_assets):
                    alloc = min(ASSET_WEIGHT_LIMIT, remaining)
                    init_guess[i] = alloc
                    remaining -= alloc
                    if remaining <= 1e-12:
                        break
                # Distribution proportionnelle du reliquat si nécessaire
                if remaining > 1e-12:
                    free_idx = [i for i, v in enumerate(init_guess) if v < ASSET_WEIGHT_LIMIT - 1e-12]
                    if free_idx:
                        add_each = remaining / len(free_idx)
                        for i in free_idx:
                            init_guess[i] += min(add_each, ASSET_WEIGHT_LIMIT - init_guess[i])
                init_guess = init_guess / init_guess.sum()  # Normalisation numérique finale

            opt_result = sco.minimize(
                negative_sharpe_ratio,
                init_guess,
                args=(mean_daily_returns_opt, cov_matrix_opt, rf_daily_365),
                method='SLSQP',
                bounds=bounds,
                constraints=constraints,
                options={'disp': False, 'ftol': 1e-9, 'maxiter': 500}
            )

            if opt_result.success:
                # Récupérer les poids et les nettoyer (mettre les très petites valeurs à 0)
                optimal_weights_array = opt_result.x
                optimal_weights_array[optimal_weights_array < 1e-6] = 0 # Seuil
                optimal_weights_array /= np.sum(optimal_weights_array) # Renormaliser
                optimal_weights = pd.DataFrame(optimal_weights_array, index=mean_daily_returns_opt.index, columns=['Weight'])
                optimal_weights = optimal_weights[optimal_weights['Weight'] > 1e-6] # Filtrer les poids nuls
                st.session_state['optim_success'] = True # Marqueur de succès
            else:
                st.session_state['optim_success'] = False
                st.session_state['optim_error'] = opt_result.message
                optimal_weights = None

        except Exception as e:
            st.session_state['optim_success'] = False
            st.session_state['optim_error'] = str(e)
            optimal_weights = None
    else:
         optimal_weights = None # Scipy non dispo ou données manquantes
    # --- FIN NOUVEAU ---

    # ... (Calcul des indicateurs 'indicators_df' inchangé) ...
    returns_aligned = returns_full[[str(t) for t in all_tickers]].loc[bench_returns.index]
    indicators_list = []
    for ticker_str in returns_aligned.columns:
        ticker = ticker_str
        Y = returns_aligned[ticker_str]
        common_idx = bench_returns.index.intersection(Y.dropna().index)
        if len(common_idx) < 2: continue
        Y_aligned = Y.loc[common_idx]; X_aligned = bench_returns.loc[common_idx].values.reshape(-1, 1)
        ind = calculate_indicators(Y_aligned, rf_daily_365);
        vol = ind['Volatilité']; var = ind['VaR 99%']; sharpe = ind['Sharpe']
        corr = np.nan; beta = np.nan; bench_vals = bench_returns.loc[common_idx]
        if np.isfinite(bench_vals).all() and np.isfinite(Y_aligned).all():
            if bench_vals.std(ddof=0) != 0 and Y_aligned.std(ddof=0) != 0:
                 with warnings.catch_warnings(): warnings.simplefilter("ignore"); corr = np.corrcoef(bench_vals, Y_aligned)[0, 1]
            if X_aligned.std(ddof=0) != 0:
                try: model = LinearRegression(); model.fit(X_aligned, Y_aligned); beta = model.coef_[0]
                except ValueError: beta = 0.0

        asset_class = asset_class_map.get(ticker, 'N/A')
        indicators_list.append({'Ticker': ticker, 'Asset Class': asset_class, 'Volatilite Annuelle': vol, 'Beta (vs Benchmark)': beta, 'Correlation (vs Benchmark)': corr, 'VaR 99% (1 jour)': var, 'Sharpe Ratio Annuel': sharpe})

    indicators_df = pd.DataFrame(indicators_list); corr_matrix = returns_aligned.corr()
    
    # Retourne aussi les données pour l'optimisation ET les poids optimaux
    return indicators_df, corr_matrix, bench_indicators_full, asset_class_map, mean_daily_returns_opt, cov_matrix_opt, optimal_weights


#@st.cache_data # Cache peut être problématique ici
def calculate_active_weights(portfolio_weights_df, benchmark_df, prices_hist):
    """Calcule les poids courants du portefeuille et les poids actifs par rapport au benchmark."""
    if portfolio_weights_df is None or benchmark_df is None or prices_hist is None or prices_hist.empty:
        return None

    try:
        if START_DATE_SIMULATION not in prices_hist.index:
            actual_start_prices_date = prices_hist[prices_hist.index >= START_DATE_SIMULATION].index.min()
            if pd.isna(actual_start_prices_date):
                 st.error(f"Cannot find prices at or after simulation start date {START_DATE_SIMULATION.strftime('%Y-%m-%d')}")
                 return None
            start_prices = prices_hist.loc[actual_start_prices_date]
        else:
             start_prices = prices_hist.loc[START_DATE_SIMULATION]

        latest_prices = prices_hist.iloc[-1]

        portfolio_weights_df['BBG Ticker'] = portfolio_weights_df['BBG Ticker'].astype(str)
        benchmark_df['BBG Ticker'] = benchmark_df['BBG Ticker'].astype(str)

        # 1. Calculer les poids benchmark théoriques
        benchmark_composition = {}
        tickers_by_class = get_tickers_by_class(benchmark_df, benchmark_df['BBG Ticker'].unique())
        for class_name, weight_total in BENCHMARK_WEIGHTS.items():
             if class_name.lower() == 'cash':
                 benchmark_composition[CASH_TICKER_NAME] = weight_total
             else:
                 class_key = 'action' if class_name == 'Action' else \
                             'bond' if class_name == 'Gov bond' else \
                             'commodity' if class_name == 'Commodities' else None
                 if class_key and tickers_by_class.get(class_key):
                     num_assets = len(tickers_by_class[class_key])
                     weight_per_asset = weight_total / num_assets if num_assets > 0 else 0
                     for ticker in tickers_by_class[class_key]:
                         benchmark_composition[ticker] = weight_per_asset
        benchmark_weights_series = pd.Series(benchmark_composition, name="Benchmark Weight")

        # 2. Calculer les poids courants du portefeuille
        weights_with_class = portfolio_weights_df.merge(
            benchmark_df[['BBG Ticker', 'Asset Class']], on='BBG Ticker', how='left'
        )

        active_weight_data = []
        total_current_value = 0
        start_fx = start_prices.get('EURUSD Curncy', np.nan)
        latest_fx = latest_prices.get('EURUSD Curncy', np.nan)

        for _, row in weights_with_class.iterrows():
            ticker = str(row['BBG Ticker'])
            initial_weight = row['Weight']
            asset_class = row['Asset Class'] if pd.notna(row['Asset Class']) else ('Cash' if CASH_TICKER_NAME.lower() == ticker.lower() else 'Unknown')

            initial_alloc_eur = initial_weight * INITIAL_NAV_EUR

            if ticker.lower() == CASH_TICKER_NAME.lower():
                init_qty = initial_alloc_eur
                current_value = initial_alloc_eur
            elif ticker in start_prices.index.astype(str) and ticker in latest_prices.index.astype(str) and pd.notna(start_prices[ticker]) and start_prices[ticker] != 0:
                start_price = start_prices[ticker]
                latest_price = latest_prices[ticker]
                if asset_class == 'Commodities' and pd.notna(start_fx) and start_fx != 0 and pd.notna(latest_fx):
                     initial_alloc_usd = initial_alloc_eur / start_fx
                     init_qty = initial_alloc_usd / start_price if start_price != 0 else 0
                     current_value_usd = init_qty * latest_price
                     current_value = current_value_usd * latest_fx
                else:
                    init_qty = initial_alloc_eur / start_price if start_price != 0 else 0
                    current_value = init_qty * latest_price
            else:
                current_value = 0

            if pd.notna(current_value):
                 total_current_value += current_value

            active_weight_data.append({
                'Asset Class': asset_class, 'BBG Ticker': ticker,
                'Current Value (EUR)': current_value
            })

        active_weight_df = pd.DataFrame(active_weight_data)

        if total_current_value != 0:
            active_weight_df['Current Weight'] = active_weight_df['Current Value (EUR)'] / total_current_value
        else:
            active_weight_df['Current Weight'] = 0.0

        # 3. Fusionner avec les poids benchmark et calculer poids actif
        active_weight_df = active_weight_df.set_index('BBG Ticker')
        benchmark_weights_series.index = benchmark_weights_series.index.astype(str)
        combined_df = pd.concat([benchmark_weights_series, active_weight_df[['Asset Class', 'Current Weight']]], axis=1)

        combined_df['Benchmark Weight'] = combined_df['Benchmark Weight'].fillna(0)
        combined_df['Current Weight'] = combined_df['Current Weight'].fillna(0)
        if not isinstance(benchmark_df.index, pd.Index) or benchmark_df.index.name != 'BBG Ticker':
             benchmark_df_indexed_active = benchmark_df.set_index(benchmark_df['BBG Ticker'].astype(str))
        else:
             benchmark_df_indexed_active = benchmark_df.copy()
             benchmark_df_indexed_active.index = benchmark_df_indexed_active.index.astype(str)

        combined_df['Asset Class'] = combined_df['Asset Class'].fillna(benchmark_df_indexed_active['Asset Class'])
        combined_df['Asset Class'] = combined_df['Asset Class'].fillna('Unknown')

        combined_df['Active Weight'] = combined_df['Current Weight'] - combined_df['Benchmark Weight']

        # CORRECTION: Utiliser une LISTE au lieu d'un SET
        active_weight_final = combined_df[
            ['Asset Class', 'Benchmark Weight', 'Current Weight', 'Active Weight']
        ].reset_index().rename(columns={'index': 'BBG Ticker'}).copy()
        active_weight_final.loc[active_weight_final['BBG Ticker'].str.lower() == CASH_TICKER_NAME.lower(), 'Asset Class'] = 'Cash'

        return active_weight_final

    except KeyError as e:
         st.error(f"Error calculating active weights: Missing data for ticker {e} on start or latest date.")
         return None
    except Exception as e:
        st.error(f"Error calculating active weights: {e}")
        return None

def calculate_simulation_performance(portfolio_df, benchmark_df, returns_all, start_date):
    """Calcule les performances de simulation, gérant le cash explicite ET les frais, ET la contribution."""
    if portfolio_df is None or benchmark_df is None or returns_all is None: return None, None, None, None, None
    returns_sim = returns_all[returns_all.index >= start_date].copy()
    if returns_sim.empty: st.warning(f"No data since {start_date.strftime('%Y-%m-%d')}."); return None, None, None, None, None

    cash_daily_365, rf_daily_365, mgmt_fee_daily_365 = calculate_daily_rates()
    tickers = get_tickers_by_class(benchmark_df, returns_sim.columns)

    # --- Benchmark Returns & NAV (Brut) ---
    bench_returns_gross = calculate_benchmark_returns(returns_sim, tickers, cash_daily_365).fillna(0)
    actual_start_brut = bench_returns_gross.index.min()
    actual_start = start_date
    if start_date not in bench_returns_gross.index:
         bench_returns_gross.loc[start_date] = 0.0
         bench_returns_gross = bench_returns_gross.sort_index()

    nav_bench_raw = (1 + bench_returns_gross).cumprod(); nav_bench = nav_bench_raw * 100; nav_bench.name = "Benchmark"

    # --- Portfolio Returns (Brut) & NAV (Net de frais) ---
    weights_dict = portfolio_df.set_index('BBG Ticker')['Weight'].to_dict()

    cash_weight_explicit = 0.0; cash_ticker_found = None
    for ticker, weight in weights_dict.items():
        if CASH_TICKER_NAME.lower() == str(ticker).lower():
            cash_weight_explicit = weight; cash_ticker_found = ticker; break

    portfolio_asset_tickers = [t for t in weights_dict.keys() if str(t) in returns_sim.columns and (cash_ticker_found is None or str(t).lower() != str(cash_ticker_found).lower())]
    portfolio_returns_raw = returns_sim[[str(t) for t in portfolio_asset_tickers]]
    aligned_weights = pd.Series({t: weights_dict[t] for t in portfolio_asset_tickers})
    weighted_asset_returns = portfolio_returns_raw.multiply(aligned_weights, axis=1).sum(axis=1).fillna(0)
    portfolio_returns_gross = weighted_asset_returns + (cash_weight_explicit * cash_daily_365)

    if start_date not in portfolio_returns_gross.index:
        portfolio_returns_gross.loc[start_date] = 0.0
        portfolio_returns_gross = portfolio_returns_gross.sort_index()

    nav_portfolio = pd.Series(index=portfolio_returns_gross.index, dtype=float)
    nav_portfolio.loc[start_date] = 100.0
    start_loc = portfolio_returns_gross.index.get_loc(start_date)
    for i in range(start_loc + 1, len(portfolio_returns_gross)):
         current_date = portfolio_returns_gross.index[i]
         previous_date = portfolio_returns_gross.index[i-1]
         prev_nav = nav_portfolio.loc[previous_date] if previous_date in nav_portfolio.index else nav_portfolio.iloc[i-1]
         daily_gross_return = portfolio_returns_gross.loc[current_date]
         current_nav = prev_nav * (1 + daily_gross_return) * (1 - mgmt_fee_daily_365)
         nav_portfolio.loc[current_date] = current_nav
    nav_portfolio.name = "Votre Fonds (Net)"
    nav_portfolio = nav_portfolio.ffill()

    # --- Calcul Contribution P&L (Brut) ---
    pnl_contributions = []
    if not isinstance(benchmark_df.index, pd.Index) or benchmark_df.index.name != 'BBG Ticker':
         benchmark_df_indexed_contrib = benchmark_df.set_index(benchmark_df['BBG Ticker'].astype(str))
    else: benchmark_df_indexed_contrib = benchmark_df
    asset_class_map_contrib = benchmark_df_indexed_contrib['Asset Class']
    sim_period_returns_contrib = returns_sim[returns_sim.index >= start_date]

    for ticker, initial_weight in weights_dict.items():
        ticker_str = str(ticker)
        asset_class = asset_class_map_contrib.get(ticker_str, 'Cash' if CASH_TICKER_NAME.lower() == ticker_str.lower() else 'Unknown')
        initial_value = initial_weight * 100

        if ticker_str == cash_ticker_found:
             relevant_dates = returns_all[returns_all.index >= start_date].index
             num_days = len(relevant_dates)
             cash_nav = pd.Series(index=relevant_dates, dtype=float)
             if not relevant_dates.empty:
                 cash_nav.iloc[0] = initial_value
                 for d in range(1, num_days):
                     cash_nav.iloc[d] = cash_nav.iloc[d-1] * (1 + cash_daily_365)
                 final_value = cash_nav.iloc[-1]
             else: final_value = initial_value
             pnl = final_value - initial_value

        elif ticker_str in sim_period_returns_contrib.columns:
             cum_ret_asset = (1 + sim_period_returns_contrib[ticker_str]).prod() - 1
             final_value = initial_value * (1 + cum_ret_asset)
             pnl = final_value - initial_value
        else: pnl = 0

        pnl_contributions.append({'Asset Class': asset_class, 'P&L Contribution (Base 100)': pnl})

    contribution_df = pd.DataFrame(pnl_contributions)
    if 'Asset Class' in contribution_df.columns:
        contribution_by_class = contribution_df.groupby('Asset Class')['P&L Contribution (Base 100)'].sum().reset_index()
    else:
        contribution_by_class = pd.DataFrame(columns=['Asset Class', 'P&L Contribution (Base 100)'])

    # --- MODIFICATION: Calcul Ratio d'Information au lieu de TE ---
    portfolio_returns_net = nav_portfolio.pct_change().fillna(0)
    sim_indicators = {"benchmark": {}, "portfolio": {}}
    ir_series = None  # Remplace te_series
    avg_ir = np.nan  # Remplace avg_te
    
    bench_rets_stats = bench_returns_gross[bench_returns_gross.index > start_date]
    port_rets_stats = portfolio_returns_net[portfolio_returns_net.index > start_date]

    if len(bench_rets_stats) >= 1:
        sim_indicators['benchmark'] = calculate_indicators(bench_rets_stats, rf_daily_365)
        sim_indicators['portfolio'] = calculate_indicators(port_rets_stats, rf_daily_365)
        
        if len(bench_rets_stats) >= 2:
            common_ir_index = bench_rets_stats.index.intersection(port_rets_stats.index)
            if not common_ir_index.empty:
                # Calcul des rendements actifs (excédents)
                active_returns = port_rets_stats.loc[common_ir_index] - bench_rets_stats.loc[common_ir_index]
                
                if len(active_returns) >= 2:
                    # Ratio d'Information = Mean(Active Returns) / Std(Active Returns) * sqrt(252)
                    mean_active = active_returns.mean()
                    std_active = active_returns.std()
                    
                    if std_active != 0 and pd.notna(std_active):
                        avg_ir = (mean_active / std_active) * np.sqrt(TRADING_DAYS)
                    
                    # Calcul du RI roulant sur 60 jours
                    window = 60
                    if len(active_returns) >= window:
                        rolling_mean = active_returns.rolling(window=window).mean()
                        rolling_std = active_returns.rolling(window=window).std()
                        
                        # Éviter division par zéro
                        ir_series = (rolling_mean / rolling_std) * np.sqrt(TRADING_DAYS)
                        ir_series = ir_series.replace([np.inf, -np.inf], np.nan).dropna()
                        ir_series.name = "Information Ratio (60j)"
                        
                        if not ir_series.empty:
                            avg_ir = ir_series.mean()

    comparison = pd.DataFrame({'Benchmark': nav_bench, 'Votre Fonds (Net)': nav_portfolio})
    if start_date in comparison.index: comparison.loc[start_date] = 100.0
    else: comparison.loc[start_date] = 100.0; comparison = comparison.sort_index()
    comparison = comparison.ffill()

    # Retourne ir_series et avg_ir au lieu de te_series et avg_te
    return comparison, sim_indicators, ir_series, avg_ir, contribution_by_class

# --- Interface ---

st.markdown(f"""
<div class="bloomberg-header animate-in">
    <div class="session-info">
        <span class="live-indicator"></span>
        <span style="color: {COLORS['success']}; font-weight: 700;">EN DIRECT</span>
    </div>
    <h1>⬛ M2 MBFA TERMINAL</h1>
    <div class="subtitle">
        SYSTÈME D'ANALYSE ET DE GESTION DE PORTEFEUILLE | 
        SESSION: {datetime.now().strftime('%d/%m/%Y %H:%M:%S')} UTC
    </div>
</div>
""", unsafe_allow_html=True)

# --- Data Loading & Processing ---
# Initialisation des variables
benchmark_df, prices_raw, portfolio_df = None, None, None
prices_hist, returns_all = None, None
indicators_full, corr_matrix, bench_indicators_full, asset_map = None, None, None, None
mean_returns_opt, cov_matrix_opt, optimal_weights = None, None, None # Ajout optimal_weights
active_weight_df = None

with st.spinner("CHARGEMENT DES DONNÉES DU MARCHÉ... VEUILLEZ PATIENTER..."):
    benchmark_df, prices_raw, portfolio_df = load_data()
    if benchmark_df is None or prices_raw is None or portfolio_df is None: st.error("Échec du chargement des données critiques."); st.stop()
    prices_hist, returns_all = process_prices(prices_raw)
    if prices_hist is None or returns_all is None: st.error("Échec du traitement des données de prix."); st.stop()
    # --- MODIFIED: Récupération des 7 variables ---
    indicators_full, corr_matrix, bench_indicators_full, asset_map, mean_returns_opt, cov_matrix_opt, optimal_weights = calculate_full_period_indicators(benchmark_df, prices_hist, returns_all)
    # --- FIN MODIFICATION ---
    if indicators_full is None: st.error("Échec du calcul des indicateurs sur la période complète."); st.stop()
    active_weight_df = calculate_active_weights(portfolio_df, benchmark_df, prices_hist)


# --- Market Movers Ticker HTML Generation --- (Inchangé)
if returns_all is not None and not returns_all.empty:
    try:
        latest_date = returns_all.index[-1]
        latest_returns = returns_all.iloc[-1].dropna()

        if benchmark_df is not None:
             investment_universe = benchmark_df['BBG Ticker'].astype(str).str.strip().tolist()
             valid_tickers = [t for t in latest_returns.index if t in investment_universe]
             latest_returns = latest_returns[valid_tickers]

        if not latest_returns.empty:
            top_gainers = latest_returns.nlargest(3)
            top_losers = latest_returns.nsmallest(3)

            ticker_html = f"<div class='market-ticker animate-in'>"
            ticker_html += f"<span class='ticker-label'>📈 MOUVEMENTS DU MARCHÉ | {latest_date.strftime('%d %B %Y')}</span>"
            ticker_html += "<div class='ticker-wrap'><div class='ticker-content'>"
            
            # Création du contenu
            ticker_segment = "<div class='ticker-item'>"
            ticker_segment += f"<strong style='color: {COLORS['success']};'>PLUS FORTES HAUSSES:</strong>&nbsp;&nbsp;"
            for ticker, val in top_gainers.items():
                 ticker_segment += f"<span class='ticker'>{ticker}</span>&nbsp;<span class='price-up'>{val:+.2%}</span>"
            
            ticker_segment += f"&nbsp;&nbsp;<strong style='color: {COLORS['danger']};'>PLUS FORTES BAISSES:</strong>&nbsp;&nbsp;"
            for ticker, val in top_losers.items():
                 ticker_segment += f"<span class='ticker'>{ticker}</span>&nbsp;<span class='price-down'>{val:+.2%}</span>"
            ticker_segment += "</div>"
            
            # Dupliquer le contenu pour un défilement continu sans coupure
            ticker_html += ticker_segment + ticker_segment
            
            ticker_html += "</div></div></div>"
            st.markdown(ticker_html, unsafe_allow_html=True)

    except Exception as e:
        pass
# --- FIN Market Movers ---

# --- Calcul des poids du portefeuille pour la barre latérale --- (Inchangé)
portfolio_class_weights = {}
if portfolio_df is not None and benchmark_df is not None:
    # ... (code inchangé) ...
    portfolio_df['BBG Ticker'] = portfolio_df['BBG Ticker'].astype(str)
    benchmark_df['BBG Ticker'] = benchmark_df['BBG Ticker'].astype(str)
    display_weights_sidebar = portfolio_df.merge(benchmark_df[['BBG Ticker', 'Asset Class']], on='BBG Ticker', how='left')
    cash_row_sidebar = display_weights_sidebar[display_weights_sidebar['BBG Ticker'].str.contains(CASH_TICKER_NAME, case=False, na=False)]
    explicit_cash_weight_sidebar = cash_row_sidebar['Weight'].sum() if not cash_row_sidebar.empty else 0.0
    non_cash_weights_sidebar = display_weights_sidebar[~display_weights_sidebar['BBG Ticker'].str.contains(CASH_TICKER_NAME, case=False, na=False)]
    if 'Asset Class' in display_weights_sidebar.columns:
        class_weights_sidebar = non_cash_weights_sidebar.groupby('Asset Class')['Weight'].sum()
        portfolio_class_weights = class_weights_sidebar.to_dict()
    if explicit_cash_weight_sidebar > 0.0001:
        portfolio_class_weights['Cash'] = explicit_cash_weight_sidebar


# --- Barre Latérale (Sidebar) --- (Inchangé)
st.sidebar.markdown("### ⚙️ PARAMÈTRES SYSTÈME")
with st.sidebar.expander("💼 COMPOSITION DU PORTEFEUILLE", expanded=True):
    st.markdown("**VOTRE ALLOCATION ACTUELLE**")
    bars = create_progress_bar("ACTIONS", portfolio_class_weights.get('Action', 0.0), COLORS['danger'])
    bars += create_progress_bar("OBLIGATIONS", portfolio_class_weights.get('Gov bond', 0.0), COLORS['blue_bright'])
    bars += create_progress_bar("MATIÈRES PREMIÈRES", portfolio_class_weights.get('Commodities', 0.0), COLORS['accent_orange'])
    bars += create_progress_bar("LIQUIDITÉS", portfolio_class_weights.get('Cash', 0.0), COLORS['success'])
    st.markdown(bars, unsafe_allow_html=True)

with st.sidebar.expander("📊 COMPOSITION DU BENCHMARK", expanded=True):
    st.markdown("**STRATÉGIE 60/20/15/5**")
    bench_bars = create_progress_bar("ACTIONS", BENCHMARK_WEIGHTS['Action'], COLORS['danger'])
    bench_bars += create_progress_bar("OBLIGATIONS", BENCHMARK_WEIGHTS['Gov bond'], COLORS['blue_bright'])
    bench_bars += create_progress_bar("MATIÈRES PREMIÈRES", BENCHMARK_WEIGHTS['Commodities'], COLORS['accent_orange'])
    bench_bars += create_progress_bar("LIQUIDITÉS", BENCHMARK_WEIGHTS['Cash'], COLORS['success'])
    st.markdown(bench_bars, unsafe_allow_html=True)

with st.sidebar.expander("💰 TAUX SANS RISQUE & CASH", expanded=True):
    st.metric("TAUX ANNUEL", f"{RISK_FREE_RATE_ANNUAL:.2%}", help="Utilisé pour le calcul du ratio de Sharpe")
    st.caption(f"RÉMUNÉRATION CASH: {CASH_RATE_ANNUAL:.2%} | BASE: {CALENDAR_DAYS} JOURS")

with st.sidebar.expander("💸 FRAIS DE GESTION", expanded=True):
     st.metric("GESTION (ANNUEL)", f"{MANAGEMENT_FEE_ANNUAL:.2%}", help=f"Déduits quotidiennement sur base {CALENDAR_DAYS} jours")
     st.metric("TRANSACTION (PAR ORDRE)", f"{TRANSACTION_FEE_RATE:.2%}", help="Appliqués sur le nominal acheté/vendu")

with st.sidebar.expander("📡 SOURCE DES DONNÉES", expanded=True):
    st.info("**SOURCE**: Google Sheets\n\n**PORTEFEUILLE**: Col C (Ticker) & F (Poids)")
    st.caption(f"DERNIÈRE MAJ: {datetime.now().strftime('%d/%m/%Y %H:%M')}")

# --- TABS EN FRANÇAIS ---
tab1, tab2, tab3 = st.tabs(["📊 SUIVI", "📋 POSITIONS", "📈 ANALYTICS"])

# --- TAB 1: SUIVI (Traduction française) ---
with tab1:
    st.markdown(f"## 📊 ANALYSE DE PERFORMANCE: {START_DATE_SIMULATION.strftime('%d/%m/%Y')} - AUJOURD'HUI")
    
    # MODIFICATION: Renommer les variables retournées
    comparison, sim_ind, ir_series, avg_ir, contribution_by_class = calculate_simulation_performance(
        portfolio_df, benchmark_df, returns_all, START_DATE_SIMULATION
    )

    st.markdown("### 🎯 INDICATEURS RAPIDES")
    if comparison is not None and not comparison.empty:
        try:
            latest_nav_bench = comparison['Benchmark'].iloc[-1]
            latest_nav_port = comparison['Votre Fonds (Net)'].iloc[-1]
            perf_bench = (latest_nav_bench / 100) - 1
            perf_port = (latest_nav_port / 100) - 1
            outperformance = perf_port - perf_bench
            qcol1, qcol2, qcol3, qcol4, qcol5 = st.columns(5)
            qcol1.metric("VL PORTEFEUILLE (NET)", f"{latest_nav_port:.2f}", f"{perf_port:+.2%}")
            qcol2.metric("VL BENCHMARK", f"{latest_nav_bench:.2f}", f"{perf_bench:+.2%}")
            qcol3.metric("SURPERFORMANCE", f"{outperformance:+.2%}")
            if sim_ind:
                qcol4.metric("VOLATILITÉ (ANN.)", f"{sim_ind['portfolio']['Volatilité']:.2%}" if pd.notna(sim_ind['portfolio'].get('Volatilité')) else "N/A", help=f"Annualisée sur {TRADING_DAYS}j")
                qcol5.metric("SHARPE (ANN.)", f"{sim_ind['portfolio']['Sharpe']:.3f}" if pd.notna(sim_ind['portfolio'].get('Sharpe')) else "N/A", help=f"Annualisé vs {RISK_FREE_RATE_ANNUAL:.1%} Rf")
        except Exception as e:
            st.warning(f"Impossible d'afficher les indicateurs: {e}")
    else:
        st.warning("Indicateurs rapides indisponibles.")
    st.markdown("---")

    st.markdown("### 💹 CONTRIBUTION À LA PERFORMANCE (BRUT, BASE 100)")
    if contribution_by_class is not None and not contribution_by_class.empty:
         if 'Asset Class' in contribution_by_class.columns and 'P&L Contribution (Base 100)' in contribution_by_class.columns:
              contrib_chart_data = contribution_by_class.set_index('Asset Class')
              st.bar_chart(contrib_chart_data['P&L Contribution (Base 100)'])
              st.dataframe(contribution_by_class.style.format({'P&L Contribution (Base 100)': '{:+.2f}'}), use_container_width=True)
              st.caption("**Note**: Contribution basée sur les poids initiaux et les rendements bruts cumulés (hors frais).")
         else:
              st.warning("Données de contribution incomplètes.")
    else:
         st.warning("Données de contribution indisponibles.")
    st.markdown("---")

    if sim_ind:
        st.markdown("### 📊 INDICATEURS CLÉS DE PERFORMANCE (PÉRIODE DE SIMULATION)")
        col1, col2 = st.columns(2)
        with col1:
            st.markdown("#### BENCHMARK (BRUT)")
            subcol1, subcol2, subcol3 = st.columns(3)
            subcol1.metric("VOLATILITÉ", f"{sim_ind['benchmark']['Volatilité']:.2%}" if pd.notna(sim_ind['benchmark']['Volatilité']) else "N/A")
            subcol2.metric("SHARPE", f"{sim_ind['benchmark']['Sharpe']:.3f}" if pd.notna(sim_ind['benchmark']['Sharpe']) else "N/A")
            subcol3.metric("VAR 99%", f"{sim_ind['benchmark']['VaR 99%']:.2%}" if pd.notna(sim_ind['benchmark']['VaR 99%']) else "N/A")
        with col2:
            st.markdown("#### PORTEFEUILLE (NET)")
            subcol1, subcol2, subcol3 = st.columns(3)
            subcol1.metric("VOLATILITÉ", f"{sim_ind['portfolio']['Volatilité']:.2%}" if pd.notna(sim_ind['portfolio']['Volatilité']) else "N/A")
            subcol2.metric("SHARPE", f"{sim_ind['portfolio']['Sharpe']:.3f}" if pd.notna(sim_ind['portfolio']['Sharpe']) else "N/A")
            subcol3.metric("VAR 99%", f"{sim_ind['portfolio']['VaR 99%']:.2%}" if pd.notna(sim_ind['portfolio']['VaR 99%']) else "N/A")
    st.markdown("---")

    st.markdown("### 📌 RÉFÉRENCE BENCHMARK (PÉRIODE COMPLÈTE, BRUT)")
    if bench_indicators_full:
        col1, col2, col3 = st.columns(3)
        col1.metric("VOLATILITÉ", f"{bench_indicators_full['Volatilité Annuelle']:.2%}" if pd.notna(bench_indicators_full['Volatilité Annuelle']) else "N/A")
        col2.metric("SHARPE", f"{bench_indicators_full['Ratio de Sharpe Annuel']:.3f}" if pd.notna(bench_indicators_full['Ratio de Sharpe Annuel']) else "N/A")
        col3.metric("VAR 99%", f"{bench_indicators_full['VaR 99% (1 jour)']:.2%}" if pd.notna(bench_indicators_full['VaR 99% (1 jour)']) else "N/A")
    st.markdown("---")

    # MODIFICATION: Graphique avec Ratio d'Information
    st.markdown("### 📈 GRAPHIQUE DE PERFORMANCE & RATIO D'INFORMATION")
    if comparison is not None:
        fig, ax1 = plt.subplots(figsize=(14, 7))
        fig.patch.set_facecolor(COLORS['bg_dark'])
        ax1.set_facecolor(COLORS['bg_panel'])

        ax1.plot(comparison.index, comparison['Benchmark'], color=COLORS['blue_bright'], linewidth=2.5, linestyle='--', label='BENCHMARK (BRUT)', alpha=0.9)
        ax1.plot(comparison.index, comparison['Votre Fonds (Net)'], color=COLORS['accent_orange'], linewidth=2.5, label='PORTEFEUILLE (NET)', alpha=0.9)
        ax1.set_ylabel("VL (BASE 100)", fontsize=11, fontweight='600', color=COLORS['text_primary'], fontfamily='monospace')
        ax1.set_xlabel("DATE", fontsize=10, fontweight='500', color=COLORS['text_secondary'])
        ax1.tick_params(axis='y', labelcolor=COLORS['text_primary'], colors=COLORS['text_primary'])
        ax1.tick_params(axis='x', labelcolor=COLORS['text_secondary'], colors=COLORS['text_secondary'])
        min_val = comparison.min().min() if not comparison.empty else 90
        max_val = comparison.max().max() if not comparison.empty else 110
        ax1.set_ylim(bottom=max(80, min_val - 2), top=min(120, max_val + 2))

        ax1.grid(True, alpha=0.2, linestyle='--', linewidth=0.5, color=COLORS['grid'])
        ax1.spines['bottom'].set_color(COLORS['border'])
        ax1.spines['top'].set_color(COLORS['border'])
        ax1.spines['left'].set_color(COLORS['border'])
        ax1.spines['right'].set_color(COLORS['border'])
        
        # Axe secondaire pour le Ratio d'Information
        ax2 = ax1.twinx()
        ax2.set_ylabel('RATIO D\'INFORMATION (ANN.)', fontsize=11, fontweight='600', color=COLORS['accent_yellow'], fontfamily='monospace')
        ax2.tick_params(axis='y', labelcolor=COLORS['accent_yellow'], colors=COLORS['accent_yellow'])
        
        lines = []; labels = []
        lines1, labels1 = ax1.get_legend_handles_labels()
        lines.extend(lines1); labels.extend(labels1)
        
        if ir_series is not None and not ir_series.empty:
            ir_plot = ir_series
            line_ir, = ax2.plot(ir_plot.index, ir_plot, color=COLORS['accent_yellow'], linewidth=2, label='RI 60J', alpha=0.8)
            lines.append(line_ir)
            labels.append(f'RATIO D\'INFO. (60J ROLL)')
            
            # Ajuster les limites y pour le RI (typiquement entre -2 et 2)
            max_ir_val = ir_plot.max()
            min_ir_val = ir_plot.min()
            y_range = max(abs(max_ir_val), abs(min_ir_val)) if pd.notna(max_ir_val) and pd.notna(min_ir_val) else 1.5
            ax2.set_ylim(-y_range * 1.2, y_range * 1.2)
            
            # Ligne horizontale à 0
            ax2.axhline(0, color=COLORS['text_secondary'], linestyle=':', linewidth=1, alpha=0.5)
            
        elif not np.isnan(avg_ir):
            line_ir = ax2.axhline(avg_ir, color=COLORS['accent_yellow'], linestyle=':', linewidth=2, label=f'RI MOY ({avg_ir:.2f})', alpha=0.8)
            lines.append(line_ir)
            labels.append(f'RI MOYEN ({avg_ir:.2f})')
            ax2.set_ylim(-2, 2)
            ax2.axhline(0, color=COLORS['text_secondary'], linestyle=':', linewidth=1, alpha=0.5)
        else:
            ax2.set_yticks([])

        ax1.legend(lines, labels, loc='upper left', frameon=True, facecolor=COLORS['bg_panel'], edgecolor=COLORS['border'], fontsize=9, labelcolor=COLORS['text_primary'])
        plt.title("SUIVI DE PERFORMANCE & RATIO D'INFORMATION (PORTEFEUILLE NET vs BENCHMARK BRUT)", fontsize=13, fontweight='700', pad=15, color=COLORS['accent_orange'], fontfamily='monospace')
        plt.xticks(rotation=45, fontsize=8)
        fig.tight_layout()
        st.pyplot(fig)
        
        # Affichage métrique RI moyenne
        if not np.isnan(avg_ir):
            col1, col2, col3 = st.columns([1, 1, 1])
            with col2:
                # Déterminer la couleur selon la performance
                ir_color = COLORS['success'] if avg_ir > 0.5 else COLORS['accent_yellow'] if avg_ir > 0 else COLORS['danger']
                st.markdown(f"""
                <div style='text-align: center; padding: 1.5rem; background: linear-gradient(135deg, {COLORS['bg_panel']} 0%, {COLORS['bg_secondary']} 100%); 
                            border: 2px solid {ir_color}; border-radius: 8px; box-shadow: 0 4px 20px rgba(0,0,0,0.5);'>
                    <p style='color: {COLORS['accent_yellow']}; font-size: 0.7rem; font-weight: 700; letter-spacing: 0.2em; margin-bottom: 0.5rem;'>
                        RATIO D'INFORMATION MOYEN
                    </p>
                    <p style='color: {ir_color}; font-size: 2.5rem; font-weight: 800; margin: 0; text-shadow: 0 0 10px {ir_color};'>
                        {avg_ir:.3f}
                    </p>
                    <p style='color: {COLORS['text_secondary']}; font-size: 0.75rem; margin-top: 0.5rem;'>
                        Annualisé ({TRADING_DAYS}j) | Fenêtre 60j
                    </p>
                </div>
                """, unsafe_allow_html=True)
                
                # Interprétation pédagogique
                if avg_ir > 0.5:
                    st.success("✅ **EXCELLENT** : Le portefeuille génère une surperformance significative ajustée du risque actif.")
                elif avg_ir > 0:
                    st.info("📊 **POSITIF** : Le portefeuille surperforme le benchmark de manière constante.")
                elif avg_ir > -0.5:
                    st.warning("⚠️ **SOUS-PERFORMANCE** : Le portefeuille sous-performe légèrement le benchmark.")
                else:
                    st.error("❌ **ATTENTION** : Sous-performance importante par rapport au benchmark.")
    else:
        st.warning("DONNÉES DE SIMULATION INDISPONIBLES")

# --- TAB 2: POSITIONS --- (Inchangé)
with tab2:
    st.markdown("## 📋 POSITIONS DU PORTEFEUILLE")
    if portfolio_df is not None and benchmark_df is not None:
        st.markdown("### 📊 RÉSUMÉ DU PORTEFEUILLE")
        portfolio_df['BBG Ticker'] = portfolio_df['BBG Ticker'].astype(str)
        benchmark_df['BBG Ticker'] = benchmark_df['BBG Ticker'].astype(str)
        display_weights = portfolio_df.merge(benchmark_df[['BBG Ticker', 'Asset Class']], on='BBG Ticker', how='left'); display_weights = display_weights[['Asset Class', 'BBG Ticker', 'Weight']]

        cash_row = display_weights[display_weights['BBG Ticker'].str.contains(CASH_TICKER_NAME, case=False, na=False)]
        explicit_cash_weight = cash_row['Weight'].sum() if not cash_row.empty else 0.0
        non_cash_weights = display_weights[~display_weights['BBG Ticker'].str.contains(CASH_TICKER_NAME, case=False, na=False)]

        col1, col2, col3, col4 = st.columns(4);
        col1.metric("POSITIONS", len(non_cash_weights) + (1 if explicit_cash_weight > 0 else 0))
        col2.metric("POIDS ACTIFS", f"{non_cash_weights['Weight'].sum():.1%}")
        col3.metric("POIDS CASH", f"{explicit_cash_weight:.2%}", help="Défini explicitement dans la feuille 'Portefeuille'")
        avg_weight = non_cash_weights['Weight'].mean() if not non_cash_weights.empty else 0.0
        col4.metric("POIDS MOYEN", f"{avg_weight:.2%}")

        st.markdown("---")
        col_left, col_right = st.columns([2, 1])
        with col_left:
            st.markdown("#### DÉTAIL DES POSITIONS ACTUELLES")
            df_display = pd.concat([non_cash_weights, cash_row]).reset_index(drop=True)
            styled_df = df_display.style.format({'Weight': '{:.2%}'}).background_gradient(subset=['Weight'], cmap='YlOrRd', vmin=0, vmax=max(0.01, df_display['Weight'].max()))
            st.dataframe(styled_df, use_container_width=True, height=400)
        with col_right:
            st.markdown("#### RÉPARTITION PAR CLASSE D'ACTIF")
            if 'Asset Class' in display_weights.columns:
                class_weights = non_cash_weights.groupby('Asset Class')['Weight'].sum().sort_values(ascending=False);
                for asset_class, weight in class_weights.items(): st.metric(asset_class.upper(), f"{weight:.2%}")
                if explicit_cash_weight > 0.0001: st.metric("CASH", f"{explicit_cash_weight:.2%}")
            else: st.warning("Données de classe d'actif indisponibles")
        st.markdown("---")

        # --- Section Active Weight ---
        st.markdown("### ⚖️ ANALYSE DES POIDS ACTIFS (vs Benchmark)")
        if active_weight_df is not None:
            latest_active_date = prices_hist.index[-1].strftime('%d %b %Y') if prices_hist is not None else "N/A"
            st.caption(f"**Comparaison** des poids actuels du portefeuille vs benchmark (au {latest_active_date}).")

            def color_active_weight_styler(val):
                """Applies color based on active weight value for Styler."""
                if pd.isna(val): return ''
                threshold = 0.0001
                color = COLORS['danger'] if val < -threshold else COLORS['success'] if val > threshold else COLORS['text_secondary']
                return f'color: {color}; font-weight: bold;'

            active_weight_display = active_weight_df[
                (abs(active_weight_df['Benchmark Weight']) > 1e-6) | (abs(active_weight_df['Current Weight']) > 1e-6)
            ].copy()

            styled_active_df = active_weight_display.style.format({
                'Benchmark Weight': '{:.2%}',
                'Current Weight': '{:.2%}',
                'Active Weight': '{:+.2%}'
            }).apply(lambda s: s.map(color_active_weight_styler), subset=['Active Weight'])

            st.dataframe(styled_active_df, use_container_width=True, height=450)

            st.markdown("#### VISUALISATION DES POIDS ACTIFS")
            active_chart_data = active_weight_display[abs(active_weight_display['Active Weight']) > 1e-6].set_index('BBG Ticker')['Active Weight']
            if not active_chart_data.empty:
                st.bar_chart(active_chart_data)
            else:
                st.info("Aucun poids actif significatif à afficher.")
        else:
            st.warning("Données de poids actifs indisponibles.")
        st.markdown("---")

        st.markdown("### 📊 VISUALISATION DE L'ALLOCATION (Actuelle)")
        if 'Asset Class' in display_weights.columns:
            current_class_weights = non_cash_weights.groupby('Asset Class')['Weight'].sum();
            if explicit_cash_weight > 0.0001: current_class_weights['Cash'] = explicit_cash_weight
            class_data_pie = current_class_weights[current_class_weights > 0]

            if not class_data_pie.empty:
                fig_pie, ax_pie = plt.subplots(figsize=(10, 6)); fig_pie.patch.set_facecolor(COLORS['bg_dark']); ax_pie.set_facecolor(COLORS['bg_dark'])
                colors_pie = [COLORS['danger'], COLORS['blue_bright'], COLORS['accent_orange'], COLORS['success'], COLORS['accent_yellow']]
                wedges, texts, autotexts = ax_pie.pie(class_data_pie.values, labels=class_data_pie.index, autopct='%1.1f%%', colors=colors_pie[:len(class_data_pie)], startangle=90, textprops={'fontsize': 10, 'fontweight': '600', 'color': COLORS['text_primary'], 'fontfamily': 'monospace'})
                for autotext in autotexts: autotext.set_color(COLORS['bg_dark']); autotext.set_fontweight('bold'); autotext.set_fontsize(11)
                ax_pie.set_title("ALLOCATION PAR CLASSE D'ACTIF", fontsize=13, fontweight='700', pad=15, color=COLORS['accent_orange'], fontfamily='monospace'); st.pyplot(fig_pie)
            else: st.warning("Aucune donnée d'allocation.")
        st.markdown("---")
        st.markdown("### 📜 RÈGLES DE GESTION & CONTRAINTES")
        st.markdown(f"""
        <div class='bloomberg-panel'>
            <h4>📋 Résumé du Mandat de Gestion</h4>
            <ul>
                <li><strong>Frais de Gestion:</strong> {MANAGEMENT_FEE_ANNUAL:.2%} p.a. (déduits quotidiennement)</li>
                <li><strong>Rémunération Cash:</strong> {CASH_RATE_ANNUAL:.2%} p.a. (appliquée quotidiennement)</li>
                <li><strong>Frais de Transaction:</strong> {TRANSACTION_FEE_RATE:.2%} par ordre. <span style='color:{COLORS['text_secondary']};'>*Note: Non appliqués dans la simulation actuelle.*</span></li>
                <li><strong>Facilité de Découvert:</strong> Jusqu'à 20% autorisé (sous conditions).</li>
                <li><strong>Calcul du Risque (si Levier):</strong> VaR (1j, 99%) obligatoire.</li>
                <li><strong>Base de Trading:</strong> Prix de clôture.</li>
                <li><strong>Univers d'Investissement:</strong> Composants du benchmark uniquement.</li>
                <li><strong>Objectif:</strong> Battre le benchmark.</li>
            </ul>
        </div>
        """, unsafe_allow_html=True)
        st.warning("**🔧 SIMULATEUR DE TRANSACTIONS**\n\n*EN DÉVELOPPEMENT*\n\nDisponible prochainement pour tester vos stratégies.")
    else:
        st.error("DONNÉES DU PORTEFEUILLE INDISPONIBLES")


# --- TAB 3: ANALYTICS --- (Inchangé)
with tab3:
    st.markdown("## ASSET ANALYTICS")
    if indicators_full is not None and corr_matrix is not None and bench_indicators_full is not None:
        subtab1, subtab2, subtab3 = st.tabs(["INDICATORS", "VISUAL ANALYSIS", "CORRELATION"])
        with subtab1:
            st.markdown("### ASSET CHARACTERISTICS"); st.caption("Calculated over full historical period")
            col1, col2, col3, col4 = st.columns(4); col1.metric("ASSETS ANALYZED", len(indicators_full))
            avg_vol = indicators_full['Volatilite Annuelle'].mean(); col2.metric("AVG VOL (ANN.)", f"{avg_vol:.2%}")
            avg_sharpe = indicators_full['Sharpe Ratio Annuel'].mean(); col3.metric("AVG SHARPE (ANN.)", f"{avg_sharpe:.3f}")
            avg_beta = indicators_full['Beta (vs Benchmark)'].mean(); col4.metric("AVG BETA", f"{avg_beta:.2f}")
            st.markdown("---")
            col_filter1, col_filter2 = st.columns(2)
            with col_filter1: asset_classes = ['ALL'] + sorted(list(indicators_full['Asset Class'].dropna().unique())); selected_class = st.selectbox("FILTER BY ASSET CLASS", asset_classes, key="filter_indicators")
            with col_filter2: sort_by = st.selectbox("SORT BY", ['Ticker', 'Volatilite Annuelle', 'Sharpe Ratio Annuel', 'Beta (vs Benchmark)'], key="sort_indicators")
            if selected_class == 'ALL': filtered_df = indicators_full.copy()
            else: filtered_df = indicators_full[indicators_full['Asset Class'] == selected_class].copy()
            filtered_df = filtered_df.sort_values(by=sort_by, ascending=(sort_by != 'Sharpe Ratio Annuel'))
            styled_indicators = filtered_df.style.format({
                'Volatilite Annuelle': '{:.2%}', 'Beta (vs Benchmark)': '{:.2f}',
                'Correlation (vs Benchmark)': '{:.2f}', 'VaR 99% (1 jour)': '{:.2%}',
                'Sharpe Ratio Annuel': '{:.3f}'
            }, na_rep='N/A').background_gradient(
                subset=['Sharpe Ratio Annuel'], cmap='RdYlGn', vmin=-1, vmax=2
            ).background_gradient(
                subset=['Volatilite Annuelle'], cmap='Reds', vmin=0, vmax=max(0.01, filtered_df['Volatilite Annuelle'].max()) if not filtered_df.empty else 1
            ).background_gradient(
                 subset=['Beta (vs Benchmark)'], cmap='coolwarm', vmin=min(0, filtered_df['Beta (vs Benchmark)'].min()) if not filtered_df.empty else 0, vmax=max(1.5, filtered_df['Beta (vs Benchmark)'].max()) if not filtered_df.empty else 1.5
            ).background_gradient(
                 subset=['Correlation (vs Benchmark)'], cmap='coolwarm', vmin=-1, vmax=1
            )

            st.dataframe(styled_indicators, use_container_width=True, height=500)
            csv = filtered_df.to_csv(index=False).encode('utf-8'); st.download_button("DOWNLOAD CSV", csv, f"indicators_{selected_class.lower()}.csv", "text/csv", key='download_indicators')
        with subtab2:
            st.markdown("### RISK-RETURN ANALYSIS")
            col1, col2, col3 = st.columns([1, 2, 1])
            with col2: asset_classes_viz = ['ALL'] + sorted(list(indicators_full['Asset Class'].dropna().unique())); selected_class_viz = st.selectbox("FILTER BY CLASS", asset_classes_viz, key="filter_viz")
            if selected_class_viz == 'ALL': data_plot = indicators_full.dropna(subset=['Beta (vs Benchmark)', 'Volatilite Annuelle'])
            else: data_plot = indicators_full[indicators_full['Asset Class'] == selected_class_viz].dropna(subset=['Beta (vs Benchmark)', 'Volatilite Annuelle'])
            st.info(f"Displaying **{len(data_plot)}** assets")
            if not data_plot.empty:
                fig_scatter, ax_scatter = plt.subplots(figsize=(12, 7)); fig_scatter.patch.set_facecolor(COLORS['bg_dark']); ax_scatter.set_facecolor(COLORS['bg_panel'])
                class_colors = {'Action': COLORS['danger'], 'Gov bond': COLORS['success'], 'Commodities': COLORS['accent_orange']} # Rouge, Turquoise, Orange
                for asset_class in data_plot['Asset Class'].unique():
                    if pd.notna(asset_class): subset = data_plot[data_plot['Asset Class'] == asset_class]; ax_scatter.scatter(subset['Beta (vs Benchmark)'], subset['Volatilite Annuelle'] * 100, label=asset_class, s=120, alpha=0.8, color=class_colors.get(asset_class, COLORS['text_secondary']), edgecolors=COLORS['text_primary'], linewidth=1.5)
                ax_scatter.set_xlabel('BETA (VS BENCHMARK)', fontsize=11, fontweight='600', color=COLORS['text_primary'], fontfamily='monospace'); ax_scatter.set_ylabel('ANNUAL VOLATILITY (%)', fontsize=11, fontweight='600', color=COLORS['text_primary'], fontfamily='monospace'); ax_scatter.set_title('RISK-BETA ANALYSIS', fontsize=13, fontweight='700', pad=15, color=COLORS['accent_orange'], fontfamily='monospace'); ax_scatter.grid(True, alpha=0.2, linestyle='--', linewidth=0.5, color=COLORS['grid']); ax_scatter.tick_params(colors=COLORS['text_secondary']); ax_scatter.spines['bottom'].set_color(COLORS['border']); ax_scatter.spines['top'].set_color(COLORS['border']); ax_scatter.spines['left'].set_color(COLORS['border']); ax_scatter.spines['right'].set_color(COLORS['border'])
                legend = ax_scatter.legend(loc='best', frameon=True, facecolor=COLORS['bg_panel'], edgecolor=COLORS['border'], fontsize=9); [text.set_color(COLORS['text_primary']) for text in legend.get_texts()]
                ax_scatter.axvline(1.0, color=COLORS['text_secondary'], linestyle='--', alpha=0.5, linewidth=1.5); fig_scatter.tight_layout(); st.pyplot(fig_scatter)
                st.markdown("---")
                st.markdown("### SHARPE RATIO VS VOLATILITY")
                data_plot_sharpe = data_plot.dropna(subset=['Sharpe Ratio Annuel'])
                if not data_plot_sharpe.empty:
                    fig_sharpe, ax_sharpe = plt.subplots(figsize=(12, 7)); fig_sharpe.patch.set_facecolor(COLORS['bg_dark']); ax_sharpe.set_facecolor(COLORS['bg_panel'])
                    for asset_class in data_plot_sharpe['Asset Class'].unique():
                        if pd.notna(asset_class): subset = data_plot_sharpe[data_plot_sharpe['Asset Class'] == asset_class]; ax_sharpe.scatter(subset['Volatilite Annuelle'] * 100, subset['Sharpe Ratio Annuel'], label=asset_class, s=120, alpha=0.8, color=class_colors.get(asset_class, COLORS['text_secondary']), edgecolors=COLORS['text_primary'], linewidth=1.5)
                    ax_sharpe.set_xlabel('ANNUAL VOLATILITY (%)', fontsize=11, fontweight='600', color=COLORS['text_primary'], fontfamily='monospace'); ax_sharpe.set_ylabel('SHARPE RATIO (ANN.)', fontsize=11, fontweight='600', color=COLORS['text_primary'], fontfamily='monospace'); ax_sharpe.set_title('RISK-ADJUSTED RETURN', fontsize=13, fontweight='700', pad=15, color=COLORS['accent_orange'], fontfamily='monospace'); ax_sharpe.grid(True, alpha=0.2, linestyle='--', linewidth=0.5, color=COLORS['grid']); ax_sharpe.tick_params(colors=COLORS['text_secondary']); ax_sharpe.spines['bottom'].set_color(COLORS['border']); ax_sharpe.spines['top'].set_color(COLORS['border']); ax_sharpe.spines['left'].set_color(COLORS['border']); ax_sharpe.spines['right'].set_color(COLORS['border'])
                    legend = ax_sharpe.legend(loc='best', frameon=True, facecolor=COLORS['bg_panel'], edgecolor=COLORS['border'], fontsize=9); [text.set_color(COLORS['text_primary']) for text in legend.get_texts()]
                    ax_sharpe.axhline(0, color=COLORS['text_secondary'], linestyle='--', alpha=0.5, linewidth=1.5); fig_sharpe.tight_layout(); st.pyplot(fig_sharpe)
                else: st.warning("Données Sharpe insuffisantes")
            else: st.warning("Aucune donnée à afficher")
        with subtab3:
            st.markdown("### CORRELATION MATRIX"); st.caption("Calculated over full historical period")
            if corr_matrix is not None and not corr_matrix.empty:
                col1, col2, col3, col4 = st.columns(4); corr_values = corr_matrix.values[np.triu_indices_from(corr_matrix.values, k=1)]; col1.metric("AVG CORR", f"{corr_values.mean():.2f}"); col2.metric("MAX CORR", f"{corr_values.max():.2f}"); col3.metric("MIN CORR", f"{corr_values.min():.2f}"); col4.metric("STD DEV", f"{corr_values.std():.2f}")
                st.markdown("---")
                all_assets = corr_matrix.columns.tolist(); col_filter1, col_filter2 = st.columns(2)
                with col_filter1: show_all = st.checkbox("SHOW ALL ASSETS", value=True)
                if not show_all:
                    with col_filter2: n_assets = st.slider("NUMBER OF ASSETS", min_value=5, max_value=min(50, len(all_assets)), value=min(20, len(all_assets))); selected_assets = all_assets[:n_assets]; corr_display = corr_matrix.loc[selected_assets, selected_assets]
                else: corr_display = corr_matrix
                styled_corr = corr_display.style.background_gradient(cmap='coolwarm', vmin=-1, vmax=1).format("{:.2f}", na_rep='N/A')
                st.dataframe(styled_corr, use_container_width=True, height=600)
                csv_corr = corr_display.to_csv().encode('utf-8'); st.download_button("DOWNLOAD MATRIX", csv_corr, "correlation_matrix.csv", "text/csv", key='download_corr')
                st.markdown("---")
                st.markdown("### CORRELATION HEATMAP")
                fig_heatmap, ax_heatmap = plt.subplots(figsize=(14, 12)); fig_heatmap.patch.set_facecolor(COLORS['bg_dark'])
                if len(corr_display) > 30: st.info(f"Display limited to first 30 assets"); corr_viz = corr_display.iloc[:30, :30]
                else: corr_viz = corr_display
                im = ax_heatmap.imshow(corr_viz, cmap='coolwarm', aspect='auto', vmin=-1, vmax=1)
                cbar = plt.colorbar(im, ax=ax_heatmap); cbar.set_label('CORRELATION', rotation=270, labelpad=20, fontsize=10, fontweight='600', color=COLORS['text_primary'], fontfamily='monospace'); cbar.ax.tick_params(colors=COLORS['text_secondary'])
                ax_heatmap.set_xticks(range(len(corr_viz.columns))); ax_heatmap.set_yticks(range(len(corr_viz.index))); ax_heatmap.set_xticklabels(corr_viz.columns, rotation=90, fontsize=7, color=COLORS['text_secondary']); ax_heatmap.set_yticklabels(corr_viz.index, fontsize=7, color=COLORS['text_secondary']); ax_heatmap.set_title('CORRELATION HEATMAP', fontsize=13, fontweight='700', pad=15, color=COLORS['accent_orange'], fontfamily='monospace'); fig_heatmap.tight_layout(); st.pyplot(fig_heatmap)
            else: st.error("Correlation matrix unavailable")
    else: st.error("Analytics data unavailable")

# --- Footer Bloomberg Style ---
st.markdown("---")
st.markdown(f"""
<div class="footer-terminal">
    <strong>M2 MBFA TERMINAL</strong> | SYSTÈME D'ANALYSE DE PORTEFEUILLE PROFESSIONNEL<br>
    SESSION: {datetime.now().strftime('%d/%m/%Y %H:%M:%S UTC')} | 
    VERSION: <strong>v3.4 ÉDITION FRANÇAISE PREMIUM | RATIO D'INFORMATION</strong><br>
    © 2025 | Tous droits réservés
</div>
""", unsafe_allow_html=True)