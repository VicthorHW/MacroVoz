import os
import sys
import json
import traceback

# =====================================================================
# INJEÇÃO DAS DLLS DA NVIDIA (Corrigido para venv e compilação)
# =====================================================================
if getattr(sys, 'frozen', False):
    pasta_nvidia = sys._MEIPASS
else:
    # sys.prefix aponta para a raiz exata do ambiente (venv ou global)
    pasta_nvidia = os.path.join(sys.prefix, "Lib", "site-packages", "nvidia")

if os.path.exists(pasta_nvidia) and not getattr(sys, 'frozen', False):
    cudnn_bin = os.path.join(pasta_nvidia, "cudnn", "bin")
    cublas_bin = os.path.join(pasta_nvidia, "cublas", "bin")
    
    # Adiciona as pastas ao PATH do sistema
    os.environ["PATH"] = f"{cudnn_bin};{cublas_bin};" + os.environ.get("PATH", "")
    
    # Força o Python a enxergar as DLLs (Necessário no Windows)
    if hasattr(os, 'add_dll_directory'):
        try:
            if os.path.exists(cudnn_bin): os.add_dll_directory(cudnn_bin)
            if os.path.exists(cublas_bin): os.add_dll_directory(cublas_bin)
        except Exception as e:
            print(f"Aviso na injeção de DLL: {e}")

# =====================================================================
# IMPORTS GERAIS
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
import pystray
from PIL import Image, ImageDraw, ImageTk

# =====================================================================
# ORGANIZAÇÃO E ESTADO
# =====================================================================
PASTA_DADOS = "data"
PASTA_AUDIOS = os.path.join(PASTA_DADOS, "audios_recentes")
ARQUIVO_CONFIG = os.path.join(PASTA_DADOS, "config_macrovoz.json")
ARQUIVO_LOG = "crash_log.txt"

os.makedirs(PASTA_AUDIOS, exist_ok=True)

config = {
    "hotkey": "f8", 
    "modo": "toggle",
    "auto_colar": True,
    "apagar_tecla": False,
    "hardware": "auto" # auto, cuda, cpu
}

if os.path.exists(ARQUIVO_CONFIG):
    try:
        with open(ARQUIVO_CONFIG, "r") as f:
            config.update(json.load(f))
    except: pass

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

def gerar_icone():
    img = Image.new('RGB', (64, 64), color=(30, 144, 255))
    d = ImageDraw.Draw(img)
    d.text((18, 24), "MV", fill=(255, 255, 255))
    return img
icone_imagem = gerar_icone()

# =====================================================================
# LÓGICA DA IA E FALLBACK DE HARDWARE
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
        else:
            raise ValueError("Forçado para CPU")
            
    except Exception as e:
        print(f"Falha ao iniciar CUDA. Motivo: {e}")
        try:
            print("Fazendo fallback para CPU...")
            app.after(0, lambda: lbl_status.configure(text="⏳ Aviso: GPU falhou. Carregando em modo CPU...", text_color="#ffcc00"))
            model = WhisperModel("large-v3", device="cpu", compute_type="int8")
            app.after(0, lambda: lbl_hw_status.configure(text="Motor: CPU (Lento) 🐢", text_color="#ffcc00"))
            seg_hw.set("CPU")
        except Exception as e_cpu:
            erro_fatal = traceback.format_exc()
            registrar_erro(erro_fatal)
            app.after(0, lambda: lbl_status.configure(text="❌ Erro Fatal ao carregar IA. Veja o crash_log.txt", text_color="#cc0000"))
            return

    app.after(0, resetar_status)

# =====================================================================
# GRAVAÇÃO E VISUALIZADOR DE ÁUDIO
# =====================================================================
def callback_audio(indata, frames, time_info, status):
    if is_recording: 
        audio_data.append(indata.copy())
        # Cálculo simples de volume (RMS) para animar a barra
        volume = np.linalg.norm(indata) * 10 
        # Limita entre 0 e 1 para a barra de progresso
        volume_norm = min(max(volume, 0.0), 1.0)
        app.after(0, lambda: bar_volume.set(volume_norm))

def iniciar_gravacao():
    global is_recording, audio_data, stream
    if model is None: return # Impede gravar se a IA deu erro
    
    audio_data = []
    is_recording = True
    bar_volume.set(0) # Reseta visualizador
    
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
    if stream:
        stream.stop()
        stream.close()
    
    app.after(0, lambda: bar_volume.set(0)) # Zera a barra
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
                    for _ in range(qtd_backspace):
                        keyboard.send('backspace')
                        time.sleep(0.05)
                time.sleep(0.1)
                keyboard.send('ctrl+v')
            
            hora_formatada = datetime.now().strftime("%H:%M:%S")
            app.after(0, lambda: adicionar_item_historico(hora_formatada, texto, caminho_audio))
            
    except Exception as e:
        registrar_erro(traceback.format_exc())
        app.after(0, lambda: lbl_status.configure(text="❌ Erro na Transcrição! Veja o log.", text_color="#cc0000"))
        time.sleep(3) # Mostra o erro por 3s antes de resetar
        
    app.after(0, resetar_status)

def resetar_status():
    if model:
        lbl_status.configure(text=f"🟢 Pronto ({config['hotkey'].upper()})", text_color="#00C851")
    else:
        lbl_status.configure(text="❌ IA Inoperante. Reinicie.", text_color="#cc0000")

# (Aqui entra o restante do código que já tínhamos para player, tray e teclado)
# =====================================================================
# PLAYER E GERENCIAMENTO
# =====================================================================
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
            if btn.winfo_exists():
                app.after(0, lambda: btn.configure(text="▶ Áudio", fg_color=["#3B8ED0", "#1F6AA5"]))
            player_state["tocando"] = False
            
    threading.Thread(target=aguardar_fim, daemon=True).start()

def limpar_historico():
    if player_state["tocando"]:
        sd.stop()
        player_state["tocando"] = False
        player_state["btn_atual"] = None
    for widget in scroll_historico.winfo_children(): widget.destroy()
    if os.path.exists(PASTA_AUDIOS):
        for arquivo in os.listdir(PASTA_AUDIOS):
            try: os.remove(os.path.join(PASTA_AUDIOS, arquivo))
            except: pass

# =====================================================================
# CONTROLE UNIFICADO
# =====================================================================
def processar_evento(evento_tipo):
    global is_key_down, is_recording
    if evento_tipo == 'down':
        if not is_key_down:
            is_key_down = True
            if config["modo"] == "toggle":
                if not is_recording: iniciar_gravacao()
                else: parar_gravacao()
            elif config["modo"] == "hold":
                iniciar_gravacao()
    elif evento_tipo == 'up':
        is_key_down = False
        if config["modo"] == "hold" and is_recording:
            parar_gravacao()

def hook_teclado(e):
    if aguardando_tecla: return
    if e.name.lower() == config["hotkey"].lower(): processar_evento(e.event_type)

def hook_mouse(e):
    if aguardando_tecla: return
    if isinstance(e, mouse.ButtonEvent) and str(e.button).lower() == config["hotkey"].lower(): processar_evento(e.event_type)

keyboard.hook(hook_teclado)
mouse.hook(hook_mouse)

# =====================================================================
# INTERFACE GRÁFICA
# =====================================================================
ctk.set_appearance_mode("dark")
ctk.set_default_color_theme("blue")
app = ctk.CTk()
app.title("MacroVoz - IA Local")
app.geometry("800x600")

icone_tk = ImageTk.PhotoImage(icone_imagem)
app.wm_iconphoto(True, icone_tk)

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

# O Visualizador de Áudio (Mic Test)
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

# Seleção de Modo
def mudar_modo(valor):
    config["modo"] = "toggle" if valor == "Alternar" else "hold"
    salvar_config()
seg_modo = ctk.CTkSegmentedButton(frame_esq, values=["Alternar", "Segurar"], command=mudar_modo)
seg_modo.pack(pady=10)
seg_modo.set("Alternar" if config["modo"] == "toggle" else "Segurar")

# Seleção de Hardware
lbl_hw_title = ctk.CTkLabel(frame_esq, text="Aceleração de Hardware:", font=("Arial", 11))
lbl_hw_title.pack(pady=(10, 0))

def mudar_hw(valor):
    config["hardware"] = "cuda" if valor == "CUDA (GPU)" else "cpu"
    salvar_config()
    threading.Thread(target=inicializar_modelo).start() # Reinicia a IA no novo hardware

seg_hw = ctk.CTkSegmentedButton(frame_esq, values=["CUDA (GPU)", "CPU"], command=mudar_hw)
seg_hw.pack(pady=5)
seg_hw.set("CUDA (GPU)" if config.get("hardware", "auto") in ["auto", "cuda"] else "CPU")

frame_opcoes = ctk.CTkFrame(frame_esq, fg_color="transparent")
frame_opcoes.pack(pady=15, padx=20, fill="x")

def toggle_colar(): config["auto_colar"] = sw_colar.get() == 1; salvar_config()
sw_colar = ctk.CTkSwitch(frame_opcoes, text="Auto Colar", command=toggle_colar)
sw_colar.pack(pady=5, anchor="w")
if config.get("auto_colar", True): sw_colar.select()

def toggle_apagar(): config["apagar_tecla"] = sw_apagar.get() == 1; salvar_config()
sw_apagar = ctk.CTkSwitch(frame_opcoes, text="Apagar Atalho", command=toggle_apagar)
sw_apagar.pack(pady=5, anchor="w")
if config.get("apagar_tecla", False): sw_apagar.select()

def ocultar_janela():
    global app_visible
    app.withdraw(); app_visible = False

btn_ocultar = ctk.CTkButton(frame_esq, text="Esconder", fg_color="transparent", border_width=1, command=ocultar_janela)
btn_ocultar.pack(side="bottom", pady=20)

# --- CONTEÚDO DIREITO ---
frame_hist_header = ctk.CTkFrame(frame_dir, fg_color="transparent")
frame_hist_header.pack(fill="x", padx=10, pady=(15, 5))
lbl_hist = ctk.CTkLabel(frame_hist_header, text="Últimas Transcrições", font=("Arial", 18, "bold"))
lbl_hist.pack(side="left")
btn_limpar = ctk.CTkButton(frame_hist_header, text="🗑 Limpar", width=60, fg_color="#cc0000", hover_color="#990000", command=limpar_historico)
btn_limpar.pack(side="right")

scroll_historico = ctk.CTkScrollableFrame(frame_dir, fg_color="transparent")
scroll_historico.pack(fill="both", expand=True, padx=10, pady=5)

def adicionar_item_historico(hora, texto, caminho_audio):
    item_frame = ctk.CTkFrame(scroll_historico, corner_radius=8)
    item_frame.pack(fill="x", pady=5)
    lbl_texto = ctk.CTkLabel(item_frame, text=f"[{hora}] {texto}", wraplength=350, justify="left")
    lbl_texto.pack(side="left", padx=10, pady=10)
    btn_play = ctk.CTkButton(item_frame, text="▶ Áudio", width=60, height=28)
    btn_play.configure(command=lambda b=btn_play: alternar_reproducao(caminho_audio, b))
    btn_play.pack(side="right", padx=10)

def salvar_config():
    with open(ARQUIVO_CONFIG, "w") as f: json.dump(config, f)

# =====================================================================
# SYSTEM TRAY E INIT
# =====================================================================
def mostrar_janela(icon, item):
    global app_visible
    app.after(0, app.deiconify)
    app_visible = True

def fechar_tudo(icon, item):
    icon.stop()
    os._exit(0)

def setup_tray():
    menu = pystray.Menu(pystray.MenuItem('Abrir Interface', mostrar_janela), pystray.MenuItem('Sair', fechar_tudo))
    icon = pystray.Icon("MacroVoz", icone_imagem, "MacroVoz", menu)
    icon.run()

app.protocol("WM_DELETE_WINDOW", ocultar_janela)

def iniciar_sistema():
    inicializar_modelo()
    threading.Thread(target=setup_tray, daemon=True).start()

if __name__ == "__main__":
    threading.Thread(target=iniciar_sistema, daemon=True).start()
    app.mainloop()