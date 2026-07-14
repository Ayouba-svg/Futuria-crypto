def display_results_v2(result, price, change):
    print("\n" + "=" * 45)
    print(f"🪙  {result['coin'].upper()}")
    print(f"Prix actuel      : {price} $")
    print(f"Variation 24h    : {round(change, 2)}%")
    print(f"Score IA         : {result['score']}/100")
    print(f"Confiance        : {result['confidence']}%")
    print(f"Signal           : {result['signal']}")
    print("-" * 45)
    print("Raisons :")
    for reason in result['reasons']:
        print(f"  • {reason}")
    print("=" * 45)