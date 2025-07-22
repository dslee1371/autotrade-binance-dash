import os

import streamlit as st
import pandas as pd
import numpy as np
import plotly.express as px
import plotly.graph_objects as go
from plotly.subplots import make_subplots
from datetime import datetime, timedelta
from dotenv import load_dotenv
load_dotenv()
import time

# --- SQLAlchemy import 추가 ---
from sqlalchemy import create_engine

# MySQL 연결 정보 (환경변수로 관리하세요)
user     = os.getenv("MYSQL_USER")      # ex) 'myuser'
password = os.getenv("MYSQL_PASSWORD")  # ex) 'myp@ss:word'
host     = "mysql"
port     = 3306
db_name  = "mydb"


# mysql+mysqlconnector://<사용자>:<비밀번호>@<호스트>:<포트>/<데이터베이스>
DB_URI = f"mysql+mysqlconnector://{user}:{password}@{host}:{port}/{db_name}"

engine = create_engine(
    DB_URI,
    pool_pre_ping=True,
)

# 페이지 설정
st.set_page_config(
    page_title="비트코인 트레이딩 봇 대시보드",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="expanded"
)

# 스타일 설정
st.markdown("""
<style>
    .main-header {
        font-size: 2.5rem;
        font-weight: bold;
        color: #FF9500;
        margin-bottom: 1rem;
    }
    .sub-header {
        font-size: 1.5rem;
        font-weight: bold;
        color: #FF9500;
        margin-top: 2rem;
        margin-bottom: 1rem;
    }
    .profit {
        color: #00CC96;
        font-weight: bold;
    }
    .loss {
        color: #EF553B;
        font-weight: bold;
    }
    .info-box {
        background-color: #262730;
        padding: 1rem;
        border-radius: 0.5rem;
        margin-bottom: 1rem;
    }
    .stat-value {
        font-size: 1.8rem;
        font-weight: bold;
    }
    .stat-label {
        font-size: 0.9rem;
        color: #888;
    }
</style>
""", unsafe_allow_html=True)

# DB 설정
def get_connection():
    """MySQL 데이터베이스 연결을 리턴"""
    try:
        if DRIVER == 'mysql-connector':
            return db_driver.connect(
                host=DB_CONFIG['host'],
                port=DB_CONFIG['port'],
                user=DB_CONFIG['user'],
                password=DB_CONFIG['password'],
                database=DB_CONFIG['database'],
                auth_plugin='mysql_native_password'
            )
        else:
            return db_driver.connect(
                host=DB_CONFIG['host'],
                port=DB_CONFIG['port'],
                user=DB_CONFIG['user'],
                password=DB_CONFIG['password'],
                database=DB_CONFIG['database'],
                charset='utf8mb4',
                cursorclass=db_driver.cursors.DictCursor
            )
    except Error as e:
        print(f"Error connecting to MySQL ({DRIVER}): {e}")
        raise

# 데이터 로딩 함수
@st.cache_data(ttl=60)  # 60초마다 데이터 갱신
def load_trades_data():
    query = """
    SELECT t.id, t.timestamp, t.action, t.entry_price, t.amount, t.order_size, 
           t.leverage, t.stop_loss, t.take_profit, t.kelly_fraction, t.win_probability, 
           t.volatility, t.status,
           tr.close_timestamp, tr.close_price, tr.pnl, tr.pnl_percentage, tr.result
    FROM trades t
    LEFT JOIN trade_results tr ON t.id = tr.trade_id
    ORDER BY t.timestamp DESC
    """
    # SQLAlchemy 엔진을 직접 전달
    df = pd.read_sql_query(query, engine)
    
    # 날짜 열 변환
    df['timestamp']       = pd.to_datetime(df['timestamp'])
    df['close_timestamp'] = pd.to_datetime(df['close_timestamp'])
    
    # 거래 기간 계산
    df['duration'] = df.apply(
        lambda row: (row['close_timestamp'] - row['timestamp']).total_seconds() / 60 
        if not pd.isna(row['close_timestamp']) else None, 
        axis=1
    )
    return df

@st.cache_data(ttl=60)
def load_account_history():
    query = """
    SELECT timestamp, balance, equity, unrealized_pnl
    FROM account_history
    ORDER BY timestamp
    """
    df = pd.read_sql_query(query, engine)
    df['timestamp'] = pd.to_datetime(df['timestamp'])
    return df

# 거래 성과 통계 계산 함수
def calculate_performance_stats(trades_df):
    if trades_df.empty:
        return {
            'total_trades': 0,
            'profitable_trades': 0,
            'losing_trades': 0,
            'win_rate': 0,
            'avg_profit': 0,
            'avg_loss': 0,
            'total_pnl': 0,
            'max_profit': 0,
            'max_loss': 0,
            'avg_duration': 0,
            'long_win_rate': 0,
            'short_win_rate': 0,
            'total_long': 0,
            'total_short': 0
        }
    
    # 닫힌 거래만 필터링
    closed_trades = trades_df[trades_df['status'] == 'closed']
    if closed_trades.empty:
        return {
            'total_trades': 0,
            'profitable_trades': 0,
            'losing_trades': 0,
            'win_rate': 0,
            'avg_profit': 0,
            'avg_loss': 0,
            'total_pnl': 0,
            'max_profit': 0,
            'max_loss': 0,
            'avg_duration': 0,
            'long_win_rate': 0,
            'short_win_rate': 0,
            'total_long': 0,
            'total_short': 0
        }
    
    # 수익 거래와 손실 거래 분리
    profitable_trades = closed_trades[closed_trades['pnl'] > 0]
    losing_trades = closed_trades[closed_trades['pnl'] <= 0]
    
    # 방향별 거래 필터링
    long_trades = closed_trades[closed_trades['action'] == 'long']
    short_trades = closed_trades[closed_trades['action'] == 'short']
    
    # 방향별 수익 거래
    long_profitable = long_trades[long_trades['pnl'] > 0]
    short_profitable = short_trades[short_trades['pnl'] > 0]
    
    # 통계 계산
    total_trades = len(closed_trades)
    profitable_count = len(profitable_trades)
    losing_count = len(losing_trades)
    win_rate = profitable_count / total_trades if total_trades > 0 else 0
    
    avg_profit = profitable_trades['pnl'].mean() if not profitable_trades.empty else 0
    avg_loss = losing_trades['pnl'].mean() if not losing_trades.empty else 0
    total_pnl = closed_trades['pnl'].sum()
    
    max_profit = profitable_trades['pnl'].max() if not profitable_trades.empty else 0
    max_loss = losing_trades['pnl'].min() if not losing_trades.empty else 0
    
    avg_duration = closed_trades['duration'].mean() if 'duration' in closed_trades.columns else 0
    
    long_win_rate = len(long_profitable) / len(long_trades) if len(long_trades) > 0 else 0
    short_win_rate = len(short_profitable) / len(short_trades) if len(short_trades) > 0 else 0
    
    return {
        'total_trades': total_trades,
        'profitable_trades': profitable_count,
        'losing_trades': losing_count,
        'win_rate': win_rate,
        'avg_profit': avg_profit,
        'avg_loss': avg_loss,
        'total_pnl': total_pnl,
        'max_profit': max_profit,
        'max_loss': max_loss,
        'avg_duration': avg_duration,
        'long_win_rate': long_win_rate,
        'short_win_rate': short_win_rate,
        'total_long': len(long_trades),
        'total_short': len(short_trades)
    }

# 시간대별 성과 분석
def analyze_time_performance(trades_df):
    if trades_df.empty:
        return pd.DataFrame()

    # ① copy() 추가
    closed_trades = trades_df[trades_df['status']=='closed'].copy()
    if closed_trades.empty:
        return pd.DataFrame()

    closed_trades['hour']      = closed_trades['timestamp'].dt.hour
    closed_trades['time_slot'] = (closed_trades['hour']//4)*4
    closed_trades['time_range']= closed_trades['time_slot'].apply(
                                    lambda x: f"{x:02d}-{(x+4)%24:02d}"
                                 )

    # ② observed=False 명시
    time_performance = closed_trades.groupby('time_range', observed=False).agg({
        'id': 'count',
        'pnl': ['sum', 'mean', lambda x: (x>0).sum()/len(x) if len(x)>0 else 0]
    }).reset_index()

    time_performance.columns = [
        'time_range', 'trade_count', 'total_pnl', 'avg_pnl', 'win_rate'
    ]
    return time_performance


# 변동성 기반 성과 분석
def analyze_volatility_performance(trades_df):
    if trades_df.empty:
        return pd.DataFrame()
    
    closed_trades = trades_df[trades_df['status'] == 'closed'].copy()  # <- .copy() 추가
    if closed_trades.empty:
        return pd.DataFrame()
    
    bins = [0, 1, 2, 3, float('inf')]
    labels = ['0-1%', '1-2%', '2-3%', '3%+']
    
    closed_trades['volatility_range'] = pd.cut(closed_trades['volatility'], bins=bins, labels=labels, right=False)
    
    volatility_performance = closed_trades.groupby('volatility_range', observed=False).agg({
        'id': 'count',
        'pnl': ['sum', 'mean', lambda x: (x > 0).sum() / len(x) if len(x) > 0 else 0]
    }).reset_index()
    
    volatility_performance.columns = ['volatility_range', 'trade_count', 'total_pnl', 'avg_pnl', 'win_rate']
    return volatility_performance


# 켈리 비율 기반 성과 분석
def analyze_kelly_performance(trades_df):
    if trades_df.empty:
        return pd.DataFrame()

    # ① copy() 로 명시적 복사본 만들기
    closed_trades = trades_df[trades_df['status']=='closed'].copy()
    if closed_trades.empty:
        return pd.DataFrame()

    bins   = [0, 0.02, 0.05, 0.08, 0.1, 1.0]
    labels = ['0-2%', '2-5%', '5-8%', '8-10%', '10%+']

    closed_trades['kelly_range'] = pd.cut(
        closed_trades['kelly_fraction'],
        bins=bins,
        labels=labels,
        right=False
    )

    # ② observed=False 를 명시
    kelly_performance = closed_trades.groupby('kelly_range', observed=False).agg({
        'id': 'count',
        'pnl': [
            'sum',
            'mean',
            lambda x: (x>0).sum()/len(x) if len(x)>0 else 0
        ]
    }).reset_index()

    kelly_performance.columns = [
        'kelly_range', 'trade_count', 'total_pnl', 'avg_pnl', 'win_rate'
    ]
    return kelly_performance


# 최신 활성 거래 정보 가져오기
def get_active_trade_info(trades_df):
    if trades_df.empty:
        return None
    
    # 오픈된 거래만 필터링
    open_trades = trades_df[trades_df['status'] == 'open']
    if open_trades.empty:
        return None
    
    # 가장 최근의 오픈된 거래
    latest_open = open_trades.iloc[0]
    return latest_open

# PnL 색상 강조 함수 (데이터프레임 표시용)
def color_pnl(val):
    if pd.isna(val):
        color = 'black'
    elif val > 0:
        color = '#00CC96'  # 수익은 녹색
    elif val < 0:
        color = '#EF553B'  # 손실은 빨간색
    else:
        color = 'white'
    return f'color: {color}'

# 메인 대시보드 UI
def main():
    # 헤더
    st.markdown('<div class="main-header">비트코인 트레이딩 봇 대시보드</div>', unsafe_allow_html=True)
    
    
    # 데이터 로딩
    with st.spinner('데이터 로딩 중...'):
        try:
            trades_df = load_trades_data()
            account_history = load_account_history()
        except Exception as e:
            st.error(f"데이터 로딩 중 오류가 발생했습니다: {str(e)}")
            return
    
    # 사이드바
    st.sidebar.header("설정")
    refresh_interval = st.sidebar.slider("자동 새로고침 간격(초)", 5, 300, 60)
    date_range = st.sidebar.date_input(
        "날짜 범위",
        value=(datetime.now() - timedelta(days=30), datetime.now()),
        max_value=datetime.now()
    )
    
    # 필터 적용된 데이터 (날짜 범위)
    start_date, end_date = date_range
    start_date = pd.Timestamp(start_date)
    end_date = pd.Timestamp(end_date) + timedelta(days=1)  # 포함 범위
    
    filtered_trades = trades_df[(trades_df['timestamp'] >= start_date) & (trades_df['timestamp'] <= end_date)]
    filtered_account = account_history[(account_history['timestamp'] >= start_date) & (account_history['timestamp'] <= end_date)]
    
    # 성과 통계 계산
    stats = calculate_performance_stats(filtered_trades)
    
    # 활성 거래 상태
    active_trade = get_active_trade_info(trades_df)
    
    # 대시보드 섹션 구성
    
    # 1. 상태 개요 섹션
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        st.markdown('<div class="stat-label">총 수익/손실</div>', unsafe_allow_html=True)
        pnl_color = "profit" if stats['total_pnl'] > 0 else "loss"
        st.markdown(f'<div class="stat-value {pnl_color}">${stats["total_pnl"]:.2f}</div>', unsafe_allow_html=True)
    
    with col2:
        st.markdown('<div class="stat-label">승률</div>', unsafe_allow_html=True)
        st.markdown(f'<div class="stat-value">{stats["win_rate"]:.2%}</div>', unsafe_allow_html=True)
    
    with col3:
        st.markdown('<div class="stat-label">총 거래 수</div>', unsafe_allow_html=True)
        st.markdown(f'<div class="stat-value">{stats["total_trades"]}</div>', unsafe_allow_html=True)
    
    with col4:
        if not filtered_account.empty:
            current_balance = filtered_account['balance'].iloc[-1]
            st.markdown('<div class="stat-label">현재 잔액</div>', unsafe_allow_html=True)
            st.markdown(f'<div class="stat-value">${current_balance:.2f}</div>', unsafe_allow_html=True)
    
    # 2. 활성 거래 정보
    st.markdown('<div class="sub-header">활성 거래 상태</div>', unsafe_allow_html=True)
    
    if active_trade is not None:
        active_cols = st.columns(4)
        
        with active_cols[0]:
            st.markdown(f'<div class="info-box">' +
                      f'<div class="stat-label">포지션</div>' +
                      f'<div class="stat-value">{active_trade["action"].upper()}</div>' +
                      f'</div>', unsafe_allow_html=True)
        
        with active_cols[1]:
            st.markdown(f'<div class="info-box">' +
                      f'<div class="stat-label">진입가격</div>' +
                      f'<div class="stat-value">${active_trade["entry_price"]:.2f}</div>' +
                      f'</div>', unsafe_allow_html=True)
        
        with active_cols[2]:
            st.markdown(f'<div class="info-box">' +
                      f'<div class="stat-label">수량</div>' +
                      f'<div class="stat-value">{active_trade["amount"]:.3f} BTC</div>' +
                      f'</div>', unsafe_allow_html=True)
        
        with active_cols[3]:
            st.markdown(f'<div class="info-box">' +
                      f'<div class="stat-label">레버리지</div>' +
                      f'<div class="stat-value">{active_trade["leverage"]}x</div>' +
                      f'</div>', unsafe_allow_html=True)
        
        active_cols2 = st.columns(4)
        
        with active_cols2[0]:
            st.markdown(f'<div class="info-box">' +
                      f'<div class="stat-label">스탑로스</div>' +
                      f'<div class="stat-value">${active_trade["stop_loss"]:.2f}</div>' +
                      f'</div>', unsafe_allow_html=True)
        
        with active_cols2[1]:
            st.markdown(f'<div class="info-box">' +
                      f'<div class="stat-label">손익실현</div>' +
                      f'<div class="stat-value">${active_trade["take_profit"]:.2f}</div>' +
                      f'</div>', unsafe_allow_html=True)
        
        with active_cols2[2]:
            st.markdown(f'<div class="info-box">' +
                      f'<div class="stat-label">켈리 비율</div>' +
                      f'<div class="stat-value">{active_trade["kelly_fraction"]:.2%}</div>' +
                      f'</div>', unsafe_allow_html=True)
        
        with active_cols2[3]:
            st.markdown(f'<div class="info-box">' +
                      f'<div class="stat-label">승리 확률</div>' +
                      f'<div class="stat-value">{active_trade["win_probability"]:.2%}</div>' +
                      f'</div>', unsafe_allow_html=True)
        
        # 개장 이후 경과 시간 계산
        if pd.notna(active_trade["timestamp"]):
            open_time = active_trade["timestamp"]
            current_time = pd.Timestamp.now()
            elapsed = current_time - open_time
            elapsed_hours = elapsed.total_seconds() / 3600
            
            st.markdown(f'<div class="info-box">' +
                      f'<div class="stat-label">개장 시간</div>' +
                      f'<div>{open_time.strftime("%Y-%m-%d %H:%M:%S")} (약 {elapsed_hours:.1f}시간 전)</div>' +
                      f'</div>', unsafe_allow_html=True)
    else:
        st.info("현재 활성화된 거래가 없습니다.")
    
    # 3. 거래 내역 그래프
    st.markdown('<div class="sub-header">거래 내역 & 수익/손실</div>', unsafe_allow_html=True)
    
    if not filtered_trades.empty and 'pnl' in filtered_trades.columns:
        # 닫힌 거래만 필터링
        closed_trades = filtered_trades[filtered_trades['status'] == 'closed']
        
        if not closed_trades.empty:
            # 날짜별 누적 PnL 계산
            closed_trades_sorted = closed_trades.sort_values('close_timestamp')
            closed_trades_sorted['cumulative_pnl'] = closed_trades_sorted['pnl'].cumsum()
            
            # PnL 시간별 변화 그래프
            fig = make_subplots(specs=[[{"secondary_y": True}]])
            
            # 개별 거래 PnL
            scatter = go.Scatter(
                x=closed_trades_sorted['close_timestamp'],
                y=closed_trades_sorted['pnl'],
                mode='markers',
                marker=dict(
                    size=10,
                    color=closed_trades_sorted['pnl'].apply(lambda x: 'green' if x > 0 else 'red'),
                    symbol=closed_trades_sorted['action'].apply(lambda x: 'triangle-up' if x == 'long' else 'triangle-down')
                ),
                name='개별 거래 PnL'
            )
            
            # 누적 PnL
            line = go.Scatter(
                x=closed_trades_sorted['close_timestamp'],
                y=closed_trades_sorted['cumulative_pnl'],
                mode='lines',
                line=dict(width=2, color='yellow'),
                name='누적 PnL',
                yaxis='y2'
            )
            
            fig.add_trace(scatter)
            fig.add_trace(line, secondary_y=True)
            
            fig.update_layout(
                title='거래 내역 및 누적 수익/손실',
                xaxis_title='날짜',
                yaxis_title='개별 거래 PnL (USDT)',
                yaxis2_title='누적 PnL (USDT)',
                height=500,
                template='plotly_dark',
                hovermode='x unified'
            )
            
            st.plotly_chart(fig, use_container_width=True)
        else:
            st.info("선택한 기간에 완료된 거래가 없습니다.")
    else:
        st.info("거래 내역이 없습니다.")
    
    # 4. 계정 잔액 변화 그래프
    st.markdown('<div class="sub-header">계정 잔액 변화</div>', unsafe_allow_html=True)
    
    if not filtered_account.empty:
        fig = go.Figure()
        
        fig.add_trace(go.Scatter(
            x=filtered_account['timestamp'],
            y=filtered_account['balance'],
            mode='lines',
            name='계정 잔액',
            line=dict(width=2, color='#00CC96')
        ))
        
        fig.update_layout(
            title='계정 잔액 변화',
            xaxis_title='날짜',
            yaxis_title='잔액 (USDT)',
            height=400,
            template='plotly_dark',
            hovermode='x unified'
        )
        
        st.plotly_chart(fig, use_container_width=True)
    else:
        st.info("계정 잔액 내역이 없습니다.")
    
    # 5. 성과 분석 섹션
    st.markdown('<div class="sub-header">성과 분석</div>', unsafe_allow_html=True)
    
    # 분석 탭
    tab1, tab2, tab3, tab4 = st.tabs(["종합 통계", "시간대별 성과", "변동성별 성과", "켈리 비율별 성과"])
    
    with tab1:
        if stats['total_trades'] > 0:
            # 승패 비율 차트
            win_loss_col, direction_col = st.columns(2)
            
            with win_loss_col:
                win_loss_data = pd.DataFrame([
                    {'Category': '수익 거래', 'Count': stats['profitable_trades']},
                    {'Category': '손실 거래', 'Count': stats['losing_trades']}
                ])
                
                fig = px.pie(
                    win_loss_data, 
                    names='Category', 
                    values='Count',
                    color='Category',
                    color_discrete_map={'수익 거래': '#00CC96', '손실 거래': '#EF553B'},
                    title='승패 비율'
                )
                fig.update_layout(template='plotly_dark')
                st.plotly_chart(fig, use_container_width=True)
            
            with direction_col:
                direction_data = pd.DataFrame([
                    {'Direction': 'LONG', 'Count': stats['total_long'], 'Win Rate': stats['long_win_rate']},
                    {'Direction': 'SHORT', 'Count': stats['total_short'], 'Win Rate': stats['short_win_rate']}
                ])
                
                fig = px.bar(
                    direction_data,
                    x='Direction',
                    y='Count',
                    color='Win Rate',
                    color_continuous_scale='RdYlGn',
                    range_color=[0, 1],
                    title='방향별 승률',
                    text=direction_data['Win Rate'].apply(lambda x: f"{x:.2%}")
                )
                fig.update_layout(template='plotly_dark')
                st.plotly_chart(fig, use_container_width=True)
            
            # 통계 카드
            stat_col1, stat_col2, stat_col3, stat_col4 = st.columns(4)
            
            with stat_col1:
                st.markdown(f'<div class="info-box">' +
                          f'<div class="stat-label">평균 수익</div>' +
                          f'<div class="stat-value profit">${stats["avg_profit"]:.2f}</div>' +
                          f'</div>', unsafe_allow_html=True)
            
            with stat_col2:
                st.markdown(f'<div class="info-box">' +
                          f'<div class="stat-label">평균 손실</div>' +
                          f'<div class="stat-value loss">${stats["avg_loss"]:.2f}</div>' +
                          f'</div>', unsafe_allow_html=True)
            
            with stat_col3:
                st.markdown(f'<div class="info-box">' +
                          f'<div class="stat-label">최대 수익</div>' +
                          f'<div class="stat-value profit">${stats["max_profit"]:.2f}</div>' +
                          f'</div>', unsafe_allow_html=True)
            
            with stat_col4:
                st.markdown(f'<div class="info-box">' +
                          f'<div class="stat-label">최대 손실</div>' +
                          f'<div class="stat-value loss">${stats["max_loss"]:.2f}</div>' +
                          f'</div>', unsafe_allow_html=True)
            
            if stats['avg_duration'] > 0:
                st.markdown(f'<div class="info-box">' +
                          f'<div class="stat-label">평균 거래 시간</div>' +
                          f'<div class="stat-value">{stats["avg_duration"]:.1f}분 ({stats["avg_duration"]/60:.1f}시간)</div>' +
                          f'</div>', unsafe_allow_html=True)
        else:
            st.info("선택한 기간에 완료된 거래가 없습니다.")
    
    with tab2:
        time_perf = analyze_time_performance(filtered_trades)
        if not time_perf.empty:
            fig = px.bar(
                time_perf, 
                x='time_range', 
                y='trade_count',
                color='win_rate',
                color_continuous_scale='RdYlGn',
                range_color=[0, 1],
                title='시간대별 거래 성과',
                text=time_perf['win_rate'].apply(lambda x: f"{x:.2%}")
            )
            fig.update_layout(template='plotly_dark', xaxis_title='시간대', yaxis_title='거래 수')
            st.plotly_chart(fig, use_container_width=True)
            
            # 시간대별 누적 PnL
            fig2 = px.bar(
                time_perf,
                x='time_range',
                y='total_pnl',
                color='total_pnl',
                color_continuous_scale='RdYlGn',
                title='시간대별 누적 수익/손실'
            )
            fig2.update_layout(template='plotly_dark', xaxis_title='시간대', yaxis_title='누적 PnL (USDT)')
            st.plotly_chart(fig2, use_container_width=True)
            
            # 데이터프레임으로 표시
            st.write("시간대별 거래 통계:")
            formatted_time_df = time_perf.copy()
            formatted_time_df['win_rate'] = formatted_time_df['win_rate'].apply(lambda x: f"{x:.2%}")
            formatted_time_df['total_pnl'] = formatted_time_df['total_pnl'].apply(lambda x: f"${x:.2f}")
            formatted_time_df['avg_pnl'] = formatted_time_df['avg_pnl'].apply(lambda x: f"${x:.2f}")
            st.dataframe(formatted_time_df)
        else:
            st.info("시간대별 성과 분석을 위한 데이터가 충분하지 않습니다.")
    
    with tab3:
        vol_perf = analyze_volatility_performance(filtered_trades)
        if not vol_perf.empty:
            fig = px.bar(
                vol_perf, 
                x='volatility_range', 
                y='trade_count',
                color='win_rate',
                color_continuous_scale='RdYlGn',
                range_color=[0, 1],
                title='변동성별 거래 성과',
                text=vol_perf['win_rate'].apply(lambda x: f"{x:.2%}")
            )
            fig.update_layout(template='plotly_dark', xaxis_title='변동성 범위', yaxis_title='거래 수')
            st.plotly_chart(fig, use_container_width=True)
            
            # 변동성별 누적 PnL
            fig2 = px.bar(
                vol_perf,
                x='volatility_range',
                y='total_pnl',
                color='total_pnl',
                color_continuous_scale='RdYlGn',
                title='변동성별 누적 수익/손실'
            )
            fig2.update_layout(template='plotly_dark', xaxis_title='변동성 범위', yaxis_title='누적 PnL (USDT)')
            st.plotly_chart(fig2, use_container_width=True)
            
            # 데이터프레임으로 표시
            st.write("변동성별 거래 통계:")
            formatted_vol_df = vol_perf.copy()
            formatted_vol_df['win_rate'] = formatted_vol_df['win_rate'].apply(lambda x: f"{x:.2%}")
            formatted_vol_df['total_pnl'] = formatted_vol_df['total_pnl'].apply(lambda x: f"${x:.2f}")
            formatted_vol_df['avg_pnl'] = formatted_vol_df['avg_pnl'].apply(lambda x: f"${x:.2f}")
            st.dataframe(formatted_vol_df)
        else:
            st.info("변동성별 성과 분석을 위한 데이터가 충분하지 않습니다.")
    
    with tab4:
        kelly_perf = analyze_kelly_performance(filtered_trades)
        if not kelly_perf.empty:
            fig = px.bar(
                kelly_perf, 
                x='kelly_range', 
                y='trade_count',
                color='win_rate',
                color_continuous_scale='RdYlGn',
                range_color=[0, 1],
                title='켈리 비율별 거래 성과',
                text=kelly_perf['win_rate'].apply(lambda x: f"{x:.2%}")
            )
            fig.update_layout(template='plotly_dark', xaxis_title='켈리 비율 범위', yaxis_title='거래 수')
            st.plotly_chart(fig, use_container_width=True)
            
            # 켈리 비율별 누적 PnL
            fig2 = px.bar(
                kelly_perf,
                x='kelly_range',
                y='total_pnl',
                color='total_pnl',
                color_continuous_scale='RdYlGn',
                title='켈리 비율별 누적 수익/손실'
            )
            fig2.update_layout(template='plotly_dark', xaxis_title='켈리 비율 범위', yaxis_title='누적 PnL (USDT)')
            st.plotly_chart(fig2, use_container_width=True)
            
            # 데이터프레임으로 표시
            st.write("켈리 비율별 거래 통계:")
            formatted_kelly_df = kelly_perf.copy()
            formatted_kelly_df['win_rate'] = formatted_kelly_df['win_rate'].apply(lambda x: f"{x:.2%}")
            formatted_kelly_df['total_pnl'] = formatted_kelly_df['total_pnl'].apply(lambda x: f"${x:.2f}")
            formatted_kelly_df['avg_pnl'] = formatted_kelly_df['avg_pnl'].apply(lambda x: f"${x:.2f}")
            st.dataframe(formatted_kelly_df)
        else:
            st.info("켈리 비율별 성과 분석을 위한 데이터가 충분하지 않습니다.")
    
    # 6. 최근 거래 내역 표
    st.markdown('<div class="sub-header">최근 거래 내역</div>', unsafe_allow_html=True)
    
    if not filtered_trades.empty:
        # 컬럼 선택 및 형식화
        display_cols = ['id', 'timestamp', 'action', 'entry_price', 'amount', 'leverage', 
                         'kelly_fraction', 'win_probability', 'status', 'close_timestamp', 
                         'close_price', 'pnl', 'pnl_percentage', 'result']
        
        display_df = filtered_trades[display_cols].copy()
        
        # 컬럼명 한글화
        column_mapping = {
            'id': '거래 ID',
            'timestamp': '개장 시간',
            'action': '포지션',
            'entry_price': '진입가',
            'amount': '수량',
            'leverage': '레버리지',
            'kelly_fraction': '켈리 비율',
            'win_probability': '승리 확률',
            'status': '상태',
            'close_timestamp': '종료 시간',
            'close_price': '종료가',
            'pnl': '수익/손실',
            'pnl_percentage': '수익률(%)',
            'result': '결과'
        }
        
        display_df.rename(columns=column_mapping, inplace=True)
        
        # 데이터 형식화
        if '진입가' in display_df.columns:
            display_df['진입가'] = display_df['진입가'].apply(lambda x: f"${x:.2f}" if pd.notna(x) else "")
        
        if '종료가' in display_df.columns:
            display_df['종료가'] = display_df['종료가'].apply(lambda x: f"${x:.2f}" if pd.notna(x) else "")
            
        if '수량' in display_df.columns:
            display_df['수량'] = display_df['수량'].apply(lambda x: f"{x:.3f}" if pd.notna(x) else "")
            
        if '켈리 비율' in display_df.columns:
            display_df['켈리 비율'] = display_df['켈리 비율'].apply(lambda x: f"{x:.2%}" if pd.notna(x) else "")
            
        if '승리 확률' in display_df.columns:
            display_df['승리 확률'] = display_df['승리 확률'].apply(lambda x: f"{x:.2%}" if pd.notna(x) else "")
            
        if '수익/손실' in display_df.columns:
            display_df['수익/손실'] = display_df['수익/손실'].apply(lambda x: f"${x:.2f}" if pd.notna(x) else "")
            
        if '수익률(%)' in display_df.columns:
            display_df['수익률(%)'] = display_df['수익률(%)'].apply(lambda x: f"{x:.2f}%" if pd.notna(x) else "")
            
        if '포지션' in display_df.columns:
            display_df['포지션'] = display_df['포지션'].apply(lambda x: x.upper() if pd.notna(x) else "")
            
        # 데이터프레임 출력 (스타일링 없이)
        st.dataframe(display_df)
    else:
        st.info("선택한 기간에 거래 내역이 없습니다.")
    
    # 자동 새로고침 설정
    if st.sidebar.button('지금 새로고침'):
        st.rerun()
    
    st.sidebar.markdown(f"마지막 새로고침: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    
    # 자동 새로고침 카운터
    if refresh_interval > 0:
        placeholder = st.sidebar.empty()
        refresh_count = refresh_interval
        
        while refresh_count > 0:
            placeholder.markdown(f"다음 새로고침까지 **{refresh_count}초** 남음")
            time.sleep(1)
            refresh_count -= 1
        
        placeholder.markdown("데이터 새로고침 중...")
        st.rerun()

if __name__ == "__main__":
    main()
