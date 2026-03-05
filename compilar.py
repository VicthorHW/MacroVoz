import os
import subprocess
import sys
import re
import shutil
from faster_whisper.utils import download_model

def menu_interativo():
    print("="*50)
    print(" 🛠️  CONSTRUTOR DO MACROVOZ - MENU DE VERSÕES")
    print("="*50)
    print("Escolha a edição que deseja compilar:\n")
    print("1) Edição LITE      (Modelo: 'tiny')    - ~75MB (IA)")
    print("2) Edição STANDARD  (Modelo: 'base')    - ~145MB (IA)")
    print("3) Edição PRO       (Modelo: 'small')   - ~480MB (IA) - Recomendado")
    print("4) Edição ULTRA     (Modelo: 'large-v3')- ~3.0GB (IA)")
    print("="*50)
    
    escolha = input("Digite o número da versão (1 a 4): ").strip()
    
    opcoes = {
        "1": {"nome_app": "MacroVoz_Lite", "modelo_ia": "tiny"},
        "2": {"nome_app": "MacroVoz_Standard", "modelo_ia": "base"},
        "3": {"nome_app": "MacroVoz_Pro", "modelo_ia": "small"},
        "4": {"nome_app": "MacroVoz_Ultra", "modelo_ia": "large-v3"}
    }
    
    if escolha not in opcoes:
        print("Opção inválida! Cancelando.")
        sys.exit(1)
        
    return opcoes[escolha]

def alterar_modelo_no_codigo(arquivo_py, novo_modelo):
    with open(arquivo_py, "r", encoding="utf-8") as f:
        codigo = f.read()
    
    # Atualiza as chamadas de WhisperModel no código fonte
    codigo_modificado = re.sub(r'WhisperModel\((["\']).*?(["\'])', f'WhisperModel("{novo_modelo}"', codigo)
    
    with open(arquivo_py, "w", encoding="utf-8") as f:
        f.write(codigo_modificado)

def construir_exe():
    config_build = menu_interativo()
    nome_app = config_build["nome_app"]
    modelo_ia = config_build["modelo_ia"]
    
    # --- PASSO NOVO: VERIFICAÇÃO / DOWNLOAD DO MODELO ---
    print(f"\n🔍 Verificando se o modelo '{modelo_ia}' está disponível...")
    try:
        # Se o modelo não existir, ele baixa agora com barra de progresso no terminal
        download_model(modelo_ia)
        print(f"✅ Modelo '{modelo_ia}' pronto para uso.")
    except Exception as e:
        print(f"❌ Erro ao baixar o modelo: {e}")
        sys.exit(1)
    # ----------------------------------------------------

    print(f"\n🚀 Iniciando compilação da versão: {nome_app}")
    
    caminho_base = sys.prefix
    pasta_site_packages = os.path.join(caminho_base, "Lib", "site-packages")
    arquivo_principal = "MacroVoz.py"
    arquivo_backup = "MacroVoz_backup.py"
    arquivo_ico = os.path.join("assets", "macrovoz-icone.ico")
    
    if sys.prefix == sys.base_prefix:
        print("\nAVISO: Você não está no ambiente virtual (venv)!")
        import time; time.sleep(3)
    
    shutil.copyfile(arquivo_principal, arquivo_backup)
    alterar_modelo_no_codigo(arquivo_principal, modelo_ia)
    
    try:
        comando = [
            "python", "-m", "PyInstaller",
            "--noconfirm",
            "--onedir",
            "--windowed",
            f"--icon={arquivo_ico}",
            f"--name={nome_app}",
            "--add-data=assets;assets",      # Inclui a pasta assets (logo e ícone)
            "--collect-data=faster_whisper", 
            "--collect-all=customtkinter",   
            
            "--exclude-module=matplotlib",
            "--exclude-module=scipy",
            "--exclude-module=pandas",
            "--exclude-module=torch",        # Dieta rigorosa
            "--exclude-module=torchaudio",
            "--exclude-module=torchvision",
            
            f"--add-data={os.path.join(pasta_site_packages, 'ctranslate2')};ctranslate2", 
            f"--add-binary={os.path.join(pasta_site_packages, 'nvidia', 'cublas', 'bin', '*.dll')};.", 
            f"--add-binary={os.path.join(pasta_site_packages, 'nvidia', 'cudnn', 'bin', '*.dll')};.", 
            
            arquivo_principal
        ]

        processo = subprocess.Popen(comando, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
        for linha in processo.stdout:
            print(linha.strip())
        processo.wait()
        
        if processo.returncode == 0:
            print(f"\n✅ Sucesso! Versão '{nome_app}' criada na pasta 'dist/'.")
        else:
            print("\n❌ Houve um erro na compilação.")
            
    finally:
        shutil.copyfile(arquivo_backup, arquivo_principal)
        os.remove(arquivo_backup)
        print("🔄 Código original do MacroVoz.py restaurado.")

if __name__ == "__main__":
    construir_exe()