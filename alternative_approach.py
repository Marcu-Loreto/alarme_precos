import requests
from bs4 import BeautifulSoup
import time
import random

def get_flight_prices():
    # URL alternativa - página principal da Decolar
    url = "https://www.decolar.com"
    
    # Headers mais completos para simular um navegador real
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.7",
        "Accept-Language": "pt-BR,pt;q=0.9,en-US;q=0.8,en;q=0.7",
        "Accept-Encoding": "gzip, deflate, br",
        "DNT": "1",
        "Connection": "keep-alive",
        "Upgrade-Insecure-Requests": "1",
        "Sec-Fetch-Dest": "document",
        "Sec-Fetch-Mode": "navigate",
        "Sec-Fetch-Site": "none",
        "Sec-Fetch-User": "?1",
        "sec-ch-ua": '"Not_A Brand";v="8", "Chromium";v="120", "Google Chrome";v="120"',
        "sec-ch-ua-mobile": "?0",
        "sec-ch-ua-platform": '"Windows"',
        "Cache-Control": "max-age=0"
    }
    
    # Criar uma sessão para manter cookies
    session = requests.Session()
    session.headers.update(headers)
    
    try:
        # Primeiro, acessar a página principal
        print("Acessando página principal...")
        response = session.get(url)
        print(f"Status code: {response.status_code}")
        
        if response.status_code == 200:
            print("Página principal carregada com sucesso!")
            soup = BeautifulSoup(response.text, "html.parser")
            print(f"Título: {soup.title.string if soup.title else 'Sem título'}")
            
            # Aguardar um pouco antes da próxima requisição
            time.sleep(random.uniform(3, 5))
            
            # Tentar acessar a página de passagens
            flight_url = "https://www.decolar.com/passagens-aereas"
            print("Tentando acessar página de passagens...")
            flight_response = session.get(flight_url)
            print(f"Status code da página de passagens: {flight_response.status_code}")
            
            if flight_response.status_code == 200:
                print("Página de passagens carregada!")
                return flight_response.text
            else:
                print(f"Erro ao acessar página de passagens: {flight_response.status_code}")
                return None
                
        else:
            print(f"Erro ao acessar página principal: {response.status_code}")
            print("Headers da resposta:")
            for key, value in response.headers.items():
                print(f"{key}: {value}")
            return None
            
    except Exception as e:
        print(f"Erro durante a requisição: {e}")
        return None

if __name__ == "__main__":
    content = get_flight_prices()
    if content:
        print("Conteúdo obtido com sucesso!")
        # Aqui você pode adicionar a lógica para extrair os preços
    else:
        print("Não foi possível obter o conteúdo da página.") 