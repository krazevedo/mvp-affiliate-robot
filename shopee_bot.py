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
LIMIAR_SIMILARIDADE_DUPLICATA = 80
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

def analisar_e_pontuar_com_ia(produtos_candidatos):
    """
    Envia uma lista de produtos para a IA em lotes menores para maior robustez.
    """
    print(f"\n[FASE 2] Iniciando Análise com IA para {len(produtos_candidatos)} candidatos...")
    if not produtos_candidatos:
        return []

    TAMANHO_DO_LOTE = 25
    analise_completa = []
    
    # Divide a lista de candidatos em lotes menores
    lotes = [produtos_candidatos[i:i + TAMANHO_DO_LOTE] for i in range(0, len(produtos_candidatos), TAMANHO_DO_LOTE)]
    
    for i, lote in enumerate(lotes):
        print(f"  - Processando lote {i+1} de {len(lotes)} (com {len(lote)} produtos)...")
        dados_para_ia = []
        for p in lote:
            dados_para_ia.append({
                "itemId": p.get('itemId'), "productName": p.get('productName'), "ratingStar": p.get('ratingStar'),
                "sales": p.get('sales'), "priceDiscountRate": p.get('priceDiscountRate')
            })

        prompt = (
            "Você é um copywriter de elite para um canal de ofertas no Telegram chamado 'Conexão Descontos'. "
            "Sua tarefa é analisar uma lista de produtos em formato JSON e, para cada um, criar 3 coisas: uma pontuação, uma justificativa, e um texto de venda.\n\n"
            "**Regras da Pontuação:**\n"
            "Para a 'pontuacao' (0 a 100), valorize uma combinação de muitas `sales` e um `ratingStar` alto. Um `priceDiscountRate` alto é um bônus importante. Produtos com `ratingStar` abaixo de 4.5 devem receber nota baixa (abaixo de 50).\n\n"
            "**Regras do Texto de Venda:**\n"
            "1. **Estrutura:** Crie um **Título Chamativo** curto em negrito com 1-2 emojis, seguido por 1-2 frases focadas em benefícios e urgência.\n"
            "2. **Conteúdo Obrigatório:** O texto DEVE mencionar o **desconto em porcentagem** (ex: 'com X% OFF!') e a **avaliação em estrelas** (ex: 'com X.X estrelas de avaliação!').\n"
            "3. **Conteúdo Proibido:** **NÃO mencione o número de vendas.**\n"
            "4. **Formato da Resposta:** Sua resposta deve ser **APENAS** um objeto JSON válido com a chave 'analise_de_produtos', contendo uma lista. Cada objeto na lista deve ter três chaves: 'itemId' (do tipo numérico), 'pontuacao' (de 0 a 100) e 'texto_de_venda' (o texto persuasivo)."
            f"\n\nAnalise os seguintes produtos: {json.dumps(dados_para_ia, ensure_ascii=False)}"
        )

        try:
            response = model.generate_content(prompt)
            texto_limpo = response.text.strip().replace("```json", "").replace("```", "")
            resultado_ia_lote = json.loads(texto_limpo)
            
            if resultado_ia_lote and 'analise_de_produtos' in resultado_ia_lote:
                print(f"    -> Lote {i+1} analisado com sucesso pela IA.")
                analise_completa.extend(resultado_ia_lote['analise_de_produtos'])
            else:
                print(f"    -> Lote {i+1} retornou uma resposta vazia ou malformada da IA.")

        except Exception as e:
            print(f"    -> ERRO CRÍTICO ao analisar o lote {i+1} com a IA: {e}")
            # Continua para o próximo lote
            continue
        
        time.sleep(5) # Pausa entre os lotes para não sobrecarregar a API

    print(f"Análise da IA finalizada. {len(analise_completa)} produtos foram analisados com sucesso.")
    return analise_completa
    
def verificar_link_ativo(url):
    try:
        headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'}
        response = requests.get(url, headers=headers, timeout=5, allow_redirects=True)
        return response.status_code == 200 and "O produto não existe" not in response.text
    except requests.exceptions.RequestException:
        return False

def eh_duplicata_por_nome(novo_produto, historico_valores):
    """
    Verifica se um produto é muito similar a algo já postado,
    limpando os nomes antes da comparação para maior precisão.
    """
    
    def limpar_nome(nome):
        """Remove palavras genéricas e formata o nome para comparação."""
        nome = nome.lower()
        palavras_a_remover = [
            'original', 'promoção', 'oferta', 'envio rápido', 'premium',
            'com fio', 'sem fio', 'para', 'com', 'de', 'a', 'o', 'e'
        ]
        for palavra in palavras_a_remover:
            nome = nome.replace(palavra, '')
        # Remove espaços extras que sobraram
        return " ".join(nome.split())

    nome_novo_limpo = limpar_nome(novo_produto.get('productName', ''))
    
    for produto_antigo in historico_valores:
        nome_antigo_limpo = limpar_nome(produto_antigo.get('productName', ''))
        
        similaridade = fuzz.token_sort_ratio(nome_novo_limpo, nome_antigo_limpo)
        
        if similaridade > LIMIAR_SIMILARIDADE_DUPLICATA:
            print(f"    -> Duplicata por nome encontrada! Similaridade de {similaridade}% entre '{novo_produto.get('productName')}' e '{produto_antigo.get('productName')}'")
            return True
    return False

# --- 4. FUNÇÃO DE COLETA HÍBRIDA ---
def coletar_ofertas_candidatas(palavras_chave, lojas_favoritas, paginas_a_verificar, historico_ids, historico_valores):
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
                    avaliacao_str = produto.get('ratingStar', "0")
                    if not avaliacao_str or float(avaliacao_str) < 4.0:
                        continue # Pula produtos com avaliação baixa

                    if int(produto.get('itemId')) in historico_ids or not verificar_link_ativo(produto.get("productLink")):
                        continue
                    
                    if eh_duplicata_por_nome(produto, historico_valores):
                        continue

                    ofertas_candidatas.append(produto)
            except Exception as e: print(f"    Erro na requisição: {e}"); break
            time.sleep(2)

    return list({str(prod.get('itemId')): prod for prod in ofertas_candidatas}.values())

# --- 5. EXECUÇÃO PRINCIPAL ---
if __name__ == "__main__":
    print(f"\n🤖 Robô Curador com IA Iniciado (v21 - IA-Native)")
    
    historico = carregar_historico()
    historico_ids = {int(item_id) for item_id in historico.keys()}
    print(f"Carregado histórico com {len(historico)} itens.")

    # FASE 1: Coleta
    candidatos = coletar_ofertas_candidatas(PALAVRAS_CHAVE_DE_BUSCA, LOJAS_FAVORITAS_IDS, PAGINAS_A_VERIFICAR, historico_ids, historico.values())
    
    # FASE 2: Análise, Pontuação e Geração de Texto pela IA
    if not candidatos:
        print("Nenhuma nova oferta encontrada para análise. Ciclo finalizado.")
    else:
        analise_ia = analisar_e_pontuar_com_ia(candidatos)
        
        if not analise_ia:
            print("A IA não retornou uma análise válida. Ciclo finalizado.")
        else:
            # Mapeia a análise da IA de volta para os produtos candidatos
            mapa_analise = {analise['itemId']: analise for analise in analise_ia}
            ofertas_finais = []
            for produto in candidatos:
                if produto['itemId'] in mapa_analise:
                    produto['pontuacao'] = mapa_analise[produto['itemId']].get('pontuacao', 0)
                    produto['texto_ia'] = mapa_analise[produto['itemId']].get('texto_de_venda', '')
                    ofertas_finais.append(produto)
            
            # Ordena pela pontuação dada pela IA
            ofertas_ordenadas = sorted(ofertas_finais, key=lambda p: p['pontuacao'], reverse=True)

            # FASE 3: Publicação
            print(f"\n[FASE 3] Publicando as {QUANTIDADE_DE_POSTS_POR_EXECUCAO} melhores ofertas analisadas pela IA...")
            for produto_final in ofertas_ordenadas[:QUANTIDADE_DE_POSTS_POR_EXECUCAO]:
                mensagem = (
                    f"{produto_final['texto_ia']}\n\n"
                    f"<b>💰 Preço:</b> A partir de R$ {produto_final.get('priceMin')}\n"
                    f"<b>🏪 Loja:</b> {produto_final.get('shopName')}\n"
                    f"<a href='{produto_final.get('offerLink')}'><b>👉 Ver Oferta e Comprar</b></a>"
                )
                if enviar_mensagem_telegram(mensagem):
                    salvar_no_historico(produto_final, historico)

    print("\n✅ Ciclo do Robô Curador com IA finalizado.")