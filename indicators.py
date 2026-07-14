import ta

def calculate_indicators(df):
    """Calcule tous les indicateurs sur le DataFrame"""
    df['rsi'] = ta.momentum.RSIIndicator(df['close'], window=14).rsi()

    macd = ta.trend.MACD(df['close'])
    df['macd'] = macd.macd()
    df['macd_signal'] = macd.macd_signal()

    df['sma20'] = df['close'].rolling(window=20).mean()
    df['sma50'] = df['close'].rolling(window=50).mean()

    bb = ta.volatility.BollingerBands(df['close'], window=20, window_dev=2)
    df['bb_high'] = bb.bollinger_hband()
    df['bb_low'] = bb.bollinger_lband()

    df['volume_sma'] = df['volume'].rolling(window=20).mean()

    # Volatilité récente en % : écart-type des variations journalières du
    # prix sur une fenêtre de 14 jours, exprimé en %. Plus la valeur est
    # haute, plus la crypto bouge fort récemment (utile pour ajuster la
    # taille de position ou le stop-loss selon le risque réel du marché).
    df['volatilite_pct'] = df['close'].pct_change().rolling(window=14).std() * 100

    return df
