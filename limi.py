from selenium import webdriver
from selenium.webdriver.firefox.service import Service
from selenium.webdriver.common.by import By
from selenium.common.exceptions import NoSuchElementException, WebDriverException
from selenium.webdriver.firefox.options import Options as FirefoxOptions
import time
from flask import Flask, jsonify, request
import threading
from collections import defaultdict
from decimal import Decimal, InvalidOperation
import os

# O caminho para o geckodriver não é mais necessário, pois será instalado pelo build.sh.
# driver_path = r'C:\Users\Usuario\Desktop\mr_robot\geckodriver.exe'  

# A variável 'meses' não estava sendo utilizada.
# meses = ['2025-07', '2025-06', '2025-05'] 

# O Service não precisa mais ser definido globalmente.

email = os.environ.get("ROBO_EMAIL", "")
senha = os.environ.get("ROBO_SENHA", "")
url_login = "https://lemitti.com/auth/login"  
url_extrato = "https://lemitti.com/report/tickets/2025-07"  

# Token de autenticação simples
TOKEN = "meu_token_secreto"

# Variável global para armazenar o último valor lido
global_total = None

def fazer_login(driver):
    print("Acessando página de login...")
    driver.get(url_login)
    time.sleep(2)
    print("Preenchendo e-mail...")
    campo_email = driver.find_element(By.ID, "email")
    campo_email.clear()
    campo_email.send_keys(email)
    print("Preenchendo senha...")
    campo_senha = driver.find_element(By.ID, "password")
    campo_senha.clear()
    campo_senha.send_keys(senha)
    print("Clicando no botão de login...")
    botao_login = driver.find_element(By.XPATH, "//button[@type='submit']")
    botao_login.click()
    time.sleep(2)

def monitorar_total():
    global global_total
    while True:
        driver = None
        try:
            print("Configurando opções do Firefox para modo headless...")
            options = FirefoxOptions()
            options.add_argument("--headless")
            options.add_argument("--disable-gpu")
            options.add_argument("--no-sandbox") # Essencial para rodar como root em containers
            options.add_argument("--window-size=1920,1080")
            
            print("Iniciando navegador Firefox em modo headless...")
            # O Selenium vai procurar o geckodriver no PATH do sistema.
            driver = webdriver.Firefox(options=options)
            
            fazer_login(driver)
            print("Acessando extrato...")
            driver.get(url_extrato)
            time.sleep(2)
            while True:
                try:
                    tbody = driver.find_element(By.CSS_SELECTOR, "table tbody")
                    rows = tbody.find_elements(By.TAG_NAME, "tr")
                    campos = [
                        "qtd",                # Qtd.
                        "cpfs_enriquecidos", # CPF's enriquecidos
                        "cpfs_faturados",    # CPF's faturados
                        "sub_total_a",       # Sub-total A
                        "descontos_b",       # Descontos B
                        "total_a_b"          # Total A + B
                    ]
                    ultimos_7 = []
                    linhas_por_dia = defaultdict(list)
                    for row in rows:
                        ths = row.find_elements(By.TAG_NAME, "th")
                        tds = row.find_elements(By.TAG_NAME, "td")
                        values = [td.text for td in tds]
                        data = ths[0].text if len(ths) > 0 else ""
                        print(f"Linha capturada: {[th.text for th in ths]} + {values}")
                        if len(values) >= 3 and data:
                            valor_final = values[-1]
                            filtrado = {
                                "data": data,
                                "cpfs_faturados": values[1] if len(values) > 1 else "",
                                "cpfs_enriquecidos": values[0] if len(values) > 0 else "",
                                "valor": valor_final
                            }
                            linhas_por_dia[data].append(filtrado)

                    # Agora, para cada data, soma os valores dos campos
                    dias = []
                    for data in linhas_por_dia:
                        total_cpfs_faturados = 0
                        total_cpfs_enriquecidos = 0
                        total_valor = Decimal("0.00")
                        for item in linhas_por_dia[data]:
                            try:
                                total_cpfs_faturados += int(item["cpfs_faturados"]) if item["cpfs_faturados"] else 0
                            except ValueError:
                                pass
                            try:
                                total_cpfs_enriquecidos += int(item["cpfs_enriquecidos"]) if item["cpfs_enriquecidos"] else 0
                            except ValueError:
                                pass
                            try:
                                valor = Decimal(item["valor"].replace("R$", "").replace(",", ".")) if item["valor"] else Decimal("0.00")
                                total_valor += valor
                            except InvalidOperation:
                                pass
                        dias.append({
                            "data": data,
                            "cpfs_faturados": total_cpfs_faturados,
                            "cpfs_enriquecidos": total_cpfs_enriquecidos,
                            "valor": f'R${total_valor:.2f}'.replace('.', ',')
                        })
                    # Ordena por data (assumindo formato dd/mm/yyyy ou dd/mm/aaaa)
                    def parse_data(d):
                        try:
                            return tuple(map(int, d.split("/")[::-1]))
                        except Exception:
                            return (0, 0, 0)
                    dias_ordenados = sorted(dias, key=lambda x: parse_data(x["data"]))
                    global_total = dias_ordenados[-7:]  # últimos 7 dias, do mais antigo para o mais recente
                    print(f"Últimos 7 dias filtrados: {global_total}")
                    time.sleep(10)
                except NoSuchElementException:
                    print("Linhas de dias não encontradas, tentando novamente...")
                    time.sleep(5)
                except WebDriverException as wde:
                    print(f"WebDriverException detectada, reiniciando... {wde}")
                    break
        except Exception as e:
            print(f"Erro detectado: {e}. Reiniciando processo...")
        finally:
            if driver is not None:
                try:
                    driver.quit()
                except Exception as e:
                    print(f"Erro ao fechar o driver: {e}")
            time.sleep(5)

# Flask app para expor o endpoint
app = Flask(__name__)

@app.route('/total', methods=['GET'])
def get_total():
    if request.args.get("token") != TOKEN:
        return jsonify({"error": "Unauthorized"}), 401
    if global_total is not None:
        return jsonify(global_total)
    else:
        return jsonify({"error": "Nenhum valor lido ainda"}), 404

if __name__ == '__main__':
    try:
        t = threading.Thread(target=monitorar_total, daemon=True)
        t.start()
        app.run(host='0.0.0.0', port=5000)
    except Exception as e:
        print(f"Erro fatal: {e}")
        import traceback
        traceback.print_exc()
        input("Pressione Enter para sair...")
