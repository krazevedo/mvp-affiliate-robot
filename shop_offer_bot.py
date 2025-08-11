# Versão 2.0 - O Robô Caçador de Lojas (Baseado na Documentação Oficial)
import requests, time, hashlib, json, os, sys

# --- 1. CONFIGURAÇÕES GERAIS E SEGREDOS ---
print("--- INICIANDO VERIFICAÇÃO DE VARIÁVEIS DE AMBIENTE ---")
SHOPEE_PARTNER_ID_STR = os.environ.get("SHOPEE_PARTNER_ID")
SHOPEE_API_KEY = os.environ.get("SHOPEE_API_KEY")
TELEGRAM_BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN")
TELEGRAM_CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID")

if not all([SHOPEE_PARTNER_ID_STR, SHOPEE_API_KEY, TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID]):
    print("\nERRO CRÍTICO: Segredos não carregados.")
    sys.exit(1)

SHOPEE_PARTNER_ID = int(SHOPEE_PARTNER_ID_STR)
SHOPEE_API_URL = "https://open-api.affiliate.shopee.com.br/graphql"
print("Variáveis de ambiente carregadas com sucesso.")

# --- 2. PARÂMETROS DO CAÇADOR DE LOJAS ---
HISTORICO_OFERTAS_ARQUIVO = "historico_lojas.json" # Novo nome para o histórico
# Lembre-se de substituir pelos IDs de LOJA que você pesquisou
SHOP_IDS_PARA_MONITORAR = [84499012, 12345678] 
QUANTIDADE_DE_POSTS_POR_EXECUCAO = 2

# --- 3. FUNÇÕES AUXILIARES ---
def carregar_historico():
    if not os.path.exists(HISTORICO_OFERTAS_ARQUIVO): return set()
    with open(HISTORICO_OFERTAS_ARQUIVO, 'r', encoding='utf-8') as f:
        try: return set(json.load(f))
        except json.JSONDecodeError: return set()

def salvar_no_historico(offer_id):
    historico = carregar_historico()
    historico.add(offer_id)
    with open(HISTORICO_OFERTAS_ARQUIVO, 'w', encoding='utf-8') as f:
        json.dump(list(historico), f)

def enviar_mensagem_telegram(mensagem, foto_url=None):
    """Envia mensagem para o Telegram, com suporte opcional para foto."""
    if foto_url:
        print("Enviando post com foto para o Telegram...")
        # Usa o endpoint sendPhoto se uma URL de imagem for fornecida
        api_endpoint = "sendPhoto"
        payload = {'chat_id': TELEGRAM_CHAT_ID, 'photo': foto_url, 'caption': mensagem, 'parse_mode': 'HTML'}
    else:
        print("Enviando post de texto para o Telegram...")
        api_endpoint = "sendMessage"
        payload = {'chat_id': TELEGRAM_CHAT_ID, 'text': mensagem, 'parse_mode': 'HTML', 'disable_web_page_preview': False}
    
    telegram_api_url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/{api_endpoint}"
    
    try:
        response = requests.post(telegram_api_url, json=payload)
        response_json = response.json()
        if response_json.get("ok"):
            print("Postagem enviada com sucesso!")
            return True
        else:
            print(f"--- ERRO TELEGRAM ---: {response_json.get('description')}")
            return False
    except requests.exceptions.RequestException as e:
        print(f"Erro de conexão com a API do Telegram: {e}")
        return False

# --- 4. LÓGICA PRINCIPAL DO CAÇADOR DE LOJAS ---
def buscar_ofertas_de_loja(shop_id, historico):
    print(f"\nBuscando ofertas para o Shop ID: {shop_id}...")
    ofertas_para_postar = []
    
    # Consulta GraphQL 100% baseada na sua documentação
    graphql_query = """
    query {
        shopOfferV2(shopId: %d, limit: 5, sortType: 2) {
            nodes {
                offerId
                offerName
                shopName
                link
                commissionRate
                banners {
                    imageUrl
                }
            }
        }
    }
    """ % (shop_id)

    timestamp = int(time.time())
    body = {"query": graphql_query, "variables": {}}
    payload_str = json.dumps(body, separators=(',', ':'))
    base_string = f"{SHOPEE_PARTNER_ID}{timestamp}{payload_str}{SHOPEE_API_KEY}"
    sign = hashlib.sha256(base_string.encode('utf-8')).hexdigest()
    auth_header = f"SHA256 Credential={SHOPEE_PARTNER_ID}, Timestamp={timestamp}, Signature={sign}"
    headers = {'Authorization': auth_header, 'Content-Type': 'application/json'}

    try:
        response = requests.post(SHOPEE_API_URL, data=payload_str, headers=headers)
        data = response.json()
        if "errors" in data and data["errors"]:
            print(f"    Erro Shopee: {data['errors']}")
            return []
        
        offer_list = data.get("data", {}).get("shopOfferV2", {}).get("nodes", [])
        print(f"  - Encontradas {len(offer_list)} ofertas na loja.")

        for oferta in offer_list:
            if oferta.get('offerId') not in historico:
                ofertas_para_postar.append(oferta)
                # Adiciona ao histórico na hora para não postar duplicatas da mesma execução
                historico.add(oferta.get('offerId'))
            else:
                print(f"    - Oferta '{oferta.get('offerName')}' já está no histórico. Ignorando.")
        
    except Exception as e:
        print(f"    - Erro na requisição para a loja {shop_id}: {e}")

    return ofertas_para_postar

# --- 5. EXECUÇÃO ---
if __name__ == "__main__":
    print("🤖 Robô Caçador de Lojas Iniciado (v2.0) 🤖")
    historico_atual = carregar_historico()

    todas_as_ofertas = []
    for shop_id in SHOP_IDS_PARA_MONITORAR:
        novas_ofertas = buscar_ofertas_de_loja(shop_id, historico_atual)
        todas_as_ofertas.extend(novas_ofertas)
        time.sleep(3)
    
    if not todas_as_ofertas:
        print("\nNenhuma nova oferta de loja encontrada neste ciclo.")
    else:
        print(f"\nPublicando as melhores {QUANTIDADE_DE_POSTS_POR_EXECUCAO} ofertas de loja encontradas...")
        for oferta_final in todas_as_ofertas[:QUANTIDADE_DE_POSTS_POR_EXECUCAO]:
            loja = oferta_final.get('shopName')
            
            mensagem = (
                f"🛍️ **CAMPANHA ESPECIAL DA LOJA {loja.upper()}** 🛍️\n\n"
                f"Confira as ofertas exclusivas da campanha: \"{oferta_final.get('offerName')}\"!\n\n"
                f"Comissão de até <b>{float(oferta_final.get('commissionRate', 0)) * 100:.1f}%</b> para afiliados!\n\n"
                f"<a href='{oferta_final.get('link')}'><b>👉 Ver Todas as Ofertas da Campanha</b></a>"
            )

            banner_url = None
            if oferta_final.get('banners'):
                banner_url = oferta_final['banners'][0].get('imageUrl')

            if enviar_mensagem_telegram(mensagem, foto_url=banner_url):
                salvar_no_historico(oferta_final.get('offerId'))

    print("\n✅ Ciclo do Caçador de Lojas finalizado.")