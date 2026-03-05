<div align="center">
  <img src="assets/macrovoz-logo.png" alt="Logo MacroVoz" width="200">
  <br>
  
# 🎙️ MacroVoz - IA Local de Transcrição (Speech-to-Text)

[![Python Version](https://img.shields.io/badge/Python-3.8%2B-blue?logo=python&logoColor=white)](#)
[![OS](https://img.shields.io/badge/OS-Windows-0078D6?logo=windows&logoColor=white)](#)
[![Status](https://img.shields.io/badge/Status-Ativo-success)](#)
[![AI Powered](https://img.shields.io/badge/AI-Faster--Whisper-orange)](#)

Uma ferramenta de automação (Macro) inteligente que transforma sua fala em texto instantaneamente, rodando de forma **100% offline** na sua própria máquina. Ideal para conversar com IAs, preencher formulários e redigir textos de forma ágil, sem precisar digitar.

</div>

---

## 📑 Índice
- [💡 Sobre o Projeto](#-sobre-o-projeto)
- [✨ Principais Funcionalidades](#-principais-funcionalidades)
- [🚀 Como Usar (Versão Pronta - .exe)](#-como-usar-versão-pronta---exe)
- [💻 Ambiente de Desenvolvimento (Setup do Zero)](#-ambiente-de-desenvolvimento-setup-do-zero)
- [🧪 Como Testar a Aplicação](#-como-testar-a-aplicação)
- [🛠️ Como Compilar o Seu Próprio .exe](#️-como-compilar-o-seu-próprio-exe)
- [🙌 Créditos](#-créditos)

---

## 💡 Sobre o Projeto

O **MacroVoz** nasceu da necessidade de agilizar a interação diária com ferramentas de Inteligência Artificial e automatizar a digitação. Em vez de depender de sistemas online de ditado (que podem ser lentos ou comprometer a privacidade), este projeto utiliza o poderoso motor **Faster-Whisper**. 

Ele fica rodando silenciosamente em segundo plano (System Tray). Ao pressionar a tecla de atalho (ou botão do mouse) configurada, ele grava seu áudio, aciona a placa de vídeo (CUDA) para transcrição quase instantânea, e **cola o texto automaticamente** onde o seu cursor estiver piscando.

---

## ✨ Principais Funcionalidades

* **Processamento Local (Offline):** Total privacidade. Nenhum áudio seu é enviado para servidores na nuvem.
* **Múltiplos Motores de IA:** Suporte nativo para diferentes tamanhos de modelo de Inteligência Artificial, permitindo escolher entre máxima performance ou máxima precisão.
* **Auto-Colar (Auto-Paste):** Digita o texto processado instantaneamente na janela ativa.
* **Atalhos Globais:** Suporta qualquer tecla do teclado e botões extras do mouse (como Avançar/Voltar).
* **Modos de Operação:** * *Alternar (Toggle):* Clique para gravar, clique para parar.
  * *Segurar (Hold / Push-to-Talk):* Grava apenas enquanto o botão estiver pressionado.
* **Fallback de Hardware Inteligente:** Tenta usar a Placa de Vídeo (GPU) para velocidade máxima. Se o PC não for compatível, muda automaticamente para o modo Processador (CPU) sem fechar o programa.
* **Visualizador de Áudio Real-Time:** Uma barra de progresso que reage à sua voz, garantindo que o microfone está captando o áudio.
* **Sistema Anti-Crash:** Tratamento de erros embutido. Falhas geram um arquivo `crash_log.txt` detalhado em vez de fechar o aplicativo do nada.
* **Player de Histórico:** Interface gráfica moderna com log das últimas transcrições e possibilidade de reouvir o áudio original.
* **Inteligência Anti-Poluição:** Apaga automaticamente a tecla de atalho digitada sem querer antes de colar o texto.

---

## 🚀 Como Usar (Versão Pronta - .exe)

Se você não é programador ou quer apenas usar a ferramenta rapidamente, baixe a versão compilada! O projeto disponibiliza diferentes "Edições" dependendo da capacidade do seu PC (da mais leve à mais pesada).

1. Acesse a aba [Releases](../../releases) deste repositório.
2. Escolha e baixe o arquivo `.zip` da edição que preferir (Recomendamos a **Edição Pro**).
3. Extraia em uma pasta de sua preferência.
4. Dê um duplo clique no `.exe`. O ícone aparecerá perto do relógio do Windows.

| ⚙️ Requisitos para o .exe | Detalhes |
| :--- | :--- |
| **Sistema** | Windows 10 ou 11 (64-bits) |
| **Hardware** | Processador moderno (Placa de vídeo NVIDIA recomendada para velocidade máxima) |

---

## 💻 Ambiente de Desenvolvimento (Setup do Zero)

Se você deseja modificar o código, contribuir com o projeto ou apenas rodar direto pelo Python, siga este passo a passo para recriar o ambiente de desenvolvimento isolado.

### 1. Pré-requisitos
* **Python 3.8 ou superior** instalado.
* **Git** instalado.

### 2. Clonando o Repositório
Abra o seu terminal e baixe o código-fonte:
```bash
git clone https://github.com/VicthorHW/MacroVoz
cd faster-whisper-offline
```

### 3. Criando a "Sala Limpa" (Ambiente Virtual)
Para não causar conflitos com outras bibliotecas do seu PC, crie um ambiente virtual:
```bash
python -m venv venv
```

### 4. Ativando o Ambiente Virtual
Você precisa ativar o ambiente toda vez que for programar ou rodar o script.
* **No Windows (PowerShell):**
  ```powershell
  .\venv\Scripts\Activate.ps1
  ```

### 5. Instalando as Dependências
Com o ambiente ativado, instale todas as bibliotecas necessárias exatas a partir do arquivo de requisitos:
```bash
python -m pip install -r requirements.txt
```

### 6. Executando o Projeto
Pronto! Agora é só iniciar o programa:
```bash
python MacroVoz.py
```

### 7. Trocando o Modelo de IA (Opcional)
Se quiser testar modelos mais leves ou mais precisos direto no código-fonte, abra o arquivo `MacroVoz.py`, procure pela função `inicializar_modelo()` e altere o nome do modelo na seguinte linha:
```python
# Mude "small" para "tiny", "base", "medium" ou "large-v3"
model = WhisperModel("small", device="cuda", compute_type="float16")
```

---

## 🧪 Como Testar a Aplicação

Assim que a interface gráfica abrir, siga estes passos para garantir que tudo está funcionando:

1. **Teste de Hardware:** Olhe o canto superior esquerdo do "Painel de Controle". O sistema indicará `Motor: GPU (CUDA) 🚀` se a sua placa de vídeo foi reconhecida.
2. **Teste de Microfone:** Pressione o botão de atalho configurado (por padrão, `F8`). Fale no microfone e observe a barra verde de volume oscilar.
3. **Teste de Colagem:** Abra um Bloco de Notas, deixe o cursor piscando. Pressione o atalho, fale uma frase e pare a gravação. O texto deve aparecer escrito automaticamente.
4. **Teste de Log:** Verifique a aba direita "Últimas Transcrições". O seu texto deve aparecer lá. Clique em `▶ Áudio` para reouvir.

---

## 🛠️ Como Compilar o Seu Próprio .exe

O projeto inclui um construtor inteligente (`compilar.py`) que automatiza a criação de executáveis otimizados e com diferentes níveis de precisão/peso.

Com o seu `(venv)` ativado, rode:
```bash
# 1. Instale o PyInstaller no ambiente isolado (se ainda não tiver)
python -m pip install pyinstaller

# 2. Rode o script de construção
python compilar.py
```

O terminal abrirá um **Menu Interativo** perguntando qual edição você deseja compilar:
* **1) Edição LITE (`tiny`):** A mais leve e rápida. Ideal para PCs mais antigos.
* **2) Edição STANDARD (`base`):** O ponto de equilíbrio básico.
* **3) Edição PRO (`small`):** A recomendada. Excelente precisão para português e mantém um tamanho otimizado.
* **4) Edição ULTRA (`large-v3`):** Precisão absoluta, nível de estúdio, mas gera um arquivo bastante pesado.

O script cuidará de toda a "dieta" de bibliotecas para manter o `.exe` o mais limpo possível. Quando finalizar, a sua versão distribuível estará pronta dentro da pasta `dist/`.

---

## 🙌 Créditos

* **Motor de Transcrição:** Desenvolvido em cima da tecnologia open-source [Faster-Whisper](https://github.com/SYSTRAN/faster-whisper).
* **Interface Gráfica:** Construída com [CustomTkinter](https://github.com/TomSchimansky/CustomTkinter).
* 🤖 **Assistência de IA:** Todo este projeto foi arquitetado e desenvolvido com o auxílio do modelo **Gemini 3.1 Pro** da Google.

---
<div align="center">
  <p>Feito para tornar a automação por voz mais acessível e privada. 🎙️⚡</p>
</div>