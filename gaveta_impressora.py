import tkinter as tk
from tkinter import ttk, messagebox, scrolledtext
import serial
import serial.tools.list_ports
import threading
import time
import socket

GAVETA_CMD_1 = bytes([0x1B, 0x70, 0x00, 0x19, 0x19])
GAVETA_CMD_2 = bytes([0x1B, 0x70, 0x01, 0x19, 0x19])
GAVETA_CMD_3 = bytes([0x10, 0x14, 0x01, 0x00, 0x05])
INIT_CMD     = bytes([0x1B, 0x40])


class GavetaApp(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("Controle de Gaveta — Impressora ESC/POS")
        self.geometry("600x660")
        self.resizable(False, False)
        self.configure(bg="#1a1a2e")

        self.conn       = None
        self.conn_mode  = "none"   # "serial" | "usb" | "tcp"
        self.connection_type = tk.StringVar(value="serial")
        self.port_var   = tk.StringVar()
        self.baud_var   = tk.StringVar(value="9600")
        self.ip_var     = tk.StringVar(value="192.168.0.100")
        self.tcp_port_var = tk.StringVar(value="9100")
        self.cmd_var    = tk.StringVar(value="cmd1")

        self._build_ui()
        self._refresh_ports()

    # ─── ENVIO UNIFICADO ───────────────────────
    def _send(self, data):
        if self.conn_mode == "tcp":
            self.conn.send(data)
        else:
            self.conn.write(data)
            if hasattr(self.conn, "flush"):
                self.conn.flush()

    # ─── UI ────────────────────────────────────
    def _build_ui(self):
        header = tk.Frame(self, bg="#16213e", pady=14)
        header.pack(fill="x")
        tk.Label(header, text="🖨️  Controle de Gaveta", font=("Courier New", 18, "bold"),
                 bg="#16213e", fg="#e94560").pack()
        tk.Label(header, text="Impressora ESC/POS  •  Abertura de Gaveta",
                 font=("Courier New", 9), bg="#16213e", fg="#a8a8b3").pack()

        frm_tipo = tk.LabelFrame(self, text=" Tipo de Conexão ", font=("Courier New", 10, "bold"),
                                  bg="#1a1a2e", fg="#e94560", padx=12, pady=10)
        frm_tipo.pack(fill="x", padx=18, pady=(14, 4))

        tk.Radiobutton(frm_tipo, text="USB / Serial (COM)", variable=self.connection_type,
                       value="serial", command=self._toggle_conn,
                       bg="#1a1a2e", fg="#ffffff", selectcolor="#0f3460",
                       activebackground="#1a1a2e", font=("Courier New", 10)).grid(row=0, column=0, sticky="w")
        tk.Radiobutton(frm_tipo, text="Rede TCP/IP (LAN)", variable=self.connection_type,
                       value="tcp", command=self._toggle_conn,
                       bg="#1a1a2e", fg="#ffffff", selectcolor="#0f3460",
                       activebackground="#1a1a2e", font=("Courier New", 10)).grid(row=0, column=1, sticky="w", padx=30)

        self.frm_serial = tk.Frame(frm_tipo, bg="#1a1a2e")
        self.frm_serial.grid(row=1, column=0, columnspan=2, sticky="ew", pady=(8, 0))

        tk.Label(self.frm_serial, text="Porta:", bg="#1a1a2e", fg="#a8a8b3",
                 font=("Courier New", 10)).grid(row=0, column=0, sticky="w")
        self.port_combo = ttk.Combobox(self.frm_serial, textvariable=self.port_var,
                                        width=18, font=("Courier New", 10))
        self.port_combo.grid(row=0, column=1, padx=6)

        tk.Button(self.frm_serial, text="↺", command=self._refresh_ports,
                  bg="#0f3460", fg="#e94560", font=("Courier New", 11, "bold"),
                  relief="flat", cursor="hand2", padx=6).grid(row=0, column=2)

        tk.Label(self.frm_serial, text="Baud Rate:", bg="#1a1a2e", fg="#a8a8b3",
                 font=("Courier New", 10)).grid(row=0, column=3, padx=(12, 4), sticky="w")
        ttk.Combobox(self.frm_serial, textvariable=self.baud_var,
                     values=["9600", "19200", "38400", "57600", "115200"],
                     width=8, font=("Courier New", 10)).grid(row=0, column=4)

        self.frm_tcp = tk.Frame(frm_tipo, bg="#1a1a2e")

        tk.Label(self.frm_tcp, text="IP:", bg="#1a1a2e", fg="#a8a8b3",
                 font=("Courier New", 10)).grid(row=0, column=0, sticky="w")
        tk.Entry(self.frm_tcp, textvariable=self.ip_var, width=16,
                 bg="#0f3460", fg="#ffffff", insertbackground="white",
                 font=("Courier New", 10), relief="flat").grid(row=0, column=1, padx=6)
        tk.Label(self.frm_tcp, text="Porta TCP:", bg="#1a1a2e", fg="#a8a8b3",
                 font=("Courier New", 10)).grid(row=0, column=2, padx=(10, 4), sticky="w")
        tk.Entry(self.frm_tcp, textvariable=self.tcp_port_var, width=6,
                 bg="#0f3460", fg="#ffffff", insertbackground="white",
                 font=("Courier New", 10), relief="flat").grid(row=0, column=3)

        frm_btn_conn = tk.Frame(self, bg="#1a1a2e")
        frm_btn_conn.pack(pady=8)
        self.btn_conectar = tk.Button(frm_btn_conn, text="⚡  CONECTAR",
                                       command=self._conectar,
                                       bg="#e94560", fg="#ffffff",
                                       font=("Courier New", 12, "bold"),
                                       relief="flat", padx=24, pady=8, cursor="hand2")
        self.btn_conectar.pack(side="left", padx=6)
        self.btn_desconectar = tk.Button(frm_btn_conn, text="✖  DESCONECTAR",
                                          command=self._desconectar,
                                          bg="#555", fg="#ccc",
                                          font=("Courier New", 12, "bold"),
                                          relief="flat", padx=24, pady=8, cursor="hand2",
                                          state="disabled")
        self.btn_desconectar.pack(side="left", padx=6)

        self.lbl_status = tk.Label(self, text="● Desconectado", font=("Courier New", 10, "bold"),
                                    bg="#1a1a2e", fg="#e94560")
        self.lbl_status.pack(pady=2)

        frm_cmd = tk.LabelFrame(self, text=" Comando ESC/POS para Gaveta ",
                                  font=("Courier New", 10, "bold"),
                                  bg="#1a1a2e", fg="#e94560", padx=12, pady=10)
        frm_cmd.pack(fill="x", padx=18, pady=6)

        for val, texto in [
            ("cmd1", "ESC p 0 25 25  (Gaveta pino 2 — padrão Epson)"),
            ("cmd2", "ESC p 1 25 25  (Gaveta pino 5)"),
            ("cmd3", "DLE EOT 1      (Alternativo Epson/Bematech)"),
        ]:
            tk.Radiobutton(frm_cmd, text=texto, variable=self.cmd_var, value=val,
                           bg="#1a1a2e", fg="#ffffff", selectcolor="#0f3460",
                           activebackground="#1a1a2e",
                           font=("Courier New", 9)).pack(anchor="w")

        self.btn_abrir = tk.Button(self, text="🔓  ABRIR GAVETA",
                                    command=self._abrir_gaveta,
                                    bg="#00b4d8", fg="#000000",
                                    font=("Courier New", 15, "bold"),
                                    relief="flat", pady=14, cursor="hand2",
                                    state="disabled")
        self.btn_abrir.pack(fill="x", padx=18, pady=10)

        self.btn_teste = tk.Button(self, text="🖨️  IMPRIMIR TESTE",
                                    command=self._imprimir_teste,
                                    bg="#0f3460", fg="#ffffff",
                                    font=("Courier New", 11, "bold"),
                                    relief="flat", pady=8, cursor="hand2",
                                    state="disabled")
        self.btn_teste.pack(fill="x", padx=18, pady=(0, 8))

        frm_log = tk.LabelFrame(self, text=" Log ", font=("Courier New", 10, "bold"),
                                  bg="#1a1a2e", fg="#e94560", padx=8, pady=6)
        frm_log.pack(fill="both", expand=True, padx=18, pady=(0, 14))

        self.log_box = scrolledtext.ScrolledText(frm_log, height=8, font=("Courier New", 9),
                                                  bg="#0d0d1a", fg="#00ff88",
                                                  insertbackground="white", relief="flat",
                                                  state="disabled")
        self.log_box.pack(fill="both", expand=True)

        tk.Button(frm_log, text="Limpar log", command=self._limpar_log,
                  bg="#222", fg="#888", font=("Courier New", 8),
                  relief="flat", cursor="hand2").pack(anchor="e", pady=(4, 0))

    # ─── HELPERS ───────────────────────────────
    def _toggle_conn(self):
        if self.connection_type.get() == "serial":
            self.frm_tcp.grid_remove()
            self.frm_serial.grid(row=1, column=0, columnspan=2, sticky="ew", pady=(8, 0))
        else:
            self.frm_serial.grid_remove()
            self.frm_tcp.grid(row=1, column=0, columnspan=2, sticky="ew", pady=(8, 0))

    def _refresh_ports(self):
        ports = [p.device for p in serial.tools.list_ports.comports()]
        # Adiciona portas USB de impressora comuns no Linux
        import glob
        ports += glob.glob("/dev/usb/lp*") + glob.glob("/dev/ttyUSB*")
        ports = sorted(set(ports))
        self.port_combo["values"] = ports
        if ports:
            # Prefere USB printer
            usb = [p for p in ports if "usb" in p.lower() or "USB" in p]
            self.port_var.set(usb[0] if usb else ports[0])
        self._log("Portas detectadas: " + (", ".join(ports) if ports else "nenhuma"))

    def _log(self, msg):
        self.log_box.configure(state="normal")
        ts = time.strftime("%H:%M:%S")
        self.log_box.insert("end", f"[{ts}]  {msg}\n")
        self.log_box.see("end")
        self.log_box.configure(state="disabled")

    def _limpar_log(self):
        self.log_box.configure(state="normal")
        self.log_box.delete("1.0", "end")
        self.log_box.configure(state="disabled")

    def _set_conectado(self, ok):
        if ok:
            self.lbl_status.config(text="● Conectado", fg="#00ff88")
            self.btn_conectar.config(state="disabled")
            self.btn_desconectar.config(state="normal", bg="#e94560", fg="#fff")
            self.btn_abrir.config(state="normal")
            self.btn_teste.config(state="normal")
        else:
            self.lbl_status.config(text="● Desconectado", fg="#e94560")
            self.btn_conectar.config(state="normal")
            self.btn_desconectar.config(state="disabled", bg="#555", fg="#ccc")
            self.btn_abrir.config(state="disabled")
            self.btn_teste.config(state="disabled")

    # ─── CONEXÃO ───────────────────────────────
    def _conectar(self):
        threading.Thread(target=self._conectar_thread, daemon=True).start()

    def _conectar_thread(self):
        try:
            if self.connection_type.get() == "serial":
                port = self.port_var.get().strip()
                if not port:
                    self._log("❌ Selecione uma porta.")
                    return

                if "usb/lp" in port or port.startswith("/dev/usb"):
                    # Impressora USB direta — não é serial, abre como arquivo
                    self.conn = open(port, "wb")
                    self.conn_mode = "usb"
                    self._send(INIT_CMD)
                    self._log(f"✅ Conectado via USB direto: {port}")
                else:
                    baud = int(self.baud_var.get())
                    self.conn = serial.Serial(port, baud, timeout=2)
                    self.conn_mode = "serial"
                    self._send(INIT_CMD)
                    self._log(f"✅ Conectado via Serial: {port} @ {baud} baud")
            else:
                ip = self.ip_var.get().strip()
                tcp_port = int(self.tcp_port_var.get())
                self.conn = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                self.conn.settimeout(5)
                self.conn.connect((ip, tcp_port))
                self.conn_mode = "tcp"
                self._send(INIT_CMD)
                self._log(f"✅ Conectado via TCP: {ip}:{tcp_port}")

            self.after(0, lambda: self._set_conectado(True))

        except PermissionError:
            port = self.port_var.get().strip()
            self._log(f"❌ Sem permissão! Rode: sudo chmod 666 {port}")
            self.conn = None
            self.after(0, lambda: self._set_conectado(False))
        except Exception as e:
            self._log(f"❌ Erro na conexão: {e}")
            self.conn = None
            self.after(0, lambda: self._set_conectado(False))

    def _desconectar(self):
        try:
            if self.conn:
                self.conn.close()
                self.conn = None
                self.conn_mode = "none"
            self._log("🔌 Desconectado.")
        except Exception as e:
            self._log(f"⚠️  Erro ao desconectar: {e}")
        self._set_conectado(False)

    # ─── GAVETA ────────────────────────────────
    def _abrir_gaveta(self):
        if not self.conn:
            messagebox.showwarning("Aviso", "Conecte à impressora primeiro.")
            return
        threading.Thread(target=self._abrir_gaveta_thread, daemon=True).start()

    def _abrir_gaveta_thread(self):
        try:
            cmd_map = {"cmd1": GAVETA_CMD_1, "cmd2": GAVETA_CMD_2, "cmd3": GAVETA_CMD_3}
            self._send(cmd_map[self.cmd_var.get()])
            self._log(f"🔓 Gaveta aberta! ({self.cmd_var.get().upper()})")
        except Exception as e:
            self._log(f"❌ Erro ao abrir gaveta: {e}")
            self.after(0, lambda: self._set_conectado(False))

    # ─── TESTE DE IMPRESSÃO ────────────────────
    def _imprimir_teste(self):
        if not self.conn:
            return
        threading.Thread(target=self._imprimir_thread, daemon=True).start()

    def _imprimir_thread(self):
        try:
            ticket  = INIT_CMD
            ticket += bytes([0x1B, 0x61, 0x01])
            ticket += bytes([0x1B, 0x21, 0x30])
            ticket += "TESTE DE IMPRESSAO\n".encode("latin-1")
            ticket += bytes([0x1B, 0x21, 0x00])
            ticket += "--------------------------------\n".encode("latin-1")
            ticket += time.strftime("Data: %d/%m/%Y %H:%M:%S\n").encode("latin-1")
            ticket += "Gaveta: CONECTADA\n".encode("latin-1")
            ticket += "--------------------------------\n".encode("latin-1")
            ticket += bytes([0x0A, 0x0A, 0x0A])
            ticket += bytes([0x1D, 0x56, 0x41, 0x00])
            self._send(ticket)
            self._log("🖨️  Cupom de teste enviado!")
        except Exception as e:
            self._log(f"❌ Erro ao imprimir: {e}")


if __name__ == "__main__":
    app = GavetaApp()
    app.mainloop()