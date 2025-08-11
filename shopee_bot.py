# Versão 19 - O Ecossistema Completo (Busca por Keyword + Loja)
import requests, time, hashlib, json, random, os, sys, math
import google.generativeai as genai
from thefuzz import fuzz

# --- 1. CONFIGURAÇÕES GERAIS E SEGREDOS ---
SHOPEE_PARTNER_ID_STR = os.environ.get("SHOPEE_PARTNER_ID")
SHOPEE_API_KEY = os.environ.get("SHOPEE_API_KEY")
TELEGRAM_BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN")
TELEGRAM_CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID")
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY")
if not all([...]): sys.exit("ERRO: Segredos não carregados.")
SHOPEE_PARTNER_ID = int(SHOPEE_PARTNER_ID_STR)
SHOPEE_API_URL = "https://open-api.affiliate.shopee.com.br/graphql"
try:
    genai.configure(api_key=GEMINI_API_KEY)
    model = genai.GenerativeModel('gemini-1.5-flash-latest')
    print("IA configurada com sucesso.")
except Exception as e: sys.exit(f"ERRO AO CONFIGURAR A IA: {e}")

# --- 2. PARÂMETROS DE CURADORIA ---
HISTORICO_PRODUTOS_ARQUIVO = "historico_produtos.json"
QUANTIDADE_DE_POSTS_POR_EXECUCAO = 3
PAGINAS_A_VERIFICAR = 2
LIMIAR_DE_DESCONTO_REPOSTAGEM = 0.15
COOLDOWN_REPOSTAGEM_DIAS = 7
LIMIAR_SIMILARIDADE_DUPLICATA = 85
LOJAS_FAVORITAS_IDS = [369632653, 288420684, 286277644, 1157280425, 1315886500, 349591196, 886950101] # Adicione os IDs de suas lojas de confiança aqui

TEMPLATES_MENSAGENS = [ # Templates para novas ofertas
    ("<b>✨ OFERTA IMPERDÍVEL ✨</b>\n\n"
     "{texto_ia}\n\n"
     "<b>💰 Preço:</b> A partir de R$ {priceMin}\n"
     "<b>🏪 Loja:</b> {shopName}\n"
     "<b>⭐ Avaliação:</b> {ratingStar} estrelas\n\n"
     "<a href='{offerLink}'><b>👉 Ver Oferta Agora</b></a>"),
]

TEMPLATES_ALERTA_PRECO = [ # Templates para queda de preço
    ("🚨 **BAIXOU O PREÇO!** 🚨\n\n"
     "<b>{productName}</b>\n\n"
     "📉 De R$ {preco_antigo:.2f} por apenas <b>R$ {priceMin:.2f}</b>! Uma queda de <b>{desconto_percentual}%</b>!\n"
     "🏪 Loja: {shopName}\n\n"
     "<a href='{offerLink}'><b>🏃‍♂️ Corre pra garantir antes que o preço suba!</b></a>")
]

# --- 3. FUNÇÕES AUXILIARES COMPLETAS ---
def carregar_keywords(caminho_arquivo="keywords.txt"):
    try:
        with open(caminho_arquivo, 'r', encoding='utf-8') as f:
            keywords = [linha.strip() for linha in f if linha.strip()]
            print(f"Carregadas {len(keywords)} palavras-chave de {caminho_arquivo}.")
            return keywords
    except FileNotFoundError:
        print(f"ERRO: Arquivo '{caminho_arquivo}' não encontrado.")
        return []

PALAVRAS_CHAVE_DE_BUSCA = carregar_keywords()

def carregar_historico():
    if not os.path.exists(HISTORICO_PRODUTOS_ARQUIVO): return {}
    with open(HISTORICO_PRODUTOS_ARQUIVO, 'r', encoding='utf-8') as f:
        try: return json.load(f)
        except json.JSONDecodeError: return {}

def salvar_no_historico(produto, historico):
    item_id = str(produto.get('itemId'))
    historico[item_id] = {
        "productName": produto.get('productName'),
        "priceMin": float(produto.get('priceMin', 0)),
        "lastPostedTimestamp": int(time.time())
    }
    with open(HISTORICO_PRODUTOS_ARQUIVO, 'w', encoding='utf-8') as f:
        json.dump(historico, f, ensure_ascii=False, indent=2)

def enviar_mensagem_telegram(mensagem):
    print("Enviando mensagem para o Telegram...")
    telegram_api_url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    payload = {'chat_id': TELEGRAM_CHAT_ID, 'text': mensagem, 'parse_mode': 'HTML', 'disable_web_page_preview': False}
    try:
        response = requests.post(telegram_api_url, json=payload, timeout=10)
        response_json = response.json()
        if response_json.get("ok"):
            print("Mensagem enviada com sucesso!")
            return True
        else:
            print(f"--- ERRO TELEGRAM ---: {response_json.get('description')}")
            return False
    except requests.exceptions.RequestException as e:
        print(f"Erro de conexão com a API do Telegram: {e}")
        return False

def calcular_pontuacao(produto):
    try:
        pontuacao = 0.0
        if not produto.get('ratingStar') or float(produto.get('ratingStar', "0")) < 4.0: return 0.0
        desconto = produto.get('priceDiscountRate'); avaliacao = float(produto.get('ratingStar', "0")); vendas = produto.get('sales')
        if desconto is not None: pontuacao += float(desconto) * 1.5
        if avaliacao is not None: pontuacao += avaliacao * 1.0
        if vendas is not None and vendas > 0: pontuacao += math.log10(vendas) * 0.8
        return pontuacao
    except (ValueError, TypeError): return 0.0

def gerar_texto_com_ia(produto):
    print(f"    - Gerando texto com IA para '{produto.get('productName')}'...")
    try:
        prompt = (f"Você é um especialista em marketing para um canal de ofertas. Crie uma chamada curta e empolgante (máximo 3 frases, use emojis) para o produto: '{produto.get('productName')}'. Foque nos benefícios.")
        response = model.generate_content(prompt)
        return response.text.strip()
    except Exception as e:
        print(f"    - Erro ao gerar texto com IA: {e}")
        return f"✨ Confira esta super oferta! ✨\n\n{produto.get('productName')}"

def verificar_link_ativo(url):
    try:
        headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'}
        response = requests.get(url, headers=headers, timeout=5, allow_redirects=True)
        return response.status_code == 200 and "O produto não existe" not in response.text
    except requests.exceptions.RequestException:
        return False

def eh_duplicata_por_nome(novo_produto, historico_valores):
    for produto_antigo in historico_valores:
        if fuzz.token_sort_ratio(novo_produto.get('productName'), produto_antigo.get('productName')) > LIMIAR_SIMILARIDADE_DUPLICATA:
            print(f"    -> Duplicata por nome encontrada com '{produto_antigo.get('productName')}'")
            return True
    return False

# --- 4. FUNÇÃO DE COLETA HÍBRIDA ---
def coletar_ofertas_candidatas(palavras_chave, lojas_favoritas, paginas_a_verificar, historico_ids):
    print("\n[FASE 1] Iniciando Coleta Híbrida de Ofertas...")
    ofertas_candidatas = []
    itens_por_pagina = 15
    fontes_de_busca = [{'tipo': 'keyword', 'valor': kw} for kw in palavras_chave] + [{'tipo': 'shopId', 'valor': sid} for sid in lojas_favoritas]

    for fonte in fontes_de_busca:
        print(f"  - Buscando por {fonte['tipo']}: '{fonte['valor']}'...")
        for pagina_atual in range(1, paginas_a_verificar + 1):
            query_params = f'{fonte["tipo"]}: "{fonte["valor"]}"' if fonte["tipo"] == 'keyword' else f'{fonte["tipo"]}: {fonte["valor"]}'
            graphql_query = f"""query {{ productOfferV2({query_params}, limit: {itens_por_pagina}, page: {pagina_atual}) {{ nodes {{ itemId productName priceMin priceMax offerLink productLink shopName ratingStar sales priceDiscountRate }} }} }}"""
            timestamp = int(time.time()); body = {"query": graphql_query, "variables": {}}; payload_str = json.dumps(body, separators=(',', ':'))
            base_string = f"{SHOPEE_PARTNER_ID}{timestamp}{payload_str}{SHOPEE_API_KEY}"
            sign = hashlib.sha256(base_string.encode('utf-8')).hexdigest()
            auth_header = f"SHA256 Credential={SHOPEE_PARTNER_ID}, Timestamp={timestamp}, Signature={sign}"
            headers = {'Authorization': auth_header, 'Content-Type': 'application/json'}
            try:
                response = requests.post(SHOPEE_API_URL, data=payload_str, headers=headers)
                data = response.json()
                if "errors" in data and data["errors"]: print(f"    Erro Shopee: {data['errors']}"); break
                product_list = data.get("data", {}).get("productOfferV2", {}).get("nodes", [])
                if not product_list: break
                for produto in product_list:
                    if int(produto.get('itemId')) in historico_ids or not verificar_link_ativo(produto.get("productLink")):
                        continue
                    ofertas_candidatas.append(produto)
            except Exception as e: print(f"    Erro na requisição: {e}"); break
            time.sleep(2)

    return list({str(prod.get('itemId')): prod for prod in ofertas_candidatas}.values())

# --- 5. EXECUÇÃO PRINCIPAL ---
if __name__ == "__main__":
    print(f"\n🤖 Robô Ecossistema Iniciado (v20)")
    historico = carregar_historico()
    historico_ids = {int(item_id) for item_id in historico.keys()}
    print(f"Carregado histórico com {len(historico)} itens para vigilância.")

    candidatos = coletar_ofertas_candidatas(PALAVRAS_CHAVE_DE_BUSCA, LOJAS_FAVORITAS_IDS, PAGINAS_A_VERIFICAR, historico_ids)
    
    # FASE 2: Análise e Separação
    print("\n[FASE 2] Analisando ofertas: Novidades vs. Queda de Preço...")
    novas_ofertas_candidatas = []
    alertas_de_preco = []
    cooldown_segundos = COOLDOWN_REPOSTAGEM_DIAS * 24 * 60 * 60

    for produto in candidatos:
        item_id_str = str(produto.get('itemId'))
        if item_id_str in historico:
            preco_antigo = historico[item_id_str].get('priceMin', float('inf')); preco_novo_str = produto.get('priceMin')
            if not preco_novo_str: continue
            preco_novo = float(preco_novo_str); ultimo_post = historico[item_id_str].get('lastPostedTimestamp', 0)
            if preco_novo < (preco_antigo * (1 - LIMIAR_DE_DESCONTO_REPOSTAGEM)) and (time.time() - ultimo_post) > cooldown_segundos:
                produto['preco_antigo'] = preco_antigo; produto['desconto_percentual'] = round((1 - (preco_novo / preco_antigo)) * 100)
                alertas_de_preco.append(produto)
                print(f"  -> ALERTA DE PREÇO! '{produto['productName']}' de R${preco_antigo:.2f} por R${preco_novo:.2f}")
        else:
            if not eh_duplicata_por_nome(produto, historico.values()):
                novas_ofertas_candidatas.append(produto)

    # FASE 3: Pontuação e Ordenação
    print(f"\n[FASE 3] Pontuando e Ordenando {len(novas_ofertas_candidatas)} Novidades...")
    for produto in novas_ofertas_candidatas:
        produto['pontuacao'] = calcular_pontuacao(produto)
    novas_ofertas_ordenadas = sorted(novas_ofertas_candidatas, key=lambda p: p.get('pontuacao', 0), reverse=True)
    
    lista_final_para_postar = alertas_de_preco + novas_ofertas_ordenadas
    
    # FASE 4: Publicação
    if not lista_final_para_postar:
        print("Nenhuma oferta relevante para postar neste ciclo.")
    else:
        print(f"\n[FASE 4] Publicando as {QUANTIDADE_DE_POSTS_POR_EXECUCAO} melhores ofertas...")
        postagens_feitas = 0
        for produto in lista_final_para_postar:
            if postagens_feitas >= QUANTIDADE_DE_POSTS_POR_EXECUCAO: break
            
            if 'preco_antigo' in produto:
                template = random.choice(TEMPLATES_ALERTA_PRECO)
                produto['priceMin'] = float(produto.get('priceMin', 0))
                mensagem = template.format(**produto)
            else:
                template = random.choice(TEMPLATES_MENSAGENS)
                texto_ia = gerar_texto_com_ia(produto)
                mensagem = template.format(texto_ia=texto_ia, **produto)

            if enviar_mensagem_telegram(mensagem):
                salvar_no_historico(produto, historico)
                postagens_feitas += 1
    
    print("\n✅ Ciclo do Robô finalizado.")