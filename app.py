import streamlit as st
import requests
import json
import pandas as pd
import math
from datetime import datetime, timedelta
import plotly.graph_objects as go
import plotly.express as px

# Sayfa ayarları
st.set_page_config(
    page_title="Futbol Analiz Uygulaması",
    page_icon="⚽",
    layout="wide",
    initial_sidebar_state="expanded"
)

# CSS stilleri
st.markdown("""
<style>
    .main-header {
        font-size: 2.5rem;
        color: #1f77b4;
        text-align: center;
        margin-bottom: 2rem;
    }
    .analysis-card {
        background-color: #f0f2f6;
        padding: 1.5rem;
        border-radius: 10px;
        margin-bottom: 1rem;
        border-left: 5px solid #1f77b4;
    }
    .probability-bar {
        height: 25px;
        border-radius: 5px;
        margin: 5px 0;
    }
    .team-form {
        font-size: 1.2rem;
        font-weight: bold;
    }
    .positive { color: #28a745; }
    .negative { color: #dc3545; }
    .neutral { color: #ffc107; }
</style>
""", unsafe_allow_html=True)

class APIFootballClient:
    def __init__(self):
        self.base_url = "https://v3.football.api-sports.io"
        self.headers = {
            'x-rapidapi-host': 'v3.football.api-sports.io',
            'x-rapidapi-key': st.secrets.get("API_FOOTBALL_KEY", "")
        }
    
    def make_request(self, endpoint, params=None):
        try:
            url = f"{self.base_url}/{endpoint}"
            response = requests.get(url, headers=self.headers, params=params, timeout=10)
            return response.json() if response.status_code == 200 else None
        except:
            return None

class FootballAnalyzer:
    def __init__(self):
        self.client = APIFootballClient()
    
    def get_countries(self):
        """Ülke listesini getir"""
        data = self.client.make_request("countries")
        if data and 'response' in data:
            return {item['name']: item['code'] for item in data['response']}
        return {}
    
    def get_leagues(self, country):
        """Lig listesini getir"""
        params = {'country': country}
        data = self.client.make_request("leagues", params)
        if data and 'response' in data:
            leagues = {}
            for league in data['response']:
                league_info = league['league']
                leagues[league_info['name']] = {
                    'id': league_info['id'],
                    'season': league['seasons'][0]['year']
                }
            return leagues
        return {}
    
    def get_teams(self, league_name):
        """Takım listesini getir"""
        leagues = st.session_state.get('leagues', {})
        if league_name not in leagues:
            return {}
        
        league_id = leagues[league_name]['id']
        season = leagues[league_name]['season']
        
        params = {'league': league_id, 'season': season}
        data = self.client.make_request("teams", params)
        
        if data and 'response' in data:
            teams = {}
            for team in data['response']:
                team_info = team['team']
                teams[team_info['name']] = {
                    'id': team_info['id'],
                    'code': team_info.get('code', 'N/A')
                }
            return teams
        return {}
    
    def get_team_form(self, team_name, league_name, matches=5):
        """Takım formunu getir"""
        leagues = st.session_state.get('leagues', {})
        teams = st.session_state.get('teams', {})
        
        if team_name not in teams or league_name not in leagues:
            return []
        
        team_id = teams[team_name]['id']
        league_id = leagues[league_name]['id']
        season = leagues[league_name]['season']
        
        params = {'team': team_id, 'league': league_id, 'season': season, 'last': matches}
        data = self.client.make_request("fixtures", params)
        
        if data and 'response' in data:
            form = []
            for match in data['response']:
                home_team = match['teams']['home']['name']
                away_team = match['teams']['away']['name']
                home_goals = match['goals']['home']
                away_goals = match['goals']['away']
                
                if team_name == home_team:
                    if home_goals > away_goals: form.append('W')
                    elif home_goals == away_goals: form.append('D')
                    else: form.append('L')
                else:
                    if away_goals > home_goals: form.append('W')
                    elif away_goals == home_goals: form.append('D')
                    else: form.append('L')
            return form
        return []
    
    def get_head_to_head(self, team1, team2, matches=5):
        """Kafa kafaya geçmiş"""
        teams = st.session_state.get('teams', {})
        if team1 not in teams or team2 not in teams:
            return []
        
        team1_id = teams[team1]['id']
        team2_id = teams[team2]['id']
        
        params = {'h2h': f"{team1_id}-{team2_id}", 'last': matches}
        data = self.client.make_request("fixtures/headtohead", params)
        
        if data and 'response' in data:
            history = []
            for match in data['response']:
                history.append({
                    'date': match['fixture']['date'][:10],
                    'home_team': match['teams']['home']['name'],
                    'away_team': match['teams']['away']['name'],
                    'score': f"{match['goals']['home']}-{match['goals']['away']}"
                })
            return history
        return []
    
    def calculate_probabilities(self, home_team, away_team, home_form, away_form, history):
        """Olasılık hesapları"""
        # Form puanı hesapla
        def form_score(form):
            points = {'W': 3, 'D': 1, 'L': 0}
            return sum(points.get(result, 0) for result in form) / (len(form) * 3) if form else 0.5
        
        home_form_score = form_score(home_form)
        away_form_score = form_score(away_form)
        
        # Ev avantajı
        home_advantage = 1.15
        
        # Gol beklentileri
        home_goal_expectancy = (home_form_score * 2.0 + 0.5) * home_advantage
        away_goal_expectancy = away_form_score * 1.5 + 0.3
        
        # Olasılıklar
        home_strength = home_form_score * home_advantage
        away_strength = away_form_score
        
        total_strength = home_strength + away_strength
        home_win = (home_strength / total_strength) * 60
        draw = 25
        away_win = (away_strength / total_strength) * 40
        
        # Normalize
        total = home_win + draw + away_win
        home_win_pct = (home_win / total) * 100
        draw_pct = (draw / total) * 100
        away_win_pct = (away_win / total) * 100
        
        return {
            'probabilities': {
                'home_win': round(home_win_pct, 1),
                'draw': round(draw_pct, 1),
                'away_win': round(away_win_pct, 1)
            },
            'goal_expectancies': {
                'home': round(home_goal_expectancy, 2),
                'away': round(away_goal_expectancy, 2)
            },
            'form_scores': {
                'home': round(home_form_score * 100, 1),
                'away': round(away_form_score * 100, 1)
            }
        }

def main():
    # Başlık
    st.markdown('<div class="main-header">⚽ Profesyonel Futbol Analiz Uygulaması</div>', unsafe_allow_html=True)
    
    # Sidebar - API Key
    with st.sidebar:
        st.header("⚙️ Ayarlar")
        
        api_key = st.text_input("API Football Key", type="password", 
                               help="rapidapi.com/api-sports sitesinden alabilirsiniz")
        
        if api_key:
            st.success("✅ API Key tanımlandı")
            if 'api_client' not in st.session_state:
                st.session_state.api_client = APIFootballClient()
                st.session_state.api_client.headers['x-rapidapi-key'] = api_key
                st.session_state.analyzer = FootballAnalyzer()
        else:
            st.warning("🔑 Lütfen API key girin")
            return
    
    # Analiz bölümü
    analyzer = st.session_state.get('analyzer')
    if not analyzer:
        st.info("Lütfen sidebar'dan API key girin")
        return
    
    # Ülke, Lig, Takım seçimi
    col1, col2, col3 = st.columns(3)
    
    with col1:
        if 'countries' not in st.session_state:
            st.session_state.countries = analyzer.get_countries()
        
        countries = list(st.session_state.countries.keys())
        selected_country = st.selectbox("🌍 Ülke Seçin", countries, key="country_select")
        
        if selected_country:
            st.session_state.leagues = analyzer.get_leagues(selected_country)
    
    with col2:
        if 'leagues' in st.session_state:
            leagues = list(st.session_state.leagues.keys())
            selected_league = st.selectbox("🏆 Lig Seçin", leagues, key="league_select")
            
            if selected_league:
                st.session_state.teams = analyzer.get_teams(selected_league)
    
    with col3:
        if 'teams' in st.session_state:
            teams = list(st.session_state.teams.keys())
            
            selected_home_team = st.selectbox("🏠 Ev Takımı", teams, key="home_team_select")
            selected_away_team = st.selectbox("✈️ Deplasman Takımı", teams, key="away_team_select")
    
    # Analiz butonu
    if st.button("🎯 Maç Analizi Yap", type="primary", use_container_width=True):
        if selected_home_team and selected_away_team and selected_home_team != selected_away_team:
            with st.spinner("Veriler yükleniyor ve analiz yapılıyor..."):
                # Verileri getir
                home_form = analyzer.get_team_form(selected_home_team, selected_league)
                away_form = analyzer.get_team_form(selected_away_team, selected_league)
                h2h_history = analyzer.get_head_to_head(selected_home_team, selected_away_team)
                
                # Analiz yap
                analysis = analyzer.calculate_probabilities(
                    selected_home_team, selected_away_team, home_form, away_form, h2h_history
                )
                
                # Sonuçları göster
                display_analysis_results(selected_home_team, selected_away_team, 
                                       home_form, away_form, h2h_history, analysis)
        else:
            st.error("Lütfen farklı iki takım seçin")

def display_analysis_results(home_team, away_team, home_form, away_form, history, analysis):
    """Analiz sonuçlarını göster"""
    
    # Başlık
    st.markdown(f"## 📊 {home_team} vs {away_team} Analiz Raporu")
    
    # İki sütunlu layout
    col1, col2 = st.columns(2)
    
    with col1:
        # Form analizi
        st.subheader("📈 Form Durumu")
        
        col1a, col1b = st.columns(2)
        with col1a:
            display_team_form(home_team, home_form, analysis['form_scores']['home'])
        with col1b:
            display_team_form(away_team, away_form, analysis['form_scores']['away'])
        
        # Karşılaşma geçmişi
        if history:
            st.subheader("📜 Son Karşılaşmalar")
            history_df = pd.DataFrame(history)
            st.dataframe(history_df, use_container_width=True)
    
    with col2:
        # Olasılık grafiği
        st.subheader("🎲 Maç Sonuç Olasılıkları")
        display_probability_chart(analysis['probabilities'], home_team, away_team)
        
        # Gol beklentileri
        st.subheader("⚽ Gol Beklentileri")
        display_goal_expectancies(analysis['goal_expectancies'], home_team, away_team)
    
    # Tavsiyeler
    st.subheader("💡 Analiz Tavsiyeleri")
    display_recommendations(analysis, home_team, away_team)
    
    # Detaylı analiz
    with st.expander("🔍 Detaylı İstatistikler"):
        display_detailed_stats(analysis, home_team, away_team)

def display_team_form(team_name, form, score):
    """Takım formunu göster"""
    form_display = "".join(form) if form else "Veri yok"
    form_color = "positive" if score > 60 else "negative" if score < 40 else "neutral"
    
    st.markdown(f"""
    <div class="analysis-card">
        <div class="team-form {form_color}">{team_name}</div>
        <div>Form: <strong>{form_display}</strong></div>
        <div>Form Puanı: <strong>{score}/100</strong></div>
    </div>
    """, unsafe_allow_html=True)

def display_probability_chart(probabilities, home_team, away_team):
    """Olasılık grafiğini göster"""
    fig = go.Figure()
    
    outcomes = [f"{home_team} Galibiyeti", "Beraberlik", f"{away_team} Galibiyeti"]
    probs = [probabilities['home_win'], probabilities['draw'], probabilities['away_win']]
    colors = ['#28a745', '#ffc107', '#dc3545']
    
    fig.add_trace(go.Bar(
        x=outcomes,
        y=probs,
        marker_color=colors,
        text=[f'{p}%' for p in probs],
        textposition='auto',
    ))
    
    fig.update_layout(
        title="Maç Sonuç Olasılıkları",
        xaxis_title="Sonuçlar",
        yaxis_title="Olasılık (%)",
        showlegend=False,
        height=300
    )
    
    st.plotly_chart(fig, use_container_width=True)

def display_goal_expectancies(expectancies, home_team, away_team):
    """Gol beklentilerini göster"""
    col1, col2 = st.columns(2)
    
    with col1:
        st.metric(
            label=f"{home_team} Gol Beklentisi",
            value=expectancies['home'],
            delta=None
        )
    
    with col2:
        st.metric(
            label=f"{away_team} Gol Beklentisi",
            value=expectancies['away'],
            delta=None
        )
    
    total_goals = expectancies['home'] + expectancies['away']
    st.metric(
        label="Toplam Gol Beklentisi",
        value=f"{total_goals:.2f}",
        delta="Üst 2.5" if total_goals > 2.5 else "Alt 2.5"
    )

def display_recommendations(analysis, home_team, away_team):
    """Tavsiyeleri göster"""
    recommendations = []
    probs = analysis['probabilities']
    goals = analysis['goal_expectancies']
    
    # Sonuç tavsiyeleri
    if probs['home_win'] > 55:
        recommendations.append(f"✅ **{home_team} galibiyeti** (Yüksek güven)")
        recommendations.append("✅ **Ev takımı -0.5 handicap**")
    elif probs['away_win'] > 50:
        recommendations.append(f"✅ **{away_team} galibiyeti**")
        recommendations.append("✅ **Deplasman takımı +0.5 handicap**")
    else:
        recommendations.append("⚠️ **Beraberlik veya tek gol farkı**")
        recommendations.append("✅ **Çifte şans (1X veya X2)**")
    
    # Gol tavsiyeleri
    total_goals = goals['home'] + goals['away']
    if total_goals > 2.5:
        recommendations.append("✅ **Toplam gol üst 2.5**")
    else:
        recommendations.append("✅ **Toplam gol alt 2.5**")
    
    # İki takım gol
    if goals['home'] > 0.8 and goals['away'] > 0.8:
        recommendations.append("✅ **İki takım da gol atar (GG)**")
    else:
        recommendations.append("⚠️ **İki takım gol (GG) riskli**")
    
    # Tavsiyeleri göster
    for rec in recommendations:
        st.write(rec)

def display_detailed_stats(analysis, home_team, away_team):
    """Detaylı istatistikleri göster"""
    col1, col2, col3 = st.columns(3)
    
    with col1:
        st.metric("Ev Takımı Form Gücü", f"{analysis['form_scores']['home']}/100")
        st.metric("Ev Gol Beklentisi", analysis['goal_expectancies']['home'])
    
    with col2:
        st.metric("Deplasman Form Gücü", f"{analysis['form_scores']['away']}/100")
        st.metric("Deplasman Gol Beklentisi", analysis['goal_expectancies']['away'])
    
    with col3:
        st.metric("Toplam Gol Beklentisi", 
                 f"{analysis['goal_expectancies']['home'] + analysis['goal_expectancies']['away']:.2f}")
        st.metric("Gol Farkı", 
                 f"{analysis['goal_expectancies']['home'] - analysis['goal_expectancies']['away']:+.2f}")

if __name__ == "__main__":
    main()
