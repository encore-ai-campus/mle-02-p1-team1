"""모든 화면이 공유하는 레이아웃과 짧은 설명 요소."""
from html import escape
import streamlit as st


def apply_theme():
    st.markdown('''<style>
    :root { --ink:#24383b; --muted:#65777c; --line:#e1e8e8; --accent:#168269; }
    .stApp { background:#f6f8f8; color:var(--ink); }
    .block-container { max-width:1180px; padding:2.2rem 2rem 4rem; }
    [data-testid="stSidebar"] { background:#fff; border-right:1px solid var(--line); }
    [data-testid="stSidebar"] h2 { font-size:1.35rem; letter-spacing:.02em; }
    h1,h2,h3 { color:var(--ink); letter-spacing:-.035em; }
    h1 { font-size:2.35rem !important; line-height:1.25 !important; }
    h2 { font-size:1.5rem !important; } h3 { font-size:1.15rem !important; }
    p,li { line-height:1.8; } [data-testid="stCaptionContainer"] { color:var(--muted); }
    [data-testid="stVerticalBlockBorderWrapper"] { background:#fff; border-radius:16px; }
    [data-testid="stMetric"] { background:#fff; border:1px solid var(--line); padding:16px 18px; border-radius:14px; }
    [data-testid="stMetricLabel"] { color:var(--muted); } [data-testid="stMetricValue"] { font-size:1.8rem; }
    .portal-hero { margin-bottom:28px; padding:26px 30px; background:#edf5f2; border:1px solid #dcece5; border-radius:20px; }
    .portal-hero .eyebrow { font-size:11px; letter-spacing:.14em; color:#168269; font-weight:700; margin-bottom:12px; }
    .portal-hero h1 { margin:0 0 10px; padding:0; } .portal-hero p { margin:0; color:#536b67; max-width:760px; }
    .step-list { display:grid; gap:12px; margin:16px 0; }
    .step-card { display:flex; gap:15px; padding:17px 20px; background:#fff; border:1px solid var(--line); border-radius:13px; }
    .step-no { flex-shrink:0; width:30px; height:30px; background:#e9f4ee; border-radius:9px; color:#168269; text-align:center; line-height:30px; font-weight:700; }
    .step-card strong { color:var(--ink); } .step-card p { margin:3px 0 0; color:#65777c; font-size:14px; }
    .portal-note { border-left:3px solid #168269; padding:12px 16px; background:#edf5f2; border-radius:0 8px 8px 0; margin:16px 0; line-height:1.8; }
    .portal-footer { color:#75868b; font-size:12px; padding-top:28px; margin-top:24px; border-top:1px solid var(--line); }
    button { border-radius:9px !important; } [data-baseweb="textarea"] { border-radius:12px; }
    @media(max-width:700px) { .block-container { padding:1rem .9rem 3rem; } .portal-hero { padding:21px 20px; } h1{font-size:1.8rem !important;} }
    </style>''', unsafe_allow_html=True)


def hero(eyebrow, title, description):
    st.markdown(f'<section class="portal-hero"><div class="eyebrow">{escape(eyebrow)}</div><h1>{escape(title)}</h1><p>{escape(description)}</p></section>', unsafe_allow_html=True)


def steps(items):
    cards = ''.join(f'<div class="step-card"><div class="step-no">{i}</div><div><strong>{escape(title)}</strong><p>{escape(text)}</p></div></div>'
                    for i, (title, text) in enumerate(items, 1))
    st.markdown(f'<div class="step-list">{cards}</div>', unsafe_allow_html=True)


def note(text):
    st.markdown(f'<div class="portal-note">{escape(text)}</div>', unsafe_allow_html=True)


def footer():
    st.markdown('<div class="portal-footer">CASPER MANUAL LAB · 캐스퍼 일렉트릭 매뉴얼 기반 프로젝트 · 기록 기준 2026.10.02</div>', unsafe_allow_html=True)
