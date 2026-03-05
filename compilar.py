import os
import subprocess
import sys
import re
import shutil

def menu_interativo():
    print("="*50)
    print(" 🛠️  CONSTRUTOR DO MACROVOZ - MENU DE VERSÕES")
    print("="*50)
    print("Escolha a edição que deseja compilar:\n")
    print("1) Edição LITE      (Modelo: 'tiny')    - Super leve, menor precisão.")
    print("2) Edição STANDARD  (Modelo: 'base')    - Equilíbrio básico.")
    print("3) Edição PRO       (Modelo: 'small')   - Excelente precisão, peso moderado. (Recomendado)")
    print("4) Edição ULTRA     (Modelo: 'large-v3')- Precisão máxima, muito pesado. (O original)")
    print("="*50)
    
    escolha = input("Digite o número da versão (1 a 4): ").strip()
    
    opcoes = {
        "1": {"nome_app": "MacroVoz_Lite", "modelo_ia": "tiny"},
        "2": {"nome_app": "MacroVoz_Standard", "modelo_ia": "base"},
        "3": {"nome_app": "MacroVoz_Pro", "modelo_ia": "small"},
        "4": {"nome_app": "MacroVoz_Ultra", "modelo_ia": "large-v3"}
    }
    
    if escolha not in opcoes:
        print("Opção inválida! Cancelando compilação.")
        sys.exit(1)
        
    return opcoes[escolha]

def alterar_modelo_no_codigo(arquivo_py, novo_modelo):
    """Lê o arquivo principal, troca o modelo da IA e salva temporariamente."""
    with open(arquivo_py, "r", encoding="utf-8") as f:
        codigo = f.read()
    
    # Procura a linha onde o modelo é definido e substitui apenas o nome do modelo
    codigo_modificado = re.sub(r'WhisperModel\((["\']).*?(["\'])', f'WhisperModel("{novo_modelo}"', codigo)
    
    with open(arquivo_py, "w", encoding="utf-8") as f:
        f.write(codigo_modificado)

def construir_exe():
    config_build = menu_interativo()
    nome_app = config_build["nome_app"]
    modelo_ia = config_build["modelo_ia"]
    
    print(f"\n🚀 Iniciando compilação da versão: {nome_app} (Modelo: {modelo_ia})")
    
    caminho_base = sys.prefix
    pasta_site_packages = os.path.join(caminho_base, "Lib", "site-packages")
    arquivo_principal = "MacroVoz.py"
    arquivo_backup = "MacroVoz_backup.py"
    
    if sys.prefix == sys.base_prefix:
        print("\nAVISO: Você não está no ambiente virtual (venv)!")
        print("Cancele (Ctrl+C) e ative o (venv) para evitar um programa gigante.\n")
        import time; time.sleep(3)
    
    # 1. Faz backup do arquivo original e altera o código para a versão escolhida
    shutil.copyfile(arquivo_principal, arquivo_backup)
    alterar_modelo_no_codigo(arquivo_principal, modelo_ia)
    
    try:
        # 2. Configura os parâmetros do PyInstaller
        comando = [
            "python", "-m", "PyInstaller",
            "--noconfirm",
            "--onedir",
            "--windowed",
            f"--name={nome_app}", # Usa o codinome escolhido
            
            "--collect-data=faster_whisper", 
            "--collect-all=customtkinter",   
            
            # DIETA RIGOROSA: Bloqueando bibliotecas gigantes
            "--exclude-module=matplotlib",
            "--exclude-module=scipy",
            "--exclude-module=pandas",
            "--exclude-module=IPython",
            "--exclude-module=jupyter",
            "--exclude-module=torch",        # O maior vilão de peso (~2GB)
            "--exclude-module=torchaudio",
            "--exclude-module=torchvision",
            "--exclude-module=tensorboard",
            
            f"--add-data={os.path.join(pasta_site_packages, 'ctranslate2')};ctranslate2", 
            f"--add-binary={os.path.join(pasta_site_packages, 'nvidia', 'cublas', 'bin', '*.dll')};.", 
            f"--add-binary={os.path.join(pasta_site_packages, 'nvidia', 'cudnn', 'bin', '*.dll')};.", 
            
            arquivo_principal
        ]

        print("\n⏳ Empacotando... Isso vai demorar alguns minutos. Pegue um café!\n")
        
        processo = subprocess.Popen(comando, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
        for linha in processo.stdout:
            print(linha.strip())
        processo.wait()
        
        if processo.returncode == 0:
            print(f"\n✅ Sucesso! Versão '{nome_app}' criada na pasta 'dist/'.")
        else:
            print("\n❌ Houve um erro na compilação.")
            
    finally:
        # 3. Restaura o arquivo original independentemente de erro ou sucesso
        shutil.copyfile(arquivo_backup, arquivo_principal)
        os.remove(arquivo_backup)
        print("🔄 Código original do MacroVoz.py restaurado com segurança.")

if __name__ == "__main__":
    construir_exe()