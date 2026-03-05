import os
import sys
import json
import traceback
import ctypes
import socket

# =====================================================================
# TRAVA DE INSTÂNCIA ÚNICA (Evita abrir o programa duas vezes)
# =====================================================================
def verificar_instancia_unica():
    # Usamos uma porta alta aleatória que dificilmente estará em uso (ex: 65432)
    try:
        lock_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        lock_socket.bind(('127.0.0.1', 65432))
        # Mantemos o socket aberto durante toda a execução do programa
        return lock_socket
    except socket.error:
        # Se der erro, é porque a porta já está ocupada por outra instância
        import tkinter.messagebox as messagebox
        root = tk.Tk()
        root.withdraw()
        messagebox.showwarning("MacroVoz já está rodando", 
                               "O MacroVoz já está em execução.\nVerifique o ícone na bandeja do sistema.")
        os._exit(0)

# Ativa a trava logo no início
_instancia_lock = verificar_instancia_unica()

# =====================================================================
# INJEÇÃO DAS DLLS DA NVIDIA
# =====================================================================
if getattr(sys, 'frozen', False):
    pasta_nvidia = sys._MEIPASS
else:
    pasta_nvidia = os.path.join(sys.prefix, "Lib", "site-packages", "nvidia")

if os.path.exists(pasta_nvidia) and not getattr(sys, 'frozen', False):
    cudnn_bin = os.path.join(pasta_nvidia, "cudnn", "bin")
    cublas_bin = os.path.join(pasta_nvidia, "cublas", "bin")
    os.environ["PATH"] = f"{cudnn_bin};{cublas_bin};" + os.environ.get("PATH", "")
    if hasattr(os, 'add_dll_directory'):
        try:
            if os.path.exists(cudnn_bin): os.add_dll_directory(cudnn_bin)
            if os.path.exists(cublas_bin): os.add_dll_directory(cublas_bin)
        except: pass

# =====================================================================
# IMPORTS GERAIS E INTERFACE
# =====================================================================
import sounddevice as sd
import numpy as np
import soundfile as sf
import keyboard
import mouse
import pyperclip
import time
import threading
from datetime import datetime
from faster_whisper import WhisperModel
import customtkinter as ctk
import tkinter as tk
import pystray
from PIL import Image, ImageDraw, ImageTk

# =====================================================================
# TOOLTIP (DICAS FLUTUANTES)
# =====================================================================
class Tooltip:
    def __init__(self, widget, text):
        self.widget = widget
        self.text = text
        self.tw = None
        self.widget.bind("<Enter>", self.enter)
        self.widget.bind("<Leave>", self.leave)

    def enter(self, event=None):
        x = self.widget.winfo_rootx() + 20
        y = self.widget.winfo_rooty() + self.widget.winfo_height() + 5
        self.tw = tk.Toplevel(self.widget)
        self.tw.wm_overrideredirect(True)
        self.tw.wm_geometry(f"+{x}+{y}")
        # Estilo da caixinha de dica
        lbl = tk.Label(self.tw, text=self.text, justify='left',
                       background="#2b2b2b", foreground="#ffffff", 
                       relief='solid', borderwidth=1, font=("Arial", 9), padx=5, pady=3)
        lbl.pack()

    def leave(self, event=None):
        if self.tw:
            self.tw.destroy()
            self.tw = None

# =====================================================================
# ORGANIZAÇÃO E ESTADO
# =====================================================================
PASTA_DADOS = "data"
PASTA_AUDIOS = os.path.join(PASTA_DADOS, "audios_recentes")
ARQUIVO_CONFIG = os.path.join(PASTA_DADOS, "config_macrovoz.json")
ARQUIVO_HISTORICO = os.path.join(PASTA_DADOS, "historico.json")
ARQUIVO_LOG = "crash_log.txt"

os.makedirs(PASTA_AUDIOS, exist_ok=True)

config = {
    "hotkey": "f8", 
    "modo": "toggle",
    "auto_colar": True,
    "apagar_tecla": False,
    "hardware": "auto"
}

if os.path.exists(ARQUIVO_CONFIG):
    try:
        with open(ARQUIVO_CONFIG, "r") as f: config.update(json.load(f))
    except: pass

historico_db = []

is_recording = False
is_key_down = False
audio_data = []
stream = None
model = None
app_visible = True
aguardando_tecla = False
player_state = {"tocando": False, "btn_atual": None}

def registrar_erro(erro_msg):
    with open(ARQUIVO_LOG, "a") as f:
        f.write(f"\n[{datetime.now().strftime('%d/%m/%Y %H:%M:%S')}]\n{erro_msg}\n{'-'*40}")

# =====================================================================
# CARREGAMENTO DE ÍCONE FÍSICO (Com Fallback)
# =====================================================================

# --- FUNÇÃO PARA RESOLVER CAMINHOS NO EXE ---
def obter_caminho_recurso(caminho_relativo):
    """ Retorna o caminho absoluto para o recurso, funcionando para dev e PyInstaller """
    try:
        # O PyInstaller cria uma pasta temporária e armazena o caminho em _MEIPASS
        base_path = sys._MEIPASS
    except Exception:
        base_path = os.path.abspath(".")
    return os.path.join(base_path, caminho_relativo)

# --- FORÇAR ÍCONE NA BARRA DE TAREFAS (Windows) ---
try:
    # Isso informa ao Windows que este é um app único e deve usar o próprio ícone
    meu_appid = 'vitorhw.macrovoz.v1' 
    ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(meu_appid)
except:
    pass

def obter_icone():
    # Usa a nova função de caminho para encontrar o ícone nos assets
    caminho_ico = obter_caminho_recurso(os.path.join("assets", "macrovoz-icone.ico"))
    if os.path.exists(caminho_ico):
        return Image.open(caminho_ico)
    
    # Fallback de segurança
    img = Image.new('RGB', (64, 64), color=(30, 144, 255))
    return img

icone_imagem = obter_icone()

# =====================================================================
# LÓGICA DA IA
# =====================================================================
def inicializar_modelo():
    global model
    app.after(0, lambda: lbl_status.configure(text="⏳ Testando Hardware e Carregando IA...", text_color="#ffb84d"))
    alvo = config["hardware"]
    try:
        if alvo in ["auto", "cuda"]:
            print("Tentando inicializar em CUDA (Placa de Vídeo)...")
            model = WhisperModel("large-v3", device="cuda", compute_type="float16")
            app.after(0, lambda: lbl_hw_status.configure(text="Motor: GPU (CUDA) 🚀", text_color="#00C851"))
            seg_hw.set("CUDA (GPU)")
        else: raise ValueError("Forçado para CPU")
    except Exception as e:
        print(f"Fazendo fallback para CPU. Motivo: {e}")
        try:
            app.after(0, lambda: lbl_status.configure(text="⏳ Aviso: GPU falhou. Carregando em modo CPU...", text_color="#ffcc00"))
            model = WhisperModel("large-v3", device="cpu", compute_type="int8")
            app.after(0, lambda: lbl_hw_status.configure(text="Motor: CPU (Lento) 🐢", text_color="#ffcc00"))
            seg_hw.set("CPU")
        except Exception as e_cpu:
            registrar_erro(traceback.format_exc())
            app.after(0, lambda: lbl_status.configure(text="❌ Erro Fatal ao carregar IA. Veja o log.", text_color="#cc0000"))
            return
    app.after(0, resetar_status)

# =====================================================================
# GRAVAÇÃO E TRANSCRIÇÃO
# =====================================================================
def callback_audio(indata, frames, time_info, status):
    if is_recording: 
        audio_data.append(indata.copy())
        volume = np.linalg.norm(indata) * 10 
        app.after(0, lambda: bar_volume.set(min(max(volume, 0.0), 1.0)))

def iniciar_gravacao():
    global is_recording, audio_data, stream
    if model is None: return 
    audio_data = []
    is_recording = True
    bar_volume.set(0) 
    try:
        stream = sd.InputStream(samplerate=16000, channels=1, callback=callback_audio, dtype='float32')
        stream.start()
        app.after(0, lambda: lbl_status.configure(text="🔴 Gravando... Fale agora!", text_color="#ff4444"))
    except Exception as e:
        registrar_erro(traceback.format_exc())
        app.after(0, lambda: lbl_status.configure(text="❌ Erro no Microfone!", text_color="#cc0000"))
        is_recording = False

def parar_gravacao():
    global is_recording, stream
    is_recording = False
    if stream: stream.stop(); stream.close()
    app.after(0, lambda: bar_volume.set(0))
    app.after(0, lambda: lbl_status.configure(text="⚙️ Processando Áudio...", text_color="#ffb84d"))
    threading.Thread(target=processar_audio, args=(audio_data.copy(),)).start()

def processar_audio(frames_gravados):
    if not frames_gravados: 
        app.after(0, resetar_status)
        return
    try:
        audio_np = np.concatenate(frames_gravados, axis=0)
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        caminho_audio = os.path.join(PASTA_AUDIOS, f"audio_{timestamp}.wav")
        sf.write(caminho_audio, audio_np, 16000)
        
        segments, info = model.transcribe(caminho_audio, beam_size=1, language="pt")
        texto = " ".join([segment.text for segment in segments]).strip()
        
        if texto:
            pyperclip.copy(texto)
            if config.get("auto_colar", True):
                if config.get("apagar_tecla", False) and len(config["hotkey"]) == 1:
                    qtd_backspace = 2 if config["modo"] == "toggle" else 1
                    for _ in range(qtd_backspace): keyboard.send('backspace'); time.sleep(0.05)
                time.sleep(0.1)
                keyboard.send('ctrl+v')
            
            hora_formatada = datetime.now().strftime("%H:%M")
            app.after(0, lambda: adicionar_item_historico(hora_formatada, texto, caminho_audio, salvar_db=True))
            
    except Exception as e:
        registrar_erro(traceback.format_exc())
        app.after(0, lambda: lbl_status.configure(text="❌ Erro na Transcrição!", text_color="#cc0000"))
        time.sleep(3) 
    app.after(0, resetar_status)

def resetar_status():
    if model: lbl_status.configure(text=f"🟢 Pronto ({config['hotkey'].upper()})", text_color="#00C851")
    else: lbl_status.configure(text="❌ IA Inoperante. Reinicie.", text_color="#cc0000")

# =====================================================================
# GERENCIAMENTO DE HISTÓRICO E PLAYER
# =====================================================================
def salvar_db():
    with open(ARQUIVO_HISTORICO, "w", encoding="utf-8") as f:
        json.dump(historico_db, f, ensure_ascii=False, indent=4)

def carregar_db():
    global historico_db
    if os.path.exists(ARQUIVO_HISTORICO):
        try:
            with open(ARQUIVO_HISTORICO, "r", encoding="utf-8") as f:
                historico_db = json.load(f)
                for item in historico_db:
                    adicionar_item_historico(item["hora"], item["texto"], item["audio"], salvar_db=False)
        except Exception as e:
            print("Erro ao carregar histórico:", e)

def alternar_reproducao(caminho, btn):
    if player_state["tocando"]:
        sd.stop()
        player_state["tocando"] = False
        if player_state["btn_atual"] and player_state["btn_atual"].winfo_exists():
            player_state["btn_atual"].configure(text="▶ Áudio", fg_color=["#3B8ED0", "#1F6AA5"])
        if player_state["btn_atual"] == btn:
            player_state["btn_atual"] = None
            return

    if not os.path.exists(caminho): return
    data, fs = sf.read(caminho)
    sd.play(data, fs)
    player_state["tocando"] = True
    player_state["btn_atual"] = btn
    btn.configure(text="⏹ Parar", fg_color="#ff4444")
    
    def aguardar_fim():
        sd.wait()
        if player_state["tocando"] and player_state["btn_atual"] == btn:
            if btn.winfo_exists(): app.after(0, lambda: btn.configure(text="▶ Áudio", fg_color=["#3B8ED0", "#1F6AA5"]))
            player_state["tocando"] = False
    threading.Thread(target=aguardar_fim, daemon=True).start()

def limpar_historico():
    global historico_db
    if player_state["tocando"]: sd.stop(); player_state["tocando"] = False; player_state["btn_atual"] = None
    for widget in scroll_historico.winfo_children(): widget.destroy()
    
    # Limpa arquivos físicos e JSON
    historico_db = []
    salvar_db()
    if os.path.exists(PASTA_AUDIOS):
        for arquivo in os.listdir(PASTA_AUDIOS):
            try: os.remove(os.path.join(PASTA_AUDIOS, arquivo))
            except: pass

def adicionar_item_historico(hora, texto, caminho_audio, salvar_db=False):
    item_frame = ctk.CTkFrame(scroll_historico, corner_radius=8)
    item_frame.pack(fill="x", pady=5)
    
    # Textbox permite selecionar e copiar o texto livremente
    caixa_texto = ctk.CTkTextbox(item_frame, height=55, wrap="word", fg_color="transparent")
    caixa_texto.pack(side="left", fill="both", expand=True, padx=10, pady=10)
    caixa_texto.insert("0.0", f"[{hora}] {texto}")
    caixa_texto.configure(state="disabled") # Impede edição, mas permite seleção
    
    # Frame para botões à direita
    btn_frame = ctk.CTkFrame(item_frame, fg_color="transparent")
    btn_frame.pack(side="right", padx=10, pady=10)
    
    btn_copiar = ctk.CTkButton(btn_frame, text="📋 Copiar", width=60, height=24, fg_color="#4CAF50", hover_color="#388E3C",
                               command=lambda t=texto: pyperclip.copy(t))
    btn_copiar.pack(pady=(0, 5))
    
    btn_play = ctk.CTkButton(btn_frame, text="▶ Áudio", width=60, height=24)
    btn_play.configure(command=lambda b=btn_play: alternar_reproducao(caminho_audio, b))
    btn_play.pack()

    if salvar_db:
        # Insere sempre no topo da lista
        historico_db.insert(0, {"hora": hora, "texto": texto, "audio": caminho_audio})
        # Limita o histórico aos últimos 50 itens para não pesar
        if len(historico_db) > 50:
            historico_db.pop()
        salvar_db()
        
        # Reordena a interface para o novo item aparecer no topo
        item_frame.pack(before=scroll_historico.winfo_children()[0])

# =====================================================================
# CONTROLE UNIFICADO (HOOKS)
# =====================================================================
def processar_evento(evento_tipo):
    global is_key_down, is_recording
    if evento_tipo == 'down':
        if not is_key_down:
            is_key_down = True
            if config["modo"] == "toggle":
                if not is_recording: iniciar_gravacao()
                else: parar_gravacao()
            elif config["modo"] == "hold": iniciar_gravacao()
    elif evento_tipo == 'up':
        is_key_down = False
        if config["modo"] == "hold" and is_recording: parar_gravacao()

def hook_teclado(e):
    if aguardando_tecla: return
    if e.name.lower() == config["hotkey"].lower(): processar_evento(e.event_type)

def hook_mouse(e):
    if aguardando_tecla: return
    if isinstance(e, mouse.ButtonEvent) and str(e.button).lower() == config["hotkey"].lower(): processar_evento(e.event_type)

keyboard.hook(hook_teclado)
mouse.hook(hook_mouse)

# =====================================================================
# INTERFACE GRÁFICA PRINCIPAL
# =====================================================================
ctk.set_appearance_mode("dark")
ctk.set_default_color_theme("blue")
app = ctk.CTk()
app.title("MacroVoz - IA Local")
app.geometry("800x600")

# Define o ícone da janela usando o caminho resolvido
caminho_icone_janela = obter_caminho_recurso(os.path.join("assets", "macrovoz-icone.ico"))
if os.path.exists(caminho_icone_janela):
    # Dica: iconbitmap funciona melhor com caminhos absolutos no Windows
    app.iconbitmap(caminho_icone_janela)

# Define o ícone físico na janela, se existir
if os.path.exists("icone.ico"):
    app.iconbitmap("icone.ico")

frame_esq = ctk.CTkFrame(app, width=300, corner_radius=10)
frame_esq.pack(side="left", fill="y", padx=10, pady=10)
frame_esq.pack_propagate(False)

frame_dir = ctk.CTkFrame(app, corner_radius=10)
frame_dir.pack(side="right", fill="both", expand=True, padx=(0, 10), pady=10)

# --- CONTEÚDO ESQUERDO ---
lbl_titulo = ctk.CTkLabel(frame_esq, text="Painel de Controle", font=("Arial", 18, "bold"))
lbl_titulo.pack(pady=(20, 5))

lbl_hw_status = ctk.CTkLabel(frame_esq, text="Motor: Verificando...", font=("Arial", 12))
lbl_hw_status.pack(pady=0)

lbl_status = ctk.CTkLabel(frame_esq, text="⏳ Inicializando...", font=("Arial", 14, "bold"))
lbl_status.pack(pady=10)

bar_volume = ctk.CTkProgressBar(frame_esq, width=200, height=10, progress_color="#00C851")
bar_volume.pack(pady=5)
bar_volume.set(0)

def definir_atalho():
    global aguardando_tecla
    aguardando_tecla = True
    btn_hotkey.configure(text="Aguardando tecla...", fg_color="#ffb84d")
    def salvar_novo_atalho(tecla):
        global aguardando_tecla
        config["hotkey"] = str(tecla)
        salvar_config()
        aguardando_tecla = False
        app.after(0, lambda: btn_hotkey.configure(text=f"Atalho: {config['hotkey'].upper()}", fg_color=["#3a7ebf", "#1f538d"]))
        app.after(0, resetar_status)
        keyboard.unhook_all(); mouse.unhook_all()
        keyboard.hook(hook_teclado); mouse.hook(hook_mouse)
    def capturar_teclado(e):
        if aguardando_tecla and e.event_type == 'down': salvar_novo_atalho(e.name); return False
    def capturar_mouse(e):
        if aguardando_tecla and isinstance(e, mouse.ButtonEvent) and e.event_type == 'down': salvar_novo_atalho(e.button)
    keyboard.on_press(capturar_teclado, suppress=True)
    mouse.hook(capturar_mouse)

btn_hotkey = ctk.CTkButton(frame_esq, text=f"Atalho: {config['hotkey'].upper()}", command=definir_atalho)
btn_hotkey.pack(pady=(15, 5))
Tooltip(btn_hotkey, "Clique aqui e pressione a nova\ntecla ou botão do mouse que\ndeseja usar para gravar.")

def mudar_modo(valor):
    config["modo"] = "toggle" if valor == "Alternar" else "hold"
    salvar_config()
seg_modo = ctk.CTkSegmentedButton(frame_esq, values=["Alternar", "Segurar"], command=mudar_modo)
seg_modo.pack(pady=10)
seg_modo.set("Alternar" if config["modo"] == "toggle" else "Segurar")
#need to fix: Tooltip(seg_modo, "Alternar: Um clique para começar, outro para parar.\nSegurar: Grava apenas enquanto o botão estiver pressionado.")

lbl_hw_title = ctk.CTkLabel(frame_esq, text="Aceleração de Hardware:", font=("Arial", 11))
lbl_hw_title.pack(pady=(10, 0))

def mudar_hw(valor):
    config["hardware"] = "cuda" if valor == "CUDA (GPU)" else "cpu"
    salvar_config()
    threading.Thread(target=inicializar_modelo).start() 
seg_hw = ctk.CTkSegmentedButton(frame_esq, values=["CUDA (GPU)", "CPU"], command=mudar_hw)
seg_hw.pack(pady=5)
seg_hw.set("CUDA (GPU)" if config.get("hardware", "auto") in ["auto", "cuda"] else "CPU")
#need to fix: Tooltip(seg_hw, "CUDA: Usa a Placa de Vídeo (Muito rápido).\nCPU: Usa o Processador (Mais lento, modo de segurança).")

frame_opcoes = ctk.CTkFrame(frame_esq, fg_color="transparent")
frame_opcoes.pack(pady=15, padx=20, fill="x")

def toggle_colar(): config["auto_colar"] = sw_colar.get() == 1; salvar_config()
sw_colar = ctk.CTkSwitch(frame_opcoes, text="Auto Colar", command=toggle_colar)
sw_colar.pack(pady=5, anchor="w")
if config.get("auto_colar", True): sw_colar.select()
Tooltip(sw_colar, "Se ativado, cola o texto automaticamente\nonde o cursor do seu mouse estiver piscando.")

def toggle_apagar(): config["apagar_tecla"] = sw_apagar.get() == 1; salvar_config()
sw_apagar = ctk.CTkSwitch(frame_opcoes, text="Apagar Atalho", command=toggle_apagar)
sw_apagar.pack(pady=5, anchor="w")
if config.get("apagar_tecla", False): sw_apagar.select()
Tooltip(sw_apagar, "Apaga a tecla de atalho caso ela\ntenha sido digitada no seu texto sem querer.")

def ocultar_janela():
    global app_visible
    app.withdraw(); app_visible = False
btn_ocultar = ctk.CTkButton(frame_esq, text="Esconder na Bandeja", fg_color="transparent", border_width=1, command=ocultar_janela)
btn_ocultar.pack(side="bottom", pady=20)

# --- CONTEÚDO DIREITO ---
frame_hist_header = ctk.CTkFrame(frame_dir, fg_color="transparent")
frame_hist_header.pack(fill="x", padx=10, pady=(15, 5))
lbl_hist = ctk.CTkLabel(frame_hist_header, text="Últimas Transcrições", font=("Arial", 18, "bold"))
lbl_hist.pack(side="left")
btn_limpar = ctk.CTkButton(frame_hist_header, text="🗑 Limpar Histórico", width=60, fg_color="#cc0000", hover_color="#990000", command=limpar_historico)
btn_limpar.pack(side="right")

scroll_historico = ctk.CTkScrollableFrame(frame_dir, fg_color="transparent")
scroll_historico.pack(fill="both", expand=True, padx=10, pady=5)

def salvar_config():
    with open(ARQUIVO_CONFIG, "w") as f: json.dump(config, f)

# =====================================================================
# SYSTEM TRAY E INIT
# =====================================================================
tray_icon = None

def mostrar_janela(icon=None, item=None):
    global app_visible
    app.after(0, app.deiconify)
    app_visible = True

def fechar_sistema_completo(icon=None, item=None):
    """Encerra a aplicação de forma definitiva ao clicar no X ou Sair"""
    if tray_icon:
        tray_icon.stop()
    os._exit(0)

def setup_tray():
    global tray_icon
    # Menu da bandeja com a opção de fechar definitivo
    menu = pystray.Menu(
        pystray.MenuItem('Abrir Painel', mostrar_janela), 
        pystray.MenuItem('Sair do MacroVoz', fechar_sistema_completo)
    )
    tray_icon = pystray.Icon("MacroVoz", icone_imagem, "MacroVoz", menu)
    tray_icon.run()

# Configura o botão "X" da janela para encerrar o processo
app.protocol("WM_DELETE_WINDOW", fechar_sistema_completo)

def iniciar_sistema():
    carregar_db()        # Carrega o histórico de arquivos JSON
    inicializar_modelo() # Carrega o motor da IA (GPU ou CPU)
    threading.Thread(target=setup_tray, daemon=True).start()

if __name__ == "__main__":
    # Inicia a lógica de fundo e a interface principal
    threading.Thread(target=iniciar_sistema, daemon=True).start()
    app.mainloop()